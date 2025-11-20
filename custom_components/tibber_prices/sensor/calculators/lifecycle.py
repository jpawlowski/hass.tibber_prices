"""Calculator for data lifecycle status tracking."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

from custom_components.tibber_prices.coordinator.constants import UPDATE_INTERVAL

from .base import TibberPricesBaseCalculator

# Constants for lifecycle state determination
FRESH_DATA_THRESHOLD_MINUTES = 5  # Data is "fresh" within 5 minutes of API fetch
TOMORROW_CHECK_HOUR = 13  # After 13:00, we actively check for tomorrow data
TURNOVER_WARNING_SECONDS = 300  # Warn 5 minutes before midnight

# Constants for 15-minute update boundaries (Timer #1)
QUARTER_HOUR_BOUNDARIES = [0, 15, 30, 45]  # Minutes when Timer #1 can trigger
LAST_HOUR_OF_DAY = 23


class TibberPricesLifecycleCalculator(TibberPricesBaseCalculator):
    """Calculate data lifecycle status and metadata."""

    def get_lifecycle_state(self) -> str:
        """
        Determine current data lifecycle state.

        Returns one of:
        - "cached": Using cached data (normal operation)
        - "fresh": Just fetched from API (within 5 minutes)
        - "refreshing": Currently fetching data from API
        - "searching_tomorrow": After 13:00, actively looking for tomorrow data
        - "turnover_pending": Midnight is approaching (within 5 minutes)
        - "error": Last API call failed

        """
        coordinator = self.coordinator
        current_time = coordinator.time.now()

        # Check if actively fetching
        if coordinator._is_fetching:  # noqa: SLF001 - Internal state access for lifecycle tracking
            return "refreshing"

        # Check if last update failed
        # If coordinator has last_exception set, the last fetch failed
        if coordinator.last_exception is not None:
            return "error"

        # Check if data is fresh (within 5 minutes of last API fetch)
        if coordinator._last_price_update:  # noqa: SLF001 - Internal state access for lifecycle tracking
            age = current_time - coordinator._last_price_update  # noqa: SLF001
            if age <= timedelta(minutes=FRESH_DATA_THRESHOLD_MINUTES):
                return "fresh"

        # Check if midnight turnover is pending (within 15 minutes)
        midnight = coordinator.time.as_local(current_time).replace(
            hour=0, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)
        time_to_midnight = (midnight - coordinator.time.as_local(current_time)).total_seconds()
        if 0 < time_to_midnight <= TURNOVER_WARNING_SECONDS:  # Within 15 minutes of midnight (23:45-00:00)
            return "turnover_pending"

        # Check if we're in tomorrow data search mode (after 13:00 and tomorrow missing)
        now_local = coordinator.time.as_local(current_time)
        if now_local.hour >= TOMORROW_CHECK_HOUR:
            _, tomorrow_midnight = coordinator.time.get_day_boundaries("today")
            tomorrow_date = tomorrow_midnight.date()
            if coordinator._needs_tomorrow_data(tomorrow_date):  # noqa: SLF001 - Internal state access
                return "searching_tomorrow"

        # Default: using cached data
        return "cached"

    def get_cache_age_minutes(self) -> int | None:
        """Calculate how many minutes old the cached data is."""
        coordinator = self.coordinator
        if not coordinator._last_price_update:  # noqa: SLF001 - Internal state access for lifecycle tracking
            return None

        age = coordinator.time.now() - coordinator._last_price_update  # noqa: SLF001
        return int(age.total_seconds() / 60)

    def get_next_api_poll_time(self) -> datetime | None:
        """
        Calculate when the next API poll attempt will occur.

        Timer #1 runs every 15 minutes FROM INTEGRATION START, not at fixed boundaries.
        For example, if integration started at 13:07, timer runs at 13:07, 13:22, 13:37, 13:52.

        Returns:
            Next poll time when tomorrow data will be fetched (predictive).

        Logic:
            - If before 13:00 today: Show today 13:00 (when tomorrow-search begins)
            - If after 13:00 today AND tomorrow data missing: Show next Timer #1 execution (intensive polling)
            - If after 13:00 today AND tomorrow data present: Show tomorrow 13:00 (predictive!)

        """
        coordinator = self.coordinator
        current_time = coordinator.time.now()
        now_local = coordinator.time.as_local(current_time)

        # Check if tomorrow data is missing
        _, tomorrow_midnight = coordinator.time.get_day_boundaries("today")
        tomorrow_date = tomorrow_midnight.date()
        tomorrow_missing = coordinator._needs_tomorrow_data(tomorrow_date)  # noqa: SLF001

        # Case 1: Before 13:00 today - next poll is today at 13:00 (when tomorrow-search begins)
        if now_local.hour < TOMORROW_CHECK_HOUR:
            return now_local.replace(hour=TOMORROW_CHECK_HOUR, minute=0, second=0, microsecond=0)

        # Case 2: After 13:00 today AND tomorrow data missing - actively polling now
        if tomorrow_missing:
            # Calculate next Timer #1 execution based on last coordinator update
            if coordinator._last_coordinator_update is not None:  # noqa: SLF001
                next_timer = coordinator._last_coordinator_update + UPDATE_INTERVAL  # noqa: SLF001
                return coordinator.time.as_local(next_timer)

            # Fallback: If we don't know when last update was, estimate from now
            # (Should rarely happen - only on first startup before first Timer #1 run)
            return now_local + UPDATE_INTERVAL

        # Case 3: After 13:00 today AND tomorrow data present - PREDICTIVE: next fetch is tomorrow 13:xx
        # After midnight turnover, tomorrow becomes today, and we'll need NEW tomorrow data
        # Calculate tomorrow's first Timer #1 execution after 13:00 based on current timer offset
        tomorrow_midnight = now_local.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        tomorrow_13 = tomorrow_midnight.replace(hour=TOMORROW_CHECK_HOUR, minute=0, second=0, microsecond=0)

        # If we know the last coordinator update, calculate the timer offset
        if coordinator._last_coordinator_update is not None:  # noqa: SLF001
            last_update_local = coordinator.time.as_local(coordinator._last_coordinator_update)  # noqa: SLF001

            # Calculate offset: minutes + seconds past the quarter-hour boundary
            # Example: Timer runs at 13:04:37 → offset is 4 minutes 37 seconds from 13:00:00
            minutes_past_quarter = last_update_local.minute % 15
            seconds_offset = last_update_local.second

            # Find first Timer #1 execution at or after 13:00:00 tomorrow
            # Start at 13:00:00 and add offset
            candidate_time = tomorrow_13.replace(minute=minutes_past_quarter, second=seconds_offset, microsecond=0)

            # If this is before 13:00, add 15 minutes (first timer after 13:00)
            # Example: If offset is :59:30, candidate would be 12:59:30, so we add 15min → 13:14:30
            if candidate_time < tomorrow_13:
                candidate_time += UPDATE_INTERVAL

            return candidate_time

        # Fallback: If we don't know timer offset yet, assume 13:00:00
        return tomorrow_13

    def get_next_tomorrow_check_time(self) -> datetime | None:
        """
        Calculate when the next tomorrow data check will occur.

        Returns None if not applicable (before 13:00 or tomorrow already available).
        """
        coordinator = self.coordinator
        current_time = coordinator.time.now()
        now_local = coordinator.time.as_local(current_time)

        # Only relevant after 13:00
        if now_local.hour < TOMORROW_CHECK_HOUR:
            return None

        # Only relevant if tomorrow data is missing
        _, tomorrow_midnight = coordinator.time.get_day_boundaries("today")
        tomorrow_date = tomorrow_midnight.date()
        if not coordinator._needs_tomorrow_data(tomorrow_date):  # noqa: SLF001 - Internal state access
            return None

        # Next check = next regular API poll (same as get_next_api_poll_time)
        return self.get_next_api_poll_time()

    def get_next_midnight_turnover_time(self) -> datetime:
        """Calculate when the next midnight turnover will occur."""
        coordinator = self.coordinator
        current_time = coordinator.time.now()
        now_local = coordinator.time.as_local(current_time)

        # Next midnight
        return now_local.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

    def is_data_available(self, day: str) -> bool:
        """
        Check if data is available for a specific day.

        Args:
            day: "yesterday", "today", or "tomorrow"

        Returns:
            True if data exists and is not empty

        """
        coordinator = self.coordinator
        if not coordinator.data:
            return False

        price_info = coordinator.data.get("priceInfo", {})
        day_data = price_info.get(day, [])
        return bool(day_data)

    def get_data_completeness_status(self) -> str:
        """
        Get human-readable data completeness status.

        Returns:
            'complete': All data (yesterday/today/tomorrow) available
            'missing_tomorrow': Only yesterday and today available
            'missing_yesterday': Only today and tomorrow available
            'partial': Only today or some other partial combination
            'no_data': No data available at all

        """
        yesterday_available = self.is_data_available("yesterday")
        today_available = self.is_data_available("today")
        tomorrow_available = self.is_data_available("tomorrow")

        if yesterday_available and today_available and tomorrow_available:
            return "complete"
        if yesterday_available and today_available and not tomorrow_available:
            return "missing_tomorrow"
        if not yesterday_available and today_available and tomorrow_available:
            return "missing_yesterday"
        if today_available:
            return "partial"
        return "no_data"

    def get_cache_validity_status(self) -> str:
        """
        Get cache validity status.

        Returns:
            "valid": Cache is current and matches today's date
            "stale": Cache exists but is outdated
            "date_mismatch": Cache is from a different day
            "empty": No cache data

        """
        coordinator = self.coordinator
        # Check if coordinator has data (transformed, ready for entities)
        if not coordinator.data:
            return "empty"

        # Check if we have price update timestamp
        if not coordinator._last_price_update:  # noqa: SLF001 - Internal state access for lifecycle tracking
            return "empty"

        current_time = coordinator.time.now()
        current_local_date = coordinator.time.as_local(current_time).date()
        last_update_local_date = coordinator.time.as_local(coordinator._last_price_update).date()  # noqa: SLF001

        if current_local_date != last_update_local_date:
            return "date_mismatch"

        # Check if cache is stale (older than expected)
        age = current_time - coordinator._last_price_update  # noqa: SLF001
        # Consider stale if older than 2 hours (8 * 15-minute intervals)
        if age > timedelta(hours=2):
            return "stale"

        return "valid"

    def get_api_calls_today(self) -> int:
        """Get the number of API calls made today."""
        coordinator = self.coordinator

        # Reset counter if day changed
        current_date = coordinator.time.now().date()
        if coordinator._last_api_call_date != current_date:  # noqa: SLF001 - Internal state access
            return 0

        return coordinator._api_calls_today  # noqa: SLF001
