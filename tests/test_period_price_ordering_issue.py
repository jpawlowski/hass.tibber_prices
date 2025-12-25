"""
Test for period calculation issue where lower-priced intervals appear in wrong order.

Issue (from problem statement): "I get the impression that sometimes, only prices 
before the minimum daily price are considered while intervals after minimum price 
should also be included because they are actually lower than intervals before minimum price."

Key insight: The issue might be that intervals AFTER the minimum that are LOWER in price
than intervals BEFORE the minimum are not being selected for the period.

Example scenario that might expose the bug:
- 00:00-06:00: Price 0.32 (NORMAL, doesn't qualify for best price)
- 06:00-12:00: Price 0.28 (CHEAP, daily MINIMUM - qualifies)
- 12:00-18:00: Price 0.30 (CHEAP, qualifies - LOWER than 00:00-06:00 but HIGHER than minimum)
- 18:00-24:00: Price 0.35 (NORMAL, doesn't qualify)

If algorithm processes chronologically and breaks periods on non-qualifying intervals,
it should still work fine. But what if the issue is about PRICE ORDER not TIME ORDER?

Let me try a different scenario - maybe the problem is with flex calculation
or reference price selection.
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


def _create_scenario_minimum_in_middle() -> list[dict]:
    """
    Create scenario where daily minimum is in the middle of the day.
    
    The issue might be: If daily minimum is at 12:00, and there are qualifying
    intervals both before AND after, are all of them included?
    """
    now_local = dt_util.now()
    base_time = now_local.replace(hour=0, minute=0, second=0, microsecond=0)

    daily_min = 0.25  # Minimum at 12:00
    daily_avg = 0.31
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

    # Morning: Moderate prices (00:00-06:00) - price 0.30
    # This is BELOW average but ABOVE minimum
    for hour in range(6):
        for minute in [0, 15, 30, 45]:
            intervals.append(_create_interval(hour, minute, 0.30, "CHEAP", "LOW"))

    # Late morning: Higher prices (06:00-12:00) - price 0.33
    for hour in range(6, 12):
        for minute in [0, 15, 30, 45]:
            intervals.append(_create_interval(hour, minute, 0.33, "NORMAL", "NORMAL"))

    # Midday: Daily MINIMUM (12:00-13:00) - price 0.25
    for hour in range(12, 13):
        for minute in [0, 15, 30, 45]:
            intervals.append(_create_interval(hour, minute, 0.25, "VERY_CHEAP", "VERY_LOW"))

    # Afternoon: Back up slightly (13:00-18:00) - price 0.27
    # This is LOWER than morning (0.30) but HIGHER than minimum (0.25)
    for hour in range(13, 18):
        for minute in [0, 15, 30, 45]:
            intervals.append(_create_interval(hour, minute, 0.27, "CHEAP", "LOW"))

    # Evening: High prices (18:00-24:00) - price 0.38
    for hour in range(18, 24):
        for minute in [0, 15, 30, 45]:
            intervals.append(_create_interval(hour, minute, 0.38, "EXPENSIVE", "HIGH"))

    return intervals


@pytest.mark.asyncio
async def test_periods_include_intervals_lower_than_morning_prices():
    """
    Test that afternoon intervals (price 0.27) are included even though
    they're higher than the minimum (0.25) but lower than morning (0.30).
    
    Expected: Both morning (0.30) and afternoon (0.27) should be in periods
    if flex/min_distance criteria allow.
    """
    mock_coordinator = Mock()
    mock_coordinator.config_entry = Mock()
    time_service = TibberPricesTimeService(mock_coordinator)
    
    test_time = dt_util.now()
    time_service.now = Mock(return_value=test_time)
    
    intervals = _create_scenario_minimum_in_middle()

    # Daily stats for verification
    daily_min = 0.25
    daily_avg = 0.31

    # Config with flex allowing prices up to 0.25 * 1.30 = 0.325
    # This should include:
    # - Morning 0.30 ✓ (within flex, below avg)
    # - Minimum 0.25 ✓ (within flex, below avg)
    # - Afternoon 0.27 ✓ (within flex, below avg)
    # - Late morning 0.33 ✗ (exceeds flex)
    # - Evening 0.38 ✗ (exceeds flex)
    
    config = TibberPricesPeriodConfig(
        reverse_sort=False,  # Best price
        flex=0.30,  # 30% flex allows up to 0.325
        min_distance_from_avg=10.0,  # Prices must be <= 0.31 * 0.90 = 0.279
        min_period_length=60,  # 1 hour minimum
        threshold_low=0.25,
        threshold_high=0.30,
        threshold_volatility_moderate=10.0,
        threshold_volatility_high=20.0,
        threshold_volatility_very_high=30.0,
        level_filter=None,  # No level filter
        gap_count=0,
    )

    # Calculate periods
    result = calculate_periods(intervals, config=config, time=time_service)
    periods = result["periods"]

    # Debug output
    print(f"\nDaily stats: min={daily_min}, avg={daily_avg}")
    print(f"Flex threshold: {daily_min * 1.30:.3f}")
    print(f"Min distance threshold: {daily_avg * 0.90:.3f}")
    print(f"\nInterval prices:")
    print(f"  00:00-06:00: 0.30 (should qualify if min_distance allows)")
    print(f"  06:00-12:00: 0.33 (should NOT qualify - exceeds flex)")
    print(f"  12:00-13:00: 0.25 (MINIMUM - should qualify)")
    print(f"  13:00-18:00: 0.27 (should qualify - lower than morning)")
    print(f"  18:00-24:00: 0.38 (should NOT qualify)")
    print(f"\nFound {len(periods)} period(s):")
    for i, period in enumerate(periods):
        print(f"  Period {i+1}: {period['start'].strftime('%H:%M')} to {period['end'].strftime('%H:%M')}")

    # With min_distance = 10%, threshold is 0.31 * 0.90 = 0.279
    # Morning (0.30) exceeds this threshold → should NOT be included
    # Minimum (0.25) ✓
    # Afternoon (0.27) ✓
    
    # Expected: 2 separate periods (minimum and afternoon) OR 1 combined period if adjacent
    
    assert len(periods) > 0, "Should find at least one period"
    
    # Check if afternoon period is found (13:00-18:00, price 0.27)
    afternoon_period_found = any(
        p["start"].hour <= 13 and p["end"].hour >= 16
        for p in periods
    )
    
    assert afternoon_period_found, (
        "Afternoon period (13:00-18:00, price 0.27) should be included. "
        "It's lower than morning prices (0.30) and qualifies by both "
        "flex (0.27 < 0.325) and min_distance (0.27 < 0.279) criteria."
    )


@pytest.mark.asyncio
async def test_strict_min_distance_filters_higher_before_minimum():
    """
    Test with strict min_distance that filters morning but keeps afternoon.
    
    This tests whether the algorithm correctly distinguishes between:
    - Morning (0.30): Higher price, before minimum
    - Afternoon (0.27): Lower price, after minimum
    """
    mock_coordinator = Mock()
    mock_coordinator.config_entry = Mock()
    time_service = TibberPricesTimeService(mock_coordinator)
    
    test_time = dt_util.now()
    time_service.now = Mock(return_value=test_time)
    
    intervals = _create_scenario_minimum_in_middle()

    # Strict config: min_distance=15% → threshold = 0.31 * 0.85 = 0.2635
    # This should filter morning (0.30) but keep afternoon (0.27)
    
    config = TibberPricesPeriodConfig(
        reverse_sort=False,
        flex=0.50,  # Very permissive flex
        min_distance_from_avg=15.0,  # Strict: prices must be <= 0.2635
        min_period_length=60,
        threshold_low=0.25,
        threshold_high=0.30,
        threshold_volatility_moderate=10.0,
        threshold_volatility_high=20.0,
        threshold_volatility_very_high=30.0,
        level_filter=None,
        gap_count=0,
    )

    # Calculate periods
    result = calculate_periods(intervals, config=config, time=time_service)
    periods = result["periods"]

    print(f"\n--- Strict min_distance test ---")
    print(f"Config: flex={config.flex*100}%, min_distance={config.min_distance_from_avg}%")
    print(f"Daily avg: {daily_avg}")
    print(f"Nominal min distance threshold: {0.31 * 0.85:.4f}")
    print(f"With flex={config.flex*100}% → scaled min_distance (approx): {config.min_distance_from_avg * 0.25}%")
    print(f"Scaled threshold: {0.31 * (1 - (config.min_distance_from_avg * 0.25 / 100)):.4f}")
    print(f"Morning 0.30: {'FAIL' if 0.30 > 0.2635 else 'PASS'} (vs nominal threshold)")
    print(f"Minimum 0.25: {'FAIL' if 0.25 > 0.2635 else 'PASS'} (vs nominal threshold)")
    print(f"Afternoon 0.27: {'FAIL' if 0.27 > 0.2635 else 'PASS'} (vs nominal threshold)")
    print(f"\nFound {len(periods)} period(s):")
    for i, period in enumerate(periods):
        print(f"  Period {i+1}: {period['start'].strftime('%H:%M')} to {period['end'].strftime('%H:%M')}")

    # Morning should be filtered out (0.30 > 0.2635)
    # Minimum and afternoon should form period(s)
    
    assert len(periods) > 0, "Should find periods for minimum and afternoon"
    
    # Verify morning is NOT in periods
    morning_period_found = any(
        p["start"].hour == 0
        for p in periods
    )
    
    assert not morning_period_found, (
        "Morning period (0.30) should be filtered by strict min_distance. "
        "Only minimum (0.25) and afternoon (0.27) should be in periods."
    )
    
    # Verify afternoon IS in periods
    afternoon_period_found = any(
        p["start"].hour <= 13 and p["end"].hour >= 16
        for p in periods
    )
    
    assert afternoon_period_found, (
        "Afternoon period (0.27) should be included - it's lower than morning "
        "and passes the min_distance filter."
    )
