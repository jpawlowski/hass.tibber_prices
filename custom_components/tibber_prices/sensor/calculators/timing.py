"""
Timing calculator for best/peak price period timing sensors.

This module handles all timing-related calculations for period-based sensors:
- Period end times (when does current/next period end?)
- Period start times (when does next period start?)
- Remaining minutes (how long until period ends?)
- Progress (how far through the period are we?)
- Next period timing (when does the next period start?)

The calculator provides smart defaults:
- Active period → show current period timing
    - No active → show next period timing
    - No more periods → 0 for numeric values, None for timestamps
"""

from datetime import datetime

from .base import TibberPricesBaseCalculator  # Constants

PROGRESS_GRACE_PERIOD_SECONDS = 60  # Show 100% for 1 minute after period ends


class TibberPricesTimingCalculator(TibberPricesBaseCalculator):
    """
    Calculator for period timing sensors.

    Handles timing information for best_price and peak_price periods:
    - Active period timing (end time, remaining minutes, progress)
    - Next period timing (start time, minutes until start)
    - Period duration (total length in minutes)

    Period states:
    - ACTIVE: A period is currently running
    - GRACE: Period just ended (within 60s), still showing 100% progress
    - IDLE: No active period, waiting for next one
    """

    def get_period_timing_value(
        self,
        *,
        period_type: str,
        value_type: str,
    ) -> datetime | float | None:
        """
        Get timing-related values for best_price/peak_price periods.

        This method provides timing information based on whether a period is currently
        active or not, ensuring sensors always provide useful information.

        Value types behavior:
        - end_time: Active period → current end | No active → next period end | None if no periods
        - next_start_time: Active period → next-next start | No active → next start | None if no more
        - remaining_minutes: Active period → minutes to end | No active → 0
        - progress: Active period → 0-100% | No active → 0
        - next_in_minutes: Active period → minutes to next-next | No active → minutes to next | None if no more

        Args:
            period_type: "best_price" or "peak_price"
            value_type: "end_time", "remaining_minutes", "progress", "next_start_time", "next_in_minutes"

        Returns:
            - datetime for end_time/next_start_time
            - float for remaining_minutes/next_in_minutes/progress (or 0 when not active)
            - None if no relevant period data available

        """
        if not self.coordinator.data:
            return None

        # Get period data from coordinator
        periods_data = self.coordinator.data.get("periods", {})
        period_data = periods_data.get(period_type)

        if not period_data or not period_data.get("periods"):
            # No periods available - return 0 for numeric sensors, None for timestamps
            return 0 if value_type in ("remaining_minutes", "progress", "next_in_minutes") else None

        period_summaries = period_data["periods"]
        time = self.coordinator.time
        now = time.now()

        # Find current, previous and next periods
        current_period = self._find_active_period(period_summaries)
        previous_period = self._find_previous_period(period_summaries)
        next_period = self._find_next_period(period_summaries, skip_current=bool(current_period))

        # Delegate to specific calculators
        return self._calculate_timing_value(value_type, current_period, previous_period, next_period, now)

    def _calculate_timing_value(
        self,
        value_type: str,
        current_period: dict | None,
        previous_period: dict | None,
        next_period: dict | None,
        now: datetime,
    ) -> datetime | float | None:
        """Calculate specific timing value based on type and available periods."""
        # Define calculation strategies for each value type
        calculators = {
            "end_time": lambda: (
                current_period.get("end") if current_period else (next_period.get("end") if next_period else None)
            ),
            "period_duration": lambda: self._calc_period_duration(current_period, next_period),
            "next_start_time": lambda: next_period.get("start") if next_period else None,
            "remaining_minutes": lambda: (self._calc_remaining_minutes(current_period) if current_period else 0),
            "progress": lambda: self._calc_progress_with_grace_period(current_period, previous_period, now),
            "next_in_minutes": lambda: (self._calc_next_in_minutes(next_period) if next_period else None),
        }

        calculator = calculators.get(value_type)
        return calculator() if calculator else None

    def _find_active_period(self, periods: list) -> dict | None:
        """
        Find currently active period.

        Args:
            periods: List of period dictionaries

        Returns:
            Currently active period or None

        """
        time = self.coordinator.time
        for period in periods:
            start = period.get("start")
            end = period.get("end")
            if start and end and time.is_current_interval(start, end):
                return period
        return None

    def _find_previous_period(self, periods: list) -> dict | None:
        """
        Find the most recent period that has already ended.

        Args:
            periods: List of period dictionaries

        Returns:
            Most recent past period or None

        """
        time = self.coordinator.time
        past_periods = [p for p in periods if p.get("end") and time.is_in_past(p["end"])]

        if not past_periods:
            return None

        # Sort by end time descending to get the most recent one
        past_periods.sort(key=lambda p: p["end"], reverse=True)
        return past_periods[0]

    def _find_next_period(self, periods: list, *, skip_current: bool = False) -> dict | None:
        """
        Find next future period.

        Args:
            periods: List of period dictionaries
            skip_current: If True, try to skip the first future period (to get next-next)
                         If only one future period exists, return it anyway (pragmatic fallback)

        Returns:
            Next period dict or None if no future periods

        """
        time = self.coordinator.time
        future_periods = [p for p in periods if p.get("start") and time.is_in_future(p["start"])]

        if not future_periods:
            return None

        # Sort by start time to ensure correct order
        future_periods.sort(key=lambda p: p["start"])

        # If skip_current requested and we have multiple periods, return second
        # If only one period left, return it anyway (pragmatic: better than showing unknown)
        if skip_current and len(future_periods) > 1:
            return future_periods[1]

        # Default: return first future period
        return future_periods[0] if future_periods else None

        return None

    def _calc_remaining_minutes(self, period: dict) -> int:
        """
        Calculate ROUNDED minutes until period ends.

        Uses standard rounding (0.5 rounds up) to match Home Assistant frontend
        relative time display. This ensures sensor values match what users see
        in the UI ("in X minutes").

        Args:
            period: Period dictionary

        Returns:
            Rounded minutes until period ends (matches HA frontend display)

        """
        time = self.coordinator.time
        end = period.get("end")
        if not end:
            return 0
        return time.minutes_until_rounded(end)

    def _calc_next_in_minutes(self, period: dict) -> int:
        """
        Calculate ROUNDED minutes until next period starts.

        Uses standard rounding (0.5 rounds up) to match Home Assistant frontend
        relative time display. This ensures sensor values match what users see
        in the UI ("in X minutes").

        Args:
            period: Period dictionary

        Returns:
            Rounded minutes until period starts (matches HA frontend display)

        """
        time = self.coordinator.time
        start = period.get("start")
        if not start:
            return 0
        return time.minutes_until_rounded(start)

    def _calc_period_duration(self, current_period: dict | None, next_period: dict | None) -> float | None:
        """
        Calculate total duration of active or next period in minutes.

        Returns duration of current period if active, otherwise duration of next period.
        This gives users a consistent view of period length regardless of timing.

        Args:
            current_period: Currently active period (if any)
            next_period: Next upcoming period (if any)

        Returns:
            Duration in minutes, or None if no periods available

        """
        period = current_period or next_period
        if not period:
            return None

        start = period.get("start")
        end = period.get("end")
        if not start or not end:
            return None

        duration = (end - start).total_seconds() / 60
        return max(0, duration)

    def _calc_progress(self, period: dict, now: datetime) -> float:
        """Calculate progress percentage (0-100) of current period."""
        start = period.get("start")
        end = period.get("end")
        if not start or not end:
            return 0
        total_duration = (end - start).total_seconds()
        if total_duration <= 0:
            return 0
        elapsed = (now - start).total_seconds()
        progress = (elapsed / total_duration) * 100
        return min(100, max(0, progress))

    def _calc_progress_with_grace_period(
        self, current_period: dict | None, previous_period: dict | None, now: datetime
    ) -> float:
        """
        Calculate progress with grace period after period end.

        Shows 100% for 1 minute after period ends to allow triggers on 100% completion.
        This prevents the progress from jumping directly from ~99% to 0% without ever
        reaching 100%, which would make automations like "when progress = 100%" impossible.
        """
        # If we have an active period, calculate normal progress
        if current_period:
            return self._calc_progress(current_period, now)

        # No active period - check if we just finished one (within grace period)
        if previous_period:
            previous_end = previous_period.get("end")
            if previous_end:
                seconds_since_end = (now - previous_end).total_seconds()
                # Grace period: Show 100% for defined time after period ended
                if 0 <= seconds_since_end <= PROGRESS_GRACE_PERIOD_SECONDS:
                    return 100

        # No active period and either no previous period or grace period expired
        return 0
