"""
Price outlook in the shape of a weather forecast: the coming clock hours, and the parts of the day.

All are views on the same interval prices, grouped differently:
- hours: clock hours (:00-:59), always 48 of them as far as prices are known: at least one hour
  back, everything ahead up to the end of the known prices, and before that as much of the past
  as fills the 48 (yesterday's while tomorrow's prices aren't out). Cards show it from one hour
  back, like the hourly strip of a weather forecast, and can scroll back
- day parts: blocks that follow the daily routine instead of the calendar, from the part
  before the one running now onwards (like the hours, a little look back). Night crosses
  midnight (22-06), so "tonight" is one block
- days: today and, once its prices are complete, tomorrow, as calendar days

The functions only group intervals; averaging and level aggregation happen where the
display unit is known (sensor attributes).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from itertools import pairwise
from typing import TYPE_CHECKING, Any, NamedTuple

from custom_components.tibber_prices.utils.average import clock_hour_bounds, clock_hour_key

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

# Start hour of each part of the day, in daily order; a part lasts until the next one starts.
# Follows the daily load curve in Europe: morning peak, daytime (often solar), evening peak, night
DAY_PARTS: tuple[tuple[str, int], ...] = (("morning", 6), ("day", 9), ("evening", 17), ("night", 22))

# The same as {part: [start hour, end hour]}, for the sensor attribute (cards read it from there)
DAY_PART_HOURS: dict[str, list[int]] = {
    name: [hour, DAY_PARTS[(index + 1) % len(DAY_PARTS)][1]] for index, (name, hour) in enumerate(DAY_PARTS)
}

OUTLOOK_HOURS_BACK = 1  # At least this many hours before the current one
OUTLOOK_HOURS_WINDOW = 48  # Hours in all, the past filling up what the future leaves
# Up to the end of the known prices (at most the end of tomorrow), so tomorrow's low and high
# are always in the strip while ahead; wide cards show more hours, narrow ones scroll
OUTLOOK_HOURS_AHEAD = 47
MIN_PARTIAL_DAY_PART = timedelta(hours=1)  # Shorter rests of a day part aren't shown
OUTLOOK_DAY_PART_COUNT = 8  # Up to the end of tomorrow, e.g. evening, night, ..., evening, night
OUTLOOK_DAY_PARTS_BACK = 1  # The part before the running one (cards show it while tomorrow is unknown)


# known_starts() not passed in: the builder works it out (pass it when building several outlooks
# from the same prices, so they're sorted once)
_WORK_OUT: Any = object()


class TibberPricesOutlookBlock(NamedTuple):
    """A span of time with the price intervals that start in it."""

    start: datetime
    end: datetime
    intervals: list[dict[str, Any]]
    part: str | None = None  # day part name, None for clock hours
    complete: bool = True  # False: the last day part, cut off where the known prices end


def build_hour_outlook(
    intervals: Sequence[dict[str, Any]],
    now: datetime,
    interval_time: Callable[[dict[str, Any]], datetime | None],
    *,
    hours_back: int = OUTLOOK_HOURS_BACK,
    hours_ahead: int = OUTLOOK_HOURS_AHEAD,
    window: int = OUTLOOK_HOURS_WINDOW,
) -> list[TibberPricesOutlookBlock]:
    """
    Group intervals into the clock hours around now: `window` hours where the prices allow.

    The hours ahead (up to `hours_ahead`) come first; at least `hours_back` hours before the
    current one, and more of the past as far as needed to fill the window. Hours without any
    price are left out (edge of the data).

    Args:
        intervals: Price intervals, any order
        now: Reference time (the current interval start)
        interval_time: Returns an interval's start time
        hours_back: Clock hours before the current one, at least
        hours_ahead: Clock hours after the current one, at most
        window: Hours in all, as far as there are prices

    """
    by_hour: dict[datetime, list[dict[str, Any]]] = {}
    for interval in intervals:
        if (start := interval_time(interval)) is not None:
            by_hour.setdefault(clock_hour_key(start), []).append(interval)

    blocks = []
    current = None
    for offset in range(-max(hours_back, window - 1), hours_ahead + 1):
        start, end = clock_hour_bounds(now, offset)
        if hour_intervals := by_hour.get(clock_hour_key(start)):
            if offset == 0:
                current = len(blocks)
            blocks.append(TibberPricesOutlookBlock(start, end, hour_intervals))
    if current is None:  # No price for the hour running now: as far as known around it
        return blocks[-window:]
    # The past fills what the future leaves of the window, but never less than hours_back (the
    # future is never cut: shortly after midnight that makes one hour more)
    back = max(hours_back, window - (len(blocks) - current))
    return blocks[max(0, current - back) :]


def build_day_part_outlook(
    intervals: Sequence[dict[str, Any]],
    now: datetime,
    interval_time: Callable[[dict[str, Any]], datetime | None],
    *,
    count: int = OUTLOOK_DAY_PART_COUNT,
    parts_back: int = OUTLOOK_DAY_PARTS_BACK,
    since: datetime | None = None,
    known: Any = _WORK_OUT,
) -> list[TibberPricesOutlookBlock]:
    """
    Group intervals into the parts of the day, from some before the running one on.

    The list starts `parts_back` parts before the running one, or earlier with `since`: at the
    part that time falls into (so the parts cover what the hours do). A part whose beginning
    lies before the known prices is left out: its numbers would cover only some of it. The
    part where the known prices end is included as far as it is known (at least an hour), with
    complete=False: its average covers only that stretch, which consumers must make clear (an
    average over two hours of a night is not the night's).

    Args:
        intervals: Price intervals, any order
        now: Reference time, timezone-aware in the home's timezone
        interval_time: Returns an interval's start time
        count: Maximum number of parts from the running one on
        parts_back: Parts before the running one, at least (left out where no prices are known)
        since: Start the list at the part this time falls into, if that's earlier
        known: known_starts() of the intervals, if already worked out

    """
    if known is _WORK_OUT:
        known = known_starts(intervals, interval_time)
    if known is None:
        return []
    starts, data_end = known
    data_start = starts[0][0]

    running_start, part = _day_part_at(now)
    part_start = running_start
    for _ in range(parts_back):
        part_start, part = _previous_day_part(part_start, part)
    if since is not None:
        since_start, since_part = _day_part_at(since)
        if since_start.astimezone(UTC) < part_start.astimezone(UTC):
            part_start, part = since_start, since_part

    blocks = []
    ahead = 0  # Parts from the running one on
    while ahead < count:
        part_end, next_part = _next_day_part(part_start, part)
        lo, hi = part_start.astimezone(UTC), part_end.astimezone(UTC)
        if data_end < hi:
            # Where the prices end: the part as far as known, marked incomplete, if at least an
            # hour of it is known (e.g. tonight until midnight before tomorrow's prices arrive)
            if data_end - lo >= MIN_PARTIAL_DAY_PART:
                known_part = [interval for start, interval in starts if lo <= start < data_end]
                end = data_end.astimezone(part_start.tzinfo)
                blocks.append(TibberPricesOutlookBlock(part_start, end, known_part, part, complete=False))
            break
        part_intervals = [interval for start, interval in starts if lo <= start < hi]
        if lo >= data_start and part_intervals:
            blocks.append(TibberPricesOutlookBlock(part_start, part_end, part_intervals, part))
            if lo >= running_start.astimezone(UTC):
                ahead += 1
        part_start, part = part_end, next_part
    return blocks


def build_day_outlook(
    intervals: Sequence[dict[str, Any]],
    now: datetime,
    interval_time: Callable[[dict[str, Any]], datetime | None],
    *,
    known: Any = _WORK_OUT,
) -> list[TibberPricesOutlookBlock]:
    """
    Group intervals into today and tomorrow (calendar days, midnight to midnight).

    Like the day parts, a day is only included while its prices are complete, so tomorrow
    appears once its prices are published.

    Args:
        intervals: Price intervals, any order
        now: Reference time, timezone-aware in the home's timezone
        interval_time: Returns an interval's start time
        known: known_starts() of the intervals, if already worked out

    """
    if known is _WORK_OUT:
        known = known_starts(intervals, interval_time)
    if known is None:
        return []
    starts, data_end = known

    blocks = []
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    for _ in range(2):
        # Wall-clock midnight of the next day (23 or 25 hours on clock change days)
        day_end = (day_start + timedelta(days=1)).replace(hour=0)
        lo, hi = day_start.astimezone(UTC), day_end.astimezone(UTC)
        if data_end < hi:
            break
        if day_intervals := [interval for start, interval in starts if lo <= start < hi]:
            blocks.append(TibberPricesOutlookBlock(day_start, day_end, day_intervals))
        day_start = day_end
    return blocks


def known_starts(
    intervals: Sequence[dict[str, Any]],
    interval_time: Callable[[dict[str, Any]], datetime | None],
) -> tuple[list[tuple[datetime, dict[str, Any]]], datetime] | None:
    """
    Return the priced intervals sorted by start, as (UTC start, interval), and where they end (None without any).

    Only intervals with a price count as known: a day or part of the day without one is no
    day yet. In UTC: local times with the same tzinfo compare by wall clock, so the repeated
    hour when clocks go back would collide. The end is the last start plus one interval length:
    the shortest step between two starts (a quarter hour missing at the end would make the last
    step longer, and the data seem to reach further than it does).
    """
    starts = sorted(
        (
            (start.astimezone(UTC), interval)
            for interval in intervals
            if "total" in interval and (start := interval_time(interval)) is not None
        ),
        key=lambda item: item[0],
    )
    if not starts:
        return None
    steps = [b[0] - a[0] for a, b in pairwise(starts) if b[0] > a[0]]
    step = min(steps) if steps else timedelta(minutes=15)
    return starts, starts[-1][0] + step


def _day_part_at(moment: datetime) -> tuple[datetime, str]:
    """Return start and name of the day part `moment` falls into."""
    for name, hour in reversed(DAY_PARTS):
        if moment.hour >= hour:
            return moment.replace(hour=hour, minute=0, second=0, microsecond=0), name
    # Before the first part of the day: still last night, which began the evening before
    name, hour = DAY_PARTS[-1]
    return (moment - timedelta(days=1)).replace(hour=hour, minute=0, second=0, microsecond=0), name


def _previous_day_part(part_start: datetime, part: str) -> tuple[datetime, str]:
    """Return start and name of the part before `part`, which began at `part_start`."""
    names = [name for name, _ in DAY_PARTS]
    previous_name, previous_hour = DAY_PARTS[(names.index(part) - 1) % len(DAY_PARTS)]
    day = part_start - timedelta(days=1) if previous_hour >= part_start.hour else part_start
    return day.replace(hour=previous_hour), previous_name


def _next_day_part(part_start: datetime, part: str) -> tuple[datetime, str]:
    """Return start and name of the part after `part`, which began at `part_start`."""
    names = [name for name, _ in DAY_PARTS]
    next_name, next_hour = DAY_PARTS[(names.index(part) + 1) % len(DAY_PARTS)]
    day = part_start + timedelta(days=1) if next_hour <= part_start.hour else part_start
    return day.replace(hour=next_hour), next_name
