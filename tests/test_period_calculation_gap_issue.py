"""
Test for period calculation issue where qualifying intervals after minimum price are skipped.

Issue: When the daily minimum price occurs in the middle of the day, intervals AFTER
the minimum that qualify (low price) might not be included in best price periods
if there are non-qualifying intervals between them and previous periods.

Example scenario (Dec 25, 2025 type):
- 00:00-06:00: Price 0.30 (CHEAP, qualifies for best price)
- 06:00-12:00: Price 0.35 (NORMAL, doesn't qualify)
- 12:00-13:00: Price 0.28 (CHEAP, MINIMUM - qualifies)
- 13:00-15:00: Price 0.36 (NORMAL, doesn't qualify)
- 15:00-18:00: Price 0.29 (CHEAP, qualifies - should be included!)
- 18:00-24:00: Price 0.38 (EXPENSIVE, doesn't qualify)

Expected: Three separate periods (00:00-06:00, 12:00-13:00, 15:00-18:00)
Actual (bug): Only two periods (00:00-06:00, 12:00-13:00) - third period skipped

Root cause: Sequential processing with temporal continuity requirement.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from custom_components.tibber_prices.coordinator.period_handlers import (
    TibberPricesPeriodConfig,
    calculate_periods,
)
from custom_components.tibber_prices.coordinator.time_service import (
    TibberPricesTimeService,
)
from homeassistant.util import dt as dt_util


def _create_test_intervals_with_gap_issue() -> list[dict]:
    """
    Create test data that demonstrates the gap issue.

    Pattern simulates a day where qualifying intervals appear in three separate
    time windows, separated by non-qualifying intervals.
    """
    now_local = dt_util.now()
    base_time = now_local.replace(hour=0, minute=0, second=0, microsecond=0)

    daily_min = 0.28  # Minimum at 12:00
    daily_avg = 0.32
    daily_max = 0.38

    def _create_interval(hour: int, minute: int, price: float, level: str, rating: str) -> dict:
        """Create a single interval dict."""
        return {
            "startsAt": base_time.replace(hour=hour, minute=minute),
            "total": price,
            "level": level,
            "rating_level": rating,
            "_original_price": price,
            "trailing_avg_24h": daily_avg,
            "daily_min": daily_min,
            "daily_avg": daily_avg,
            "daily_max": daily_max,
        }

    intervals = []

    # Period 1: Early morning (00:00-06:00) - CHEAP, qualifies
    for hour in range(6):
        for minute in [0, 15, 30, 45]:
            intervals.append(_create_interval(hour, minute, 0.30, "CHEAP", "LOW"))

    # Gap 1: Morning peak (06:00-12:00) - NORMAL, doesn't qualify
    for hour in range(6, 12):
        for minute in [0, 15, 30, 45]:
            intervals.append(_create_interval(hour, minute, 0.35, "NORMAL", "NORMAL"))

    # Period 2: Midday minimum (12:00-13:00) - VERY CHEAP, qualifies
    for hour in range(12, 13):
        for minute in [0, 15, 30, 45]:
            intervals.append(_create_interval(hour, minute, 0.28, "VERY_CHEAP", "VERY_LOW"))

    # Gap 2: Afternoon rise (13:00-15:00) - NORMAL, doesn't qualify
    for hour in range(13, 15):
        for minute in [0, 15, 30, 45]:
            intervals.append(_create_interval(hour, minute, 0.36, "NORMAL", "NORMAL"))

    # Period 3: Late afternoon dip (15:00-18:00) - CHEAP, qualifies (THIS IS THE BUG)
    # This period should be included because price 0.29 is:
    # - Within flex from daily minimum (0.28)
    # - Below average - min_distance
    # - Marked as CHEAP level
    for hour in range(15, 18):
        for minute in [0, 15, 30, 45]:
            intervals.append(_create_interval(hour, minute, 0.29, "CHEAP", "LOW"))

    # Gap 3: Evening peak (18:00-24:00) - EXPENSIVE, doesn't qualify
    for hour in range(18, 24):
        for minute in [0, 15, 30, 45]:
            intervals.append(_create_interval(hour, minute, 0.38, "EXPENSIVE", "HIGH"))

    return intervals


@pytest.mark.asyncio
async def test_best_price_includes_all_qualifying_periods():
    """Test that all qualifying periods are found, not just those before/at minimum."""
    # Setup
    mock_coordinator = Mock()
    mock_coordinator.config_entry = Mock()
    time_service = TibberPricesTimeService(mock_coordinator)
    
    # Mock now() to return test date
    test_time = dt_util.now()
    time_service.now = Mock(return_value=test_time)
    
    intervals = _create_test_intervals_with_gap_issue()

    # Daily stats for verification
    daily_min = 0.28
    daily_avg = 0.32

    # Config: 20% flex, 5% min_distance, level filter = CHEAP or better
    config = TibberPricesPeriodConfig(
        reverse_sort=False,  # Best price
        flex=0.20,  # 20% flex allows prices up to 0.28 * 1.20 = 0.336
        min_distance_from_avg=5.0,  # Prices must be <= 0.32 * 0.95 = 0.304
        min_period_length=60,  # 1 hour minimum
        threshold_low=0.25,
        threshold_high=0.30,
        threshold_volatility_moderate=10.0,
        threshold_volatility_high=20.0,
        threshold_volatility_very_high=30.0,
        level_filter="cheap",  # Only CHEAP or better
        gap_count=0,
    )

    # Calculate periods
    result = calculate_periods(intervals, config=config, time=time_service)
    periods = result["periods"]

    # Debug output
    print(f"\nDaily stats: min={daily_min}, avg={daily_avg}")
    print(f"Flex threshold: {daily_min * 1.20:.3f}")
    print(f"Min distance threshold: {daily_avg * 0.95:.3f}")
    print(f"\nFound {len(periods)} period(s):")
    for i, period in enumerate(periods):
        print(f"  Period {i+1}: {period['start']} to {period['end']} ({period.get('length_minutes')}min)")

    # Expected periods:
    # 1. 00:00-06:00 (price 0.30: within flex 0.336, below distance 0.304, CHEAP level) ✓
    # 2. 12:00-13:00 (price 0.28: within flex 0.336, below distance 0.304, VERY_CHEAP level) ✓
    # 3. 15:00-18:00 (price 0.29: within flex 0.336, below distance 0.304, CHEAP level) ✓ THIS ONE MIGHT BE MISSING

    # Assertions
    assert len(periods) >= 2, f"Expected at least 2 periods, got {len(periods)}"

    # Check if third period is found (this is the bug fix target)
    # If only 2 periods found, the late afternoon period (15:00-18:00) was skipped
    if len(periods) == 2:
        pytest.fail(
            "BUG CONFIRMED: Only 2 periods found. "
            "The late afternoon period (15:00-18:00, price 0.29) was skipped "
            "even though it qualifies (CHEAP level, within flex and min_distance). "
            "This demonstrates the issue where qualifying intervals AFTER the daily "
            "minimum are not included in best price periods."
        )

    # If fix is working, we should have 3 periods
    assert len(periods) == 3, (
        f"Expected 3 periods (early morning, midday, late afternoon), got {len(periods)}. "
        f"Periods found: {[(p['start'], p['end']) for p in periods]}"
    )

    # Verify periods are at expected times
    period_hours = [(p["start"].hour, p["end"].hour) for p in periods]
    expected_ranges = [(0, 6), (12, 13), (15, 18)]

    for expected_start, expected_end in expected_ranges:
        found = any(start <= expected_start < end or start < expected_end <= end for start, end in period_hours)
        assert found, f"Expected period in range {expected_start}:00-{expected_end}:00 not found"


@pytest.mark.asyncio
async def test_best_price_with_relaxed_criteria():
    """Test with more relaxed criteria to ensure at least some periods are found."""
    mock_coordinator = Mock()
    mock_coordinator.config_entry = Mock()
    time_service = TibberPricesTimeService(mock_coordinator)
    
    # Mock now() to return test date
    test_time = dt_util.now()
    time_service.now = Mock(return_value=test_time)
    
    intervals = _create_test_intervals_with_gap_issue()

    # Very relaxed config to ensure periods are found
    config = TibberPricesPeriodConfig(
        reverse_sort=False,
        flex=0.50,  # 50% flex - very permissive
        min_distance_from_avg=0.0,  # Disabled
        min_period_length=60,
        threshold_low=0.25,
        threshold_high=0.30,
        threshold_volatility_moderate=10.0,
        threshold_volatility_high=20.0,
        threshold_volatility_very_high=30.0,
        level_filter=None,  # No level filter
        gap_count=0,
    )

    result = calculate_periods(intervals, config=config, time=time_service)
    periods = result["periods"]

    print(f"\nWith relaxed criteria: Found {len(periods)} period(s)")
    for i, period in enumerate(periods):
        print(f"  Period {i+1}: {period['start']} to {period['end']}")

    # Even with very relaxed criteria, if we only get 2 periods, something is wrong
    assert len(periods) > 0, "No periods found even with very relaxed criteria"
