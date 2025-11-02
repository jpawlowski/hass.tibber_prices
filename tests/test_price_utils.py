"""Test price utils calculations."""

from datetime import timedelta

from custom_components.tibber_prices.price_utils import (
    calculate_difference_percentage,
    calculate_rating_level,
    calculate_trailing_average_for_interval,
    enrich_price_info_with_differences,
)
from homeassistant.util import dt as dt_util


def test_calculate_trailing_average_for_interval() -> None:
    """Test trailing average calculation for a specific interval."""
    # Create sample price data spanning 24 hours
    base_time = dt_util.now().replace(hour=12, minute=0, second=0, microsecond=0)

    prices = []
    # Create 96 quarter-hourly intervals (24 hours worth)
    for i in range(96):
        price_time = base_time - timedelta(hours=24) + timedelta(minutes=15 * i)
        prices.append(
            {
                "startsAt": price_time.isoformat(),
                "total": 0.1 + (i * 0.001),  # Incrementing price
            }
        )

    # Test interval at current time (should average last 24 hours)
    test_time = base_time
    average = calculate_trailing_average_for_interval(test_time, prices)

    assert average is not None
    # Average of 96 prices from 0.1 to 0.195 (0.1 + 95*0.001)
    expected_avg = (0.1 + 0.195) / 2  # ~0.1475
    assert abs(average - expected_avg) < 0.001


def test_calculate_difference_percentage() -> None:
    """Test difference percentage calculation."""
    current = 0.15
    average = 0.10

    diff = calculate_difference_percentage(current, average)
    assert diff is not None
    assert abs(diff - 50.0) < 0.01  # 50% higher than average

    # Test with same price
    diff = calculate_difference_percentage(0.10, 0.10)
    assert diff == 0.0

    # Test with None average
    diff = calculate_difference_percentage(0.15, None)
    assert diff is None

    # Test with zero average
    diff = calculate_difference_percentage(0.15, 0.0)
    assert diff is None


def test_enrich_price_info_with_differences() -> None:
    """Test enriching price info with difference values."""
    base_time = dt_util.now().replace(hour=12, minute=0, second=0, microsecond=0)

    # Create mock price data covering 48 hours
    price_info = {
        "yesterday": [],
        "today": [],
        "tomorrow": [],
    }

    # Fill yesterday with constant price
    for i in range(96):  # 96 intervals = 24 hours
        price_time = base_time - timedelta(days=1) + timedelta(minutes=15 * i)
        price_info["yesterday"].append(
            {
                "startsAt": price_time.isoformat(),
                "total": 0.10,
            }
        )

    # Add one interval for today
    price_info["today"].append(
        {
            "startsAt": base_time.isoformat(),
            "total": 0.15,
        }
    )

    # Add one interval for tomorrow
    price_info["tomorrow"].append(
        {
            "startsAt": (base_time + timedelta(days=1)).isoformat(),
            "total": 0.12,
        }
    )

    enriched = enrich_price_info_with_differences(price_info)

    # Today's price should have a difference calculated
    assert "difference" in enriched["today"][0]
    assert enriched["today"][0]["difference"] is not None
    # 0.15 vs average of 0.10 = 50% higher
    assert abs(enriched["today"][0]["difference"] - 50.0) < 1.0

    # Today's price should also have a rating_level (50% > 10% threshold = HIGH)
    assert "rating_level" in enriched["today"][0]
    assert enriched["today"][0]["rating_level"] == "HIGH"

    # Tomorrow's price should also have a difference
    assert "difference" in enriched["tomorrow"][0]
    assert enriched["tomorrow"][0]["difference"] is not None

    # Tomorrow's price should have a rating_level
    # The average will be pulled from yesterday (0.10) and today (0.15)
    # With tomorrow price at 0.12, it should be close to NORMAL or LOW
    assert "rating_level" in enriched["tomorrow"][0]
    rating_level_tomorrow = enriched["tomorrow"][0]["rating_level"]
    assert rating_level_tomorrow in {"LOW", "NORMAL"}


def test_calculate_rating_level() -> None:
    """Test rating level calculation based on difference percentage and thresholds."""
    threshold_low = -10
    threshold_high = 10

    # Test LOW threshold
    level = calculate_rating_level(-15.0, threshold_low, threshold_high)
    assert level == "LOW"

    # Test exact low threshold
    level = calculate_rating_level(-10.0, threshold_low, threshold_high)
    assert level == "LOW"

    # Test HIGH threshold
    level = calculate_rating_level(15.0, threshold_low, threshold_high)
    assert level == "HIGH"

    # Test exact high threshold
    level = calculate_rating_level(10.0, threshold_low, threshold_high)
    assert level == "HIGH"

    # Test NORMAL (between thresholds)
    level = calculate_rating_level(0.0, threshold_low, threshold_high)
    assert level == "NORMAL"

    level = calculate_rating_level(5.0, threshold_low, threshold_high)
    assert level == "NORMAL"

    level = calculate_rating_level(-5.0, threshold_low, threshold_high)
    assert level == "NORMAL"

    # Test None difference
    level = calculate_rating_level(None, threshold_low, threshold_high)
    assert level is None

    # Test edge case: difference in both ranges (both ranges simultaneously)
    # This shouldn't normally happen, but if low > high, return NORMAL
    level = calculate_rating_level(5.0, 10, -10)  # inverted thresholds
    assert level == "NORMAL"


if __name__ == "__main__":
    test_calculate_trailing_average_for_interval()
    test_calculate_difference_percentage()
    test_enrich_price_info_with_differences()
    test_calculate_rating_level()
