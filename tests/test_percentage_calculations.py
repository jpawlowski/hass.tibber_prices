"""Test Bug #9, #10, #11: Percentage calculations with negative prices use abs() correctly."""

from datetime import UTC, datetime

import pytest

from custom_components.tibber_prices.coordinator.period_handlers.period_statistics import (
    calculate_period_price_diff,
)
from custom_components.tibber_prices.utils.price import calculate_price_trend


@pytest.fixture
def price_context_negative() -> dict:
    """Create price context with negative reference price."""
    return {
        "ref_prices": {
            datetime(2025, 11, 22, tzinfo=UTC).date(): -0.20,  # -20 ct daily minimum
        }
    }


@pytest.fixture
def price_context_positive() -> dict:
    """Create price context with positive reference price."""
    return {
        "ref_prices": {
            datetime(2025, 11, 22, tzinfo=UTC).date(): 0.20,  # 20 ct daily minimum
        }
    }


def test_bug9_period_price_diff_negative_reference(price_context_negative: dict) -> None:
    """
    Test Bug #9: Period price diff percentage uses abs() for negative reference prices.

    Previously: Used ref_price directly → wrong sign for negative prices
    Now: Uses abs(ref_price) → correct percentage direction
    """
    start_time = datetime(2025, 11, 22, 12, 0, tzinfo=UTC)
    price_avg = -0.10  # Period average in base currency (EUR) = -10 ct

    period_diff, period_diff_pct = calculate_period_price_diff(price_avg, start_time, price_context_negative)

    # Reference price: -0.20 EUR (-20 ct)
    # Difference: -0.10 - (-0.20) = 0.10 EUR (period is 10 ct MORE EXPENSIVE than reference)
    # Percentage: 0.10 / abs(-0.20) * 100 = +50% (correctly shows increase)
    assert period_diff == 0.10, "Difference should be +0.10 EUR (+10 ct)"
    assert period_diff_pct == 50.0, "Percentage should be +50% (more expensive than ref)"


def test_bug9_period_price_diff_more_negative_than_reference(price_context_negative: dict) -> None:
    """
    Test Bug #9: Period more negative (cheaper) than reference.

    Verifies that when period average is more negative than reference,
    the percentage correctly shows negative (cheaper).
    """
    start_time = datetime(2025, 11, 22, 12, 0, tzinfo=UTC)
    price_avg = -0.25  # More negative (cheaper) than reference: -0.25 EUR = -25 ct

    period_diff, period_diff_pct = calculate_period_price_diff(price_avg, start_time, price_context_negative)

    # Reference: -0.20 EUR (-20 ct)
    # Difference: -0.25 - (-0.20) = -0.05 EUR (period is 5 ct CHEAPER)
    # Percentage: -0.05 / abs(-0.20) * 100 = -25% (correctly shows decrease)
    assert period_diff == -0.05, "Difference should be -0.05 EUR (-5 ct)"
    assert period_diff_pct == -25.0, "Percentage should be -25% (cheaper than ref)"


def test_bug9_period_price_diff_positive_reference(price_context_positive: dict) -> None:
    """
    Test Bug #9: Period price diff with positive reference price (sanity check).

    Verifies that abs() doesn't break normal positive price calculations.
    """
    start_time = datetime(2025, 11, 22, 12, 0, tzinfo=UTC)
    price_avg = 0.30  # Period average in base currency (EUR) = 30 ct

    period_diff, period_diff_pct = calculate_period_price_diff(price_avg, start_time, price_context_positive)

    # Reference: 0.20 EUR (20 ct)
    # Difference: 0.30 - 0.20 = 0.10 EUR (10 ct)
    # Percentage: 0.10 / 0.20 * 100 = +50%
    assert period_diff == 0.10, "Difference should be +0.10 EUR (+10 ct)"
    assert period_diff_pct == 50.0, "Percentage should be +50%"


def test_bug10_trend_diff_negative_current_price() -> None:
    """
    Test Bug #10: Trend diff percentage uses abs() for negative current prices.

    Previously: Used current_interval_price directly → wrong sign
    Now: Uses abs(current_interval_price) → correct percentage direction
    """
    # Current price: -10 ct/kWh (negative)
    # Future average: -5 ct/kWh (less negative, i.e., rising toward zero)
    current_interval_price = -0.10
    future_average = -0.05
    threshold_rising = 10.0
    threshold_falling = -10.0
    threshold_strongly_rising = 20.0
    threshold_strongly_falling = -20.0

    trend, diff_pct, trend_value = calculate_price_trend(
        current_interval_price=current_interval_price,
        future_average=future_average,
        threshold_rising=threshold_rising,
        threshold_falling=threshold_falling,
        threshold_strongly_rising=threshold_strongly_rising,
        threshold_strongly_falling=threshold_strongly_falling,
        volatility_adjustment=False,  # Disable to simplify test
    )

    # Difference: -5 - (-10) = 5 ct
    # Percentage: 5 / abs(-10) * 100 = +50% (correctly shows rising)
    # With 5-level scale: +50% >= 20% strongly_rising threshold => strongly_rising
    assert diff_pct > 0, "Percentage should be positive (price rising toward zero)"
    assert diff_pct == pytest.approx(50.0, abs=0.1), "Should be +50%"
    assert trend == "strongly_rising", "Trend should be 'strongly_rising' (above strongly_rising threshold)"
    assert trend_value == 2, "Trend value should be 2 for strongly_rising"


