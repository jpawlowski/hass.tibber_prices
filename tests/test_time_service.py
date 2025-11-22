"""Tests for TimeService - critical time handling with boundary tolerance and DST."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from custom_components.tibber_prices.coordinator.time_service import (
    TibberPricesTimeService,
)

# =============================================================================
# Quarter-Hour Rounding with Boundary Tolerance (CRITICAL)
# =============================================================================


def test_round_to_quarter_exact_boundary() -> None:
    """Test rounding when exactly on boundary."""
    time_service = TibberPricesTimeService(datetime(2025, 11, 22, 14, 0, 0, tzinfo=UTC))
    rounded = time_service.round_to_nearest_quarter()
    assert rounded == datetime(2025, 11, 22, 14, 0, 0, tzinfo=UTC)


def test_round_to_quarter_within_tolerance_before_boundary() -> None:
    """Test rounding when 2 seconds before boundary (within 2s tolerance)."""
    # 14:59:58 → should round UP to 15:00:00 (within 2s tolerance)
    time_service = TibberPricesTimeService(datetime(2025, 11, 22, 14, 59, 58, tzinfo=UTC))
    rounded = time_service.round_to_nearest_quarter()
    assert rounded == datetime(2025, 11, 22, 15, 0, 0, tzinfo=UTC)


def test_round_to_quarter_exactly_2s_before_boundary() -> None:
    """Test rounding when exactly 2 seconds before boundary (edge of 2s tolerance)."""
    # 14:59:58 → should round UP to 15:00:00 (exactly 2s tolerance)
    time_service = TibberPricesTimeService(datetime(2025, 11, 22, 14, 59, 58, tzinfo=UTC))
    rounded = time_service.round_to_nearest_quarter()
    assert rounded == datetime(2025, 11, 22, 15, 0, 0, tzinfo=UTC)


def test_round_to_quarter_just_outside_tolerance_before() -> None:
    """Test rounding when 3 seconds before boundary (outside 2s tolerance)."""
    # 14:59:57 → should STAY at 14:45:00 (>2s away from boundary)
    time_service = TibberPricesTimeService(datetime(2025, 11, 22, 14, 59, 57, tzinfo=UTC))
    rounded = time_service.round_to_nearest_quarter()
    assert rounded == datetime(2025, 11, 22, 14, 45, 0, tzinfo=UTC)


def test_round_to_quarter_within_2s_after_boundary() -> None:
    """Test rounding when 1 second after boundary (within 2s tolerance)."""
    # 15:00:01 → should round DOWN to 15:00:00 (within 2s tolerance)
    time_service = TibberPricesTimeService(datetime(2025, 11, 22, 15, 0, 1, tzinfo=UTC))
    rounded = time_service.round_to_nearest_quarter()
    assert rounded == datetime(2025, 11, 22, 15, 0, 0, tzinfo=UTC)


def test_round_to_quarter_exactly_2s_after_boundary() -> None:
    """Test rounding when exactly 2 seconds after boundary (edge of 2s tolerance)."""
    # 15:00:02 → should round DOWN to 15:00:00 (exactly 2s tolerance)
    time_service = TibberPricesTimeService(datetime(2025, 11, 22, 15, 0, 2, tzinfo=UTC))
    rounded = time_service.round_to_nearest_quarter()
    assert rounded == datetime(2025, 11, 22, 15, 0, 0, tzinfo=UTC)


def test_round_to_quarter_just_outside_tolerance_after() -> None:
    """Test rounding when 3 seconds after boundary (outside 2s tolerance)."""
    # 15:00:03 → should STAY at 15:00:00 (>2s away from next boundary)
    time_service = TibberPricesTimeService(datetime(2025, 11, 22, 15, 0, 3, tzinfo=UTC))
    rounded = time_service.round_to_nearest_quarter()
    assert rounded == datetime(2025, 11, 22, 15, 0, 0, tzinfo=UTC)


def test_round_to_quarter_mid_interval() -> None:
    """Test rounding when in middle of interval (far from boundaries)."""
    # 14:37:30 → should floor to 14:30:00 (not near any boundary)
    time_service = TibberPricesTimeService(datetime(2025, 11, 22, 14, 37, 30, tzinfo=UTC))
    rounded = time_service.round_to_nearest_quarter()
    assert rounded == datetime(2025, 11, 22, 14, 30, 0, tzinfo=UTC)


def test_round_to_quarter_microseconds_before_boundary() -> None:
    """Test rounding with microseconds just before boundary."""
    # 14:59:59.999999 → should round UP to 15:00:00
    time_service = TibberPricesTimeService(datetime(2025, 11, 22, 14, 59, 59, 999999, tzinfo=UTC))
    rounded = time_service.round_to_nearest_quarter()
    assert rounded == datetime(2025, 11, 22, 15, 0, 0, tzinfo=UTC)


def test_round_to_quarter_microseconds_after_boundary() -> None:
    """Test rounding with microseconds just after boundary."""
    # 15:00:00.000001 → should round DOWN to 15:00:00
    time_service = TibberPricesTimeService(datetime(2025, 11, 22, 15, 0, 0, 1, tzinfo=UTC))
    rounded = time_service.round_to_nearest_quarter()
    assert rounded == datetime(2025, 11, 22, 15, 0, 0, tzinfo=UTC)


def test_round_to_quarter_all_boundaries() -> None:
    """Test rounding at all four quarter-hour boundaries."""
    # Test :00, :15, :30, :45 boundaries
    boundaries = [
        (datetime(2025, 11, 22, 14, 0, 1, tzinfo=UTC), datetime(2025, 11, 22, 14, 0, 0, tzinfo=UTC)),
        (datetime(2025, 11, 22, 14, 15, 1, tzinfo=UTC), datetime(2025, 11, 22, 14, 15, 0, tzinfo=UTC)),
        (datetime(2025, 11, 22, 14, 30, 1, tzinfo=UTC), datetime(2025, 11, 22, 14, 30, 0, tzinfo=UTC)),
        (datetime(2025, 11, 22, 14, 45, 1, tzinfo=UTC), datetime(2025, 11, 22, 14, 45, 0, tzinfo=UTC)),
    ]

    for input_time, expected in boundaries:
        time_service = TibberPricesTimeService(input_time)
        rounded = time_service.round_to_nearest_quarter()
        assert rounded == expected, f"Failed for {input_time}: got {rounded}, expected {expected}"


def test_round_to_quarter_midnight_boundary_before() -> None:
    """Test rounding just before midnight (critical edge case)."""
    # 23:59:59 → should round to midnight 00:00:00 of NEXT day (1 second away, within tolerance)
    time_service = TibberPricesTimeService(datetime(2025, 11, 22, 23, 59, 59, tzinfo=UTC))
    rounded = time_service.round_to_nearest_quarter()
    # Within 2s of midnight boundary, rounds to 00:00:00 of NEXT day (Nov 23)
    assert rounded == datetime(2025, 11, 23, 0, 0, 0, tzinfo=UTC)


def test_round_to_quarter_midnight_boundary_at() -> None:
    """Test rounding exactly at midnight."""
    # 00:00:00 → should stay 00:00:00
    time_service = TibberPricesTimeService(datetime(2025, 11, 23, 0, 0, 0, tzinfo=UTC))
    rounded = time_service.round_to_nearest_quarter()
    assert rounded == datetime(2025, 11, 23, 0, 0, 0, tzinfo=UTC)


def test_round_to_quarter_first_interval_of_day() -> None:
    """Test rounding in first interval of day."""
    # 00:07:30 → should floor to 00:00:00
    time_service = TibberPricesTimeService(datetime(2025, 11, 23, 0, 7, 30, tzinfo=UTC))
    rounded = time_service.round_to_nearest_quarter()
    assert rounded == datetime(2025, 11, 23, 0, 0, 0, tzinfo=UTC)


def test_round_to_quarter_last_interval_of_day() -> None:
    """Test rounding in last interval of day (23:45-00:00)."""
    # 23:52:30 → should floor to 23:45:00 (same day, not near boundary)
    time_service = TibberPricesTimeService(datetime(2025, 11, 22, 23, 52, 30, tzinfo=UTC))
    rounded = time_service.round_to_nearest_quarter()
    assert rounded == datetime(2025, 11, 22, 23, 45, 0, tzinfo=UTC)


def test_round_to_quarter_midnight_wrap_exactly_2s_before() -> None:
    """Test rounding exactly 2 seconds before midnight (edge of 2s tolerance)."""
    # 23:59:58 → should round to midnight 00:00:00 of NEXT day (exactly 2s tolerance)
    time_service = TibberPricesTimeService(datetime(2025, 11, 22, 23, 59, 58, tzinfo=UTC))
    rounded = time_service.round_to_nearest_quarter()
    assert rounded == datetime(2025, 11, 23, 0, 0, 0, tzinfo=UTC)


def test_round_to_quarter_midnight_wrap_outside_tolerance() -> None:
    """Test rounding 3 seconds before midnight (outside 2s tolerance)."""
    # 23:59:57 → should STAY at 23:45:00 (>2s away from boundary)
    time_service = TibberPricesTimeService(datetime(2025, 11, 22, 23, 59, 57, tzinfo=UTC))
    rounded = time_service.round_to_nearest_quarter()
    assert rounded == datetime(2025, 11, 22, 23, 45, 0, tzinfo=UTC)


def test_round_to_quarter_midnight_wrap_with_microseconds() -> None:
    """Test rounding with microseconds just before midnight."""
    # 23:59:59.999999 → should round to midnight 00:00:00 of NEXT day
    time_service = TibberPricesTimeService(datetime(2025, 11, 22, 23, 59, 59, 999999, tzinfo=UTC))
    rounded = time_service.round_to_nearest_quarter()
    assert rounded == datetime(2025, 11, 23, 0, 0, 0, tzinfo=UTC)


# =============================================================================
# DST Handling (CRITICAL for 23h/25h days)
# =============================================================================


def test_get_expected_intervals_standard_day() -> None:
    """Test interval count on standard 24-hour day."""
    time_service = TibberPricesTimeService(datetime(2025, 11, 22, 12, 0, 0, tzinfo=UTC))
    # Standard day: 24 hours x 4 intervals/hour = 96 intervals
    count = time_service.get_expected_intervals_for_day(datetime(2025, 11, 22, tzinfo=UTC).date())
    assert count == 96


@pytest.mark.skip(reason="DST handling requires local timezone setup (Europe/Berlin) - tested in integration tests")
def test_get_expected_intervals_spring_dst_23h_day() -> None:
    """Test interval count on Spring DST day (23 hours, clock jumps forward)."""
    # In Europe: Last Sunday of March, 02:00 → 03:00 (23-hour day)
    # 2025-03-30 is the last Sunday of March
    # NOTE: This test requires time_service to use Europe/Berlin timezone, not UTC
    time_service = TibberPricesTimeService(datetime(2025, 3, 30, 12, 0, 0, tzinfo=UTC))
    count = time_service.get_expected_intervals_for_day(datetime(2025, 3, 30, tzinfo=UTC).date())
    # 23 hours x 4 intervals/hour = 92 intervals
    assert count == 92


@pytest.mark.skip(reason="DST handling requires local timezone setup (Europe/Berlin) - tested in integration tests")
def test_get_expected_intervals_fall_dst_25h_day() -> None:
    """Test interval count on Fall DST day (25 hours, clock jumps backward)."""
    # In Europe: Last Sunday of October, 03:00 → 02:00 (25-hour day)
    # 2025-10-26 is the last Sunday of October
    # NOTE: This test requires time_service to use Europe/Berlin timezone, not UTC
    time_service = TibberPricesTimeService(datetime(2025, 10, 26, 12, 0, 0, tzinfo=UTC))
    count = time_service.get_expected_intervals_for_day(datetime(2025, 10, 26, tzinfo=UTC).date())
    # 25 hours x 4 intervals/hour = 100 intervals
    assert count == 100


# =============================================================================
# Day Boundaries
# =============================================================================


def test_get_day_boundaries_today() -> None:
    """Test day boundaries for 'today'."""
    time_service = TibberPricesTimeService(datetime(2025, 11, 22, 14, 30, 0, tzinfo=UTC))
    start, end = time_service.get_day_boundaries("today")

    # Start should be midnight today
    assert start.hour == 0
    assert start.minute == 0
    assert start.second == 0
    assert start.date() == datetime(2025, 11, 22, tzinfo=UTC).date()

    # End should be midnight tomorrow
    assert end.hour == 0
    assert end.minute == 0
    assert end.second == 0
    assert end.date() == datetime(2025, 11, 23, tzinfo=UTC).date()


def test_get_day_boundaries_yesterday() -> None:
    """Test day boundaries for 'yesterday'."""
    time_service = TibberPricesTimeService(datetime(2025, 11, 22, 14, 30, 0, tzinfo=UTC))
    start, end = time_service.get_day_boundaries("yesterday")

    # Start should be midnight yesterday
    assert start.date() == datetime(2025, 11, 21, tzinfo=UTC).date()

    # End should be midnight today
    assert end.date() == datetime(2025, 11, 22, tzinfo=UTC).date()


def test_get_day_boundaries_tomorrow() -> None:
    """Test day boundaries for 'tomorrow'."""
    time_service = TibberPricesTimeService(datetime(2025, 11, 22, 14, 30, 0, tzinfo=UTC))
    start, end = time_service.get_day_boundaries("tomorrow")

    # Start should be midnight tomorrow
    assert start.date() == datetime(2025, 11, 23, tzinfo=UTC).date()

    # End should be midnight day after tomorrow
    assert end.date() == datetime(2025, 11, 24, tzinfo=UTC).date()


# =============================================================================
# Interval Offset Calculations
# =============================================================================


def test_get_interval_offset_current() -> None:
    """Test offset=0 returns current interval start."""
    time_service = TibberPricesTimeService(datetime(2025, 11, 22, 14, 37, 23, tzinfo=UTC))
    result = time_service.get_interval_offset_time(0)
    assert result == datetime(2025, 11, 22, 14, 30, 0, tzinfo=UTC)


def test_get_interval_offset_next() -> None:
    """Test offset=1 returns next interval start."""
    time_service = TibberPricesTimeService(datetime(2025, 11, 22, 14, 37, 23, tzinfo=UTC))
    result = time_service.get_interval_offset_time(1)
    assert result == datetime(2025, 11, 22, 14, 45, 0, tzinfo=UTC)


def test_get_interval_offset_previous() -> None:
    """Test offset=-1 returns previous interval start."""
    time_service = TibberPricesTimeService(datetime(2025, 11, 22, 14, 37, 23, tzinfo=UTC))
    result = time_service.get_interval_offset_time(-1)
    assert result == datetime(2025, 11, 22, 14, 15, 0, tzinfo=UTC)


def test_get_interval_offset_multiple_forward() -> None:
    """Test multiple intervals forward."""
    time_service = TibberPricesTimeService(datetime(2025, 11, 22, 14, 37, 23, tzinfo=UTC))
    result = time_service.get_interval_offset_time(4)  # +1 hour
    assert result == datetime(2025, 11, 22, 15, 30, 0, tzinfo=UTC)


def test_get_interval_offset_cross_hour_boundary() -> None:
    """Test offset crossing hour boundary."""
    time_service = TibberPricesTimeService(datetime(2025, 11, 22, 14, 52, 0, tzinfo=UTC))
    # Current: 14:45, +1 = 15:00
    result = time_service.get_interval_offset_time(1)
    assert result == datetime(2025, 11, 22, 15, 0, 0, tzinfo=UTC)


def test_get_interval_offset_cross_day_boundary() -> None:
    """Test offset crossing midnight."""
    time_service = TibberPricesTimeService(datetime(2025, 11, 22, 23, 52, 0, tzinfo=UTC))
    # Current: 23:45, +1 = 00:00 next day
    result = time_service.get_interval_offset_time(1)
    assert result == datetime(2025, 11, 23, 0, 0, 0, tzinfo=UTC)


# =============================================================================
# Time Comparison Helpers
# =============================================================================


def test_is_current_interval_true() -> None:
    """Test is_current_interval returns True when time is in interval."""
    time_service = TibberPricesTimeService(datetime(2025, 11, 22, 14, 37, 0, tzinfo=UTC))
    start = datetime(2025, 11, 22, 14, 30, 0, tzinfo=UTC)
    end = datetime(2025, 11, 22, 14, 45, 0, tzinfo=UTC)
    assert time_service.is_current_interval(start, end) is True


def test_is_current_interval_false_before() -> None:
    """Test is_current_interval returns False when time is before interval."""
    time_service = TibberPricesTimeService(datetime(2025, 11, 22, 14, 29, 0, tzinfo=UTC))
    start = datetime(2025, 11, 22, 14, 30, 0, tzinfo=UTC)
    end = datetime(2025, 11, 22, 14, 45, 0, tzinfo=UTC)
    assert time_service.is_current_interval(start, end) is False


def test_is_current_interval_false_after() -> None:
    """Test is_current_interval returns False when time is after interval."""
    time_service = TibberPricesTimeService(datetime(2025, 11, 22, 14, 45, 0, tzinfo=UTC))
    start = datetime(2025, 11, 22, 14, 30, 0, tzinfo=UTC)
    end = datetime(2025, 11, 22, 14, 45, 0, tzinfo=UTC)
    # end is exclusive, so exactly at end is False
    assert time_service.is_current_interval(start, end) is False


def test_is_current_interval_at_start() -> None:
    """Test is_current_interval returns True when exactly at start."""
    time_service = TibberPricesTimeService(datetime(2025, 11, 22, 14, 30, 0, tzinfo=UTC))
    start = datetime(2025, 11, 22, 14, 30, 0, tzinfo=UTC)
    end = datetime(2025, 11, 22, 14, 45, 0, tzinfo=UTC)
    # start is inclusive
    assert time_service.is_current_interval(start, end) is True


# =============================================================================
# Time-Travel (Reference Time Injection)
# =============================================================================


def test_reference_time_consistency() -> None:
    """Test that reference time stays consistent throughout service lifetime."""
    ref_time = datetime(2025, 11, 22, 14, 37, 23, tzinfo=UTC)
    time_service = TibberPricesTimeService(ref_time)

    # Multiple calls should return same value
    assert time_service.now() == ref_time
    assert time_service.now() == ref_time
    assert time_service.now() == ref_time


def test_time_travel_simulation() -> None:
    """Test time-travel capability (inject specific time)."""
    # Simulate being at a specific moment in the past
    past_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
    time_service = TibberPricesTimeService(past_time)

    assert time_service.now() == past_time
    assert time_service.now().year == 2024
    assert time_service.now().month == 1


# =============================================================================
# Minutes Calculation and Rounding
# =============================================================================


def test_minutes_until_rounded_standard_rounding() -> None:
    """Test minutes_until_rounded uses standard rounding (0.5 rounds up)."""
    ref_time = datetime(2025, 11, 22, 14, 0, 0, tzinfo=UTC)
    time_service = TibberPricesTimeService(ref_time)

    # 44.2 minutes → 44
    future = datetime(2025, 11, 22, 14, 44, 12, tzinfo=UTC)
    assert time_service.minutes_until_rounded(future) == 44

    # 44.5 minutes → 45 (rounds up)
    future = datetime(2025, 11, 22, 14, 44, 30, tzinfo=UTC)
    assert time_service.minutes_until_rounded(future) == 45

    # 44.7 minutes → 45
    future = datetime(2025, 11, 22, 14, 44, 42, tzinfo=UTC)
    assert time_service.minutes_until_rounded(future) == 45


def test_minutes_until_rounded_zero() -> None:
    """Test minutes_until_rounded returns 0 for past times."""
    ref_time = datetime(2025, 11, 22, 14, 0, 0, tzinfo=UTC)
    time_service = TibberPricesTimeService(ref_time)

    past = datetime(2025, 11, 22, 13, 0, 0, tzinfo=UTC)
    assert time_service.minutes_until_rounded(past) == -60


def test_minutes_until_rounded_string_input() -> None:
    """Test minutes_until_rounded accepts ISO string input."""
    ref_time = datetime(2025, 11, 22, 14, 0, 0, tzinfo=UTC)
    time_service = TibberPricesTimeService(ref_time)

    # Should parse and calculate
    result = time_service.minutes_until_rounded("2025-11-22T15:00:00+00:00")
    assert result == 60
