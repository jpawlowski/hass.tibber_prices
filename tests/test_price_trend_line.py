"""Tests for the price trend line and its confirmed timeline (utils/trend.py, trend calculator)."""

from __future__ import annotations

from datetime import datetime, timedelta
import math
from types import SimpleNamespace

import pytest

from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService
from custom_components.tibber_prices.sensor.calculators.trend import TibberPricesTrendCalculator
from custom_components.tibber_prices.utils.trend import (
    TREND_DIRECTION_GROUPS,
    TrendSegment,
    build_trend_segments,
    calculate_trend_line_change,
    trend_for_group,
)
from homeassistant.util import dt as dt_util

# ---------------------------------------------------------------------------
# Trend line
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_straight_ramp_gives_its_rise_over_the_horizon() -> None:
    """A straight ramp of 0.1 per interval rises 0.6 over 6 intervals."""
    prices = [1.0 + 0.1 * i for i in range(13)]

    change = calculate_trend_line_change(prices, 6)

    assert change is not None
    assert change.diff_abs == pytest.approx(0.6)


@pytest.mark.unit
def test_single_outlier_barely_moves_the_line() -> None:
    """A spike in the current interval shifts a level comparison by -23 %, the line not at all."""
    prices = [1.3] + [1.0] * 12

    change = calculate_trend_line_change(prices, 6)

    assert change is not None
    assert change.diff_abs == pytest.approx(0.0)


@pytest.mark.unit
def test_symmetric_peak_is_flat_overall() -> None:
    """Up and down within the window cancel out: no overall direction."""
    prices = [1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.2, 2.0, 1.8, 1.6, 1.4, 1.2, 1.0]

    change = calculate_trend_line_change(prices, 6)

    assert change is not None
    assert change.diff_abs == pytest.approx(0.0, abs=1e-9)


@pytest.mark.unit
def test_prices_around_zero_give_finite_percentages() -> None:
    """Negative and zero prices don't blow up the percentage."""
    prices = [-0.06 + 0.01 * i for i in range(13)]

    change = calculate_trend_line_change(prices, 6)

    assert change is not None
    assert change.diff_abs > 0
    assert math.isfinite(change.diff_pct)


@pytest.mark.unit
def test_too_few_prices() -> None:
    """Fewer than 5 prices: no trend line."""
    assert calculate_trend_line_change([1.0, 1.1, 1.2, 1.3], 6) is None


# ---------------------------------------------------------------------------
# Confirmed timeline
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_short_deviation_keeps_the_segment() -> None:
    """Two differing intervals with confirmation 3 are an outlier, not a trend change."""
    raw = ["rising", "rising", "falling", "falling", "rising", "strongly_rising"]

    assert build_trend_segments(raw, 3) == [TrendSegment(0, "rising")]


@pytest.mark.unit
def test_confirmed_change_starts_at_first_differing_interval() -> None:
    """Three intervals agreeing on a new direction confirm it, dated to the first of them."""
    raw = ["rising", "rising", "rising", "stable", "stable", "stable", "rising"]

    assert build_trend_segments(raw, 3) == [TrendSegment(0, "rising"), TrendSegment(3, "stable")]


@pytest.mark.unit
def test_brief_pass_through_stable_is_no_segment() -> None:
    """rising -> one stable -> falling: the change goes straight to falling where it starts."""
    raw = ["rising", "rising", "rising", "stable", "falling", "strongly_falling", "falling"]

    assert build_trend_segments(raw, 3) == [TrendSegment(0, "rising"), TrendSegment(4, "falling")]


@pytest.mark.unit
def test_strength_changes_are_not_trend_changes() -> None:
    """rising <-> strongly_rising stays one segment."""
    raw = ["rising", "strongly_rising", "strongly_rising", "strongly_rising", "rising"]

    assert build_trend_segments(raw, 3) == [TrendSegment(0, "rising")]


@pytest.mark.unit
def test_trend_for_group_falls_back_to_mild_level() -> None:
    """Inside a rising segment a stable outlier reads as rising; matching strengths stay."""
    assert trend_for_group("stable", "rising") == "rising"
    assert trend_for_group("strongly_rising", "rising") == "strongly_rising"


# ---------------------------------------------------------------------------
# Calculator: state, start and next change come from one timeline
# ---------------------------------------------------------------------------

DAY = datetime(2026, 10, 14, 0, 0, tzinfo=dt_util.get_default_time_zone())


