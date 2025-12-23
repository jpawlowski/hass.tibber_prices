"""Calculator for data lifecycle status tracking."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from custom_components.tibber_prices.coordinator.constants import UPDATE_INTERVAL

from .base import TibberPricesBaseCalculator

# Constants for lifecycle state determination
FRESH_DATA_THRESHOLD_MINUTES = 5  # Data is "fresh" within 5 minutes of API fetch
TOMORROW_CHECK_HOUR = 13  # After 13:00, we actively check for tomorrow data
TURNOVER_WARNING_SECONDS = 900  # Warn 15 minutes before midnight (last quarter-hour: 23:45-00:00)

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
        - "turnover_pending": Last interval of day (23:45-00:00, midnight approaching)
        - "error": Last API call failed

        Priority order (highest to lowest):
        1. refreshing - Active operation has highest priority
        2. error - Errors must be immediately visible
        3. turnover_pending - Important event at 23:45, should stay visible
        4. searching_tomorrow - Stable during search phase (13:00-~15:00)
        5. fresh - Informational only, lowest priority among active states
        6. cached - Default fallback

        """
        coordinator = self.coordinator
        current_time = coordinator.time.now()

        # Priority 1: Check if actively fetching (highest priority)
        if coordinator._is_fetching:  # noqa: SLF001 - Internal state access for lifecycle tracking
            return "refreshing"

        # Priority 2: Check if last update failed
        # If coordinator has last_exception set, the last fetch failed
        if coordinator.last_exception is not None:
            return "error"

        # Priority 3: Check if midnight turnover is pending (last quarter of day: 23:45-00:00)
        midnight = coordinator.time.as_local(current_time).replace(
            hour=0, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)
        time_to_midnight = (midnight - coordinator.time.as_local(current_time)).total_seconds()
        if 0 < time_to_midnight <= TURNOVER_WARNING_SECONDS:  # Within 15 minutes of midnight (23:45-00:00)
            return "turnover_pending"

        # Priority 4: Check if we're in tomorrow data search mode (after 13:00 and tomorrow missing)
        # This should remain stable during the search phase, not flicker with "fresh" every 15 minutes
        now_local = coordinator.time.as_local(current_time)
        if now_local.hour >= TOMORROW_CHECK_HOUR and coordinator._needs_tomorrow_data():  # noqa: SLF001 - Internal state access
            return "searching_tomorrow"

        # Priority 5: Check if data is fresh (within 5 minutes of last API fetch)
        # Lower priority than searching_tomorrow to avoid state flickering during search phase
        if coordinator._last_price_update:  # noqa: SLF001 - Internal state access for lifecycle tracking
            age = current_time - coordinator._last_price_update  # noqa: SLF001
            if age <= timedelta(minutes=FRESH_DATA_THRESHOLD_MINUTES):
                return "fresh"

        # Priority 6: Default - using cached data
        return "cached"

    def get_sensor_fetch_age_minutes(self) -> int | None:
        """
        Calculate how many minutes ago sensor data was last fetched.

        Uses the Pool's last_sensor_fetch as the source of truth.
        This only counts API fetches for sensor data (protected range),
        not service-triggered fetches for chart data.

        Returns:
            Minutes since last sensor fetch, or None if no fetch recorded.

        """
        pool_stats = self._get_pool_stats()
        if not pool_stats or not pool_stats.get("last_sensor_fetch"):
            return None

        last_fetch = pool_stats["last_sensor_fetch"]
        # Parse ISO timestamp
        last_fetch_dt = datetime.fromisoformat(last_fetch)
        age = self.coordinator.time.now() - last_fetch_dt
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
        tomorrow_missing = coordinator._needs_tomorrow_data()  # noqa: SLF001

        # Get tomorrow date for time calculations
        _, tomorrow_midnight = coordinator.time.get_day_boundaries("today")

        # Case 1: Before 13:00 today - next poll is today at 13:xx:xx (when tomorrow-search begins)
        if now_local.hour < TOMORROW_CHECK_HOUR:
            # Calculate exact time based on Timer #1 offset (minute and second precision)
            if coordinator._last_coordinator_update is not None:  # noqa: SLF001
                last_update_local = coordinator.time.as_local(coordinator._last_coordinator_update)  # noqa: SLF001
                # Timer offset: minutes + seconds past the quarter-hour
                minutes_past_quarter = last_update_local.minute % 15
                seconds_offset = last_update_local.second

                # Calculate first timer execution at or after 13:00 today
                # Just apply timer offset to 13:00 (first quarter-hour mark >= 13:00)
                # Timer runs at X:04:37 → Next poll at 13:04:37
                return now_local.replace(
                    hour=TOMORROW_CHECK_HOUR,
                    minute=minutes_past_quarter,
                    second=seconds_offset,
                    microsecond=0,
                )

            # Fallback: No timer history yet
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

    def get_next_midnight_turnover_time(self) -> datetime:
        """Calculate when the next midnight turnover will occur."""
        coordinator = self.coordinator
        current_time = coordinator.time.now()
        now_local = coordinator.time.as_local(current_time)

        # Next midnight
        return now_local.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

    def get_api_calls_today(self) -> int:
        """Get the number of API calls made today."""
        coordinator = self.coordinator

        # Reset counter if day changed
        current_date = coordinator.time.now().date()
        if coordinator._last_api_call_date != current_date:  # noqa: SLF001 - Internal state access
            return 0

        return coordinator._api_calls_today  # noqa: SLF001

    def has_tomorrow_data(self) -> bool:
        """
        Check if tomorrow's price data is available.

        Returns:
            True if tomorrow data exists in the pool.

        """
        return not self.coordinator._needs_tomorrow_data()  # noqa: SLF001

    def get_pool_stats(self) -> dict[str, Any] | None:
        """
        Get interval pool statistics.

        Returns:
            Dict with pool stats or None if pool not available.
            Contains:
            - Sensor intervals (protected range):
              - sensor_intervals_count: Intervals in protected range
              - sensor_intervals_expected: Expected count (usually 384)
              - sensor_intervals_has_gaps: True if gaps exist
            - Cache statistics:
              - cache_intervals_total: Total intervals in cache
              - cache_intervals_limit: Maximum cache size
              - cache_fill_percent: How full the cache is (%)
              - cache_intervals_extra: Intervals outside protected range
            - Timestamps:
              - last_sensor_fetch: When sensor data was last fetched
              - cache_oldest_interval: Oldest interval in cache
              - cache_newest_interval: Newest interval in cache
            - Metadata:
              - fetch_groups_count: Number of API fetch batches stored

        """
        return self._get_pool_stats()

    def _get_pool_stats(self) -> dict[str, Any] | None:
        """
        Get pool stats from coordinator.

        Returns:
            Pool statistics dict or None.

        """
        coordinator = self.coordinator
        # Access the pool via the price data manager
        if hasattr(coordinator, "_price_data_manager"):
            price_data_manager = coordinator._price_data_manager  # noqa: SLF001
            if hasattr(price_data_manager, "_interval_pool"):
                pool = price_data_manager._interval_pool  # noqa: SLF001
                if pool is not None:
                    return pool.get_pool_stats()
        return None
