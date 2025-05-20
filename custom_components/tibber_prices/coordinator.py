"""Coordinator for fetching Tibber price data."""

from __future__ import annotations

import asyncio
import logging
import secrets
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any, Final, cast

import homeassistant.util.dt as dt_util
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

if TYPE_CHECKING:
    from collections.abc import Callable

    from .data import TibberPricesConfigEntry

from .api import (
    TibberPricesApiClientAuthenticationError,
    TibberPricesApiClientCommunicationError,
    TibberPricesApiClientError,
)
from .const import DOMAIN, LOGGER

_LOGGER = logging.getLogger(__name__)

PRICE_UPDATE_RANDOM_MIN_HOUR: Final = 13  # Don't check before 13:00
PRICE_UPDATE_RANDOM_MAX_HOUR: Final = 15  # Don't check after 15:00
RANDOM_DELAY_MAX_MINUTES: Final = 120  # Maximum random delay in minutes
NO_DATA_ERROR_MSG: Final = "No data available"
STORAGE_VERSION: Final = 1
UPDATE_INTERVAL: Final = timedelta(days=1)  # Both price and rating data update daily
UPDATE_FAILED_MSG: Final = "Update failed"
AUTH_FAILED_MSG: Final = "Authentication failed"
MIN_RETRY_INTERVAL: Final = timedelta(minutes=10)
END_OF_DAY_HOUR: Final = 24  # End of day hour for logic clarity


@callback
def _raise_no_data() -> None:
    """Raise error when no data is available."""
    raise TibberPricesApiClientError(NO_DATA_ERROR_MSG)


@callback
def _get_latest_timestamp_from_prices(
    price_data: dict | None,
) -> datetime | None:
    """Get the latest timestamp from price data."""
    if not price_data or "priceInfo" not in price_data:
        return None

    try:
        price_info = price_data["priceInfo"]
        latest_timestamp = None

        # Check today's prices
        if today_prices := price_info.get("today"):
            for price in today_prices:
                if starts_at := price.get("startsAt"):
                    timestamp = dt_util.parse_datetime(starts_at)
                    if timestamp and (not latest_timestamp or timestamp > latest_timestamp):
                        latest_timestamp = timestamp

        # Check tomorrow's prices
        if tomorrow_prices := price_info.get("tomorrow"):
            for price in tomorrow_prices:
                if starts_at := price.get("startsAt"):
                    timestamp = dt_util.parse_datetime(starts_at)
                    if timestamp and (not latest_timestamp or timestamp > latest_timestamp):
                        latest_timestamp = timestamp

    except (KeyError, IndexError, TypeError):
        return None
    else:
        return latest_timestamp


@callback
def _get_latest_timestamp_from_rating(
    rating_data: dict | None,
) -> datetime | None:
    """Get the latest timestamp from rating data."""
    if not rating_data or "priceRating" not in rating_data:
        return None

    try:
        price_rating = rating_data["priceRating"]
        latest_timestamp = None

        # Check all rating types (hourly, daily, monthly)
        for rating_type in ["hourly", "daily", "monthly"]:
            if rating_entries := price_rating.get(rating_type, []):
                for entry in rating_entries:
                    if time := entry.get("time"):
                        timestamp = dt_util.parse_datetime(time)
                        if timestamp and (not latest_timestamp or timestamp > latest_timestamp):
                            latest_timestamp = timestamp
    except (KeyError, IndexError, TypeError):
        return None
    else:
        return latest_timestamp


