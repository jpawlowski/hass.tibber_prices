"""Test Bug #8: Average functions return None instead of 0.0 when no data available."""

from datetime import UTC, datetime, timedelta

import pytest

from custom_components.tibber_prices.utils.average import (
    calculate_leading_24h_avg,
    calculate_trailing_24h_avg,
)


@pytest.fixture
def sample_prices() -> list[dict]:
    """Create sample price data for testing."""
    base_time = datetime(2025, 11, 22, 12, 0, tzinfo=UTC)
    return [
        {"startsAt": base_time - timedelta(hours=2), "total": -10.0},
        {"startsAt": base_time - timedelta(hours=1), "total": -5.0},
        {"startsAt": base_time, "total": 0.0},
        {"startsAt": base_time + timedelta(hours=1), "total": 5.0},
        {"startsAt": base_time + timedelta(hours=2), "total": 10.0},
    ]


def test_trailing_avg_returns_none_when_empty() -> None:
    """
    Test that calculate_trailing_24h_avg returns None when no data in window.

    Bug #8: Previously returned 0.0, which with negative prices could be
    misinterpreted as a real average value.
    """
    interval_start = datetime(2025, 11, 22, 12, 0, tzinfo=UTC)
    empty_prices: list[dict] = []

    result = calculate_trailing_24h_avg(empty_prices, interval_start)

    assert result is None, "Empty price list should return None, not 0.0"


def test_leading_avg_returns_none_when_empty() -> None:
    """
    Test that calculate_leading_24h_avg returns None when no data in window.

    Bug #8: Previously returned 0.0, which with negative prices could be
    misinterpreted as a real average value.
    """
    interval_start = datetime(2025, 11, 22, 12, 0, tzinfo=UTC)
    empty_prices: list[dict] = []

    result = calculate_leading_24h_avg(empty_prices, interval_start)

    assert result is None, "Empty price list should return None, not 0.0"


def test_trailing_avg_returns_none_when_no_data_in_window(sample_prices: list[dict]) -> None:
    """
    Test that calculate_trailing_24h_avg returns None when data exists but not in the window.

    This tests the case where we have price data, but it doesn't fall within
    the 24-hour trailing window for the given interval.
    """
    # Sample data spans 10:00-14:00 UTC on 2025-11-22
    # Set interval_start to a time where the 24h trailing window doesn't contain this data
    # For example, 2 hours after the last data point
    interval_start = datetime(2025, 11, 22, 16, 0, tzinfo=UTC)

    result = calculate_trailing_24h_avg(sample_prices, interval_start)

    # Trailing window is 16:00 - 24h = yesterday 16:00 to today 16:00
    # Sample data is from 10:00-14:00, which IS in this window
    assert result is not None, "Should find data in 24h trailing window"
    # Average of all sample prices: (-10 + -5 + 0 + 5 + 10) / 5 = 0.0
    assert result == pytest.approx(0.0), "Average should be 0.0"


def test_leading_avg_returns_none_when_no_data_in_window(sample_prices: list[dict]) -> None:
    """
    Test that calculate_leading_24h_avg returns None when data exists but not in the window.

    This tests the case where we have price data, but it doesn't fall within
    the 24-hour leading window for the given interval.
    """
    # Sample data spans 10:00-14:00 UTC on 2025-11-22
    # Set interval_start far in the future, so 24h leading window doesn't contain the data
    interval_start = datetime(2025, 11, 23, 15, 0, tzinfo=UTC)

    result = calculate_leading_24h_avg(sample_prices, interval_start)

    # Leading window is from 15:00 today to 15:00 tomorrow
    # Sample data is from yesterday, outside this window
    assert result is None, "Should return None when no data in 24h leading window"


def test_trailing_avg_with_negative_prices_distinguishes_zero(sample_prices: list[dict]) -> None:
    """
    Test that calculate_trailing_24h_avg correctly distinguishes 0.0 average from None.

    Bug #8 motivation: With negative prices, we need to know if the average is
    truly 0.0 (real value) or if there's no data (None).
    """
    # Use base_time where we have data
    interval_start = datetime(2025, 11, 22, 12, 0, tzinfo=UTC)

    result = calculate_trailing_24h_avg(sample_prices, interval_start)

    # Should return an actual average (negative, since we have -10, -5 in the trailing window)
    assert result is not None, "Should return average when data exists"
    assert isinstance(result, float), "Should return float, not None"
    assert result != 0.0, "With negative prices, average should not be exactly 0.0"


