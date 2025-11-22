"""
Test cache validity status after midnight turnover.

This test verifies that cache_validity correctly reports "valid" after midnight
turnover, even when _last_price_update is 5+ hours old (set to 00:00 during turnover).
The data is still valid because it was rotated (tomorrow→today), not stale.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import Mock

import pytest

from custom_components.tibber_prices.coordinator.time_service import (
    TibberPricesTimeService,
)
from custom_components.tibber_prices.sensor.calculators.lifecycle import (
    TibberPricesLifecycleCalculator,
)


@pytest.mark.unit
def test_cache_validity_after_midnight_no_api_calls_within_2h() -> None:
    """
    Test cache validity after midnight turnover - within 2 hour window.

    Scenario:
    - Midnight turnover happened at 00:00 (set _last_price_update to 00:00)
    - Current time: 01:30 (1.5 hours after turnover)
    - Coordinator last ran at 01:15 (15 minutes ago)
    - Cache age: 1.5 hours < 2 hours → Should be "valid"

    Expected: "valid" (not "stale")
    Rationale: Data was rotated at midnight and is less than 2 hours old.
    """
    # Create mock coordinator with midnight turnover state
    mock_coordinator = Mock(spec=["data", "_last_price_update", "_last_coordinator_update", "time"])

    # Midnight turnover happened at 00:00
    midnight = datetime(2025, 11, 22, 0, 0, 0)  # noqa: DTZ001 - Test uses naive datetime for simplicity

    # Current time: 01:30 (1.5 hours after turnover)
    current_time = datetime(2025, 11, 22, 1, 30, 0)  # noqa: DTZ001 - Test uses naive datetime

    # Coordinator last checked at 01:15
    coordinator_check_time = datetime(2025, 11, 22, 1, 15, 0)  # noqa: DTZ001 - Test uses naive datetime

    # Mock TimeService
    mock_time_service = Mock(spec=TibberPricesTimeService)
    mock_time_service.now.return_value = current_time
    mock_time_service.as_local.side_effect = lambda dt: dt  # Assume UTC = local for simplicity

    # Configure coordinator state
    mock_coordinator.data = {"priceInfo": {}}  # Has data
    mock_coordinator._last_price_update = midnight  # noqa: SLF001 - Test accesses internal state
    mock_coordinator._last_coordinator_update = coordinator_check_time  # noqa: SLF001 - Test accesses internal state
    mock_coordinator.time = mock_time_service

    # Create calculator
    calculator = TibberPricesLifecycleCalculator(mock_coordinator)

    # Get cache validity status
    status = calculator.get_cache_validity_status()

    # Should be "valid" - within 2-hour grace period after midnight
    assert status == "valid"


@pytest.mark.unit
def test_cache_validity_after_midnight_no_api_calls_beyond_2h_coordinator_recent() -> None:
    """
    Test cache validity after midnight turnover - beyond 2 hour window BUT coordinator ran recently.

    Scenario:
    - Midnight turnover happened at 00:00 (set _last_price_update to 00:00)
    - Current time: 05:57 (5 hours 57 minutes after turnover)
    - Coordinator last ran at 05:45 (12 minutes ago)
    - Cache age: ~6 hours > 2 hours, BUT coordinator checked recently → Should be "valid"

    Expected: "valid" (NOT "stale")
    Rationale: Even though _last_price_update is old, coordinator validated cache recently.
    """
    # Create mock coordinator with midnight turnover state
    mock_coordinator = Mock(spec=["data", "_last_price_update", "_last_coordinator_update", "time"])

    # Midnight turnover happened at 00:00
    midnight = datetime(2025, 11, 22, 0, 0, 0)  # noqa: DTZ001 - Test uses naive datetime

    # Current time: 05:57 (almost 6 hours after turnover)
    current_time = datetime(2025, 11, 22, 5, 57, 0)  # noqa: DTZ001 - Test uses naive datetime

    # Coordinator last checked at 05:45 (12 minutes ago)
    coordinator_check_time = datetime(2025, 11, 22, 5, 45, 0)  # noqa: DTZ001 - Test uses naive datetime

    # Mock TimeService
    mock_time_service = Mock(spec=TibberPricesTimeService)
    mock_time_service.now.return_value = current_time
    mock_time_service.as_local.side_effect = lambda dt: dt  # Assume UTC = local

    # Configure coordinator state
    mock_coordinator.data = {"priceInfo": {}}  # Has data
    mock_coordinator._last_price_update = midnight  # noqa: SLF001 - Test accesses internal state
    mock_coordinator._last_coordinator_update = coordinator_check_time  # noqa: SLF001 - Test accesses internal state
    mock_coordinator.time = mock_time_service

    # Create calculator
    calculator = TibberPricesLifecycleCalculator(mock_coordinator)

    # Get cache validity status
    status = calculator.get_cache_validity_status()

    # Should be "valid" - coordinator validated cache recently
    assert status == "valid"


@pytest.mark.unit
def test_cache_validity_after_midnight_beyond_2h_coordinator_old() -> None:
    """
    Test cache validity when cache is old AND coordinator hasn't run recently.

    Scenario:
    - Midnight turnover happened at 00:00
    - Current time: 05:57
    - Coordinator last ran at 05:00 (57 minutes ago > 30 min threshold)
    - Cache age: ~6 hours > 2 hours AND coordinator check old → Should be "stale"

    Expected: "stale"
    Rationale: Cache is old and coordinator hasn't validated it recently.
    """
    # Create mock coordinator
    mock_coordinator = Mock(spec=["data", "_last_price_update", "_last_coordinator_update", "time"])

    # Midnight turnover happened at 00:00
    midnight = datetime(2025, 11, 22, 0, 0, 0)  # noqa: DTZ001 - Test uses naive datetime

    # Current time: 05:57
    current_time = datetime(2025, 11, 22, 5, 57, 0)  # noqa: DTZ001 - Test uses naive datetime

    # Coordinator last checked at 05:00 (57 minutes ago - beyond 30 min threshold)
    coordinator_check_time = datetime(2025, 11, 22, 5, 0, 0)  # noqa: DTZ001 - Test uses naive datetime

    # Mock TimeService
    mock_time_service = Mock(spec=TibberPricesTimeService)
    mock_time_service.now.return_value = current_time
    mock_time_service.as_local.side_effect = lambda dt: dt

    # Configure coordinator state
    mock_coordinator.data = {"priceInfo": {}}  # Has data
    mock_coordinator._last_price_update = midnight  # noqa: SLF001 - Test accesses internal state
    mock_coordinator._last_coordinator_update = coordinator_check_time  # noqa: SLF001 - Test accesses internal state
    mock_coordinator.time = mock_time_service

    # Create calculator
    calculator = TibberPricesLifecycleCalculator(mock_coordinator)

    # Get cache validity status
    status = calculator.get_cache_validity_status()

    # Should be "stale" - cache old and coordinator check also old
    assert status == "stale"


@pytest.mark.unit
def test_cache_validity_after_midnight_with_api_call() -> None:
    """
    Test cache validity after midnight with API call made.

    Scenario:
    - API call made at 00:15 (updated _last_price_update to 00:15)
    - Current time: 05:57 (5h 42m after last API call)
    - Age: ~5h 42m > 2 hours, BUT coordinator ran at 05:45 → Should be "valid"

    Expected: "valid" (NOT "stale")
    Rationale: Coordinator validated cache recently (within 30 min).
    """
    # Create mock coordinator
    mock_coordinator = Mock(spec=["data", "_last_price_update", "_last_coordinator_update", "time"])

    # API call happened at 00:15 (15 minutes after midnight)
    last_api_call = datetime(2025, 11, 22, 0, 15, 0)  # noqa: DTZ001 - Test uses naive datetime

    # Current time: 05:57
    current_time = datetime(2025, 11, 22, 5, 57, 0)  # noqa: DTZ001 - Test uses naive datetime

    # Coordinator last checked at 05:45
    coordinator_check_time = datetime(2025, 11, 22, 5, 45, 0)  # noqa: DTZ001 - Test uses naive datetime

    # Mock TimeService
    mock_time_service = Mock(spec=TibberPricesTimeService)
    mock_time_service.now.return_value = current_time
    mock_time_service.as_local.side_effect = lambda dt: dt

    # Configure coordinator state
    mock_coordinator.data = {"priceInfo": {}}  # Has data
    mock_coordinator._last_price_update = last_api_call  # noqa: SLF001 - Test accesses internal state
    mock_coordinator._last_coordinator_update = coordinator_check_time  # noqa: SLF001 - Test accesses internal state
    mock_coordinator.time = mock_time_service

    # Create calculator
    calculator = TibberPricesLifecycleCalculator(mock_coordinator)

    # Get cache validity status
    status = calculator.get_cache_validity_status()

    # Should be "valid" - coordinator validated recently
    assert status == "valid"


@pytest.mark.unit
def test_cache_validity_date_mismatch() -> None:
    """
    Test cache validity when cache is from yesterday.

    Scenario:
    - Cache is from Nov 21 (yesterday)
    - Current time: Nov 22, 05:57 (today)
    - Should report "date_mismatch"

    Expected: "date_mismatch"
    Rationale: Cache is from a different day, turnover didn't happen yet.
    """
    # Create mock coordinator
    mock_coordinator = Mock(spec=["data", "_last_price_update", "_last_coordinator_update", "time"])

    # Cache from yesterday
    yesterday = datetime(2025, 11, 21, 22, 0, 0)  # noqa: DTZ001 - Test uses naive datetime

    # Current time: today 05:57
    current_time = datetime(2025, 11, 22, 5, 57, 0)  # noqa: DTZ001 - Test uses naive datetime

    # Mock TimeService
    mock_time_service = Mock(spec=TibberPricesTimeService)
    mock_time_service.now.return_value = current_time
    mock_time_service.as_local.side_effect = lambda dt: dt

    # Configure coordinator state
    mock_coordinator.data = {"priceInfo": {}}  # Has data
    mock_coordinator._last_price_update = yesterday  # noqa: SLF001 - Test accesses internal state
    mock_coordinator._last_coordinator_update = None  # noqa: SLF001 - Test accesses internal state
    mock_coordinator.time = mock_time_service

    # Create calculator
    calculator = TibberPricesLifecycleCalculator(mock_coordinator)

    # Get cache validity status
    status = calculator.get_cache_validity_status()

    # Should be "date_mismatch" - cache is from different day
    assert status == "date_mismatch"


@pytest.mark.unit
def test_cache_validity_empty_no_data() -> None:
    """
    Test cache validity when no data exists.

    Expected: "empty"
    """
    mock_coordinator = Mock(spec=["data", "_last_price_update", "_api_calls_today", "time"])
    mock_coordinator.data = None  # No data

    calculator = TibberPricesLifecycleCalculator(mock_coordinator)
    status = calculator.get_cache_validity_status()

    assert status == "empty"


@pytest.mark.unit
def test_cache_validity_empty_no_timestamp() -> None:
    """
    Test cache validity when data exists but no timestamp.

    Expected: "empty"
    """
    mock_coordinator = Mock(spec=["data", "_last_price_update", "_api_calls_today", "time"])
    mock_coordinator.data = {"priceInfo": {}}  # Has data
    mock_coordinator._last_price_update = None  # noqa: SLF001 - Test accesses internal state

    calculator = TibberPricesLifecycleCalculator(mock_coordinator)
    status = calculator.get_cache_validity_status()

    assert status == "empty"
