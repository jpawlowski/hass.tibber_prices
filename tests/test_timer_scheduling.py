"""
Test timer scheduling for entity updates at correct intervals.

This tests the three-timer architecture:
- Timer #1: API polling (15 min, random offset) - tested in test_next_api_poll.py
- Timer #2: Quarter-hour entity refresh (:00, :15, :30, :45)
- Timer #3: Timing sensors refresh (:00, :30 every minute)

See docs/development/timer-architecture.md for architecture overview.
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from custom_components.tibber_prices.coordinator.constants import (
    QUARTER_HOUR_BOUNDARIES,
)
from custom_components.tibber_prices.coordinator.listeners import (
    TibberPricesListenerManager,
)
from homeassistant.core import HomeAssistant


@pytest.fixture
def hass_mock() -> HomeAssistant:
    """Create a mock HomeAssistant instance."""
    return MagicMock(spec=HomeAssistant)


@pytest.fixture
def listener_manager(hass_mock: HomeAssistant) -> TibberPricesListenerManager:
    """Create a ListenerManager instance for testing."""
    return TibberPricesListenerManager(hass_mock, log_prefix="test_home")


def test_schedule_quarter_hour_refresh_registers_timer(
    listener_manager: TibberPricesListenerManager,
) -> None:
    """
    Test that quarter-hour refresh registers timer with correct boundaries.

    Timer #2 should trigger at :00, :15, :30, :45 exactly.
    """
    handler = MagicMock()

    with patch("custom_components.tibber_prices.coordinator.listeners.async_track_utc_time_change") as mock_track:
        mock_track.return_value = MagicMock()  # Simulated cancel callback

        listener_manager.schedule_quarter_hour_refresh(handler)

        # Verify async_track_utc_time_change was called with correct parameters
        mock_track.assert_called_once()
        args, kwargs = mock_track.call_args

        # Check positional arguments
        assert args[0] == listener_manager.hass  # hass instance
        assert args[1] == handler  # callback function

        # Check keyword arguments
        assert "minute" in kwargs
        assert "second" in kwargs
        assert kwargs["minute"] == (0, 15, 30, 45)  # QUARTER_HOUR_BOUNDARIES
        assert kwargs["second"] == 0  # Exact boundary


def test_schedule_quarter_hour_refresh_cancels_existing_timer(
    listener_manager: TibberPricesListenerManager,
) -> None:
    """Test that scheduling quarter-hour refresh cancels any existing timer."""
    handler = MagicMock()
    cancel_mock = MagicMock()

    with patch("custom_components.tibber_prices.coordinator.listeners.async_track_utc_time_change") as mock_track:
        mock_track.return_value = cancel_mock

        # Schedule first timer
        listener_manager.schedule_quarter_hour_refresh(handler)
        first_cancel = listener_manager._quarter_hour_timer_cancel  # noqa: SLF001  # type: ignore[attr-defined]
        assert first_cancel is not None

        # Schedule second timer (should cancel first)
        listener_manager.schedule_quarter_hour_refresh(handler)

        # Verify cancel was called
        cancel_mock.assert_called_once()


def test_schedule_minute_refresh_registers_timer(
    listener_manager: TibberPricesListenerManager,
) -> None:
    """
    Test that minute refresh registers timer with correct 30-second boundaries.

    Timer #3 should trigger at :XX:00 and :XX:30 every minute.
    """
    handler = MagicMock()

    with patch("custom_components.tibber_prices.coordinator.listeners.async_track_utc_time_change") as mock_track:
        mock_track.return_value = MagicMock()  # Simulated cancel callback

        listener_manager.schedule_minute_refresh(handler)

        # Verify async_track_utc_time_change was called with correct parameters
        mock_track.assert_called_once()
        args, kwargs = mock_track.call_args

        # Check positional arguments
        assert args[0] == listener_manager.hass  # hass instance
        assert args[1] == handler  # callback function

        # Check keyword arguments
        assert "second" in kwargs
        assert kwargs["second"] == [0, 30]  # Every 30 seconds


def test_schedule_minute_refresh_cancels_existing_timer(
    listener_manager: TibberPricesListenerManager,
) -> None:
    """Test that scheduling minute refresh cancels any existing timer."""
    handler = MagicMock()
    cancel_mock = MagicMock()

    with patch("custom_components.tibber_prices.coordinator.listeners.async_track_utc_time_change") as mock_track:
        mock_track.return_value = cancel_mock

        # Schedule first timer
        listener_manager.schedule_minute_refresh(handler)
        first_cancel = listener_manager._minute_timer_cancel  # noqa: SLF001  # type: ignore[attr-defined]
        assert first_cancel is not None

        # Schedule second timer (should cancel first)
        listener_manager.schedule_minute_refresh(handler)

        # Verify cancel was called
        cancel_mock.assert_called_once()


def test_quarter_hour_timer_boundaries_match_constants(
    listener_manager: TibberPricesListenerManager,
) -> None:
    """
    Test that timer boundaries match QUARTER_HOUR_BOUNDARIES constant.

    This ensures Timer #2 triggers match the expected quarter-hour marks.
    """
    handler = MagicMock()

    with patch("custom_components.tibber_prices.coordinator.listeners.async_track_utc_time_change") as mock_track:
        mock_track.return_value = MagicMock()

        listener_manager.schedule_quarter_hour_refresh(handler)

        _, kwargs = mock_track.call_args
        assert kwargs["minute"] == QUARTER_HOUR_BOUNDARIES


@pytest.mark.asyncio
async def test_quarter_hour_callback_execution(
    listener_manager: TibberPricesListenerManager,
) -> None:
    """
    Test that quarter-hour timer callback is executed when scheduled time arrives.

    This simulates Home Assistant triggering the callback at quarter-hour boundary.
    """
    callback_executed = False
    callback_time = None

    def test_callback(now: datetime) -> None:
        nonlocal callback_executed, callback_time
        callback_executed = True
        callback_time = now

    # We need to actually trigger the callback to test execution
    with patch("custom_components.tibber_prices.coordinator.listeners.async_track_utc_time_change") as mock_track:
        # Capture the callback that would be registered
        registered_callback = None

        def capture_callback(_hass: Any, callback: Any, **_kwargs: Any) -> Any:
            nonlocal registered_callback
            registered_callback = callback
            return MagicMock()  # Cancel function

        mock_track.side_effect = capture_callback

        listener_manager.schedule_quarter_hour_refresh(test_callback)

        # Simulate Home Assistant triggering the callback
        assert registered_callback is not None
        test_time = datetime(2025, 11, 22, 14, 15, 0, tzinfo=UTC)
        registered_callback(test_time)

        # Verify callback was executed
        assert callback_executed
        assert callback_time == test_time


@pytest.mark.asyncio
async def test_minute_callback_execution(
    listener_manager: TibberPricesListenerManager,
) -> None:
    """
    Test that minute timer callback is executed when scheduled time arrives.

    This simulates Home Assistant triggering the callback at 30-second boundary.
    """
    callback_executed = False
    callback_time = None

    def test_callback(now: datetime) -> None:
        nonlocal callback_executed, callback_time
        callback_executed = True
        callback_time = now

    with patch("custom_components.tibber_prices.coordinator.listeners.async_track_utc_time_change") as mock_track:
        # Capture the callback that would be registered
        registered_callback = None

        def capture_callback(_hass: Any, callback: Any, **_kwargs: Any) -> Any:
            nonlocal registered_callback
            registered_callback = callback
            return MagicMock()  # Cancel function

        mock_track.side_effect = capture_callback

        listener_manager.schedule_minute_refresh(test_callback)

        # Simulate Home Assistant triggering the callback at :30 seconds
        assert registered_callback is not None
        test_time = datetime(2025, 11, 22, 14, 23, 30, tzinfo=UTC)
        registered_callback(test_time)

        # Verify callback was executed
        assert callback_executed
        assert callback_time == test_time


def test_multiple_timer_independence(
    listener_manager: TibberPricesListenerManager,
) -> None:
    """
    Test that quarter-hour and minute timers operate independently.

    Both timers should be able to coexist without interfering.
    """
    quarter_handler = MagicMock()
    minute_handler = MagicMock()

    with patch("custom_components.tibber_prices.coordinator.listeners.async_track_utc_time_change") as mock_track:
        mock_track.return_value = MagicMock()

        # Schedule both timers
        listener_manager.schedule_quarter_hour_refresh(quarter_handler)
        listener_manager.schedule_minute_refresh(minute_handler)

        # Verify both were registered (implementation detail check)
        assert hasattr(listener_manager, "_quarter_hour_timer_cancel")
        assert hasattr(listener_manager, "_minute_timer_cancel")
        assert listener_manager._quarter_hour_timer_cancel is not None  # noqa: SLF001  # type: ignore[attr-defined]
        assert listener_manager._minute_timer_cancel is not None  # noqa: SLF001  # type: ignore[attr-defined]

        # Verify async_track_utc_time_change was called twice
        assert mock_track.call_count == 2
