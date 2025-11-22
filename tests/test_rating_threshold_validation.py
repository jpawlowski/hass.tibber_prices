"""Tests for Bug #6: Rating threshold validation in calculate_rating_level()."""

import logging

import pytest
from _pytest.logging import LogCaptureFixture

from custom_components.tibber_prices.utils.price import calculate_rating_level


@pytest.fixture
def caplog_debug(caplog: LogCaptureFixture) -> LogCaptureFixture:
    """Set log level to DEBUG for capturing all log messages."""
    caplog.set_level(logging.DEBUG)
    return caplog


def test_rating_level_with_correct_thresholds() -> None:
    """Test rating level calculation with correctly configured thresholds."""
    # Normal thresholds: low < high
    threshold_low = -10.0
    threshold_high = 10.0

    # Test LOW rating
    assert calculate_rating_level(-15.0, threshold_low, threshold_high) == "LOW"
    assert calculate_rating_level(-10.0, threshold_low, threshold_high) == "LOW"  # Boundary

    # Test NORMAL rating
    assert calculate_rating_level(-5.0, threshold_low, threshold_high) == "NORMAL"
    assert calculate_rating_level(0.0, threshold_low, threshold_high) == "NORMAL"
    assert calculate_rating_level(5.0, threshold_low, threshold_high) == "NORMAL"

    # Test HIGH rating
    assert calculate_rating_level(10.0, threshold_low, threshold_high) == "HIGH"  # Boundary
    assert calculate_rating_level(15.0, threshold_low, threshold_high) == "HIGH"


def test_rating_level_with_none_difference() -> None:
    """Test that None difference returns None."""
    assert calculate_rating_level(None, -10.0, 10.0) is None


def test_rating_level_with_inverted_thresholds_warns(caplog_debug: LogCaptureFixture) -> None:
    """
    Test that inverted thresholds (low > high) trigger warning and return NORMAL.

    Bug #6: Previously had dead code checking for impossible condition.
    Now validates thresholds and warns user about misconfiguration.
    """
    # Inverted thresholds: low > high (user configuration error)
    threshold_low = 15.0  # Should be negative!
    threshold_high = 5.0  # Lower than low!

    # Should return NORMAL as fallback
    result = calculate_rating_level(10.0, threshold_low, threshold_high)
    assert result == "NORMAL"

    # Should log warning
    assert len(caplog_debug.records) == 1
    assert caplog_debug.records[0].levelname == "WARNING"
    assert "Invalid rating thresholds" in caplog_debug.records[0].message
    assert "threshold_low (15.00) >= threshold_high (5.00)" in caplog_debug.records[0].message


def test_rating_level_with_equal_thresholds_warns(caplog_debug: LogCaptureFixture) -> None:
    """Test that equal thresholds trigger warning and return NORMAL."""
    # Equal thresholds (edge case of misconfiguration)
    threshold_low = 10.0
    threshold_high = 10.0

    # Should return NORMAL as fallback
    result = calculate_rating_level(10.0, threshold_low, threshold_high)
    assert result == "NORMAL"

    # Should log warning
    assert len(caplog_debug.records) == 1
    assert caplog_debug.records[0].levelname == "WARNING"
    assert "Invalid rating thresholds" in caplog_debug.records[0].message


def test_rating_level_with_negative_prices_and_inverted_thresholds(caplog_debug: LogCaptureFixture) -> None:
    """
    Test rating level with negative prices and misconfigured thresholds.

    This tests the scenario that motivated Bug #6 fix: negative prices
    combined with threshold misconfiguration should be detected, not silently
    produce wrong results.
    """
    # User accidentally configured thresholds in wrong order
    threshold_low = 15.0  # Should be LOWER than high!
    threshold_high = 5.0  # Inverted!

    # Negative price difference (cheap compared to average)
    difference = -20.0

    # Should detect misconfiguration and return NORMAL
    result = calculate_rating_level(difference, threshold_low, threshold_high)
    assert result == "NORMAL"

    # Should warn user
    assert len(caplog_debug.records) == 1
    assert "Invalid rating thresholds" in caplog_debug.records[0].message


def test_rating_level_edge_cases_with_correct_thresholds() -> None:
    """Test edge cases with correctly configured thresholds."""
    threshold_low = -10.0
    threshold_high = 10.0

    # Exact boundary values
    assert calculate_rating_level(-10.0, threshold_low, threshold_high) == "LOW"
    assert calculate_rating_level(10.0, threshold_low, threshold_high) == "HIGH"

    # Just inside NORMAL range
    assert calculate_rating_level(-9.99, threshold_low, threshold_high) == "NORMAL"
    assert calculate_rating_level(9.99, threshold_low, threshold_high) == "NORMAL"

    # Just outside NORMAL range
    assert calculate_rating_level(-10.01, threshold_low, threshold_high) == "LOW"
    assert calculate_rating_level(10.01, threshold_low, threshold_high) == "HIGH"


def test_rating_level_with_extreme_differences() -> None:
    """Test rating level with extreme difference percentages."""
    threshold_low = -10.0
    threshold_high = 10.0

    # Very negative (very cheap)
    assert calculate_rating_level(-500.0, threshold_low, threshold_high) == "LOW"

    # Very positive (very expensive)
    assert calculate_rating_level(500.0, threshold_low, threshold_high) == "HIGH"


def test_rating_level_asymmetric_thresholds() -> None:
    """Test rating level with asymmetric thresholds (different magnitudes)."""
    # Asymmetric but valid: more sensitive to expensive prices
    threshold_low = -20.0  # Wider cheap range
    threshold_high = 5.0  # Narrower expensive range

    assert calculate_rating_level(-25.0, threshold_low, threshold_high) == "LOW"
    assert calculate_rating_level(-15.0, threshold_low, threshold_high) == "NORMAL"
    assert calculate_rating_level(0.0, threshold_low, threshold_high) == "NORMAL"
    assert calculate_rating_level(6.0, threshold_low, threshold_high) == "HIGH"
