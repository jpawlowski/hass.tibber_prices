"""
Test with actual December 25, 2025 price data provided by user.

This test uses the exact price data from the user's comment to verify
that the period calculation works correctly with real-world data.
"""

from __future__ import annotations

from datetime import datetime, timezone
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


def _create_dec25_intervals() -> list[dict]:
    """Create intervals from the actual Dec 25, 2025 data."""
    # Real price data from user's comment
    prices_data = [
        ("2025-12-25T00:00:00.000+01:00", 0.295, "NORMAL"),
        ("2025-12-25T00:15:00.000+01:00", 0.2893, "NORMAL"),
        ("2025-12-25T00:30:00.000+01:00", 0.2893, "NORMAL"),
        ("2025-12-25T00:45:00.000+01:00", 0.2926, "NORMAL"),
        ("2025-12-25T01:00:00.000+01:00", 0.2878, "NORMAL"),
        ("2025-12-25T01:15:00.000+01:00", 0.2865, "NORMAL"),
        ("2025-12-25T01:30:00.000+01:00", 0.2847, "NORMAL"),
        ("2025-12-25T01:45:00.000+01:00", 0.2845, "NORMAL"),
        ("2025-12-25T02:00:00.000+01:00", 0.2852, "NORMAL"),
        ("2025-12-25T02:15:00.000+01:00", 0.2837, "NORMAL"),
        ("2025-12-25T02:30:00.000+01:00", 0.2837, "NORMAL"),
        ("2025-12-25T02:45:00.000+01:00", 0.2833, "NORMAL"),
        ("2025-12-25T03:00:00.000+01:00", 0.2841, "NORMAL"),
        ("2025-12-25T03:15:00.000+01:00", 0.2828, "NORMAL"),
        ("2025-12-25T03:30:00.000+01:00", 0.2824, "NORMAL"),
        ("2025-12-25T03:45:00.000+01:00", 0.2818, "NORMAL"),
        ("2025-12-25T04:00:00.000+01:00", 0.2814, "NORMAL"),
        ("2025-12-25T04:15:00.000+01:00", 0.281, "NORMAL"),
        ("2025-12-25T04:30:00.000+01:00", 0.2813, "NORMAL"),
        ("2025-12-25T04:45:00.000+01:00", 0.2812, "NORMAL"),
        ("2025-12-25T05:00:00.000+01:00", 0.2804, "NORMAL"),
        ("2025-12-25T05:15:00.000+01:00", 0.2806, "NORMAL"),
        ("2025-12-25T05:30:00.000+01:00", 0.2769, "NORMAL"),
        ("2025-12-25T05:45:00.000+01:00", 0.2777, "NORMAL"),
        ("2025-12-25T06:00:00.000+01:00", 0.2728, "CHEAP"),
        ("2025-12-25T06:15:00.000+01:00", 0.277, "NORMAL"),
        ("2025-12-25T06:30:00.000+01:00", 0.277, "NORMAL"),
        ("2025-12-25T06:45:00.000+01:00", 0.2724, "CHEAP"),
        ("2025-12-25T07:00:00.000+01:00", 0.2717, "CHEAP"),
        ("2025-12-25T07:15:00.000+01:00", 0.277, "NORMAL"),
        ("2025-12-25T07:30:00.000+01:00", 0.2855, "NORMAL"),
        ("2025-12-25T07:45:00.000+01:00", 0.2882, "NORMAL"),
        ("2025-12-25T08:00:00.000+01:00", 0.2925, "NORMAL"),
        ("2025-12-25T08:15:00.000+01:00", 0.293, "NORMAL"),
        ("2025-12-25T08:30:00.000+01:00", 0.2966, "NORMAL"),
        ("2025-12-25T08:45:00.000+01:00", 0.2888, "NORMAL"),
        ("2025-12-25T09:00:00.000+01:00", 0.2968, "NORMAL"),
        ("2025-12-25T09:15:00.000+01:00", 0.2942, "NORMAL"),
        ("2025-12-25T09:30:00.000+01:00", 0.2926, "NORMAL"),
        ("2025-12-25T09:45:00.000+01:00", 0.2897, "NORMAL"),
        ("2025-12-25T10:00:00.000+01:00", 0.2854, "NORMAL"),
        ("2025-12-25T10:15:00.000+01:00", 0.28, "NORMAL"),
        ("2025-12-25T10:30:00.000+01:00", 0.2752, "NORMAL"),
        ("2025-12-25T10:45:00.000+01:00", 0.2806, "NORMAL"),
        ("2025-12-25T11:00:00.000+01:00", 0.2758, "NORMAL"),
        ("2025-12-25T11:15:00.000+01:00", 0.2713, "CHEAP"),
        ("2025-12-25T11:30:00.000+01:00", 0.2743, "NORMAL"),
        ("2025-12-25T11:45:00.000+01:00", 0.277, "NORMAL"),
        ("2025-12-25T12:00:00.000+01:00", 0.2816, "NORMAL"),
        ("2025-12-25T12:15:00.000+01:00", 0.2758, "NORMAL"),
        ("2025-12-25T12:30:00.000+01:00", 0.2699, "CHEAP"),
        ("2025-12-25T12:45:00.000+01:00", 0.2687, "CHEAP"),
        ("2025-12-25T13:00:00.000+01:00", 0.2665, "CHEAP"),  # Daily minimum
        ("2025-12-25T13:15:00.000+01:00", 0.267, "CHEAP"),
        ("2025-12-25T13:30:00.000+01:00", 0.2723, "NORMAL"),
        ("2025-12-25T13:45:00.000+01:00", 0.2874, "NORMAL"),
        ("2025-12-25T14:00:00.000+01:00", 0.2779, "NORMAL"),
        ("2025-12-25T14:15:00.000+01:00", 0.2953, "NORMAL"),
        ("2025-12-25T14:30:00.000+01:00", 0.3015, "NORMAL"),
        ("2025-12-25T14:45:00.000+01:00", 0.3168, "NORMAL"),
        ("2025-12-25T15:00:00.000+01:00", 0.3055, "NORMAL"),
        ("2025-12-25T15:15:00.000+01:00", 0.3161, "NORMAL"),
        ("2025-12-25T15:30:00.000+01:00", 0.3328, "NORMAL"),
        ("2025-12-25T15:45:00.000+01:00", 0.3364, "NORMAL"),
        ("2025-12-25T16:00:00.000+01:00", 0.3234, "NORMAL"),
        ("2025-12-25T16:15:00.000+01:00", 0.3176, "NORMAL"),
        ("2025-12-25T16:30:00.000+01:00", 0.3317, "NORMAL"),
        ("2025-12-25T16:45:00.000+01:00", 0.3317, "NORMAL"),
        ("2025-12-25T17:00:00.000+01:00", 0.3211, "NORMAL"),
        ("2025-12-25T17:15:00.000+01:00", 0.3283, "NORMAL"),
        ("2025-12-25T17:30:00.000+01:00", 0.3316, "NORMAL"),
        ("2025-12-25T17:45:00.000+01:00", 0.3317, "NORMAL"),
        ("2025-12-25T18:00:00.000+01:00", 0.3295, "NORMAL"),
        ("2025-12-25T18:15:00.000+01:00", 0.3293, "NORMAL"),
        ("2025-12-25T18:30:00.000+01:00", 0.3281, "NORMAL"),
        ("2025-12-25T18:45:00.000+01:00", 0.3261, "NORMAL"),
        ("2025-12-25T19:00:00.000+01:00", 0.3258, "NORMAL"),
        ("2025-12-25T19:15:00.000+01:00", 0.3255, "NORMAL"),
        ("2025-12-25T19:30:00.000+01:00", 0.3243, "NORMAL"),
        ("2025-12-25T19:45:00.000+01:00", 0.3262, "NORMAL"),
        ("2025-12-25T20:00:00.000+01:00", 0.3302, "NORMAL"),
        ("2025-12-25T20:15:00.000+01:00", 0.331, "NORMAL"),
        ("2025-12-25T20:30:00.000+01:00", 0.3205, "NORMAL"),
        ("2025-12-25T20:45:00.000+01:00", 0.3169, "NORMAL"),
        ("2025-12-25T21:00:00.000+01:00", 0.3231, "NORMAL"),
        ("2025-12-25T21:15:00.000+01:00", 0.3307, "NORMAL"),
        ("2025-12-25T21:30:00.000+01:00", 0.3288, "NORMAL"),
        ("2025-12-25T21:45:00.000+01:00", 0.3239, "NORMAL"),
        ("2025-12-25T22:00:00.000+01:00", 0.3325, "NORMAL"),
        ("2025-12-25T22:15:00.000+01:00", 0.3317, "NORMAL"),
        ("2025-12-25T22:30:00.000+01:00", 0.3317, "NORMAL"),
        ("2025-12-25T22:45:00.000+01:00", 0.3271, "NORMAL"),
        ("2025-12-25T23:00:00.000+01:00", 0.3304, "NORMAL"),
        ("2025-12-25T23:15:00.000+01:00", 0.3252, "NORMAL"),
        ("2025-12-25T23:30:00.000+01:00", 0.324, "NORMAL"),
        ("2025-12-25T23:45:00.000+01:00", 0.3211, "NORMAL"),
    ]
    
    # Calculate daily statistics
    prices = [p[1] for p in prices_data]
    daily_min = min(prices)  # 0.2665
    daily_max = max(prices)  # 0.3364
    daily_avg = sum(prices) / len(prices)
    
    intervals = []
    for time_str, price, level in prices_data:
        # Parse timestamp
        dt = datetime.fromisoformat(time_str)
        
        intervals.append({
            "startsAt": dt,
            "total": price,
            "level": level,
            "rating_level": "LOW" if level == "CHEAP" else "NORMAL",
            "_original_price": price,
            "trailing_avg_24h": daily_avg,
            "daily_min": daily_min,
            "daily_avg": daily_avg,
            "daily_max": daily_max,
        })
    
    return intervals


