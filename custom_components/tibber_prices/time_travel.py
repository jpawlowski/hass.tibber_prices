"""
Time-travel subentries - shared helpers.

A time-travel view is a `ConfigSubentry` of a home's config entry. It shows the
same home's prices as they were at a point in the past, with the clock still
advancing normally: only the reference date is shifted.

Two offset modes:

* **days** - a fixed shift, e.g. "7 days ago". The offset is constant.
* **yearly** - the same month and day in an earlier year, e.g. "last year". The
  offset is *not* constant (leap years, DST), so it is resolved fresh against
  real time on every update cycle.

Everything downstream of the shifted clock follows automatically:

* The coordinator builds every `TibberPricesTimeService` from the resolved
  reference, so "now", "today" and "tomorrow" all refer to the shifted date.
* The IntervalPool fetches and protects the shifted 4-day window instead of the
  live one, which is why each view needs its own pool (see
  `_async_create_interval_pool` in `__init__.py`).
* Entities, devices and storage keys are scoped with the subentry ID so a view
  never collides with its parent entry.

Two things make a view unavailable rather than wrong, and both are deliberate -
faking data would silently corrupt comparisons:

* **Before the resolution change.** Tibber switched from hourly to
  quarter-hourly prices on 2025-10-01 (`QUARTER_HOURLY_SINCE`). This
  integration's logic is built for 15-minute intervals, so earlier dates cannot
  be interpreted. Yearly mode therefore stays unusable until one full year of
  quarter-hourly data exists.
* **Leap days.** In yearly mode, 29 February has no counterpart in a non-leap
  target year. The view reports unavailable instead of sliding to 1 March.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal

from .const import (
    CONF_HEADLESS,
    CONF_REALISTIC_TOMORROW,
    CONF_TOMORROW_ARRIVAL_HOUR,
    CONF_VIRTUAL_TIME_OFFSET_DAYS,
    CONF_VIRTUAL_TIME_OFFSET_HOURS,
    CONF_VIRTUAL_TIME_OFFSET_MINUTES,
    CONF_VIRTUAL_TIME_OFFSET_MODE,
    CONF_VIRTUAL_TIME_OFFSET_YEARS,
    DEFAULT_HEADLESS,
    DEFAULT_REALISTIC_TOMORROW,
    DEFAULT_TOMORROW_ARRIVAL_HOUR,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from homeassistant.config_entries import ConfigEntry, ConfigSubentry

# Subentry type key. Must match the `config_subentries.<type>` key in the
# translation files and the key returned by async_get_supported_subentry_types().
SUBENTRY_TYPE_TIME_TRAVEL = "time_travel"

OffsetMode = Literal["days", "yearly"]

MODE_DAYS: OffsetMode = "days"
MODE_YEARLY: OffsetMode = "yearly"

# Tibber switched from hourly to quarter-hourly prices on this date. Everything
# before it is unusable for this integration's 15-minute logic.
QUARTER_HOURLY_SINCE = date(2025, 10, 1)

# Slider bounds for the day offset (one year + one week, matching the range
# get_intervals_for_day_offsets() accepts).
MAX_OFFSET_DAYS = 374

# Yearly mode never goes further back than this many years.
MAX_OFFSET_YEARS = 5

# A view needs the two days before its reference date for trailing averages, so
# the reference must sit at least this far after the resolution change.
_TRAILING_DAYS_NEEDED = 2


@dataclass(frozen=True)
class TimeShift:
    """
    The clock shift of a time-travel view.

    Resolved against real time on every update cycle rather than stored as a
    fixed timedelta: in yearly mode the distance to the target date changes with
    leap years, and in both modes a DST boundary between now and the target
    would otherwise skew the wall-clock time.
    """

    mode: OffsetMode = MODE_DAYS
    days: int = 0
    years: int = 0
    hours: int = 0
    minutes: int = 0

    @property
    def is_live(self) -> bool:
        """Return True if this shift does not move the clock at all."""
        if self.mode == MODE_YEARLY:
            return not (self.years or self.hours or self.minutes)
        return not (self.days or self.hours or self.minutes)

    def resolve(self, real_now: datetime) -> datetime | None:
        """
        Return the shifted "now" for a given real time.

        Args:
            real_now: Timezone-aware real current time.

        Returns:
            The shifted datetime, or None when the target does not exist - a
            29 February that the target year does not have. Callers must treat
            None as "unavailable" and must not substitute a nearby date.

        """
        if self.is_live:
            return real_now

        target = self.target_date(real_now.date())
        if target is None:
            return None

        shifted = real_now.replace(year=target.year, month=target.month, day=target.day)
        return shifted + timedelta(hours=self.hours, minutes=self.minutes)

    def has_data_coverage(self, real_now: datetime) -> bool:
        """
        Return True if the shifted window lies in the quarter-hourly era.

        The view also needs the two days before its reference date for trailing
        averages, so a reference sitting exactly on the resolution change is not
        enough.
        """
        shifted = self.resolve(real_now)
        if shifted is None:
            return False
        return shifted.date() - timedelta(days=_TRAILING_DAYS_NEEDED) >= QUARTER_HOURLY_SINCE

    def target_date(self, today: date) -> date | None:
        """Return the shifted calendar date, or None if it does not exist."""
        if self.mode == MODE_YEARLY:
            try:
                return today.replace(year=today.year + self.years)
            except ValueError:
                # 29 February in a non-leap target year. Sliding to 1 March would
                # compare against the wrong day, so the view goes unavailable.
                return None
        return today + timedelta(days=self.days)

    def describe(self) -> str:
        """Return a stable machine-readable mode description for diagnostics."""
        if self.is_live:
            return "live"
        return f"time_travel_{self.mode}"


def get_time_shift(subentry: ConfigSubentry | None) -> TimeShift:
    """
    Read the clock shift configured for a subentry.

    Args:
        subentry: The time-travel subentry, or None for the live config entry.

    Returns:
        The configured shift; a live (zero) shift when there is no subentry.

    """
    if subentry is None:
        return TimeShift()
    return build_time_shift(subentry.data)


def build_time_shift(data: Mapping[str, Any]) -> TimeShift:
    """
    Build a normalized shift from subentry data.

    Components are forced non-positive: the config flow stores negative values,
    but hand-edited or partially migrated storage must not be able to shift the
    clock into the future - there is no price data there to show.
    """
    mode: OffsetMode = MODE_YEARLY if data.get(CONF_VIRTUAL_TIME_OFFSET_MODE) == MODE_YEARLY else MODE_DAYS
    return TimeShift(
        mode=mode,
        days=-abs(int(data.get(CONF_VIRTUAL_TIME_OFFSET_DAYS, 0) or 0)),
        years=-abs(int(data.get(CONF_VIRTUAL_TIME_OFFSET_YEARS, 0) or 0)),
        hours=-abs(int(data.get(CONF_VIRTUAL_TIME_OFFSET_HOURS, 0) or 0)),
        minutes=-abs(int(data.get(CONF_VIRTUAL_TIME_OFFSET_MINUTES, 0) or 0)),
    )


def max_selectable_days(today: date) -> int:
    """
    Return the largest day offset that still has quarter-hourly data.

    The slider shrinks the range instead of letting users pick a date the
    integration would only be able to report as unavailable. Grows by one per
    day until it reaches MAX_OFFSET_DAYS.
    """
    available = (today - QUARTER_HOURLY_SINCE).days - _TRAILING_DAYS_NEEDED
    return max(0, min(MAX_OFFSET_DAYS, available))


def max_selectable_years(today: date) -> int:
    """
    Return the largest year offset that still has quarter-hourly data.

    Zero until one full year of quarter-hourly data exists (2026-10-03, given
    the two trailing days each view needs), which is when yearly mode becomes
    usable at all.
    """
    for years in range(1, MAX_OFFSET_YEARS + 1):
        shift = TimeShift(mode=MODE_YEARLY, years=-years)
        target = shift.target_date(today)
        if target is None or target - timedelta(days=_TRAILING_DAYS_NEEDED) < QUARTER_HOURLY_SINCE:
            return years - 1
    return MAX_OFFSET_YEARS


def is_headless(subentry: ConfigSubentry | None) -> bool:
    """Return True if the view exposes diagnostic sensors only."""
    if subentry is None:
        return False
    return bool(subentry.data.get(CONF_HEADLESS, DEFAULT_HEADLESS))


def uses_realistic_tomorrow(subentry: ConfigSubentry | None) -> bool:
    """Return True if the view withholds tomorrow's prices until the arrival hour."""
    if subentry is None:
        return False
    return bool(subentry.data.get(CONF_REALISTIC_TOMORROW, DEFAULT_REALISTIC_TOMORROW))


