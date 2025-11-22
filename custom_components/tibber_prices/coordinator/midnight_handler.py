"""
Midnight turnover detection and coordination handler.

This module provides atomic coordination logic for midnight turnover between
multiple timers (DataUpdateCoordinator and quarter-hour refresh timer).

The handler ensures that midnight turnover happens exactly once per day,
regardless of which timer detects it first.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


class TibberPricesMidnightHandler:
    """
    Handles midnight turnover detection and atomic coordination.

    This class encapsulates the logic for detecting when midnight has passed
    and ensuring that data rotation happens exactly once per day.

    The atomic coordination works without locks by comparing date values:
    - Timer #1 and Timer #2 both check if current_date > last_checked_date
    - First timer to succeed marks the date as checked
    - Second timer sees dates are equal and skips turnover
    - Timer #3 doesn't participate in midnight logic (only 30-second timing updates)

    HA Restart Handling:
    - If HA restarts after midnight, _last_midnight_check is None (fresh handler)
    - But _last_actual_turnover is restored from cache with yesterday's date
    - is_turnover_needed() detects the date mismatch and returns True
    - Missed midnight turnover is caught up on first timer run after restart

    Attributes:
        _last_midnight_check: Last datetime when midnight turnover was checked
        _last_actual_turnover: Last datetime when turnover actually happened

    """

    def __init__(self) -> None:
        """Initialize the midnight handler."""
        self._last_midnight_check: datetime | None = None
        self._last_actual_turnover: datetime | None = None

    def is_turnover_needed(self, now: datetime) -> bool:
        """
        Check if midnight turnover is needed without side effects.

        This is a pure check function - it doesn't modify state. Call
        mark_turnover_done() after successfully performing the turnover.

        IMPORTANT: If handler is uninitialized (HA restart), this checks if we
        need to catch up on midnight turnover that happened while HA was down.

        Args:
            now: Current datetime to check

        Returns:
            True if midnight has passed since last check, False otherwise

        """
        # First time initialization after HA restart
        if self._last_midnight_check is None:
            # Check if we need to catch up on missed midnight turnover
            # If last_actual_turnover exists, we can determine if midnight was missed
            if self._last_actual_turnover is not None:
                last_turnover_date = self._last_actual_turnover.date()
                current_date = now.date()
                # Turnover needed if we're on a different day than last turnover
                return current_date > last_turnover_date
            # Both None = fresh start, no turnover needed yet
            return False

        # Extract date components
        last_checked_date = self._last_midnight_check.date()
        current_date = now.date()

        # Midnight crossed if current date is after last checked date
        return current_date > last_checked_date

    def mark_turnover_done(self, now: datetime) -> None:
        """
        Mark that midnight turnover has been completed.

        Updates both check timestamp and actual turnover timestamp to prevent
        duplicate turnover by another timer.

        Args:
            now: Current datetime when turnover was completed

        """
        self._last_midnight_check = now
        self._last_actual_turnover = now

    def update_check_time(self, now: datetime) -> None:
        """
        Update the last check time without marking turnover as done.

        Used for initializing the handler or updating the check timestamp
        without triggering turnover logic.

        Args:
            now: Current datetime to set as last check time

        """
        if self._last_midnight_check is None:
            self._last_midnight_check = now

    @property
    def last_turnover_time(self) -> datetime | None:
        """Get the timestamp of the last actual turnover."""
        return self._last_actual_turnover

    @property
    def last_check_time(self) -> datetime | None:
        """Get the timestamp of the last midnight check."""
        return self._last_midnight_check
