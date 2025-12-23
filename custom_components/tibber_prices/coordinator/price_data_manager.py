"""
Price data management for the coordinator.

This module manages all price-related data for the Tibber Prices integration:

**User Data** (fetched directly via API):
- Home metadata (name, address, timezone)
- Account info (subscription status)
- Currency settings
- Refreshed daily (24h interval)

**Price Data** (fetched via IntervalPool):
- Quarter-hourly price intervals
- Yesterday/today/tomorrow coverage
- The IntervalPool handles actual API fetching, deduplication, and caching
- This manager coordinates the data flow and user data refresh

Data flow:
    Tibber API → IntervalPool → PriceDataManager → Coordinator → Sensors
                     ↑                  ↓
              (actual fetching)   (orchestration + user data)

Note: Price data is NOT cached in this module - IntervalPool is the single
source of truth. This module only caches user_data for daily refresh cycle.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from custom_components.tibber_prices.api import (
    TibberPricesApiClientAuthenticationError,
    TibberPricesApiClientCommunicationError,
    TibberPricesApiClientError,
)
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import cache, helpers

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from custom_components.tibber_prices.api import TibberPricesApiClient
    from custom_components.tibber_prices.interval_pool import TibberPricesIntervalPool

    from .time_service import TibberPricesTimeService

_LOGGER = logging.getLogger(__name__)

# Hour when Tibber publishes tomorrow's prices (around 13:00 local time)
# Before this hour, requesting tomorrow data will always fail → wasted API call
TOMORROW_DATA_AVAILABLE_HOUR = 13


class TibberPricesPriceDataManager:
    """
    Manages price and user data for the coordinator.

    Responsibilities:
    - User data: Fetches directly via API, validates, caches with persistence
    - Price data: Coordinates with IntervalPool (which does actual API fetching)
    - Cache management: Loads/stores both data types to HA persistent storage
    - Update decisions: Determines when fresh data is needed

    Note: Despite the name, this class does NOT do the actual price fetching.
    The IntervalPool handles API calls, deduplication, and interval management.
    This class orchestrates WHEN to fetch and processes the results.
    """

    def __init__(  # noqa: PLR0913
        self,
        api: TibberPricesApiClient,
        store: Any,
        log_prefix: str,
        user_update_interval: timedelta,
        time: TibberPricesTimeService,
        home_id: str,
        interval_pool: TibberPricesIntervalPool,
    ) -> None:
        """
        Initialize the price data manager.

        Args:
            api: API client for direct requests (user data only).
            store: Home Assistant storage for persistence.
            log_prefix: Prefix for log messages (e.g., "[Home Name]").
            user_update_interval: How often to refresh user data (default: 1 day).
            time: TimeService for time operations.
            home_id: Home ID this manager is responsible for.
            interval_pool: IntervalPool for price data (handles actual fetching).

        """
        self.api = api
        self._store = store
        self._log_prefix = log_prefix
        self._user_update_interval = user_update_interval
        self.time: TibberPricesTimeService = time
        self.home_id = home_id
        self._interval_pool = interval_pool

        # Cached data (user data only - price data is in IntervalPool)
        self._cached_user_data: dict[str, Any] | None = None
        self._last_user_update: datetime | None = None

    def _log(self, level: str, message: str, *args: object, **kwargs: object) -> None:
        """Log with coordinator-specific prefix."""
        prefixed_message = f"{self._log_prefix} {message}"
        getattr(_LOGGER, level)(prefixed_message, *args, **kwargs)

    async def load_cache(self) -> None:
        """Load cached user data from storage (price data is in IntervalPool)."""
        cache_data = await cache.load_cache(self._store, self._log_prefix, time=self.time)

        self._cached_user_data = cache_data.user_data
        self._last_user_update = cache_data.last_user_update

    def should_fetch_tomorrow_data(
        self,
        current_price_info: list[dict[str, Any]] | None,
    ) -> bool:
        """
        Determine if tomorrow's data should be requested from the API.

        This is the key intelligence that prevents API spam:
        - Tibber publishes tomorrow's prices around 13:00 each day
        - Before 13:00, requesting tomorrow data will always fail → wasted API call
        - If we already have tomorrow data, no need to request it again

        The decision logic:
        1. Before 13:00 local time → Don't fetch (data not available yet)
        2. After 13:00 AND tomorrow data already present → Don't fetch (already have it)
        3. After 13:00 AND tomorrow data missing → Fetch (data should be available)

        Args:
            current_price_info: List of price intervals from current coordinator data.
                               Used to check if tomorrow data already exists.

        Returns:
            True if tomorrow data should be requested, False otherwise.

        """
        now = self.time.now()
        now_local = self.time.as_local(now)
        current_hour = now_local.hour

        # Before TOMORROW_DATA_AVAILABLE_HOUR - tomorrow data not available yet
        if current_hour < TOMORROW_DATA_AVAILABLE_HOUR:
            self._log("debug", "Before %d:00 - not requesting tomorrow data", TOMORROW_DATA_AVAILABLE_HOUR)
            return False

        # After TOMORROW_DATA_AVAILABLE_HOUR - check if we already have tomorrow data
        if current_price_info:
            has_tomorrow = self.has_tomorrow_data(current_price_info)
            if has_tomorrow:
                self._log(
                    "debug", "After %d:00 but already have tomorrow data - not requesting", TOMORROW_DATA_AVAILABLE_HOUR
                )
                return False
            self._log("debug", "After %d:00 and tomorrow data missing - will request", TOMORROW_DATA_AVAILABLE_HOUR)
            return True

        # No current data - request tomorrow data if after TOMORROW_DATA_AVAILABLE_HOUR
        self._log(
            "debug", "After %d:00 with no current data - will request tomorrow data", TOMORROW_DATA_AVAILABLE_HOUR
        )
        return True

    async def store_cache(self, last_midnight_check: datetime | None = None) -> None:
        """Store cache data (user metadata only, price data is in IntervalPool)."""
        cache_data = cache.TibberPricesCacheData(
            user_data=self._cached_user_data,
            last_user_update=self._last_user_update,
            last_midnight_check=last_midnight_check,
        )
        await cache.save_cache(self._store, cache_data, self._log_prefix)

    def _validate_user_data(self, user_data: dict, home_id: str) -> bool:  # noqa: PLR0911
        """
        Validate user data completeness.

        Rejects incomplete/invalid data from API to prevent caching temporary errors.
        Currency information is critical - if missing, we cannot safely calculate prices.

        Args:
            user_data: User data dict from API.
            home_id: Home ID to validate against.

        Returns:
            True if data is valid and complete, False otherwise.

        """
        if not user_data:
            self._log("warning", "User data validation failed: Empty data")
            return False

        viewer = user_data.get("viewer")
        if not viewer or not isinstance(viewer, dict):
            self._log("warning", "User data validation failed: Missing or invalid viewer")
            return False

        homes = viewer.get("homes")
        if not homes or not isinstance(homes, list) or len(homes) == 0:
            self._log("warning", "User data validation failed: No homes found")
            return False

        # Find our home and validate it has required data
        home_found = False
        for home in homes:
            if home.get("id") == home_id:
                home_found = True

                # Validate home has timezone (required for cursor calculation)
                if not home.get("timeZone"):
                    self._log("warning", "User data validation failed: Home %s missing timezone", home_id)
                    return False

                # Currency is critical - if home has subscription, must have currency
                subscription = home.get("currentSubscription")
                if subscription and subscription is not None:
                    price_info = subscription.get("priceInfo")
                    if price_info and price_info is not None:
                        current = price_info.get("current")
                        if current and current is not None:
                            currency = current.get("currency")
                            if not currency:
                                self._log(
                                    "warning",
                                    "User data validation failed: Home %s has subscription but no currency",
                                    home_id,
                                )
                                return False

                break

        if not home_found:
            self._log("warning", "User data validation failed: Home %s not found in homes list", home_id)
            return False

        self._log("debug", "User data validation passed for home %s", home_id)
        return True

    async def update_user_data_if_needed(self, current_time: datetime) -> bool:
        """
        Update user data if needed (daily check).

        Only accepts complete and valid data. If API returns incomplete data
        (e.g., during maintenance), keeps existing cached data and retries later.

        Returns:
            True if user data was updated, False otherwise

        """
        if self._last_user_update is None or current_time - self._last_user_update >= self._user_update_interval:
            try:
                self._log("debug", "Updating user data")
                user_data = await self.api.async_get_viewer_details()

                # Validate before caching
                if not self._validate_user_data(user_data, self.home_id):
                    self._log(
                        "warning",
                        "Rejecting incomplete user data from API - keeping existing cached data",
                    )
                    return False  # Keep existing data, don't update timestamp

                # Data is valid, cache it
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

    async def fetch_home_data(
        self,
        home_id: str,
        current_time: datetime,
        *,
        include_tomorrow: bool = True,
    ) -> dict[str, Any]:
        """
        Fetch data for a single home via pool.

        Args:
            home_id: Home ID to fetch data for.
            current_time: Current time for timestamp in result.
            include_tomorrow: If True, request tomorrow's data too. If False,
                             only request up to end of today.

        """
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

                # Validate data before accepting it (especially on initial setup)
                if not self._validate_user_data(user_data, self.home_id):
                    msg = "Received incomplete user data from API - cannot proceed with price fetching"
                    self._log("error", msg)
                    raise TibberPricesApiClientError(msg)  # noqa: TRY301

                self._cached_user_data = user_data
                self._last_user_update = current_time
            except (
                TibberPricesApiClientError,
                TibberPricesApiClientCommunicationError,
            ) as ex:
                msg = f"Failed to fetch user data (required for price fetching): {ex}"
                self._log("error", msg)
                raise TibberPricesApiClientError(msg) from ex

        # At this point, _cached_user_data is guaranteed to be not None (checked above)
        if not self._cached_user_data:
            msg = "User data unexpectedly None after fetch attempt"
            raise TibberPricesApiClientError(msg)

        # Retrieve price data via IntervalPool (single source of truth)
        price_info = await self._fetch_via_pool(home_id, include_tomorrow=include_tomorrow)

        # Extract currency for this home from user_data
        currency = self._get_currency_for_home(home_id)

        self._log("debug", "Successfully fetched data for home %s (%d intervals)", home_id, len(price_info))

        return {
            "timestamp": current_time,
            "home_id": home_id,
            "price_info": price_info,
            "currency": currency,
        }

    async def _fetch_via_pool(
        self,
        home_id: str,
        *,
        include_tomorrow: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Retrieve price data via IntervalPool.

        The IntervalPool is the single source of truth for price data:
        - Handles actual API calls to Tibber
        - Manages deduplication and caching
        - Provides intervals from day-before-yesterday to end-of-today/tomorrow

        This method delegates to the Pool's get_sensor_data() which returns
        all relevant intervals for sensor display.

        Args:
            home_id: Home ID (currently unused, Pool knows its home).
            include_tomorrow: If True, request tomorrow's data too. If False,
                             only request up to end of today. This prevents
                             API spam before 13:00 when Tibber doesn't have
                             tomorrow data yet.

        Returns:
            List of price interval dicts.

        """
        # user_data is guaranteed by fetch_home_data(), but needed for type narrowing
        if self._cached_user_data is None:
            return []

        self._log(
            "debug",
            "Retrieving price data for home %s via interval pool (include_tomorrow=%s)",
            home_id,
            include_tomorrow,
        )
        return await self._interval_pool.get_sensor_data(
            api_client=self.api,
            user_data=self._cached_user_data,
            include_tomorrow=include_tomorrow,
        )

    def _get_currency_for_home(self, home_id: str) -> str:
        """
        Get currency for a specific home from cached user_data.

        Returns:
            Currency code (e.g., "EUR", "NOK", "SEK").

        Raises:
            TibberPricesApiClientError: If currency cannot be determined.

        """
        if not self._cached_user_data:
            msg = "No user data cached - cannot determine currency"
            self._log("error", msg)
            raise TibberPricesApiClientError(msg)

        viewer = self._cached_user_data.get("viewer", {})
        homes = viewer.get("homes", [])

        for home in homes:
            if home.get("id") == home_id:
                # Extract currency from nested structure
                # Use 'or {}' to handle None values (homes without active subscription)
                subscription = home.get("currentSubscription") or {}
                price_info = subscription.get("priceInfo") or {}
                current = price_info.get("current") or {}
                currency = current.get("currency")

                if not currency:
                    # Home without active subscription - cannot determine currency
                    msg = f"Home {home_id} has no active subscription - currency unavailable"
                    self._log("error", msg)
                    raise TibberPricesApiClientError(msg)

                self._log("debug", "Extracted currency %s for home %s", currency, home_id)
                return currency

        # Home not found in cached data - data validation should have caught this
        msg = f"Home {home_id} not found in user data - data validation failed"
        self._log("error", msg)
        raise TibberPricesApiClientError(msg)

    def _check_home_exists(self, home_id: str) -> bool:
        """
        Check if a home ID exists in cached user data.

        Args:
            home_id: The home ID to check.

        Returns:
            True if home exists, False otherwise.

        """
        if not self._cached_user_data:
            # No user data yet - assume home exists (will be checked on next update)
            return True

        viewer = self._cached_user_data.get("viewer", {})
        homes = viewer.get("homes", [])

        return any(home.get("id") == home_id for home in homes)

    async def handle_main_entry_update(
        self,
        current_time: datetime,
        home_id: str,
        transform_fn: Callable[[dict[str, Any]], dict[str, Any]],
        *,
        current_price_info: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Handle update for main entry - fetch data for this home.

        The IntervalPool is the single source of truth for price data:
        - It handles API fetching, deduplication, and caching internally
        - We decide WHEN to fetch tomorrow data (after 13:00, if not already present)
        - This prevents API spam before 13:00 when Tibber doesn't have tomorrow data

        This method:
        1. Updates user data if needed (daily)
        2. Determines if tomorrow data should be requested
        3. Fetches price data via IntervalPool
        4. Transforms result for coordinator

        Args:
            current_time: Current time for update decisions.
            home_id: Home ID to fetch data for.
            transform_fn: Function to transform raw data for coordinator.
            current_price_info: Current price intervals (from coordinator.data["priceInfo"]).
                               Used to check if tomorrow data already exists.

        """
        # Update user data if needed (daily check)
        user_data_updated = await self.update_user_data_if_needed(current_time)

        # Check if this home still exists in user data after update
        # This detects when a home was removed from the Tibber account
        home_exists = self._check_home_exists(home_id)
        if not home_exists:
            self._log("warning", "Home ID %s not found in Tibber account", home_id)
            # Return a special marker in the result that coordinator can check
            result = transform_fn({})
            result["_home_not_found"] = True  # Special marker for coordinator
            return result

        # Determine if we should request tomorrow data
        include_tomorrow = self.should_fetch_tomorrow_data(current_price_info)

        # Fetch price data via IntervalPool
        self._log(
            "debug",
            "Fetching price data for home %s via interval pool (include_tomorrow=%s)",
            home_id,
            include_tomorrow,
        )
        raw_data = await self.fetch_home_data(home_id, current_time, include_tomorrow=include_tomorrow)

        # Parse timestamps immediately after fetch
        raw_data = helpers.parse_all_timestamps(raw_data, time=self.time)

        # Store user data cache (price data persisted by IntervalPool)
        if user_data_updated:
            await self.store_cache()

        # Transform for main entry
        return transform_fn(raw_data)

    async def handle_api_error(
        self,
        error: Exception,
    ) -> None:
        """
        Handle API errors - re-raise appropriate exceptions.

        Note: With IntervalPool as source of truth, there's no local price cache
        to fall back to. The Pool has its own persistence, so on next update
        it will use its cached intervals if API is unavailable.
        """
        if isinstance(error, TibberPricesApiClientAuthenticationError):
            msg = "Invalid access token"
            raise ConfigEntryAuthFailed(msg) from error

        msg = f"Error communicating with API: {error}"
        raise UpdateFailed(msg) from error

    @property
    def cached_user_data(self) -> dict[str, Any] | None:
        """Get cached user data."""
        return self._cached_user_data

    def has_tomorrow_data(self, price_info: list[dict[str, Any]]) -> bool:
        """
        Check if tomorrow's price data is available.

        Args:
            price_info: List of price intervals from coordinator data.

        Returns:
            True if at least one interval from tomorrow is present.

        """
        if not price_info:
            return False

        # Get tomorrow's date
        now = self.time.now()
        tomorrow = (self.time.as_local(now) + timedelta(days=1)).date()

        # Check if any interval is from tomorrow
        for interval in price_info:
            if "startsAt" not in interval:
                continue

            # startsAt is already a datetime object after _transform_data()
            interval_time = interval["startsAt"]
            if isinstance(interval_time, str):
                # Fallback: parse if still string (shouldn't happen with transformed data)
                interval_time = self.time.parse_datetime(interval_time)

            if interval_time and self.time.as_local(interval_time).date() == tomorrow:
                return True

        return False
