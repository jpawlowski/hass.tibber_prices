"""Tests for get_rolling_hour_window (rolling hour values and window_start/window_end)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService
from custom_components.tibber_prices.entity_utils import get_rolling_hour_window
from homeassistant.util import dt as dt_util

BASE = datetime(2026, 10, 13, 12, 0, tzinfo=dt_util.get_default_time_zone())
INTERVALS = [{"startsAt": BASE + timedelta(minutes=15 * i), "total": float(i)} for i in range(16)]  # 12:00-16:00


def _starts(window: list[dict]) -> list[str]:
    return [interval["startsAt"].strftime("%H:%M") for interval in window]


@pytest.fixture
def time() -> TibberPricesTimeService:
    return TibberPricesTimeService(reference_time=BASE)


@pytest.mark.unit
def test_current_hour_is_centered_on_current_interval(time: TibberPricesTimeService) -> None:
    """At 13:20 (interval 13:15) the window is 12:45-14:00: 30 min back, current, 30 min ahead."""
    window = get_rolling_hour_window(INTERVALS, BASE.replace(hour=13, minute=20), 0, time=time)

    assert _starts(window) == ["12:45", "13:00", "13:15", "13:30", "13:45"]


@pytest.mark.unit
def test_next_hour_shifts_center_by_four_intervals(time: TibberPricesTimeService) -> None:
    """Next hour moves the center one hour ahead (14:15): window 13:45-15:00."""
    window = get_rolling_hour_window(INTERVALS, BASE.replace(hour=13, minute=20), 1, time=time)

    assert _starts(window) == ["13:45", "14:00", "14:15", "14:30", "14:45"]


@pytest.mark.unit
def test_window_is_cut_at_data_edges(time: TibberPricesTimeService) -> None:
    """At the first known interval only the current and the following two remain."""
    window = get_rolling_hour_window(INTERVALS, BASE, 0, time=time)

    assert _starts(window) == ["12:00", "12:15", "12:30"]


@pytest.mark.unit
def test_unknown_current_interval_gives_empty_window(time: TibberPricesTimeService) -> None:
    """Without data for the current interval there is no window."""
    assert get_rolling_hour_window(INTERVALS, BASE - timedelta(hours=1), 0, time=time) == []


@pytest.mark.unit
def test_next_hour_beyond_data_gives_empty_window(time: TibberPricesTimeService) -> None:
    """Shortly before the data ends, the next hour has no center: no window, not the current hour's tail."""
    last = INTERVALS[-1]["startsAt"]

    assert get_rolling_hour_window(INTERVALS, last, 1, time=time) == []


@pytest.mark.unit
def test_repeated_hour_at_dst_fall_back_centers_on_the_right_copy(berlin: ZoneInfo) -> None:
    """At 02:20 CET on the fall-back day the window centers on the second 02:15, not the first."""
    first = datetime(2026, 10, 25, 0, 0, tzinfo=UTC)  # 02:00 CEST
    intervals = [{"startsAt": (first + timedelta(minutes=15 * i)).astimezone(berlin)} for i in range(16)]
    now = (first + timedelta(hours=1, minutes=20)).astimezone(berlin)  # 02:20 CET

    window = get_rolling_hour_window(intervals, now, 0, time=TibberPricesTimeService(reference_time=now))

    assert [dt_util.as_utc(interval["startsAt"]) for interval in window] == [
        first + timedelta(minutes=15 * i) for i in range(3, 8)
    ]