def tomorrow_arrival_hour(subentry: ConfigSubentry | None) -> int:
    """Return the local hour at which a view starts showing tomorrow's prices."""
    if subentry is None:
        return DEFAULT_TOMORROW_ARRIVAL_HOUR
    raw = subentry.data.get(CONF_TOMORROW_ARRIVAL_HOUR, DEFAULT_TOMORROW_ARRIVAL_HOUR)
    try:
        hour = int(raw)
    except TypeError, ValueError:
        return DEFAULT_TOMORROW_ARRIVAL_HOUR
    return min(23, max(0, hour))


def is_time_travel_subentry(subentry: ConfigSubentry) -> bool:
    """Return True if the subentry is a time-travel view of its parent entry."""
    return subentry.subentry_type == SUBENTRY_TYPE_TIME_TRAVEL


def iter_time_travel_subentries(entry: ConfigEntry) -> Iterator[ConfigSubentry]:
    """
    Yield the time-travel subentries of a config entry, in a stable order.

    Ordering by subentry ID keeps entity creation deterministic across restarts.
    """
    for subentry in sorted(entry.subentries.values(), key=lambda s: s.subentry_id):
        if is_time_travel_subentry(subentry):
            yield subentry


def subentry_storage_id(entry_id: str, subentry: ConfigSubentry | None) -> str:
    """
    Return the storage identifier for a coordinator's interval pool.

    The live coordinator keeps the plain entry ID so existing pool storage stays
    valid; each time-travel view gets its own suffixed store.
    """
    if subentry is None:
        return entry_id
    return f"{entry_id}_{subentry.subentry_id}"
