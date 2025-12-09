"""Test midnight-crossing period assignment with group_periods_by_day()."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.tibber_prices.coordinator.period_handlers.relaxation import (
    group_periods_by_day,
)


@pytest.fixture
def base_date() -> datetime:
    """Provide base date for tests."""
    return datetime(2025, 11, 21, 0, 0, 0, tzinfo=ZoneInfo("Europe/Berlin"))


def create_test_period(start_hour: int, end_hour: int, base_date: datetime) -> dict:
    """Create a test period dict."""
    start = base_date.replace(hour=start_hour, minute=0, second=0, microsecond=0)

    # Handle periods crossing midnight
    if end_hour < start_hour:
        end = (base_date + timedelta(days=1)).replace(hour=end_hour, minute=0, second=0, microsecond=0)
    else:
        end = base_date.replace(hour=end_hour, minute=0, second=0, microsecond=0)

    return {
        "start": start,
        "end": end,
        "duration_minutes": int((end - start).total_seconds() / 60),
        "price_median": 25.5,
    }


@pytest.mark.unit
def test_period_within_single_day(base_date: datetime) -> None:
    """Test period completely within one day (10:00-14:00)."""
    periods = [create_test_period(10, 14, base_date)]

    result = group_periods_by_day(periods)

    assert len(result) == 1, f"Expected 1 day, got {len(result)}"


@pytest.mark.unit
def test_period_crossing_midnight(base_date: datetime) -> None:
    """Test period crossing midnight (23:00-02:00)."""
    periods = [create_test_period(23, 2, base_date)]

    result = group_periods_by_day(periods)

    assert len(result) == 2, f"Expected 2 days, got {len(result)}"

    # Verify the period appears in both days
    today = base_date.date()
    tomorrow = (base_date + timedelta(days=1)).date()
    assert today in result, f"Period should appear in {today}"
    assert tomorrow in result, f"Period should appear in {tomorrow}"


@pytest.mark.unit
def test_multiple_periods_with_midnight_crossing(base_date: datetime) -> None:
    """Test multiple periods, some crossing midnight (8:00-12:00, 14:00-18:00, 22:00-03:00)."""
    periods = [
        create_test_period(8, 12, base_date),  # Morning, same day
        create_test_period(14, 18, base_date),  # Afternoon, same day
        create_test_period(22, 3, base_date),  # Night, crosses midnight
    ]

    result = group_periods_by_day(periods)

    today = base_date.date()
    tomorrow = (base_date + timedelta(days=1)).date()

    # Check that today has 3 periods (all of them)
    today_periods = result.get(today, [])
    assert len(today_periods) == 3, f"Today should have 3 periods, got {len(today_periods)}"

    # Check that tomorrow has 1 period (the midnight-crossing one)
    tomorrow_periods = result.get(tomorrow, [])
    assert len(tomorrow_periods) == 1, f"Tomorrow should have 1 period, got {len(tomorrow_periods)}"


@pytest.mark.unit
def test_period_spanning_three_days(base_date: datetime) -> None:
    """Test period spanning 3 days (22:00 day1 - 02:00 day3)."""
    day1 = base_date
    day3 = base_date + timedelta(days=2)

    period = {
        "start": day1.replace(hour=22, minute=0),
        "end": day3.replace(hour=2, minute=0),
        "duration_minutes": int((day3.replace(hour=2) - day1.replace(hour=22)).total_seconds() / 60),
        "price_median": 25.5,
    }

    periods = [period]
    result = group_periods_by_day(periods)

    assert len(result) == 3, f"Expected 3 days, got {len(result)}"

    # Verify the period appears in all 3 days
    day1_date = day1.date()
    day2_date = (base_date + timedelta(days=1)).date()
    day3_date = day3.date()
    assert day1_date in result, f"Period should appear in {day1_date}"
    assert day2_date in result, f"Period should appear in {day2_date}"
    assert day3_date in result, f"Period should appear in {day3_date}"


@pytest.mark.unit
def test_min_periods_scenario(base_date: datetime) -> None:
    """Test real-world scenario with min_periods=2 per day."""
    # Yesterday: 2 periods (one crosses midnight to today)
    yesterday = base_date - timedelta(days=1)
    periods = [
        create_test_period(10, 14, yesterday),  # Yesterday 10-14
        create_test_period(23, 2, yesterday),  # Yesterday 23 - Today 02 (crosses midnight!)
        create_test_period(15, 19, base_date),  # Today 15-19
    ]

    result = group_periods_by_day(periods)

    yesterday_date = yesterday.date()
    today_date = base_date.date()

    yesterday_periods = result.get(yesterday_date, [])
    today_periods = result.get(today_date, [])

    # Both days should have 2 periods (min_periods requirement met)
    assert len(yesterday_periods) == 2, "Yesterday should have 2 periods"
    assert len(today_periods) == 2, "Today should have 2 periods (including midnight-crosser)"
