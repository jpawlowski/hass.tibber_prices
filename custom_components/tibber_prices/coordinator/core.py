"""Enhanced coordinator for fetching Tibber price data with comprehensive caching."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

if TYPE_CHECKING:
    from datetime import date, datetime

    from homeassistant.config_entries import ConfigEntry

    from .listeners import TimeServiceCallback

from custom_components.tibber_prices import const as _const
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

from . import helpers
from .constants import (
    STORAGE_VERSION,
    UPDATE_INTERVAL,
)
from .data_fetching import TibberPricesDataFetcher
from .data_transformation import TibberPricesDataTransformer
from .listeners import TibberPricesListenerManager
from .periods import TibberPricesPeriodCalculator
from .time_service import TibberPricesTimeService

_LOGGER = logging.getLogger(__name__)

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
#     Returns True if current_date > _last_midnight_check.date()
#     Returns False if already done today
#   - Whoever runs first (Timer #1 or Timer #2) performs turnover:
#     Calls _perform_midnight_data_rotation(now)
#     Updates _last_midnight_check to current time
#   - The other timer sees turnover already done and skips
#   - No locks needed - date comparison is naturally atomic
#   - No race condition possible - Python datetime.date() comparison is thread-safe
#
# =============================================================================


class TibberPricesDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Enhanced coordinator with main/subentry pattern and comprehensive caching."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        version: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

        self.config_entry = config_entry
        self.api = TibberPricesApiClient(
            access_token=config_entry.data[CONF_ACCESS_TOKEN],
            session=aiohttp_client.async_get_clientsession(hass),
            version=version,
        )

        # Storage for persistence
        storage_key = f"{DOMAIN}.{config_entry.entry_id}"
        self._store = Store(hass, STORAGE_VERSION, storage_key)

        # Log prefix for identifying this coordinator instance
        self._log_prefix = f"[{config_entry.title}]"

        # Track if this is the main entry (first one created)
        self._is_main_entry = not self._has_existing_main_coordinator()

        # Initialize time service (single source of truth for all time operations)
        self.time = TibberPricesTimeService()

        # Set time on API client (needed for rate limiting)
        self.api.time = self.time

        # Initialize helper modules
        self._listener_manager = TibberPricesListenerManager(hass, self._log_prefix)
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
            perform_turnover_fn=self._perform_midnight_turnover,
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
        self._cached_transformed_data: dict[str, Any] | None = None
        self._last_transformation_config: dict[str, Any] | None = None
        self._last_midnight_check: datetime | None = None

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
        current_date = now.date()

        # First time check - initialize (no turnover needed)
        if self._last_midnight_check is None:
            return False

        last_check_date = self._last_midnight_check.date()

        # Turnover needed if we've crossed into a new day
        return current_date > last_check_date

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
        last_check_date = self._last_midnight_check.date() if self._last_midnight_check else current_date

        self._log(
            "debug",
            "Performing midnight turnover: last_check=%s, current=%s",
            last_check_date,
            current_date,
        )

        # Perform rotation on cached data if available
        if self._cached_price_data and "homes" in self._cached_price_data:
            for home_id, home_data in self._cached_price_data["homes"].items():
                if "price_info" in home_data:
                    price_info = home_data["price_info"]
                    rotated = self._perform_midnight_turnover(price_info)
                    home_data["price_info"] = rotated
                    self._log("debug", "Rotated price data for home %s", home_id)

            # Update coordinator's data with enriched rotated data
            if self.data:
                # Re-transform data to ensure enrichment is applied to rotated data
                if self.is_main_entry():
                    self.data = self._transform_data_for_main_entry(self._cached_price_data)
                else:
                    # For subentry, get fresh data from main coordinator after rotation
                    # Main coordinator will have performed rotation already
                    self.data["timestamp"] = now

        # Mark turnover as done for today (atomic update)
        self._last_midnight_check = now

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

        # Notify listeners about updated data
        self.async_update_listeners()

        return True

    async def async_shutdown(self) -> None:
        """Shut down the coordinator and clean up timers."""
        self._listener_manager.cancel_timers()

    def _has_existing_main_coordinator(self) -> bool:
        """Check if there's already a main coordinator in hass.data."""
        domain_data = self.hass.data.get(DOMAIN, {})
        return any(
            isinstance(coordinator, TibberPricesDataUpdateCoordinator) and coordinator.is_main_entry()
            for coordinator in domain_data.values()
        )

    def is_main_entry(self) -> bool:
        """Return True if this is the main entry that fetches data for all homes."""
        return self._is_main_entry

    async def _async_update_data(self) -> dict[str, Any]:
        """
        Fetch data from Tibber API (called by DataUpdateCoordinator timer).

        This is Timer #1 (HA's built-in coordinator timer, every 15 min).
        """
        self._log("debug", "[Timer #1] DataUpdateCoordinator check triggered")

        # Create TimeService with fresh reference time for this update cycle
        self.time = TibberPricesTimeService()
        current_time = self.time.now()

        # Update helper modules with fresh TimeService instance
        self.api.time = self.time
        self._data_fetcher.time = self.time
        self._data_transformer.time = self.time
        self._period_calculator.time = self.time

        # Load cache if not already loaded
        if self._cached_price_data is None and self._cached_user_data is None:
            await self.load_cache()

        # Initialize midnight check on first run
        if self._last_midnight_check is None:
            self._last_midnight_check = current_time

        # CRITICAL: Check for midnight turnover FIRST (before any data operations)
        # This prevents race condition with Timer #2 (quarter-hour refresh)
        # Whoever runs first (Timer #1 or Timer #2) performs turnover, the other skips
        midnight_turnover_needed = self._check_midnight_turnover_needed(current_time)
        if midnight_turnover_needed:
            self._log("info", "[Timer #1] Midnight turnover detected, performing data rotation")
            self._perform_midnight_data_rotation(current_time)
            # After rotation, save cache and notify entities
            await self._store_cache()
            # Return current data (enriched after rotation) to trigger entity updates
            if self.data:
                return self.data

        try:
            if self.is_main_entry():
                # Main entry fetches data for all homes
                configured_home_ids = self._get_configured_home_ids()
                result = await self._data_fetcher.handle_main_entry_update(
                    current_time,
                    configured_home_ids,
                    self._transform_data_for_main_entry,
                )
                # CRITICAL: Sync cached_user_data after API call (for new integrations without cache)
                # handle_main_entry_update() may have fetched user_data via update_user_data_if_needed()
                self._cached_user_data = self._data_fetcher.cached_user_data
                return result
            # Subentries get data from main coordinator
            return await self._handle_subentry_update()

        except (
            TibberPricesApiClientAuthenticationError,
            TibberPricesApiClientCommunicationError,
            TibberPricesApiClientError,
        ) as err:
            return await self._data_fetcher.handle_api_error(
                err,
                self._transform_data_for_main_entry,
            )

    async def _handle_subentry_update(self) -> dict[str, Any]:
        """Handle update for subentry - get data from main coordinator."""
        main_data = await self._get_data_from_main_coordinator()
        return self._transform_data_for_subentry(main_data)

    async def _get_data_from_main_coordinator(self) -> dict[str, Any]:
        """Get data from the main coordinator (subentries only)."""
        # Find the main coordinator
        main_coordinator = self._find_main_coordinator()
        if not main_coordinator:
            msg = "Main coordinator not found"
            raise UpdateFailed(msg)

        # Wait for main coordinator to have data
        if main_coordinator.data is None:
            main_coordinator.async_set_updated_data({})

        # Return the main coordinator's data
        return main_coordinator.data or {}

    def _find_main_coordinator(self) -> TibberPricesDataUpdateCoordinator | None:
        """Find the main coordinator that fetches data for all homes."""
        domain_data = self.hass.data.get(DOMAIN, {})
        for coordinator in domain_data.values():
            if (
                isinstance(coordinator, TibberPricesDataUpdateCoordinator)
                and coordinator.is_main_entry()
                and coordinator != self
            ):
                return coordinator
        return None

    def _get_configured_home_ids(self) -> set[str]:
        """Get all home_ids that have active config entries (main + subentries)."""
        home_ids = helpers.get_configured_home_ids(self.hass)

        self._log(
            "debug",
            "Found %d configured home(s): %s",
            len(home_ids),
            ", ".join(sorted(home_ids)),
        )

        return home_ids

    async def load_cache(self) -> None:
        """Load cached data from storage."""
        await self._data_fetcher.load_cache()
        # Sync legacy references
        self._cached_price_data = self._data_fetcher.cached_price_data
        self._cached_user_data = self._data_fetcher.cached_user_data

    def _perform_midnight_turnover(self, price_info: dict[str, Any]) -> dict[str, Any]:
        """
        Perform midnight turnover on price data.

        Moves: today → yesterday, tomorrow → today, clears tomorrow.

        This handles cases where:
        - Server was running through midnight
        - Cache is being refreshed and needs proper day rotation

        Args:
            price_info: The price info dict with 'today', 'tomorrow', 'yesterday' keys

        Returns:
            Updated price_info with rotated day data

        """
        return helpers.perform_midnight_turnover(price_info, time=self.time)

    async def _store_cache(self) -> None:
        """Store cache data."""
        await self._data_fetcher.store_cache(self._last_midnight_check)

    def _needs_tomorrow_data(self, tomorrow_date: date) -> bool:
        """Check if tomorrow data is missing or invalid."""
        return helpers.needs_tomorrow_data(self._cached_price_data, tomorrow_date)

    def _has_valid_tomorrow_data(self, tomorrow_date: date) -> bool:
        """Check if we have valid tomorrow data (inverse of _needs_tomorrow_data)."""
        return not self._needs_tomorrow_data(tomorrow_date)

    @callback
    def _merge_cached_data(self) -> dict[str, Any]:
        """Merge cached data into the expected format for main entry."""
        if not self._cached_price_data:
            return {}
        return self._transform_data_for_main_entry(self._cached_price_data)

    def _get_threshold_percentages(self) -> dict[str, int]:
        """Get threshold percentages from config options."""
        return self._data_transformer.get_threshold_percentages()

    def _calculate_periods_for_price_info(self, price_info: dict[str, Any]) -> dict[str, Any]:
        """Calculate periods (best price and peak price) for the given price info."""
        return self._period_calculator.calculate_periods_for_price_info(price_info)

    def _get_current_transformation_config(self) -> dict[str, Any]:
        """Get current configuration that affects data transformation."""
        return {
            "thresholds": self._get_threshold_percentages(),
            "volatility_thresholds": {
                "moderate": self.config_entry.options.get(_const.CONF_VOLATILITY_THRESHOLD_MODERATE, 15.0),
                "high": self.config_entry.options.get(_const.CONF_VOLATILITY_THRESHOLD_HIGH, 25.0),
                "very_high": self.config_entry.options.get(_const.CONF_VOLATILITY_THRESHOLD_VERY_HIGH, 40.0),
            },
            "best_price_config": {
                "flex": self.config_entry.options.get(_const.CONF_BEST_PRICE_FLEX, 15.0),
                "max_level": self.config_entry.options.get(_const.CONF_BEST_PRICE_MAX_LEVEL, "NORMAL"),
                "min_period_length": self.config_entry.options.get(_const.CONF_BEST_PRICE_MIN_PERIOD_LENGTH, 4),
                "min_distance_from_avg": self.config_entry.options.get(
                    _const.CONF_BEST_PRICE_MIN_DISTANCE_FROM_AVG, -5.0
                ),
                "max_level_gap_count": self.config_entry.options.get(_const.CONF_BEST_PRICE_MAX_LEVEL_GAP_COUNT, 0),
                "enable_min_periods": self.config_entry.options.get(_const.CONF_ENABLE_MIN_PERIODS_BEST, False),
                "min_periods": self.config_entry.options.get(_const.CONF_MIN_PERIODS_BEST, 2),
                "relaxation_attempts": self.config_entry.options.get(_const.CONF_RELAXATION_ATTEMPTS_BEST, 4),
            },
            "peak_price_config": {
                "flex": self.config_entry.options.get(_const.CONF_PEAK_PRICE_FLEX, 15.0),
                "min_level": self.config_entry.options.get(_const.CONF_PEAK_PRICE_MIN_LEVEL, "HIGH"),
                "min_period_length": self.config_entry.options.get(_const.CONF_PEAK_PRICE_MIN_PERIOD_LENGTH, 4),
                "min_distance_from_avg": self.config_entry.options.get(
                    _const.CONF_PEAK_PRICE_MIN_DISTANCE_FROM_AVG, 5.0
                ),
                "max_level_gap_count": self.config_entry.options.get(_const.CONF_PEAK_PRICE_MAX_LEVEL_GAP_COUNT, 0),
                "enable_min_periods": self.config_entry.options.get(_const.CONF_ENABLE_MIN_PERIODS_PEAK, False),
                "min_periods": self.config_entry.options.get(_const.CONF_MIN_PERIODS_PEAK, 2),
                "relaxation_attempts": self.config_entry.options.get(_const.CONF_RELAXATION_ATTEMPTS_PEAK, 4),
            },
        }

    def _should_retransform_data(self, current_time: datetime) -> bool:
        """Check if data transformation should be performed."""
        # No cached transformed data - must transform
        if self._cached_transformed_data is None:
            return True

        # Configuration changed - must retransform
        current_config = self._get_current_transformation_config()
        if current_config != self._last_transformation_config:
            self._log("debug", "Configuration changed, retransforming data")
            return True

        # Check for midnight turnover
        now_local = self.time.as_local(current_time)
        current_date = now_local.date()

        if self._last_midnight_check is None:
            return True

        last_check_local = self.time.as_local(self._last_midnight_check)
        last_check_date = last_check_local.date()

        if current_date != last_check_date:
            self._log("debug", "Midnight turnover detected, retransforming data")
            return True

        return False

    def _transform_data_for_main_entry(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Transform raw data for main entry (aggregated view of all homes)."""
        current_time = self.time.now()

        # Return cached transformed data if no retransformation needed
        if not self._should_retransform_data(current_time) and self._cached_transformed_data is not None:
            self._log("debug", "Using cached transformed data (no transformation needed)")
            return self._cached_transformed_data

        self._log("debug", "Transforming price data (enrichment only, periods calculated separately)")

        # Delegate actual transformation to DataTransformer (enrichment only)
        transformed_data = self._data_transformer.transform_data_for_main_entry(raw_data)

        # Add periods (calculated and cached separately by PeriodCalculator)
        if "priceInfo" in transformed_data:
            transformed_data["periods"] = self._calculate_periods_for_price_info(transformed_data["priceInfo"])

        # Cache the transformed data
        self._cached_transformed_data = transformed_data
        self._last_transformation_config = self._get_current_transformation_config()
        self._last_midnight_check = current_time

        return transformed_data

    def _transform_data_for_subentry(self, main_data: dict[str, Any]) -> dict[str, Any]:
        """Transform main coordinator data for subentry (home-specific view)."""
        current_time = self.time.now()

        # Return cached transformed data if no retransformation needed
        if not self._should_retransform_data(current_time) and self._cached_transformed_data is not None:
            self._log("debug", "Using cached transformed data (no transformation needed)")
            return self._cached_transformed_data

        self._log("debug", "Transforming price data for home (enrichment only, periods calculated separately)")

        home_id = self.config_entry.data.get("home_id")
        if not home_id:
            return main_data

        # Delegate actual transformation to DataTransformer (enrichment only)
        transformed_data = self._data_transformer.transform_data_for_subentry(main_data, home_id)

        # Add periods (calculated and cached separately by PeriodCalculator)
        if "priceInfo" in transformed_data:
            transformed_data["periods"] = self._calculate_periods_for_price_info(transformed_data["priceInfo"])

        # Cache the transformed data
        self._cached_transformed_data = transformed_data
        self._last_transformation_config = self._get_current_transformation_config()
        self._last_midnight_check = current_time

        return transformed_data

    # --- Methods expected by sensors and services ---

    def get_home_data(self, home_id: str) -> dict[str, Any] | None:
        """Get data for a specific home."""
        if not self.data:
            return None

        homes_data = self.data.get("homes", {})
        return homes_data.get(home_id)

    def get_current_interval(self) -> dict[str, Any] | None:
        """Get the price data for the current interval."""
        if not self.data:
            return None

        price_info = self.data.get("priceInfo", {})
        if not price_info:
            return None

        now = self.time.now()
        return find_price_data_for_interval(price_info, now, time=self.time)

    def get_all_intervals(self) -> list[dict[str, Any]]:
        """Get all price intervals (today + tomorrow)."""
        if not self.data:
            return []

        price_info = self.data.get("priceInfo", {})
        today_prices = price_info.get("today", [])
        tomorrow_prices = price_info.get("tomorrow", [])
        return today_prices + tomorrow_prices

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
