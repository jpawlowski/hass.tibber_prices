"""Coordinator for fetching Tibber price data."""

from __future__ import annotations

import asyncio
import logging
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
    if not price_data:
        return None

    try:
        latest_timestamp = None

        # Check today's prices
        if today_prices := price_data.get("today"):
            for price in today_prices:
                if starts_at := price.get("startsAt"):
                    timestamp = dt_util.parse_datetime(starts_at)
                    if timestamp and (not latest_timestamp or timestamp > latest_timestamp):
                        latest_timestamp = timestamp

        # Check tomorrow's prices
        if tomorrow_prices := price_data.get("tomorrow"):
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


class TibberPricesDataUpdateCoordinator(DataUpdateCoordinator[dict]):
    """Coordinator for fetching Tibber price data."""

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
        self._remove_update_listeners: list[Any] = []
        self._force_update = False
        self._rotation_lock = asyncio.Lock()
        self._last_attempted_price_update: datetime | None = None
        self._random_update_minute: int | None = None
        self._random_update_date: date | None = None
        self._remove_update_listeners.append(
            async_track_time_change(
                hass,
                self._async_refresh_quarter_hour,
                minute=[0, 15, 30, 45],
                second=0,
            )
        )

    async def async_shutdown(self) -> None:
        """Clean up coordinator on shutdown."""
        await super().async_shutdown()
        for listener in self._remove_update_listeners:
            listener()

    async def async_request_refresh(self) -> None:
        """Request an immediate refresh of the data."""
        self._force_update = True
        await self.async_refresh()

    async def _async_refresh_quarter_hour(self, now: datetime | None = None) -> None:
        """Refresh at every quarter hour, and rotate at midnight before update."""
        if now and now.hour == 0 and now.minute == 0:
            if self._is_today_data_stale():
                LOGGER.warning("Detected stale 'today' data (not from today) at midnight. Forcing full refresh.")
                await self._fetch_all_data()
            else:
                await self._perform_midnight_rotation()
        await self.async_refresh()

    async def _async_update_data(self) -> dict:
        """Fetch new state data for the coordinator. Handles expired credentials by raising ConfigEntryAuthFailed."""
        if self._cached_price_data is None:
            try:
                await self._async_initialize()
            except TimeoutError as exception:
                msg = "Timeout during initialization"
                LOGGER.error(
                    "%s: %s",
                    msg,
                    exception,
                    extra={"error_type": "timeout_init"},
                )
                raise UpdateFailed(msg) from exception
            except TibberPricesApiClientAuthenticationError as exception:
                msg = "Authentication failed: credentials expired or invalid"
                LOGGER.error(
                    "Authentication failed (likely expired credentials) during initialization",
                    extra={"error": str(exception), "error_type": "auth_failed_init"},
                )
                raise ConfigEntryAuthFailed(msg) from exception
            except Exception as exception:
                msg = "Unexpected error during initialization"
                LOGGER.exception(
                    "%s",
                    msg,
                    extra={"error": str(exception), "error_type": "unexpected_init"},
                )
                raise UpdateFailed(msg) from exception
        try:
            current_time = dt_util.now()
            result = None
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
                self._force_update = False
                result = await self._fetch_all_data()
            else:
                result = await self._handle_conditional_update(current_time)
        except TibberPricesApiClientAuthenticationError as exception:
            msg = "Authentication failed: credentials expired or invalid"
            LOGGER.error(
                "Authentication failed (likely expired credentials)",
                extra={"error": str(exception), "error_type": "auth_failed"},
            )
            raise ConfigEntryAuthFailed(msg) from exception
        except TimeoutError as exception:
            msg = "Timeout during data update"
            LOGGER.warning(
                "%s: %s",
                msg,
                exception,
                extra={"error_type": "timeout_runtime"},
            )
            if self._cached_price_data is not None:
                LOGGER.info("Using cached data as fallback after timeout")
                return self._merge_all_cached_data()
            raise UpdateFailed(msg) from exception
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

    async def _fetch_all_data(self) -> dict:
        """Fetch all data from the API without checking update conditions."""
        current_time = dt_util.now()
        new_data = {
            "price_data": None,
            "rating_data": {"hourly": None, "daily": None, "monthly": None},
        }
        try:
            price_data = await self._fetch_price_data()
            new_data["price_data"] = self._extract_data(price_data, "priceInfo", ("yesterday", "today", "tomorrow"))
            for rating_type in ["hourly", "daily", "monthly"]:
                try:
                    rating_data = await self._get_rating_data_for_type(rating_type)
                    new_data["rating_data"][rating_type] = rating_data
                except TibberPricesApiClientError as ex:
                    LOGGER.error("Failed to fetch %s rating data: %s", rating_type, ex)
        except TibberPricesApiClientError as ex:
            LOGGER.error("Failed to fetch price data: %s", ex)
            if self._cached_price_data is not None:
                LOGGER.info("Using cached data as fallback after price data fetch failure")
                return self._merge_all_cached_data()
            raise
        if new_data["price_data"] is None:
            LOGGER.error("No price data available after fetch")
            if self._cached_price_data is not None:
                LOGGER.info("Using cached data as fallback due to missing price data")
                return self._merge_all_cached_data()
            _raise_no_data()
        self._cached_price_data = cast("dict", new_data["price_data"])
        self._last_price_update = current_time
        for rating_type, rating_data in new_data["rating_data"].items():
            if rating_data is not None:
                self._update_rating_cache(rating_type, rating_data, current_time)
        await self._store_cache()
        LOGGER.debug("Updated and stored all cache data at %s", current_time)
        return self._merge_all_cached_data()

    async def _fetch_price_data(self) -> dict:
        """Fetch fresh price data from API. Assumes errors are handled in api.py."""
        client = self.config_entry.runtime_data.client
        home_id = self.config_entry.unique_id
        if not home_id:
            LOGGER.error("No home_id (unique_id) set in config entry!")
            return {}
        data = await client.async_get_price_info(home_id)
        if not data:
            return {}
        price_info = data.get("priceInfo", {})
        if not price_info:
            return {}
        return price_info

    async def _get_rating_data_for_type(self, rating_type: str) -> dict:
        """Get fresh rating data for a specific type in flat format. Assumes errors are handled in api.py."""
        client = self.config_entry.runtime_data.client
        home_id = self.config_entry.unique_id
        if not home_id:
            LOGGER.error("No home_id (unique_id) set in config entry!")
            return {}
        method_map = {
            "hourly": client.async_get_hourly_price_rating,
            "daily": client.async_get_daily_price_rating,
            "monthly": client.async_get_monthly_price_rating,
        }
        fetch_method = method_map.get(rating_type)
        if not fetch_method:
            msg = f"Unknown rating type: {rating_type}"
            raise ValueError(msg)
        data = await fetch_method(home_id)
        if not data:
            return {}
        try:
            price_rating = data.get("priceRating", data)
            threshold = price_rating.get("thresholdPercentages")
            entries = price_rating.get(rating_type, [])
            currency = price_rating.get("currency")
        except KeyError as ex:
            LOGGER.error("Failed to extract rating data (flat format): %s", ex)
            raise TibberPricesApiClientError(
                TibberPricesApiClientError.EMPTY_DATA_ERROR.format(query_type=rating_type)
            ) from ex
        return {"priceRating": {rating_type: entries, "thresholdPercentages": threshold, "currency": currency}}

    async def _async_initialize(self) -> None:
        """Load stored data in flat format and check for stale 'today' data."""
        stored = await self._store.async_load()
        if stored is None:
            LOGGER.warning("No cache file found or cache is empty on startup.")
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
            # Stale data detection on startup
            if self._is_today_data_stale():
                LOGGER.warning("Detected stale 'today' data on startup (not from today). Forcing full refresh.")
                await self._fetch_all_data()
        else:
            LOGGER.info("No cache loaded; will fetch fresh data on first update.")

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

    async def _perform_midnight_rotation(self) -> None:
        """Perform the data rotation at midnight within the hourly update process."""
        LOGGER.info("Performing midnight data rotation as part of hourly update cycle")
        if not self._cached_price_data:
            LOGGER.debug("No cached price data available for midnight rotation")
            return
        async with self._rotation_lock:
            try:
                today_count = len(self._cached_price_data.get("today", []))
                tomorrow_count = len(self._cached_price_data.get("tomorrow", []))
                yesterday_count = len(self._cached_price_data.get("yesterday", []))
                LOGGER.debug(
                    "Before rotation - Yesterday: %d, Today: %d, Tomorrow: %d items",
                    yesterday_count,
                    today_count,
                    tomorrow_count,
                )
                if today_data := self._cached_price_data.get("today"):
                    self._cached_price_data["yesterday"] = today_data
                else:
                    LOGGER.warning("No today's data available to move to yesterday")
                if tomorrow_data := self._cached_price_data.get("tomorrow"):
                    self._cached_price_data["today"] = tomorrow_data
                    self._cached_price_data["tomorrow"] = []
                else:
                    LOGGER.warning("No tomorrow's data available to move to today")
                await self._store_cache()
                LOGGER.info(
                    "Completed midnight rotation - Yesterday: %d, Today: %d, Tomorrow: %d items",
                    len(self._cached_price_data.get("yesterday", [])),
                    len(self._cached_price_data.get("today", [])),
                    len(self._cached_price_data.get("tomorrow", [])),
                )
                self._force_update = True
            except (KeyError, TypeError, ValueError) as ex:
                LOGGER.error("Error during midnight data rotation in hourly update: %s", ex)

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

    def _log_update_decision(self, ctx: dict) -> None:
        """Log update decision context for debugging."""
        LOGGER.debug("[tibber_prices] Update decision: %s", ctx)

    def _get_tomorrow_data_status(self) -> tuple[int, bool]:
        """Return (interval_count, tomorrow_data_complete) for tomorrow's prices (flat structure)."""
        tomorrow_prices = []
        if self._cached_price_data:
            raw_tomorrow = self._cached_price_data.get("tomorrow", [])
            if raw_tomorrow is None:
                LOGGER.warning(
                    "Tomorrow price data is None, treating as empty list. Full price_data: %s",
                    self._cached_price_data,
                )
                tomorrow_prices = []
            elif not isinstance(raw_tomorrow, list):
                LOGGER.warning(
                    "Tomorrow price data is not a list: %r. Full price_data: %s",
                    raw_tomorrow,
                    self._cached_price_data,
                )
                tomorrow_prices = list(raw_tomorrow) if hasattr(raw_tomorrow, "__iter__") else []
            else:
                tomorrow_prices = raw_tomorrow
        else:
            LOGGER.warning("No cached price_data available: %s", self._cached_price_data)
        interval_count = len(tomorrow_prices)
        min_tomorrow_intervals_hourly = 24
        min_tomorrow_intervals_15min = 96
        tomorrow_data_complete = interval_count in {min_tomorrow_intervals_hourly, min_tomorrow_intervals_15min}
        if interval_count == 0:
            LOGGER.debug(
                "Tomorrow price data is empty at late hour. Raw tomorrow data: %s | Full price_data: %s",
                tomorrow_prices,
                self._cached_price_data,
            )
        return interval_count, tomorrow_data_complete

    @callback
    def _should_update_price_data(self, current_time: datetime) -> bool:
        """Decide if price data should be updated. Logs all decision points for debugging."""
        should_update, log_ctx = self._decide_price_update(current_time)
        self._log_update_decision(log_ctx)
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
        # Always use last_update if present and valid
        if last_update and (current_time - last_update) < interval:
            return False
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

    @callback
    def _extract_data(self, data: dict, container_key: str, keys: tuple[str, ...]) -> dict:
        """Extract and harmonize data for caching in flat format."""
        # For price data, just flatten to {key: list} for each key
        try:
            container = data[container_key]
            if not isinstance(container, dict):
                LOGGER.error(
                    "Extracted %s is not a dict: %r. Full data: %s",
                    container_key,
                    container,
                    data,
                )
                container = {}
            extracted = {key: list(container.get(key, [])) for key in keys}
        except (KeyError, IndexError, TypeError):
            # For flat price data, just copy keys from data
            extracted = {key: list(data.get(key, [])) for key in keys}
        return extracted

    @callback
    def _update_rating_cache(self, rating_type: str, rating_data: dict, current_time: datetime) -> None:
        """Update the rating cache for a specific rating type."""
        if rating_type == "hourly":
            self._cached_rating_data_hourly = cast("dict", rating_data)
            self._last_rating_update_hourly = current_time
        elif rating_type == "daily":
            self._cached_rating_data_daily = cast("dict", rating_data)
            self._last_rating_update_daily = current_time
        else:
            self._cached_rating_data_monthly = cast("dict", rating_data)
            self._last_rating_update_monthly = current_time
        LOGGER.debug("Updated %s rating data cache at %s", rating_type, current_time)

    @callback
    def _merge_all_cached_data(self) -> dict:
        """Merge all cached data into Home Assistant-style structure: priceInfo, priceRating, currency."""
        if not self._cached_price_data:
            return {}
        merged = {
            "priceInfo": dict(self._cached_price_data),  # 'today', 'tomorrow', 'yesterday' under 'priceInfo'
        }
        price_rating = {
            "hourly": [],
            "daily": [],
            "monthly": [],
            "thresholdPercentages": None,
            "currency": None,
        }
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
                if not price_rating["currency"]:
                    price_rating["currency"] = cached["priceRating"].get("currency")
        merged["priceRating"] = price_rating
        merged["currency"] = price_rating["currency"]
        return merged

    @callback
    def _recover_timestamp(
        self,
        data: dict | None,
        stored_timestamp: str | None,
        rating_type: str | None = None,
    ) -> datetime | None:
        """Recover timestamp from stored value or data."""
        # Always prefer the stored timestamp if present and valid
        if stored_timestamp:
            ts = dt_util.parse_datetime(stored_timestamp)
            if ts:
                return ts
        # Fallback to data-derived timestamp
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
        if not price_data:
            return None
        today = self._get_latest_timestamp(price_data, "today", None, "startsAt")
        tomorrow = self._get_latest_timestamp(price_data, "tomorrow", None, "startsAt")
        if today and tomorrow:
            return max(today, tomorrow)
        return today or tomorrow

    @callback
    def _get_latest_rating_timestamp(self, rating_data: dict | None, rating_type: str | None = None) -> datetime | None:
        """Get the latest timestamp from rating data, optionally for a specific type."""
        if not rating_type:
            latest = None
            for rtype in ("hourly", "daily", "monthly"):
                ts = self._get_latest_timestamp(rating_data, "priceRating", rtype, "time")
                if ts and (not latest or ts > latest):
                    latest = ts
            return latest
        return self._get_latest_timestamp(rating_data, "priceRating", rating_type, "time")

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

    def get_all_intervals(self) -> list[dict]:
        """Return a combined, sorted list of all price intervals for yesterday, today, and tomorrow."""
        price_info = self.data.get("priceInfo", {}) if self.data else {}
        all_prices = price_info.get("yesterday", []) + price_info.get("today", []) + price_info.get("tomorrow", [])
        return sorted(
            all_prices,
            key=lambda p: dt_util.parse_datetime(p.get("startsAt") or "") or dt_util.now(),
        )

    def get_interval_granularity(self) -> int | None:
        """Return the interval granularity in minutes (e.g., 15 or 60) for today's data."""
        price_info = self.data.get("priceInfo", {}) if self.data else {}
        today_prices = price_info.get("today", [])
        from .sensor import detect_interval_granularity

        return detect_interval_granularity(today_prices) if today_prices else None

    def get_current_interval_data(self) -> dict | None:
        """Return the price data for the current interval."""
        price_info = self.data.get("priceInfo", {}) if self.data else {}
        if not price_info:
            return None
        now = dt_util.now()
        interval_length = self.get_interval_granularity()
        from .sensor import find_price_data_for_interval

        return find_price_data_for_interval(price_info, now, interval_length)

    def get_combined_price_info(self) -> dict:
        """Return a dict with all intervals under a single key 'all'."""
        return {"all": self.get_all_intervals()}

    def is_tomorrow_data_available(self) -> bool | None:
        """Return True if tomorrow's data is fully available, False if not, None if unknown."""
        tomorrow_prices = self.data.get("priceInfo", {}).get("tomorrow", []) if self.data else []
        interval_count = len(tomorrow_prices)
        min_tomorrow_intervals_hourly = 24
        min_tomorrow_intervals_15min = 96
        tomorrow_interval_counts = {min_tomorrow_intervals_hourly, min_tomorrow_intervals_15min}
        return interval_count in tomorrow_interval_counts

    def _transform_api_response(self, data: dict[str, Any]) -> dict:
        """Transform API response to coordinator data format."""
        return cast("dict", data)

    def _should_update_random_window(self, current_time: datetime, log_ctx: dict) -> tuple[bool, dict]:
        """Determine if a random update should occur in the random window (13:00-15:00)."""
        today = current_time.date()
        if self._random_update_date != today or self._random_update_minute is None:
            self._random_update_date = today
            import secrets

            self._random_update_minute = secrets.randbelow(RANDOM_DELAY_MAX_MINUTES)
        log_ctx["window"] = "random"
        log_ctx["random_update_minute"] = self._random_update_minute
        log_ctx["current_minute"] = current_time.minute
        if current_time.minute == self._random_update_minute:
            if self._last_attempted_price_update:
                since_last = current_time - self._last_attempted_price_update
                log_ctx["since_last_attempt"] = str(since_last)
                if since_last >= MIN_RETRY_INTERVAL:
                    self._last_attempted_price_update = current_time
                    log_ctx["reason"] = "random window, random minute, min retry met"
                    log_ctx["decision"] = True
                    return True, log_ctx
                log_ctx["reason"] = "random window, random minute, min retry not met"
                log_ctx["decision"] = False
                return False, log_ctx
            self._last_attempted_price_update = current_time
            log_ctx["reason"] = "random window, first attempt"
            log_ctx["decision"] = True
            return True, log_ctx
        log_ctx["reason"] = "random window, not random minute"
        log_ctx["decision"] = False
        return False, log_ctx

    def _decide_price_update(self, current_time: datetime) -> tuple[bool, dict]:
        current_hour = current_time.hour
        log_ctx = {
            "current_time": str(current_time),
            "current_hour": current_hour,
            "has_cached_price_data": bool(self._cached_price_data),
            "last_price_update": str(self._last_price_update) if self._last_price_update else None,
        }
        should_update = False
        if current_hour < PRICE_UPDATE_RANDOM_MIN_HOUR:
            should_update = not self._cached_price_data
            log_ctx["window"] = "early"
            log_ctx["reason"] = "no cache" if should_update else "cache present"
            log_ctx["decision"] = should_update
            return should_update, log_ctx
        interval_count, tomorrow_data_complete = self._get_tomorrow_data_status()
        log_ctx["interval_count"] = interval_count
        log_ctx["tomorrow_data_complete"] = tomorrow_data_complete
        in_random_window = PRICE_UPDATE_RANDOM_MIN_HOUR <= current_hour < PRICE_UPDATE_RANDOM_MAX_HOUR
        in_late_window = PRICE_UPDATE_RANDOM_MAX_HOUR <= current_hour < END_OF_DAY_HOUR
        if (
            tomorrow_data_complete
            and self._last_price_update
            and (current_time - self._last_price_update) < UPDATE_INTERVAL
        ):
            should_update = False
            log_ctx["window"] = "any"
            log_ctx["reason"] = "tomorrow_data_complete and last_price_update < 24h"
            log_ctx["decision"] = should_update
            return should_update, log_ctx
        if in_random_window and not tomorrow_data_complete:
            return self._should_update_random_window(current_time, log_ctx)
        if in_late_window and not tomorrow_data_complete:
            should_update = True
            log_ctx["window"] = "late"
            log_ctx["reason"] = "late window, tomorrow data missing (force update)"
            log_ctx["decision"] = should_update
            return should_update, log_ctx
        should_update = False
        log_ctx["window"] = "late-or-random"
        log_ctx["reason"] = "no update needed"
        log_ctx["decision"] = should_update
        return should_update, log_ctx

    def _is_today_data_stale(self) -> bool:
        """Return True if the first 'today' interval is not from today (stale cache)."""
        if not self._cached_price_data:
            return True
        today_prices = self._cached_price_data.get("today", [])
        if not today_prices:
            return True  # No data, treat as stale
        first = today_prices[0]
        starts_at = first.get("startsAt")
        if not starts_at:
            return True
        dt = dt_util.parse_datetime(starts_at)
        if not dt:
            return True
        return dt.date() != dt_util.now().date()