def _curve(minutes: int) -> float:
    """Typical day: flat night, peak at 17:00, falling into the night (with a little noise)."""
    hours = minutes / 60
    peak = 2.0 * math.exp(-(((hours - 17) / 2.5) ** 2))
    noise = 0.02 if (minutes // 15) % 2 else -0.02
    return round(0.5 + peak + noise, 4)


def _calculator(now: datetime, prices: list[float]) -> TibberPricesTrendCalculator:
    intervals = [
        {"startsAt": DAY - timedelta(days=1) + timedelta(minutes=15 * i), "total": price}
        for i, price in enumerate(prices)
    ]
    coordinator = SimpleNamespace(
        data={"priceInfo": intervals, "referenceTime": now, "currency": "EUR"},
        time=TibberPricesTimeService(reference_time=now),
        config_entry=SimpleNamespace(options={"currency_display_mode": "base"}),
        hass=None,
    )
    return TibberPricesTrendCalculator(coordinator)  # type: ignore[arg-type]


def _day_prices(override: dict[int, float] | None = None) -> list[float]:
    """Yesterday, today and tomorrow (3 x 96 intervals), the same curve each day."""
    prices = [_curve((i % 96) * 15) for i in range(3 * 96)]
    for index, price in (override or {}).items():
        prices[96 + index] = price
    return prices


@pytest.mark.unit
def test_outlier_in_current_interval_does_not_flip_the_trend() -> None:
    """A one-interval spike at 06:00 on a flat morning keeps the trend stable."""
    now = DAY + timedelta(hours=6)
    assert _calculator(now, _day_prices()).get_current_trend_value() == "stable"
    calculator = _calculator(now, _day_prices({24: 0.8}))

    assert calculator.get_current_trend_value() == "stable"


@pytest.mark.unit
def test_v_shape_turns_at_the_minimum() -> None:
    """Falling until the minimum, rising from it: the window is centered on now, not ahead of it."""
    v_day = (
        [0.24] * 44
        + [round(0.24 - 0.01 * i, 4) for i in range(1, 12)]
        + [round(0.13 + 0.015 * i, 4) for i in range(1, 12)]
    )
    v_day += [v_day[-1]] * (96 - len(v_day))
    prices = v_day * 3  # minimum at 13:30 (interval 54)

    def group(hour: int, minute: int) -> str:
        now = DAY + timedelta(hours=hour, minutes=minute)
        return TREND_DIRECTION_GROUPS[_calculator(now, prices).get_current_trend_value()]

    assert group(12, 30) == "falling"
    assert group(13, 15) == "falling"
    assert group(13, 45) == "rising"


@pytest.mark.unit
def test_rising_before_the_peak_and_falling_after() -> None:
    """Heading into the 17:00 peak is rising, leaving it is falling."""
    assert TREND_DIRECTION_GROUPS[_calculator(DAY + timedelta(hours=14), _day_prices()).get_current_trend_value()] == (
        "rising"
    )
    assert (
        TREND_DIRECTION_GROUPS[_calculator(DAY + timedelta(hours=18), _day_prices()).get_current_trend_value()]
        == "falling"
    )


@pytest.mark.unit
def test_state_follows_the_announced_change() -> None:
    """Walking through the day: the trend group only changes where the previous step announced it."""
    prices = _day_prices()
    previous_group = None
    announced = None
    for quarter in range(8 * 4, 22 * 4):
        now = DAY + timedelta(minutes=15 * quarter)
        calculator = _calculator(now, prices)
        group = TREND_DIRECTION_GROUPS[calculator.get_current_trend_value()]
        if previous_group is not None and group != previous_group:
            assert announced == now, f"unannounced change at {now:%H:%M}"
        previous_group = group
        announced = calculator.get_next_trend_change_value()


@pytest.mark.unit
def test_missing_prices_keep_their_time_position() -> None:
    """Gaps don't squeeze the time axis: a ramp with two missing prices keeps its slope."""
    prices: list[float | None] = [1.0 + 0.1 * i for i in range(13)]
    prices[2] = prices[3] = None

    change = calculate_trend_line_change(prices, 6)

    assert change is not None
    assert change.diff_abs == pytest.approx(0.6)


@pytest.mark.unit
def test_outlier_at_the_edge_is_no_segment() -> None:
    """A single differing trend at the start of the data doesn't create a trend start right after it."""
    raw = ["rising", "stable", "stable", "stable", "stable"]

    assert build_trend_segments(raw, 3) == [TrendSegment(0, "stable")]


@pytest.mark.unit
def test_missing_total_does_not_break_the_trend() -> None:
    """An interval with total None (API gap) is skipped instead of raising."""
    now = DAY + timedelta(hours=14)
    prices = _day_prices()
    calculator = _calculator(now, prices)
    calculator.coordinator.data["priceInfo"][96 + 58]["total"] = None

    assert calculator.get_current_trend_value() in TREND_DIRECTION_GROUPS
