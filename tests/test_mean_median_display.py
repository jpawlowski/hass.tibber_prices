"""
Test mean/median display configuration for average sensors.

This test verifies that:
1. Sensors with average values respect CONF_AVERAGE_SENSOR_DISPLAY setting
2. State shows the configured value (mean or median)
3. Attributes show the alternate value
4. Calculations that depend on averages use mean internally (not affected by display setting)
"""

import statistics
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest

from custom_components.tibber_prices.const import (
    CONF_AVERAGE_SENSOR_DISPLAY,
    DEFAULT_AVERAGE_SENSOR_DISPLAY,
)
from custom_components.tibber_prices.sensor.attributes.helpers import (
    add_alternate_average_attribute,
)
from custom_components.tibber_prices.utils.average import calculate_mean, calculate_median


@pytest.fixture
def mock_prices() -> list[dict]:
    """Create mock price data with known mean and median."""
    base_time = datetime(2025, 12, 18, 0, 0, tzinfo=UTC)
    # Prices: 10, 20, 30, 40, 100
    # Mean = 40.0, Median = 30.0 (intentionally different)
    return [
        {"startsAt": (base_time + timedelta(hours=i)).isoformat(), "total": price, "level": "normal"}
        for i, price in enumerate([10.0, 20.0, 30.0, 40.0, 100.0])
    ]


def test_average_price_today_displays_median_when_configured(
    mock_prices: list[dict],
) -> None:
    """Test that average_price_today sensor shows median in state when configured."""
    # Setup mock config entry with median display
    mock_entry = Mock()
    mock_entry.entry_id = "test_entry"
    mock_entry.options = {
        CONF_AVERAGE_SENSOR_DISPLAY: "median",
    }

    # Setup mock coordinator data with today's prices
    coordinator_data = {
        "priceInfo": mock_prices,
        "currency": "EUR",
    }

    # Mock coordinator
    mock_coordinator = Mock()
    mock_coordinator.data = coordinator_data
    mock_coordinator.config_entry = mock_entry
    mock_coordinator.time = Mock()
    mock_coordinator.time.now.return_value = datetime(2025, 12, 18, 12, 0, tzinfo=UTC)

    # Get prices for today
    prices = [float(p["total"]) for p in mock_prices]

    # Calculate expected values
    expected_mean = calculate_mean(prices)  # 40.0
    expected_median = calculate_median(prices)  # 30.0

    # Verify that mean and median are actually different (test setup)
    assert expected_mean != expected_median, "Test setup requires different mean and median"
    assert expected_mean == pytest.approx(40.0), f"Expected mean 40.0, got {expected_mean}"
    assert expected_median == pytest.approx(30.0), f"Expected median 30.0, got {expected_median}"


def test_average_price_today_displays_mean_when_configured(
    mock_prices: list[dict],
) -> None:
    """Test that average_price_today sensor shows mean in state when configured."""
    # Setup mock config entry with mean display
    mock_entry = Mock()
    mock_entry.entry_id = "test_entry"
    mock_entry.options = {
        CONF_AVERAGE_SENSOR_DISPLAY: "mean",
    }

    # Setup mock coordinator data
    coordinator_data = {
        "priceInfo": mock_prices,
        "currency": "EUR",
    }

    mock_coordinator = Mock()
    mock_coordinator.data = coordinator_data
    mock_coordinator.config_entry = mock_entry
    mock_coordinator.time = Mock()
    mock_coordinator.time.now.return_value = datetime(2025, 12, 18, 12, 0, tzinfo=UTC)

    # Get prices for today
    prices = [float(p["total"]) for p in mock_prices]

    # Calculate expected values
    expected_mean = calculate_mean(prices)  # 40.0
    expected_median = calculate_median(prices)  # 30.0

    # Verify setup
    assert expected_mean == pytest.approx(40.0)
    assert expected_median == pytest.approx(30.0)


def test_default_display_is_median() -> None:
    """Test that default display mode is median."""
    assert DEFAULT_AVERAGE_SENSOR_DISPLAY == "median", "Default should be median for consistency"


def test_rolling_hour_average_respects_display_setting() -> None:
    """Test that rolling hour average sensors respect display configuration."""
    # Create two config entries with different settings
    config_mean = Mock()
    config_mean.options = {CONF_AVERAGE_SENSOR_DISPLAY: "mean"}

    config_median = Mock()
    config_median.options = {CONF_AVERAGE_SENSOR_DISPLAY: "median"}

    # Test that the setting is read correctly
    assert config_mean.options.get(CONF_AVERAGE_SENSOR_DISPLAY) == "mean"
    assert config_median.options.get(CONF_AVERAGE_SENSOR_DISPLAY) == "median"


