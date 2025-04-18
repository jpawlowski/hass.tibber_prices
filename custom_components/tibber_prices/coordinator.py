"""DataUpdateCoordinator for tibber_prices."""

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .api import (
    TibberPricesApiClientAuthenticationError,
    TibberPricesApiClientError,
)
from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import TibberPricesConfigEntry


PRICE_UPDATE_RANDOM_MIN_HOUR = 13  # Don't check before 13:00
PRICE_UPDATE_RANDOM_MAX_HOUR = 15  # Don't check after 15:00
PRICE_UPDATE_INTERVAL = timedelta(days=1)
RATING_UPDATE_INTERVAL = timedelta(hours=1)
NO_DATA_ERROR_MSG = "No data available"
STORAGE_VERSION = 1


def _raise_no_data() -> None:
    """Raise error when no data is available."""
    raise TibberPricesApiClientError(NO_DATA_ERROR_MSG)


# https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
class TibberPricesDataUpdateCoordinator(DataUpdateCoordinator):
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
        self._entry = entry
        storage_key = f"{DOMAIN}.{entry.entry_id}"
        self._store = Store(hass, STORAGE_VERSION, storage_key)
        self._cached_price_data: dict | None = None
        self._cached_rating_data: dict | None = None
        self._last_price_update: datetime | None = None
        self._last_rating_update: datetime | None = None
        self._scheduled_price_update: asyncio.Task | None = None

    async def _async_initialize(self) -> None:
        """Load stored data."""
        stored = await self._store.async_load()
        if stored:
            self._cached_price_data = stored.get("price_data")
            self._cached_rating_data = stored.get("rating_data")
            if last_price := stored.get("last_price_update"):
                self._last_price_update = dt_util.parse_datetime(last_price)
            if last_rating := stored.get("last_rating_update"):
                self._last_rating_update = dt_util.parse_datetime(last_rating)
            LOGGER.debug(
                "Loaded stored cache data - Price from: %s, Rating from: %s",
                self._last_price_update,
                self._last_rating_update,
            )

    async def _async_update_data(self) -> Any:
        """Update data via library."""
        if self._cached_price_data is None:
            # First run after startup, load stored data
            await self._async_initialize()

        try:
            data = await self._update_all_data()
        except TibberPricesApiClientAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except TibberPricesApiClientError as exception:
            raise UpdateFailed(exception) from exception
        else:
            return data

    async def _update_all_data(self) -> dict[str, Any]:
        """Update all data and manage cache."""
        current_time = dt_util.now()
        processed_data: dict[str, Any] | None = None
        is_initial_setup = self._cached_price_data is None

        # Handle price data update if needed
        if self._should_update_price_data(current_time):
            # Check if we're within the allowed time window for price updates
            # or if this is initial setup
            current_hour = current_time.hour
            if is_initial_setup or self._is_price_update_window(current_hour):
                # Add random delay only for regular updates, not initial setup
                if not is_initial_setup:
                    delay = random.randint(0, 120)  # noqa: S311
                    LOGGER.debug(
                        "Adding random delay of %d minutes before price update",
                        delay,
                    )
                    await asyncio.sleep(delay * 60)

                # Get fresh price data
                data = await self._fetch_price_data()
                self._cached_price_data = self._extract_price_data(data)
                self._last_price_update = current_time
                await self._store_cache()
                LOGGER.debug("Updated price data cache at %s", current_time)
                processed_data = data

        # Handle rating data update if needed
        if self._should_update_rating_data(current_time):
            rating_data = await self._get_rating_data()
            self._cached_rating_data = self._extract_rating_data(rating_data)
            self._last_rating_update = current_time
            await self._store_cache()
            LOGGER.debug("Updated rating data cache at %s", current_time)
            processed_data = rating_data

        # If we have cached data but no updates were needed
        if (
            processed_data is None
            and self._cached_price_data
            and self._cached_rating_data
        ):
            LOGGER.debug(
                "Using cached data - Price from: %s, Rating from: %s",
                self._last_price_update,
                self._last_rating_update,
            )
            processed_data = self._merge_cached_data()

        if processed_data is None:
            _raise_no_data()

        return cast("dict[str, Any]", processed_data)

    async def _store_cache(self) -> None:
        """Store cache data."""
        last_price = (
            self._last_price_update.isoformat() if self._last_price_update else None
        )
        last_rating = (
            self._last_rating_update.isoformat() if self._last_rating_update else None
        )
        data = {
            "price_data": self._cached_price_data,
            "rating_data": self._cached_rating_data,
            "last_price_update": last_price,
            "last_rating_update": last_rating,
        }
        await self._store.async_save(data)

    def _should_update_price_data(self, current_time: datetime) -> bool:
        """Check if price data should be updated."""
        return (
            self._cached_price_data is None
            or self._last_price_update is None
            or current_time - self._last_price_update >= PRICE_UPDATE_INTERVAL
        )

    def _should_update_rating_data(self, current_time: datetime) -> bool:
        """Check if rating data should be updated."""
        return (
            self._cached_rating_data is None
            or self._last_rating_update is None
            or current_time - self._last_rating_update >= RATING_UPDATE_INTERVAL
        )

    def _is_price_update_window(self, current_hour: int) -> bool:
        """Check if current hour is within price update window."""
        return (
            PRICE_UPDATE_RANDOM_MIN_HOUR <= current_hour <= PRICE_UPDATE_RANDOM_MAX_HOUR
        )

    async def _fetch_price_data(self) -> dict:
        """Fetch fresh price data from API."""
        client = self._entry.runtime_data.client
        return await client.async_get_price_info()

    def _extract_price_data(self, data: dict) -> dict:
        """Extract price data for caching."""
        price_info = data["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]
        return {
            "data": {
                "viewer": {
                    "homes": [{"currentSubscription": {"priceInfo": price_info}}]
                }
            }
        }

    def _extract_rating_data(self, data: dict) -> dict:
        """Extract rating data for caching."""
        return {
            "data": {
                "viewer": {
                    "homes": [
                        {
                            "currentSubscription": {
                                "priceRating": data["data"]["viewer"]["homes"][0][
                                    "currentSubscription"
                                ]["priceRating"]
                            }
                        }
                    ]
                }
            }
        }

    def _merge_cached_data(self) -> dict:
        """Merge cached price and rating data."""
        if not self._cached_price_data or not self._cached_rating_data:
            return {}

        subscription = {
            "priceInfo": self._cached_price_data["data"]["viewer"]["homes"][0][
                "currentSubscription"
            ]["priceInfo"],
            "priceRating": self._cached_rating_data["data"]["viewer"]["homes"][0][
                "currentSubscription"
            ]["priceRating"],
        }

        return {"data": {"viewer": {"homes": [{"currentSubscription": subscription}]}}}

    async def _get_rating_data(self) -> dict:
        """Get fresh rating data from API."""
        client = self._entry.runtime_data.client
        daily = await client.async_get_daily_price_rating()
        hourly = await client.async_get_hourly_price_rating()
        monthly = await client.async_get_monthly_price_rating()

        rating_base = daily["viewer"]["homes"][0]["currentSubscription"]["priceRating"]

        return {
            "data": {
                "viewer": {
                    "homes": [
                        {
                            "currentSubscription": {
                                "priceRating": {
                                    "thresholdPercentages": rating_base[
                                        "thresholdPercentages"
                                    ],
                                    "daily": rating_base["daily"],
                                    "hourly": hourly["viewer"]["homes"][0][
                                        "currentSubscription"
                                    ]["priceRating"]["hourly"],
                                    "monthly": monthly["viewer"]["homes"][0][
                                        "currentSubscription"
                                    ]["priceRating"]["monthly"],
                                }
                            }
                        }
                    ]
                }
            }
        }
