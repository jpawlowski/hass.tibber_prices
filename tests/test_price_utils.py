"""Test price utils calculations."""

from datetime import timedelta

from custom_components.tibber_prices.price_utils import (
    calculate_difference_percentage,
    calculate_rating_level,
    calculate_trailing_average_for_interval,
    enrich_price_info_with_differences,
)
from homeassistant.util import dt as dt_util

# Constants for testing
TOLERANCE_PERCENT = 0.001
TOLERANCE_DIFF = 0.01
PERCENT_50 = 50.0
PERCENT_1 = 1.0
INTERVALS_PER_DAY = 96
BASE_PRICE = 0.10
NEXT_PRICE = 0.15
TOMORROW_PRICE = 0.12
THRESHOLD_LOW = -10
THRESHOLD_HIGH = 10


def test_calculate_trailing_average_for_interval() -> None:
    """Test trailing average calculation for a specific interval."""
    # Create sample price data spanning 24 hours
    base_time = dt_util.now().replace(hour=12, minute=0, second=0, microsecond=0)

    prices = []
    # Create 96 quarter-hourly intervals (24 hours worth)
    for i in range(INTERVALS_PER_DAY):
        price_time = base_time - timedelta(hours=24) + timedelta(minutes=15 * i)
        prices.append(
            {
                "startsAt": price_time.isoformat(),
                "total": BASE_PRICE + (i * 0.001),  # Incrementing price
            }
        )

    # Test interval at current time (should average last 24 hours)
    test_time = base_time
    average = calculate_trailing_average_for_interval(test_time, prices)

    assert average is not None  # noqa: S101
    # Average of 96 prices from 0.1 to 0.195 (0.1 + 95*0.001)
    expected_avg = (BASE_PRICE + 0.195) / 2  # ~0.1475
    assert abs(average - expected_avg) < TOLERANCE_PERCENT  # noqa: S101


def test_calculate_difference_percentage() -> None:
    """Test difference percentage calculation."""
    current = NEXT_PRICE
    average = BASE_PRICE

    diff = calculate_difference_percentage(current, average)
    assert diff is not None  # noqa: S101
    assert abs(diff - PERCENT_50) < TOLERANCE_DIFF  # noqa: S101

    # Test with same price
    diff = calculate_difference_percentage(BASE_PRICE, BASE_PRICE)
    assert diff == 0.0  # noqa: S101

    # Test with None average
    diff = calculate_difference_percentage(NEXT_PRICE, None)
    assert diff is None  # noqa: S101

    # Test with zero average
    diff = calculate_difference_percentage(NEXT_PRICE, 0.0)
    assert diff is None  # noqa: S101


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
    for i in range(INTERVALS_PER_DAY):  # 96 intervals = 24 hours
        price_time = base_time - timedelta(days=1) + timedelta(minutes=15 * i)
        price_info["yesterday"].append(
            {
                "startsAt": price_time.isoformat(),
                "total": BASE_PRICE,
            }
        )

    # Add one interval for today
    price_info["today"].append(
        {
            "startsAt": base_time.isoformat(),
            "total": NEXT_PRICE,
        }
    )

    # Add one interval for tomorrow
    price_info["tomorrow"].append(
        {
            "startsAt": (base_time + timedelta(days=1)).isoformat(),
            "total": TOMORROW_PRICE,
        }
    )

    enriched = enrich_price_info_with_differences(price_info)

    # Today's price should have a difference calculated
    assert "difference" in enriched["today"][0]  # noqa: S101
    assert enriched["today"][0]["difference"] is not None  # noqa: S101
    # 0.15 vs average of 0.10 = 50% higher
    assert abs(enriched["today"][0]["difference"] - PERCENT_50) < PERCENT_1  # noqa: S101

    # Today's price should also have a rating_level (50% > 10% threshold = HIGH)
    assert "rating_level" in enriched["today"][0]  # noqa: S101
    assert enriched["today"][0]["rating_level"] == "HIGH"  # noqa: S101

    # Tomorrow's price should also have a difference
    assert "difference" in enriched["tomorrow"][0]  # noqa: S101
    assert enriched["tomorrow"][0]["difference"] is not None  # noqa: S101

    # Tomorrow's price should have a rating_level
    # The average will be pulled from yesterday (0.10) and today (0.15)
    # With tomorrow price at 0.12, it should be close to NORMAL or LOW
    assert "rating_level" in enriched["tomorrow"][0]  # noqa: S101
    rating_level_tomorrow = enriched["tomorrow"][0]["rating_level"]
    assert rating_level_tomorrow in {"LOW", "NORMAL"}  # noqa: S101


def test_calculate_rating_level() -> None:
    """Test rating level calculation based on difference percentage and thresholds."""
    # Test LOW threshold
    level = calculate_rating_level(-15.0, THRESHOLD_LOW, THRESHOLD_HIGH)
    assert level == "LOW"  # noqa: S101

    # Test exact low threshold
    level = calculate_rating_level(-10.0, THRESHOLD_LOW, THRESHOLD_HIGH)
    assert level == "LOW"  # noqa: S101

    # Test HIGH threshold
    level = calculate_rating_level(15.0, THRESHOLD_LOW, THRESHOLD_HIGH)
    assert level == "HIGH"  # noqa: S101

    # Test exact high threshold
    level = calculate_rating_level(10.0, THRESHOLD_LOW, THRESHOLD_HIGH)
    assert level == "HIGH"  # noqa: S101

    # Test NORMAL (between thresholds)
    level = calculate_rating_level(0.0, THRESHOLD_LOW, THRESHOLD_HIGH)
    assert level == "NORMAL"  # noqa: S101

    level = calculate_rating_level(5.0, THRESHOLD_LOW, THRESHOLD_HIGH)
    assert level == "NORMAL"  # noqa: S101

    level = calculate_rating_level(-5.0, THRESHOLD_LOW, THRESHOLD_HIGH)
    assert level == "NORMAL"  # noqa: S101

    # Test None difference
    level = calculate_rating_level(None, THRESHOLD_LOW, THRESHOLD_HIGH)
    assert level is None  # noqa: S101

    # Test edge case: difference in both ranges (both ranges simultaneously)
    # This shouldn't normally happen, but if low > high, return NORMAL
    level = calculate_rating_level(5.0, 10, -10)  # inverted thresholds
    assert level == "NORMAL"  # noqa: S101


if __name__ == "__main__":
    test_calculate_trailing_average_for_interval()
    test_calculate_difference_percentage()
    test_enrich_price_info_with_differences()
    test_calculate_rating_level()
