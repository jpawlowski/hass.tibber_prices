"""Enhanced coordinator for fetching Tibber price data with comprehensive caching."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import date, datetime

    from homeassistant.config_entries import ConfigEntry

    from .listeners import TimeServiceCallback

from custom_components.tibber_prices.api import (
    TibberPricesApiClient,
    TibberPricesApiClientAuthenticationError,
    TibberPricesApiClientCommunicationError,
    TibberPricesApiClientError,
)
from custom_components.tibber_prices.const import DOMAIN
from custom_components.tibber_prices.utils.price import (
    find_price_data_for_interval,
)
from homeassistant.exceptions import ConfigEntryAuthFailed

from . import helpers
from .constants import (
    STORAGE_VERSION,
    UPDATE_INTERVAL,
)
from .data_fetching import TibberPricesDataFetcher
from .data_transformation import TibberPricesDataTransformer
from .listeners import TibberPricesListenerManager
from .midnight_handler import TibberPricesMidnightHandler
from .periods import TibberPricesPeriodCalculator
from .time_service import TibberPricesTimeService

_LOGGER = logging.getLogger(__name__)

# Lifecycle state transition thresholds
FRESH_TO_CACHED_SECONDS = 300  # 5 minutes


def get_connection_state(coordinator: TibberPricesDataUpdateCoordinator) -> bool | None:
    """
    Determine API connection state based on lifecycle and exceptions.

    This is the source of truth for the connection binary sensor.
    It ensures consistency between lifecycle_status and connection state.

    Returns:
        True: Connected and working (cached or fresh data)
        False: Connection failed or auth failed
        None: Unknown state (no data yet, initializing)

    Logic:
        - Auth failures → definitively disconnected (False)
        - Other errors with cached data → considered connected (True, using cache)
        - No errors with data → connected (True)
        - No data and no error → initializing (None)

    """
    # Auth failures = definitively disconnected
    # User must provide new token via reauth flow
    if isinstance(coordinator.last_exception, ConfigEntryAuthFailed):
        return False

    # Other errors but cache available = considered connected (using cached data as fallback)
    # This shows "on" but lifecycle_status will show "error" to indicate degraded operation
    if coordinator.last_exception and coordinator.data:
        return True

    # No error and data available = connected
    if coordinator.data:
        return True

    # No data and no error = initializing (unknown state)
    return None


# =============================================================================
# TIMER SYSTEM - Three independent update mechanisms:
# =============================================================================
#
# Timer #1: DataUpdateCoordinator (HA's built-in, every UPDATE_INTERVAL)
#   - Purpose: Check if API data needs updating, fetch if necessary
#   - Trigger: _async_update_data()
#   - What it does:
#     * Checks for midnight turnover FIRST (prevents race condition with Timer #2)
#     * If turnover needed: Rotates data, saves cache, notifies entities, returns
#     * Checks _should_update_price_data() (tomorrow missing? interval passed?)
#     * Fetches fresh data from API if needed
#     * Uses cached data otherwise (fast path)
#     * Transforms data only when needed (config change, new data, midnight)
#   - Load distribution:
#     * Start time varies per installation → natural distribution
#     * Tomorrow data check adds 0-30s random delay → prevents thundering herd
#   - Midnight coordination:
#     * Atomic check using _check_midnight_turnover_needed(now)
#     * If turnover needed, performs it and returns early
#     * Timer #2 will see turnover already done and skip
#
# Timer #2: Quarter-Hour Refresh (exact :00, :15, :30, :45 boundaries)
#   - Purpose: Update time-sensitive entity states at interval boundaries
#   - Trigger: _handle_quarter_hour_refresh()
#   - What it does:
#     * Checks for midnight turnover (atomic check, coordinates with Timer #1)
#     * If Timer #1 already did turnover → skip gracefully
#     * If turnover needed → performs it, saves cache, notifies all entities
#     * Otherwise → only notifies time-sensitive entities (fast path)
#   - Midnight coordination:
#     * Uses same atomic check as Timer #1
#     * Whoever runs first does turnover, the other skips
#     * No race condition possible (date comparison is atomic)
#
# Timer #3: Minute Refresh (every minute)
#   - Purpose: Update countdown/progress sensors
#   - Trigger: _handle_minute_refresh()
#   - What it does:
#     * Notifies minute-update entities (remaining_minutes, progress)
#     * Does NOT fetch data or transform - uses existing cache
#     * No midnight handling (not relevant for timing sensors)
#
# Midnight Turnover Coordination:
#   - Both Timer #1 and Timer #2 check for midnight turnover
#   - Atomic check: _check_midnight_turnover_needed(now)
#     Returns True if current_date > _last_midnight_turnover_check.date()
#     Returns False if already done today
#   - Whoever runs first (Timer #1 or Timer #2) performs turnover:
#     Calls _perform_midnight_data_rotation(now)
#     Updates _last_midnight_turnover_check and _last_actual_turnover to current time
#   - The other timer sees turnover already done and skips
#   - No locks needed - date comparison is naturally atomic
#   - No race condition possible - Python datetime.date() comparison is thread-safe
#   - _last_transformation_time is separate and tracks when data was last transformed (for cache)
#
#   CRITICAL - Dual Listener System:
#   After midnight turnover, BOTH listener groups must be notified:
#   1. Normal listeners (async_update_listeners) - standard HA entities
#   2. Time-sensitive listeners (_async_update_time_sensitive_listeners) - quarter-hour entities
#
#   Why? Entities like best_price_period and peak_price_period register as time-sensitive
#   listeners and won't update if only async_update_listeners() is called. This caused
#   the bug where period binary sensors showed stale data until the next quarter-hour
#   refresh at 00:15 (they were updated then because Timer #2 explicitly calls
#   _async_update_time_sensitive_listeners in its normal flow).
#
# =============================================================================


class TibberPricesDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Enhanced coordinator with main/subentry pattern and comprehensive caching."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api_client: TibberPricesApiClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

        self.config_entry = config_entry

        # Get home_id from config entry
        self._home_id = config_entry.data.get("home_id", "")
        if not self._home_id:
            _LOGGER.error("No home_id found in config entry %s", config_entry.entry_id)

        # Use the API client from runtime_data (created in __init__.py with proper TOKEN handling)
        self.api = api_client

        # Storage for persistence
        storage_key = f"{DOMAIN}.{config_entry.entry_id}"
        self._store = Store(hass, STORAGE_VERSION, storage_key)

        # Log prefix for identifying this coordinator instance
        self._log_prefix = f"[{config_entry.title}]"

        # Note: In the new architecture, all coordinators (parent + subentries) fetch their own data
        # No distinction between "main" and "sub" coordinators anymore

        # Initialize time service (single source of truth for all time operations)
        self.time = TibberPricesTimeService()

        # Set time on API client (needed for rate limiting)
        self.api.time = self.time

        # Initialize helper modules
        self._listener_manager = TibberPricesListenerManager(hass, self._log_prefix)
        self._midnight_handler = TibberPricesMidnightHandler()
        self._data_fetcher = TibberPricesDataFetcher(
            api=self.api,
            store=self._store,
            log_prefix=self._log_prefix,
            user_update_interval=timedelta(days=1),
            time=self.time,
        )
        self._data_transformer = TibberPricesDataTransformer(
            config_entry=config_entry,
            log_prefix=self._log_prefix,
            calculate_periods_fn=lambda price_info: self._period_calculator.calculate_periods_for_price_info(
                price_info
            ),
            time=self.time,
        )
        self._period_calculator = TibberPricesPeriodCalculator(
            config_entry=config_entry,
            log_prefix=self._log_prefix,
        )

        # Register options update listener to invalidate config caches
        config_entry.async_on_unload(config_entry.add_update_listener(self._handle_options_update))

        # Legacy compatibility - keep references for methods that access directly
        self._cached_user_data: dict[str, Any] | None = None
        self._last_user_update: datetime | None = None
        self._user_update_interval = timedelta(days=1)
        self._cached_price_data: dict[str, Any] | None = None
        self._last_price_update: datetime | None = None

        # Data lifecycle tracking for diagnostic sensor
        self._lifecycle_state: str = (
            "cached"  # Current state: cached, fresh, refreshing, searching_tomorrow, turnover_pending, error
        )
        self._api_calls_today: int = 0  # Counter for API calls today
        self._last_api_call_date: date | None = None  # Date of last API call (for daily reset)
        self._is_fetching: bool = False  # Flag to track active API fetch
        self._last_coordinator_update: datetime | None = None  # When Timer #1 last ran (_async_update_data)
        self._lifecycle_callbacks: list[Callable[[], None]] = []  # Push-update callbacks for lifecycle sensor

        # Start timers
        self._listener_manager.schedule_quarter_hour_refresh(self._handle_quarter_hour_refresh)
        self._listener_manager.schedule_minute_refresh(self._handle_minute_refresh)

    def _log(self, level: str, message: str, *args: Any, **kwargs: Any) -> None:
        """Log with coordinator-specific prefix."""
        prefixed_message = f"{self._log_prefix} {message}"
        getattr(_LOGGER, level)(prefixed_message, *args, **kwargs)

    async def _handle_options_update(self, _hass: HomeAssistant, _config_entry: ConfigEntry) -> None:
        """Handle options update by invalidating config caches."""
        self._log("debug", "Options updated, invalidating config caches")
        self._data_transformer.invalidate_config_cache()
        self._period_calculator.invalidate_config_cache()
        # Trigger a refresh to apply new configuration
        await self.async_request_refresh()

    @callback
    def async_add_time_sensitive_listener(self, update_callback: TimeServiceCallback) -> CALLBACK_TYPE:
        """
        Listen for time-sensitive updates that occur every quarter-hour.

        Time-sensitive entities (like current_interval_price, next_interval_price, etc.) should use this
        method instead of async_add_listener to receive updates at quarter-hour boundaries.

        Returns:
            Callback that can be used to remove the listener

        """
        return self._listener_manager.async_add_time_sensitive_listener(update_callback)

    @callback
    def _async_update_time_sensitive_listeners(self, time_service: TibberPricesTimeService) -> None:
        """
        Update all time-sensitive entities without triggering a full coordinator update.

        Args:
            time_service: TibberPricesTimeService instance with reference time for this update cycle

        """
        self._listener_manager.async_update_time_sensitive_listeners(time_service)

    @callback
    def async_add_minute_update_listener(self, update_callback: TimeServiceCallback) -> CALLBACK_TYPE:
        """
        Listen for minute-by-minute updates for timing sensors.

        Timing sensors (like best_price_remaining_minutes, peak_price_progress, etc.) should use this
        method to receive updates every minute for accurate countdown/progress tracking.

        Returns:
            Callback that can be used to remove the listener

        """
        return self._listener_manager.async_add_minute_update_listener(update_callback)

    @callback
    def _async_update_minute_listeners(self, time_service: TibberPricesTimeService) -> None:
        """
        Update all minute-update entities without triggering a full coordinator update.

        Args:
            time_service: TibberPricesTimeService instance with reference time for this update cycle

        """
        self._listener_manager.async_update_minute_listeners(time_service)

    @callback
    def _handle_quarter_hour_refresh(self, _now: datetime | None = None) -> None:
        """
        Handle quarter-hour entity refresh (Timer #2).

        This is a SYNCHRONOUS callback (decorated with @callback) - it runs in the event loop
        without async/await overhead because it performs only fast, non-blocking operations:
        - Midnight turnover check (date comparison, data rotation)
        - Listener notifications (entity state updates)

        NO I/O operations (no API calls, no file operations), so no need for async def.

        This is triggered at exact quarter-hour boundaries (:00, :15, :30, :45).
        Does NOT fetch new data - only updates entity states based on existing cached data.
        """
        # Create LOCAL TimeService with fresh reference time for this refresh
        # Each timer has its own TimeService instance - no shared state between timers
        # This timer updates 30+ time-sensitive entities at quarter-hour boundaries
        # (Timer #3 handles timing entities separately - no overlap)
        time_service = TibberPricesTimeService()
        now = time_service.now()

        # Update shared coordinator time (used by Timer #1 and other operations)
        # This is safe because we're in a @callback (synchronous event loop)
        self.time = time_service

        # Update helper modules with fresh TimeService instance
        self.api.time = time_service
        self._data_fetcher.time = time_service
        self._data_transformer.time = time_service
        self._period_calculator.time = time_service

        self._log("debug", "[Timer #2] Quarter-hour refresh triggered at %s", now.isoformat())

        # Check if midnight has passed since last check
        midnight_turnover_performed = self._check_and_handle_midnight_turnover(now)

        if midnight_turnover_performed:
            # Midnight turnover was performed by THIS call (Timer #1 didn't run yet)
            self._log("info", "[Timer #2] Midnight turnover performed, entities updated")
            # Schedule cache save asynchronously (we're in a callback)
            self.hass.async_create_task(self._store_cache())
            # async_update_listeners() was already called in _check_and_handle_midnight_turnover
            # This includes time-sensitive listeners, so skip regular update to avoid double-update
        else:
            # Regular quarter-hour refresh - only update time-sensitive entities
            # (Midnight turnover was either not needed, or already done by Timer #1)
            # Pass local time_service to entities (not self.time which could be overwritten)
            self._async_update_time_sensitive_listeners(time_service)

    @callback
    def _handle_minute_refresh(self, _now: datetime | None = None) -> None:
        """
        Handle 30-second entity refresh for timing sensors (Timer #3).

        This is a SYNCHRONOUS callback (decorated with @callback) - it runs in the event loop
        without async/await overhead because it performs only fast, non-blocking operations:
        - Listener notifications for timing sensors (remaining_minutes, progress)

        NO I/O operations (no API calls, no file operations), so no need for async def.
        Runs every 30 seconds to keep sensor values in sync with HA frontend display.

        This runs every 30 seconds to update countdown/progress sensors.
        Timing calculations use rounded minutes matching HA's relative time display.
        Does NOT fetch new data - only updates entity states based on existing cached data.
        """
        # Create LOCAL TimeService with fresh reference time for this 30-second refresh
        # Each timer has its own TimeService instance - no shared state between timers
        # Timer #2 updates 30+ time-sensitive entities (prices, levels, timestamps)
        # Timer #3 updates 6 timing entities (remaining_minutes, progress, next_in_minutes)
        # NO overlap - entities are registered with either Timer #2 OR Timer #3, never both
        time_service = TibberPricesTimeService()

        # Only log at debug level to avoid log spam (this runs every 30 seconds)
        self._log("debug", "[Timer #3] 30-second refresh for timing sensors")

        # Update only minute-update entities (remaining_minutes, progress, etc.)
        # Pass local time_service to entities (not self.time which could be overwritten)
        self._async_update_minute_listeners(time_service)

    def _check_midnight_turnover_needed(self, now: datetime) -> bool:
        """
        Check if midnight turnover is needed (atomic check, no side effects).

        This is called by BOTH Timer #1 and Timer #2 to coordinate turnover.
        Returns True only if turnover hasn't been performed yet today.

        Args:
            now: Current datetime

        Returns:
            True if midnight turnover is needed, False if already done

        """
        # Initialize handler on first use
        if self._midnight_handler.last_check_time is None:
            self._midnight_handler.update_check_time(now)
            return False

        # Delegate to midnight handler
        return self._midnight_handler.is_turnover_needed(now)

    def _perform_midnight_data_rotation(self, now: datetime) -> None:
        """
        Perform midnight data rotation on cached data (side effects).

        This rotates yesterday/today/tomorrow and updates coordinator data.
        Called by whoever detects midnight first (Timer #1 or Timer #2).

        IMPORTANT: This method is NOT @callback because it modifies shared state.
        Call this from async context only to ensure proper serialization.

        Args:
            now: Current datetime

        """
        current_date = now.date()
        last_check_date = (
            self._midnight_handler.last_check_time.date() if self._midnight_handler.last_check_time else current_date
        )

        self._log(
            "debug",
            "Performing midnight turnover: last_check=%s, current=%s",
            last_check_date,
            current_date,
        )

        # With flat interval list architecture, no rotation needed!
        # get_intervals_for_day_offsets() automatically filters by date.
        # Just update coordinator's data to trigger entity updates.
        if self.data and self._cached_price_data:
            # Re-transform data to ensure enrichment is refreshed
            self.data = self._transform_data(self._cached_price_data)

            # CRITICAL: Update _last_price_update to current time after midnight
            # This prevents cache_validity from showing "date_mismatch" after midnight
            # The data is still valid (just rotated today→yesterday, tomorrow→today)
            # Update timestamp to reflect that the data is current for the new day
            self._last_price_update = now

        # Mark turnover as done for today (atomic update)
        self._midnight_handler.mark_turnover_done(now)

    @callback
    def _check_and_handle_midnight_turnover(self, now: datetime) -> bool:
        """
        Check if midnight has passed and perform data rotation if needed.

        This is called by Timer #2 (quarter-hour refresh) to ensure timely rotation
        without waiting for the next API update cycle.

        Coordinates with Timer #1 using atomic check on _last_midnight_check date.
        If Timer #1 already performed turnover, this skips gracefully.

        Returns:
            True if midnight turnover was performed by THIS call, False otherwise

        """
        # Check if turnover is needed (atomic, no side effects)
        if not self._check_midnight_turnover_needed(now):
            # Already done today (by Timer #1 or previous Timer #2 call)
            return False

        # Turnover needed - perform it
        # Note: We need to schedule this as a task because _perform_midnight_data_rotation
        # is not a callback and may need async operations
        self._log("info", "[Timer #2] Midnight turnover detected, performing data rotation")
        self._perform_midnight_data_rotation(now)

        # CRITICAL: Notify BOTH listener groups after midnight turnover
        # - async_update_listeners(): Notifies normal entities (via HA's DataUpdateCoordinator)
        # - async_update_time_sensitive_listeners(): Notifies time-sensitive entities (custom system)
        # Without both calls, period binary sensors (best_price_period, peak_price_period)
        # won't update because they're time-sensitive listeners, not normal listeners.
        self.async_update_listeners()

        # Create TimeService with fresh reference time for time-sensitive entity updates
        time_service = TibberPricesTimeService()
        self._async_update_time_sensitive_listeners(time_service)

        return True

    async def async_shutdown(self) -> None:
        """
        Shut down the coordinator and clean up timers.

        Cancels all three timer types:
        - Timer #1: API polling (coordinator update timer)
        - Timer #2: Quarter-hour entity updates
        - Timer #3: Minute timing sensor updates

        Also saves cache to persist any unsaved changes.
        """
        # Cancel all timers first
        self._listener_manager.cancel_timers()

        # Save cache to persist any unsaved data
        # This ensures we don't lose data if HA is shutting down
        try:
            await self._store_cache()
            self._log("debug", "Cache saved during shutdown")
        except OSError as err:
            # Log but don't raise - shutdown should complete even if cache save fails
            self._log("error", "Failed to save cache during shutdown: %s", err)

    async def _async_update_data(self) -> dict[str, Any]:
        """
        Fetch data from Tibber API (called by DataUpdateCoordinator timer).

        This is Timer #1 (HA's built-in coordinator timer, every 15 min).
        """
        self._log("debug", "[Timer #1] DataUpdateCoordinator check triggered")

        # Track when Timer #1 ran (for next_api_poll calculation)
        self._last_coordinator_update = self.time.now()

        # Create TimeService with fresh reference time for this update cycle
        self.time = TibberPricesTimeService()
        current_time = self.time.now()

        # Transition lifecycle state from "fresh" to "cached" if enough time passed
        # (5 minutes threshold defined in lifecycle calculator)
        if self._lifecycle_state == "fresh" and self._last_price_update:
            age = current_time - self._last_price_update
            if age.total_seconds() > FRESH_TO_CACHED_SECONDS:
                self._lifecycle_state = "cached"

        # Update helper modules with fresh TimeService instance
        self.api.time = self.time
        self._data_fetcher.time = self.time
        self._data_transformer.time = self.time
        self._period_calculator.time = self.time

        # Load cache if not already loaded
        if self._cached_price_data is None and self._cached_user_data is None:
            await self.load_cache()

        # Initialize midnight handler on first run
        if self._midnight_handler.last_check_time is None:
            self._midnight_handler.update_check_time(current_time)

        # CRITICAL: Check for midnight turnover FIRST (before any data operations)
        # This prevents race condition with Timer #2 (quarter-hour refresh)
        # Whoever runs first (Timer #1 or Timer #2) performs turnover, the other skips
        midnight_turnover_needed = self._check_midnight_turnover_needed(current_time)
        if midnight_turnover_needed:
            self._log("info", "[Timer #1] Midnight turnover detected, performing data rotation")
            self._perform_midnight_data_rotation(current_time)
            # After rotation, save cache and notify entities
            await self._store_cache()

            # CRITICAL: Notify time-sensitive listeners explicitly
            # When Timer #1 performs turnover, returning self.data will trigger
            # async_update_listeners() (normal listeners) automatically via DataUpdateCoordinator.
            # But time-sensitive listeners (like best_price_period, peak_price_period)
            # won't be notified unless we explicitly call their update method.
            # This ensures ALL entities see the updated periods after midnight turnover.
            time_service = TibberPricesTimeService()
            self._async_update_time_sensitive_listeners(time_service)

            # Return current data (enriched after rotation) to trigger entity updates
            if self.data:
                return self.data

        try:
            # Reset API call counter if day changed
            current_date = current_time.date()
            if self._last_api_call_date != current_date:
                self._api_calls_today = 0
                self._last_api_call_date = current_date

            # Track last_price_update timestamp before fetch to detect if data actually changed
            old_price_update = self._last_price_update

            result = await self._data_fetcher.handle_main_entry_update(
                current_time,
                self._home_id,
                self._transform_data,
            )

            # CRITICAL: Sync cached data after API call
            # handle_main_entry_update() updates data_fetcher's cache, we need to sync:
            # 1. cached_user_data (for new integrations, may be fetched via update_user_data_if_needed())
            # 2. cached_price_data (CRITICAL: contains tomorrow data, needed for _needs_tomorrow_data())
            # 3. _last_price_update (for lifecycle tracking: cache age, fresh state detection)
            self._cached_user_data = self._data_fetcher.cached_user_data
            self._cached_price_data = self._data_fetcher.cached_price_data
            self._last_price_update = self._data_fetcher._last_price_update  # noqa: SLF001 - Sync for lifecycle tracking

            # Update lifecycle tracking only if we fetched NEW data (timestamp changed)
            # This prevents recorder spam from state changes when returning cached data
            if self._last_price_update != old_price_update:
                self._api_calls_today += 1
                self._lifecycle_state = "fresh"  # Data just fetched
                # No separate lifecycle notification needed - normal async_update_listeners()
                # will trigger all entities (including lifecycle sensor) after this return
        except (
            TibberPricesApiClientAuthenticationError,
            TibberPricesApiClientCommunicationError,
            TibberPricesApiClientError,
        ) as err:
            # Reset lifecycle state on error
            self._is_fetching = False
            self._lifecycle_state = "error"
            # No separate lifecycle notification needed - error case returns data
            # which triggers normal async_update_listeners()
            return await self._data_fetcher.handle_api_error(
                err,
                self._transform_data,
            )
        else:
            return result

    async def load_cache(self) -> None:
        """Load cached data from storage."""
        await self._data_fetcher.load_cache()
        # Sync legacy references
        self._cached_price_data = self._data_fetcher.cached_price_data
        self._cached_user_data = self._data_fetcher.cached_user_data
        self._last_price_update = self._data_fetcher._last_price_update  # noqa: SLF001 - Sync for lifecycle tracking
        self._last_user_update = self._data_fetcher._last_user_update  # noqa: SLF001 - Sync for lifecycle tracking

        # CRITICAL: Restore midnight handler state from cache
        # If cache is from today, assume turnover already happened at midnight
        # This allows proper turnover detection after HA restart
        if self._last_price_update:
            cache_date = self.time.as_local(self._last_price_update).date()
            today_date = self.time.as_local(self.time.now()).date()
            if cache_date == today_date:
                # Cache is from today, so midnight turnover already happened
                today_midnight = self.time.as_local(self.time.now()).replace(hour=0, minute=0, second=0, microsecond=0)
                # Restore handler state: mark today's midnight as last turnover
                self._midnight_handler.mark_turnover_done(today_midnight)

    async def _store_cache(self) -> None:
        """Store cache data."""
        await self._data_fetcher.store_cache(self._midnight_handler.last_check_time)

    def _needs_tomorrow_data(self) -> bool:
        """Check if tomorrow data is missing or invalid."""
        return helpers.needs_tomorrow_data(self._cached_price_data)

    def _has_valid_tomorrow_data(self) -> bool:
        """Check if we have valid tomorrow data (inverse of _needs_tomorrow_data)."""
        return not self._needs_tomorrow_data()

    @callback
    def _merge_cached_data(self) -> dict[str, Any]:
        """Merge cached data into the expected format for main entry."""
        if not self._cached_price_data:
            return {}
        return self._transform_data(self._cached_price_data)

    def _get_threshold_percentages(self) -> dict[str, int]:
        """Get threshold percentages from config options."""
        return self._data_transformer.get_threshold_percentages()

    def _calculate_periods_for_price_info(self, price_info: dict[str, Any]) -> dict[str, Any]:
        """Calculate periods (best price and peak price) for the given price info."""
        return self._period_calculator.calculate_periods_for_price_info(price_info)

    def _transform_data(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Transform raw data for main entry (aggregated view of all homes)."""
        # Delegate complete transformation to DataTransformer (enrichment + periods)
        # DataTransformer handles its own caching internally
        return self._data_transformer.transform_data(raw_data)

    # --- Methods expected by sensors and services ---

    def get_home_data(self, home_id: str) -> dict[str, Any] | None:
        """Get data for a specific home (returns this coordinator's data if home_id matches)."""
        if not self.data:
            return None

        # In new architecture, each coordinator manages one home only
        # Return data only if requesting this coordinator's home
        if home_id == self._home_id:
            return self.data

        return None

    def get_current_interval(self) -> dict[str, Any] | None:
        """Get the price data for the current interval."""
        if not self.data:
            return None

        if not self.data:
            return None

        now = self.time.now()
        return find_price_data_for_interval(self.data, now, time=self.time)

    async def refresh_user_data(self) -> bool:
        """Force refresh of user data and return True if data was updated."""
        try:
            current_time = self.time.now()
            self._log("info", "Forcing user data refresh (bypassing cache)")

            # Force update by calling API directly (bypass cache check)
            user_data = await self.api.async_get_viewer_details()
            self._cached_user_data = user_data
            self._last_user_update = current_time
            self._log("info", "User data refreshed successfully - found %d home(s)", len(user_data.get("homes", [])))

            await self._store_cache()
        except (
            TibberPricesApiClientAuthenticationError,
            TibberPricesApiClientCommunicationError,
            TibberPricesApiClientError,
        ):
            return False
        else:
            return True

    def get_user_profile(self) -> dict[str, Any]:
        """Get user profile information."""
        return {
            "last_updated": self._last_user_update,
            "cached_user_data": self._cached_user_data is not None,
        }

    def get_user_homes(self) -> list[dict[str, Any]]:
        """Get list of user homes."""
        if not self._cached_user_data:
            return []
        viewer = self._cached_user_data.get("viewer", {})
        return viewer.get("homes", [])
