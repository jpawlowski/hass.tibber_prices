"""Tests for sensor state consistency between connection, tomorrow_data_available, and lifecycle_status."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from custom_components.tibber_prices.binary_sensor.core import (
    TibberPricesBinarySensor,
)
from custom_components.tibber_prices.coordinator.core import (
    TibberPricesDataUpdateCoordinator,
    get_connection_state,
)
from custom_components.tibber_prices.sensor.calculators.lifecycle import (
    TibberPricesLifecycleCalculator,
)
from homeassistant.components.binary_sensor import BinarySensorEntityDescription
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from unittest.mock import Mock as MockType


def create_mock_coordinator() -> Mock:
    """
    Create a properly mocked coordinator for entity initialization.

    Includes all attributes required by TibberPricesEntity.__init__:
    - hass.config.language (for translations)
    - config_entry.data, .unique_id, .entry_id (for device info)
    - get_user_profile() (for home information)
    """
    coordinator = Mock(spec=TibberPricesDataUpdateCoordinator)
    coordinator.data = None
    coordinator.last_exception = None
    coordinator._is_fetching = False  # noqa: SLF001

    # Mock hass for language configuration
    coordinator.hass = Mock()
    coordinator.hass.config.language = "en"

    # Mock config_entry for entity initialization
    coordinator.config_entry = Mock()
    coordinator.config_entry.data = {}
    coordinator.config_entry.entry_id = "test_entry_id"
    coordinator.config_entry.unique_id = "test_home_id"

    # Mock user profile method
    coordinator.get_user_profile.return_value = {
        "home": {
            "appNickname": "Test Home",
            "type": "APARTMENT",
        }
    }

    return coordinator


def create_price_intervals(day_offset: int = 0) -> list[dict]:
    """Create 96 mock price intervals (quarter-hourly for one day)."""
    # Use CURRENT date so tests work regardless of when they run
    now_local = dt_util.now()
    base_date = now_local.replace(hour=0, minute=0, second=0, microsecond=0)

    intervals = []
    for i in range(96):
        interval_time = base_date.replace(day=base_date.day + day_offset, hour=i // 4, minute=(i % 4) * 15)
        intervals.append(
            {
                "startsAt": interval_time.isoformat(),
                "total": 20.0 + (i % 10),
                "energy": 18.0 + (i % 10),
                "tax": 2.0,
                "level": "NORMAL",
            }
        )
    return intervals


def create_coordinator_data(*, today: bool = True, tomorrow: bool = False) -> dict:
    """
    Create coordinator data in the new flat-list format.

    Args:
        today: Include today's 96 intervals
        tomorrow: Include tomorrow's 96 intervals

    Returns:
        Dict with flat priceInfo list: {"priceInfo": [...]}

    """
    all_intervals = []
    if today:
        all_intervals.extend(create_price_intervals(0))  # Today (offset 0)
    if tomorrow:
        all_intervals.extend(create_price_intervals(1))  # Tomorrow (offset 1)

    return {"priceInfo": all_intervals}


@pytest.fixture
def mock_coordinator() -> MockType:
    """Fixture providing a properly mocked coordinator."""
    return create_mock_coordinator()


# =============================================================================
# Connection State Tests (get_connection_state helper)
# =============================================================================


def test_connection_state_auth_failed(mock_coordinator: MockType) -> None:
    """Test connection state when auth fails - should be False (disconnected)."""
    mock_coordinator.data = create_coordinator_data(today=True, tomorrow=False)
    mock_coordinator.last_exception = ConfigEntryAuthFailed("Invalid token")

    # Auth failure = definitively disconnected, even with cached data
    assert get_connection_state(mock_coordinator) is False


def test_connection_state_api_error_with_cache(mock_coordinator: MockType) -> None:
    """Test connection state when API errors but cache available - should be True (using cache)."""
    mock_coordinator.data = create_coordinator_data(today=True, tomorrow=False)
    mock_coordinator.last_exception = UpdateFailed("API timeout")

    # Other errors with cache = considered connected (degraded operation)
    assert get_connection_state(mock_coordinator) is True


def test_connection_state_api_error_no_cache(mock_coordinator: MockType) -> None:
    """Test connection state when API errors and no cache - should be None (unknown)."""
    mock_coordinator.data = None  # No data
    mock_coordinator.last_exception = UpdateFailed("API timeout")

    # No data and error = unknown state
    assert get_connection_state(mock_coordinator) is None


def test_connection_state_normal_operation(mock_coordinator: MockType) -> None:
    """Test connection state during normal operation - should be True (connected)."""
    mock_coordinator.data = create_coordinator_data(today=True, tomorrow=False)
    mock_coordinator.last_exception = None

    # Normal operation with data = connected
    assert get_connection_state(mock_coordinator) is True


def test_connection_state_initializing(mock_coordinator: MockType) -> None:
    """Test connection state when initializing - should be None (unknown)."""
    mock_coordinator.data = None
    mock_coordinator.last_exception = None

    # No data, no error = initializing (unknown)
    assert get_connection_state(mock_coordinator) is None


# =============================================================================
# Sensor Consistency Tests - Auth Error Scenario
# =============================================================================


def test_sensor_consistency_auth_error() -> None:
    """Test all 3 sensors are consistent when auth fails."""
    coordinator = Mock(spec=TibberPricesDataUpdateCoordinator)
    coordinator.data = create_coordinator_data(today=True, tomorrow=False)
    coordinator.last_exception = ConfigEntryAuthFailed("Invalid token")
    coordinator.time = Mock()
    coordinator._is_fetching = False  # noqa: SLF001

    # Connection: Should be False (disconnected)
    connection_state = get_connection_state(coordinator)
    assert connection_state is False, "Connection should be off when auth fails"

    # Lifecycle: Should be "error"
    lifecycle_calc = TibberPricesLifecycleCalculator(coordinator)
    lifecycle_state = lifecycle_calc.get_lifecycle_state()
    assert lifecycle_state == "error", "Lifecycle should be 'error' when auth fails"


def test_sensor_consistency_api_error_with_cache() -> None:
    """Test all 3 sensors are consistent when API errors but cache available."""
    coordinator = Mock(spec=TibberPricesDataUpdateCoordinator)
    coordinator.data = create_coordinator_data(today=True, tomorrow=True)
    coordinator.last_exception = UpdateFailed("API timeout")
    coordinator.time = Mock()
    coordinator._is_fetching = False  # noqa: SLF001
    coordinator._last_price_update = datetime(2025, 11, 22, 10, 0, 0, tzinfo=UTC)  # noqa: SLF001

    # Connection: Should be True (using cache)
    connection_state = get_connection_state(coordinator)
    assert connection_state is True, "Connection should be on when using cache"

    # Lifecycle: Should be "error" (last fetch failed)
    lifecycle_calc = TibberPricesLifecycleCalculator(coordinator)
    lifecycle_state = lifecycle_calc.get_lifecycle_state()
    assert lifecycle_state == "error", "Lifecycle should be 'error' when last fetch failed"


def test_sensor_consistency_normal_operation() -> None:
    """Test all 3 sensors are consistent during normal operation."""
    coordinator = Mock(spec=TibberPricesDataUpdateCoordinator)
    coordinator.data = create_coordinator_data(today=True, tomorrow=False)
    coordinator.last_exception = None
    coordinator.time = Mock()
    coordinator._is_fetching = False  # noqa: SLF001
    coordinator._last_price_update = datetime(2025, 11, 22, 10, 0, 0, tzinfo=UTC)  # noqa: SLF001

    # Mock time methods for lifecycle calculator
    now = datetime(2025, 11, 22, 10, 15, 0, tzinfo=UTC)
    coordinator.time.now.return_value = now
    coordinator.time.as_local.return_value = now

    # Connection: Should be True
    connection_state = get_connection_state(coordinator)
    assert connection_state is True, "Connection should be on during normal operation"

    # Lifecycle: Should be "cached" (not within 5min of fetch)
    lifecycle_calc = TibberPricesLifecycleCalculator(coordinator)
    lifecycle_state = lifecycle_calc.get_lifecycle_state()
    assert lifecycle_state == "cached", "Lifecycle should be 'cached' during normal operation"


def test_sensor_consistency_refreshing() -> None:
    """Test all 3 sensors are consistent when actively fetching."""
    coordinator = Mock(spec=TibberPricesDataUpdateCoordinator)
    coordinator.data = create_coordinator_data(today=True, tomorrow=False)
    coordinator.last_exception = None
    coordinator.time = Mock()
    coordinator._is_fetching = True  # noqa: SLF001 - Currently fetching
    coordinator._last_price_update = datetime(2025, 11, 22, 10, 0, 0, tzinfo=UTC)  # noqa: SLF001

    # Connection: Should be True (has data, no error)
    connection_state = get_connection_state(coordinator)
    assert connection_state is True, "Connection should be on when refreshing"

    # Lifecycle: Should be "refreshing"
    lifecycle_calc = TibberPricesLifecycleCalculator(coordinator)
    lifecycle_state = lifecycle_calc.get_lifecycle_state()
    assert lifecycle_state == "refreshing", "Lifecycle should be 'refreshing' when actively fetching"


# =============================================================================
# Tomorrow Data Available - Auth Error Handling
# =============================================================================


def test_tomorrow_data_available_auth_error_returns_none() -> None:
    """Test tomorrow_data_available returns None when auth fails (cannot check)."""
    coordinator = create_mock_coordinator()
    coordinator.data = create_coordinator_data(today=False, tomorrow=True)
    coordinator.last_exception = ConfigEntryAuthFailed("Invalid token")
    coordinator.time = Mock()

    description = BinarySensorEntityDescription(
        key="tomorrow_data_available",
        name="Tomorrow Data Available",
    )

    sensor = TibberPricesBinarySensor(coordinator, description)

    # Even with full tomorrow data, should return None when auth fails
    state = sensor._tomorrow_data_available_state()  # noqa: SLF001
    assert state is None, "Should return None (unknown) when auth fails, even with cached data"


def test_tomorrow_data_available_no_data_returns_none() -> None:
    """Test tomorrow_data_available returns None when no coordinator data."""
    coordinator = create_mock_coordinator()
    coordinator.data = None  # No data
    coordinator.last_exception = None
    coordinator.time = Mock()

    description = BinarySensorEntityDescription(
        key="tomorrow_data_available",
        name="Tomorrow Data Available",
    )

    sensor = TibberPricesBinarySensor(coordinator, description)

    state = sensor._tomorrow_data_available_state()  # noqa: SLF001
    assert state is None, "Should return None when no coordinator data"


def test_tomorrow_data_available_normal_operation_full_data() -> None:
    """Test tomorrow_data_available returns True when tomorrow data is complete."""
    coordinator = create_mock_coordinator()
    coordinator.data = create_coordinator_data(today=False, tomorrow=True)
    coordinator.last_exception = None

    # Mock time service for expected intervals calculation
    now_date = dt_util.now().date()
    time_service = Mock()
    time_service.get_local_date.return_value = now_date
    time_service.get_expected_intervals_for_day.return_value = 96  # Standard day
    coordinator.time = time_service

    description = BinarySensorEntityDescription(
        key="tomorrow_data_available",
        name="Tomorrow Data Available",
    )

    sensor = TibberPricesBinarySensor(coordinator, description)

    state = sensor._tomorrow_data_available_state()  # noqa: SLF001
    assert state is True, "Should return True when tomorrow data is complete"


def test_tomorrow_data_available_normal_operation_missing_data() -> None:
    """Test tomorrow_data_available returns False when tomorrow data is missing."""
    coordinator = create_mock_coordinator()
    coordinator.data = create_coordinator_data(today=True, tomorrow=False)  # No tomorrow data
    coordinator.last_exception = None

    time_service = Mock()
    time_service.get_local_date.return_value = datetime(2025, 11, 23, tzinfo=UTC).date()
    time_service.get_expected_intervals_for_day.return_value = 96
    coordinator.time = time_service

    description = BinarySensorEntityDescription(
        key="tomorrow_data_available",
        name="Tomorrow Data Available",
    )

    sensor = TibberPricesBinarySensor(coordinator, description)

    state = sensor._tomorrow_data_available_state()  # noqa: SLF001
    assert state is False, "Should return False when tomorrow data is missing"


# =============================================================================
# Integration Tests - Combined Sensor States
# =============================================================================


def test_combined_states_auth_error_scenario() -> None:
    """
    Integration test: Verify all 3 sensors show consistent states during auth error.

    Scenario: API returns 401 Unauthorized, cached data exists
    Expected:
    - connection: False (off)
    - tomorrow_data_available: None (unknown)
    - lifecycle_status: "error"
    """
    # Setup coordinator with auth error state
    coordinator = create_mock_coordinator()
    coordinator.data = create_coordinator_data(today=True, tomorrow=True)
    coordinator.last_exception = ConfigEntryAuthFailed("Invalid access token")
    coordinator._is_fetching = False  # noqa: SLF001

    time_service = Mock()
    time_service.get_local_date.return_value = datetime(2025, 11, 22, tzinfo=UTC).date()  # Today is 22nd
    time_service.get_expected_intervals_for_day.return_value = 96
    coordinator.time = time_service

    # Test 1: Connection state
    connection_state = get_connection_state(coordinator)
    assert connection_state is False, "Connection must be False on auth error"

    # Test 2: Tomorrow data available state
    tomorrow_desc = BinarySensorEntityDescription(
        key="tomorrow_data_available",
        name="Tomorrow Data Available",
    )
    tomorrow_sensor = TibberPricesBinarySensor(coordinator, tomorrow_desc)
    tomorrow_state = tomorrow_sensor._tomorrow_data_available_state()  # noqa: SLF001
    assert tomorrow_state is None, "Tomorrow data must be None (unknown) on auth error"

    # Test 3: Lifecycle state
    lifecycle_calc = TibberPricesLifecycleCalculator(coordinator)
    lifecycle_state = lifecycle_calc.get_lifecycle_state()
    assert lifecycle_state == "error", "Lifecycle must be 'error' on auth error"


def test_combined_states_api_error_with_cache_scenario() -> None:
    """
    Integration test: Verify all 3 sensors show consistent states during API error with cache.

    Scenario: API times out, but cached data available
    Expected:
    - connection: True (on - using cache)
    - tomorrow_data_available: True/False (checks cached data)
    - lifecycle_status: "error" (last fetch failed)
    """
    # Setup coordinator with API error but cache available
    coordinator = create_mock_coordinator()
    coordinator.data = create_coordinator_data(today=True, tomorrow=True)
    coordinator.last_exception = UpdateFailed("API timeout after 30s")
    coordinator._is_fetching = False  # noqa: SLF001
    coordinator._last_price_update = datetime(2025, 11, 22, 10, 0, 0, tzinfo=UTC)  # noqa: SLF001

    time_service = Mock()
    time_service.get_local_date.return_value = datetime(2025, 11, 22, tzinfo=UTC).date()  # Today is 22nd
    time_service.get_expected_intervals_for_day.return_value = 96
    coordinator.time = time_service

    # Test 1: Connection state
    connection_state = get_connection_state(coordinator)
    assert connection_state is True, "Connection must be True when using cache"

    # Test 2: Tomorrow data available state
    tomorrow_desc = BinarySensorEntityDescription(
        key="tomorrow_data_available",
        name="Tomorrow Data Available",
    )
    tomorrow_sensor = TibberPricesBinarySensor(coordinator, tomorrow_desc)
    tomorrow_state = tomorrow_sensor._tomorrow_data_available_state()  # noqa: SLF001
    assert tomorrow_state is True, "Tomorrow data should check cached data normally"

    # Test 3: Lifecycle state
    lifecycle_calc = TibberPricesLifecycleCalculator(coordinator)
    lifecycle_state = lifecycle_calc.get_lifecycle_state()
    assert lifecycle_state == "error", "Lifecycle must be 'error' when last fetch failed"


def test_combined_states_normal_operation_scenario() -> None:
    """
    Integration test: Verify all 3 sensors show consistent states during normal operation.

    Scenario: No errors, data available
    Expected:
    - connection: True (on)
    - tomorrow_data_available: True/False (checks data)
    - lifecycle_status: "cached" or "fresh"
    """
    # Setup coordinator in normal operation
    coordinator = create_mock_coordinator()
    coordinator.data = create_coordinator_data(today=True, tomorrow=True)
    coordinator.last_exception = None
    coordinator._is_fetching = False  # noqa: SLF001
    coordinator._last_price_update = datetime(2025, 11, 22, 10, 0, 0, tzinfo=UTC)  # noqa: SLF001 - 10 minutes ago

    # Mock time (10 minutes after last update = "cached" state)
    now = datetime(2025, 11, 22, 10, 10, 0, tzinfo=UTC)
    time_service = Mock()
    time_service.now.return_value = now
    time_service.as_local.return_value = now
    time_service.get_local_date.return_value = datetime(2025, 11, 22, tzinfo=UTC).date()  # Today is 22nd
    time_service.get_expected_intervals_for_day.return_value = 96
    coordinator.time = time_service

    # Test 1: Connection state
    connection_state = get_connection_state(coordinator)
    assert connection_state is True, "Connection must be True during normal operation"

    # Test 2: Tomorrow data available state
    tomorrow_desc = BinarySensorEntityDescription(
        key="tomorrow_data_available",
        name="Tomorrow Data Available",
    )
    tomorrow_sensor = TibberPricesBinarySensor(coordinator, tomorrow_desc)
    tomorrow_state = tomorrow_sensor._tomorrow_data_available_state()  # noqa: SLF001
    assert tomorrow_state is True, "Tomorrow data should be available"

    # Test 3: Lifecycle state
    lifecycle_calc = TibberPricesLifecycleCalculator(coordinator)
    lifecycle_state = lifecycle_calc.get_lifecycle_state()
    assert lifecycle_state == "cached", "Lifecycle should be 'cached' (>5min since fetch)"
