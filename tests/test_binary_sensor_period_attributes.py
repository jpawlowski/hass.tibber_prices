"""Regression tests for visible best/peak period binary sensor attributes."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from custom_components.tibber_prices.binary_sensor.attributes import build_final_attributes_simple
from custom_components.tibber_prices.const import CONF_CURRENCY_DISPLAY_MODE, DISPLAY_MODE_BASE
from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService
from homeassistant.util import dt as dt_util


def _dt(value: str):
    """Parse a timezone-aware datetime string for tests."""
    parsed = dt_util.parse_datetime(value)
    assert parsed is not None
    return parsed


@pytest.mark.unit
def test_build_final_attributes_exposes_day_statistics_on_current_period() -> None:
    """Day-level period context should be exposed on the visible binary sensor attrs."""
    current_period = {
        "start": _dt("2025-11-22T12:00:00+01:00"),
        "end": _dt("2025-11-22T13:00:00+01:00"),
        "duration_minutes": 60,
        "level": "CHEAP",
        "rating_level": "LOW",
        "rating_difference_%": -15.0,
        "price_mean": -0.1,
        "price_median": -0.12,
        "price_min": -0.3,
        "price_max": 0.1,
        "price_spread": 0.4,
        "price_coefficient_variation_%": 12.3,
        "volatility": "moderate",
        "period_price_diff_from_daily_min": 0.2,
        "period_price_diff_from_daily_min_%": 200.0,
        "day_volatility_%": 400.0,
        "day_price_min": -30.0,
        "day_price_max": 10.0,
        "day_price_span": 40.0,
        "period_interval_count": 4,
        "period_position": 1,
        "period_count_total": 1,
        "period_count_remaining": 0,
    }
    time = TibberPricesTimeService(reference_time=_dt("2025-11-22T12:00:00+01:00"))
    config_entry = Mock(options={CONF_CURRENCY_DISPLAY_MODE: DISPLAY_MODE_BASE})

    attributes = build_final_attributes_simple(
        current_period,
        [current_period],
        time=time,
        config_entry=config_entry,
    )

    assert attributes["price_mean"] == -0.1
    assert attributes["period_price_diff_from_daily_min"] == 0.2
    assert attributes["day_volatility_%"] == 400.0
    assert attributes["day_price_min"] == -30.0
    assert attributes["day_price_max"] == 10.0
    assert attributes["day_price_span"] == 40.0

    nested_period = attributes["periods"][0]
    assert nested_period["day_volatility_%"] == 400.0
    assert nested_period["day_price_min"] == -30.0
    assert nested_period["day_price_max"] == 10.0
    assert nested_period["day_price_span"] == 40.0
