"""Tests for Bug #6: Rating threshold validation in calculate_rating_level()."""

import logging

import pytest
from _pytest.logging import LogCaptureFixture

from custom_components.tibber_prices.utils.price import (
    _apply_rating_gap_tolerance,
    calculate_rating_level,
)


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


# =============================================================================
# Hysteresis Tests - Prevent flickering at threshold boundaries
# =============================================================================


def test_hysteresis_prevents_flickering_at_low_threshold() -> None:
    """Test that hysteresis prevents rapid switching at LOW threshold boundary."""
    threshold_low = -10.0
    threshold_high = 10.0
    hysteresis = 2.0

    # Without previous state: enters LOW at threshold
    assert calculate_rating_level(-10.0, threshold_low, threshold_high) == "LOW"

    # With previous state LOW: stays LOW until exceeds exit threshold (-10 + 2 = -8)
    assert (
        calculate_rating_level(-9.5, threshold_low, threshold_high, previous_rating="LOW", hysteresis=hysteresis)
        == "LOW"
    )
    assert (
        calculate_rating_level(-8.5, threshold_low, threshold_high, previous_rating="LOW", hysteresis=hysteresis)
        == "LOW"
    )
    # Exits LOW when exceeding exit threshold
    assert (
        calculate_rating_level(-7.5, threshold_low, threshold_high, previous_rating="LOW", hysteresis=hysteresis)
        == "NORMAL"
    )

    # With previous state NORMAL: enters LOW at standard threshold
    assert (
        calculate_rating_level(-10.0, threshold_low, threshold_high, previous_rating="NORMAL", hysteresis=hysteresis)
        == "LOW"
    )
    assert (
        calculate_rating_level(-9.5, threshold_low, threshold_high, previous_rating="NORMAL", hysteresis=hysteresis)
        == "NORMAL"
    )


def test_hysteresis_prevents_flickering_at_high_threshold() -> None:
    """Test that hysteresis prevents rapid switching at HIGH threshold boundary."""
    threshold_low = -10.0
    threshold_high = 10.0
    hysteresis = 2.0

    # Without previous state: enters HIGH at threshold
    assert calculate_rating_level(10.0, threshold_low, threshold_high) == "HIGH"

    # With previous state HIGH: stays HIGH until drops below exit threshold (10 - 2 = 8)
    assert (
        calculate_rating_level(9.5, threshold_low, threshold_high, previous_rating="HIGH", hysteresis=hysteresis)
        == "HIGH"
    )
    assert (
        calculate_rating_level(8.5, threshold_low, threshold_high, previous_rating="HIGH", hysteresis=hysteresis)
        == "HIGH"
    )
    # Exits HIGH when dropping below exit threshold
    assert (
        calculate_rating_level(7.5, threshold_low, threshold_high, previous_rating="HIGH", hysteresis=hysteresis)
        == "NORMAL"
    )

    # With previous state NORMAL: enters HIGH at standard threshold
    assert (
        calculate_rating_level(10.0, threshold_low, threshold_high, previous_rating="NORMAL", hysteresis=hysteresis)
        == "HIGH"
    )
    assert (
        calculate_rating_level(9.5, threshold_low, threshold_high, previous_rating="NORMAL", hysteresis=hysteresis)
        == "NORMAL"
    )


def test_hysteresis_allows_direct_transition_low_to_high() -> None:
    """Test that extreme price swings can jump directly from LOW to HIGH."""
    threshold_low = -10.0
    threshold_high = 10.0
    hysteresis = 2.0

    # Even when in LOW state, a very high price should transition to HIGH
    assert (
        calculate_rating_level(15.0, threshold_low, threshold_high, previous_rating="LOW", hysteresis=hysteresis)
        == "HIGH"
    )

    # And vice versa
    assert (
        calculate_rating_level(-15.0, threshold_low, threshold_high, previous_rating="HIGH", hysteresis=hysteresis)
        == "LOW"
    )


def test_hysteresis_with_zero_value() -> None:
    """Test that zero hysteresis behaves like original function."""
    threshold_low = -10.0
    threshold_high = 10.0
    hysteresis = 0.0

    # With zero hysteresis, should behave exactly like original function
    assert (
        calculate_rating_level(-10.0, threshold_low, threshold_high, previous_rating="NORMAL", hysteresis=hysteresis)
        == "LOW"
    )
    assert (
        calculate_rating_level(-9.9, threshold_low, threshold_high, previous_rating="LOW", hysteresis=hysteresis)
        == "NORMAL"
    )


