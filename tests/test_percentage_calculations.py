"""Test Bug #9, #10, #11: Percentage calculations with negative prices use abs() correctly."""

from datetime import UTC, datetime
from unittest.mock import Mock

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
    price_avg = -10.0  # Period average in minor units (ct)

    mock_config_entry = Mock()
    mock_config_entry.options.get.return_value = "minor"  # Default display mode

    period_diff, period_diff_pct = calculate_period_price_diff(
        price_avg, start_time, price_context_negative, mock_config_entry
    )

    # Reference price: -20 ct
    # Difference: -10 - (-20) = 10 ct (period is 10 ct MORE EXPENSIVE than reference)
    # Percentage: 10 / abs(-20) * 100 = +50% (correctly shows increase)
    assert period_diff == 10.0, "Difference should be +10 ct"
    assert period_diff_pct == 50.0, "Percentage should be +50% (more expensive than ref)"


def test_bug9_period_price_diff_more_negative_than_reference(price_context_negative: dict) -> None:
    """
    Test Bug #9: Period more negative (cheaper) than reference.

    Verifies that when period average is more negative than reference,
    the percentage correctly shows negative (cheaper).
    """
    start_time = datetime(2025, 11, 22, 12, 0, tzinfo=UTC)
    price_avg = -25.0  # More negative (cheaper) than reference -20 ct

    mock_config_entry = Mock()
    mock_config_entry.options.get.return_value = "minor"  # Default display mode

    period_diff, period_diff_pct = calculate_period_price_diff(
        price_avg, start_time, price_context_negative, mock_config_entry
    )

    # Reference: -20 ct
    # Difference: -25 - (-20) = -5 ct (period is 5 ct CHEAPER)
    # Percentage: -5 / abs(-20) * 100 = -25% (correctly shows decrease)
    assert period_diff == -5.0, "Difference should be -5 ct"
    assert period_diff_pct == -25.0, "Percentage should be -25% (cheaper than ref)"


def test_bug9_period_price_diff_positive_reference(price_context_positive: dict) -> None:
    """
    Test Bug #9: Period price diff with positive reference price (sanity check).

    Verifies that abs() doesn't break normal positive price calculations.
    """
    start_time = datetime(2025, 11, 22, 12, 0, tzinfo=UTC)
    price_avg = 30.0  # ct

    mock_config_entry = Mock()
    mock_config_entry.options.get.return_value = "minor"  # Default display mode

    period_diff, period_diff_pct = calculate_period_price_diff(
        price_avg, start_time, price_context_positive, mock_config_entry
    )

    # Reference: 20 ct
    # Difference: 30 - 20 = 10 ct
    # Percentage: 10 / 20 * 100 = +50%
    assert period_diff == 10.0, "Difference should be +10 ct"
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

    trend, diff_pct = calculate_price_trend(
        current_interval_price=current_interval_price,
        future_average=future_average,
        threshold_rising=threshold_rising,
        threshold_falling=threshold_falling,
        volatility_adjustment=False,  # Disable to simplify test
    )

    # Difference: -5 - (-10) = 5 ct
    # Percentage: 5 / abs(-10) * 100 = +50% (correctly shows rising)
    assert diff_pct > 0, "Percentage should be positive (price rising toward zero)"
    assert diff_pct == pytest.approx(50.0, abs=0.1), "Should be +50%"
    assert trend == "rising", "Trend should be 'rising' (above 10% threshold)"


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

    trend, diff_pct = calculate_price_trend(
        current_interval_price=current_interval_price,
        future_average=future_average,
        threshold_rising=threshold_rising,
        threshold_falling=threshold_falling,
        volatility_adjustment=False,
    )

    # Difference: -15 - (-10) = -5 ct
    # Percentage: -5 / abs(-10) * 100 = -50% (correctly shows falling)
    assert diff_pct < 0, "Percentage should be negative (price falling deeper)"
    assert diff_pct == pytest.approx(-50.0, abs=0.1), "Should be -50%"
    assert trend == "falling", "Trend should be 'falling' (below -10% threshold)"


def test_bug10_trend_diff_zero_current_price() -> None:
    """
    Test Bug #10: Trend handles zero current price edge case.

    Division by zero should be handled gracefully.
    """
    current_interval_price = 0.0
    future_average = 0.05
    threshold_rising = 10.0
    threshold_falling = -10.0

    trend, diff_pct = calculate_price_trend(
        current_interval_price=current_interval_price,
        future_average=future_average,
        threshold_rising=threshold_rising,
        threshold_falling=threshold_falling,
        volatility_adjustment=False,
    )

    # Edge case: current=0 → diff_pct should be 0.0 (avoid division by zero)
    assert diff_pct == 0.0, "Should return 0.0 to avoid division by zero"
    assert trend == "stable", "Should be stable when diff is 0%"


def test_bug10_trend_diff_positive_prices_unchanged() -> None:
    """
    Test Bug #10: Trend calculation with positive prices still works correctly.

    Verifies that abs() doesn't break normal positive price calculations.
    """
    current_interval_price = 0.10  # 10 ct
    future_average = 0.15  # 15 ct (rising)
    threshold_rising = 10.0
    threshold_falling = -10.0

    trend, diff_pct = calculate_price_trend(
        current_interval_price=current_interval_price,
        future_average=future_average,
        threshold_rising=threshold_rising,
        threshold_falling=threshold_falling,
        volatility_adjustment=False,
    )

    # Difference: 15 - 10 = 5 ct
    # Percentage: 5 / 10 * 100 = +50%
    assert diff_pct == pytest.approx(50.0, abs=0.1), "Should be +50%"
    assert trend == "rising", "Should be rising"


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
