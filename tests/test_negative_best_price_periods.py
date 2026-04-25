"""Regression tests for best-price periods with negative prices."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from custom_components.tibber_prices.coordinator.period_handlers.core import calculate_periods
from custom_components.tibber_prices.coordinator.period_handlers.types import TibberPricesPeriodConfig
from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService


def _create_interval(dt: datetime, price: float, level: str) -> dict:
    """Create a single interval dict."""
    rating = "LOW" if price <= 5.0 else "NORMAL"
    return {
        "startsAt": dt,
        "total": price,
        "level": level,
        "rating_level": rating,
        "_original_price": price,
    }


def _build_day_with_overrides(overrides: dict[tuple[int, int], tuple[float, str]]) -> list[dict]:
    """Build a day of 15-minute intervals with targeted overrides."""
    tz = ZoneInfo("Europe/Berlin")
    base = datetime(2025, 4, 25, 0, 0, 0, tzinfo=tz)
    intervals: list[dict] = []

    for hour in range(24):
        for minute in (0, 15, 30, 45):
            price, level = overrides.get((hour, minute), (20.0, "NORMAL"))
            intervals.append(_create_interval(base.replace(hour=hour, minute=minute), price, level))

    return intervals


def _create_time_service() -> TibberPricesTimeService:
    """Create a deterministic time service for period calculation."""
    tz = ZoneInfo("Europe/Berlin")
    return TibberPricesTimeService(datetime(2025, 4, 25, 12, 0, 0, tzinfo=tz))


def _create_day_pattern(valley_start: tuple[int, int], valley_end: tuple[int, int]) -> dict:
    """Create a minimal day-pattern dict for geometric flex tests."""
    tz = ZoneInfo("Europe/Berlin")
    base = datetime(2025, 4, 25, 0, 0, 0, tzinfo=tz)
    return {
        "pattern": "valley",
        "confidence": 1.0,
        "day_cv_percent": 100.0,
        "segments": [],
        "extreme_time": base.replace(hour=13, minute=30),
        "valley_start": base.replace(hour=valley_start[0], minute=valley_start[1]),
        "valley_end": base.replace(hour=valley_end[0], minute=valley_end[1]),
        "peak_start": None,
        "peak_end": None,
    }


@pytest.mark.unit
class TestNegativeBestPricePeriods:
    """Validate local shoulder rescue around short negative cores only."""

    def test_short_negative_dip_can_be_rescued_by_local_shoulders(self) -> None:
        """A short negative core may extend into directly adjacent cheap shoulders."""
        intervals = _build_day_with_overrides(
            {
                (10, 45): (5.0, "CHEAP"),
                (11, 0): (2.0, "CHEAP"),
                (11, 15): (-1.5, "VERY_CHEAP"),
                (11, 30): (-1.0, "VERY_CHEAP"),
                (11, 45): (2.0, "CHEAP"),
                (12, 0): (5.0, "CHEAP"),
            }
        )
        config = TibberPricesPeriodConfig(
            reverse_sort=False,
            flex=0.15,
            min_distance_from_avg=5.0,
            min_period_length=60,
        )

        result = calculate_periods(intervals, config=config, time=_create_time_service())
        periods = result["periods"]

        assert len(periods) == 1, "Expected the short negative dip to survive as one local period"
        assert periods[0]["start"].hour == 11 and periods[0]["start"].minute == 0
        assert periods[0]["end"].hour == 12 and periods[0]["end"].minute == 0
        assert periods[0]["duration_minutes"] == 60

    def test_long_negative_block_stays_negative_only(self) -> None:
        """A multi-hour negative block must not pull in positive shoulders."""
        intervals = _build_day_with_overrides(
            {
                (10, 30): (2.0, "CHEAP"),
                (10, 45): (2.0, "CHEAP"),
                (11, 0): (-1.5, "VERY_CHEAP"),
                (11, 15): (-1.4, "VERY_CHEAP"),
                (11, 30): (-1.3, "VERY_CHEAP"),
                (11, 45): (-1.2, "VERY_CHEAP"),
                (12, 0): (-1.1, "VERY_CHEAP"),
                (12, 15): (-1.0, "VERY_CHEAP"),
                (12, 30): (-0.9, "VERY_CHEAP"),
                (12, 45): (-0.8, "VERY_CHEAP"),
                (13, 0): (2.0, "CHEAP"),
                (13, 15): (2.0, "CHEAP"),
            }
        )
        config = TibberPricesPeriodConfig(
            reverse_sort=False,
            flex=0.15,
            min_distance_from_avg=5.0,
            min_period_length=180,
        )

        result = calculate_periods(intervals, config=config, time=_create_time_service())

        assert result["periods"] == [], "Long negative blocks should not be widened with positive shoulders"

    def test_negative_core_ignores_geometric_and_shape_extension(self) -> None:
        """Negative best-price periods must not widen via geometric or shape extension."""
        intervals = _build_day_with_overrides(
            {
                (11, 45): (7.93, "VERY_CHEAP"),
                (12, 0): (4.5, "VERY_CHEAP"),
                (12, 15): (-1.0, "VERY_CHEAP"),
                (12, 30): (-2.0, "VERY_CHEAP"),
                (12, 45): (-3.0, "VERY_CHEAP"),
                (13, 0): (-4.0, "VERY_CHEAP"),
                (13, 15): (-5.36, "VERY_CHEAP"),
                (13, 30): (-4.5, "VERY_CHEAP"),
                (13, 45): (-3.5, "VERY_CHEAP"),
                (14, 0): (-2.5, "VERY_CHEAP"),
                (14, 15): (-1.5, "VERY_CHEAP"),
                (14, 30): (-0.5, "VERY_CHEAP"),
                (14, 45): (2.0, "VERY_CHEAP"),
                (15, 0): (4.0, "VERY_CHEAP"),
                (15, 15): (7.0, "VERY_CHEAP"),
            }
        )
        config = TibberPricesPeriodConfig(
            reverse_sort=False,
            flex=0.15,
            min_distance_from_avg=5.0,
            min_period_length=60,
            extend_to_extreme=True,
            max_extension_intervals=4,
            geometric_extra_flex=0.20,
        )
        day_patterns_by_date = {
            datetime(2025, 4, 25, 0, 0, 0, tzinfo=ZoneInfo("Europe/Berlin")).date(): _create_day_pattern(
                (11, 45), (15, 15)
            )
        }

        result = calculate_periods(
            intervals,
            config=config,
            time=_create_time_service(),
            day_patterns_by_date=day_patterns_by_date,
        )

        assert len(result["periods"]) == 1
        assert result["periods"][0]["start"].hour == 12 and result["periods"][0]["start"].minute == 15
        assert result["periods"][0]["end"].hour == 14 and result["periods"][0]["end"].minute == 45
        assert result["periods"][0].get("geometric_extension_active") is None
        assert result["periods"][0].get("extension_intervals_added") is None