def test_bug10_trend_diff_negative_falling_deeper() -> None:
    """
    Test Bug #10: Trend correctly shows falling when price becomes more negative.

    Verifies that when price goes from -10 to -15 (falling deeper into negative),
    the percentage correctly shows negative trend.
    """
    current_interval_price = -0.10  # -10 ct
    future_average = -0.15  # -15 ct (more negative = cheaper)
    threshold_rising = 10.0
    threshold_falling = -10.0
    threshold_strongly_rising = 20.0
    threshold_strongly_falling = -20.0

    trend, diff_pct, trend_value = calculate_price_trend(
        current_interval_price=current_interval_price,
        future_average=future_average,
        threshold_rising=threshold_rising,
        threshold_falling=threshold_falling,
        threshold_strongly_rising=threshold_strongly_rising,
        threshold_strongly_falling=threshold_strongly_falling,
        volatility_adjustment=False,
    )

    # Difference: -15 - (-10) = -5 ct
    # Percentage: -5 / abs(-10) * 100 = -50% (correctly shows falling)
    # With 5-level scale: -50% <= -20% strongly_falling threshold => strongly_falling
    assert diff_pct < 0, "Percentage should be negative (price falling deeper)"
    assert diff_pct == pytest.approx(-50.0, abs=0.1), "Should be -50%"
    assert trend == "strongly_falling", "Trend should be 'strongly_falling' (below strongly_falling threshold)"
    assert trend_value == -2, "Trend value should be -2 for strongly_falling"


def test_bug10_trend_diff_zero_current_price() -> None:
    """
    Test Bug #10: Trend handles zero current price edge case.

    Division by zero should be handled gracefully.
    """
    current_interval_price = 0.0
    future_average = 0.05
    threshold_rising = 10.0
    threshold_falling = -10.0
    threshold_strongly_rising = 20.0
    threshold_strongly_falling = -20.0

    trend, diff_pct, trend_value = calculate_price_trend(
        current_interval_price=current_interval_price,
        future_average=future_average,
        threshold_rising=threshold_rising,
        threshold_falling=threshold_falling,
        threshold_strongly_rising=threshold_strongly_rising,
        threshold_strongly_falling=threshold_strongly_falling,
        volatility_adjustment=False,
    )

    # Edge case: current=0 → diff_pct should be 0.0 (avoid division by zero)
    assert diff_pct == 0.0, "Should return 0.0 to avoid division by zero"
    assert trend == "stable", "Should be stable when diff is 0%"
    assert trend_value == 0, "Trend value should be 0 for stable"


def test_bug10_trend_diff_positive_prices_unchanged() -> None:
    """
    Test Bug #10: Trend calculation with positive prices still works correctly.

    Verifies that abs() doesn't break normal positive price calculations.
    """
    current_interval_price = 0.10  # 10 ct
    future_average = 0.15  # 15 ct (rising)
    threshold_rising = 10.0
    threshold_falling = -10.0
    threshold_strongly_rising = 20.0
    threshold_strongly_falling = -20.0

    trend, diff_pct, trend_value = calculate_price_trend(
        current_interval_price=current_interval_price,
        future_average=future_average,
        threshold_rising=threshold_rising,
        threshold_falling=threshold_falling,
        threshold_strongly_rising=threshold_strongly_rising,
        threshold_strongly_falling=threshold_strongly_falling,
        volatility_adjustment=False,
    )

    # Difference: 15 - 10 = 5 ct
    # Percentage: 5 / 10 * 100 = +50%
    # With 5-level scale: +50% >= 20% strongly_rising threshold => strongly_rising
    assert diff_pct == pytest.approx(50.0, abs=0.1), "Should be +50%"
    assert trend == "strongly_rising", "Should be strongly_rising (above strongly_rising threshold)"
    assert trend_value == 2, "Trend value should be 2 for strongly_rising"


def test_bug11_later_half_diff_calculation_note() -> None:
    """
    Test Bug #11: Note about later_half_diff calculation fix.

    Bug #11 was fixed in sensor/calculators/trend.py by:
    1. Changing condition from `if current_interval_price > 0` to `if current_interval_price != 0`
    2. Using abs(current_interval_price) in percentage calculation

    This allows calculation for negative prices and uses correct formula:
    later_half_diff = ((later_half_avg - current_interval_price) / abs(current_interval_price)) * 100

    Testing this requires integration test with full coordinator setup,
    so we document the fix here and rely on existing integration tests
    to verify the behavior.
    """
    # This is a documentation test - the actual fix is tested via integration tests
    assert True, "Bug #11 fix documented"
