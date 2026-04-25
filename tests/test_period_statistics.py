"""Regression tests for period summary day statistics."""

from __future__ import annotations

from datetime import datetime

import pytest

from custom_components.tibber_prices.coordinator.period_handlers.period_statistics import build_period_summary_dict
from custom_components.tibber_prices.coordinator.period_handlers.types import (
    TibberPricesPeriodData,
    TibberPricesPeriodStatistics,
)


def _build_stats() -> TibberPricesPeriodStatistics:
    """Create minimal summary stats for period-summary tests."""
    return TibberPricesPeriodStatistics(
        aggregated_level="cheap",
        aggregated_rating="low",
        rating_difference_pct=-10.0,
        price_mean=-0.2,
        price_median=-0.2,
        price_min=-0.3,
        price_max=0.1,
        price_spread=0.4,
        volatility="moderate",
        coefficient_of_variation=12.3,
        period_price_diff=0.0,
        period_price_diff_pct=0.0,
    )


def _build_period_data(day: datetime) -> TibberPricesPeriodData:
    """Create minimal period timing data for summary tests."""
    return TibberPricesPeriodData(
        start_time=day.replace(hour=1),
        end_time=day.replace(hour=2),
        period_length=4,
        period_idx=1,
        total_periods=1,
    )


@pytest.mark.unit
class TestPeriodSummaryDayVolatility:
    """Validate day_volatility_% semantics on extreme price days."""

    def test_day_volatility_uses_absolute_average_for_negative_price_days(self) -> None:
        """Negative-average days should still report meaningful volatility percentage."""
        day = datetime(2025, 11, 22)
        summary = build_period_summary_dict(
            _build_period_data(day),
            _build_stats(),
            reverse_sort=False,
            price_context={
                "intervals_by_day": {
                    day.date(): [
                        {"total": -0.30},
                        {"total": -0.10},
                        {"total": 0.10},
                    ]
                },
                "avg_prices": {day.date(): -0.10},
            },
        )

        assert summary["day_volatility_%"] == 400.0
        assert summary["day_price_min"] == -30.0
        assert summary["day_price_max"] == 10.0
        assert summary["day_price_span"] == 40.0

    def test_day_volatility_is_none_when_day_average_is_zero(self) -> None:
        """Zero-average days should avoid reporting a misleading 0% volatility."""
        day = datetime(2025, 11, 23)
        summary = build_period_summary_dict(
            _build_period_data(day),
            _build_stats(),
            reverse_sort=False,
            price_context={
                "intervals_by_day": {
                    day.date(): [
                        {"total": -0.20},
                        {"total": 0.20},
                    ]
                },
                "avg_prices": {day.date(): 0.0},
            },
        )

        assert summary["day_volatility_%"] is None
        assert summary["day_price_min"] == -20.0
        assert summary["day_price_max"] == 20.0
        assert summary["day_price_span"] == 40.0
