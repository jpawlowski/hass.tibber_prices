"""Enhanced coordinator for fetching Tibber price data with comprehensive caching."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.event import async_track_utc_time_change
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

from .api import (
    TibberPricesApiClient,
    TibberPricesApiClientAuthenticationError,
    TibberPricesApiClientCommunicationError,
    TibberPricesApiClientError,
)
from .const import (
    CONF_BEST_PRICE_FLEX,
    CONF_BEST_PRICE_MAX_LEVEL,
    CONF_BEST_PRICE_MAX_LEVEL_GAP_COUNT,
    CONF_BEST_PRICE_MIN_DISTANCE_FROM_AVG,
    CONF_BEST_PRICE_MIN_PERIOD_LENGTH,
    CONF_ENABLE_MIN_PERIODS_BEST,
    CONF_ENABLE_MIN_PERIODS_PEAK,
    CONF_MIN_PERIODS_BEST,
    CONF_MIN_PERIODS_PEAK,
    CONF_PEAK_PRICE_FLEX,
    CONF_PEAK_PRICE_MAX_LEVEL_GAP_COUNT,
    CONF_PEAK_PRICE_MIN_DISTANCE_FROM_AVG,
    CONF_PEAK_PRICE_MIN_LEVEL,
    CONF_PEAK_PRICE_MIN_PERIOD_LENGTH,
    CONF_PRICE_RATING_THRESHOLD_HIGH,
    CONF_PRICE_RATING_THRESHOLD_LOW,
    CONF_RELAXATION_ATTEMPTS_BEST,
    CONF_RELAXATION_ATTEMPTS_PEAK,
    CONF_RELAXATION_STEP_BEST,
    CONF_RELAXATION_STEP_PEAK,
    CONF_VOLATILITY_THRESHOLD_HIGH,
    CONF_VOLATILITY_THRESHOLD_MODERATE,
    CONF_VOLATILITY_THRESHOLD_VERY_HIGH,
    DEFAULT_BEST_PRICE_FLEX,
    DEFAULT_BEST_PRICE_MAX_LEVEL,
    DEFAULT_BEST_PRICE_MAX_LEVEL_GAP_COUNT,
    DEFAULT_BEST_PRICE_MIN_DISTANCE_FROM_AVG,
    DEFAULT_BEST_PRICE_MIN_PERIOD_LENGTH,
    DEFAULT_ENABLE_MIN_PERIODS_BEST,
    DEFAULT_ENABLE_MIN_PERIODS_PEAK,
    DEFAULT_MIN_PERIODS_BEST,
    DEFAULT_MIN_PERIODS_PEAK,
    DEFAULT_PEAK_PRICE_FLEX,
    DEFAULT_PEAK_PRICE_MAX_LEVEL_GAP_COUNT,
    DEFAULT_PEAK_PRICE_MIN_DISTANCE_FROM_AVG,
    DEFAULT_PEAK_PRICE_MIN_LEVEL,
    DEFAULT_PEAK_PRICE_MIN_PERIOD_LENGTH,
    DEFAULT_PRICE_RATING_THRESHOLD_HIGH,
    DEFAULT_PRICE_RATING_THRESHOLD_LOW,
    DEFAULT_RELAXATION_ATTEMPTS_BEST,
    DEFAULT_RELAXATION_ATTEMPTS_PEAK,
    DEFAULT_RELAXATION_STEP_BEST,
    DEFAULT_RELAXATION_STEP_PEAK,
    DEFAULT_VOLATILITY_THRESHOLD_HIGH,
    DEFAULT_VOLATILITY_THRESHOLD_MODERATE,
    DEFAULT_VOLATILITY_THRESHOLD_VERY_HIGH,
    DOMAIN,
    MIN_INTERVALS_FOR_GAP_TOLERANCE,
    PRICE_LEVEL_MAPPING,
)
from .period_utils import (
    PeriodConfig,
    calculate_periods_with_relaxation,
)
from .price_utils import (
    enrich_price_info_with_differences,
    find_price_data_for_interval,
)

_LOGGER = logging.getLogger(__name__)

# Storage version for storing data
STORAGE_VERSION = 1

# Update interval - fetch data every 15 minutes (when data is incomplete)
UPDATE_INTERVAL = timedelta(minutes=15)

# Update interval when all data is available - every 4 hours (reduce API calls)
UPDATE_INTERVAL_COMPLETE = timedelta(hours=4)

# Quarter-hour boundaries for entity state updates (minutes: 00, 15, 30, 45)
QUARTER_HOUR_BOUNDARIES = (0, 15, 30, 45)

# Hour after which tomorrow's price data is expected (13:00 local time)
TOMORROW_DATA_CHECK_HOUR = 13

# Entity keys that require quarter-hour updates (time-sensitive entities)
# These entities calculate values based on current time and need updates every 15 minutes
# All other entities only update when new API data arrives
TIME_SENSITIVE_ENTITY_KEYS = frozenset(
    {
        # Current/next/previous price sensors
        "current_interval_price",
        "next_interval_price",
        "previous_interval_price",
        # Current/next/previous price levels
        "current_interval_price_level",
        "next_interval_price_level",
        "previous_interval_price_level",
        # Rolling hour calculations (5-interval windows)
        "current_hour_average_price",
        "next_hour_average_price",
        "current_hour_price_level",
        "next_hour_price_level",
        # Current/next/previous price ratings
        "current_interval_price_rating",
        "next_interval_price_rating",
        "previous_interval_price_rating",
        "current_hour_price_rating",
        "next_hour_price_rating",
        # Future average sensors (rolling N-hour windows from next interval)
        "next_avg_1h",
        "next_avg_2h",
        "next_avg_3h",
        "next_avg_4h",
        "next_avg_5h",
        "next_avg_6h",
        "next_avg_8h",
        "next_avg_12h",
        # Price trend sensors
        "price_trend_1h",
        "price_trend_2h",
        "price_trend_3h",
        "price_trend_4h",
        "price_trend_5h",
        "price_trend_6h",
        "price_trend_8h",
        "price_trend_12h",
        # Trailing/leading 24h calculations (based on current interval)
        "trailing_price_average",
        "leading_price_average",
        "trailing_price_min",
        "trailing_price_max",
        "leading_price_min",
        "leading_price_max",
        # Binary sensors that check if current time is in a period
        "peak_price_period",
        "best_price_period",
        # Best/Peak price timestamp sensors (periods only change at interval boundaries)
        "best_price_end_time",
        "best_price_next_start_time",
        "peak_price_end_time",
        "peak_price_next_start_time",
    }
)

# Entities that require minute-by-minute updates (separate from quarter-hour updates)
# These are timing sensors that track countdown/progress within best/peak price periods
# Timestamp sensors (end_time, next_start_time) only need quarter-hour updates since periods
# can only change at interval boundaries
MINUTE_UPDATE_ENTITY_KEYS = frozenset(
    {
        # Best Price countdown/progress sensors (need minute updates)
        "best_price_remaining_minutes",
        "best_price_progress",
        "best_price_next_in_minutes",
        # Peak Price countdown/progress sensors (need minute updates)
        "peak_price_remaining_minutes",
        "peak_price_progress",
        "peak_price_next_in_minutes",
    }
)


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

        # User data cache (updated daily)
        self._cached_user_data: dict[str, Any] | None = None
        self._last_user_update: datetime | None = None
        self._user_update_interval = timedelta(days=1)

        # Price data cache
        self._cached_price_data: dict[str, Any] | None = None
        self._last_price_update: datetime | None = None

        # Track the last date we checked for midnight turnover
        self._last_midnight_check: datetime | None = None

        # Track if this is the main entry (first one created)
        self._is_main_entry = not self._has_existing_main_coordinator()

        # Log prefix for identifying this coordinator instance
        self._log_prefix = f"[{config_entry.title}]"

        # Quarter-hour entity refresh timer (runs at :00, :15, :30, :45)
        self._quarter_hour_timer_cancel: CALLBACK_TYPE | None = None

        # Minute-by-minute entity refresh timer (runs every minute for timing sensors)
        self._minute_timer_cancel: CALLBACK_TYPE | None = None

        # Selective listener system for time-sensitive entities
        # Regular listeners update on API data changes, time-sensitive listeners update every 15 minutes
        self._time_sensitive_listeners: list[CALLBACK_TYPE] = []

        # Minute-update listener system for timing sensors
        # These listeners update every minute to track progress/remaining time in periods
        self._minute_update_listeners: list[CALLBACK_TYPE] = []

        self._schedule_quarter_hour_refresh()
        self._schedule_minute_refresh()

    def _log(self, level: str, message: str, *args: Any, **kwargs: Any) -> None:
        """Log with coordinator-specific prefix."""
        prefixed_message = f"{self._log_prefix} {message}"
        getattr(_LOGGER, level)(prefixed_message, *args, **kwargs)

    @callback
    def async_add_time_sensitive_listener(self, update_callback: CALLBACK_TYPE) -> CALLBACK_TYPE:
        """
        Listen for time-sensitive updates that occur every quarter-hour.

        Time-sensitive entities (like current_interval_price, next_interval_price, etc.) should use this
        method instead of async_add_listener to receive updates at quarter-hour boundaries.

        Returns:
            Callback that can be used to remove the listener

        """
        self._time_sensitive_listeners.append(update_callback)

        def remove_listener() -> None:
            """Remove update listener."""
            if update_callback in self._time_sensitive_listeners:
                self._time_sensitive_listeners.remove(update_callback)

        return remove_listener

    @callback
    def _async_update_time_sensitive_listeners(self) -> None:
        """Update all time-sensitive entities without triggering a full coordinator update."""
        for update_callback in self._time_sensitive_listeners:
            update_callback()

        self._log(
            "debug",
            "Updated %d time-sensitive entities at quarter-hour boundary",
            len(self._time_sensitive_listeners),
        )

    @callback
    def async_add_minute_update_listener(self, update_callback: CALLBACK_TYPE) -> CALLBACK_TYPE:
        """
        Listen for minute-by-minute updates for timing sensors.

        Timing sensors (like best_price_remaining_minutes, peak_price_progress, etc.) should use this
        method to receive updates every minute for accurate countdown/progress tracking.

        Returns:
            Callback that can be used to remove the listener

        """
        self._minute_update_listeners.append(update_callback)

        def remove_listener() -> None:
            """Remove update listener."""
            if update_callback in self._minute_update_listeners:
                self._minute_update_listeners.remove(update_callback)

        return remove_listener

    @callback
    def _async_update_minute_listeners(self) -> None:
        """Update all minute-update entities without triggering a full coordinator update."""
        for update_callback in self._minute_update_listeners:
            update_callback()

        self._log(
            "debug",
            "Updated %d minute-update entities",
            len(self._minute_update_listeners),
        )

    def _schedule_quarter_hour_refresh(self) -> None:
        """Schedule the next quarter-hour entity refresh using Home Assistant's time tracking."""
        # Cancel any existing timer
        if self._quarter_hour_timer_cancel:
            self._quarter_hour_timer_cancel()
            self._quarter_hour_timer_cancel = None

        # Use Home Assistant's async_track_utc_time_change to trigger exactly at quarter-hour boundaries
        # This ensures we trigger at :00, :15, :30, :45 seconds=1 to avoid triggering too early
        self._quarter_hour_timer_cancel = async_track_utc_time_change(
            self.hass,
            self._handle_quarter_hour_refresh,
            minute=QUARTER_HOUR_BOUNDARIES,
            second=1,
        )

        self._log(
            "debug",
            "Scheduled quarter-hour refresh for boundaries: %s (at second=1)",
            QUARTER_HOUR_BOUNDARIES,
        )

    @callback
    def _handle_quarter_hour_refresh(self, _now: datetime | None = None) -> None:
        """Handle quarter-hour entity refresh - check for midnight turnover and update entities."""
        now = dt_util.now()
        self._log("debug", "Quarter-hour refresh triggered at %s", now.isoformat())

        # Check if midnight has passed since last check
        midnight_turnover_performed = self._check_and_handle_midnight_turnover(now)

        if midnight_turnover_performed:
            self._log("info", "Midnight turnover detected and performed during quarter-hour refresh")
            # Schedule cache save asynchronously (we're in a callback)
            self.hass.async_create_task(self._store_cache())
            # Entity update already done in _check_and_handle_midnight_turnover
            # Skip the regular update to avoid double-update
        else:
            # Regular quarter-hour refresh - only update time-sensitive entities
            # This causes time-sensitive entity state properties to be re-evaluated with the current time
            # Static entities (statistics, diagnostics) only update when new API data arrives
            self._async_update_time_sensitive_listeners()

    def _schedule_minute_refresh(self) -> None:
        """Schedule minute-by-minute entity refresh for timing sensors."""
        # Cancel any existing timer
        if self._minute_timer_cancel:
            self._minute_timer_cancel()
            self._minute_timer_cancel = None

        # Use Home Assistant's async_track_utc_time_change to trigger every minute at second=1
        # This ensures timing sensors (remaining_minutes, progress) update accurately
        self._minute_timer_cancel = async_track_utc_time_change(
            self.hass,
            self._handle_minute_refresh,
            second=1,
        )

        self._log(
            "debug",
            "Scheduled minute-by-minute refresh for timing sensors (every minute at second=1)",
        )

    @callback
    def _handle_minute_refresh(self, _now: datetime | None = None) -> None:
        """Handle minute-by-minute entity refresh for timing sensors."""
        # Only log at debug level to avoid log spam (this runs every minute)
        self._log("debug", "Minute refresh triggered for timing sensors")

        # Update only minute-update entities (remaining_minutes, progress, etc.)
        self._async_update_minute_listeners()

    @callback
    def _check_and_handle_midnight_turnover(self, now: datetime) -> bool:
        """
        Check if midnight has passed and perform data rotation if needed.

        This is called by the quarter-hour timer to ensure timely rotation
        without waiting for the next API update cycle.

        Returns:
            True if midnight turnover was performed, False otherwise

        """
        current_date = now.date()

        # First time check - initialize
        if self._last_midnight_check is None:
            self._last_midnight_check = now
            return False

        last_check_date = self._last_midnight_check.date()

        # Check if we've crossed into a new day
        if current_date > last_check_date:
            self._log(
                "debug",
                "Midnight crossed: last_check=%s, current=%s",
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
                        # For subentry, we need to get data from main coordinator
                        # but we can update the timestamp to trigger entity refresh
                        self.data["timestamp"] = now

                    # Notify listeners about the updated data after rotation
                    self.async_update_listeners()

            self._last_midnight_check = now
            return True

        self._last_midnight_check = now
        return False

    async def async_shutdown(self) -> None:
        """Shut down the coordinator and clean up timers."""
        if self._quarter_hour_timer_cancel:
            self._quarter_hour_timer_cancel()
            self._quarter_hour_timer_cancel = None

        if self._minute_timer_cancel:
            self._minute_timer_cancel()
            self._minute_timer_cancel = None

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
        """Fetch data from Tibber API."""
        # Load cache if not already loaded
        if self._cached_price_data is None and self._cached_user_data is None:
            await self._load_cache()

        current_time = dt_util.utcnow()

        try:
            if self.is_main_entry():
                # Main entry fetches data for all homes
                return await self._handle_main_entry_update(current_time)
            # Subentries get data from main coordinator
            return await self._handle_subentry_update()

        except TibberPricesApiClientAuthenticationError as err:
            msg = "Invalid access token"
            raise ConfigEntryAuthFailed(msg) from err
        except (
            TibberPricesApiClientCommunicationError,
            TibberPricesApiClientError,
        ) as err:
            # Use cached data as fallback if available
            if self._cached_price_data is not None:
                self._log("warning", "API error, using cached data: %s", err)
                return self._merge_cached_data()
            msg = f"Error communicating with API: {err}"
            raise UpdateFailed(msg) from err

    async def _handle_main_entry_update(self, current_time: datetime) -> dict[str, Any]:
        """Handle update for main entry - fetch data for all homes."""
        # Update user data if needed (daily check)
        await self._update_user_data_if_needed(current_time)

        # Check if we need to update price data
        if self._should_update_price_data(current_time):
            raw_data = await self._fetch_all_homes_data()
            # Cache the data
            self._cached_price_data = raw_data
            self._last_price_update = current_time
            await self._store_cache()
            # Transform for main entry: provide aggregated view
            return self._transform_data_for_main_entry(raw_data)

        # Use cached data if available
        if self._cached_price_data is not None:
            return self._transform_data_for_main_entry(self._cached_price_data)

        # Fallback: no cache and no update needed (shouldn't happen)
        self._log("warning", "No cached data available and update not triggered - returning empty data")
        return {
            "timestamp": current_time,
            "homes": {},
            "priceInfo": {},
        }

    async def _handle_subentry_update(self) -> dict[str, Any]:
        """Handle update for subentry - get data from main coordinator."""
        main_data = await self._get_data_from_main_coordinator()
        return self._transform_data_for_subentry(main_data)

    async def _fetch_all_homes_data(self) -> dict[str, Any]:
        """Fetch data for all homes (main coordinator only)."""
        self._log("debug", "Fetching data for all homes")

        # Get price data for all homes
        price_data = await self.api.async_get_price_info()

        all_homes_data = {}
        homes_list = price_data.get("homes", {})

        for home_id, home_price_data in homes_list.items():
            # Store raw price data without enrichment
            # Enrichment will be done dynamically when data is transformed
            home_data = {
                "price_info": home_price_data,
            }
            all_homes_data[home_id] = home_data

        return {
            "timestamp": dt_util.utcnow(),
            "homes": all_homes_data,
        }

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

    async def _load_cache(self) -> None:
        """Load cached data from storage."""
        try:
            stored = await self._store.async_load()
            if stored:
                self._cached_price_data = stored.get("price_data")
                self._cached_user_data = stored.get("user_data")

                # Restore timestamps
                if last_price_update := stored.get("last_price_update"):
                    self._last_price_update = dt_util.parse_datetime(last_price_update)
                if last_user_update := stored.get("last_user_update"):
                    self._last_user_update = dt_util.parse_datetime(last_user_update)
                if last_midnight_check := stored.get("last_midnight_check"):
                    self._last_midnight_check = dt_util.parse_datetime(last_midnight_check)

                # Validate cache: check if price data is from a previous day
                if not self._is_cache_valid():
                    self._log("info", "Cached price data is from a previous day, clearing cache to fetch fresh data")
                    self._cached_price_data = None
                    self._last_price_update = None
                    await self._store_cache()
                else:
                    self._log("debug", "Cache loaded successfully")
            else:
                self._log("debug", "No cache found, will fetch fresh data")
        except OSError as ex:
            self._log("warning", "Failed to load cache: %s", ex)

    def _is_cache_valid(self) -> bool:
        """
        Validate if cached price data is still current.

        Returns False if:
        - No cached data exists
        - Cached data is from a different calendar day (in local timezone)
        - Midnight turnover has occurred since cache was saved

        """
        if self._cached_price_data is None or self._last_price_update is None:
            return False

        current_local_date = dt_util.as_local(dt_util.now()).date()
        last_update_local_date = dt_util.as_local(self._last_price_update).date()

        if current_local_date != last_update_local_date:
            self._log(
                "debug",
                "Cache date mismatch: cached=%s, current=%s",
                last_update_local_date,
                current_local_date,
            )
            return False

        return True

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
        current_local_date = dt_util.as_local(dt_util.now()).date()

        # Extract current data
        today_prices = price_info.get("today", [])
        tomorrow_prices = price_info.get("tomorrow", [])

        # Check if any of today's prices are from the previous day
        prices_need_rotation = False
        if today_prices:
            first_today_price_str = today_prices[0].get("startsAt")
            if first_today_price_str:
                first_today_price_time = dt_util.parse_datetime(first_today_price_str)
                if first_today_price_time:
                    first_today_price_date = dt_util.as_local(first_today_price_time).date()
                    prices_need_rotation = first_today_price_date < current_local_date

        if prices_need_rotation:
            self._log("info", "Performing midnight turnover: today→yesterday, tomorrow→today")
            return {
                "yesterday": today_prices,
                "today": tomorrow_prices,
                "tomorrow": [],
                "currency": price_info.get("currency", "EUR"),
            }

        return price_info

    async def _store_cache(self) -> None:
        """Store cache data."""
        data = {
            "price_data": self._cached_price_data,
            "user_data": self._cached_user_data,
            "last_price_update": (self._last_price_update.isoformat() if self._last_price_update else None),
            "last_user_update": (self._last_user_update.isoformat() if self._last_user_update else None),
            "last_midnight_check": (self._last_midnight_check.isoformat() if self._last_midnight_check else None),
        }

        try:
            await self._store.async_save(data)
            self._log("debug", "Cache stored successfully")
        except OSError:
            _LOGGER.exception("Failed to store cache")

    async def _update_user_data_if_needed(self, current_time: datetime) -> None:
        """Update user data if needed (daily check)."""
        if self._last_user_update is None or current_time - self._last_user_update >= self._user_update_interval:
            try:
                self._log("debug", "Updating user data")
                user_data = await self.api.async_get_viewer_details()
                self._cached_user_data = user_data
                self._last_user_update = current_time
                self._log("debug", "User data updated successfully")
            except (
                TibberPricesApiClientError,
                TibberPricesApiClientCommunicationError,
            ) as ex:
                self._log("warning", "Failed to update user data: %s", ex)

    @callback
    def _should_update_price_data(self, current_time: datetime) -> bool:
        """
        Check if price data should be updated from the API.

        Updates occur when:
        1. No cached data exists
        2. Cache is invalid (from previous day)
        3. It's after 13:00 local time and tomorrow's data is missing or invalid
        4. Regular update interval has passed

        """
        if self._cached_price_data is None:
            self._log("debug", "Should update: No cached price data")
            return True
        if self._last_price_update is None:
            self._log("debug", "Should update: No last price update timestamp")
            return True

        now_local = dt_util.as_local(current_time)
        tomorrow_date = (now_local + timedelta(days=1)).date()

        # Check if after 13:00 and tomorrow data is missing or invalid
        if (
            now_local.hour >= TOMORROW_DATA_CHECK_HOUR
            and self._cached_price_data
            and "homes" in self._cached_price_data
            and self._needs_tomorrow_data(tomorrow_date)
        ):
            self._log("debug", "Should update: After %s:00 and valid tomorrow data missing", TOMORROW_DATA_CHECK_HOUR)
            return True

        # Check regular update interval
        time_since_update = current_time - self._last_price_update

        # Determine appropriate interval based on data completeness
        has_tomorrow_data = self._has_valid_tomorrow_data(tomorrow_date)
        interval = UPDATE_INTERVAL_COMPLETE if has_tomorrow_data else UPDATE_INTERVAL
        should_update = time_since_update >= interval

        if should_update:
            self._log(
                "debug",
                "Should update price data: %s (time since last update: %s, interval: %s, has_tomorrow: %s)",
                should_update,
                time_since_update,
                interval,
                has_tomorrow_data,
            )

        return should_update

    def _needs_tomorrow_data(self, tomorrow_date: date) -> bool:
        """Check if tomorrow data is missing or invalid."""
        if not self._cached_price_data or "homes" not in self._cached_price_data:
            return False

        for home_data in self._cached_price_data["homes"].values():
            price_info = home_data.get("price_info", {})
            tomorrow_prices = price_info.get("tomorrow", [])

            # Check if tomorrow data is missing
            if not tomorrow_prices:
                return True

            # Check if tomorrow data is actually for tomorrow (validate date)
            first_price = tomorrow_prices[0]
            if starts_at := first_price.get("startsAt"):
                price_time = dt_util.parse_datetime(starts_at)
                if price_time:
                    price_date = dt_util.as_local(price_time).date()
                    if price_date != tomorrow_date:
                        self._log(
                            "debug",
                            "Tomorrow data has wrong date: expected=%s, actual=%s",
                            tomorrow_date,
                            price_date,
                        )
                        return True

        return False

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
        options = self.config_entry.options or {}
        return {
            "low": options.get(CONF_PRICE_RATING_THRESHOLD_LOW, DEFAULT_PRICE_RATING_THRESHOLD_LOW),
            "high": options.get(CONF_PRICE_RATING_THRESHOLD_HIGH, DEFAULT_PRICE_RATING_THRESHOLD_HIGH),
        }

    def _get_period_config(self, *, reverse_sort: bool) -> dict[str, Any]:
        """Get period calculation configuration from config options."""
        options = self.config_entry.options
        data = self.config_entry.data

        if reverse_sort:
            # Peak price configuration
            flex = options.get(CONF_PEAK_PRICE_FLEX, data.get(CONF_PEAK_PRICE_FLEX, DEFAULT_PEAK_PRICE_FLEX))
            min_distance_from_avg = options.get(
                CONF_PEAK_PRICE_MIN_DISTANCE_FROM_AVG,
                data.get(CONF_PEAK_PRICE_MIN_DISTANCE_FROM_AVG, DEFAULT_PEAK_PRICE_MIN_DISTANCE_FROM_AVG),
            )
            min_period_length = options.get(
                CONF_PEAK_PRICE_MIN_PERIOD_LENGTH,
                data.get(CONF_PEAK_PRICE_MIN_PERIOD_LENGTH, DEFAULT_PEAK_PRICE_MIN_PERIOD_LENGTH),
            )
        else:
            # Best price configuration
            flex = options.get(CONF_BEST_PRICE_FLEX, data.get(CONF_BEST_PRICE_FLEX, DEFAULT_BEST_PRICE_FLEX))
            min_distance_from_avg = options.get(
                CONF_BEST_PRICE_MIN_DISTANCE_FROM_AVG,
                data.get(CONF_BEST_PRICE_MIN_DISTANCE_FROM_AVG, DEFAULT_BEST_PRICE_MIN_DISTANCE_FROM_AVG),
            )
            min_period_length = options.get(
                CONF_BEST_PRICE_MIN_PERIOD_LENGTH,
                data.get(CONF_BEST_PRICE_MIN_PERIOD_LENGTH, DEFAULT_BEST_PRICE_MIN_PERIOD_LENGTH),
            )

        # Convert flex from percentage to decimal (e.g., 5 -> 0.05)
        try:
            flex = float(flex) / 100
        except (TypeError, ValueError):
            flex = DEFAULT_BEST_PRICE_FLEX / 100 if not reverse_sort else DEFAULT_PEAK_PRICE_FLEX / 100

        return {
            "flex": flex,
            "min_distance_from_avg": float(min_distance_from_avg),
            "min_period_length": int(min_period_length),
        }

    def _should_show_periods(
        self,
        price_info: dict[str, Any],
        *,
        reverse_sort: bool,
        level_override: str | None = None,
    ) -> bool:
        """
        Check if periods should be shown based on level filter only.

        Args:
            price_info: Price information dict with today/yesterday/tomorrow data
            reverse_sort: If False (best_price), checks max_level filter.
                         If True (peak_price), checks min_level filter.
            level_override: Optional override for level filter ("any" to disable)

        Returns:
            True if periods should be displayed, False if they should be filtered out.

        """
        # Only check level filter (day-level check: "does today have any qualifying intervals?")
        return self._check_level_filter(
            price_info,
            reverse_sort=reverse_sort,
            override=level_override,
        )

    def _split_at_gap_clusters(
        self,
        today_intervals: list[dict[str, Any]],
        level_order: int,
        min_period_length: int,
        *,
        reverse_sort: bool,
    ) -> list[list[dict[str, Any]]]:
        """
        Split intervals into sub-sequences at gap clusters.

        A gap cluster is 2+ consecutive intervals that don't meet the level requirement.
        This allows recovering usable periods from sequences that would otherwise be rejected.

        Args:
            today_intervals: List of price intervals for today
            level_order: Required level order from PRICE_LEVEL_MAPPING
            min_period_length: Minimum number of intervals required for a valid sub-sequence
            reverse_sort: True for peak price, False for best price

        Returns:
            List of sub-sequences, each at least min_period_length long.

        """
        sub_sequences = []
        current_sequence = []
        consecutive_non_qualifying = 0

        for interval in today_intervals:
            interval_level = PRICE_LEVEL_MAPPING.get(interval.get("level", "NORMAL"), 0)
            meets_requirement = interval_level >= level_order if reverse_sort else interval_level <= level_order

            if meets_requirement:
                # Qualifying interval - add to current sequence
                current_sequence.append(interval)
                consecutive_non_qualifying = 0
            elif consecutive_non_qualifying == 0:
                # First non-qualifying interval (single gap) - add to current sequence
                current_sequence.append(interval)
                consecutive_non_qualifying = 1
            else:
                # Second+ consecutive non-qualifying interval = gap cluster starts
                # Save current sequence if long enough (excluding the first gap we just added)
                if len(current_sequence) - 1 >= min_period_length:
                    sub_sequences.append(current_sequence[:-1])  # Exclude the first gap
                current_sequence = []
                consecutive_non_qualifying = 0

        # Don't forget last sequence
        if len(current_sequence) >= min_period_length:
            sub_sequences.append(current_sequence)

        return sub_sequences

    def _check_short_period_strict(
        self,
        today_intervals: list[dict[str, Any]],
        level_order: int,
        *,
        reverse_sort: bool,
    ) -> bool:
        """
        Strict filtering for short periods (< 1.5h) without gap tolerance.

        All intervals must meet the requirement perfectly, or at least one does
        and all others are exact matches.

        Args:
            today_intervals: List of price intervals for today
            level_order: Required level order from PRICE_LEVEL_MAPPING
            reverse_sort: True for peak price, False for best price

        Returns:
            True if all intervals meet requirement (with at least one qualifying), False otherwise.

        """
        has_qualifying = False
        for interval in today_intervals:
            interval_level = PRICE_LEVEL_MAPPING.get(interval.get("level", "NORMAL"), 0)
            meets_requirement = interval_level >= level_order if reverse_sort else interval_level <= level_order
            if meets_requirement:
                has_qualifying = True
            elif interval_level != level_order:
                # Any deviation in short periods disqualifies the entire sequence
                return False
        return has_qualifying

    def _check_level_filter_with_gaps(
        self,
        today_intervals: list[dict[str, Any]],
        level_order: int,
        max_gap_count: int,
        *,
        reverse_sort: bool,
    ) -> bool:
        """
        Check if intervals meet level requirements with gap tolerance and minimum distance.

        A "gap" is an interval that deviates by exactly 1 level step.
        For best price: CHEAP allows NORMAL as gap (but not EXPENSIVE).
        For peak price: EXPENSIVE allows NORMAL as gap (but not CHEAP).

        Gap tolerance is only applied to periods with at least MIN_INTERVALS_FOR_GAP_TOLERANCE
        intervals (1.5h). Shorter periods use strict filtering (zero tolerance).

        Between gaps, there must be a minimum number of "good" intervals to prevent
        periods that are mostly interrupted by gaps.

        Args:
            today_intervals: List of price intervals for today
            level_order: Required level order from PRICE_LEVEL_MAPPING
            max_gap_count: Maximum total gaps allowed
            reverse_sort: True for peak price, False for best price

        Returns:
            True if any qualifying sequence exists, False otherwise.

        """
        if not today_intervals:
            return False

        interval_count = len(today_intervals)

        # Periods shorter than MIN_INTERVALS_FOR_GAP_TOLERANCE (1.5h) use strict filtering
        if interval_count < MIN_INTERVALS_FOR_GAP_TOLERANCE:
            period_type = "peak" if reverse_sort else "best"
            _LOGGER.debug(
                "Using strict filtering for short %s period (%d intervals < %d min required for gap tolerance)",
                period_type,
                interval_count,
                MIN_INTERVALS_FOR_GAP_TOLERANCE,
            )
            return self._check_short_period_strict(today_intervals, level_order, reverse_sort=reverse_sort)

        # Try normal gap tolerance check first
        if self._check_sequence_with_gap_tolerance(
            today_intervals, level_order, max_gap_count, reverse_sort=reverse_sort
        ):
            return True

        # Normal check failed - try splitting at gap clusters as fallback
        # Get minimum period length from config (convert minutes to intervals)
        if reverse_sort:
            min_period_minutes = self.config_entry.options.get(
                CONF_PEAK_PRICE_MIN_PERIOD_LENGTH,
                DEFAULT_PEAK_PRICE_MIN_PERIOD_LENGTH,
            )
        else:
            min_period_minutes = self.config_entry.options.get(
                CONF_BEST_PRICE_MIN_PERIOD_LENGTH,
                DEFAULT_BEST_PRICE_MIN_PERIOD_LENGTH,
            )

        min_period_intervals = min_period_minutes // 15

        sub_sequences = self._split_at_gap_clusters(
            today_intervals,
            level_order,
            min_period_intervals,
            reverse_sort=reverse_sort,
        )

        # Check if ANY sub-sequence passes gap tolerance
        for sub_seq in sub_sequences:
            if self._check_sequence_with_gap_tolerance(sub_seq, level_order, max_gap_count, reverse_sort=reverse_sort):
                return True

        return False

    def _check_sequence_with_gap_tolerance(
        self,
        intervals: list[dict[str, Any]],
        level_order: int,
        max_gap_count: int,
        *,
        reverse_sort: bool,
    ) -> bool:
        """
        Check if a single interval sequence passes gap tolerance requirements.

        This is the core gap tolerance logic extracted for reuse with sub-sequences.

        Args:
            intervals: List of price intervals to check
            level_order: Required level order from PRICE_LEVEL_MAPPING
            max_gap_count: Maximum total gaps allowed
            reverse_sort: True for peak price, False for best price

        Returns:
            True if sequence meets all gap tolerance requirements, False otherwise.

        """
        if not intervals:
            return False

        interval_count = len(intervals)

        # Calculate minimum distance between gaps dynamically.
        # Shorter periods require relatively larger distances.
        # Longer periods allow gaps closer together.
        # Distance is never less than 2 intervals between gaps.
        min_distance_between_gaps = max(2, (interval_count // max_gap_count) // 2)

        # Limit total gaps to max 25% of period length to prevent too many outliers.
        # This ensures periods remain predominantly "good" even when long.
        effective_max_gaps = min(max_gap_count, interval_count // 4)

        gap_count = 0
        consecutive_good_count = 0
        has_qualifying_interval = False

        for interval in intervals:
            interval_level = PRICE_LEVEL_MAPPING.get(interval.get("level", "NORMAL"), 0)

            # Check if interval meets the strict requirement
            meets_requirement = interval_level >= level_order if reverse_sort else interval_level <= level_order

            if meets_requirement:
                has_qualifying_interval = True
                consecutive_good_count += 1
                continue

            # Check if this is a tolerable gap (exactly 1 step deviation)
            is_tolerable_gap = interval_level == level_order - 1 if reverse_sort else interval_level == level_order + 1

            if is_tolerable_gap:
                # If we already had gaps, check minimum distance
                if gap_count > 0 and consecutive_good_count < min_distance_between_gaps:
                    # Not enough "good" intervals between gaps
                    return False

                gap_count += 1
                if gap_count > effective_max_gaps:
                    return False

                # Reset counter for next gap
                consecutive_good_count = 0
            else:
                # Too far from required level (more than 1 step deviation)
                return False

        return has_qualifying_interval

    def _check_level_filter(
        self,
        price_info: dict[str, Any],
        *,
        reverse_sort: bool,
        override: str | None = None,
    ) -> bool:
        """
        Check if today has any intervals that meet the level requirement with gap tolerance.

        Gap tolerance allows a configurable number of intervals within a qualifying sequence
        to deviate by one level step (e.g., CHEAP allows NORMAL, but not EXPENSIVE).

        Args:
            price_info: Price information dict with today data
            reverse_sort: If False (best_price), checks max_level (upper bound filter).
                         If True (peak_price), checks min_level (lower bound filter).
            override: Optional override value (e.g., "any" to disable filter)

        Returns:
            True if ANY sequence of intervals meets the level requirement
            (considering gap tolerance), False otherwise.

        """
        # Use override if provided
        if override is not None:
            level_config = override
        # Get appropriate config based on sensor type
        elif reverse_sort:
            # Peak price: minimum level filter (lower bound)
            level_config = self.config_entry.options.get(
                CONF_PEAK_PRICE_MIN_LEVEL,
                DEFAULT_PEAK_PRICE_MIN_LEVEL,
            )
        else:
            # Best price: maximum level filter (upper bound)
            level_config = self.config_entry.options.get(
                CONF_BEST_PRICE_MAX_LEVEL,
                DEFAULT_BEST_PRICE_MAX_LEVEL,
            )

        # "any" means no level filtering
        if level_config == "any":
            return True

        # Get today's intervals
        today_intervals = price_info.get("today", [])

        if not today_intervals:
            return True  # If no data, don't filter

        # Get gap tolerance configuration
        if reverse_sort:
            max_gap_count = self.config_entry.options.get(
                CONF_PEAK_PRICE_MAX_LEVEL_GAP_COUNT,
                DEFAULT_PEAK_PRICE_MAX_LEVEL_GAP_COUNT,
            )
        else:
            max_gap_count = self.config_entry.options.get(
                CONF_BEST_PRICE_MAX_LEVEL_GAP_COUNT,
                DEFAULT_BEST_PRICE_MAX_LEVEL_GAP_COUNT,
            )

        # Note: level_config is lowercase from selector, but PRICE_LEVEL_MAPPING uses uppercase
        level_order = PRICE_LEVEL_MAPPING.get(level_config.upper(), 0)

        # If gap tolerance is 0, use simple ANY check (backwards compatible)
        if max_gap_count == 0:
            if reverse_sort:
                # Peak price: level >= min_level (show if ANY interval is expensive enough)
                return any(
                    PRICE_LEVEL_MAPPING.get(interval.get("level", "NORMAL"), 0) >= level_order
                    for interval in today_intervals
                )
            # Best price: level <= max_level (show if ANY interval is cheap enough)
            return any(
                PRICE_LEVEL_MAPPING.get(interval.get("level", "NORMAL"), 0) <= level_order
                for interval in today_intervals
            )

        # Use gap-tolerant check
        return self._check_level_filter_with_gaps(
            today_intervals,
            level_order,
            max_gap_count,
            reverse_sort=reverse_sort,
        )

    def _calculate_periods_for_price_info(self, price_info: dict[str, Any]) -> dict[str, Any]:
        """
        Calculate periods (best price and peak price) for the given price info.

        Applies volatility and level filtering based on user configuration.
        If filters don't match, returns empty period lists.
        """
        yesterday_prices = price_info.get("yesterday", [])
        today_prices = price_info.get("today", [])
        tomorrow_prices = price_info.get("tomorrow", [])
        all_prices = yesterday_prices + today_prices + tomorrow_prices

        # Get rating thresholds from config
        threshold_low = self.config_entry.options.get(
            CONF_PRICE_RATING_THRESHOLD_LOW,
            DEFAULT_PRICE_RATING_THRESHOLD_LOW,
        )
        threshold_high = self.config_entry.options.get(
            CONF_PRICE_RATING_THRESHOLD_HIGH,
            DEFAULT_PRICE_RATING_THRESHOLD_HIGH,
        )

        # Get volatility thresholds from config
        threshold_volatility_moderate = self.config_entry.options.get(
            CONF_VOLATILITY_THRESHOLD_MODERATE,
            DEFAULT_VOLATILITY_THRESHOLD_MODERATE,
        )
        threshold_volatility_high = self.config_entry.options.get(
            CONF_VOLATILITY_THRESHOLD_HIGH,
            DEFAULT_VOLATILITY_THRESHOLD_HIGH,
        )
        threshold_volatility_very_high = self.config_entry.options.get(
            CONF_VOLATILITY_THRESHOLD_VERY_HIGH,
            DEFAULT_VOLATILITY_THRESHOLD_VERY_HIGH,
        )

        # Get relaxation configuration for best price
        enable_relaxation_best = self.config_entry.options.get(
            CONF_ENABLE_MIN_PERIODS_BEST,
            DEFAULT_ENABLE_MIN_PERIODS_BEST,
        )

        # Check if best price periods should be shown
        # If relaxation is enabled, always calculate (relaxation will try "any" filter)
        # If relaxation is disabled, apply level filter check
        if enable_relaxation_best:
            show_best_price = bool(all_prices)
        else:
            show_best_price = self._should_show_periods(price_info, reverse_sort=False) if all_prices else False
        min_periods_best = self.config_entry.options.get(
            CONF_MIN_PERIODS_BEST,
            DEFAULT_MIN_PERIODS_BEST,
        )
        relaxation_step_best = self.config_entry.options.get(
            CONF_RELAXATION_STEP_BEST,
            DEFAULT_RELAXATION_STEP_BEST,
        )
        relaxation_attempts_best = self.config_entry.options.get(
            CONF_RELAXATION_ATTEMPTS_BEST,
            DEFAULT_RELAXATION_ATTEMPTS_BEST,
        )

        # Calculate best price periods (or return empty if filtered)
        if show_best_price:
            best_config = self._get_period_config(reverse_sort=False)
            # Get level filter configuration
            max_level_best = self.config_entry.options.get(
                CONF_BEST_PRICE_MAX_LEVEL,
                DEFAULT_BEST_PRICE_MAX_LEVEL,
            )
            gap_count_best = self.config_entry.options.get(
                CONF_BEST_PRICE_MAX_LEVEL_GAP_COUNT,
                DEFAULT_BEST_PRICE_MAX_LEVEL_GAP_COUNT,
            )
            best_period_config = PeriodConfig(
                reverse_sort=False,
                flex=best_config["flex"],
                min_distance_from_avg=best_config["min_distance_from_avg"],
                min_period_length=best_config["min_period_length"],
                threshold_low=threshold_low,
                threshold_high=threshold_high,
                threshold_volatility_moderate=threshold_volatility_moderate,
                threshold_volatility_high=threshold_volatility_high,
                threshold_volatility_very_high=threshold_volatility_very_high,
                level_filter=max_level_best,
                gap_count=gap_count_best,
            )
            best_periods, best_relaxation = calculate_periods_with_relaxation(
                all_prices,
                config=best_period_config,
                enable_relaxation=enable_relaxation_best,
                min_periods=min_periods_best,
                relaxation_step_pct=relaxation_step_best,
                max_relaxation_attempts=relaxation_attempts_best,
                should_show_callback=lambda lvl: self._should_show_periods(
                    price_info,
                    reverse_sort=False,
                    level_override=lvl,
                ),
            )
        else:
            best_periods = {
                "periods": [],
                "intervals": [],
                "metadata": {"total_intervals": 0, "total_periods": 0, "config": {}},
            }
            best_relaxation = {"relaxation_active": False, "relaxation_attempted": False}

        # Get relaxation configuration for peak price
        enable_relaxation_peak = self.config_entry.options.get(
            CONF_ENABLE_MIN_PERIODS_PEAK,
            DEFAULT_ENABLE_MIN_PERIODS_PEAK,
        )

        # Check if peak price periods should be shown
        # If relaxation is enabled, always calculate (relaxation will try "any" filter)
        # If relaxation is disabled, apply level filter check
        if enable_relaxation_peak:
            show_peak_price = bool(all_prices)
        else:
            show_peak_price = self._should_show_periods(price_info, reverse_sort=True) if all_prices else False
        min_periods_peak = self.config_entry.options.get(
            CONF_MIN_PERIODS_PEAK,
            DEFAULT_MIN_PERIODS_PEAK,
        )
        relaxation_step_peak = self.config_entry.options.get(
            CONF_RELAXATION_STEP_PEAK,
            DEFAULT_RELAXATION_STEP_PEAK,
        )
        relaxation_attempts_peak = self.config_entry.options.get(
            CONF_RELAXATION_ATTEMPTS_PEAK,
            DEFAULT_RELAXATION_ATTEMPTS_PEAK,
        )

        # Calculate peak price periods (or return empty if filtered)
        if show_peak_price:
            peak_config = self._get_period_config(reverse_sort=True)
            # Get level filter configuration
            min_level_peak = self.config_entry.options.get(
                CONF_PEAK_PRICE_MIN_LEVEL,
                DEFAULT_PEAK_PRICE_MIN_LEVEL,
            )
            gap_count_peak = self.config_entry.options.get(
                CONF_PEAK_PRICE_MAX_LEVEL_GAP_COUNT,
                DEFAULT_PEAK_PRICE_MAX_LEVEL_GAP_COUNT,
            )
            peak_period_config = PeriodConfig(
                reverse_sort=True,
                flex=peak_config["flex"],
                min_distance_from_avg=peak_config["min_distance_from_avg"],
                min_period_length=peak_config["min_period_length"],
                threshold_low=threshold_low,
                threshold_high=threshold_high,
                threshold_volatility_moderate=threshold_volatility_moderate,
                threshold_volatility_high=threshold_volatility_high,
                threshold_volatility_very_high=threshold_volatility_very_high,
                level_filter=min_level_peak,
                gap_count=gap_count_peak,
            )
            peak_periods, peak_relaxation = calculate_periods_with_relaxation(
                all_prices,
                config=peak_period_config,
                enable_relaxation=enable_relaxation_peak,
                min_periods=min_periods_peak,
                relaxation_step_pct=relaxation_step_peak,
                max_relaxation_attempts=relaxation_attempts_peak,
                should_show_callback=lambda lvl: self._should_show_periods(
                    price_info,
                    reverse_sort=True,
                    level_override=lvl,
                ),
            )
        else:
            peak_periods = {
                "periods": [],
                "intervals": [],
                "metadata": {"total_intervals": 0, "total_periods": 0, "config": {}},
            }
            peak_relaxation = {"relaxation_active": False, "relaxation_attempted": False}

        return {
            "best_price": best_periods,
            "best_price_relaxation": best_relaxation,
            "peak_price": peak_periods,
            "peak_price_relaxation": peak_relaxation,
        }

    def _transform_data_for_main_entry(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Transform raw data for main entry (aggregated view of all homes)."""
        # For main entry, we can show data from the first home as default
        # or provide an aggregated view
        homes_data = raw_data.get("homes", {})
        if not homes_data:
            return {
                "timestamp": raw_data.get("timestamp"),
                "homes": {},
                "priceInfo": {},
            }

        # Use the first home's data as the main entry's data
        first_home_data = next(iter(homes_data.values()))
        price_info = first_home_data.get("price_info", {})

        # Perform midnight turnover if needed (handles day transitions)
        price_info = self._perform_midnight_turnover(price_info)

        # Ensure all required keys exist (API might not return tomorrow data yet)
        price_info.setdefault("yesterday", [])
        price_info.setdefault("today", [])
        price_info.setdefault("tomorrow", [])
        price_info.setdefault("currency", "EUR")

        # Enrich price info dynamically with calculated differences and rating levels
        # This ensures enrichment is always up-to-date, especially after midnight turnover
        thresholds = self._get_threshold_percentages()
        price_info = enrich_price_info_with_differences(
            price_info,
            threshold_low=thresholds["low"],
            threshold_high=thresholds["high"],
        )

        # Calculate periods (best price and peak price)
        periods = self._calculate_periods_for_price_info(price_info)

        return {
            "timestamp": raw_data.get("timestamp"),
            "homes": homes_data,
            "priceInfo": price_info,
            "periods": periods,
        }

    def _transform_data_for_subentry(self, main_data: dict[str, Any]) -> dict[str, Any]:
        """Transform main coordinator data for subentry (home-specific view)."""
        home_id = self.config_entry.data.get("home_id")
        if not home_id:
            return main_data

        homes_data = main_data.get("homes", {})
        home_data = homes_data.get(home_id, {})

        if not home_data:
            return {
                "timestamp": main_data.get("timestamp"),
                "priceInfo": {},
            }

        price_info = home_data.get("price_info", {})

        # Perform midnight turnover if needed (handles day transitions)
        price_info = self._perform_midnight_turnover(price_info)

        # Ensure all required keys exist (API might not return tomorrow data yet)
        price_info.setdefault("yesterday", [])
        price_info.setdefault("today", [])
        price_info.setdefault("tomorrow", [])
        price_info.setdefault("currency", "EUR")

        # Enrich price info dynamically with calculated differences and rating levels
        # This ensures enrichment is always up-to-date, especially after midnight turnover
        thresholds = self._get_threshold_percentages()
        price_info = enrich_price_info_with_differences(
            price_info,
            threshold_low=thresholds["low"],
            threshold_high=thresholds["high"],
        )

        # Calculate periods (best price and peak price)
        periods = self._calculate_periods_for_price_info(price_info)

        return {
            "timestamp": main_data.get("timestamp"),
            "priceInfo": price_info,
            "periods": periods,
        }

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

        now = dt_util.now()
        return find_price_data_for_interval(price_info, now)

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
            current_time = dt_util.utcnow()
            await self._update_user_data_if_needed(current_time)
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
        return self._cached_user_data.get("homes", [])
