"""Tests for find_level_run_times (cheap_until / next_cheap_start attributes)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.tibber_prices.const import CHEAP_PRICE_LEVELS, EXPENSIVE_PRICE_LEVELS
from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService
from custom_components.tibber_prices.utils.price import find_level_run_times
from homeassistant.util import dt as dt_util

BASE = datetime(2026, 10, 13, 20, 0, tzinfo=dt_util.get_default_time_zone())


def _intervals(levels: list[str]) -> list[dict]:
    """Build consecutive 15-minute intervals starting at BASE with the given levels."""
    return [{"startsAt": BASE + timedelta(minutes=15 * i), "level": level} for i, level in enumerate(levels)]


def _at(index: int) -> datetime:
    return BASE + timedelta(minutes=15 * index)


GROUPS = {"cheap": CHEAP_PRICE_LEVELS, "expensive": EXPENSIVE_PRICE_LEVELS}


@pytest.fixture
def time() -> TibberPricesTimeService:
    return TibberPricesTimeService(reference_time=BASE)


def _runs(intervals: list[dict], current: datetime, time: TibberPricesTimeService, group: str = "cheap") -> tuple:
    return find_level_run_times(intervals, current, GROUPS, time=time)[group]


@pytest.mark.unit
def test_inside_cheap_run_returns_end_and_next_run(time: TibberPricesTimeService) -> None:
    """Current interval cheap: until = end of the run, next = start of the following run."""
    intervals = _intervals(["CHEAP", "VERY_CHEAP", "CHEAP", "NORMAL", "EXPENSIVE", "CHEAP"])

    until, next_start = _runs(intervals, _at(0), time)

    assert until == _at(3)  # run covers intervals 0-2, ends where interval 3 starts
    assert next_start == _at(5)


@pytest.mark.unit
def test_outside_run_has_no_until(time: TibberPricesTimeService) -> None:
    """Current interval not cheap: until is None, next is the first cheap interval ahead."""
    intervals = _intervals(["EXPENSIVE", "NORMAL", "CHEAP", "CHEAP", "NORMAL"])

    until, next_start = _runs(intervals, _at(0), time)

    assert until is None
    assert next_start == _at(2)


@pytest.mark.unit
def test_run_reaching_end_of_data_has_unknown_end(time: TibberPricesTimeService) -> None:
    """A run that lasts until the last known interval has no known end (e.g. tomorrow not published)."""
    intervals = _intervals(["NORMAL", "EXPENSIVE", "VERY_EXPENSIVE"])

    until, next_start = _runs(intervals, _at(1), time, "expensive")

    assert until is None
    assert next_start is None


@pytest.mark.unit
def test_gap_in_data_ends_nothing(time: TibberPricesTimeService) -> None:
    """A missing interval doesn't join two runs, and the run before it has no known end."""
    intervals = _intervals(["CHEAP", "CHEAP", "CHEAP", "CHEAP"])
    del intervals[2]

    until, next_start = _runs(intervals, _at(0), time)

    assert until is None
    assert next_start == _at(3)


@pytest.mark.unit
def test_both_groups_in_one_call(time: TibberPricesTimeService) -> None:
    """Cheap and expensive come from the same timeline."""
    intervals = _intervals(["EXPENSIVE", "EXPENSIVE", "NORMAL", "CHEAP"])

    runs = find_level_run_times(intervals, _at(0), GROUPS, time=time)

    assert runs == {"cheap": (None, _at(3)), "expensive": (_at(2), None)}


@pytest.mark.unit
def test_repeated_hour_at_dst_fall_back(berlin: ZoneInfo) -> None:
    """On the fall-back day the two 02:00 hours stay in real order: CEST first, then CET."""
    first = datetime(2026, 10, 25, 0, 0, tzinfo=UTC)  # 02:00 CEST
    levels = ["CHEAP"] * 4 + ["NORMAL"] * 4  # 02:00-02:45 CEST cheap, 02:00-02:45 CET normal
    intervals = [
        {"startsAt": (first + timedelta(minutes=15 * i)).astimezone(berlin), "level": level}
        for i, level in enumerate(levels)
    ]
    time = TibberPricesTimeService(reference_time=intervals[0]["startsAt"])

    until, next_start = _runs(intervals, intervals[0]["startsAt"], time)

    assert until is not None
    assert dt_util.as_utc(until) == first + timedelta(hours=1)  # 02:00 CET, not 03:00
    assert next_start is None


@pytest.mark.unit
def test_past_runs_are_ignored_and_order_does_not_matter(time: TibberPricesTimeService) -> None:
    """Cheap intervals before the current one never count; input order is irrelevant."""
    intervals = list(reversed(_intervals(["CHEAP", "CHEAP", "NORMAL", "NORMAL"])))

    until, next_start = _runs(intervals, _at(2), time)

    assert until is None
    assert next_start is None


@pytest.mark.unit
def test_current_interval_missing_from_data(time: TibberPricesTimeService) -> None:
    """Without data for the current interval there is no run, only a next start."""
    intervals = _intervals(["NORMAL", "CHEAP"])[1:]

    until, next_start = _runs(intervals, _at(0), time)

    assert until is None
    assert next_start == _at(1)