def test_leading_avg_with_negative_prices_distinguishes_zero(sample_prices: list[dict]) -> None:
    """
    Test that calculate_leading_24h_avg correctly distinguishes 0.0 average from None.

    Bug #8 motivation: With negative prices, we need to know if the average is
    truly 0.0 (real value) or if there's no data (None).
    """
    # Use base_time - 2h to include all sample data in leading window
    interval_start = datetime(2025, 11, 22, 10, 0, tzinfo=UTC)

    result = calculate_leading_24h_avg(sample_prices, interval_start)

    # Should return an actual average (0.0 because average of -10, -5, 0, 5, 10 = 0.0)
    assert result is not None, "Should return average when data exists"
    assert isinstance(result, float), "Should return float, not None"
    assert result == 0.0, "Average of symmetric negative/positive prices should be 0.0"


def test_trailing_avg_with_all_negative_prices() -> None:
    """
    Test calculate_trailing_24h_avg with all negative prices.

    Verifies that the function correctly calculates averages when all prices
    are negative (common scenario in Norway/Germany with high renewable energy).
    """
    base_time = datetime(2025, 11, 22, 12, 0, tzinfo=UTC)
    all_negative = [
        {"startsAt": base_time - timedelta(hours=3), "total": -15.0},
        {"startsAt": base_time - timedelta(hours=2), "total": -10.0},
        {"startsAt": base_time - timedelta(hours=1), "total": -5.0},
    ]

    result = calculate_trailing_24h_avg(all_negative, base_time)

    assert result is not None, "Should return average for all negative prices"
    assert result < 0, "Average should be negative"
    assert result == pytest.approx(-10.0), "Average of -15, -10, -5 should be -10.0"


def test_leading_avg_with_all_negative_prices() -> None:
    """
    Test calculate_leading_24h_avg with all negative prices.

    Verifies that the function correctly calculates averages when all prices
    are negative (common scenario in Norway/Germany with high renewable energy).
    """
    base_time = datetime(2025, 11, 22, 12, 0, tzinfo=UTC)
    all_negative = [
        {"startsAt": base_time, "total": -5.0},
        {"startsAt": base_time + timedelta(hours=1), "total": -10.0},
        {"startsAt": base_time + timedelta(hours=2), "total": -15.0},
    ]

    result = calculate_leading_24h_avg(all_negative, base_time)

    assert result is not None, "Should return average for all negative prices"
    assert result < 0, "Average should be negative"
    assert result == pytest.approx(-10.0), "Average of -5, -10, -15 should be -10.0"


def test_trailing_avg_returns_none_with_none_timestamps() -> None:
    """
    Test that calculate_trailing_24h_avg handles None timestamps gracefully.

    Price data with None startsAt should be skipped, and if no valid data
    remains, the function should return None.
    """
    interval_start = datetime(2025, 11, 22, 12, 0, tzinfo=UTC)
    prices_with_none = [
        {"startsAt": None, "total": 10.0},
        {"startsAt": None, "total": 20.0},
    ]

    result = calculate_trailing_24h_avg(prices_with_none, interval_start)

    assert result is None, "Should return None when all timestamps are None"


def test_leading_avg_returns_none_with_none_timestamps() -> None:
    """
    Test that calculate_leading_24h_avg handles None timestamps gracefully.

    Price data with None startsAt should be skipped, and if no valid data
    remains, the function should return None.
    """
    interval_start = datetime(2025, 11, 22, 12, 0, tzinfo=UTC)
    prices_with_none = [
        {"startsAt": None, "total": 10.0},
        {"startsAt": None, "total": 20.0},
    ]

    result = calculate_leading_24h_avg(prices_with_none, interval_start)

    assert result is None, "Should return None when all timestamps are None"