@pytest.mark.asyncio
async def test_dec25_actual_data_analysis():
    """
    Analyze the actual Dec 25, 2025 data to understand price distribution.
    
    Key observations from the data:
    - Daily minimum: 0.2665 (at 13:00)
    - Daily maximum: 0.3364 (at 15:45)
    - Most prices are NORMAL (only a few CHEAP intervals scattered throughout)
    - Early morning (00:00-06:00): prices around 0.28-0.295
    - Late afternoon (13:00-13:15): absolute minimum around 0.2665-0.267
    
    User's concern: "only prices before the minimum daily price are considered 
    while intervals after minimum price should also be included because they are 
    actually lower than intervals before minimum price"
    
    This suggests intervals AFTER 13:00 (the minimum) that have lower prices than
    intervals BEFORE 13:00 should be included.
    """
    mock_coordinator = Mock()
    mock_coordinator.config_entry = Mock()
    time_service = TibberPricesTimeService(mock_coordinator)
    
    # Use the actual date from the data
    test_time = dt_util.parse_datetime("2025-12-25T12:00:00+01:00")
    time_service.now = Mock(return_value=test_time)
    
    intervals = _create_dec25_intervals()
    
    # Calculate actual statistics
    prices = [i["total"] for i in intervals]
    daily_min = min(prices)
    daily_max = max(prices)
    daily_avg = sum(prices) / len(prices)
    
    print(f"\n=== December 25, 2025 Price Analysis ===")
    print(f"Daily minimum: {daily_min:.4f} (at 13:00)")
    print(f"Daily average: {daily_avg:.4f}")
    print(f"Daily maximum: {daily_max:.4f} (at 15:45)")
    print(f"Price range: {daily_max - daily_min:.4f}")
    
    # Find CHEAP intervals
    cheap_intervals = [(i["startsAt"], i["total"]) for i in intervals if i["level"] == "CHEAP"]
    print(f"\nCHEAP intervals ({len(cheap_intervals)}):")
    for dt, price in cheap_intervals:
        print(f"  {dt.strftime('%H:%M')}: {price:.4f}")
    
    # Test with default config (15% flex)
    config = TibberPricesPeriodConfig(
        reverse_sort=False,  # Best price
        flex=0.15,  # 15% default
        min_distance_from_avg=5.0,  # 5% default
        min_period_length=60,
        threshold_low=0.25,
        threshold_high=0.30,
        threshold_volatility_moderate=10.0,
        threshold_volatility_high=20.0,
        threshold_volatility_very_high=30.0,
        level_filter="cheap",  # Only CHEAP intervals
        gap_count=0,
    )
    
    result = calculate_periods(intervals, config=config, time=time_service)
    periods = result["periods"]
    
    # Get calculated reference prices
    ref_data = result["reference_data"]
    ref_min = list(ref_data["ref_prices"].values())[0]
    ref_avg = list(ref_data["avg_prices"].values())[0]
    
    flex_threshold = ref_min * (1 + config.flex)
    distance_threshold = ref_avg * (1 - config.min_distance_from_avg / 100)
    
    print(f"\n=== Period Calculation (flex={config.flex*100}%, min_distance={config.min_distance_from_avg}%, level=CHEAP) ===")
    print(f"Reference minimum: {ref_min:.4f}")
    print(f"Reference average: {ref_avg:.4f}")
    print(f"Flex threshold (min * 1.{config.flex}): {flex_threshold:.4f}")
    print(f"Distance threshold (avg * 0.95): {distance_threshold:.4f}")
    print(f"\nIntervals must meet ALL of:")
    print(f"  1. price <= {flex_threshold:.4f} (flex filter)")
    print(f"  2. price <= {distance_threshold:.4f} (min_distance filter)")
    print(f"  3. level = CHEAP (level filter)")
    
    print(f"\n=== Results ===")
    print(f"Found {len(periods)} period(s):")
    for i, period in enumerate(periods, 1):
        start = period['start']
        end = period['end']
        print(f"  Period {i}: {start.strftime('%H:%M')} - {end.strftime('%H:%M')}")
    
    # Analyze which CHEAP intervals should qualify
    print(f"\n=== CHEAP Interval Analysis ===")
    for dt, price in cheap_intervals:
        in_flex = price <= flex_threshold
        in_distance = price <= distance_threshold
        qualifies = in_flex and in_distance
        status = "✓ QUALIFIES" if qualifies else "✗ excluded"
        reasons = []
        if not in_flex:
            reasons.append(f"exceeds flex ({price:.4f} > {flex_threshold:.4f})")
        if not in_distance:
            reasons.append(f"too close to avg ({price:.4f} > {distance_threshold:.4f})")
        
        reason_str = f" - {', '.join(reasons)}" if reasons else ""
        print(f"  {dt.strftime('%H:%M')}: {price:.4f} - {status}{reason_str}")
    
    # Verify the fix works
    assert len(periods) > 0, "Should find at least one period with CHEAP intervals"


