"""
Unit tests for midnight turnover handler.

These tests verify the atomic coordination logic that prevents duplicate
midnight turnover between multiple timers.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from custom_components.tibber_prices.coordinator.midnight_handler import (
    TibberPricesMidnightHandler,
)


@pytest.mark.unit
def test_first_check_initializes_without_turnover() -> None:
    """Test that the first check initializes but doesn't trigger turnover."""
    handler = TibberPricesMidnightHandler()

    time1 = datetime(2025, 11, 22, 14, 30, 0, tzinfo=ZoneInfo("Europe/Oslo"))

    # First check should return False (no turnover yet)
    assert not handler.is_turnover_needed(time1)

    # But update_check_time should initialize
    handler.update_check_time(time1)
    assert handler.last_check_time == time1


@pytest.mark.unit
def test_midnight_crossing_triggers_turnover() -> None:
    """Test that crossing midnight triggers turnover detection."""
    handler = TibberPricesMidnightHandler()

    # Initialize at 23:59:59 on Nov 22
    time1 = datetime(2025, 11, 22, 23, 59, 59, tzinfo=ZoneInfo("Europe/Oslo"))
    handler.update_check_time(time1)

    # Check at 00:00:00 on Nov 23 (midnight crossed!)
    time2 = datetime(2025, 11, 23, 0, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    assert handler.is_turnover_needed(time2)


@pytest.mark.unit
def test_same_day_no_turnover() -> None:
    """Test that multiple checks on the same day don't trigger turnover."""
    handler = TibberPricesMidnightHandler()

    # Initialize at 10:00
    time1 = datetime(2025, 11, 22, 10, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    handler.update_check_time(time1)

    # Check later same day at 14:00
    time2 = datetime(2025, 11, 22, 14, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    assert not handler.is_turnover_needed(time2)

    # Check even later at 23:59
    time3 = datetime(2025, 11, 22, 23, 59, 59, tzinfo=ZoneInfo("Europe/Oslo"))
    assert not handler.is_turnover_needed(time3)


@pytest.mark.unit
def test_atomic_coordination_prevents_duplicate_turnover() -> None:
    """Test that marking turnover done prevents duplicate execution."""
    handler = TibberPricesMidnightHandler()

    # Initialize on Nov 22
    time1 = datetime(2025, 11, 22, 23, 50, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    handler.update_check_time(time1)

    # Midnight on Nov 23 - first timer detects it
    midnight = datetime(2025, 11, 23, 0, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    assert handler.is_turnover_needed(midnight)

    # First timer marks it done
    handler.mark_turnover_done(midnight)

    # Second timer checks shortly after - should return False
    time2 = datetime(2025, 11, 23, 0, 0, 10, tzinfo=ZoneInfo("Europe/Oslo"))
    assert not handler.is_turnover_needed(time2)


@pytest.mark.unit
def test_mark_turnover_updates_both_timestamps() -> None:
    """Test that mark_turnover_done updates both check and turnover timestamps."""
    handler = TibberPricesMidnightHandler()

    time1 = datetime(2025, 11, 22, 10, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    handler.update_check_time(time1)

    midnight = datetime(2025, 11, 23, 0, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    handler.mark_turnover_done(midnight)

    # Both timestamps should be updated
    assert handler.last_check_time == midnight
    assert handler.last_turnover_time == midnight


@pytest.mark.unit
def test_next_day_triggers_new_turnover() -> None:
    """Test that the next day's midnight triggers turnover again."""
    handler = TibberPricesMidnightHandler()

    # Day 1: Initialize and mark turnover done
    day1 = datetime(2025, 11, 22, 10, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    handler.update_check_time(day1)

    midnight1 = datetime(2025, 11, 23, 0, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    assert handler.is_turnover_needed(midnight1)
    handler.mark_turnover_done(midnight1)

    # Day 2: Next midnight should trigger again
    midnight2 = datetime(2025, 11, 24, 0, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    assert handler.is_turnover_needed(midnight2)


@pytest.mark.unit
def test_multiple_days_skipped_still_triggers() -> None:
    """Test that skipping multiple days still triggers turnover."""
    handler = TibberPricesMidnightHandler()

    # Last check on Nov 22
    time1 = datetime(2025, 11, 22, 10, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    handler.update_check_time(time1)

    # Check 3 days later on Nov 25 (skipped 23rd and 24th)
    time2 = datetime(2025, 11, 25, 14, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    assert handler.is_turnover_needed(time2)


@pytest.mark.unit
def test_update_check_time_without_triggering_turnover() -> None:
    """Test that update_check_time initializes without turnover side effects."""
    handler = TibberPricesMidnightHandler()

    time1 = datetime(2025, 11, 22, 10, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    handler.update_check_time(time1)

    # Last turnover should still be None
    assert handler.last_check_time == time1
    assert handler.last_turnover_time is None

    # Next day should trigger turnover
    time2 = datetime(2025, 11, 23, 0, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    assert handler.is_turnover_needed(time2)


@pytest.mark.unit
def test_ha_restart_after_midnight_with_cached_turnover() -> None:
    """
    Test HA restart scenario: cached turnover from yesterday, restart after midnight.

    Scenario:
    - Nov 21 23:50: Last turnover marked (before HA shutdown)
    - Nov 22 00:30: HA restarts (handler is fresh, but turnover was cached)
    - Expected: Turnover should be triggered to catch up

    This simulates: mark_turnover_done() was called on Nov 21, handler state is
    restored (simulated by manually setting _last_actual_turnover), then first
    check after restart should detect missed midnight.
    """
    handler = TibberPricesMidnightHandler()

    # Simulate: Last turnover was on Nov 21 at 23:59:59 (just before midnight)
    last_turnover = datetime(2025, 11, 21, 23, 59, 59, tzinfo=ZoneInfo("Europe/Oslo"))
    # Manually restore handler state (simulates cache restoration)
    handler._last_actual_turnover = last_turnover  # noqa: SLF001 - Test setup

    # HA restarts at Nov 22 00:30 (after midnight)
    restart_time = datetime(2025, 11, 22, 0, 30, 0, tzinfo=ZoneInfo("Europe/Oslo"))

    # First check after restart - should detect missed midnight
    # _last_midnight_check is None (fresh handler), but _last_actual_turnover exists
    assert handler.is_turnover_needed(restart_time) is True

    # Perform turnover
    handler.mark_turnover_done(restart_time)

    # Second check - should not trigger again
    time_2 = datetime(2025, 11, 22, 1, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    assert handler.is_turnover_needed(time_2) is False


@pytest.mark.unit
def test_ha_restart_same_day_with_cached_turnover() -> None:
    """
    Test HA restart scenario: cached turnover from today, restart same day.

    Scenario:
    - Nov 22 00:05: Turnover happened (after HA started)
    - Nov 22 14:00: HA restarts
    - Expected: No turnover needed (already done today)

    This ensures we don't trigger duplicate turnover when restarting same day.
    """
    handler = TibberPricesMidnightHandler()

    # Simulate: Last turnover was today at 00:05
    last_turnover = datetime(2025, 11, 22, 0, 5, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    # Manually restore handler state (simulates cache restoration)
    handler._last_actual_turnover = last_turnover  # noqa: SLF001 - Test setup

    # HA restarts at 14:00 same day
    restart_time = datetime(2025, 11, 22, 14, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))

    # First check after restart - should NOT trigger (same day)
    assert handler.is_turnover_needed(restart_time) is False

    # Initialize check time for subsequent checks
    handler.update_check_time(restart_time)

    # Later check same day - still no turnover
    time_2 = datetime(2025, 11, 22, 18, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    assert handler.is_turnover_needed(time_2) is False


@pytest.mark.unit
def test_simultaneous_timer_checks_at_midnight() -> None:
    """
    Test race condition: Timer #1 and Timer #2 both check at exactly 00:00:00.

    This is the critical atomic coordination test - both timers detect midnight
    simultaneously, but only one should perform turnover.

    Scenario:
    - Nov 21 23:45: Both timers initialized
    - Nov 22 00:00:00: Both timers check simultaneously
    - Expected: First check returns True, second returns False (atomic)
    """
    handler = TibberPricesMidnightHandler()

    # Initialize on Nov 21 at 23:45
    init_time = datetime(2025, 11, 21, 23, 45, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    handler.update_check_time(init_time)

    # Both timers wake up at exactly 00:00:00
    midnight = datetime(2025, 11, 22, 0, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))

    # Timer #1 checks first (or both check "simultaneously" in sequence)
    timer1_check = handler.is_turnover_needed(midnight)
    assert timer1_check is True  # Midnight crossed

    # Timer #1 performs turnover
    handler.mark_turnover_done(midnight)

    # Timer #2 checks immediately after (could be microseconds later)
    timer2_check = handler.is_turnover_needed(midnight)
    assert timer2_check is False  # Already done by Timer #1

    # Verify state: turnover happened exactly once
    assert handler.last_turnover_time == midnight
    assert handler.last_check_time == midnight


@pytest.mark.unit
def test_timer_check_at_00_00_01_after_turnover_at_00_00_00() -> None:
    """
    Test edge case: One timer does turnover at 00:00:00, second checks at 00:00:01.

    This ensures that even a 1-second delay doesn't cause duplicate turnover
    when both checks happen on the same calendar day.

    Scenario:
    - Nov 22 00:00:00: Timer #1 does turnover
    - Nov 22 00:00:01: Timer #2 checks (1 second later)
    - Expected: Timer #2 should skip (same day)
    """
    handler = TibberPricesMidnightHandler()

    # Initialize on Nov 21
    init_time = datetime(2025, 11, 21, 23, 45, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    handler.update_check_time(init_time)

    # Timer #1 checks at exactly 00:00:00
    midnight_00 = datetime(2025, 11, 22, 0, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    assert handler.is_turnover_needed(midnight_00) is True
    handler.mark_turnover_done(midnight_00)

    # Timer #2 checks 1 second later
    midnight_01 = datetime(2025, 11, 22, 0, 0, 1, tzinfo=ZoneInfo("Europe/Oslo"))
    assert handler.is_turnover_needed(midnight_01) is False

    # Both timestamps point to same day - no duplicate
    assert handler.last_turnover_time.date() == midnight_01.date()  # type: ignore[union-attr]


@pytest.mark.unit
def test_rapid_consecutive_checks_same_second() -> None:
    """
    Test rapid consecutive checks within the same second at midnight.

    Simulates worst-case race condition where both timers fire within
    the same second (e.g., 00:00:00.123 and 00:00:00.456).

    Expected: First check triggers, all subsequent checks skip.
    """
    handler = TibberPricesMidnightHandler()

    # Initialize on Nov 21
    init_time = datetime(2025, 11, 21, 23, 59, 59, tzinfo=ZoneInfo("Europe/Oslo"))
    handler.update_check_time(init_time)

    # Simulate 3 checks at midnight within the same second
    midnight_check1 = datetime(2025, 11, 22, 0, 0, 0, 123000, tzinfo=ZoneInfo("Europe/Oslo"))
    midnight_check2 = datetime(2025, 11, 22, 0, 0, 0, 456000, tzinfo=ZoneInfo("Europe/Oslo"))
    midnight_check3 = datetime(2025, 11, 22, 0, 0, 0, 789000, tzinfo=ZoneInfo("Europe/Oslo"))

    # First check: turnover needed
    assert handler.is_turnover_needed(midnight_check1) is True
    handler.mark_turnover_done(midnight_check1)

    # Second and third checks: already done
    assert handler.is_turnover_needed(midnight_check2) is False
    assert handler.is_turnover_needed(midnight_check3) is False

    # Verify: turnover happened exactly once
    assert handler.last_turnover_time == midnight_check1
