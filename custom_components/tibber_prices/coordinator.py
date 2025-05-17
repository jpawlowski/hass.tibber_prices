"""Coordinator for fetching Tibber price data."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Final, TypedDict, cast

import homeassistant.util.dt as dt_util
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    TibberPricesApiClientAuthenticationError,
    TibberPricesApiClientCommunicationError,
    TibberPricesApiClientError,
)
from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from collections.abc import Callable

    from .data import TibberPricesConfigEntry

_LOGGER = logging.getLogger(__name__)

PRICE_UPDATE_RANDOM_MIN_HOUR: Final = 13  # Don't check before 13:00
PRICE_UPDATE_RANDOM_MAX_HOUR: Final = 15  # Don't check after 15:00
RANDOM_DELAY_MAX_MINUTES: Final = 120  # Maximum random delay in minutes
NO_DATA_ERROR_MSG: Final = "No data available"
STORAGE_VERSION: Final = 1
UPDATE_INTERVAL: Final = timedelta(days=1)  # Both price and rating data update daily
UPDATE_FAILED_MSG: Final = "Update failed"
AUTH_FAILED_MSG: Final = "Authentication failed"


class TibberPricesPriceInfo(TypedDict):
    """Type for price info data structure."""

    today: list[dict[str, Any]]
    tomorrow: list[dict[str, Any]]
    yesterday: list[dict[str, Any]]


class TibberPricesPriceRating(TypedDict):
    """Type for price rating data structure."""

    thresholdPercentages: dict[str, float] | None
    hourly: dict[str, Any] | None
    daily: dict[str, Any] | None
    monthly: dict[str, Any] | None


class TibberPricesSubscriptionData(TypedDict):
    """Type for price info data structure."""

    priceInfo: TibberPricesPriceInfo
    priceRating: TibberPricesPriceRating


class TibberPricesData(TypedDict):
    """Type for Tibber API response data structure."""

    data: dict[str, dict[str, list[dict[str, TibberPricesSubscriptionData]]]]


@callback
def _raise_no_data() -> None:
    """Raise error when no data is available."""
    raise TibberPricesApiClientError(NO_DATA_ERROR_MSG)


@callback
def _get_latest_timestamp_from_prices(
    price_data: TibberPricesData | None,
) -> datetime | None:
    """Get the latest timestamp from price data."""
    if not price_data or "data" not in price_data:
        return None

    try:
        subscription = price_data["data"]["viewer"]["homes"][0]["currentSubscription"]
        price_info = subscription["priceInfo"]
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
    rating_data: TibberPricesData | None,
) -> datetime | None:
    """Get the latest timestamp from rating data."""
    if not rating_data or "data" not in rating_data:
        return None

    try:
        subscription = rating_data["data"]["viewer"]["homes"][0]["currentSubscription"]
        price_rating = subscription["priceRating"]
        latest_timestamp = None

        # Check all rating types (hourly, daily, monthly)
        for rating_type in ["hourly", "daily", "monthly"]:
            if rating_entries := price_rating.get(rating_type, {}).get("entries", []):
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
class TibberPricesDataUpdateCoordinator(DataUpdateCoordinator[TibberPricesData]):
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
        self._cached_price_data: TibberPricesData | None = None
        self._cached_rating_data_hourly: TibberPricesData | None = None
        self._cached_rating_data_daily: TibberPricesData | None = None
        self._cached_rating_data_monthly: TibberPricesData | None = None
        self._last_price_update: datetime | None = None
        self._last_rating_update_hourly: datetime | None = None
        self._last_rating_update_daily: datetime | None = None
        self._last_rating_update_monthly: datetime | None = None
        self._scheduled_price_update: asyncio.Task | None = None
        self._remove_update_listeners: list[Any] = []
        self._force_update = False
        self._rotation_lock = asyncio.Lock()  # Add lock for data rotation operations

        # Schedule updates at the start of every hour
        self._remove_update_listeners.append(
            async_track_time_change(hass, self._async_refresh_hourly, minute=0, second=0)
        )

        # Schedule data rotation at midnight
        self._remove_update_listeners.append(
            async_track_time_change(hass, self._async_handle_midnight_rotation, hour=0, minute=0, second=0)
        )

    async def async_shutdown(self) -> None:
        """Clean up coordinator on shutdown."""
        await super().async_shutdown()
        for listener in self._remove_update_listeners:
            listener()

    async def _async_handle_midnight_rotation(self, _now: datetime | None = None) -> None:
        """Handle data rotation at midnight."""
        if not self._cached_price_data:
            LOGGER.debug("No cached price data available for midnight rotation")
            return

        async with self._rotation_lock:  # Ensure rotation operations are protected
            try:
                LOGGER.debug("Starting midnight data rotation")
                subscription = self._cached_price_data["data"]["viewer"]["homes"][0]["currentSubscription"]
                price_info = subscription["priceInfo"]

                # Move today's data to yesterday
                if today_data := price_info.get("today"):
                    LOGGER.debug("Moving today's data (%d entries) to yesterday", len(today_data))
                    price_info["yesterday"] = today_data
                else:
                    LOGGER.debug("No today's data available to move to yesterday")

                # Move tomorrow's data to today
                if tomorrow_data := price_info.get("tomorrow"):
                    LOGGER.debug("Moving tomorrow's data (%d entries) to today", len(tomorrow_data))
                    price_info["today"] = tomorrow_data
                    price_info["tomorrow"] = []
                else:
                    LOGGER.warning("No tomorrow's data available to move to today, clearing today's data")
                    price_info["today"] = []

                # Store the rotated data
                await self._store_cache()
                LOGGER.debug("Completed midnight data rotation")

                # No need to schedule immediate refresh - tomorrow's data won't be available yet
                # We'll wait for the regular update cycle between 13:00-15:00

            except (KeyError, TypeError, ValueError) as ex:
                LOGGER.error("Error during midnight data rotation: %s", ex)

    @callback
    def _recover_timestamp(
        self,
        data: TibberPricesData | None,
        stored_timestamp: str | None,
        rating_type: str | None = None,
    ) -> datetime | None:
        """Recover timestamp from data or stored value."""
        if stored_timestamp:
            return dt_util.parse_datetime(stored_timestamp)

        if not data:
            return None

        if rating_type:
            timestamp = self._get_latest_timestamp_from_rating_type(data, rating_type)
        else:
            timestamp = _get_latest_timestamp_from_prices(data)

        if timestamp:
            LOGGER.debug(
                "Recovered %s timestamp from data: %s",
                rating_type or "price",
                timestamp,
            )
        else:
            return None

        return timestamp

    async def _async_initialize(self) -> None:
        """Load stored data."""
        stored = await self._store.async_load()
        if stored is None:
            LOGGER.warning("No cache file found or cache is empty on startup.")
        else:
            LOGGER.debug("Loading stored data: %s", stored)

        if stored:
            # Load cached data
            self._cached_price_data = cast("TibberPricesData", stored.get("price_data"))
            self._cached_rating_data_hourly = cast("TibberPricesData", stored.get("rating_data_hourly"))
            self._cached_rating_data_daily = cast("TibberPricesData", stored.get("rating_data_daily"))
            self._cached_rating_data_monthly = cast("TibberPricesData", stored.get("rating_data_monthly"))

            # Recover timestamps
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

            # Defensive: warn if any required data is missing
            if self._cached_price_data is None:
                LOGGER.warning("Cached price data missing after cache load!")
            if self._last_price_update is None:
                LOGGER.warning("Price update timestamp missing after cache load!")
        else:
            LOGGER.info("No cache loaded; will fetch fresh data on first update.")

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

    async def _async_update_data(self) -> TibberPricesData:
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

    async def _handle_conditional_update(self, current_time: datetime) -> TibberPricesData:
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

    async def _fetch_all_data(self) -> TibberPricesData:
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
            new_data["price_data"] = self._extract_price_data(price_data)

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
        self._cached_price_data = cast("TibberPricesData", new_data["price_data"])
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
    def _update_rating_cache(self, rating_type: str, rating_data: TibberPricesData, current_time: datetime) -> None:
        """Update the rating cache for a specific rating type."""
        if rating_type == "hourly":
            self._cached_rating_data_hourly = cast("TibberPricesData", rating_data)
            self._last_rating_update_hourly = current_time
        elif rating_type == "daily":
            self._cached_rating_data_daily = cast("TibberPricesData", rating_data)
            self._last_rating_update_daily = current_time
        else:  # monthly
            self._cached_rating_data_monthly = cast("TibberPricesData", rating_data)
            self._last_rating_update_monthly = current_time
        LOGGER.debug("Updated %s rating data cache at %s", rating_type, current_time)

    async def _store_cache(self) -> None:
        """Store cache data."""

        def _recover_and_log_timestamp(
            data: TibberPricesData | None,
            last_update: datetime | None,
            get_latest_fn: Callable[[TibberPricesData], datetime | None],
            label: str,
        ) -> datetime | None:
            if data and not last_update:
                latest_timestamp = get_latest_fn(data)
                if latest_timestamp:
                    LOGGER.debug("Setting missing %s timestamp to: %s", label, latest_timestamp)
                    return latest_timestamp
                LOGGER.warning("Could not recover %s timestamp from data!", label)
            return last_update

        self._last_price_update = _recover_and_log_timestamp(
            self._cached_price_data,
            self._last_price_update,
            _get_latest_timestamp_from_prices,
            "price update",
        )
        self._last_rating_update_hourly = _recover_and_log_timestamp(
            self._cached_rating_data_hourly,
            self._last_rating_update_hourly,
            lambda d: self._get_latest_timestamp_from_rating_type(d, "hourly"),
            "hourly rating",
        )
        self._last_rating_update_daily = _recover_and_log_timestamp(
            self._cached_rating_data_daily,
            self._last_rating_update_daily,
            lambda d: self._get_latest_timestamp_from_rating_type(d, "daily"),
            "daily rating",
        )
        self._last_rating_update_monthly = _recover_and_log_timestamp(
            self._cached_rating_data_monthly,
            self._last_rating_update_monthly,
            lambda d: self._get_latest_timestamp_from_rating_type(d, "monthly"),
            "monthly rating",
        )

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
        # Defensive: warn if any required data is missing before saving
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
        """Check if price data should be updated."""
        # If no cached data, we definitely need an update
        if self._cached_price_data is None:
            LOGGER.debug("No cached price data available, update needed")
            return True

        # Get the latest timestamp from our price data
        latest_price_timestamp = _get_latest_timestamp_from_prices(self._cached_price_data)
        if not latest_price_timestamp:
            LOGGER.debug("No valid timestamp found in price data, update needed")
            return True

        # If we have price data but no last_update timestamp, set it
        if not self._last_price_update:
            self._last_price_update = latest_price_timestamp
            LOGGER.debug(
                "Setting missing price update timestamp in check: %s",
                self._last_price_update,
            )

        # Check if we're in the update window (13:00-15:00)
        current_hour = current_time.hour
        in_update_window = PRICE_UPDATE_RANDOM_MIN_HOUR <= current_hour <= PRICE_UPDATE_RANDOM_MAX_HOUR

        # Get tomorrow's date at midnight
        tomorrow = (current_time + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

        # If we're in the update window and don't have tomorrow's complete data
        if in_update_window and latest_price_timestamp < tomorrow:
            LOGGER.debug(
                "In update window (%d:00) and latest price timestamp (%s) is before tomorrow, update needed",
                current_hour,
                latest_price_timestamp,
            )
            return True

        # If it's been more than 24 hours since our last update
        if self._last_price_update and current_time - self._last_price_update >= UPDATE_INTERVAL:
            LOGGER.debug(
                "More than 24 hours since last price update (%s), update needed",
                self._last_price_update,
            )
            return True

        LOGGER.debug(
            "No price update needed - Last update: %s, Latest data: %s",
            self._last_price_update,
            latest_price_timestamp,
        )
        return False

    @callback
    def _should_update_rating_type(
        self,
        current_time: datetime,
        cached_data: TibberPricesData | None,
        last_update: datetime | None,
        rating_type: str,
    ) -> bool:
        """Check if specific rating type should be updated."""
        # If no cached data, we definitely need an update
        if cached_data is None:
            LOGGER.debug("No cached %s rating data available, update needed", rating_type)
            return True

        # Get the latest timestamp from our rating data
        latest_timestamp = self._get_latest_timestamp_from_rating_type(cached_data, rating_type)
        if not latest_timestamp:
            LOGGER.debug("No valid timestamp found in %s rating data, update needed", rating_type)
            return True

        # If we have rating data but no last_update timestamp, set it
        if not last_update:
            if rating_type == "hourly":
                self._last_rating_update_hourly = latest_timestamp
            elif rating_type == "daily":
                self._last_rating_update_daily = latest_timestamp
            else:  # monthly
                self._last_rating_update_monthly = latest_timestamp
            LOGGER.debug(
                "Setting missing %s rating timestamp in check: %s",
                rating_type,
                latest_timestamp,
            )
            last_update = latest_timestamp

        current_hour = current_time.hour
        in_update_window = PRICE_UPDATE_RANDOM_MIN_HOUR <= current_hour <= PRICE_UPDATE_RANDOM_MAX_HOUR
        should_update = False

        if rating_type == "monthly":
            current_month_start = current_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            should_update = latest_timestamp < current_month_start or (
                last_update and current_time - last_update >= timedelta(days=1)
            )
        else:
            tomorrow = (current_time + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            should_update = (
                in_update_window and latest_timestamp < tomorrow
            ) or current_time - last_update >= UPDATE_INTERVAL

        if should_update:
            LOGGER.debug(
                "Update needed for %s rating data - Last update: %s, Latest data: %s",
                rating_type,
                last_update,
                latest_timestamp,
            )
        else:
            LOGGER.debug(
                "No %s rating update needed - Last update: %s, Latest data: %s",
                rating_type,
                last_update,
                latest_timestamp,
            )

        return should_update

    @callback
    def _is_price_update_window(self, current_hour: int) -> bool:
        """Check if current hour is within price update window."""
        return PRICE_UPDATE_RANDOM_MIN_HOUR <= current_hour <= PRICE_UPDATE_RANDOM_MAX_HOUR

    async def _fetch_price_data(self) -> dict:
        """Fetch fresh price data from API."""
        client = self.config_entry.runtime_data.client
        return await client.async_get_price_info()

    @callback
    def _extract_price_data(self, data: dict) -> dict:
        """Extract price data for caching."""
        try:
            # Try to access data in the transformed structure first
            try:
                price_info = data["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]
            except KeyError:
                # If that fails, try the raw data structure
                price_info = data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]

            # Ensure we have all required fields
            extracted_price_info = {
                "today": price_info.get("today", []),
                "tomorrow": price_info.get("tomorrow", []),
                "yesterday": price_info.get("yesterday", []),
            }
        except (KeyError, IndexError) as ex:
            LOGGER.error("Error extracting price data: %s", ex)
            return {
                "data": {
                    "viewer": {
                        "homes": [
                            {
                                "currentSubscription": {
                                    "priceInfo": {
                                        "today": [],
                                        "tomorrow": [],
                                        "yesterday": [],
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        return {"data": {"viewer": {"homes": [{"currentSubscription": {"priceInfo": extracted_price_info}}]}}}

    @callback
    def _get_latest_timestamp_from_rating_type(
        self, rating_data: TibberPricesData | None, rating_type: str
    ) -> datetime | None:
        """Get the latest timestamp from a specific rating type."""
        if not rating_data or "data" not in rating_data:
            return None

        try:
            subscription = rating_data["data"]["viewer"]["homes"][0]["currentSubscription"]
            price_rating = subscription["priceRating"]
            result = None

            if rating_entries := price_rating.get(rating_type, {}).get("entries", []):
                for entry in rating_entries:
                    if time := entry.get("time"):
                        timestamp = dt_util.parse_datetime(time)
                        if timestamp and (not result or timestamp > result):
                            result = timestamp
        except (KeyError, IndexError, TypeError):
            return None
        return result

    async def _get_rating_data_for_type(self, rating_type: str) -> dict:
        """Get fresh rating data for a specific type."""
        client = self.config_entry.runtime_data.client

        if rating_type == "hourly":
            data = await client.async_get_hourly_price_rating()
        elif rating_type == "daily":
            data = await client.async_get_daily_price_rating()
        else:  # monthly
            data = await client.async_get_monthly_price_rating()

        try:
            # Try to access data in the transformed structure first
            rating = data["viewer"]["homes"][0]["currentSubscription"]["priceRating"]
        except KeyError:
            try:
                # If that fails, try the raw data structure
                rating = data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceRating"]
            except KeyError as ex:
                LOGGER.error("Failed to extract rating data: %s", ex)
                raise TibberPricesApiClientError(
                    TibberPricesApiClientError.EMPTY_DATA_ERROR.format(query_type=rating_type)
                ) from ex
            else:
                return {
                    "data": {
                        "viewer": {
                            "homes": [
                                {
                                    "currentSubscription": {
                                        "priceRating": {
                                            "thresholdPercentages": rating["thresholdPercentages"],
                                            rating_type: rating[rating_type],
                                        }
                                    }
                                }
                            ]
                        }
                    }
                }
        else:
            return {
                "data": {
                    "viewer": {
                        "homes": [
                            {
                                "currentSubscription": {
                                    "priceRating": {
                                        "thresholdPercentages": rating["thresholdPercentages"],
                                        rating_type: rating[rating_type],
                                    }
                                }
                            }
                        ]
                    }
                }
            }

    @callback
    def _merge_all_cached_data(self) -> TibberPricesData:
        """Merge all cached data."""
        if not self._cached_price_data:
            return cast("TibberPricesData", {})

        # Start with price info
        subscription = {
            "priceInfo": self._cached_price_data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"],
            "priceRating": {
                "thresholdPercentages": None,
            },
        }

        # Add rating data if available
        rating_data = {
            "hourly": self._cached_rating_data_hourly,
            "daily": self._cached_rating_data_daily,
            "monthly": self._cached_rating_data_monthly,
        }

        for rating_type, data in rating_data.items():
            if data and "data" in data:
                rating = data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceRating"]

                # Set thresholdPercentages from any available rating data
                if not subscription["priceRating"]["thresholdPercentages"]:
                    subscription["priceRating"]["thresholdPercentages"] = rating["thresholdPercentages"]

                # Add the specific rating type data
                subscription["priceRating"][rating_type] = rating[rating_type]

        return cast(
            "TibberPricesData",
            {"data": {"viewer": {"homes": [{"currentSubscription": subscription}]}}},
        )

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

    def _transform_api_response(self, data: dict[str, Any]) -> TibberPricesData:
        """Transform API response to coordinator data format."""
        return cast("TibberPricesData", data)

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
                subscription = self._cached_price_data["data"]["viewer"]["homes"][0]["currentSubscription"]
                price_info = subscription["priceInfo"]

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

    def get_all_intervals(self) -> list[dict]:
        """Return a combined, sorted list of all price intervals for yesterday, today, and tomorrow."""
        if not self.data:
            return []
        price_info = self.data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]
        all_prices = price_info.get("yesterday", []) + price_info.get("today", []) + price_info.get("tomorrow", [])
        return sorted(all_prices, key=lambda p: p["startsAt"])

    def get_interval_granularity(self) -> int | None:
        """Return the interval granularity in minutes (e.g., 15 or 60) for today's data."""
        if not self.data:
            return None
        price_info = self.data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]
        today_prices = price_info.get("today", [])
        from .sensor import detect_interval_granularity

        return detect_interval_granularity(today_prices) if today_prices else None

    def get_current_interval_data(self) -> dict | None:
        """Return the price data for the current interval."""
        if not self.data:
            return None
        price_info = self.data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]
        now = dt_util.now()
        interval_length = self.get_interval_granularity()
        from .sensor import find_price_data_for_interval

        return find_price_data_for_interval(price_info, now, interval_length)

    def get_combined_price_info(self) -> dict:
        """Return a dict with all intervals under a single key 'all'."""
        return {"all": self.get_all_intervals()}

    def is_tomorrow_data_available(self) -> bool | None:
        """Return True if tomorrow's data is fully available, False if not, None if unknown."""
        if not self.data:
            return None
        price_info = self.data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]
        tomorrow_prices = price_info.get("tomorrow", [])
        interval_count = len(tomorrow_prices)
        # Use the same logic as in binary_sensor.py
        min_tomorrow_intervals_hourly = 24
        min_tomorrow_intervals_15min = 96
        tomorrow_interval_counts = {min_tomorrow_intervals_hourly, min_tomorrow_intervals_15min}
        return interval_count in tomorrow_interval_counts