@pytest.mark.asyncio
async def test_dec25_without_level_filter():
    """Test Dec 25 data without level filter to see all qualifying intervals."""
    mock_coordinator = Mock()
    mock_coordinator.config_entry = Mock()
    time_service = TibberPricesTimeService(mock_coordinator)
    
    test_time = dt_util.parse_datetime("2025-12-25T12:00:00+01:00")
    time_service.now = Mock(return_value=test_time)
    
    intervals = _create_dec25_intervals()
    
    # Calculate statistics
    prices = [i["total"] for i in intervals]
    daily_min = min(prices)
    daily_avg = sum(prices) / len(prices)
    
    # Test without level filter to see ALL qualifying intervals
    config = TibberPricesPeriodConfig(
        reverse_sort=False,
        flex=0.15,  # 15%
        min_distance_from_avg=5.0,  # 5%
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
    
    ref_min = list(result["reference_data"]["ref_prices"].values())[0]
    ref_avg = list(result["reference_data"]["avg_prices"].values())[0]
    
    flex_threshold = ref_min * (1 + config.flex)
    distance_threshold = ref_avg * (1 - config.min_distance_from_avg / 100)
    
    print(f"\n=== Without Level Filter ===")
    print(f"Flex threshold: {flex_threshold:.4f}")
    print(f"Distance threshold: {distance_threshold:.4f}")
    print(f"\nFound {len(periods)} period(s):")
    for i, period in enumerate(periods, 1):
        start = period['start']
        end = period['end']
        length_min = (end - start).total_seconds() / 60
        print(f"  Period {i}: {start.strftime('%H:%M')} - {end.strftime('%H:%M')} ({length_min:.0f} min)")
    
    # Check which intervals qualify
    qualifying_intervals = []
    for interval in intervals:
        price = interval["total"]
        dt = interval["startsAt"]
        in_flex = price <= flex_threshold
        in_distance = price <= distance_threshold
        if in_flex and in_distance:
            qualifying_intervals.append((dt, price))
    
    print(f"\nQualifying intervals ({len(qualifying_intervals)}):")
    for dt, price in qualifying_intervals[:20]:  # Show first 20
        print(f"  {dt.strftime('%H:%M')}: {price:.4f}")
    if len(qualifying_intervals) > 20:
        print(f"  ... and {len(qualifying_intervals) - 20} more")
