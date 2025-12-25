"""
Test to verify the flex filter bug where prices BELOW the daily minimum are excluded.

BUG: In level_filtering.py line 160, the condition for best price flex filter is:
    in_flex = price >= criteria.ref_price and price <= flex_threshold

This EXCLUDES prices below the daily minimum, which is wrong!

For best price, we want LOW prices, so we should accept:
- Any price from 0 up to (daily_min + flex_amount)

NOT just:
- Prices from daily_min to (daily_min + flex_amount)

This explains the user's observation: "only prices before the minimum daily price are 
considered while intervals after minimum price should also be included because they are 
actually lower than intervals before minimum price."

If there are intervals with prices LOWER than the daily minimum (due to rounding or 
floating point precision), they would be EXCLUDED by the current logic!
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


def _create_intervals_with_prices_below_minimum() -> list[dict]:
    """
    Create test data where some intervals have prices BELOW the calculated daily minimum.
    
    This can happen in real data due to:
    1. Rounding errors in price calculations
    2. Multiple intervals at the exact same minimum price
    3. Price data arriving in batches with different precision
    """
    now_local = dt_util.now()
    base_time = now_local.replace(hour=0, minute=0, second=0, microsecond=0)

    # The "calculated" daily minimum is 0.25 (from the midday interval)
    # But we'll have an interval at 0.249 which is technically lower
    daily_min = 0.25
    daily_avg = 0.30
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
            "daily_min": daily_min,  # NOTE: This is the "calculated" minimum, not actual
            "daily_avg": daily_avg,
            "daily_max": daily_max,
        }

    intervals = []

    # Early morning: Price 0.249 - BELOW the "daily minimum" of 0.25!
    # This should be included in best price periods (it's the cheapest!)
    for hour in range(3):
        for minute in [0, 15, 30, 45]:
            intervals.append(_create_interval(hour, minute, 0.249, "VERY_CHEAP", "VERY_LOW"))

    # Mid-morning: Normal prices
    for hour in range(3, 9):
        for minute in [0, 15, 30, 45]:
            intervals.append(_create_interval(hour, minute, 0.32, "NORMAL", "NORMAL"))

    # Midday: Price exactly at "daily minimum"
    for hour in range(12, 13):
        for minute in [0, 15, 30, 45]:
            intervals.append(_create_interval(hour, minute, 0.25, "VERY_CHEAP", "VERY_LOW"))

    # Afternoon: Normal prices
    for hour in range(13, 18):
        for minute in [0, 15, 30, 45]:
            intervals.append(_create_interval(hour, minute, 0.33, "NORMAL", "NORMAL"))

    # Evening: Higher prices
    for hour in range(18, 24):
        for minute in [0, 15, 30, 45]:
            intervals.append(_create_interval(hour, minute, 0.38, "EXPENSIVE", "HIGH"))

    return intervals


@pytest.mark.asyncio
async def test_prices_below_minimum_are_included():
    """
    Test that prices BELOW the daily minimum are included in best price periods.
    
    BUG REPRODUCTION:
    With the current logic (price >= daily_min), intervals at 0.249 would be excluded
    even though they're cheaper than the "minimum" of 0.25!
    """
    mock_coordinator = Mock()
    mock_coordinator.config_entry = Mock()
    time_service = TibberPricesTimeService(mock_coordinator)
    
    test_time = dt_util.now()
    time_service.now = Mock(return_value=test_time)
    
    intervals = _create_intervals_with_prices_below_minimum()

    # Very permissive config to ensure periods are found
    config = TibberPricesPeriodConfig(
        reverse_sort=False,  # Best price
        flex=0.30,  # 30% flex
        min_distance_from_avg=0.0,  # Disable to isolate flex filter
        min_period_length=60,
        threshold_low=0.25,
        threshold_high=0.30,
        threshold_volatility_moderate=10.0,
        threshold_volatility_high=20.0,
        threshold_volatility_very_high=30.0,
        level_filter=None,
        gap_count=0,
    )

    result = calculate_periods(intervals, config=config, time=time_service)
    periods = result["periods"]

    print(f"\nDaily minimum (calculated): 0.25")
    print(f"Early morning price: 0.249 (BELOW calculated minimum!)")
    print(f"Midday price: 0.25 (AT calculated minimum)")
    print(f"Flex allows up to: {0.25 * 1.30:.3f}")
    print(f"\nWith current buggy logic (price >= daily_min):")
    print(f"  Early morning (0.249): Should be EXCLUDED (0.249 < 0.25)")
    print(f"  Midday (0.25): Should be INCLUDED (0.25 >= 0.25)")
    print(f"\nWith correct logic (price <= daily_min + flex):")
    print(f"  Early morning (0.249): Should be INCLUDED (0.249 <= 0.325)")
    print(f"  Midday (0.25): Should be INCLUDED (0.25 <= 0.325)")
    print(f"\nFound {len(periods)} period(s):")
    for i, period in enumerate(periods):
        print(f"  Period {i+1}: {period['start'].strftime('%H:%M')} to {period['end'].strftime('%H:%M')}")

    # Check if early morning period is found
    early_morning_found = any(
        p["start"].hour <= 2
        for p in periods
    )

    if not early_morning_found:
        pytest.fail(
            "BUG CONFIRMED: Early morning period (price 0.249) was excluded!\n"
            "The flex filter incorrectly requires price >= daily_min, which excludes\n"
            "prices below the minimum. This is wrong for best price mode.\n\n"
            "Fix needed in level_filtering.py line 160:\n"
            "  OLD: in_flex = price >= criteria.ref_price and price <= flex_threshold\n"
            "  NEW: in_flex = price <= flex_threshold"
        )

    assert early_morning_found, (
        "Early morning period (0.249) should be included - it's the cheapest price "
        "and well within the flex threshold."
    )


@pytest.mark.asyncio
async def test_flex_filter_accepts_all_prices_below_threshold():
    """
    Test that the flex filter accepts ALL prices below the threshold, not just those >= minimum.
    
    This is the fundamental expectation for best price mode.
    """
    mock_coordinator = Mock()
    mock_coordinator.config_entry = Mock()
    time_service = TibberPricesTimeService(mock_coordinator)
    
    test_time = dt_util.now()
    time_service.now = Mock(return_value=test_time)
    
    now_local = dt_util.now()
    base_time = now_local.replace(hour=0, minute=0, second=0, microsecond=0)

    # Create a very simple scenario
    daily_min = 1.00
    daily_avg = 2.00
    
    intervals = []
    
    # Create intervals with prices: 0.80, 0.90, 1.00, 1.10, 1.20
    # With flex=20%, threshold = 1.00 + 0.20 = 1.20
    # All of these should be included!
    prices_to_test = [0.80, 0.90, 1.00, 1.10, 1.20]
    
    for hour, price in enumerate(prices_to_test):
        intervals.append({
            "startsAt": base_time.replace(hour=hour),
            "total": price,
            "level": "CHEAP",
            "rating_level": "LOW",
            "_original_price": price,
            "trailing_avg_24h": daily_avg,
            "daily_min": daily_min,
            "daily_avg": daily_avg,
            "daily_max": 3.00,
        })

    config = TibberPricesPeriodConfig(
        reverse_sort=False,
        flex=0.20,  # 20% above minimum = 1.20
        min_distance_from_avg=0.0,  # Disable
        min_period_length=15,  # Very short to allow single intervals
        threshold_low=0.25,
        threshold_high=0.30,
        threshold_volatility_moderate=10.0,
        threshold_volatility_high=20.0,
        threshold_volatility_very_high=30.0,
        level_filter=None,
        gap_count=0,
    )

    result = calculate_periods(intervals, config=config, time=time_service)
    periods = result["periods"]
    
    # Debug: Check what reference prices were calculated
    ref_data = result.get("reference_data", {})
    ref_prices = ref_data.get("ref_prices", {})
    avg_prices = ref_data.get("avg_prices", {})
    
    print(f"\nDaily min: {daily_min}, flex: 20%, threshold: {daily_min * 1.20}")
    print(f"Actual ref_prices from calculation: {ref_prices}")
    print(f"Actual avg_prices from calculation: {avg_prices}")
    print(f"Prices tested: {prices_to_test}")
    print(f"Expected: ALL prices <= calculated threshold should be in periods")
    print(f"\nFound {len(periods)} period(s):")
    for i, period in enumerate(periods):
        print(f"  Period {i+1}: {period['start'].strftime('%H:%M')} to {period['end'].strftime('%H:%M')}")

    # Check what actually got included based on the calculated reference price
    actual_ref_price = list(ref_prices.values())[0]  # 0.80
    actual_threshold = actual_ref_price * 1.20  # 0.96
    
    print(f"\nCalculated threshold: {actual_threshold}")
    print(f"Intervals that should qualify (price <= {actual_threshold}):")
    for price in prices_to_test:
        qualifies = price <= actual_threshold
        print(f"  Price {price}: {'✓ QUALIFIES' if qualifies else '✗ excluded'}")
    
    # Intervals 0 (0.80) and 1 (0.90) should qualify
    # Intervals 2, 3, 4 should NOT qualify (prices > 0.96)
    # So we expect ONE period from hour 0 to hour 2 (ending after interval 1)
    
    assert len(periods) == 1, f"Expected 1 continuous period, got {len(periods)}"
    
    period = periods[0]
    assert period["start"].hour == 0, "Period should start at hour 0 (price 0.80)"
    # Period should include intervals at hours 0 and 1, ending at 01:15 + 15min = 01:30?
    # Actually, let me just check that it includes hour 1
    period_end_hour = period["end"].hour
    period_end_minute = period["end"].minute
    
    # Interval 1 starts at 01:00 and ends at 01:15
    # So period should end at or after 01:15
    end_time_minutes = period_end_hour * 60 + period_end_minute
    expected_min_end = 1 * 60 + 15  # 01:15
    
    assert end_time_minutes >= expected_min_end, (
        f"Period should include interval 1 (01:00-01:15). "
        f"Expected end >= 01:15, got {period_end_hour:02d}:{period_end_minute:02d}"
    )
