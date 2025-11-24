"""
Comprehensive tests for price calculations with positive, negative, and zero prices.

This test file uses parametrized tests to ensure all calculation functions
handle ALL price scenarios correctly:
- Positive prices (normal operation)
- Negative prices (Norway/Germany renewable surplus)
- Zero prices (rare but possible edge case)
- Mixed scenarios (transitions, extreme volatility)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from custom_components.tibber_prices.coordinator.time_service import (
    TibberPricesTimeService,
)
from custom_components.tibber_prices.utils.price import (
    aggregate_period_levels,
    aggregate_period_ratings,
    aggregate_price_levels,
    aggregate_price_rating,
    calculate_difference_percentage,
    calculate_rating_level,
    calculate_trailing_average_for_interval,
    calculate_volatility_level,
    enrich_price_info_with_differences,
)

# =============================================================================
# Volatility Calculation (Coefficient of Variation) - Parametrized
# =============================================================================


@pytest.mark.parametrize(
    ("prices", "expected_level", "description"),
    [
        # Positive prices - LOW volatility
        ([10.0, 11.0, 10.5, 10.2], "LOW", "stable positive prices"),
        # Negative prices - LOW volatility
        ([-10.0, -11.0, -10.5, -10.2], "LOW", "stable negative prices"),
        # Zero and near-zero - VERY_HIGH volatility (CV explodes with mean near zero)
        ([0.0, 0.1, -0.1, 0.05], "VERY_HIGH", "prices near zero (extreme CV)"),
        # Positive prices - MODERATE volatility
        ([10.0, 15.0, 12.0, 13.0], "MODERATE", "moderate positive variation"),
        # Negative prices - MODERATE volatility
        ([-10.0, -15.0, -12.0, -13.0], "MODERATE", "moderate negative variation"),
        # Mixed crossing zero - VERY_HIGH volatility (mean near zero → extreme CV)
        ([-2.0, 0.0, 2.0, 1.0], "VERY_HIGH", "mixed prices crossing zero (extreme CV)"),
        # Positive prices - HIGH volatility
        ([10.0, 20.0, 12.0, 18.0], "HIGH", "high positive variation"),
        # Negative prices - HIGH volatility
        ([-10.0, -20.0, -12.0, -18.0], "HIGH", "high negative variation"),
        # Mixed with larger spread - VERY_HIGH volatility (mean near zero)
        ([-5.0, 5.0, -3.0, 4.0], "VERY_HIGH", "high mixed variation (mean near zero)"),
        # Positive prices - VERY_HIGH volatility
        ([10.0, 40.0, 15.0, 35.0], "VERY_HIGH", "very high positive variation"),
        # Negative prices - VERY_HIGH volatility
        ([-10.0, -40.0, -15.0, -35.0], "VERY_HIGH", "very high negative variation"),
        # Extreme mixed
        ([-20.0, 20.0, -15.0, 18.0], "VERY_HIGH", "extreme mixed variation"),
    ],
)
def test_volatility_level_scenarios(
    prices: list[float],
    expected_level: str,
    description: str,
) -> None:
    """Test volatility calculation across positive, negative, and mixed price scenarios."""
    level = calculate_volatility_level(prices)
    assert level == expected_level, f"Failed for {description}: expected {expected_level}, got {level}"


@pytest.mark.parametrize(
    ("prices", "expected_level", "description"),
    [
        # Edge cases
        ([10.0], "LOW", "single positive value"),
        ([-10.0], "LOW", "single negative value"),
        ([0.0], "LOW", "single zero value"),
        ([], "LOW", "empty list"),
        ([0.0, 0.0, 0.0], "LOW", "all zeros (no variation)"),
        ([-5.0, -5.0], "LOW", "identical negative prices"),
    ],
)
def test_volatility_level_edge_cases(
    prices: list[float],
    expected_level: str,
    description: str,
) -> None:
    """Test volatility edge cases that should always return LOW."""
    level = calculate_volatility_level(prices)
    assert level == expected_level, f"Failed for {description}"


def test_volatility_level_custom_thresholds() -> None:
    """Test volatility with custom thresholds works for all price types."""
    # Test positive prices
    positive_result = calculate_volatility_level(
        [10.0, 12.5, 11.0, 13.0],
        threshold_moderate=10.0,
        threshold_high=25.0,
        threshold_very_high=50.0,
    )
    assert positive_result == "MODERATE"

    # Test negative prices
    negative_result = calculate_volatility_level(
        [-10.0, -12.5, -11.0, -13.0],
        threshold_moderate=10.0,
        threshold_high=25.0,
        threshold_very_high=50.0,
    )
    assert negative_result == "MODERATE"


# =============================================================================
# Trailing Average Calculation - Parametrized
# =============================================================================


@pytest.mark.parametrize(
    ("price_value", "expected_avg", "description"),
    [
        (10.0, 10.0, "positive prices"),
        (-10.0, -10.0, "negative prices"),
        (0.0, 0.0, "zero prices"),
    ],
)
def test_trailing_average_full_24h_data(
    price_value: float,
    expected_avg: float,
    description: str,
) -> None:
    """Test trailing average with full 24h data across different price scenarios."""
    base_time = datetime(2025, 11, 22, 14, 30, 0, tzinfo=UTC)
    intervals = [
        {
            "startsAt": base_time - timedelta(hours=24) + timedelta(minutes=15 * i),
            "total": price_value,
        }
        for i in range(96)
    ]

    avg = calculate_trailing_average_for_interval(base_time, intervals)
    assert avg == pytest.approx(expected_avg, rel=1e-9), f"Failed for {description}"


def test_trailing_average_mixed_prices() -> None:
    """Test trailing average with mixed positive/negative/zero prices."""
    base_time = datetime(2025, 11, 22, 14, 30, 0, tzinfo=UTC)

    # Mix: negative night, zero transition, positive day
    intervals = []
    for i in range(96):
        hour = i // 4  # 0-23
        if hour < 6:  # Night: negative
            price = -5.0
        elif hour < 8:  # Morning transition: zero
            price = 0.0
        else:  # Day: positive
            price = 10.0

        intervals.append(
            {
                "startsAt": base_time - timedelta(hours=24) + timedelta(minutes=15 * i),
                "total": price,
            }
        )

    avg = calculate_trailing_average_for_interval(base_time, intervals)
    # 24 intervals * -5 + 8 intervals * 0 + 64 intervals * 10 = -120 + 0 + 640 = 520
    # 520 / 96 ≈ 5.42
    assert avg is not None
    assert avg == pytest.approx(5.42, rel=0.01)


def test_trailing_average_no_data() -> None:
    """Test trailing average with no matching data."""
    base_time = datetime(2025, 11, 22, 14, 30, 0, tzinfo=UTC)
    intervals = [
        {
            "startsAt": base_time + timedelta(minutes=15 * i),
            "total": 10.0,
        }
        for i in range(96)
    ]

    avg = calculate_trailing_average_for_interval(base_time, intervals)
    assert avg is None


def test_trailing_average_boundary_inclusive() -> None:
    """Test lookback window boundaries with various price types."""
    base_time = datetime(2025, 11, 22, 14, 30, 0, tzinfo=UTC)

    intervals = [
        # Exactly 24h before → INCLUDED
        {"startsAt": base_time - timedelta(hours=24), "total": 5.0},
        # Negative price → INCLUDED
        {"startsAt": base_time - timedelta(hours=23, minutes=45), "total": -10.0},
        # Zero price → INCLUDED
        {"startsAt": base_time - timedelta(hours=23, minutes=30), "total": 0.0},
        # Exactly at base_time → EXCLUDED
        {"startsAt": base_time, "total": 100.0},
    ]

    # Should average 5.0, -10.0, 0.0 only (excludes 100.0)
    # (5 + (-10) + 0) / 3 = -5 / 3 ≈ -1.67
    avg = calculate_trailing_average_for_interval(base_time, intervals)
    assert avg == pytest.approx(-1.67, rel=0.01)


def test_trailing_average_missing_fields() -> None:
    """Test trailing average with missing startsAt or total fields."""
    base_time = datetime(2025, 11, 22, 14, 30, 0, tzinfo=UTC)

    intervals = [
        # Missing startsAt → skipped
        {"total": 10.0},
        # Missing total → skipped
        {"startsAt": base_time - timedelta(hours=1)},
        # Valid negative price
        {"startsAt": base_time - timedelta(hours=2), "total": -15.0},
        # total=None → skipped
        {"startsAt": base_time - timedelta(hours=3), "total": None},
        # Valid zero price
        {"startsAt": base_time - timedelta(hours=4), "total": 0.0},
    ]

    # Only -15.0 and 0.0 are valid → average = -7.5
    avg = calculate_trailing_average_for_interval(base_time, intervals)
    assert avg == pytest.approx(-7.5, rel=1e-9)


# =============================================================================
# Difference Percentage Calculation - Parametrized
# =============================================================================


@pytest.mark.parametrize(
    ("current", "average", "expected_diff", "description"),
    [
        # Positive prices
        (15.0, 10.0, 50.0, "positive current above positive average"),
        (8.0, 10.0, -20.0, "positive current below positive average"),
        (10.0, 10.0, 0.0, "positive current equals positive average"),
        # Negative prices (critical for Norway/Germany)
        (-8.0, -10.0, 20.0, "negative current above (less negative) than negative average"),
        (-12.0, -10.0, -20.0, "negative current below (more negative) than negative average"),
        (-10.0, -10.0, 0.0, "negative current equals negative average"),
        # Mixed scenarios
        (5.0, -10.0, 150.0, "positive current vs negative average"),
        (-5.0, 10.0, -150.0, "negative current vs positive average"),
        # Zero scenarios
        (5.0, 0.0, None, "positive current vs zero average (undefined)"),
        (-5.0, 0.0, None, "negative current vs zero average (undefined)"),
        (0.0, 10.0, -100.0, "zero current vs positive average"),
        (0.0, -10.0, 100.0, "zero current vs negative average"),
        (0.0, 0.0, None, "zero current vs zero average (undefined)"),
    ],
)
def test_difference_percentage_scenarios(
    current: float,
    average: float | None,
    expected_diff: float | None,
    description: str,
) -> None:
    """Test difference percentage calculation across all price scenarios."""
    diff = calculate_difference_percentage(current, average)

    if expected_diff is None:
        assert diff is None, f"Failed for {description}: expected None, got {diff}"
    else:
        assert diff is not None, f"Failed for {description}: expected {expected_diff}, got None"
        assert diff == pytest.approx(expected_diff, rel=1e-9), f"Failed for {description}"


def test_difference_percentage_none_average() -> None:
    """Test difference when average is None."""
    assert calculate_difference_percentage(15.0, None) is None
    assert calculate_difference_percentage(-15.0, None) is None
    assert calculate_difference_percentage(0.0, None) is None


# =============================================================================
# Rating Level Calculation - Parametrized
# =============================================================================


@pytest.mark.parametrize(
    ("difference", "expected_rating", "description"),
    [
        # Positive difference scenarios
        (-15.0, "LOW", "well below average"),
        (-10.0, "LOW", "at low threshold (boundary)"),
        (-5.0, "NORMAL", "slightly below average"),
        (0.0, "NORMAL", "at average"),
        (5.0, "NORMAL", "slightly above average"),
        (10.0, "HIGH", "at high threshold (boundary)"),
        (15.0, "HIGH", "well above average"),
        # Extreme values
        (-50.0, "LOW", "extremely below average"),
        (50.0, "HIGH", "extremely above average"),
    ],
)
def test_rating_level_scenarios(
    difference: float,
    expected_rating: str,
    description: str,
) -> None:
    """Test rating level calculation with standard thresholds."""
    rating = calculate_rating_level(difference, threshold_low=-10.0, threshold_high=10.0)
    assert rating == expected_rating, f"Failed for {description}"


def test_rating_level_none_difference() -> None:
    """Test rating when difference is None (e.g., zero average)."""
    rating = calculate_rating_level(None, threshold_low=-10.0, threshold_high=10.0)
    assert rating is None


# =============================================================================
# Price Enrichment Integration - Parametrized
# =============================================================================


@pytest.mark.parametrize(
    ("day_before_yesterday_price", "yesterday_price", "today_price", "expected_diff", "expected_rating", "description"),
    [
        # Positive prices
        (10.0, 10.0, 15.0, 50.0, "HIGH", "positive prices: day more expensive"),
        (15.0, 15.0, 10.0, -33.33, "LOW", "positive prices: day cheaper"),
        (10.0, 10.0, 10.0, 0.0, "NORMAL", "positive prices: stable"),
        # Negative prices (Norway/Germany scenario)
        (-10.0, -10.0, -15.0, -50.0, "LOW", "negative prices: day more negative (cheaper)"),
        (-15.0, -15.0, -10.0, 33.33, "HIGH", "negative prices: day less negative (expensive)"),
        (-10.0, -10.0, -10.0, 0.0, "NORMAL", "negative prices: stable"),
        # Transition scenarios
        (-10.0, -10.0, 0.0, 100.0, "HIGH", "transition: negative to zero"),
        (-10.0, -10.0, 10.0, 200.0, "HIGH", "transition: negative to positive"),
        (10.0, 10.0, 0.0, -100.0, "LOW", "transition: positive to zero"),
        (10.0, 10.0, -10.0, -200.0, "LOW", "transition: positive to negative"),
        # Zero scenarios
        (0.1, 0.1, 0.1, 0.0, "NORMAL", "prices near zero: stable"),
    ],
)
def test_enrich_price_info_scenarios(  # noqa: PLR0913  # Many parameters needed for comprehensive test scenarios
    day_before_yesterday_price: float,
    yesterday_price: float,
    today_price: float,
    expected_diff: float,
    expected_rating: str,
    description: str,
) -> None:
    """
    Test price enrichment across various price scenarios.

    CRITICAL: Tests now include day_before_yesterday data to provide full 24h lookback
    for yesterday intervals. This matches the real API structure (192 intervals from
    priceInfoRange + today/tomorrow).
    """
    base = datetime(2025, 11, 22, 0, 0, 0, tzinfo=UTC)
    time_service = TibberPricesTimeService()

    # Day before yesterday (needed for lookback)
    day_before_yesterday = [
        {"startsAt": base - timedelta(days=2) + timedelta(minutes=15 * i), "total": day_before_yesterday_price}
        for i in range(96)
    ]

    # Yesterday (will be enriched using day_before_yesterday for lookback)
    yesterday = [
        {"startsAt": base - timedelta(days=1) + timedelta(minutes=15 * i), "total": yesterday_price} for i in range(96)
    ]

    # Today (will be enriched using yesterday for lookback)
    today = [{"startsAt": base + timedelta(minutes=15 * i), "total": today_price} for i in range(96)]

    # Flat list matching API structure (priceInfoRange + today)
    all_intervals = day_before_yesterday + yesterday + today

    enriched = enrich_price_info_with_differences(all_intervals, time=time_service)

    # First "today" interval is at index 192 (96 day_before_yesterday + 96 yesterday)
    first_today = enriched[192]
    assert "difference" in first_today, f"Failed for {description}: no difference field"
    assert first_today["difference"] == pytest.approx(expected_diff, rel=0.01), f"Failed for {description}"
    assert first_today["rating_level"] == expected_rating, f"Failed for {description}"


def test_enrich_price_info_no_yesterday_data() -> None:
    """Test enrichment when no lookback data available."""
    base = datetime(2025, 11, 22, 0, 0, 0, tzinfo=UTC)
    time_service = TibberPricesTimeService()

    today = [{"startsAt": base + timedelta(minutes=15 * i), "total": 10.0} for i in range(96)]

    # New API: flat list (no yesterday data)
    all_intervals = today

    enriched = enrich_price_info_with_differences(all_intervals, time=time_service)

    # First interval has no 24h lookback → difference=None
    first_today = enriched[0]
    assert first_today.get("difference") is None
    assert first_today.get("rating_level") is None


def test_enrich_price_info_custom_thresholds() -> None:
    """
    Test enrichment with custom rating thresholds.

    CRITICAL: Includes day_before_yesterday for full 24h lookback.
    """
    base = datetime(2025, 11, 22, 0, 0, 0, tzinfo=UTC)
    time_service = TibberPricesTimeService()

    # Day before yesterday (needed for lookback)
    day_before_yesterday = [
        {"startsAt": base - timedelta(days=2) + timedelta(minutes=15 * i), "total": 10.0} for i in range(96)
    ]

    # Yesterday (provides lookback for today)
    yesterday = [{"startsAt": base - timedelta(days=1) + timedelta(minutes=15 * i), "total": 10.0} for i in range(96)]

    # Today (+10% vs yesterday average)
    today = [
        {"startsAt": base + timedelta(minutes=15 * i), "total": 11.0}  # +10% vs yesterday
        for i in range(96)
    ]

    # Flat list matching API structure
    all_intervals = day_before_yesterday + yesterday + today

    # Custom thresholds: LOW at -5%, HIGH at +5%
    enriched = enrich_price_info_with_differences(
        all_intervals,
        threshold_low=-5.0,
        threshold_high=5.0,
        time=time_service,
    )

    # First "today" interval is at index 192 (96 day_before_yesterday + 96 yesterday)
    first_today = enriched[192]
    assert first_today["difference"] == pytest.approx(10.0, rel=1e-9)
    assert first_today["rating_level"] == "HIGH"


# =============================================================================
# Price Level Aggregation (Median) - Parametrized
# =============================================================================


@pytest.mark.parametrize(
    ("levels", "expected", "description"),
    [
        (["CHEAP"], "CHEAP", "single level"),
        (["NORMAL", "NORMAL", "NORMAL"], "NORMAL", "identical levels"),
        (["VERY_CHEAP", "CHEAP", "NORMAL"], "CHEAP", "median of 3 levels"),
        (["VERY_CHEAP", "CHEAP", "NORMAL", "EXPENSIVE"], "NORMAL", "median of 4 levels (upper-middle)"),
        (["VERY_CHEAP", "VERY_EXPENSIVE", "NORMAL"], "NORMAL", "mixed extremes"),
        ([], "NORMAL", "empty list (default)"),
    ],
)
def test_aggregate_price_levels(
    levels: list[str],
    expected: str,
    description: str,
) -> None:
    """Test price level aggregation using median."""
    result = aggregate_price_levels(levels)
    assert result == expected, f"Failed for {description}"


# =============================================================================
# Price Rating Aggregation (Average) - Parametrized
# =============================================================================


@pytest.mark.parametrize(
    ("differences", "expected_rating", "expected_avg", "description"),
    [
        ([15.0], "HIGH", 15.0, "single HIGH difference"),
        ([15.0, 20.0, 18.0], "HIGH", 17.67, "multiple HIGH differences"),
        ([15.0, -15.0], "NORMAL", 0.0, "mixed averaging to NORMAL"),
        ([-15.0, -20.0, -18.0], "LOW", -17.67, "multiple LOW differences"),
        ([], "NORMAL", 0.0, "empty list (default)"),
    ],
)
def test_aggregate_price_rating(
    differences: list[float],
    expected_rating: str,
    expected_avg: float,
    description: str,
) -> None:
    """Test price rating aggregation using average difference."""
    rating, avg_diff = aggregate_price_rating(differences, threshold_low=-10.0, threshold_high=10.0)
    assert rating == expected_rating, f"Failed for {description}: rating"
    assert avg_diff == pytest.approx(expected_avg, rel=0.01), f"Failed for {description}: avg"


def test_aggregate_price_rating_with_none_values() -> None:
    """Test rating aggregation filtering out None values."""
    rating, avg_diff = aggregate_price_rating(
        [15.0, None, 20.0, None, 18.0],  # type: ignore[list-item]
        threshold_low=-10.0,
        threshold_high=10.0,
    )
    assert rating == "HIGH"
    assert avg_diff == pytest.approx(17.67, rel=0.01)


# =============================================================================
# Period Aggregation Integration
# =============================================================================


def test_aggregate_period_levels_from_intervals() -> None:
    """Test period level aggregation from interval data."""
    intervals = [
        {"level": "VERY_CHEAP"},
        {"level": "CHEAP"},
        {"level": "NORMAL"},
    ]

    result = aggregate_period_levels(intervals)
    assert result == "cheap"  # Lowercase output


def test_aggregate_period_ratings_from_intervals() -> None:
    """Test period rating aggregation from interval data."""
    intervals = [
        {"difference": 15.0},
        {"difference": -20.0},
        {"difference": 18.0},
    ]

    rating, avg_diff = aggregate_period_ratings(intervals, threshold_low=-10.0, threshold_high=10.0)
    # Average: (15 - 20 + 18) / 3 = 13 / 3 ≈ 4.33 → NORMAL
    assert rating == "normal"
    assert avg_diff == pytest.approx(4.33, rel=0.01)


def test_aggregate_period_ratings_no_data() -> None:
    """Test period rating with no valid data."""
    intervals = [
        {"other_field": "value"},  # No difference field
        {"difference": None},  # None value
    ]

    rating, avg_diff = aggregate_period_ratings(intervals, threshold_low=-10.0, threshold_high=10.0)
    assert rating is None
    assert avg_diff is None