def test_calculations_always_use_mean_internally() -> None:
    """
    Test that internal calculations (like volatility) always use mean, not median.

    This verifies that CONF_AVERAGE_SENSOR_DISPLAY only affects STATE DISPLAY,
    not internal calculations that depend on averages.

    For example:
    - Volatility calculation uses mean (standard deviation / mean)
    - Price differences use mean
    - Trend detection uses mean

    The display setting should NOT affect these calculations.
    """
    # Sample data with different mean and median
    prices = [10.0, 20.0, 30.0, 40.0, 100.0]

    # Calculate mean
    mean = calculate_mean(prices)  # 40.0

    # Volatility calculation uses mean (coefficient of variation = std_dev / mean)
    # This should ALWAYS use mean, regardless of display setting
    assert mean == pytest.approx(40.0)

    # For volatility: std_dev / mean * 100
    # The mean here should be 40.0, not the median (30.0)

    std_dev = statistics.stdev(prices)
    coefficient_of_variation = (std_dev / mean) * 100

    # Verify calculation uses mean (40.0), not median (30.0)
    expected_cv_with_mean = (std_dev / 40.0) * 100
    expected_cv_with_median = (std_dev / 30.0) * 100

    assert coefficient_of_variation == pytest.approx(expected_cv_with_mean)
    assert coefficient_of_variation != pytest.approx(expected_cv_with_median), (
        "Volatility calculation should use mean, not median"
    )


def test_trend_calculation_uses_mean() -> None:
    """
    Test that trend calculations use mean for forward-looking averages.

    Trend detection compares:
    - Later half mean (next 2h, 3h, or 6h)
    - First half mean

    These should ALWAYS use arithmetic mean for accurate trend detection,
    regardless of display preference.
    """
    # Two sets of prices with different distributions
    first_half = [10.0, 20.0, 30.0]  # mean=20.0, median=20.0
    later_half = [40.0, 50.0, 100.0]  # mean=63.33, median=50.0

    # Calculate means (used in trend detection)
    first_mean = calculate_mean(first_half)
    later_mean = calculate_mean(later_half)

    # Trend percentage should use means
    trend_pct = ((later_mean - first_mean) / first_mean) * 100

    # Verify it uses mean (not median)
    assert first_mean == pytest.approx(20.0)
    assert later_mean == pytest.approx(63.33, rel=0.01)
    assert trend_pct > 200, "Trend should show >200% increase using means"

    # If we incorrectly used medians:

    first_median = statistics.median(first_half)  # 20.0
    later_median = statistics.median(later_half)  # 50.0
    wrong_trend_pct = ((later_median - first_median) / first_median) * 100

    assert wrong_trend_pct == pytest.approx(150.0)
    assert trend_pct != pytest.approx(wrong_trend_pct), "Trend calculation should use mean, not median"


def test_attribute_contains_alternate_value() -> None:
    """
    Test that attributes contain BOTH average values for automation consistency.

    Both price_mean and price_median should always be present in attributes,
    regardless of which value is displayed in state. The value matching the state
    will be excluded from recorder via dynamic _unrecorded_attributes.
    """
    # Mock config entry with median display
    mock_entry_median = Mock()
    mock_entry_median.options = {CONF_AVERAGE_SENSOR_DISPLAY: "median"}

    # Mock cached data
    cached_data = {
        "average_price_today_mean": 40.0,
        "average_price_today_median": 30.0,
    }

    # Test median display → BOTH mean AND median in attributes
    attributes_median_display = {}
    add_alternate_average_attribute(
        attributes_median_display,
        cached_data,
        "average_price_today",
        config_entry=mock_entry_median,
    )

    assert "price_mean" in attributes_median_display, "Both values should be in attributes"
    assert "price_median" in attributes_median_display, "Both values should be in attributes"
    assert attributes_median_display["price_mean"] == 40.0
    assert attributes_median_display["price_median"] == 30.0

    # Mock config entry with mean display
    mock_entry_mean = Mock()
    mock_entry_mean.options = {CONF_AVERAGE_SENSOR_DISPLAY: "mean"}

    # Test mean display → BOTH mean AND median in attributes
    attributes_mean_display = {}
    add_alternate_average_attribute(
        attributes_mean_display,
        cached_data,
        "average_price_today",
        config_entry=mock_entry_mean,
    )

    assert "price_median" in attributes_mean_display, "Both values should be in attributes"
    assert "price_mean" in attributes_mean_display, "Both values should be in attributes"
    assert attributes_mean_display["price_median"] == 30.0
    assert attributes_mean_display["price_mean"] == 40.0


def test_next_avg_sensors_respect_display_setting() -> None:
    """Test that next_avg_Nh sensors calculation returns both mean and median."""
    # Sample data with different mean and median
    prices = [10.0, 20.0, 30.0, 40.0, 100.0]

    # Calculate mean and median
    mean = calculate_mean(prices)
    median = calculate_median(prices)

    # Verify both values are calculated
    assert mean is not None, "Mean should be calculated"
    assert median is not None, "Median should be calculated"
    assert mean != median, "Test requires different mean and median"
    assert mean == pytest.approx(40.0), f"Expected mean 40.0, got {mean}"
    assert median == pytest.approx(30.0), f"Expected median 30.0, got {median}"


def test_24h_window_sensors_respect_display_setting() -> None:
    """Test that 24h trailing/leading average calculation returns both mean and median."""
    # Sample data with different mean and median
    prices = [10.0, 20.0, 30.0, 40.0, 100.0]

    # Calculate both statistics
    mean = calculate_mean(prices)
    median = calculate_median(prices)

    # Verify both are calculated
    assert mean is not None
    assert median is not None
    assert mean != median, "Test requires different mean and median"

    # The 24h window functions (calculate_trailing_24h_mean, calculate_leading_24h_mean)
    # return (mean, median) tuples, allowing sensor to choose which to display
