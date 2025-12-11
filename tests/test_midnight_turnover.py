"""Test midnight turnover consistency - period visibility before/after midnight."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest

from custom_components.tibber_prices.coordinator.period_handlers.core import (
    calculate_periods,
)
from custom_components.tibber_prices.coordinator.period_handlers.types import (
    TibberPricesPeriodConfig,
)
from custom_components.tibber_prices.coordinator.time_service import (
    TibberPricesTimeService,
)


def create_price_interval(dt: datetime, price: float) -> dict:
    """Create a price interval dict."""
    return {
        "startsAt": dt,
        "total": price,
        "level": "NORMAL",
        "rating_level": "NORMAL",
    }


def create_price_data_scenario() -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """Create a realistic price scenario with a period crossing midnight."""
    tz = ZoneInfo("Europe/Berlin")
    base = datetime(2025, 11, 21, 0, 0, 0, tzinfo=tz)

    # Define cheap hour ranges for each day
    cheap_hours = {
        "yesterday": range(22, 24),  # 22:00-23:45
        "today": range(21, 24),  # 21:00-23:45 (crosses midnight!)
        "tomorrow": range(1),  # 00:00-00:45 (continuation)
    }

    def generate_day_prices(day_dt: datetime, cheap_range: range) -> list[dict]:
        """Generate 15-min interval prices for a day."""
        prices = []
        for hour in range(24):
            for minute in [0, 15, 30, 45]:
                dt = day_dt.replace(hour=hour, minute=minute)
                price = 15.0 if hour in cheap_range else 30.0
                prices.append(create_price_interval(dt, price))
        return prices

    yesterday_prices = generate_day_prices(base - timedelta(days=1), cheap_hours["yesterday"])
    today_prices = generate_day_prices(base, cheap_hours["today"])
    tomorrow_prices = generate_day_prices(base + timedelta(days=1), cheap_hours["tomorrow"])
    day_after_tomorrow_prices = generate_day_prices(base + timedelta(days=2), range(0))  # No cheap hours

    return yesterday_prices, today_prices, tomorrow_prices, day_after_tomorrow_prices


@pytest.fixture
def period_config() -> TibberPricesPeriodConfig:
    """Provide test period configuration."""
    return TibberPricesPeriodConfig(
        reverse_sort=False,  # Best price (cheap periods)
        flex=0.50,  # 50% flexibility
        min_distance_from_avg=-5.0,  # -5% below average
        min_period_length=60,  # 60 minutes minimum
        threshold_low=20.0,
        threshold_high=30.0,
        threshold_volatility_moderate=0.3,
        threshold_volatility_high=0.5,
        threshold_volatility_very_high=0.7,
        level_filter=None,
        gap_count=0,
    )


@pytest.mark.integration
def test_midnight_crossing_period_consistency(period_config: TibberPricesPeriodConfig) -> None:
    """
    Test that midnight-crossing periods remain visible before and after midnight turnover.

    This test simulates the real-world scenario where:
    - Before midnight (21st 22:00): Period 21:00→01:00 is visible
    - After midnight (22nd 00:30): Same period should still be visible

    The period starts on 2025-11-21 (yesterday after turnover) and ends on 2025-11-22 (today).
    """
    tz = ZoneInfo("Europe/Berlin")
    yesterday_prices, today_prices, tomorrow_prices, day_after_tomorrow_prices = create_price_data_scenario()

    # Create mock config entry
    mock_config_entry = Mock()
    mock_config_entry.options.get.return_value = "minor"

    # SCENARIO 1: Before midnight (today = 2025-11-21 22:00)
    current_time_before = datetime(2025, 11, 21, 22, 0, 0, tzinfo=tz)
    time_service_before = TibberPricesTimeService(current_time_before)
    all_prices_before = yesterday_prices + today_prices + tomorrow_prices

    result_before = calculate_periods(
        all_prices_before,
        config=period_config,
        time=time_service_before,
        config_entry=mock_config_entry,
    )
    periods_before = result_before["periods"]

    # Find the midnight-crossing period (starts 21st, ends 22nd)
    midnight_period_before = None
    for period in periods_before:
        if period["start"].date().isoformat() == "2025-11-21" and period["end"].date().isoformat() == "2025-11-22":
            midnight_period_before = period
            break

    assert midnight_period_before is not None, "Expected to find midnight-crossing period before turnover"

    # SCENARIO 2: After midnight turnover (today = 2025-11-22 00:30)
    current_time_after = datetime(2025, 11, 22, 0, 30, 0, tzinfo=tz)
    time_service_after = TibberPricesTimeService(current_time_after)

    # Simulate coordinator data shift: yesterday=21st, today=22nd, tomorrow=23rd
    yesterday_after_turnover = today_prices
    today_after_turnover = tomorrow_prices
    tomorrow_after_turnover = day_after_tomorrow_prices
    all_prices_after = yesterday_after_turnover + today_after_turnover + tomorrow_after_turnover

    result_after = calculate_periods(
        all_prices_after,
        config=period_config,
        time=time_service_after,
        config_entry=mock_config_entry,
    )
    periods_after = result_after["periods"]

    # Find period that started on 2025-11-21 (now "yesterday")
    period_from_yesterday_after = None
    for period in periods_after:
        if period["start"].date().isoformat() == "2025-11-21":
            period_from_yesterday_after = period
            break

    assert period_from_yesterday_after is not None, (
        "Expected midnight-crossing period to remain visible after turnover (we're at 00:30, period ends at 01:00)"
    )

    # Verify consistency: same absolute times
    assert midnight_period_before["start"] == period_from_yesterday_after["start"], "Start time should match"
    assert midnight_period_before["end"] == period_from_yesterday_after["end"], "End time should match"
    assert midnight_period_before["duration_minutes"] == period_from_yesterday_after["duration_minutes"], (
        "Duration should match"
    )
