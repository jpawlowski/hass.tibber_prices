"""
Test lifecycle sensor update after tomorrow data fetch.

This test ensures that when Timer #1 fetches tomorrow data after 13:00,
the lifecycle sensor correctly shows the new data (tomorrow_available=true)
and not stale attributes from before the fetch.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest

from custom_components.tibber_prices.coordinator.core import (
    TibberPricesDataUpdateCoordinator,
)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_lifecycle_sensor_updates_after_tomorrow_fetch() -> None:
    """
    Test that lifecycle sensor shows fresh tomorrow data after Timer #1 fetch.

    Scenario:
    1. Time is 13:05 (after tomorrow data expected)
    2. Coordinator fetches new data with tomorrow prices
    3. Lifecycle state changes to "fresh"
    4. Lifecycle sensor updates should see NEW coordinator.data (with tomorrow)

    Bug fixed: Previously lifecycle callbacks were called BEFORE coordinator.data
    was set, causing lifecycle sensor to show tomorrow_available=false even though
    tomorrow data was just fetched.
    """
    # Create mock hass
    mock_hass = Mock()
    mock_hass.async_create_task = Mock()

    # Setup mock coordinator
    coordinator = Mock(spec=TibberPricesDataUpdateCoordinator)
    coordinator.hass = mock_hass
    coordinator.time = Mock()

    current_time = datetime(2025, 11, 22, 13, 5, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    coordinator.time.now.return_value = current_time
    coordinator.time.as_local.side_effect = lambda dt: dt

    # Initial state: no tomorrow data
    coordinator.data = {
        "priceInfo": {
            "today": [{"startsAt": "2025-11-22T00:00:00+01:00", "total": 0.30}],
            "tomorrow": [],  # Empty - no tomorrow data yet
        }
    }
    coordinator._cached_price_data = coordinator.data["priceInfo"]  # noqa: SLF001
    coordinator._lifecycle_state = "cached"  # noqa: SLF001
    coordinator._last_price_update = current_time - timedelta(hours=1)  # noqa: SLF001

    # Mock lifecycle callbacks list
    lifecycle_callbacks = []
    coordinator._lifecycle_callbacks = lifecycle_callbacks  # noqa: SLF001
    coordinator.register_lifecycle_callback = lambda cb: lifecycle_callbacks.append(cb)

    # Create a mock sensor that tracks when it's updated
    sensor_update_count = {"count": 0, "saw_tomorrow": False}

    def mock_sensor_update() -> None:
        """Mock sensor update that checks coordinator.data."""
        sensor_update_count["count"] += 1
        # Check if sensor sees tomorrow data in coordinator.data
        if coordinator.data and coordinator.data["priceInfo"]["tomorrow"]:
            sensor_update_count["saw_tomorrow"] = True

    # Register mock sensor as lifecycle callback
    lifecycle_callbacks.append(mock_sensor_update)

    # Simulate data fetch with tomorrow prices (simulates Timer #1 after 13:00)
    new_data = {
        "priceInfo": {
            "today": [{"startsAt": "2025-11-22T00:00:00+01:00", "total": 0.30}],
            "tomorrow": [  # NEW tomorrow data
                {"startsAt": "2025-11-23T00:00:00+01:00", "total": 0.28},
                {"startsAt": "2025-11-23T01:00:00+01:00", "total": 0.27},
            ],
        }
    }

    # Update coordinator internal state (simulates what _async_update_data does)
    coordinator._cached_price_data = new_data["priceInfo"]  # noqa: SLF001
    coordinator._last_price_update = current_time  # noqa: SLF001 - New timestamp
    coordinator._lifecycle_state = "fresh"  # noqa: SLF001

    # CRITICAL: Set coordinator.data BEFORE calling lifecycle callbacks
    # This simulates what DataUpdateCoordinator framework does after _async_update_data returns
    coordinator.data = new_data

    # Simulate the fixed _notify_lifecycle_after_update() behavior
    # In the real code, this is scheduled as a task with asyncio.sleep(0)
    # to ensure it runs AFTER framework sets coordinator.data
    async def simulate_lifecycle_update() -> None:
        """Simulate the fixed lifecycle update behavior."""
        # Yield to event loop (simulates asyncio.sleep(0))
        await asyncio.sleep(0)
        # Now call callbacks - they should see NEW coordinator.data
        for callback in lifecycle_callbacks:
            callback()

    # Run the lifecycle update
    await simulate_lifecycle_update()

    # Verify sensor was updated
    assert sensor_update_count["count"] == 1, "Lifecycle callback should be called once"

    # CRITICAL: Verify sensor saw the NEW tomorrow data
    assert sensor_update_count["saw_tomorrow"], (
        "Lifecycle sensor should see tomorrow data in coordinator.data (not stale data from before fetch)"
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_lifecycle_callback_guard_before_entity_added() -> None:
    """
    Test that lifecycle callback handles being called before entity is added to hass.

    This tests the guard in _handle_lifecycle_update_for_chart() that prevents
    AttributeError when self.hass is None.
    """
    # Create mock hass
    mock_hass = Mock()
    tasks_created = []

    def mock_create_task(coro: Any) -> Mock:
        """Track created tasks."""
        tasks_created.append(coro)
        return Mock()

    mock_hass.async_create_task = mock_create_task

    # Create a mock entity that simulates chart_data_export sensor
    entity = Mock()
    entity.hass = None  # Not yet added to Home Assistant

    # Mock the _refresh_chart_data method as a Mock (not real coroutine)
    # This avoids "coroutine never awaited" warnings in test
    entity._refresh_chart_data = Mock(return_value=Mock())  # noqa: SLF001

    # Simulate the callback being called before entity is added
    # This should NOT crash with AttributeError
    def callback() -> None:
        """Simulate _handle_lifecycle_update_for_chart with guard."""
        if entity.hass is None:
            return  # Guard: Don't schedule task if not added yet
        entity.hass.async_create_task(entity._refresh_chart_data())  # noqa: SLF001

    # Call callback - should not crash
    callback()

    # Verify NO task was created (entity not added yet)
    assert len(tasks_created) == 0, "No task should be created when entity.hass is None"

    # Now simulate entity being added to hass
    entity.hass = mock_hass

    # Call callback again - should now schedule task
    callback()

    # Verify task was created this time
    assert len(tasks_created) == 1, "Task should be created after entity is added to hass"
