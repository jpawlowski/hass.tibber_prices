"""Enhanced coordinator for fetching Tibber price data with comprehensive caching."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import aiohttp_client
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
    CONF_PRICE_RATING_THRESHOLD_HIGH,
    CONF_PRICE_RATING_THRESHOLD_LOW,
    DEFAULT_PRICE_RATING_THRESHOLD_HIGH,
    DEFAULT_PRICE_RATING_THRESHOLD_LOW,
    DOMAIN,
)
from .price_utils import enrich_price_info_with_differences, find_price_data_for_interval

_LOGGER = logging.getLogger(__name__)

# Storage version for storing data
STORAGE_VERSION = 1

# Update interval - fetch data every 15 minutes
UPDATE_INTERVAL = timedelta(minutes=15)

# Quarter-hour boundaries for entity state updates (minutes: 00, 15, 30, 45)
QUARTER_HOUR_BOUNDARIES = (0, 15, 30, 45)


class TibberPricesDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Enhanced coordinator with main/subentry pattern and comprehensive caching."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
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

        # Track if this is the main entry (first one created)
        self._is_main_entry = not self._has_existing_main_coordinator()

        # Quarter-hour entity refresh timer
        self._quarter_hour_timer_handle: Any = None
        self._schedule_quarter_hour_refresh()

    def _schedule_quarter_hour_refresh(self) -> None:
        """Schedule the next quarter-hour entity refresh."""
        now = dt_util.utcnow()
        current_minute = now.minute

        # Find the next quarter-hour boundary
        for boundary in QUARTER_HOUR_BOUNDARIES:
            if boundary > current_minute:
                minutes_to_wait = boundary - current_minute
                break
        else:
            # All boundaries passed, go to first boundary of next hour
            minutes_to_wait = (60 - current_minute) + QUARTER_HOUR_BOUNDARIES[0]

        # Calculate the exact time of the next boundary
        next_refresh = now + timedelta(minutes=minutes_to_wait)
        next_refresh = next_refresh.replace(second=0, microsecond=0)

        # Cancel any existing timer
        if self._quarter_hour_timer_handle:
            self._quarter_hour_timer_handle.cancel()

        # Schedule the refresh
        self._quarter_hour_timer_handle = self.hass.loop.call_at(
            self.hass.loop.time() + (next_refresh - now).total_seconds(),
            self._handle_quarter_hour_refresh,
        )

        _LOGGER.debug(
            "Scheduled entity refresh at %s (in %d minutes)",
            next_refresh.isoformat(),
            minutes_to_wait,
        )

    def _handle_quarter_hour_refresh(self) -> None:
        """Handle quarter-hour entity refresh by triggering async state updates."""
        _LOGGER.debug("Quarter-hour refresh triggered at %s", dt_util.utcnow().isoformat())

        # Notify all listeners that there's new data without fetching fresh data
        # This causes entity state properties to be re-evaluated with the current time
        self.async_set_updated_data(self.data)

        # Schedule the next quarter-hour refresh
        self._schedule_quarter_hour_refresh()

    async def async_shutdown(self) -> None:
        """Shut down the coordinator and clean up timers."""
        if self._quarter_hour_timer_handle:
            self._quarter_hour_timer_handle()
            self._quarter_hour_timer_handle = None

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
                _LOGGER.warning("API error, using cached data: %s", err)
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

        # Use cached data
        if self._cached_price_data is not None:
            return self._transform_data_for_main_entry(self._cached_price_data)

        # No cached data, fetch new
        raw_data = await self._fetch_all_homes_data()
        self._cached_price_data = raw_data
        self._last_price_update = current_time
        await self._store_cache()
        return self._transform_data_for_main_entry(raw_data)

    async def _handle_subentry_update(self) -> dict[str, Any]:
        """Handle update for subentry - get data from main coordinator."""
        main_data = await self._get_data_from_main_coordinator()
        return self._transform_data_for_subentry(main_data)

    async def _fetch_all_homes_data(self) -> dict[str, Any]:
        """Fetch data for all homes (main coordinator only)."""
        _LOGGER.debug("Fetching data for all homes")

        # Get price data for all homes
        price_data = await self.api.async_get_price_info()

        all_homes_data = {}
        homes_list = price_data.get("homes", {})

        for home_id, home_price_data in homes_list.items():
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

                # Validate cache: check if price data is from a previous day
                if not self._is_cache_valid():
                    _LOGGER.info("Cached price data is from a previous day, clearing cache to fetch fresh data")
                    self._cached_price_data = None
                    self._last_price_update = None
                    await self._store_cache()
                else:
                    _LOGGER.debug("Cache loaded successfully")
            else:
                _LOGGER.debug("No cache found, will fetch fresh data")
        except OSError as ex:
            _LOGGER.warning("Failed to load cache: %s", ex)

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
            _LOGGER.debug(
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
            _LOGGER.info("Performing midnight turnover: today→yesterday, tomorrow→today")
            return {
                "yesterday": today_prices,
                "today": tomorrow_prices,
                "tomorrow": [],
            }

        return price_info

    async def _store_cache(self) -> None:
        """Store cache data."""
        data = {
            "price_data": self._cached_price_data,
            "user_data": self._cached_user_data,
            "last_price_update": (self._last_price_update.isoformat() if self._last_price_update else None),
            "last_user_update": (self._last_user_update.isoformat() if self._last_user_update else None),
        }

        try:
            await self._store.async_save(data)
            _LOGGER.debug("Cache stored successfully")
        except OSError:
            _LOGGER.exception("Failed to store cache")

    async def _update_user_data_if_needed(self, current_time: datetime) -> None:
        """Update user data if needed (daily check)."""
        if self._last_user_update is None or current_time - self._last_user_update >= self._user_update_interval:
            try:
                _LOGGER.debug("Updating user data")
                user_data = await self.api.async_get_viewer_details()
                self._cached_user_data = user_data
                self._last_user_update = current_time
                _LOGGER.debug("User data updated successfully")
            except (TibberPricesApiClientError, TibberPricesApiClientCommunicationError) as ex:
                _LOGGER.warning("Failed to update user data: %s", ex)

    @callback
    def _should_update_price_data(self, current_time: datetime) -> bool:
        """Check if price data should be updated."""
        if self._cached_price_data is None:
            return True
        if self._last_price_update is None:
            return True
        # Update every 15 minutes
        return (current_time - self._last_price_update) >= UPDATE_INTERVAL

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

        # Get threshold percentages for enrichment
        thresholds = self._get_threshold_percentages()

        # Enrich price info with calculated differences (trailing 24h averages)
        price_info = enrich_price_info_with_differences(
            price_info,
            threshold_low=thresholds["low"],
            threshold_high=thresholds["high"],
        )

        return {
            "timestamp": raw_data.get("timestamp"),
            "homes": homes_data,
            "priceInfo": price_info,
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

        # Get threshold percentages for enrichment
        thresholds = self._get_threshold_percentages()

        # Enrich price info with calculated differences (trailing 24h averages)
        price_info = enrich_price_info_with_differences(
            price_info,
            threshold_low=thresholds["low"],
            threshold_high=thresholds["high"],
        )

        return {
            "timestamp": main_data.get("timestamp"),
            "priceInfo": price_info,
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