# https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
class TibberPricesDataUpdateCoordinator(DataUpdateCoordinator[dict]):
    """Class to manage fetching data from the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: TibberPricesConfigEntry,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize coordinator with cache."""
        super().__init__(hass, *args, **kwargs)
        self.config_entry = entry
        storage_key = f"{DOMAIN}.{entry.entry_id}"
        self._store = Store(hass, STORAGE_VERSION, storage_key)
        self._cached_price_data: dict | None = None
        self._cached_rating_data_hourly: dict | None = None
        self._cached_rating_data_daily: dict | None = None
        self._cached_rating_data_monthly: dict | None = None
        self._last_price_update: datetime | None = None
        self._last_rating_update_hourly: datetime | None = None
        self._last_rating_update_daily: datetime | None = None
        self._last_rating_update_monthly: datetime | None = None
        self._scheduled_price_update: asyncio.Task | None = None
        self._remove_update_listeners: list[Any] = []
        self._force_update = False
        self._rotation_lock = asyncio.Lock()  # Add lock for data rotation operations
        self._last_attempted_price_update: datetime | None = None
        self._random_update_minute: int | None = None
        self._random_update_date: date | None = None

        # Schedule updates at the start of every hour
        self._remove_update_listeners.append(
            async_track_time_change(hass, self._async_refresh_hourly, minute=0, second=0)
        )

    async def async_shutdown(self) -> None:
        """Clean up coordinator on shutdown."""
        await super().async_shutdown()
        for listener in self._remove_update_listeners:
            listener()

    async def _async_refresh_hourly(self, now: datetime | None = None) -> None:
        """
        Handle the hourly refresh.

        This will:
        1. Check if it's midnight and handle rotation if needed
        2. Then perform a regular refresh
        """
        # If this is a midnight update (hour=0), handle data rotation first
        if now and now.hour == 0 and now.minute == 0:
            await self._perform_midnight_rotation()

        # Then do a regular refresh
        await self.async_refresh()

    async def _async_update_data(self) -> dict:
        """
        Fetch new state data for the coordinator.

        This method will:
        1. Initialize cached data if none exists
        2. Force update if requested via async_request_refresh
        3. Otherwise, check if update conditions are met
        4. Use cached data as fallback if API call fails
        """
        if self._cached_price_data is None:
            await self._async_initialize()

        try:
            current_time = dt_util.now()
            result = None

            # If force update requested, fetch all data
            if self._force_update:
                LOGGER.debug(
                    "Force updating data",
                    extra={
                        "reason": "force_update",
                        "last_success": self.last_update_success,
                        "last_price_update": self._last_price_update,
                        "last_rating_updates": {
                            "hourly": self._last_rating_update_hourly,
                            "daily": self._last_rating_update_daily,
                            "monthly": self._last_rating_update_monthly,
                        },
                    },
                )
                self._force_update = False  # Reset force update flag
                result = await self._fetch_all_data()
            else:
                result = await self._handle_conditional_update(current_time)

        except TibberPricesApiClientAuthenticationError as exception:
            LOGGER.error(
                "Authentication failed",
                extra={"error": str(exception), "error_type": "auth_failed"},
            )
            raise ConfigEntryAuthFailed(AUTH_FAILED_MSG) from exception
        except (
            TibberPricesApiClientCommunicationError,
            TibberPricesApiClientError,
            Exception,
        ) as exception:
            if isinstance(exception, TibberPricesApiClientCommunicationError):
                LOGGER.error(
                    "API communication error",
                    extra={
                        "error": str(exception),
                        "error_type": "communication_error",
                    },
                )
            elif isinstance(exception, TibberPricesApiClientError):
                LOGGER.error(
                    "API client error",
                    extra={"error": str(exception), "error_type": "client_error"},
                )
            else:
                LOGGER.exception(
                    "Unexpected error",
                    extra={"error": str(exception), "error_type": "unexpected"},
                )

            if self._cached_price_data is not None:
                LOGGER.info("Using cached data as fallback")
                return self._merge_all_cached_data()
            raise UpdateFailed(UPDATE_FAILED_MSG) from exception
        else:
            return result

    async def _handle_conditional_update(self, current_time: datetime) -> dict:
        """Handle conditional update based on update conditions."""
        # Simplified conditional update checking
        update_conditions = self._check_update_conditions(current_time)

        if any(update_conditions.values()):
            LOGGER.debug(
                "Updating data based on conditions",
                extra=update_conditions,
            )
            return await self._fetch_all_data()

        if self._cached_price_data is not None:
            LOGGER.debug("Using cached data")
            return self._merge_all_cached_data()

        LOGGER.debug("No cached data available, fetching new data")
        return await self._fetch_all_data()

    @callback
    def _check_update_conditions(self, current_time: datetime) -> dict[str, bool]:
        """Check all update conditions and return results as a dictionary."""
        return {
            "update_price": self._should_update_price_data(current_time),
            "update_hourly": self._should_update_rating_type(
                current_time,
                self._cached_rating_data_hourly,
                self._last_rating_update_hourly,
                "hourly",
            ),
            "update_daily": self._should_update_rating_type(
                current_time,
                self._cached_rating_data_daily,
                self._last_rating_update_daily,
                "daily",
            ),
            "update_monthly": self._should_update_rating_type(
                current_time,
                self._cached_rating_data_monthly,
                self._last_rating_update_monthly,
                "monthly",
            ),
        }

    async def _fetch_all_data(self) -> dict:
        """
        Fetch all data from the API without checking update conditions.

        This method will:
        1. Fetch all required data (price and rating data)
        2. Validate that all data is complete and valid
        3. Only then update the cache with the new data
        4. If any data is invalid, keep using the cached data
        """
        current_time = dt_util.now()
        new_data = {
            "price_data": None,
            "rating_data": {"hourly": None, "daily": None, "monthly": None},
        }

        # First fetch all data without updating cache
        try:
            # Fetch price data
            price_data = await self._fetch_price_data()
            new_data["price_data"] = self._extract_data(price_data, "priceInfo", ("yesterday", "today", "tomorrow"))

            # Fetch all rating data
            for rating_type in ["hourly", "daily", "monthly"]:
                try:
                    rating_data = await self._get_rating_data_for_type(rating_type)
                    new_data["rating_data"][rating_type] = rating_data
                except TibberPricesApiClientError as ex:
                    LOGGER.error("Failed to fetch %s rating data: %s", rating_type, ex)
                    # Don't raise here, we'll check completeness later
        except TibberPricesApiClientError as ex:
            LOGGER.error("Failed to fetch price data: %s", ex)
            if self._cached_price_data is not None:
                LOGGER.info("Using cached data as fallback after price data fetch failure")
                return self._merge_all_cached_data()
            raise

        # Validate that we have all required data
        if new_data["price_data"] is None:
            LOGGER.error("No price data available after fetch")
            if self._cached_price_data is not None:
                LOGGER.info("Using cached data as fallback due to missing price data")
                return self._merge_all_cached_data()
            _raise_no_data()

        # Only update cache if we have valid data
        self._cached_price_data = cast("dict", new_data["price_data"])
        self._last_price_update = current_time

        # Update rating data cache only for types that were successfully fetched
        for rating_type, rating_data in new_data["rating_data"].items():
            if rating_data is not None:
                self._update_rating_cache(rating_type, rating_data, current_time)

        # Store the updated cache
        await self._store_cache()
        LOGGER.debug("Updated and stored all cache data at %s", current_time)

        # Return merged data
        return self._merge_all_cached_data()

    @callback
    def _update_rating_cache(self, rating_type: str, rating_data: dict, current_time: datetime) -> None:
        """Update the rating cache for a specific rating type."""
        if rating_type == "hourly":
            self._cached_rating_data_hourly = cast("dict", rating_data)
            self._last_rating_update_hourly = current_time
        elif rating_type == "daily":
            self._cached_rating_data_daily = cast("dict", rating_data)
            self._last_rating_update_daily = current_time
        else:  # monthly
            self._cached_rating_data_monthly = cast("dict", rating_data)
            self._last_rating_update_monthly = current_time
        LOGGER.debug("Updated %s rating data cache at %s", rating_type, current_time)

    async def _store_cache(self) -> None:
        """Store cache data in flat format."""
        data = {
            "price_data": self._cached_price_data,
            "rating_data_hourly": self._cached_rating_data_hourly,
            "rating_data_daily": self._cached_rating_data_daily,
            "rating_data_monthly": self._cached_rating_data_monthly,
            "last_price_update": (self._last_price_update.isoformat() if self._last_price_update else None),
            "last_rating_update_hourly": (
                self._last_rating_update_hourly.isoformat() if self._last_rating_update_hourly else None
            ),
            "last_rating_update_daily": (
                self._last_rating_update_daily.isoformat() if self._last_rating_update_daily else None
            ),
            "last_rating_update_monthly": (
                self._last_rating_update_monthly.isoformat() if self._last_rating_update_monthly else None
            ),
        }
        LOGGER.debug(
            "Storing cache data with timestamps: %s",
            {k: v for k, v in data.items() if k.startswith("last_")},
        )
        if data["price_data"] is None:
            LOGGER.warning("Attempting to store cache with missing price_data!")
        if data["last_price_update"] is None:
            LOGGER.warning("Attempting to store cache with missing last_price_update!")
        try:
            await self._store.async_save(data)
            LOGGER.debug("Cache successfully written to disk.")
        except OSError as ex:
            LOGGER.error("Failed to write cache to disk: %s", ex)

    @callback
    def _should_update_price_data(self, current_time: datetime) -> bool:
        """
        Decide if price data should be updated.

        - No fetch before 13:00.
        - Randomized fetch minute in update window (13:00-15:00).
        - Always fetch after 15:00 if tomorrow's data is missing.
        - No fetch after midnight until 13:00.
        """
        current_hour = current_time.hour
        # Check if tomorrow's data is available
        tomorrow_prices = []
        if self._cached_price_data and "priceInfo" in self._cached_price_data:
            tomorrow_prices = self._cached_price_data["priceInfo"].get("tomorrow", [])
        interval_count = len(tomorrow_prices)
        min_tomorrow_intervals_hourly = 24
        min_tomorrow_intervals_15min = 96
        tomorrow_data_complete = interval_count in {min_tomorrow_intervals_hourly, min_tomorrow_intervals_15min}

        should_update = False
        # 1. Before 13:00: never fetch
        if current_hour < PRICE_UPDATE_RANDOM_MIN_HOUR:
            should_update = False
        # 2. In update window (13:00-15:00): fetch at random minute, with min retry interval
        elif PRICE_UPDATE_RANDOM_MIN_HOUR <= current_hour < PRICE_UPDATE_RANDOM_MAX_HOUR:
            today = current_time.date()
            if self._random_update_date != today or self._random_update_minute is None:
                self._random_update_date = today
                self._random_update_minute = secrets.randbelow(RANDOM_DELAY_MAX_MINUTES)
            # Only fetch at the random minute
            if current_time.minute == self._random_update_minute:
                # Enforce minimum retry interval
                if self._last_attempted_price_update:
                    since_last = current_time - self._last_attempted_price_update
                    if since_last < MIN_RETRY_INTERVAL:
                        LOGGER.debug(
                            "Skipping price update: last attempt was %s ago (<%s)",
                            since_last,
                            MIN_RETRY_INTERVAL,
                        )
                        should_update = False
                    else:
                        self._last_attempted_price_update = current_time
                        should_update = not tomorrow_data_complete
                else:
                    self._last_attempted_price_update = current_time
                    should_update = not tomorrow_data_complete
            else:
                should_update = False
        # 3. After update window (15:00-00:00): always fetch if tomorrow's data is missing
        elif PRICE_UPDATE_RANDOM_MAX_HOUR <= current_hour < END_OF_DAY_HOUR:
            should_update = not tomorrow_data_complete
        # 4. After midnight until 13:00: never fetch
        else:
            should_update = False
        return should_update

    @callback
    def _should_update_rating_type(
        self,
        current_time: datetime,
        cached_data: dict | None,
        last_update: datetime | None,
        rating_type: str,
    ) -> bool:
        def extra_check_monthly(now: datetime, latest: datetime) -> bool:
            current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return latest < current_month_start

        if rating_type == "monthly":
            return self._should_update_data(
                current_time,
                cached_data,
                last_update,
                lambda d: self._get_latest_rating_timestamp(d, rating_type),
                config={
                    "interval": timedelta(days=1),
                    "extra_check": extra_check_monthly,
                },
            )
        return self._should_update_data(
            current_time,
            cached_data,
            last_update,
            lambda d: self._get_latest_rating_timestamp(d, rating_type),
            config={
                "update_window": (PRICE_UPDATE_RANDOM_MIN_HOUR, PRICE_UPDATE_RANDOM_MAX_HOUR),
                "interval": UPDATE_INTERVAL,
            },
        )

    @callback
    def _should_update_data(
        self,
        current_time: datetime,
        cached_data: dict | None,
        last_update: datetime | None,
        timestamp_func: Callable[[dict | None], datetime | None],
        config: dict | None = None,
    ) -> bool:
        """Generalized update check for any data type."""
        config = config or {}
        update_window = config.get("update_window")
        interval = config.get("interval", UPDATE_INTERVAL)
        extra_check = config.get("extra_check")
        if cached_data is None:
            return True
        latest_timestamp = timestamp_func(cached_data)
        if not latest_timestamp:
            return True
        if not last_update:
            last_update = latest_timestamp
        if update_window:
            current_hour = current_time.hour
            if update_window[0] <= current_hour <= update_window[1]:
                tomorrow = (current_time + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                if latest_timestamp < tomorrow:
                    return True
        if last_update and current_time - last_update >= interval:
            return True
        return extra_check(current_time, latest_timestamp) if extra_check else False

    async def _fetch_price_data(self) -> dict:
        """Fetch fresh price data from API."""
        client = self.config_entry.runtime_data.client
        return await client.async_get_price_info()

    @callback
    def _extract_data(self, data: dict, container_key: str, keys: tuple[str, ...]) -> dict:
        """Extract and harmonize data for caching in flat format."""
        try:
            container = data[container_key]
            extracted = {key: list(container.get(key, [])) for key in keys}
        except (KeyError, IndexError, TypeError) as ex:
            LOGGER.error("Error extracting %s data: %s", container_key, ex)
            extracted = {key: [] for key in keys}
        return extracted

    @callback
    def _get_latest_timestamp_from_rating_type(self, rating_data: dict | None, rating_type: str) -> datetime | None:
        """Get the latest timestamp from a specific rating type."""
        if not rating_data or "priceRating" not in rating_data:
            return None

        try:
            price_rating = rating_data["priceRating"]
            result = None

            if rating_entries := price_rating.get(rating_type, []):
                for entry in rating_entries:
                    if time := entry.get("time"):
                        timestamp = dt_util.parse_datetime(time)
                        if timestamp and (not result or timestamp > result):
                            result = timestamp
        except (KeyError, IndexError, TypeError):
            return None
        return result

    async def _get_rating_data_for_type(self, rating_type: str) -> dict:
        """Get fresh rating data for a specific type in flat format."""
        client = self.config_entry.runtime_data.client
        method_map = {
            "hourly": client.async_get_hourly_price_rating,
            "daily": client.async_get_daily_price_rating,
            "monthly": client.async_get_monthly_price_rating,
        }
        fetch_method = method_map.get(rating_type)
        if not fetch_method:
            msg = f"Unknown rating type: {rating_type}"
            raise ValueError(msg)
        data = await fetch_method()
        try:
            price_rating = data.get("priceRating", data)
            threshold = price_rating.get("thresholdPercentages")
            entries = price_rating.get(rating_type, [])
        except KeyError as ex:
            LOGGER.error("Failed to extract rating data (flat format): %s", ex)
            raise TibberPricesApiClientError(
                TibberPricesApiClientError.EMPTY_DATA_ERROR.format(query_type=rating_type)
            ) from ex
        return {"priceRating": {rating_type: entries, "thresholdPercentages": threshold}}

    @callback
    def _merge_all_cached_data(self) -> dict:
        """Merge all cached data into flat format."""
        if not self._cached_price_data:
            return {}
        # Wrap cached price data in 'priceInfo' only if not already wrapped
        if "priceInfo" in self._cached_price_data:
            merged = {"priceInfo": self._cached_price_data["priceInfo"]}
        else:
            merged = {"priceInfo": self._cached_price_data}
        price_rating = {"hourly": [], "daily": [], "monthly": [], "thresholdPercentages": None}
        for rating_type, cached in zip(
            ["hourly", "daily", "monthly"],
            [self._cached_rating_data_hourly, self._cached_rating_data_daily, self._cached_rating_data_monthly],
            strict=True,
        ):
            if cached and "priceRating" in cached:
                entries = cached["priceRating"].get(rating_type, [])
                price_rating[rating_type] = entries
                if not price_rating["thresholdPercentages"]:
                    price_rating["thresholdPercentages"] = cached["priceRating"].get("thresholdPercentages")
        merged["priceRating"] = price_rating
        return merged

    async def _async_initialize(self) -> None:
        """Load stored data in flat format."""
        stored = await self._store.async_load()
        if stored is None:
            LOGGER.warning("No cache file found or cache is empty on startup.")
        else:
            LOGGER.debug("Loading stored data: %s", stored)
        if stored:
            self._cached_price_data = stored.get("price_data")
            self._cached_rating_data_hourly = stored.get("rating_data_hourly")
            self._cached_rating_data_daily = stored.get("rating_data_daily")
            self._cached_rating_data_monthly = stored.get("rating_data_monthly")
            self._last_price_update = self._recover_timestamp(self._cached_price_data, stored.get("last_price_update"))
            self._last_rating_update_hourly = self._recover_timestamp(
                self._cached_rating_data_hourly,
                stored.get("last_rating_update_hourly"),
                "hourly",
            )
            self._last_rating_update_daily = self._recover_timestamp(
                self._cached_rating_data_daily,
                stored.get("last_rating_update_daily"),
                "daily",
            )
            self._last_rating_update_monthly = self._recover_timestamp(
                self._cached_rating_data_monthly,
                stored.get("last_rating_update_monthly"),
                "monthly",
            )
            LOGGER.debug(
                "Loaded stored cache data - Price update: %s, Rating hourly: %s, daily: %s, monthly: %s",
                self._last_price_update,
                self._last_rating_update_hourly,
                self._last_rating_update_daily,
                self._last_rating_update_monthly,
            )
            if self._cached_price_data is None:
                LOGGER.warning("Cached price data missing after cache load!")
            if self._last_price_update is None:
                LOGGER.warning("Price update timestamp missing after cache load!")
        else:
            LOGGER.info("No cache loaded; will fetch fresh data on first update.")

    def get_all_intervals(self) -> list[dict]:
        """Return a combined, sorted list of all price intervals for yesterday, today, and tomorrow."""
        if not self.data or "priceInfo" not in self.data:
            return []
        price_info = self.data["priceInfo"]
        all_prices = price_info.get("yesterday", []) + price_info.get("today", []) + price_info.get("tomorrow", [])
        return sorted(all_prices, key=lambda p: p["startsAt"])

    def get_interval_granularity(self) -> int | None:
        """Return the interval granularity in minutes (e.g., 15 or 60) for today's data."""
        if not self.data or "priceInfo" not in self.data:
            return None
        today_prices = self.data["priceInfo"].get("today", [])
        from .sensor import detect_interval_granularity

        return detect_interval_granularity(today_prices) if today_prices else None

    def get_current_interval_data(self) -> dict | None:
        """Return the price data for the current interval."""
        if not self.data or "priceInfo" not in self.data:
            return None
        price_info = self.data["priceInfo"]
        now = dt_util.now()
        interval_length = self.get_interval_granularity()
        from .sensor import find_price_data_for_interval

        return find_price_data_for_interval(price_info, now, interval_length)

    def get_combined_price_info(self) -> dict:
        """Return a dict with all intervals under a single key 'all'."""
        return {"all": self.get_all_intervals()}

    def is_tomorrow_data_available(self) -> bool | None:
        """Return True if tomorrow's data is fully available, False if not, None if unknown."""
        if not self.data or "priceInfo" not in self.data:
            return None
        tomorrow_prices = self.data["priceInfo"].get("tomorrow", [])
        interval_count = len(tomorrow_prices)
        min_tomorrow_intervals_hourly = 24
        min_tomorrow_intervals_15min = 96
        tomorrow_interval_counts = {min_tomorrow_intervals_hourly, min_tomorrow_intervals_15min}
        return interval_count in tomorrow_interval_counts

    async def async_request_refresh(self) -> None:
        """
        Request an immediate refresh of the data.

        This method will:
        1. Set the force update flag to trigger a fresh data fetch
        2. Call async_refresh to perform the update

        The force update flag will be reset after the update is complete.
        """
        self._force_update = True
        await self.async_refresh()

    def _transform_api_response(self, data: dict[str, Any]) -> dict:
        """Transform API response to coordinator data format."""
        return cast("dict", data)

    async def _perform_midnight_rotation(self) -> None:
        """
        Perform the data rotation at midnight within the hourly update process.

        This ensures that data rotation completes before any regular updates run,
        avoiding race conditions between midnight rotation and regular updates.
        """
        LOGGER.info("Performing midnight data rotation as part of hourly update cycle")

        if not self._cached_price_data:
            LOGGER.debug("No cached price data available for midnight rotation")
            return

        async with self._rotation_lock:
            try:
                price_info = self._cached_price_data["priceInfo"]

                # Save current data state for logging
                today_count = len(price_info.get("today", []))
                tomorrow_count = len(price_info.get("tomorrow", []))
                yesterday_count = len(price_info.get("yesterday", []))

                LOGGER.debug(
                    "Before rotation - Yesterday: %d, Today: %d, Tomorrow: %d items",
                    yesterday_count,
                    today_count,
                    tomorrow_count,
                )

                # Move today's data to yesterday
                if today_data := price_info.get("today"):
                    price_info["yesterday"] = today_data
                else:
                    LOGGER.warning("No today's data available to move to yesterday")

                # Move tomorrow's data to today
                if tomorrow_data := price_info.get("tomorrow"):
                    price_info["today"] = tomorrow_data
                    price_info["tomorrow"] = []
                else:
                    LOGGER.warning("No tomorrow's data available to move to today")
                    # We don't clear today's data here to avoid potential data loss
                    # If somehow tomorrow's data isn't available, keep today's data
                    # This is different from the separate midnight rotation handler

                # Store the rotated data
                await self._store_cache()

                # Log the new state
                LOGGER.info(
                    "Completed midnight rotation - Yesterday: %d, Today: %d, Tomorrow: %d items",
                    len(price_info.get("yesterday", [])),
                    len(price_info.get("today", [])),
                    len(price_info.get("tomorrow", [])),
                )

                # Flag that we need to fetch new tomorrow's data
                self._force_update = True

            except (KeyError, TypeError, ValueError) as ex:
                LOGGER.error("Error during midnight data rotation in hourly update: %s", ex)

    @callback
    def _recover_timestamp(
        self,
        data: dict | None,
        stored_timestamp: str | None,
        rating_type: str | None = None,
    ) -> datetime | None:
        """Recover timestamp from data or stored value."""
        if stored_timestamp:
            return dt_util.parse_datetime(stored_timestamp)

        if not data:
            return None

        if rating_type:
            timestamp = self._get_latest_rating_timestamp(data, rating_type)
        else:
            timestamp = self._get_latest_price_timestamp(data)

        if timestamp:
            LOGGER.debug(
                "Recovered %s timestamp from data: %s",
                rating_type or "price",
                timestamp,
            )
        else:
            return None

        return timestamp

    @callback
    def _get_latest_timestamp(
        self,
        data: dict | None,
        container_key: str,
        entry_key: str | None = None,
        time_field: str = "startsAt",
    ) -> datetime | None:
        """Get the latest timestamp from a container in data, optionally for a subkey and time field."""
        if not data or container_key not in data:
            return None
        try:
            container = data[container_key]
            if entry_key:
                container = container.get(entry_key, [])
            latest = None
            for entry in container:
                time_str = entry.get(time_field)
                if time_str:
                    timestamp = dt_util.parse_datetime(time_str)
                    if timestamp and (not latest or timestamp > latest):
                        latest = timestamp
        except (KeyError, IndexError, TypeError):
            return None
        return latest

    @callback
    def _get_latest_price_timestamp(self, price_data: dict | None) -> datetime | None:
        """Get the latest timestamp from price data (today and tomorrow)."""
        # Check both today and tomorrow, return the latest
        today = self._get_latest_timestamp(price_data, "priceInfo", "today", "startsAt")
        tomorrow = self._get_latest_timestamp(price_data, "priceInfo", "tomorrow", "startsAt")
        if today and tomorrow:
            return max(today, tomorrow)
        return today or tomorrow

    @callback
    def _get_latest_rating_timestamp(self, rating_data: dict | None, rating_type: str | None = None) -> datetime | None:
        """Get the latest timestamp from rating data, optionally for a specific type."""
        if not rating_type:
            # Check all types and return the latest
            latest = None
            for rtype in ("hourly", "daily", "monthly"):
                ts = self._get_latest_timestamp(rating_data, "priceRating", rtype, "time")
                if ts and (not latest or ts > latest):
                    latest = ts
            return latest
        return self._get_latest_timestamp(rating_data, "priceRating", rating_type, "time")
