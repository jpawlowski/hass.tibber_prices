"""Coordinator for fetching Tibber price data."""
from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any, Final, TypedDict, cast

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .api import (
    TibberPricesApiClient,
    TibberPricesApiClientError,
    TibberPricesApiClientAuthenticationError,
    TibberPricesApiClientCommunicationError,
)
from .const import (
    DOMAIN,
    LOGGER,
)

if TYPE_CHECKING:
    from .data import TibberPricesConfigEntry

_LOGGER = logging.getLogger(__name__)

PRICE_UPDATE_RANDOM_MIN_HOUR: Final = 13  # Don't check before 13:00
PRICE_UPDATE_RANDOM_MAX_HOUR: Final = 15  # Don't check after 15:00
RANDOM_DELAY_MAX_MINUTES: Final = 120  # Maximum random delay in minutes
NO_DATA_ERROR_MSG: Final = "No data available"
STORAGE_VERSION: Final = 1
UPDATE_INTERVAL: Final = timedelta(days=1)  # Both price and rating data update daily


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
def _get_latest_timestamp_from_prices(price_data: TibberPricesData | None) -> datetime | None:
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

        return latest_timestamp

    except (KeyError, IndexError, TypeError):
        return None


@callback
def _get_latest_timestamp_from_rating(rating_data: TibberPricesData | None) -> datetime | None:
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

        return latest_timestamp

    except (KeyError, IndexError, TypeError):
        return None


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

        # Schedule updates at the start of every hour
        self._remove_update_listeners.append(
            async_track_time_change(
                hass, self._async_refresh_hourly, minute=0, second=0
            )
        )

        # Schedule data rotation at midnight
        self._remove_update_listeners.append(
            async_track_time_change(
                hass, self._async_handle_midnight_rotation, hour=0, minute=0, second=0
            )
        )

    async def async_shutdown(self) -> None:
        """Clean up coordinator on shutdown."""
        await super().async_shutdown()
        for listener in self._remove_update_listeners:
            listener()

    async def _async_handle_midnight_rotation(self, _now: datetime | None = None) -> None:
        """Handle data rotation at midnight."""
        if not self._cached_price_data:
            return

        try:
            LOGGER.debug("Starting midnight data rotation")
            subscription = self._cached_price_data["data"]["viewer"]["homes"][0]["currentSubscription"]
            price_info = subscription["priceInfo"]

            # Move today's data to yesterday
            if today_data := price_info.get("today"):
                price_info["yesterday"] = today_data

            # Move tomorrow's data to today
            if tomorrow_data := price_info.get("tomorrow"):
                price_info["today"] = tomorrow_data
                price_info["tomorrow"] = []
            else:
                price_info["today"] = []

            # Store the rotated data
            await self._store_cache()
            LOGGER.debug("Completed midnight data rotation")

            # Trigger an update to refresh the entities
            await self.async_request_refresh()

        except Exception as ex:
            LOGGER.error("Error during midnight data rotation: %s", ex)

    async def _async_initialize(self) -> None:
        """Load stored data."""
        stored = await self._store.async_load()
        LOGGER.debug("Loading stored data: %s", stored)

        if stored:
            # Load cached data
            self._cached_price_data = cast(TibberPricesData, stored.get("price_data"))
            self._cached_rating_data_hourly = cast(TibberPricesData, stored.get("rating_data_hourly"))
            self._cached_rating_data_daily = cast(TibberPricesData, stored.get("rating_data_daily"))
            self._cached_rating_data_monthly = cast(TibberPricesData, stored.get("rating_data_monthly"))

            # Get timestamps from the actual data first
            latest_price_timestamp = None
            latest_hourly_timestamp = None
            latest_daily_timestamp = None
            latest_monthly_timestamp = None

            if self._cached_price_data:
                latest_price_timestamp = _get_latest_timestamp_from_prices(self._cached_price_data)
                if latest_price_timestamp and not stored.get("last_price_update"):
                    self._last_price_update = latest_price_timestamp
                    LOGGER.debug("Recovered price update timestamp from data: %s", self._last_price_update)

            if self._cached_rating_data_hourly:
                latest_hourly_timestamp = self._get_latest_timestamp_from_rating_type(
                    self._cached_rating_data_hourly, "hourly"
                )
                if latest_hourly_timestamp and not stored.get("last_rating_update_hourly"):
                    self._last_rating_update_hourly = latest_hourly_timestamp
                    LOGGER.debug("Recovered hourly rating timestamp from data: %s", self._last_rating_update_hourly)

            if self._cached_rating_data_daily:
                latest_daily_timestamp = self._get_latest_timestamp_from_rating_type(
                    self._cached_rating_data_daily, "daily"
                )
                if latest_daily_timestamp and not stored.get("last_rating_update_daily"):
                    self._last_rating_update_daily = latest_daily_timestamp
                    LOGGER.debug("Recovered daily rating timestamp from data: %s", self._last_rating_update_daily)

            if self._cached_rating_data_monthly:
                latest_monthly_timestamp = self._get_latest_timestamp_from_rating_type(
                    self._cached_rating_data_monthly, "monthly"
                )
                if latest_monthly_timestamp and not stored.get("last_rating_update_monthly"):
                    self._last_rating_update_monthly = latest_monthly_timestamp
                    LOGGER.debug("Recovered monthly rating timestamp from data: %s", self._last_rating_update_monthly)

            # Then load stored timestamps if they exist
            if last_price := stored.get("last_price_update"):
                self._last_price_update = dt_util.parse_datetime(last_price)
            if last_rating_hourly := stored.get("last_rating_update_hourly"):
                self._last_rating_update_hourly = dt_util.parse_datetime(last_rating_hourly)
            if last_rating_daily := stored.get("last_rating_update_daily"):
                self._last_rating_update_daily = dt_util.parse_datetime(last_rating_daily)
            if last_rating_monthly := stored.get("last_rating_update_monthly"):
                self._last_rating_update_monthly = dt_util.parse_datetime(last_rating_monthly)

            LOGGER.debug(
                "Loaded stored cache data - "
                "Price update: %s (latest data: %s), "
                "Rating hourly: %s (latest data: %s), "
                "daily: %s (latest data: %s), "
                "monthly: %s (latest data: %s)",
                self._last_price_update,
                latest_price_timestamp,
                self._last_rating_update_hourly,
                latest_hourly_timestamp,
                self._last_rating_update_daily,
                latest_daily_timestamp,
                self._last_rating_update_monthly,
                latest_monthly_timestamp,
            )

    async def _async_refresh_hourly(self, *_: Any) -> None:
        """Handle the hourly refresh - don't force update."""
        await self.async_refresh()

    async def _async_update_data(self) -> TibberPricesData:
        """Fetch new state data for the coordinator.

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
                        }
                    }
                )
                self._force_update = False  # Reset force update flag
                return await self._fetch_all_data()

            # Check if we need to update based on conditions
            should_update_price = self._should_update_price_data(current_time)
            should_update_hourly = self._should_update_rating_type(
                current_time, self._cached_rating_data_hourly, self._last_rating_update_hourly, "hourly"
            )
            should_update_daily = self._should_update_rating_type(
                current_time, self._cached_rating_data_daily, self._last_rating_update_daily, "daily"
            )
            should_update_monthly = self._should_update_rating_type(
                current_time, self._cached_rating_data_monthly, self._last_rating_update_monthly, "monthly"
            )

            if any([should_update_price, should_update_hourly, should_update_daily, should_update_monthly]):
                LOGGER.debug(
                    "Updating data based on conditions",
                    extra={
                        "update_price": should_update_price,
                        "update_hourly": should_update_hourly,
                        "update_daily": should_update_daily,
                        "update_monthly": should_update_monthly,
                    }
                )
                return await self._fetch_all_data()

            # Use cached data if no update needed
            if self._cached_price_data is not None:
                LOGGER.debug("Using cached data")
                return self._merge_all_cached_data()

            # If we have no cached data and no updates needed, fetch new data
            LOGGER.debug("No cached data available, fetching new data")
            return await self._fetch_all_data()

        except TibberPricesApiClientAuthenticationError as exception:
            LOGGER.error(
                "Authentication failed",
                extra={"error": str(exception), "error_type": "auth_failed"}
            )
            raise ConfigEntryAuthFailed("Authentication failed while fetching data") from exception
        except TibberPricesApiClientCommunicationError as exception:
            LOGGER.error(
                "API communication error",
                extra={"error": str(exception), "error_type": "communication_error"}
            )
            if self._cached_price_data is not None:
                LOGGER.info("Using cached data as fallback")
                return self._merge_all_cached_data()
            raise UpdateFailed(f"Error communicating with API: {exception}") from exception
        except TibberPricesApiClientError as exception:
            LOGGER.error(
                "API client error",
                extra={"error": str(exception), "error_type": "client_error"}
            )
            if self._cached_price_data is not None:
                LOGGER.info("Using cached data as fallback")
                return self._merge_all_cached_data()
            raise UpdateFailed(f"Error fetching data: {exception}") from exception
        except Exception as exception:
            LOGGER.exception(
                "Unexpected error",
                extra={"error": str(exception), "error_type": "unexpected"}
            )
            if self._cached_price_data is not None:
                LOGGER.info("Using cached data as fallback")
                return self._merge_all_cached_data()
            raise UpdateFailed(f"Unexpected error: {exception}") from exception

    async def _fetch_all_data(self) -> TibberPricesData:
        """Fetch all data from the API without checking update conditions.

        This method will:
        1. Fetch all required data (price and rating data)
        2. Validate that all data is complete and valid
        3. Only then update the cache with the new data
        4. If any data is invalid, keep using the cached data
        """
        current_time = dt_util.now()
        new_data = {
            "price_data": None,
            "rating_data": {
                "hourly": None,
                "daily": None,
                "monthly": None
            }
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
        self._cached_price_data = cast(TibberPricesData, new_data["price_data"])
        self._last_price_update = current_time

        # Update rating data cache only for types that were successfully fetched
        for rating_type, rating_data in new_data["rating_data"].items():
            if rating_data is not None:
                if rating_type == "hourly":
                    self._cached_rating_data_hourly = cast(TibberPricesData, rating_data)
                    self._last_rating_update_hourly = current_time
                elif rating_type == "daily":
                    self._cached_rating_data_daily = cast(TibberPricesData, rating_data)
                    self._last_rating_update_daily = current_time
                else:  # monthly
                    self._cached_rating_data_monthly = cast(TibberPricesData, rating_data)
                    self._last_rating_update_monthly = current_time
                LOGGER.debug("Updated %s rating data cache at %s", rating_type, current_time)

        # Store the updated cache
        await self._store_cache()
        LOGGER.debug("Updated and stored all cache data at %s", current_time)

        # Return merged data
        return self._merge_all_cached_data()

    async def _store_cache(self) -> None:
        """Store cache data."""
        # Recover any missing timestamps from the data
        if self._cached_price_data and not self._last_price_update:
            latest_timestamp = _get_latest_timestamp_from_prices(self._cached_price_data)
            if latest_timestamp:
                self._last_price_update = latest_timestamp
                LOGGER.debug("Setting missing price update timestamp to: %s", self._last_price_update)

        rating_types = {
            "hourly": (self._cached_rating_data_hourly, self._last_rating_update_hourly),
            "daily": (self._cached_rating_data_daily, self._last_rating_update_daily),
            "monthly": (self._cached_rating_data_monthly, self._last_rating_update_monthly),
        }

        for rating_type, (cached_data, last_update) in rating_types.items():
            if cached_data and not last_update:
                latest_timestamp = self._get_latest_timestamp_from_rating_type(cached_data, rating_type)
                if latest_timestamp:
                    if rating_type == "hourly":
                        self._last_rating_update_hourly = latest_timestamp
                    elif rating_type == "daily":
                        self._last_rating_update_daily = latest_timestamp
                    else:  # monthly
                        self._last_rating_update_monthly = latest_timestamp
                    LOGGER.debug("Setting missing %s rating timestamp to: %s", rating_type, latest_timestamp)

        data = {
            "price_data": self._cached_price_data,
            "rating_data_hourly": self._cached_rating_data_hourly,
            "rating_data_daily": self._cached_rating_data_daily,
            "rating_data_monthly": self._cached_rating_data_monthly,
            "last_price_update": self._last_price_update.isoformat() if self._last_price_update else None,
            "last_rating_update_hourly": self._last_rating_update_hourly.isoformat() if self._last_rating_update_hourly else None,
            "last_rating_update_daily": self._last_rating_update_daily.isoformat() if self._last_rating_update_daily else None,
            "last_rating_update_monthly": self._last_rating_update_monthly.isoformat() if self._last_rating_update_monthly else None,
        }
        LOGGER.debug("Storing cache data with timestamps: %s", {
            k: v for k, v in data.items() if k.startswith("last_")
        })
        await self._store.async_save(data)

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
            LOGGER.debug("Setting missing price update timestamp in check: %s", self._last_price_update)

        # Check if we're in the update window (13:00-15:00)
        current_hour = current_time.hour
        in_update_window = PRICE_UPDATE_RANDOM_MIN_HOUR <= current_hour <= PRICE_UPDATE_RANDOM_MAX_HOUR

        # Get tomorrow's date at midnight
        tomorrow = (current_time + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        # If we're in the update window and don't have tomorrow's complete data
        if in_update_window and latest_price_timestamp < tomorrow:
            LOGGER.debug(
                "In update window (%d:00) and latest price timestamp (%s) is before tomorrow, update needed",
                current_hour,
                latest_price_timestamp,
            )
            return True

        # If it's been more than 24 hours since our last update
        if (
            self._last_price_update
            and current_time - self._last_price_update >= UPDATE_INTERVAL
        ):
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
            LOGGER.debug("Setting missing %s rating timestamp in check: %s", rating_type, latest_timestamp)
            last_update = latest_timestamp

        current_hour = current_time.hour
        in_update_window = PRICE_UPDATE_RANDOM_MIN_HOUR <= current_hour <= PRICE_UPDATE_RANDOM_MAX_HOUR

        if rating_type == "monthly":
            # For monthly ratings:
            # 1. Check if we have data for the current month
            # 2. Update more frequently as the data changes throughout the month
            current_month_start = current_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            if latest_timestamp < current_month_start:
                LOGGER.debug(
                    "Monthly rating data is from previous month (%s), update needed",
                    latest_timestamp,
                )
                return True

            # Update monthly data daily to get updated calculations
            if last_update and current_time - last_update >= timedelta(days=1):
                LOGGER.debug(
                    "More than 24 hours since last monthly rating update (%s), update needed for latest calculations",
                    last_update,
                )
                return True
        else:
            # For hourly and daily ratings:
            # Get tomorrow's date at midnight
            tomorrow = (current_time + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

            # If we're in the update window and don't have tomorrow's data
            if in_update_window and latest_timestamp < tomorrow:
                LOGGER.debug(
                    "In update window and %s rating data (%s) is before tomorrow, update needed",
                    rating_type,
                    latest_timestamp,
                )
                return True

            # If it's been more than 24 hours since our last update
            if current_time - last_update >= UPDATE_INTERVAL:
                LOGGER.debug(
                    "More than 24 hours since last %s rating update (%s), update needed",
                    rating_type,
                    last_update,
                )
                return True

        LOGGER.debug(
            "No %s rating update needed - Last update: %s, Latest data: %s",
            rating_type,
            last_update,
            latest_timestamp,
        )
        return False

    @callback
    def _is_price_update_window(self, current_hour: int) -> bool:
        """Check if current hour is within price update window."""
        return (
            PRICE_UPDATE_RANDOM_MIN_HOUR <= current_hour <= PRICE_UPDATE_RANDOM_MAX_HOUR
        )

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

            return {
                "data": {
                    "viewer": {
                        "homes": [{
                            "currentSubscription": {
                                "priceInfo": extracted_price_info
                            }
                        }]
                    }
                }
            }
        except (KeyError, IndexError) as ex:
            LOGGER.error("Error extracting price data: %s", ex)
            return {
                "data": {
                    "viewer": {
                        "homes": [{
                            "currentSubscription": {
                                "priceInfo": {
                                    "today": [],
                                    "tomorrow": [],
                                    "yesterday": [],
                                }
                            }
                        }]
                    }
                }
            }

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
            latest_timestamp = None

            if rating_entries := price_rating.get(rating_type, {}).get("entries", []):
                for entry in rating_entries:
                    if time := entry.get("time"):
                        timestamp = dt_util.parse_datetime(time)
                        if timestamp and (not latest_timestamp or timestamp > latest_timestamp):
                            latest_timestamp = timestamp

            return latest_timestamp

        except (KeyError, IndexError, TypeError):
            return None

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
                    TibberPricesApiClientError.EMPTY_DATA_ERROR.format(
                        query_type=rating_type
                    )
                ) from ex

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
            return cast(TibberPricesData, {})

        # Start with price info
        subscription = {
            "priceInfo": self._cached_price_data["data"]["viewer"]["homes"][0][
                "currentSubscription"
            ]["priceInfo"],
            "priceRating": {
                "thresholdPercentages": None,  # Will be set from any available rating data
            }
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

        return cast(TibberPricesData, {"data": {"viewer": {"homes": [{"currentSubscription": subscription}]}}})

    async def async_request_refresh(self) -> None:
        """Request an immediate refresh of the data.

        This method will:
        1. Set the force update flag to trigger a fresh data fetch
        2. Call async_refresh to perform the update

        The force update flag will be reset after the update is complete.
        """
        self._force_update = True
        await self.async_refresh()

    def _transform_api_response(self, data: dict[str, Any]) -> TibberPricesData:
        """Transform API response to coordinator data format."""
        return cast(TibberPricesData, data)
