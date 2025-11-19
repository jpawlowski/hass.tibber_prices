"""
TimeService - Centralized time management for Tibber Prices integration.

This service provides:
1. Single source of truth for current time
2. Timezone-aware operations (respects HA user timezone)
3. Domain-specific datetime methods (intervals, boundaries, horizons)
4. Time-travel capability (inject simulated time for testing)

All datetime operations MUST go through TimeService to ensure:
- Consistent time across update cycles
- Proper timezone handling (local time, not UTC)
- Testability (mock time in one place)
- Future time-travel feature support
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from datetime import date

# =============================================================================
# CRITICAL: This is the ONLY module allowed to import dt_util for operations!
# =============================================================================
#
# Other modules may import dt_util ONLY in these cases:
# 1. api/client.py - Rate limiting (non-critical, cosmetic)
# 2. entity_utils/icons.py - Icon updates (cosmetic, independent)
#
# All business logic MUST use TimeService instead.
# =============================================================================

# Constants (private - use TimeService methods instead)
_DEFAULT_INTERVAL_MINUTES = 15  # Tibber uses 15-minute intervals
_INTERVALS_PER_HOUR = 60 // _DEFAULT_INTERVAL_MINUTES  # 4
_INTERVALS_PER_DAY = 24 * _INTERVALS_PER_HOUR  # 96

# Rounding tolerance for boundary detection (±2 seconds)
_BOUNDARY_TOLERANCE_SECONDS = 2


class TimeService:
    """
    Centralized time service for Tibber Prices integration.

    Provides timezone-aware datetime operations with consistent time context.
    All times are in user's Home Assistant local timezone.

    Features:
    - Single source of truth for "now" per update cycle
    - Domain-specific methods (intervals, periods, boundaries)
    - Time-travel support (inject simulated time)
    - Timezone-safe (all operations respect HA user timezone)

    Usage:
        # Create service with current time
        time_service = TimeService()

        # Get consistent "now" throughout update cycle
        now = time_service.now()

        # Domain-specific operations
        current_interval_start = time_service.get_current_interval_start()
        next_interval = time_service.get_interval_offset_time(1)
        midnight = time_service.get_local_midnight()
    """

    def __init__(self, reference_time: datetime | None = None) -> None:
        """
        Initialize TimeService with reference time.

        Args:
            reference_time: Optional fixed time for this context.
                          If None, uses actual current time.
                          For time-travel: pass simulated time here.

        """
        self._reference_time = reference_time or dt_util.now()

    # =========================================================================
    # Low-Level API: Direct dt_util wrappers
    # =========================================================================

    def now(self) -> datetime:
        """
        Get current reference time in user's local timezone.

        Returns same value throughout the lifetime of this TimeService instance.
        This ensures consistent time across all calculations in an update cycle.

        Returns:
            Timezone-aware datetime in user's HA local timezone.

        """
        return self._reference_time

    def get_rounded_now(self) -> datetime:
        """
        Get current reference time rounded to nearest 15-minute boundary.

        Convenience method that combines now() + round_to_nearest_quarter().
        Use this when you need the current interval timestamp for calculations.

        Returns:
            Current reference time rounded to :00, :15, :30, or :45

        Examples:
            If now is 14:59:58 → returns 15:00:00
            If now is 14:59:30 → returns 14:45:00
            If now is 15:00:01 → returns 15:00:00

        """
        return self.round_to_nearest_quarter()

    def as_local(self, dt: datetime) -> datetime:
        """
        Convert datetime to user's local timezone.

        Args:
            dt: Timezone-aware datetime (any timezone).

        Returns:
            Same moment in time, converted to user's local timezone.

        """
        return dt_util.as_local(dt)

    def parse_datetime(self, dt_str: str) -> datetime | None:
        """
        Parse ISO 8601 datetime string.

        Args:
            dt_str: ISO 8601 formatted string (e.g., "2025-11-19T13:00:00+00:00").

        Returns:
            Timezone-aware datetime, or None if parsing fails.

        """
        return dt_util.parse_datetime(dt_str)

    def parse_and_localize(self, dt_str: str) -> datetime | None:
        """
        Parse ISO string and convert to user's local timezone.

        Combines parse_datetime() + as_local() in one call.
        Use this for API timestamps that need immediate localization.

        Args:
            dt_str: ISO 8601 formatted string (e.g., "2025-11-19T13:00:00+00:00").

        Returns:
            Timezone-aware datetime in user's local timezone, or None if parsing fails.

        """
        parsed = self.parse_datetime(dt_str)
        return self.as_local(parsed) if parsed else None

    def start_of_local_day(self, dt: datetime | None = None) -> datetime:
        """
        Get midnight (00:00) of the given datetime in user's local timezone.

        Args:
            dt: Reference datetime. If None, uses reference_time.

        Returns:
            Midnight (start of day) in user's local timezone.

        """
        target = dt if dt is not None else self._reference_time
        return dt_util.start_of_local_day(target)

    # =========================================================================
    # High-Level API: Domain-Specific Methods
    # =========================================================================

    # -------------------------------------------------------------------------
    # Interval Data Extraction
    # -------------------------------------------------------------------------

    def get_interval_time(self, interval: dict) -> datetime | None:
        """
        Extract and parse interval timestamp from API data.

        Handles common pattern: parse "startsAt" + convert to local timezone.
        Replaces repeated parse_datetime() + as_local() pattern.

        Args:
            interval: Price interval dict with "startsAt" field (ISO string or datetime object)

        Returns:
            Localized datetime or None if parsing/conversion fails

        """
        starts_at = interval.get("startsAt")
        if not starts_at:
            return None

        # If already a datetime object (parsed from cache), return as-is
        if isinstance(starts_at, datetime):
            return starts_at

        # Otherwise parse the string
        return self.parse_and_localize(starts_at)

    # -------------------------------------------------------------------------
    # Time Comparison Helpers
    # -------------------------------------------------------------------------

    def is_in_past(self, dt: datetime) -> bool:
        """
        Check if datetime is before reference time (now).

        Args:
            dt: Datetime to check

        Returns:
            True if dt < now()

        """
        return dt < self.now()

    def is_in_future(self, dt: datetime) -> bool:
        """
        Check if datetime is after or equal to reference time (now).

        Args:
            dt: Datetime to check

        Returns:
            True if dt >= now()

        """
        return dt >= self.now()

    def is_current_interval(self, start: datetime, end: datetime) -> bool:
        """
        Check if reference time (now) falls within interval [start, end).

        Args:
            start: Interval start time (inclusive)
            end: Interval end time (exclusive)

        Returns:
            True if start <= now() < end

        """
        now = self.now()
        return start <= now < end

    def is_in_day(self, dt: datetime, day: str) -> bool:
        """
        Check if datetime falls within specified calendar day.

        Args:
            dt: Datetime to check (should be localized)
            day: "yesterday", "today", or "tomorrow"

        Returns:
            True if dt is within day boundaries

        """
        start, end = self.get_day_boundaries(day)
        return start <= dt < end

    # -------------------------------------------------------------------------
    # Duration Calculations
    # -------------------------------------------------------------------------

    def get_hours_until(self, future_time: datetime) -> float:
        """
        Calculate hours from reference time (now) until future_time.

        Args:
            future_time: Future datetime

        Returns:
            Hours (can be negative if in past, decimal for partial hours)

        """
        delta = future_time - self.now()
        return delta.total_seconds() / 3600

    def get_local_date(self, offset_days: int = 0) -> date:
        """
        Get date for day at offset from reference date.

        Convenience method to replace repeated time.now().date() or
        time.get_local_midnight(n).date() patterns.

        Args:
            offset_days: Days to offset.
                        0 = today, 1 = tomorrow, -1 = yesterday, etc.

        Returns:
            Date object in user's local timezone.

        Examples:
            get_local_date()     → today's date
            get_local_date(1)    → tomorrow's date
            get_local_date(-1)   → yesterday's date

        """
        target_datetime = self._reference_time + timedelta(days=offset_days)
        return target_datetime.date()

    def is_time_in_period(self, start: datetime, end: datetime, check_time: datetime | None = None) -> bool:
        """
        Check if time falls within period [start, end).

        Args:
            start: Period start time (inclusive)
            end: Period end time (exclusive)
            check_time: Time to check. If None, uses reference time (now).

        Returns:
            True if start <= check_time < end

        Examples:
            # Check if now is in period:
            is_time_in_period(period_start, period_end)

            # Check if specific time is in period:
            is_time_in_period(window_start, window_end, some_timestamp)

        """
        t = check_time if check_time is not None else self.now()
        return start <= t < end

    def is_time_within_horizon(self, target_time: datetime, hours: int) -> bool:
        """
        Check if target time is in future within specified hour horizon.

        Combines two common checks:
        1. Is target_time in the future? (target_time > now)
        2. Is target_time within N hours? (target_time <= now + N hours)

        Args:
            target_time: Time to check
            hours: Lookahead horizon in hours

        Returns:
            True if now < target_time <= now + hours

        Examples:
            # Check if period starts within next 6 hours:
            is_time_within_horizon(period_start, hours=6)

            # Check if event happens within next 24 hours:
            is_time_within_horizon(event_time, hours=24)

        """
        now = self.now()
        horizon = now + timedelta(hours=hours)
        return now < target_time <= horizon

    def hours_since(self, past_time: datetime) -> float:
        """
        Calculate hours from past_time until reference time (now).

        Args:
            past_time: Past datetime

        Returns:
            Hours (can be negative if in future, decimal for partial hours)

        """
        delta = self.now() - past_time
        return delta.total_seconds() / 3600

    def minutes_until(self, future_time: datetime) -> float:
        """
        Calculate minutes from reference time (now) until future_time.

        Args:
            future_time: Future datetime

        Returns:
            Minutes (can be negative if in past, decimal for partial minutes)

        """
        delta = future_time - self.now()
        return delta.total_seconds() / 60

    def minutes_until_rounded(self, future_time: datetime | str) -> int:
        """
        Calculate ROUNDED minutes from reference time (now) until future_time.

        Uses standard rounding (0.5 rounds up) to match Home Assistant frontend
        relative time display. This ensures sensor values match what users see
        in the UI ("in X minutes").

        Args:
            future_time: Future datetime or ISO string to parse

        Returns:
            Rounded minutes (negative if in past)

        Examples:
            44.2 minutes → 44
            44.5 minutes → 45 (rounds up, like HA frontend)
            44.7 minutes → 45

        """
        # Parse string if needed
        if isinstance(future_time, str):
            parsed = self.parse_and_localize(future_time)
            if not parsed:
                return 0
            future_time = parsed

        delta = future_time - self.now()
        seconds = delta.total_seconds()

        # Standard rounding: 0.5 rounds up (matches HA frontend behavior)
        # Using math.floor + 0.5 instead of Python's round() which uses banker's rounding
        return math.floor(seconds / 60 + 0.5)

    # -------------------------------------------------------------------------
    # Interval Operations (15-minute grid)
    # -------------------------------------------------------------------------

    def get_interval_duration(self) -> timedelta:
        """
        Get duration of one interval.

        Returns:
            Timedelta representing interval length (15 minutes for Tibber).

        """
        return timedelta(minutes=_DEFAULT_INTERVAL_MINUTES)

    def minutes_to_intervals(self, minutes: int) -> int:
        """
        Convert minutes to number of intervals.

        Args:
            minutes: Number of minutes to convert.

        Returns:
            Number of intervals (rounded down).

        Examples:
            15 minutes → 1 interval
            30 minutes → 2 intervals
            45 minutes → 3 intervals
            60 minutes → 4 intervals

        """
        return minutes // _DEFAULT_INTERVAL_MINUTES

    def round_to_nearest_quarter(self, dt: datetime | None = None) -> datetime:
        """
        Round datetime to nearest 15-minute boundary with smart tolerance.

        Handles HA scheduling jitter: if within ±2 seconds of boundary,
        round to that boundary. Otherwise, floor to current interval.

        Args:
            dt: Datetime to round. If None, uses reference_time.

        Returns:
            Datetime rounded to nearest quarter-hour boundary.

        Examples:
            14:59:58 → 15:00:00 (within 2s of boundary)
            14:59:30 → 14:45:00 (not within 2s, stay in current)
            15:00:01 → 15:00:00 (within 2s of boundary)

        """
        target = dt if dt is not None else self._reference_time

        # Calculate total seconds in day
        total_seconds = target.hour * 3600 + target.minute * 60 + target.second + target.microsecond / 1_000_000

        # Find current interval boundaries
        interval_index = int(total_seconds // (_DEFAULT_INTERVAL_MINUTES * 60))
        interval_start_seconds = interval_index * _DEFAULT_INTERVAL_MINUTES * 60

        next_interval_index = (interval_index + 1) % _INTERVALS_PER_DAY
        next_interval_start_seconds = next_interval_index * _DEFAULT_INTERVAL_MINUTES * 60

        # Distance to boundaries
        distance_to_current = total_seconds - interval_start_seconds
        if next_interval_index == 0:  # Midnight wrap
            distance_to_next = (24 * 3600) - total_seconds
        else:
            distance_to_next = next_interval_start_seconds - total_seconds

        # Apply tolerance: if within 2 seconds of a boundary, round to it
        if distance_to_current <= _BOUNDARY_TOLERANCE_SECONDS:
            # Near current interval start → use it
            rounded_seconds = interval_start_seconds
        elif distance_to_next <= _BOUNDARY_TOLERANCE_SECONDS:
            # Near next interval start → use it
            rounded_seconds = next_interval_start_seconds
        else:
            # Not near any boundary → floor to current interval
            rounded_seconds = interval_start_seconds

        # Handle midnight wrap
        if rounded_seconds >= 24 * 3600:
            rounded_seconds = 0

        # Build rounded datetime
        hours = int(rounded_seconds // 3600)
        minutes = int((rounded_seconds % 3600) // 60)

        return target.replace(hour=hours, minute=minutes, second=0, microsecond=0)

    def get_current_interval_start(self) -> datetime:
        """
        Get start time of current 15-minute interval.

        Returns:
            Datetime at start of current interval (rounded down).

        Example:
            Reference time 14:37:23 → returns 14:30:00

        """
        return self.round_to_nearest_quarter(self._reference_time)

    def get_next_interval_start(self) -> datetime:
        """
        Get start time of next 15-minute interval.

        Returns:
            Datetime at start of next interval.

        Example:
            Reference time 14:37:23 → returns 14:45:00

        """
        return self.get_interval_offset_time(1)

    def get_interval_offset_time(self, offset: int = 0) -> datetime:
        """
        Get start time of interval at offset from current.

        Args:
            offset: Number of intervals to offset.
                   0 = current, 1 = next, -1 = previous, etc.

        Returns:
            Datetime at start of target interval.

        Examples:
            offset=0  → current interval (14:30:00)
            offset=1  → next interval (14:45:00)
            offset=-1 → previous interval (14:15:00)

        """
        current_start = self.get_current_interval_start()
        delta = timedelta(minutes=_DEFAULT_INTERVAL_MINUTES * offset)
        return current_start + delta

    # -------------------------------------------------------------------------
    # Day Boundaries (midnight-to-midnight windows)
    # -------------------------------------------------------------------------

    def get_local_midnight(self, offset_days: int = 0) -> datetime:
        """
        Get midnight (00:00) for day at offset from reference date.

        Args:
            offset_days: Days to offset.
                        0 = today, 1 = tomorrow, -1 = yesterday, etc.

        Returns:
            Midnight (start of day) in user's local timezone.

        Examples:
            offset_days=0  → today 00:00
            offset_days=1  → tomorrow 00:00
            offset_days=-1 → yesterday 00:00

        """
        target_date = self._reference_time.date() + timedelta(days=offset_days)
        target_datetime = datetime.combine(target_date, datetime.min.time())
        return dt_util.as_local(target_datetime)

    def get_day_boundaries(self, day: str = "today") -> tuple[datetime, datetime]:
        """
        Get start and end times for a day (midnight to midnight).

        Args:
            day: Day identifier ("day_before_yesterday", "yesterday", "today", "tomorrow").

        Returns:
            Tuple of (start_time, end_time) for the day.
            start_time: midnight (00:00:00) of that day
            end_time: midnight (00:00:00) of next day (exclusive boundary)

        Examples:
            day="today" → (today 00:00, tomorrow 00:00)
            day="yesterday" → (yesterday 00:00, today 00:00)

        """
        day_map = {
            "day_before_yesterday": -2,
            "yesterday": -1,
            "today": 0,
            "tomorrow": 1,
        }

        if day not in day_map:
            msg = f"Invalid day: {day}. Must be one of {list(day_map.keys())}"
            raise ValueError(msg)

        offset = day_map[day]
        start = self.get_local_midnight(offset)
        end = self.get_local_midnight(offset + 1)  # Next day's midnight

        return start, end

    def get_expected_intervals_for_day(self, day_date: date | None = None) -> int:
        """
        Calculate expected number of 15-minute intervals for a day.

        Handles DST transitions:
        - Normal day: 96 intervals (24 hours * 4)
        - Spring forward (lose 1 hour): 92 intervals (23 hours * 4)
        - Fall back (gain 1 hour): 100 intervals (25 hours * 4)

        Args:
            day_date: Date to check. If None, uses reference date.

        Returns:
            Expected number of 15-minute intervals for that day.

        """
        target_date = day_date if day_date is not None else self._reference_time.date()

        # Get midnight of target day and next day in local timezone
        #
        # IMPORTANT: We cannot use dt_util.start_of_local_day() here due to TWO issues:
        #
        # Issue 1 - pytz LMT Bug:
        #   dt_util.start_of_local_day() uses: datetime.combine(date, time(), tzinfo=tz)
        #   With pytz, this triggers the "Local Mean Time" bug - using historical timezone
        #   offsets from before standard timezones were established (e.g., +00:53 for Berlin
        #   instead of +01:00/+02:00). Both timestamps get the same wrong offset, making
        #   duration calculations incorrect for DST transitions.
        #
        # Issue 2 - Python datetime Subtraction Ignores Timezone Offsets:
        #   Even with correct offsets (e.g., via zoneinfo):
        #     start = 2025-03-30 00:00+01:00  (= 2025-03-29 23:00 UTC)
        #     end   = 2025-03-31 00:00+02:00  (= 2025-03-30 22:00 UTC)
        #     end - start = 1 day = 24 hours  (WRONG!)
        #
        #   Python's datetime subtraction uses naive date/time difference, ignoring that
        #   timezone offsets changed between the two timestamps. The real UTC duration is
        #   23 hours (Spring Forward) or 25 hours (Fall Back).
        #
        # Solution:
        #   1. Use timezone.localize() (pytz) or replace(tzinfo=tz) (zoneinfo) to get
        #      correct timezone-aware datetimes with proper offsets
        #   2. Convert to UTC before calculating duration to account for offset changes
        #
        #   This ensures DST transitions are correctly handled:
        #     - Spring Forward: 23 hours (92 intervals)
        #     - Fall Back: 25 hours (100 intervals)
        #     - Normal day: 24 hours (96 intervals)
        #
        tz = self._reference_time.tzinfo  # Get timezone from reference time

        # Create naive datetimes for midnight of target and next day
        start_naive = datetime.combine(target_date, datetime.min.time())
        next_day = target_date + timedelta(days=1)
        end_naive = datetime.combine(next_day, datetime.min.time())

        # Localize to get correct DST offset for each date
        if hasattr(tz, "localize"):
            # pytz timezone - use localize() to handle DST correctly
            start_midnight_local = tz.localize(start_naive)
            end_midnight_local = tz.localize(end_naive)
        else:
            # zoneinfo or other timezone - can use replace directly
            start_midnight_local = start_naive.replace(tzinfo=tz)
            end_midnight_local = end_naive.replace(tzinfo=tz)

        # Calculate actual duration via UTC to handle timezone offset changes correctly
        # Direct subtraction (end - start) would ignore DST offset changes and always
        # return 24 hours, even on Spring Forward (23h) or Fall Back (25h) days
        start_utc = start_midnight_local.astimezone(dt_util.UTC)
        end_utc = end_midnight_local.astimezone(dt_util.UTC)
        duration = end_utc - start_utc
        hours = duration.total_seconds() / 3600

        # Convert to intervals (4 per hour for 15-minute intervals)
        return int(hours * _INTERVALS_PER_HOUR)

    # -------------------------------------------------------------------------
    # Time Windows (relative to current interval)
    # -------------------------------------------------------------------------

    def get_trailing_window(self, hours: int = 24) -> tuple[datetime, datetime]:
        """
        Get trailing time window ending at current interval.

        Args:
            hours: Window size in hours (default 24).

        Returns:
            Tuple of (start_time, end_time) for trailing window.
            start_time: current interval - hours
            end_time: current interval start (exclusive)

        Example:
            Current interval: 14:30
            hours=24 → (yesterday 14:30, today 14:30)

        """
        end = self.get_current_interval_start()
        start = end - timedelta(hours=hours)
        return start, end

    def get_leading_window(self, hours: int = 24) -> tuple[datetime, datetime]:
        """
        Get leading time window starting at current interval.

        Args:
            hours: Window size in hours (default 24).

        Returns:
            Tuple of (start_time, end_time) for leading window.
            start_time: current interval start
            end_time: current interval + hours (exclusive)

        Example:
            Current interval: 14:30
            hours=24 → (today 14:30, tomorrow 14:30)

        """
        start = self.get_current_interval_start()
        end = start + timedelta(hours=hours)
        return start, end

    def get_next_n_hours_window(self, hours: int) -> tuple[datetime, datetime]:
        """
        Get window for next N hours starting from NEXT interval.

        Args:
            hours: Window size in hours.

        Returns:
            Tuple of (start_time, end_time).
            start_time: next interval start
            end_time: next interval start + hours (exclusive)

        Example:
            Current interval: 14:30
            hours=3 → (14:45, 17:45)

        """
        start = self.get_interval_offset_time(1)  # Next interval
        end = start + timedelta(hours=hours)
        return start, end

    # -------------------------------------------------------------------------
    # Time-Travel Support
    # -------------------------------------------------------------------------

    def with_reference_time(self, new_time: datetime) -> TimeService:
        """
        Create new TimeService with different reference time.

        Used for time-travel testing: inject simulated "now".

        Args:
            new_time: New reference time.

        Returns:
            New TimeService instance with updated reference time.

        Example:
            # Simulate being at 14:30 on 2025-11-19
            simulated_time = datetime(2025, 11, 19, 14, 30)
            future_service = time_service.with_reference_time(simulated_time)

        """
        return TimeService(reference_time=new_time)
