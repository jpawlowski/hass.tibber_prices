"""
Test chart_data_export sensor receives push updates from lifecycle changes.

This test verifies that when new price data arrives from the API (lifecycle
state changes to "fresh"), the chart_data_export sensor is immediately refreshed
via push update, not waiting for the next coordinator polling cycle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest

from custom_components.tibber_prices.sensor.core import TibberPricesSensor

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.mark.unit
def test_chart_data_export_registers_lifecycle_callback() -> None:
    """
    Test that chart_data_export sensor registers for lifecycle push updates.

    When chart_data_export sensor is created, it should register a callback
    with the coordinator to receive immediate notifications when lifecycle
    state changes (e.g., new API data arrives).
    """
    # Create mock coordinator with register_lifecycle_callback method
    mock_coordinator = Mock()
    mock_coordinator.register_lifecycle_callback = Mock(return_value=Mock())  # Returns unregister callable
    mock_coordinator.data = {"priceInfo": {}}
    mock_coordinator.config_entry = Mock()
    mock_coordinator.config_entry.entry_id = "test_entry"

    # Create mock entity description for chart_data_export
    mock_entity_description = Mock()
    mock_entity_description.key = "chart_data_export"
    mock_entity_description.translation_key = "chart_data_export"

    # Create sensor instance
    sensor = TibberPricesSensor(
        coordinator=mock_coordinator,
        entity_description=mock_entity_description,
    )

    # Verify lifecycle callback was registered
    mock_coordinator.register_lifecycle_callback.assert_called_once()

    # Verify the callback is stored for cleanup
    assert sensor._lifecycle_remove_listener is not None  # noqa: SLF001 - Test accesses internal state


@pytest.mark.unit
def test_data_lifecycle_status_registers_lifecycle_callback() -> None:
    """
    Test that data_lifecycle_status sensor also registers for lifecycle push updates.

    This is the original behavior - lifecycle sensor should still register.
    """
    # Create mock coordinator
    mock_coordinator = Mock()
    mock_coordinator.register_lifecycle_callback = Mock(return_value=Mock())
    mock_coordinator.data = {"priceInfo": {}}
    mock_coordinator.config_entry = Mock()
    mock_coordinator.config_entry.entry_id = "test_entry"

    # Create mock entity description for data_lifecycle_status
    mock_entity_description = Mock()
    mock_entity_description.key = "data_lifecycle_status"
    mock_entity_description.translation_key = "data_lifecycle_status"

    # Create sensor instance
    sensor = TibberPricesSensor(
        coordinator=mock_coordinator,
        entity_description=mock_entity_description,
    )

    # Verify lifecycle callback was registered
    mock_coordinator.register_lifecycle_callback.assert_called_once()

    # Verify the callback is stored for cleanup
    assert sensor._lifecycle_remove_listener is not None  # noqa: SLF001 - Test accesses internal state


@pytest.mark.unit
def test_other_sensors_do_not_register_lifecycle_callback() -> None:
    """
    Test that other sensors (not lifecycle or chart_data_export) don't register lifecycle callbacks.

    Only data_lifecycle_status and chart_data_export should register for push updates.
    """
    # Create mock coordinator
    mock_coordinator = Mock()
    mock_coordinator.register_lifecycle_callback = Mock(return_value=Mock())
    mock_coordinator.data = {"priceInfo": {}}
    mock_coordinator.config_entry = Mock()
    mock_coordinator.config_entry.entry_id = "test_entry"

    # Create mock entity description for a regular sensor
    mock_entity_description = Mock()
    mock_entity_description.key = "current_interval_price"
    mock_entity_description.translation_key = "current_interval_price"

    # Create sensor instance
    sensor = TibberPricesSensor(
        coordinator=mock_coordinator,
        entity_description=mock_entity_description,
    )

    # Verify lifecycle callback was NOT registered
    mock_coordinator.register_lifecycle_callback.assert_not_called()

    # Verify no lifecycle listener is stored
    assert sensor._lifecycle_remove_listener is None  # noqa: SLF001 - Test accesses internal state


@pytest.mark.unit
@pytest.mark.asyncio
async def test_chart_data_lifecycle_callback_refreshes_data() -> None:
    """
    Test that lifecycle callback for chart_data_export triggers data refresh.

    When coordinator notifies lifecycle change (e.g., new API data arrives),
    the chart_data_export sensor should immediately refresh its data by calling
    the chart data service.
    """
    # Create mock hass
    mock_hass = Mock()
    mock_hass.async_create_task = Mock()

    # Create mock coordinator
    mock_coordinator = Mock()
    mock_coordinator.data = {"priceInfo": {}}
    mock_coordinator.hass = mock_hass
    mock_coordinator.config_entry = Mock()
    mock_coordinator.config_entry.entry_id = "test_entry"

    # Track registered callbacks
    registered_callbacks: list[Callable] = []

    def mock_register_callback(callback: Callable) -> Callable:
        """Mock register that stores the callback."""
        registered_callbacks.append(callback)
        return Mock()  # Return unregister callable

    mock_coordinator.register_lifecycle_callback = mock_register_callback

    # Create mock entity description for chart_data_export
    mock_entity_description = Mock()
    mock_entity_description.key = "chart_data_export"
    mock_entity_description.translation_key = "chart_data_export"

    # Create sensor instance
    sensor = TibberPricesSensor(
        coordinator=mock_coordinator,
        entity_description=mock_entity_description,
    )

    # Assign hass to sensor (normally done by HA)
    sensor.hass = mock_hass

    # Verify callback was registered
    assert len(registered_callbacks) == 1
    lifecycle_callback = registered_callbacks[0]

    # Mock _refresh_chart_data to avoid actual service call
    sensor._refresh_chart_data = AsyncMock()  # noqa: SLF001 - Test accesses internal method

    # Trigger lifecycle callback (simulating coordinator notification)
    lifecycle_callback()

    # Verify hass.async_create_task was called (callback schedules async refresh)
    mock_hass.async_create_task.assert_called_once()

    # Get the task that was scheduled
    scheduled_task = mock_hass.async_create_task.call_args[0][0]

    # Execute the scheduled task
    await scheduled_task

    # Verify _refresh_chart_data was called
    sensor._refresh_chart_data.assert_called_once()  # noqa: SLF001 - Test accesses internal method


@pytest.mark.unit
@pytest.mark.asyncio
async def test_lifecycle_callback_cleanup_on_remove() -> None:
    """
    Test that lifecycle callback is properly unregistered when sensor is removed.

    When chart_data_export sensor is removed from HA, the lifecycle callback
    should be unregistered to prevent memory leaks.
    """
    # Create mock hass
    mock_hass = Mock()

    # Create mock coordinator
    mock_coordinator = Mock()
    mock_coordinator.data = {"priceInfo": {}}
    mock_coordinator.hass = mock_hass
    mock_coordinator.config_entry = Mock()
    mock_coordinator.config_entry.entry_id = "test_entry"

    # Track unregister callable
    unregister_mock = Mock()
    mock_coordinator.register_lifecycle_callback = Mock(return_value=unregister_mock)

    # Create mock entity description for chart_data_export
    mock_entity_description = Mock()
    mock_entity_description.key = "chart_data_export"
    mock_entity_description.translation_key = "chart_data_export"

    # Create sensor instance
    sensor = TibberPricesSensor(
        coordinator=mock_coordinator,
        entity_description=mock_entity_description,
    )

    # Assign hass to sensor
    sensor.hass = mock_hass

    # Verify callback was registered
    assert sensor._lifecycle_remove_listener is not None  # noqa: SLF001 - Test accesses internal state

    # Remove sensor from hass (trigger cleanup)
    await sensor.async_will_remove_from_hass()

    # Verify unregister callable was called
    unregister_mock.assert_called_once()

    # Verify lifecycle listener is cleared
    assert sensor._lifecycle_remove_listener is None  # noqa: SLF001 - Test accesses internal state
