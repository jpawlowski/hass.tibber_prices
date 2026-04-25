"""Regression tests for overlap resolution and merged period summaries."""

from __future__ import annotations

from datetime import timedelta

import pytest

from custom_components.tibber_prices.coordinator.period_handlers import TibberPricesPeriodConfig
from custom_components.tibber_prices.coordinator.period_handlers.period_overlap import resolve_period_overlaps
from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService
from custom_components.tibber_prices.utils.price import calculate_coefficient_of_variation
from homeassistant.util import dt as dt_util


def _create_interval(base_time, offset: int, price: float, level: str, difference: float, rating: str) -> dict:
    """Create one quarter-hour interval for overlap tests."""
    return {
        "startsAt": base_time + timedelta(minutes=offset * 15),
        "total": price,
        "level": level,
        "difference": difference,
        "rating_level": rating,
    }


@pytest.mark.unit
class TestResolvePeriodOverlaps:
    """Validate merged period summaries stay consistent after overlap resolution."""

    def test_merge_recomputes_summary_from_raw_intervals(self) -> None:
        """Overlapping periods should be rebuilt from the raw union, not glued summaries."""
        base_time = dt_util.parse_datetime("2025-11-22T10:00:00+01:00")
        assert base_time is not None

        all_prices = [
            _create_interval(base_time, 0, 0.10, "CHEAP", -12.0, "LOW"),
            _create_interval(base_time, 1, 0.10, "CHEAP", -11.0, "LOW"),
            _create_interval(base_time, 2, 0.11, "CHEAP", -10.0, "LOW"),
            _create_interval(base_time, 3, 0.11, "CHEAP", -9.0, "NORMAL"),
            _create_interval(base_time, 4, 0.12, "NORMAL", -4.0, "NORMAL"),
            _create_interval(base_time, 5, 0.13, "NORMAL", 0.0, "NORMAL"),
            _create_interval(base_time, 6, 0.13, "NORMAL", 1.0, "NORMAL"),
            _create_interval(base_time, 7, 0.14, "NORMAL", 3.0, "NORMAL"),
        ]
        config = TibberPricesPeriodConfig(
            reverse_sort=False,
            flex=0.15,
            min_distance_from_avg=0.0,
            min_period_length=60,
            threshold_low=-10.0,
            threshold_high=10.0,
        )
        time = TibberPricesTimeService(reference_time=base_time + timedelta(hours=1))

        existing_period = {
            "start": base_time,
            "end": base_time + timedelta(minutes=75),
            "duration_minutes": 75,
            "level": "cheap",
            "rating_level": "low",
            "rating_difference_%": -9.2,
            "price_mean": 0.108,
            "price_median": 0.11,
            "price_min": 0.10,
            "price_max": 0.12,
            "price_spread": 0.02,
            "price_coefficient_variation_%": 7.7,
            "volatility": "low",
            "period_interval_count": 5,
            "period_price_diff_from_daily_min": 0.008,
            "period_price_diff_from_daily_min_%": 8.0,
            "period_position": 1,
            "period_count_total": 1,
            "period_count_remaining": 0,
        }
        relaxed_period = {
            "start": base_time + timedelta(minutes=60),
            "end": base_time + timedelta(minutes=120),
            "duration_minutes": 60,
            "level": "normal",
            "rating_level": "normal",
            "rating_difference_%": 0.0,
            "price_mean": 0.13,
            "price_median": 0.13,
            "price_min": 0.12,
            "price_max": 0.14,
            "price_spread": 0.02,
            "price_coefficient_variation_%": 5.8,
            "volatility": "low",
            "period_interval_count": 4,
            "period_price_diff_from_daily_min": 0.03,
            "period_price_diff_from_daily_min_%": 30.0,
            "period_position": 1,
            "period_count_total": 1,
            "period_count_remaining": 0,
            "relaxation_active": True,
            "relaxation_level": "flex=18.0% +level_any",
        }

        merged_periods, periods_added = resolve_period_overlaps(
            existing_periods=[existing_period],
            new_relaxed_periods=[relaxed_period],
            all_prices=all_prices,
            config=config,
            time=time,
        )

        assert periods_added == 1
        assert len(merged_periods) == 1

        merged = merged_periods[0]
        expected_prices = [0.10, 0.10, 0.11, 0.11, 0.12, 0.13, 0.13, 0.14]
        expected_cv = calculate_coefficient_of_variation(expected_prices)
        assert expected_cv is not None

        assert merged["start"] == base_time
        assert merged["end"] == base_time + timedelta(minutes=120)
        assert merged["period_interval_count"] == 8
        assert merged["duration_minutes"] == 120
        assert merged["price_mean"] == 0.1175
        assert merged["price_median"] == 0.115
        assert merged["price_min"] == 0.10
        assert merged["price_max"] == 0.14
        assert merged["price_spread"] == 0.04
        assert merged["price_coefficient_variation_%"] == round(expected_cv, 1)
        assert merged["level"] == "normal"
        assert merged["rating_level"] == "normal"
        assert merged["rating_difference_%"] == -5.25
        assert merged["period_price_diff_from_daily_min"] == 0.0175
        assert merged["period_price_diff_from_daily_min_%"] == 17.5
        assert merged["relaxation_active"] is True
        assert merged["relaxation_level"] == "flex=18.0% +level_any"
        assert "merged_from" in merged
