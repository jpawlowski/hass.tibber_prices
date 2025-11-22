"""
Unit tests for lifecycle state determination.

Tests the get_lifecycle_state() method which determines the current
data lifecycle state shown to users.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest

from custom_components.tibber_prices.sensor.calculators.lifecycle import (
    FRESH_DATA_THRESHOLD_MINUTES,
    TibberPricesLifecycleCalculator,
)


@pytest.mark.unit
def test_lifecycle_state_fresh() -> None:
    """
    Test lifecycle state is 'fresh' when data is recent.

    Scenario: Last API fetch was 3 minutes ago, before 13:00 (no tomorrow search)
    Expected: State is 'fresh' (< 5 minutes threshold)
    """
    coordinator = Mock()
    coordinator.time = Mock()

    current_time = datetime(2025, 11, 22, 10, 30, 0, tzinfo=ZoneInfo("Europe/Oslo"))  # 10:30 (before 13:00)
    last_update = current_time - timedelta(minutes=3)

    coordinator.time.now.return_value = current_time
    coordinator.time.as_local.side_effect = lambda dt: dt  # Need for midnight check
    coordinator._is_fetching = False  # noqa: SLF001
    coordinator.last_exception = None
    coordinator._last_price_update = last_update  # noqa: SLF001

    calculator = TibberPricesLifecycleCalculator(coordinator)
    state = calculator.get_lifecycle_state()

    assert state == "fresh"


@pytest.mark.unit
def test_lifecycle_state_cached() -> None:
    """
    Test lifecycle state is 'cached' during normal operation.

    Scenario: Last API fetch was 10 minutes ago, no special conditions
    Expected: State is 'cached' (normal operation)
    """
    coordinator = Mock()
    coordinator.time = Mock()

    current_time = datetime(2025, 11, 22, 14, 30, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    last_update = current_time - timedelta(minutes=10)

    coordinator.time.now.return_value = current_time
    coordinator.time.as_local.side_effect = lambda dt: dt
    coordinator._is_fetching = False  # noqa: SLF001
    coordinator.last_exception = None
    coordinator._last_price_update = last_update  # noqa: SLF001

    # Mock get_day_boundaries
    today_midnight = datetime(2025, 11, 22, 0, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    tomorrow_midnight = datetime(2025, 11, 23, 0, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    coordinator.time.get_day_boundaries.return_value = (today_midnight, tomorrow_midnight)

    # Not in tomorrow search mode (before 13:00)
    coordinator._needs_tomorrow_data.return_value = False  # noqa: SLF001

    calculator = TibberPricesLifecycleCalculator(coordinator)
    state = calculator.get_lifecycle_state()

    assert state == "cached"


@pytest.mark.unit
def test_lifecycle_state_refreshing() -> None:
    """
    Test lifecycle state is 'refreshing' during API call.

    Scenario: Coordinator is currently fetching data
    Expected: State is 'refreshing' (highest priority)
    """
    coordinator = Mock()
    coordinator.time = Mock()

    current_time = datetime(2025, 11, 22, 14, 30, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    coordinator.time.now.return_value = current_time
    coordinator._is_fetching = True  # noqa: SLF001 - Currently fetching!
    coordinator.last_exception = None

    calculator = TibberPricesLifecycleCalculator(coordinator)
    state = calculator.get_lifecycle_state()

    assert state == "refreshing"


@pytest.mark.unit
def test_lifecycle_state_error() -> None:
    """
    Test lifecycle state is 'error' after failed API call.

    Scenario: Last API call failed, exception is set
    Expected: State is 'error' (high priority)
    """
    coordinator = Mock()
    coordinator.time = Mock()

    current_time = datetime(2025, 11, 22, 14, 30, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    coordinator.time.now.return_value = current_time
    coordinator._is_fetching = False  # noqa: SLF001
    coordinator.last_exception = Exception("API Error")  # Last call failed!

    calculator = TibberPricesLifecycleCalculator(coordinator)
    state = calculator.get_lifecycle_state()

    assert state == "error"


@pytest.mark.unit
def test_lifecycle_state_searching_tomorrow() -> None:
    """
    Test lifecycle state is 'searching_tomorrow' after 13:00 without tomorrow data.

    Scenario: Current time is 15:00, tomorrow data is missing
    Expected: State is 'searching_tomorrow'
    """
    coordinator = Mock()
    coordinator.time = Mock()

    # 15:00 (after 13:00 tomorrow check hour)
    current_time = datetime(2025, 11, 22, 15, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    last_update = current_time - timedelta(minutes=10)

    coordinator.time.now.return_value = current_time
    coordinator.time.as_local.side_effect = lambda dt: dt
    coordinator._is_fetching = False  # noqa: SLF001
    coordinator.last_exception = None
    coordinator._last_price_update = last_update  # noqa: SLF001

    # Mock get_day_boundaries
    today_midnight = datetime(2025, 11, 22, 0, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    tomorrow_midnight = datetime(2025, 11, 23, 0, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    coordinator.time.get_day_boundaries.return_value = (today_midnight, tomorrow_midnight)

    # Tomorrow data is missing
    coordinator._needs_tomorrow_data.return_value = True  # noqa: SLF001

    calculator = TibberPricesLifecycleCalculator(coordinator)
    state = calculator.get_lifecycle_state()

    assert state == "searching_tomorrow"


@pytest.mark.unit
def test_lifecycle_state_turnover_pending() -> None:
    """
    Test lifecycle state is 'turnover_pending' shortly before midnight.

    Scenario: Current time is 23:57 (3 minutes before midnight)
    Expected: State is 'turnover_pending' (< 5 minutes threshold)
    """
    coordinator = Mock()
    coordinator.time = Mock()

    # 23:57 (3 minutes before midnight)
    current_time = datetime(2025, 11, 22, 23, 57, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    last_update = current_time - timedelta(minutes=10)

    coordinator.time.now.return_value = current_time
    coordinator.time.as_local.side_effect = lambda dt: dt
    coordinator._is_fetching = False  # noqa: SLF001
    coordinator.last_exception = None
    coordinator._last_price_update = last_update  # noqa: SLF001

    calculator = TibberPricesLifecycleCalculator(coordinator)
    state = calculator.get_lifecycle_state()

    assert state == "turnover_pending"


@pytest.mark.unit
def test_lifecycle_state_priority_error_over_turnover() -> None:
    """
    Test that 'error' state has higher priority than 'turnover_pending'.

    Scenario: Error occurred + approaching midnight
    Expected: State is 'error' (not turnover_pending)

    Priority: error (2) > turnover_pending (3)
    """
    coordinator = Mock()
    coordinator.time = Mock()

    # 23:58 (2 minutes before midnight) BUT error occurred
    current_time = datetime(2025, 11, 22, 23, 58, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    coordinator.time.now.return_value = current_time
    coordinator.time.as_local.side_effect = lambda dt: dt
    coordinator._is_fetching = False  # noqa: SLF001
    coordinator.last_exception = Exception("API Error")  # Error has priority!

    calculator = TibberPricesLifecycleCalculator(coordinator)
    state = calculator.get_lifecycle_state()

    assert state == "error"


@pytest.mark.unit
def test_lifecycle_state_priority_turnover_over_searching() -> None:
    """
    Test that 'turnover_pending' has higher priority than 'searching_tomorrow'.

    Scenario: 23:57 (approaching midnight) + after 13:00 + tomorrow missing
    Expected: State is 'turnover_pending' (not searching_tomorrow)

    Priority: turnover_pending (3) > searching_tomorrow (4)
    """
    coordinator = Mock()
    coordinator.time = Mock()

    # 23:57 (3 minutes before midnight) + tomorrow missing
    current_time = datetime(2025, 11, 22, 23, 57, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    coordinator.time.now.return_value = current_time
    coordinator.time.as_local.side_effect = lambda dt: dt
    coordinator._is_fetching = False  # noqa: SLF001
    coordinator.last_exception = None

    # Mock get_day_boundaries
    today_midnight = datetime(2025, 11, 22, 0, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    tomorrow_midnight = datetime(2025, 11, 23, 0, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    coordinator.time.get_day_boundaries.return_value = (today_midnight, tomorrow_midnight)

    # Tomorrow data is missing
    coordinator._needs_tomorrow_data.return_value = True  # noqa: SLF001

    calculator = TibberPricesLifecycleCalculator(coordinator)
    state = calculator.get_lifecycle_state()

    assert state == "turnover_pending"


@pytest.mark.unit
def test_lifecycle_state_priority_searching_over_fresh() -> None:
    """
    Test that 'searching_tomorrow' has higher priority than 'fresh'.

    Scenario: 15:00 (after 13:00) + tomorrow missing + data just fetched (2 min ago)
    Expected: State is 'searching_tomorrow' (not fresh)

    Priority: searching_tomorrow (4) > fresh (5)

    This prevents state flickering during search phase:
    - Without priority: searching_tomorrow → fresh (5min) → searching_tomorrow → fresh (5min)...
    - With priority: searching_tomorrow (stable until tomorrow data arrives)
    """
    coordinator = Mock()
    coordinator.time = Mock()

    # 15:00 (after 13:00 tomorrow check hour)
    current_time = datetime(2025, 11, 22, 15, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    last_update = current_time - timedelta(minutes=2)  # Fresh data (< 5 min)

    coordinator.time.now.return_value = current_time
    coordinator.time.as_local.side_effect = lambda dt: dt
    coordinator._is_fetching = False  # noqa: SLF001
    coordinator.last_exception = None
    coordinator._last_price_update = last_update  # noqa: SLF001 - Data is fresh!

    # Mock get_day_boundaries
    today_midnight = datetime(2025, 11, 22, 0, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    tomorrow_midnight = datetime(2025, 11, 23, 0, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    coordinator.time.get_day_boundaries.return_value = (today_midnight, tomorrow_midnight)

    # Tomorrow data is missing
    coordinator._needs_tomorrow_data.return_value = True  # noqa: SLF001

    calculator = TibberPricesLifecycleCalculator(coordinator)
    state = calculator.get_lifecycle_state()

    # Should be searching_tomorrow (not fresh) to avoid flickering
    assert state == "searching_tomorrow"


@pytest.mark.unit
def test_lifecycle_state_priority_turnover_over_fresh() -> None:
    """
    Test that 'turnover_pending' has higher priority than 'fresh'.

    Scenario: 23:57 (approaching midnight) + data just fetched (2 min ago)
    Expected: State is 'turnover_pending' (not fresh)

    Priority: turnover_pending (3) > fresh (5)
    """
    coordinator = Mock()
    coordinator.time = Mock()

    # 23:57 (3 minutes before midnight)
    current_time = datetime(2025, 11, 22, 23, 57, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    last_update = current_time - timedelta(minutes=2)  # Fresh data (< 5 min)

    coordinator.time.now.return_value = current_time
    coordinator.time.as_local.side_effect = lambda dt: dt
    coordinator._is_fetching = False  # noqa: SLF001
    coordinator.last_exception = None
    coordinator._last_price_update = last_update  # noqa: SLF001 - Data is fresh!

    calculator = TibberPricesLifecycleCalculator(coordinator)
    state = calculator.get_lifecycle_state()

    assert state == "turnover_pending"


@pytest.mark.unit
def test_lifecycle_state_priority_refreshing_over_all() -> None:
    """
    Test that 'refreshing' state has highest priority.

    Scenario: Currently fetching + error + approaching midnight
    Expected: State is 'refreshing' (checked first)
    """
    coordinator = Mock()
    coordinator.time = Mock()

    # 23:58 (approaching midnight) + error + refreshing
    current_time = datetime(2025, 11, 22, 23, 58, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    coordinator.time.now.return_value = current_time
    coordinator.time.as_local.side_effect = lambda dt: dt
    coordinator._is_fetching = True  # noqa: SLF001 - Currently fetching!
    coordinator.last_exception = Exception("Previous error")

    calculator = TibberPricesLifecycleCalculator(coordinator)
    state = calculator.get_lifecycle_state()

    assert state == "refreshing"


@pytest.mark.unit
def test_lifecycle_state_exact_threshold_boundaries() -> None:
    """
    Test lifecycle state exactly at threshold boundaries.

    Scenario 1: Exactly 5 minutes old → should be 'cached' (not fresh)
    Scenario 2: Exactly 300 seconds to midnight → should be 'turnover_pending'
    """
    coordinator = Mock()
    coordinator.time = Mock()

    # Test 1: Exactly 5 minutes old (boundary case)
    current_time = datetime(2025, 11, 22, 14, 30, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    last_update = current_time - timedelta(minutes=FRESH_DATA_THRESHOLD_MINUTES)

    coordinator.time.now.return_value = current_time
    coordinator.time.as_local.side_effect = lambda dt: dt
    coordinator._is_fetching = False  # noqa: SLF001
    coordinator.last_exception = None
    coordinator._last_price_update = last_update  # noqa: SLF001

    today_midnight = datetime(2025, 11, 22, 0, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    tomorrow_midnight = datetime(2025, 11, 23, 0, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    coordinator.time.get_day_boundaries.return_value = (today_midnight, tomorrow_midnight)
    coordinator._needs_tomorrow_data.return_value = False  # noqa: SLF001

    calculator = TibberPricesLifecycleCalculator(coordinator)
    state = calculator.get_lifecycle_state()

    # At exactly 5 minutes, threshold is <= 5 min, so should still be fresh
    assert state == "fresh"

    # Test 2: Exactly at turnover threshold (5 minutes before midnight)
    current_time_turnover = datetime(2025, 11, 22, 23, 55, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    coordinator.time.now.return_value = current_time_turnover
    last_update_turnover = current_time_turnover - timedelta(minutes=10)
    coordinator._last_price_update = last_update_turnover  # noqa: SLF001

    calculator2 = TibberPricesLifecycleCalculator(coordinator)
    state2 = calculator2.get_lifecycle_state()

    # Exactly 5 minutes (300 seconds) to midnight → should be turnover_pending
    assert state2 == "turnover_pending"
