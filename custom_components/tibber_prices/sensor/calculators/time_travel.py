"""Calculator for time-travel mode and offset sensors."""

from __future__ import annotations

from datetime import datetime

from .base import TibberPricesBaseCalculator


class TibberPricesTimeTravelCalculator(TibberPricesBaseCalculator):
    """
    Calculator for the sensors describing what a device is showing.

    These exist on every device, live or historical. On a live device they
    report "live" and no offsets, which is precisely what someone comparing two
    devices in a chart needs to see - an empty sensor would leave the question
    open.
    """

    def get_entry_mode(self) -> str:
        """Return "live", "time_travel_days" or "time_travel_yearly"."""
        return self.coordinator.time_shift.describe()

    def get_reference_time(self) -> datetime | None:
        """
        Return the moment this device is currently showing.

        On a live device this is real time; on a view it trails real time by the
        configured offset. None while the view has no usable data (an
        unresolvable 29 February), matching the unavailable entities.
        """
        if self.coordinator.is_time_travel and not self.coordinator.last_update_success:
            return None
        return self.coordinator.time.now()

    def get_days_offset(self) -> int | None:
        """Return the day offset, or None outside of days mode."""
        shift = self.coordinator.time_shift
        if shift.is_live or shift.mode != "days":
            return None
        return shift.days

    def get_years_offset(self) -> int | None:
        """Return the year offset, or None outside of yearly mode."""
        shift = self.coordinator.time_shift
        if shift.is_live or shift.mode != "yearly":
            return None
        return shift.years

    def get_time_offset(self) -> str | None:
        """
        Return the fine-tuning offset as "-HH:MM", or None when unset.

        Rendered as a string rather than a duration because it is a signed
        wall-clock adjustment, not a measured quantity.
        """
        shift = self.coordinator.time_shift
        if shift.is_live or not (shift.hours or shift.minutes):
            return None
        return f"-{abs(shift.hours):02d}:{abs(shift.minutes):02d}"

    def get_headless_mode(self) -> str:
        """Return "on" when the device only carries diagnostic sensors."""
        return "on" if self.coordinator.headless else "off"
