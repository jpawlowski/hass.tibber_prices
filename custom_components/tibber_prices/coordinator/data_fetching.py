"""Data fetching logic for the coordinator."""

from __future__ import annotations

import asyncio
import logging
import secrets
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import timedelta

from custom_components.tibber_prices.api import (
    TibberPricesApiClientAuthenticationError,
    TibberPricesApiClientCommunicationError,
    TibberPricesApiClientError,
)
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import cache, helpers
from .constants import TOMORROW_DATA_CHECK_HOUR, TOMORROW_DATA_RANDOM_DELAY_MAX

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from custom_components.tibber_prices.api import TibberPricesApiClient

    from .time_service import TibberPricesTimeService

_LOGGER = logging.getLogger(__name__)


class TibberPricesDataFetcher:
    """Handles data fetching, caching, and main/subentry coordination."""

    def __init__(
        self,
        api: TibberPricesApiClient,
        store: Any,
        log_prefix: str,
        user_update_interval: timedelta,
        time: TibberPricesTimeService,
    ) -> None:
        """Initialize the data fetcher."""
        self.api = api
        self._store = store
        self._log_prefix = log_prefix
        self._user_update_interval = user_update_interval
        self.time: TibberPricesTimeService = time

        # Cached data
        self._cached_price_data: dict[str, Any] | None = None
        self._cached_user_data: dict[str, Any] | None = None
        self._last_price_update: datetime | None = None
        self._last_user_update: datetime | None = None

    def _log(self, level: str, message: str, *args: object, **kwargs: object) -> None:
        """Log with coordinator-specific prefix."""
        prefixed_message = f"{self._log_prefix} {message}"
        getattr(_LOGGER, level)(prefixed_message, *args, **kwargs)

    async def load_cache(self) -> None:
        """Load cached data from storage."""
        cache_data = await cache.load_cache(self._store, self._log_prefix, time=self.time)

        self._cached_price_data = cache_data.price_data
        self._cached_user_data = cache_data.user_data
        self._last_price_update = cache_data.last_price_update
        self._last_user_update = cache_data.last_user_update

        # Parse timestamps if we loaded price data from cache
        if self._cached_price_data:
            self._cached_price_data = helpers.parse_all_timestamps(self._cached_price_data, time=self.time)

        # Validate cache: check if price data is from a previous day
        if not cache.is_cache_valid(cache_data, self._log_prefix, time=self.time):
            self._log("info", "Cached price data is from a previous day, clearing cache to fetch fresh data")
            self._cached_price_data = None
            self._last_price_update = None
            await self.store_cache()

    async def store_cache(self, last_midnight_check: datetime | None = None) -> None:
        """Store cache data."""
        cache_data = cache.TibberPricesCacheData(
            price_data=self._cached_price_data,
            user_data=self._cached_user_data,
            last_price_update=self._last_price_update,
            last_user_update=self._last_user_update,
            last_midnight_check=last_midnight_check,
        )
        await cache.save_cache(self._store, cache_data, self._log_prefix)

    async def update_user_data_if_needed(self, current_time: datetime) -> bool:
        """
        Update user data if needed (daily check).

        Returns:
            True if user data was updated, False otherwise

        """
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
                return False  # Update failed
            else:
                return True  # User data was updated
        return False  # No update needed

    @callback
    def should_update_price_data(self, current_time: datetime) -> bool | str:
        """
        Check if price data should be updated from the API.

        API calls only happen when truly needed:
        1. No cached data exists
        2. Cache is invalid (from previous day - detected by _is_cache_valid)
        3. After 13:00 local time and tomorrow's data is missing or invalid

        Cache validity is ensured by:
        - _is_cache_valid() checks date mismatch on load
        - Midnight turnover clears cache (Timer #2)
        - Tomorrow data validation after 13:00

        No periodic "safety" updates - trust the cache validation!

        Returns:
            bool or str: True for immediate update, "tomorrow_check" for tomorrow
                        data check (needs random delay), False for no update

        """
        if self._cached_price_data is None:
            self._log("debug", "API update needed: No cached price data")
            return True
        if self._last_price_update is None:
            self._log("debug", "API update needed: No last price update timestamp")
            return True

        # Check if after 13:00 and tomorrow data is missing or invalid
        now_local = self.time.as_local(current_time)
        if now_local.hour >= TOMORROW_DATA_CHECK_HOUR and self._cached_price_data and self.needs_tomorrow_data():
            self._log(
                "info",
                "API update needed: After %s:00 and tomorrow's data missing/invalid",
                TOMORROW_DATA_CHECK_HOUR,
            )
            # Return special marker to indicate this is a tomorrow data check
            # Caller should add random delay to spread load
            return "tomorrow_check"

        # No update needed - cache is valid and complete
        self._log("debug", "No API update needed: Cache is valid and complete")
        return False

    def needs_tomorrow_data(self) -> bool:
        """Check if tomorrow data is missing or invalid."""
        return helpers.needs_tomorrow_data(self._cached_price_data)

    async def fetch_home_data(self, home_id: str, current_time: datetime) -> dict[str, Any]:
        """Fetch data for a single home."""
        if not home_id:
            self._log("warning", "No home ID provided - cannot fetch price data")
            return {
                "timestamp": current_time,
                "home_id": "",
                "price_info": [],
                "currency": "EUR",
            }

        # Ensure we have user_data before fetching price data
        # This is critical for timezone-aware cursor calculation
        if not self._cached_user_data:
            self._log("info", "User data not cached, fetching before price data")
            try:
                user_data = await self.api.async_get_viewer_details()
                self._cached_user_data = user_data
                self._last_user_update = current_time
            except (
                TibberPricesApiClientError,
                TibberPricesApiClientCommunicationError,
            ) as ex:
                msg = f"Failed to fetch user data (required for price fetching): {ex}"
                self._log("error", msg)
                raise TibberPricesApiClientError(msg) from ex

        # Get price data for this home
        # Pass user_data for timezone-aware cursor calculation
        # At this point, _cached_user_data is guaranteed to be not None (checked above)
        if not self._cached_user_data:
            msg = "User data unexpectedly None after fetch attempt"
            raise TibberPricesApiClientError(msg)

        self._log("debug", "Fetching price data for home %s", home_id)
        home_data = await self.api.async_get_price_info(
            home_id=home_id,
            user_data=self._cached_user_data,
        )

        # Extract currency for this home from user_data
        currency = self._get_currency_for_home(home_id)

        price_info = home_data.get("price_info", [])

        self._log("debug", "Successfully fetched data for home %s (%d intervals)", home_id, len(price_info))

        return {
            "timestamp": current_time,
            "home_id": home_id,
            "price_info": price_info,
            "currency": currency,
        }

    def _get_currency_for_home(self, home_id: str) -> str:
        """Get currency for a specific home from cached user_data."""
        if not self._cached_user_data:
            self._log("warning", "No user data cached, using EUR as default currency")
            return "EUR"

        viewer = self._cached_user_data.get("viewer", {})
        homes = viewer.get("homes", [])

        for home in homes:
            if home.get("id") == home_id:
                # Extract currency from nested structure (with fallback to EUR)
                currency = (
                    home.get("currentSubscription", {}).get("priceInfo", {}).get("current", {}).get("currency", "EUR")
                )
                self._log("debug", "Extracted currency %s for home %s", currency, home_id)
                return currency

        self._log("warning", "Home %s not found in user data, using EUR as default", home_id)
        return "EUR"

    async def handle_main_entry_update(
        self,
        current_time: datetime,
        home_id: str,
        transform_fn: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> dict[str, Any]:
        """Handle update for main entry - fetch data for this home."""
        # Update user data if needed (daily check)
        user_data_updated = await self.update_user_data_if_needed(current_time)

        # Check if we need to update price data
        should_update = self.should_update_price_data(current_time)

        if should_update:
            # If this is a tomorrow data check, add random delay to spread API load
            if should_update == "tomorrow_check":
                # Use secrets for better randomness distribution
                delay = secrets.randbelow(TOMORROW_DATA_RANDOM_DELAY_MAX + 1)
                self._log(
                    "debug",
                    "Tomorrow data check - adding random delay of %d seconds to spread load",
                    delay,
                )
                await asyncio.sleep(delay)

            self._log("debug", "Fetching fresh price data from API")
            raw_data = await self.fetch_home_data(home_id, current_time)
            # Parse timestamps immediately after API fetch
            raw_data = helpers.parse_all_timestamps(raw_data, time=self.time)
            # Cache the data (now with datetime objects)
            self._cached_price_data = raw_data
            self._last_price_update = current_time
            await self.store_cache()
            # Transform for main entry
            return transform_fn(raw_data)

        # Use cached data if available
        if self._cached_price_data is not None:
            # If user data was updated, we need to return transformed data to trigger entity updates
            # This ensures diagnostic sensors (home_type, grid_company, etc.) get refreshed
            if user_data_updated:
                self._log("debug", "User data updated - returning transformed data to update diagnostic sensors")
            else:
                self._log("debug", "Using cached price data (no API call needed)")
            return transform_fn(self._cached_price_data)

        # Fallback: no cache and no update needed (shouldn't happen)
        self._log("warning", "No cached data available and update not triggered - returning empty data")
        return {
            "timestamp": current_time,
            "home_id": home_id,
            "priceInfo": [],
            "currency": "",
        }

    async def handle_api_error(
        self,
        error: Exception,
        transform_fn: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> dict[str, Any]:
        """Handle API errors with fallback to cached data."""
        if isinstance(error, TibberPricesApiClientAuthenticationError):
            msg = "Invalid access token"
            raise ConfigEntryAuthFailed(msg) from error

        # Use cached data as fallback if available
        if self._cached_price_data is not None:
            self._log("warning", "API error, using cached data: %s", error)
            return transform_fn(self._cached_price_data)

        msg = f"Error communicating with API: {error}"
        raise UpdateFailed(msg) from error

    @property
    def cached_price_data(self) -> dict[str, Any] | None:
        """Get cached price data."""
        return self._cached_price_data

    @cached_price_data.setter
    def cached_price_data(self, value: dict[str, Any] | None) -> None:
        """Set cached price data."""
        self._cached_price_data = value

    @property
    def cached_user_data(self) -> dict[str, Any] | None:
        """Get cached user data."""
        return self._cached_user_data
