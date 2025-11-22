"""Tests for Bug #7: Min/Max functions returning 0.0 instead of None."""

from datetime import UTC, datetime, timedelta

import pytest

from custom_components.tibber_prices.coordinator.time_service import (
    TibberPricesTimeService,
)
from custom_components.tibber_prices.utils.average import (
    calculate_leading_24h_max,
    calculate_leading_24h_min,
    calculate_trailing_24h_max,
    calculate_trailing_24h_min,
)


@pytest.fixture
def time_service() -> TibberPricesTimeService:
    """Create a TibberPricesTimeService instance for testing."""
    return TibberPricesTimeService()


def test_trailing_24h_min_with_empty_window(time_service: TibberPricesTimeService) -> None:
    """
    Test that trailing min returns None when no data in window.

    Bug #7: Previously returned 0.0, which could be misinterpreted as
    a maximum value with negative prices.
    """
    # Data exists, but outside the 24h window
    old_data = [
        {
            "startsAt": datetime(2025, 11, 1, 10, 0, tzinfo=UTC),  # 20 days ago
            "total": -15.0,  # Negative price
        }
    ]

    interval_start = datetime(2025, 11, 21, 14, 0, tzinfo=UTC)  # Today

    # Should return None (no data in window), not 0.0
    result = calculate_trailing_24h_min(old_data, interval_start, time=time_service)
    assert result is None


def test_trailing_24h_max_with_empty_window(time_service: TibberPricesTimeService) -> None:
    """Test that trailing max returns None when no data in window."""
    old_data = [
        {
            "startsAt": datetime(2025, 11, 1, 10, 0, tzinfo=UTC),  # 20 days ago
            "total": -15.0,
        }
    ]

    interval_start = datetime(2025, 11, 21, 14, 0, tzinfo=UTC)

    result = calculate_trailing_24h_max(old_data, interval_start, time=time_service)
    assert result is None


def test_leading_24h_min_with_empty_window(time_service: TibberPricesTimeService) -> None:
    """Test that leading min returns None when no data in window."""
    old_data = [
        {
            "startsAt": datetime(2025, 11, 1, 10, 0, tzinfo=UTC),  # Past data
            "total": -15.0,
        }
    ]

    interval_start = datetime(2025, 11, 21, 14, 0, tzinfo=UTC)  # Today - no future data

    result = calculate_leading_24h_min(old_data, interval_start, time=time_service)
    assert result is None


def test_leading_24h_max_with_empty_window(time_service: TibberPricesTimeService) -> None:
    """Test that leading max returns None when no data in window."""
    old_data = [
        {
            "startsAt": datetime(2025, 11, 1, 10, 0, tzinfo=UTC),  # Past data
            "total": -15.0,
        }
    ]

    interval_start = datetime(2025, 11, 21, 14, 0, tzinfo=UTC)

    result = calculate_leading_24h_max(old_data, interval_start, time=time_service)
    assert result is None


def test_trailing_24h_min_with_negative_prices(time_service: TibberPricesTimeService) -> None:
    """
    Test trailing min with negative prices returns actual minimum, not 0.0.

    This demonstrates why Bug #7 was critical: with negative prices,
    0.0 would appear to be a maximum, not an error indicator.
    """
    interval_start = datetime(2025, 11, 21, 14, 0, tzinfo=UTC)
    window_start = interval_start - timedelta(hours=24)

    # All negative prices
    data = [{"startsAt": window_start + timedelta(hours=i), "total": -10.0 - i} for i in range(24)]

    result = calculate_trailing_24h_min(data, interval_start, time=time_service)

    # Should return actual minimum (-33.0), not 0.0
    assert result == -33.0
    assert result != 0.0  # Emphasize this was the bug


def test_trailing_24h_max_with_negative_prices(time_service: TibberPricesTimeService) -> None:
    """Test trailing max with negative prices."""
    interval_start = datetime(2025, 11, 21, 14, 0, tzinfo=UTC)
    window_start = interval_start - timedelta(hours=24)

    # All negative prices
    data = [{"startsAt": window_start + timedelta(hours=i), "total": -10.0 - i} for i in range(24)]

    result = calculate_trailing_24h_max(data, interval_start, time=time_service)

    # Maximum of negative numbers is least negative
    assert result == -10.0


def test_trailing_24h_min_distinguishes_zero_from_none(
    time_service: TibberPricesTimeService,
) -> None:
    """
    Test that function distinguishes between 0.0 price and no data.

    Bug #7: Previously, both cases returned 0.0, making them indistinguishable.
    """
    interval_start = datetime(2025, 11, 21, 14, 0, tzinfo=UTC)
    window_start = interval_start - timedelta(hours=24)

    # Case 1: Price is actually 0.0
    data_with_zero = [{"startsAt": window_start + timedelta(hours=i), "total": 0.0 + i} for i in range(24)]

    result_with_zero = calculate_trailing_24h_min(data_with_zero, interval_start, time=time_service)
    assert result_with_zero == 0.0  # Actual price

    # Case 2: No data in window
    empty_data: list[dict] = []

    result_no_data = calculate_trailing_24h_min(empty_data, interval_start, time=time_service)
    assert result_no_data is None  # No data

    # CRITICAL: These must be distinguishable!
    assert result_with_zero != result_no_data


def test_trailing_24h_functions_with_partial_window(
    time_service: TibberPricesTimeService,
) -> None:
    """
    Test that functions work correctly with partial 24h window.

    This tests the edge case where data exists but doesn't cover full 24h.
    """
    interval_start = datetime(2025, 11, 21, 14, 0, tzinfo=UTC)
    window_start = interval_start - timedelta(hours=24)

    # Only 12 hours of data (half the window)
    data = [{"startsAt": window_start + timedelta(hours=i), "total": float(i)} for i in range(12)]

    result_min = calculate_trailing_24h_min(data, interval_start, time=time_service)
    result_max = calculate_trailing_24h_max(data, interval_start, time=time_service)

    # Should calculate based on available data
    assert result_min == 0.0
    assert result_max == 11.0


def test_leading_24h_functions_with_negative_and_positive_mix(
    time_service: TibberPricesTimeService,
) -> None:
    """Test leading functions with mix of negative and positive prices."""
    interval_start = datetime(2025, 11, 21, 14, 0, tzinfo=UTC)

    # Mix of negative and positive prices
    data = [{"startsAt": interval_start + timedelta(hours=i), "total": -10.0 + i} for i in range(24)]

    result_min = calculate_leading_24h_min(data, interval_start, time=time_service)
    result_max = calculate_leading_24h_max(data, interval_start, time=time_service)

    assert result_min == -10.0  # Most negative
    assert result_max == 13.0  # Most positive


def test_empty_price_list_returns_none(time_service: TibberPricesTimeService) -> None:
    """Test that all functions return None with completely empty price list."""
    interval_start = datetime(2025, 11, 21, 14, 0, tzinfo=UTC)
    empty_data: list[dict] = []

    assert calculate_trailing_24h_min(empty_data, interval_start, time=time_service) is None
    assert calculate_trailing_24h_max(empty_data, interval_start, time=time_service) is None
    assert calculate_leading_24h_min(empty_data, interval_start, time=time_service) is None
    assert calculate_leading_24h_max(empty_data, interval_start, time=time_service) is None