def test_hysteresis_sequence_simulation() -> None:
    """Simulate a sequence of price changes to verify hysteresis prevents flickering."""
    threshold_low = -10.0
    threshold_high = 10.0
    hysteresis = 2.0

    # Simulate price differences oscillating around -10% threshold
    price_differences = [-9.5, -10.2, -9.8, -10.1, -9.9, -10.3, -8.5, -9.0, -7.5]
    expected_without_hysteresis = ["NORMAL", "LOW", "NORMAL", "LOW", "NORMAL", "LOW", "NORMAL", "NORMAL", "NORMAL"]
    expected_with_hysteresis = ["NORMAL", "LOW", "LOW", "LOW", "LOW", "LOW", "LOW", "LOW", "NORMAL"]

    # Without hysteresis: lots of flickering
    results_without = [calculate_rating_level(diff, threshold_low, threshold_high) for diff in price_differences]
    assert results_without == expected_without_hysteresis

    # With hysteresis: stable blocks
    results_with: list[str] = []
    previous: str | None = None
    for diff in price_differences:
        rating = calculate_rating_level(
            diff, threshold_low, threshold_high, previous_rating=previous, hysteresis=hysteresis
        )
        results_with.append(rating)
        previous = rating
    assert results_with == expected_with_hysteresis


# =============================================================================
# Gap Tolerance Tests - Smooth out isolated rating changes
# =============================================================================


def test_gap_tolerance_single_interval() -> None:
    """Test that a single isolated interval gets smoothed out."""
    # Create intervals with a single NORMAL surrounded by LOW
    intervals = [
        {"rating_level": "LOW"},
        {"rating_level": "LOW"},
        {"rating_level": "NORMAL"},  # Isolated - should be corrected
        {"rating_level": "LOW"},
        {"rating_level": "LOW"},
    ]

    _apply_rating_gap_tolerance(intervals, gap_tolerance=1)

    assert [i["rating_level"] for i in intervals] == ["LOW", "LOW", "LOW", "LOW", "LOW"]


def test_gap_tolerance_two_intervals() -> None:
    """Test that two consecutive isolated intervals get smoothed out with gap_tolerance=2."""
    # Two NORMALs surrounded by LOW
    intervals = [
        {"rating_level": "LOW"},
        {"rating_level": "NORMAL"},
        {"rating_level": "NORMAL"},
        {"rating_level": "LOW"},
    ]

    # With gap_tolerance=1, should NOT be corrected (2 > 1)
    _apply_rating_gap_tolerance(intervals, gap_tolerance=1)
    assert [i["rating_level"] for i in intervals] == ["LOW", "NORMAL", "NORMAL", "LOW"]

    # With gap_tolerance=2, SHOULD be corrected
    _apply_rating_gap_tolerance(intervals, gap_tolerance=2)
    assert [i["rating_level"] for i in intervals] == ["LOW", "LOW", "LOW", "LOW"]


def test_gap_tolerance_different_surrounding_ratings() -> None:
    """Test that gaps between different ratings are merged into the larger neighbor."""
    # NORMAL surrounded by LOW (2) on left, HIGH (2) on right
    # Both have equal size, so it should merge into LEFT (earlier in time)
    intervals = [
        {"rating_level": "LOW"},
        {"rating_level": "LOW"},
        {"rating_level": "NORMAL"},
        {"rating_level": "HIGH"},
        {"rating_level": "HIGH"},
    ]

    _apply_rating_gap_tolerance(intervals, gap_tolerance=1)

    # With equal neighbors, prefer LEFT (LOW) - single NORMAL merges into LOW
    assert [i["rating_level"] for i in intervals] == ["LOW", "LOW", "LOW", "HIGH", "HIGH"]


def test_gap_tolerance_bidirectional_larger_right() -> None:
    """Test that gaps merge into the larger neighboring block (right side)."""
    # NORMAL surrounded by LOW (2) on left, HIGH (3) on right
    # RIGHT is larger, so NORMAL should merge into HIGH
    intervals = [
        {"rating_level": "LOW"},
        {"rating_level": "LOW"},
        {"rating_level": "NORMAL"},  # Should merge into HIGH (larger neighbor)
        {"rating_level": "HIGH"},
        {"rating_level": "HIGH"},
        {"rating_level": "HIGH"},
    ]

    _apply_rating_gap_tolerance(intervals, gap_tolerance=1)

    # NORMAL merges into HIGH because HIGH block is larger
    assert [i["rating_level"] for i in intervals] == ["LOW", "LOW", "HIGH", "HIGH", "HIGH", "HIGH"]


