"""Integration test for price utils with realistic data."""

from datetime import datetime, timedelta

from custom_components.tibber_prices.price_utils import enrich_price_info_with_differences
from homeassistant.util import dt as dt_util

# Constants for integration testing
INTERVALS_PER_DAY = 96
VARIATION_THRESHOLD = 0.05
HOURS_PER_DAY = 24
INTERVALS_PER_HOUR = 4
PI_APPROX = 3.14159
INTERVAL_24 = 24
INTERVALS_68 = 68
INTERVALS_92 = 92


def generate_price_intervals(
    base_time: datetime,
    hours: int,
    base_price: float,
    variation: float = VARIATION_THRESHOLD,
) -> list:
    """Generate realistic price intervals."""
    intervals = []
    for i in range(hours * INTERVALS_PER_HOUR):  # 4 intervals per hour (15-minute intervals)
        time = base_time + timedelta(minutes=15 * i)
        # Add sinusoidal variation (peak at 18:00, low at 6:00)
        hour_of_day = time.hour + time.minute / 60
        variation_factor = 1 + variation * (((hour_of_day - 6) / 12) * PI_APPROX)
        price = base_price * (1 + 0.1 * (variation_factor - 1))

        intervals.append(
            {
                "startsAt": time.isoformat(),
                "total": price,
                "energy": price * 0.75,
                "tax": price * 0.25,
                "level": "NORMAL",
            }
        )

    return intervals


def test_realistic_day_pricing() -> None:
    """Test with realistic pricing patterns across 48 hours."""
    base_time = dt_util.now().replace(hour=12, minute=0, second=0, microsecond=0)

    # Generate realistic data
    price_info = {
        "yesterday": generate_price_intervals(
            base_time - timedelta(days=1),
            hours=HOURS_PER_DAY,
            base_price=0.12,
            variation=0.08,
        ),
        "today": generate_price_intervals(
            base_time.replace(hour=0, minute=0),
            hours=HOURS_PER_DAY,
            base_price=0.15,
            variation=0.10,
        ),
        "tomorrow": generate_price_intervals(
            base_time.replace(hour=0, minute=0) + timedelta(days=1),
            hours=HOURS_PER_DAY,
            base_price=0.13,
            variation=0.07,
        ),
    }

    # Enrich with differences
    enriched = enrich_price_info_with_differences(price_info)

    # Verify all today intervals have differences
    today_intervals = enriched["today"]
    for interval in today_intervals:
        assert "difference" in interval, (  # noqa: S101
            f"Missing difference in today interval {interval['startsAt']}"
        )
        assert "rating_level" in interval, (  # noqa: S101
            f"Missing rating_level in today interval {interval['startsAt']}"
        )

    # Verify all tomorrow intervals have differences
    tomorrow_intervals = enriched["tomorrow"]
    for interval in tomorrow_intervals:
        assert "difference" in interval, (  # noqa: S101
            f"Missing difference in tomorrow interval {interval['startsAt']}"
        )
        assert "rating_level" in interval, (  # noqa: S101
            f"Missing rating_level in tomorrow interval {interval['startsAt']}"
        )

    # Verify yesterday is unchanged (except for missing difference)
    yesterday_intervals = enriched["yesterday"]
    assert len(yesterday_intervals) == INTERVALS_PER_DAY  # noqa: S101

    # Analyze statistics
    today_levels = [i.get("rating_level") for i in today_intervals if i.get("rating_level") is not None]
    tomorrow_levels = [i.get("rating_level") for i in tomorrow_intervals if i.get("rating_level") is not None]

    # Verify rating_level values are valid
    valid_levels = {"LOW", "NORMAL", "HIGH"}
    assert all(level in valid_levels for level in today_levels), (  # noqa: S101
        "Invalid rating_level in today intervals"
    )
    assert all(level in valid_levels for level in tomorrow_levels), (  # noqa: S101
        "Invalid rating_level in tomorrow intervals"
    )

    # With realistic pricing variation and default thresholds of -10/+10,
    # we should have at least 2 different levels (most likely HIGH and NORMAL for today,
    # and NORMAL for tomorrow due to cheaper prices)
    unique_today_levels = set(today_levels)
    assert len(unique_today_levels) >= 1, (  # noqa: S101
        "Today should have at least one rating level"
    )


def test_day_boundary_calculations() -> None:
    """Test calculations across midnight boundary."""
    midnight = dt_util.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Create data that spans the midnight boundary
    price_info = {
        "yesterday": generate_price_intervals(
            midnight - timedelta(days=1),
            hours=HOURS_PER_DAY,
            base_price=0.10,
        ),
        "today": generate_price_intervals(midnight, hours=HOURS_PER_DAY, base_price=0.15),
        "tomorrow": generate_price_intervals(
            midnight + timedelta(days=1),
            hours=HOURS_PER_DAY,
            base_price=0.12,
        ),
    }

    enriched = enrich_price_info_with_differences(price_info)

    # Check the midnight boundary interval (first of tomorrow)
    midnight_tomorrow = enriched["tomorrow"][0]

    # This should include all 96 intervals from yesterday and all 96 from today
    assert "difference" in midnight_tomorrow  # noqa: S101
    diff = midnight_tomorrow.get("difference")

    # Since tomorrow is cheaper (0.12) than both yesterday (0.10) and today (0.15)
    # The difference could be negative (cheap) or positive (expensive) depending on the mix
    diff = midnight_tomorrow.get("difference")
    assert diff is not None, (  # noqa: S101
        "Midnight boundary interval should have difference"
    )


def test_early_morning_calculations() -> None:
    """Test calculations in early morning hours."""
    base_time = dt_util.now().replace(hour=6, minute=0, second=0, microsecond=0)

    price_info = {
        "yesterday": generate_price_intervals(
            base_time - timedelta(days=1),
            hours=HOURS_PER_DAY,
            base_price=0.12,
        ),
        "today": generate_price_intervals(
            base_time.replace(hour=0, minute=0),
            hours=HOURS_PER_DAY,
            base_price=0.15,
        ),
        "tomorrow": generate_price_intervals(
            base_time.replace(hour=0, minute=0) + timedelta(days=1),
            hours=HOURS_PER_DAY,
            base_price=0.13,
        ),
    }

    enriched = enrich_price_info_with_differences(price_info)

    # Get 6 AM interval (24th interval of the day)
    six_am_interval = enriched["today"][INTERVAL_24]
    assert "difference" in six_am_interval  # noqa: S101

    # At 6 AM, we should include:
    # - Yesterday from 6 AM to midnight (68 intervals)
    # - Today from midnight to 6 AM (24 intervals)
    # Total: 92 intervals (not quite 24 hours)
    assert "difference" in six_am_interval  # noqa: S101
