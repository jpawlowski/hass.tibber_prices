"""Data fetching logic for the coordinator."""

from __future__ import annotations

import asyncio
import logging
import secrets
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from custom_components.tibber_prices.api import (
    TibberPricesApiClientAuthenticationError,
    TibberPricesApiClientCommunicationError,
    TibberPricesApiClientError,
)
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from . import cache, helpers
from .constants import TOMORROW_DATA_CHECK_HOUR, TOMORROW_DATA_RANDOM_DELAY_MAX

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import date, datetime

    from custom_components.tibber_prices.api import TibberPricesApiClient

_LOGGER = logging.getLogger(__name__)


class DataFetcher:
    """Handles data fetching, caching, and main/subentry coordination."""

    def __init__(
        self,
        api: TibberPricesApiClient,
        store: Any,
        log_prefix: str,
        user_update_interval: timedelta,
    ) -> None:
        """Initialize the data fetcher."""
        self.api = api
        self._store = store
        self._log_prefix = log_prefix
        self._user_update_interval = user_update_interval

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
        cache_data = await cache.load_cache(self._store, self._log_prefix)

        self._cached_price_data = cache_data.price_data
        self._cached_user_data = cache_data.user_data
        self._last_price_update = cache_data.last_price_update
        self._last_user_update = cache_data.last_user_update

        # Validate cache: check if price data is from a previous day
        if not cache.is_cache_valid(cache_data, self._log_prefix):
            self._log("info", "Cached price data is from a previous day, clearing cache to fetch fresh data")
            self._cached_price_data = None
            self._last_price_update = None
            await self.store_cache()

    async def store_cache(self, last_midnight_check: datetime | None = None) -> None:
        """Store cache data."""
        cache_data = cache.CacheData(
            price_data=self._cached_price_data,
            user_data=self._cached_user_data,
            last_price_update=self._last_price_update,
            last_user_update=self._last_user_update,
            last_midnight_check=last_midnight_check,
        )
        await cache.store_cache(self._store, cache_data, self._log_prefix)

    async def update_user_data_if_needed(self, current_time: datetime) -> None:
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

        now_local = dt_util.as_local(current_time)
        tomorrow_date = (now_local + timedelta(days=1)).date()

        # Check if after 13:00 and tomorrow data is missing or invalid
        if (
            now_local.hour >= TOMORROW_DATA_CHECK_HOUR
            and self._cached_price_data
            and "homes" in self._cached_price_data
            and self.needs_tomorrow_data(tomorrow_date)
        ):
            self._log(
                "debug",
                "API update needed: After %s:00 and tomorrow's data missing/invalid",
                TOMORROW_DATA_CHECK_HOUR,
            )
            # Return special marker to indicate this is a tomorrow data check
            # Caller should add random delay to spread load
            return "tomorrow_check"

        # No update needed - cache is valid and complete
        return False

    def needs_tomorrow_data(self, tomorrow_date: date) -> bool:
        """Check if tomorrow data is missing or invalid."""
        return helpers.needs_tomorrow_data(self._cached_price_data, tomorrow_date)

    async def fetch_all_homes_data(self, configured_home_ids: set[str]) -> dict[str, Any]:
        """Fetch data for all homes (main coordinator only)."""
        if not configured_home_ids:
            self._log("warning", "No configured homes found - cannot fetch price data")
            return {
                "timestamp": dt_util.utcnow(),
                "homes": {},
            }

        # Get price data for configured homes only (API call with specific home_ids)
        self._log("debug", "Fetching price data for %d configured home(s)", len(configured_home_ids))
        price_data = await self.api.async_get_price_info(home_ids=configured_home_ids)

        all_homes_data = {}
        homes_list = price_data.get("homes", {})

        # Process returned data
        for home_id, home_price_data in homes_list.items():
            # Store raw price data without enrichment
            # Enrichment will be done dynamically when data is transformed
            home_data = {
                "price_info": home_price_data,
            }
            all_homes_data[home_id] = home_data

        self._log(
            "debug",
            "Successfully fetched data for %d home(s)",
            len(all_homes_data),
        )

        return {
            "timestamp": dt_util.utcnow(),
            "homes": all_homes_data,
        }

    async def handle_main_entry_update(
        self,
        current_time: datetime,
        configured_home_ids: set[str],
        transform_fn: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> dict[str, Any]:
        """Handle update for main entry - fetch data for all homes."""
        # Update user data if needed (daily check)
        await self.update_user_data_if_needed(current_time)

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
            raw_data = await self.fetch_all_homes_data(configured_home_ids)
            # Cache the data
            self._cached_price_data = raw_data
            self._last_price_update = current_time
            await self.store_cache()
            # Transform for main entry: provide aggregated view
            return transform_fn(raw_data)

        # Use cached data if available
        if self._cached_price_data is not None:
            self._log("debug", "Using cached price data (no API call needed)")
            return transform_fn(self._cached_price_data)

        # Fallback: no cache and no update needed (shouldn't happen)
        self._log("warning", "No cached data available and update not triggered - returning empty data")
        return {
            "timestamp": current_time,
            "homes": {},
            "priceInfo": {},
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

    def perform_midnight_turnover(self, price_info: dict[str, Any]) -> dict[str, Any]:
        """
        Perform midnight turnover on price data.

        Moves: today → yesterday, tomorrow → today, clears tomorrow.

        Args:
            price_info: The price info dict with 'today', 'tomorrow', 'yesterday' keys

        Returns:
            Updated price_info with rotated day data

        """
        return helpers.perform_midnight_turnover(price_info)

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
