"""Tests for aggregate_to_hourly: chart hours are clock hours (:00-:59)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from custom_components.tibber_prices.services.formatters import aggregate_to_hourly
from homeassistant.util import dt as dt_util

BASE = datetime(2026, 10, 13, 5, 0, tzinfo=dt_util.get_default_time_zone())


def _coordinator(display: str) -> SimpleNamespace:
    return SimpleNamespace(config_entry=SimpleNamespace(options={"average_sensor_display": display}))


def _intervals(prices: list[float], start: datetime = BASE) -> list[dict]:
    return [
        {"startsAt": start + timedelta(minutes=15 * i), "total": price, "level": "NORMAL", "rating_level": "NORMAL"}
        for i, price in enumerate(prices)
    ]


@pytest.mark.unit
def test_each_hour_uses_only_its_own_intervals() -> None:
    """05:00 averages 05:00-05:45 only; the steep rise at 06:00 must not leak into it."""
    intervals = _intervals([1.0, 1.0, 1.0, 1.0, 3.0, 3.0, 3.0, 3.0])

    hourly = aggregate_to_hourly(intervals, _coordinator("mean"))

    assert [(h["startsAt"].hour, h["total"]) for h in hourly] == [(5, 1.0), (6, 3.0)]


@pytest.mark.unit
def test_median_setting_is_respected() -> None:
    """With median display, the hour value is the median of its four intervals."""
    intervals = _intervals([1.0, 2.0, 3.0, 10.0])

    assert aggregate_to_hourly(intervals, _coordinator("median"))[0]["total"] == 2.5
    assert aggregate_to_hourly(intervals, _coordinator("mean"))[0]["total"] == 4.0


@pytest.mark.unit
def test_partial_hour_at_data_edge() -> None:
    """Data starting at 05:30 gives a 05:00 point from the two available intervals."""
    intervals = _intervals([2.0, 4.0, 5.0, 5.0, 5.0, 5.0], start=BASE + timedelta(minutes=30))

    hourly = aggregate_to_hourly(intervals, _coordinator("mean"))

    assert [(h["startsAt"].strftime("%H:%M"), h["total"]) for h in hourly] == [("05:00", 3.0), ("06:00", 5.0)]


@pytest.mark.unit
def test_repeated_hour_at_dst_fall_back_stays_two_hours() -> None:
    """On 2026-10-25 (Berlin) 02:00 exists twice; each gets its own point, 25 in total over the day."""
    berlin = ZoneInfo("Europe/Berlin")
    midnight = datetime(2026, 10, 24, 22, 0, tzinfo=UTC)  # 00:00 CEST
    intervals = [
        {"startsAt": (midnight + timedelta(minutes=15 * i)).astimezone(berlin), "total": float(i // 4)}
        for i in range(25 * 4)
    ]

    hourly = aggregate_to_hourly(intervals, _coordinator("mean"))

    assert len(hourly) == 25
    second, third = hourly[2], hourly[3]
    assert (second["startsAt"].hour, third["startsAt"].hour) == (2, 2)
    assert (second["total"], third["total"]) == (2.0, 3.0)  # own intervals only, not 8 mixed


@pytest.mark.unit
def test_chart_timestamps_keep_both_fall_back_hours() -> None:
    """get_chartdata's timestamp list keeps the two 02:00 hours apart (a set of local times merges them)."""
    from custom_components.tibber_prices.services.get_chartdata import _unique_timestamps  # noqa: PLC0415

    berlin = ZoneInfo("Europe/Berlin")
    first = datetime(2026, 10, 25, 0, 0, tzinfo=UTC)  # 02:00 CEST
    starts = [(first + timedelta(hours=h)).astimezone(berlin) for h in (1, 0, 1)]  # unordered, one duplicate

    result = _unique_timestamps([{"startsAt": start} for start in starts])

    assert [dt_util.as_utc(start) for start in result] == [first, first + timedelta(hours=1)]
