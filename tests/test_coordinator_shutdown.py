"""Test coordinator shutdown and cache persistence."""

from unittest.mock import AsyncMock, MagicMock

import pytest

# Import at module level to avoid PLC0415
from custom_components.tibber_prices.coordinator.core import (
    TibberPricesDataUpdateCoordinator,
)


@pytest.mark.asyncio
async def test_coordinator_shutdown_saves_cache() -> None:
    """
    Test that coordinator saves cache during shutdown.

    This ensures no data is lost when Home Assistant shuts down.
    """
    # Create mock coordinator bypassing __init__
    coordinator = object.__new__(TibberPricesDataUpdateCoordinator)

    # Mock the _store_cache method, listener manager, and repair manager
    coordinator._store_cache = AsyncMock()  # noqa: SLF001
    mock_listener_manager = MagicMock()
    mock_listener_manager.cancel_timers = MagicMock()
    coordinator._listener_manager = mock_listener_manager  # noqa: SLF001
    mock_repair_manager = MagicMock()
    mock_repair_manager.clear_all_repairs = AsyncMock()
    coordinator._repair_manager = mock_repair_manager  # noqa: SLF001
    coordinator._log = lambda *_a, **_kw: None  # noqa: SLF001

    # Call shutdown
    await coordinator.async_shutdown()

    # Verify cache was saved
    coordinator._store_cache.assert_called_once()  # noqa: SLF001
    # Verify repairs were cleared
    mock_repair_manager.clear_all_repairs.assert_called_once()
    # Verify timers were cancelled
    mock_listener_manager.cancel_timers.assert_called_once()


@pytest.mark.asyncio
async def test_coordinator_shutdown_handles_cache_error() -> None:
    """
    Test that shutdown completes even if cache save fails.

    Shutdown should be resilient and not raise exceptions.
    """
    # Create mock coordinator bypassing __init__
    coordinator = object.__new__(TibberPricesDataUpdateCoordinator)

    # Mock _store_cache to raise an exception
    coordinator._store_cache = AsyncMock(side_effect=OSError("Disk full"))  # noqa: SLF001
    mock_listener_manager = MagicMock()
    mock_listener_manager.cancel_timers = MagicMock()
    coordinator._listener_manager = mock_listener_manager  # noqa: SLF001
    mock_repair_manager = MagicMock()
    mock_repair_manager.clear_all_repairs = AsyncMock()
    coordinator._repair_manager = mock_repair_manager  # noqa: SLF001
    coordinator._log = lambda *_a, **_kw: None  # noqa: SLF001

    # Shutdown should complete without raising
    await coordinator.async_shutdown()

    # Verify _store_cache was called (even though it raised)
    coordinator._store_cache.assert_called_once()  # noqa: SLF001
    # Verify timers were still cancelled despite error
    mock_listener_manager.cancel_timers.assert_called_once()
