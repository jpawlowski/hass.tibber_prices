"""
Unit tests for next_api_poll_time calculation logic.

Tests the precise minute/second offset calculation for Timer #1 scheduling,
ensuring accurate prediction of when the next API poll will occur.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest

from custom_components.tibber_prices.coordinator.constants import UPDATE_INTERVAL
from custom_components.tibber_prices.sensor.calculators.lifecycle import (
    TibberPricesLifecycleCalculator,
)


@pytest.mark.unit
def test_next_api_poll_before_13_with_timer_offset() -> None:
    """
    Test next_api_poll before 13:00 with known timer offset.

    Scenario: Timer runs at X:04:37 (4 minutes 37 seconds past quarter-hour)
    Current time: 10:19:37 (before 13:00)
    Expected: Next poll at 13:04:37 (first timer execution at or after 13:00)
    """
    # Mock coordinator with timer history
    coordinator = Mock()
    coordinator.time = Mock()

    # Current time: 10:19:37 (Timer just ran)
    current_time = datetime(2025, 11, 22, 10, 19, 37, tzinfo=ZoneInfo("Europe/Oslo"))
    coordinator.time.now.return_value = current_time
    coordinator.time.as_local.side_effect = lambda dt: dt

    # Mock get_day_boundaries (needed to determine if tomorrow data is missing)
    today_midnight = datetime(2025, 11, 22, 0, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    tomorrow_midnight = datetime(2025, 11, 23, 0, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    coordinator.time.get_day_boundaries.return_value = (today_midnight, tomorrow_midnight)

    # Timer last ran at 10:19:37 (offset: 4 min 37 sec past quarter)
    coordinator._last_coordinator_update = current_time  # noqa: SLF001

    # Mock coordinator.data (no tomorrow data yet)
    coordinator.data = {"priceInfo": {"today": [1, 2, 3], "tomorrow": []}}

    # Mock _needs_tomorrow_data (not relevant for this case)
    coordinator._needs_tomorrow_data.return_value = False  # noqa: SLF001

    # Create calculator
    calculator = TibberPricesLifecycleCalculator(coordinator)

    # Calculate next poll
    next_poll = calculator.get_next_api_poll_time()

    # Should be 13:04:37 (first timer at or after 13:00 with same offset)
    assert next_poll is not None
    assert next_poll.hour == 13
    assert next_poll.minute == 4
    assert next_poll.second == 37


@pytest.mark.unit
def test_next_api_poll_before_13_different_offset() -> None:
    """
    Test next_api_poll with different timer offset.

    Scenario: Timer runs at X:11:22 (11 minutes 22 seconds past quarter-hour)
    Current time: 09:26:22
    Expected: Next poll at 13:11:22
    """
    coordinator = Mock()
    coordinator.time = Mock()

    current_time = datetime(2025, 11, 22, 9, 26, 22, tzinfo=ZoneInfo("Europe/Oslo"))
    coordinator.time.now.return_value = current_time
    coordinator.time.as_local.side_effect = lambda dt: dt

    # Mock get_day_boundaries
    today_midnight = datetime(2025, 11, 22, 0, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    tomorrow_midnight = datetime(2025, 11, 23, 0, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    coordinator.time.get_day_boundaries.return_value = (today_midnight, tomorrow_midnight)

    coordinator._last_coordinator_update = current_time  # noqa: SLF001
    coordinator.data = {"priceInfo": {"today": [1, 2, 3], "tomorrow": []}}
    coordinator._needs_tomorrow_data.return_value = False  # noqa: SLF001

    calculator = TibberPricesLifecycleCalculator(coordinator)
    next_poll = calculator.get_next_api_poll_time()

    assert next_poll is not None
    assert next_poll.hour == 13
    assert next_poll.minute == 11
    assert next_poll.second == 22


@pytest.mark.unit
def test_next_api_poll_before_13_offset_requires_14xx() -> None:
    """
    Test next_api_poll when timer offset doesn't fit in 13:xx hour.

    Scenario: Timer runs at X:58:15 (58 minutes past hour, 13 min past 45-min mark)
    Current time: 11:58:15
    Expected: Next poll at 13:13:15 (13:00+13min, 13:15+13min, 13:30+13min, 13:45+13min)
    Note: Even extreme offsets fit in 13:xx hour, 14:xx overflow is theoretical edge case
    """
    coordinator = Mock()
    coordinator.time = Mock()

    current_time = datetime(2025, 11, 22, 11, 58, 15, tzinfo=ZoneInfo("Europe/Oslo"))
    coordinator.time.now.return_value = current_time
    coordinator.time.as_local.side_effect = lambda dt: dt

    # Mock get_day_boundaries
    today_midnight = datetime(2025, 11, 22, 0, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    tomorrow_midnight = datetime(2025, 11, 23, 0, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    coordinator.time.get_day_boundaries.return_value = (today_midnight, tomorrow_midnight)

    # Timer offset: 58 % 15 = 13 minutes past quarter-hour
    coordinator._last_coordinator_update = current_time  # noqa: SLF001
    coordinator.data = {"priceInfo": {"today": [1, 2, 3], "tomorrow": []}}
    coordinator._needs_tomorrow_data.return_value = False  # noqa: SLF001

    calculator = TibberPricesLifecycleCalculator(coordinator)
    next_poll = calculator.get_next_api_poll_time()

    # Even with 13-minute offset, first valid is 13:13:15
    assert next_poll is not None
    assert next_poll.hour == 13
    assert next_poll.minute == 13
    assert next_poll.second == 15


@pytest.mark.unit
def test_next_api_poll_before_13_no_timer_history() -> None:
    """
    Test next_api_poll fallback when no timer history exists.

    Scenario: Integration just started, no _last_coordinator_update yet
    Current time: 10:30:00
    Expected: Fallback to 13:00:00
    """
    coordinator = Mock()
    coordinator.time = Mock()

    current_time = datetime(2025, 11, 22, 10, 30, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    coordinator.time.now.return_value = current_time
    coordinator.time.as_local.side_effect = lambda dt: dt

    # Mock get_day_boundaries
    today_midnight = datetime(2025, 11, 22, 0, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    tomorrow_midnight = datetime(2025, 11, 23, 0, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    coordinator.time.get_day_boundaries.return_value = (today_midnight, tomorrow_midnight)

    # No timer history
    coordinator._last_coordinator_update = None  # noqa: SLF001
    coordinator.data = {"priceInfo": {"today": [1, 2, 3], "tomorrow": []}}
    coordinator._needs_tomorrow_data.return_value = False  # noqa: SLF001

    calculator = TibberPricesLifecycleCalculator(coordinator)
    next_poll = calculator.get_next_api_poll_time()

    # Should fallback to 13:00:00
    assert next_poll is not None
    assert next_poll.hour == 13
    assert next_poll.minute == 0
    assert next_poll.second == 0


@pytest.mark.unit
def test_next_api_poll_after_13_tomorrow_missing() -> None:
    """
    Test next_api_poll after 13:00 when tomorrow data is missing.

    Scenario: After 13:00, actively polling for tomorrow data
    Current time: 14:30:00
    Last update: 14:15:45
    Expected: Last update + UPDATE_INTERVAL (15 minutes) = 14:30:45
    """
    coordinator = Mock()
    coordinator.time = Mock()

    current_time = datetime(2025, 11, 22, 14, 30, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    last_update = datetime(2025, 11, 22, 14, 15, 45, tzinfo=ZoneInfo("Europe/Oslo"))

    coordinator.time.now.return_value = current_time
    coordinator.time.as_local.side_effect = lambda dt: dt

    # Mock get_day_boundaries
    today_midnight = datetime(2025, 11, 22, 0, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    tomorrow_midnight = datetime(2025, 11, 23, 0, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    coordinator.time.get_day_boundaries.return_value = (today_midnight, tomorrow_midnight)

    coordinator._last_coordinator_update = last_update  # noqa: SLF001
    coordinator.data = {"priceInfo": {"today": [1, 2, 3], "tomorrow": []}}  # Tomorrow missing!
    coordinator._needs_tomorrow_data.return_value = True  # noqa: SLF001 - Tomorrow missing!

    calculator = TibberPricesLifecycleCalculator(coordinator)
    next_poll = calculator.get_next_api_poll_time()

    # Should be last_update + 15 minutes
    expected = last_update + UPDATE_INTERVAL
    assert next_poll is not None
    assert next_poll == expected
    assert next_poll.minute == 30
    assert next_poll.second == 45


@pytest.mark.unit
def test_next_api_poll_after_13_tomorrow_present() -> None:
    """
    Test next_api_poll after 13:00 when tomorrow data is present.

    Scenario: After 13:00, tomorrow data fetched, predicting tomorrow's first poll
    Current time: 15:34:12
    Timer offset: 4 minutes 12 seconds past quarter (from 15:34:12)
    Expected: Tomorrow at 13:04:12
    """
    coordinator = Mock()
    coordinator.time = Mock()

    current_time = datetime(2025, 11, 22, 15, 34, 12, tzinfo=ZoneInfo("Europe/Oslo"))
    coordinator.time.now.return_value = current_time
    coordinator.time.as_local.side_effect = lambda dt: dt

    # Mock get_day_boundaries
    today_midnight = datetime(2025, 11, 22, 0, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    tomorrow_midnight = datetime(2025, 11, 23, 0, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    coordinator.time.get_day_boundaries.return_value = (today_midnight, tomorrow_midnight)

    # Timer offset: 34 % 15 = 4 minutes past quarter-hour
    coordinator._last_coordinator_update = current_time  # noqa: SLF001
    coordinator.data = {"priceInfo": {"today": [1, 2, 3], "tomorrow": [4, 5, 6]}}  # Tomorrow present!
    coordinator._needs_tomorrow_data.return_value = False  # noqa: SLF001 - Tomorrow present!

    calculator = TibberPricesLifecycleCalculator(coordinator)
    next_poll = calculator.get_next_api_poll_time()

    # Should be tomorrow at 13:04:12
    assert next_poll is not None
    assert next_poll.day == 23  # Tomorrow
    assert next_poll.hour == 13
    assert next_poll.minute == 4
    assert next_poll.second == 12


@pytest.mark.unit
def test_next_api_poll_exact_13_00_boundary() -> None:
    """
    Test next_api_poll exactly at 13:00:00 boundary.

    Scenario: Timer runs exactly at 13:00:00 (offset: 0 min 0 sec)
    Current time: 13:00:00
    Expected: 13:00:00 (current time matches first valid slot)
    """
    coordinator = Mock()
    coordinator.time = Mock()

    current_time = datetime(2025, 11, 22, 13, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    coordinator.time.now.return_value = current_time
    coordinator.time.as_local.side_effect = lambda dt: dt

    # Mock get_day_boundaries
    today_midnight = datetime(2025, 11, 22, 0, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    tomorrow_midnight = datetime(2025, 11, 23, 0, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    coordinator.time.get_day_boundaries.return_value = (today_midnight, tomorrow_midnight)

    # Timer runs at exact quarter-hour boundaries
    coordinator._last_coordinator_update = current_time  # noqa: SLF001
    coordinator.data = {"priceInfo": {"today": [1, 2, 3], "tomorrow": []}}
    coordinator._needs_tomorrow_data.return_value = False  # noqa: SLF001

    calculator = TibberPricesLifecycleCalculator(coordinator)
    next_poll = calculator.get_next_api_poll_time()

    # Should be 13:00:00 (first valid slot)
    assert next_poll is not None
    assert next_poll.hour == 13
    assert next_poll.minute == 0
    assert next_poll.second == 0


@pytest.mark.unit
def test_next_api_poll_offset_spans_multiple_quarters() -> None:
    """
    Test timer offset calculation across different quarter-hour marks.

    Scenario: Timer at 12:47:33 (offset: 2 min 33 sec past 45-min mark)
    Expected: 13:02:33, 13:17:33, 13:32:33, or 13:47:33 depending on >= 13:00
    Result: First valid is 13:02:33
    """
    coordinator = Mock()
    coordinator.time = Mock()

    current_time = datetime(2025, 11, 22, 12, 47, 33, tzinfo=ZoneInfo("Europe/Oslo"))
    coordinator.time.now.return_value = current_time
    coordinator.time.as_local.side_effect = lambda dt: dt

    # Mock get_day_boundaries
    today_midnight = datetime(2025, 11, 22, 0, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    tomorrow_midnight = datetime(2025, 11, 23, 0, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    coordinator.time.get_day_boundaries.return_value = (today_midnight, tomorrow_midnight)

    # Timer offset: 47 % 15 = 2 minutes past quarter
    coordinator._last_coordinator_update = current_time  # noqa: SLF001
    coordinator.data = {"priceInfo": {"today": [1, 2, 3], "tomorrow": []}}
    coordinator._needs_tomorrow_data.return_value = False  # noqa: SLF001

    calculator = TibberPricesLifecycleCalculator(coordinator)
    next_poll = calculator.get_next_api_poll_time()

    # Should be 13:02:33 (first quarter-hour slot >= 13:00 with offset 2:33)
    assert next_poll is not None
    assert next_poll.hour == 13
    assert next_poll.minute == 2
    assert next_poll.second == 33
