"""Tests for the clock_hour_* attributes of the rolling hour price sensors."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService
from custom_components.tibber_prices.sensor.attributes.interval import _add_clock_hour_attributes
from homeassistant.util import dt as dt_util

CONFIG_ENTRY = SimpleNamespace(options={"currency_display_mode": "base", "average_sensor_display": "mean"})


@pytest.mark.unit
def test_repeated_hour_at_dst_fall_back_uses_only_its_own_intervals(berlin: ZoneInfo) -> None:
    """At 02:10 CET on the fall-back day the clock hour is 02:00-03:00 CET, not both 02:00 hours."""
    first = datetime(2026, 10, 25, 0, 0, tzinfo=UTC)  # 02:00 CEST
    prices = [1.0] * 4 + [3.0] * 4  # 02:xx CEST, then 02:xx CET
    intervals = [
        {"startsAt": (first + timedelta(minutes=15 * i)).astimezone(berlin), "total": price}
        for i, price in enumerate(prices)
    ]
    now = (first + timedelta(hours=1, minutes=10)).astimezone(berlin)  # 02:10 CET
    attributes: dict = {}

    _add_clock_hour_attributes(
        attributes,
        intervals,
        0,
        time=TibberPricesTimeService(reference_time=now),
        config_entry=CONFIG_ENTRY,  # type: ignore[arg-type]
    )

    assert attributes["clock_hour_price_mean"] == 3.0
    assert dt_util.parse_datetime(attributes["clock_hour_start"]) == first + timedelta(hours=1)
    assert dt_util.parse_datetime(attributes["clock_hour_end"]) == first + timedelta(hours=2)