def test_gap_tolerance_bidirectional_larger_left() -> None:
    """Test that gaps merge into the larger neighboring block (left side)."""
    # NORMAL surrounded by LOW (3) on left, HIGH (2) on right
    # LEFT is larger, so NORMAL should merge into LOW
    intervals = [
        {"rating_level": "LOW"},
        {"rating_level": "LOW"},
        {"rating_level": "LOW"},
        {"rating_level": "NORMAL"},  # Should merge into LOW (larger neighbor)
        {"rating_level": "HIGH"},
        {"rating_level": "HIGH"},
    ]

    _apply_rating_gap_tolerance(intervals, gap_tolerance=1)

    # NORMAL merges into LOW because LOW block is larger
    assert [i["rating_level"] for i in intervals] == ["LOW", "LOW", "LOW", "LOW", "HIGH", "HIGH"]


def test_gap_tolerance_chain_merge() -> None:
    """
    Test the real-world scenario: NORMAL HIGH NORMAL HIGH HIGH HIGH.

    This is the 05:30-06:45 scenario where:
    - 05:45 is HIGH (single, diff=+14%)
    - 06:00 is NORMAL (single, diff=+3.2%)
    - 06:15+ is HIGH (large block, diff>+12%)

    The algorithm looks for the first LARGE block in each direction,
    not just the immediate neighbor. This ensures small blocks are
    pulled toward the dominant large block.
    """
    intervals = [
        {"rating_level": "NORMAL"},  # 05:30
        {"rating_level": "HIGH"},  # 05:45 - single HIGH
        {"rating_level": "NORMAL"},  # 06:00 - single NORMAL
        {"rating_level": "HIGH"},  # 06:15
        {"rating_level": "HIGH"},  # 06:30
        {"rating_level": "HIGH"},  # 06:45
    ]

    _apply_rating_gap_tolerance(intervals, gap_tolerance=1)

    # With the "look through small blocks" logic:
    # - HIGH(1) at idx 1: left=NORMAL(1) small, looks further left=nothing → left_pull=(1, NORMAL)
    #                     right=NORMAL(1) small, looks further right=HIGH(3) → right_pull=(3, HIGH)
    #   Since it's already HIGH and right pull is HIGH, no change needed
    # - NORMAL(1) at idx 2: left=HIGH(1) small, looks further left=NORMAL(1) small → left_pull=(1, NORMAL)
    #                       right=HIGH(3) large → right_pull=(3, HIGH)
    #   Merges into HIGH (larger pull)
    # Result: NORMAL(1), HIGH(5)
    assert [i["rating_level"] for i in intervals] == [
        "NORMAL",
        "HIGH",
        "HIGH",
        "HIGH",
        "HIGH",
        "HIGH",
    ]


def test_gap_tolerance_multiple_gaps() -> None:
    """Test that multiple gaps in a sequence get corrected."""
    intervals = [
        {"rating_level": "LOW"},
        {"rating_level": "NORMAL"},  # Gap 1
        {"rating_level": "LOW"},
        {"rating_level": "LOW"},
        {"rating_level": "NORMAL"},  # Gap 2
        {"rating_level": "LOW"},
    ]

    _apply_rating_gap_tolerance(intervals, gap_tolerance=1)

    assert [i["rating_level"] for i in intervals] == ["LOW", "LOW", "LOW", "LOW", "LOW", "LOW"]


def test_gap_tolerance_disabled() -> None:
    """Test that gap_tolerance=0 disables the feature."""
    intervals = [
        {"rating_level": "LOW"},
        {"rating_level": "NORMAL"},
        {"rating_level": "LOW"},
    ]

    _apply_rating_gap_tolerance(intervals, gap_tolerance=0)

    # Should remain unchanged
    assert [i["rating_level"] for i in intervals] == ["LOW", "NORMAL", "LOW"]


def test_gap_tolerance_with_none_ratings() -> None:
    """Test that None ratings are skipped correctly."""
    intervals = [
        {"rating_level": None},  # Skipped
        {"rating_level": "LOW"},
        {"rating_level": "NORMAL"},
        {"rating_level": "LOW"},
        {"rating_level": None},  # Skipped
    ]

    _apply_rating_gap_tolerance(intervals, gap_tolerance=1)

    assert intervals[0]["rating_level"] is None
    assert intervals[1]["rating_level"] == "LOW"
    assert intervals[2]["rating_level"] == "LOW"  # Corrected
    assert intervals[3]["rating_level"] == "LOW"
    assert intervals[4]["rating_level"] is None


def test_gap_tolerance_high_rating_gaps() -> None:
    """Test gap tolerance for HIGH ratings."""
    intervals = [
        {"rating_level": "HIGH"},
        {"rating_level": "NORMAL"},  # Isolated
        {"rating_level": "HIGH"},
        {"rating_level": "HIGH"},
    ]

    _apply_rating_gap_tolerance(intervals, gap_tolerance=1)

    assert [i["rating_level"] for i in intervals] == ["HIGH", "HIGH", "HIGH", "HIGH"]
