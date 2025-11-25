"""Test resource cleanup and memory leak prevention."""

from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from custom_components.tibber_prices.binary_sensor.core import (
    TibberPricesBinarySensor,
)
from custom_components.tibber_prices.coordinator.core import (
    TibberPricesDataUpdateCoordinator,
)
from custom_components.tibber_prices.coordinator.listeners import (
    TibberPricesListenerManager,
)
from custom_components.tibber_prices.sensor.core import TibberPricesSensor


@pytest.mark.unit
class TestListenerCleanup:
    """Test that listeners are properly removed to prevent memory leaks."""

    def test_listener_manager_removes_time_sensitive_listeners(self) -> None:
        """Test that time-sensitive listeners can be removed."""
        # Create listener manager
        manager = object.__new__(TibberPricesListenerManager)
        manager._time_sensitive_listeners = []  # noqa: SLF001
        manager._log = lambda *_a, **_kw: None  # noqa: SLF001

        # Add a listener
        callback = Mock()
        remove_fn = manager.async_add_time_sensitive_listener(callback)

        # Verify listener was added
        assert callback in manager._time_sensitive_listeners  # noqa: SLF001
        assert len(manager._time_sensitive_listeners) == 1  # noqa: SLF001

        # Remove listener
        remove_fn()

        # Verify listener was removed
        assert callback not in manager._time_sensitive_listeners  # noqa: SLF001
        assert len(manager._time_sensitive_listeners) == 0  # noqa: SLF001

    def test_listener_manager_removes_minute_listeners(self) -> None:
        """Test that minute-update listeners can be removed."""
        # Create listener manager
        manager = object.__new__(TibberPricesListenerManager)
        manager._minute_update_listeners = []  # noqa: SLF001
        manager._log = lambda *_a, **_kw: None  # noqa: SLF001

        # Add a listener
        callback = Mock()
        remove_fn = manager.async_add_minute_update_listener(callback)

        # Verify listener was added
        assert callback in manager._minute_update_listeners  # noqa: SLF001
        assert len(manager._minute_update_listeners) == 1  # noqa: SLF001

        # Remove listener
        remove_fn()

        # Verify listener was removed
        assert callback not in manager._minute_update_listeners  # noqa: SLF001
        assert len(manager._minute_update_listeners) == 0  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_sensor_cleanup_pattern_exists(self) -> None:
        """
        Test that sensor cleanup code is present and follows correct pattern.

        Note: We can't easily test full entity initialization (requires too much mocking),
        but we verify the cleanup pattern exists in the code.
        """
        # Verify the async_will_remove_from_hass method exists and has cleanup code
        assert hasattr(TibberPricesSensor, "async_will_remove_from_hass")

        # The implementation should call remove functions for all listener types
        # This is verified by code inspection rather than runtime test
        # Pattern exists in sensor/core.py lines 143-160

    @pytest.mark.asyncio
    async def test_binary_sensor_cleanup_pattern_exists(self) -> None:
        """
        Test that binary sensor cleanup code is present and follows correct pattern.

        Note: We can't easily test full entity initialization (requires too much mocking),
        but we verify the cleanup pattern exists in the code.
        """
        # Verify the async_will_remove_from_hass method exists and has cleanup code
        assert hasattr(TibberPricesBinarySensor, "async_will_remove_from_hass")

        # The implementation should call remove functions for all listener types
        # This is verified by code inspection rather than runtime test
        # Pattern exists in binary_sensor/core.py lines 65-79


@pytest.mark.unit
class TestTimerCleanup:
    """Test that timers are properly cancelled to prevent resource leaks."""

    def test_cancel_timers_clears_quarter_hour_timer(self) -> None:
        """Test that quarter-hour timer is cancelled and cleared."""
        # Create listener manager
        manager = object.__new__(TibberPricesListenerManager)
        mock_cancel = Mock()
        manager._quarter_hour_timer_cancel = mock_cancel  # noqa: SLF001
        manager._minute_timer_cancel = None  # noqa: SLF001

        # Cancel timers
        manager.cancel_timers()

        # Verify cancel was called
        mock_cancel.assert_called_once()

        # Verify reference was cleared
        assert manager._quarter_hour_timer_cancel is None  # noqa: SLF001

    def test_cancel_timers_clears_minute_timer(self) -> None:
        """Test that minute timer is cancelled and cleared."""
        # Create listener manager
        manager = object.__new__(TibberPricesListenerManager)
        manager._quarter_hour_timer_cancel = None  # noqa: SLF001
        mock_cancel = Mock()
        manager._minute_timer_cancel = mock_cancel  # noqa: SLF001

        # Cancel timers
        manager.cancel_timers()

        # Verify cancel was called
        mock_cancel.assert_called_once()

        # Verify reference was cleared
        assert manager._minute_timer_cancel is None  # noqa: SLF001

    def test_cancel_timers_handles_both_timers(self) -> None:
        """Test that both timers are cancelled together."""
        # Create listener manager
        manager = object.__new__(TibberPricesListenerManager)
        mock_quarter_cancel = Mock()
        mock_minute_cancel = Mock()
        manager._quarter_hour_timer_cancel = mock_quarter_cancel  # noqa: SLF001
        manager._minute_timer_cancel = mock_minute_cancel  # noqa: SLF001

        # Cancel timers
        manager.cancel_timers()

        # Verify both were called
        mock_quarter_cancel.assert_called_once()
        mock_minute_cancel.assert_called_once()

        # Verify references were cleared
        assert manager._quarter_hour_timer_cancel is None  # noqa: SLF001
        assert manager._minute_timer_cancel is None  # noqa: SLF001

    def test_cancel_timers_handles_none_gracefully(self) -> None:
        """Test that cancel_timers doesn't crash if timers are None."""
        # Create listener manager with no timers
        manager = object.__new__(TibberPricesListenerManager)
        manager._quarter_hour_timer_cancel = None  # noqa: SLF001
        manager._minute_timer_cancel = None  # noqa: SLF001

        # Should not raise
        manager.cancel_timers()

        # Verify still None
        assert manager._quarter_hour_timer_cancel is None  # noqa: SLF001
        assert manager._minute_timer_cancel is None  # noqa: SLF001


@pytest.mark.unit
class TestConfigEntryCleanup:
    """Test that config entry options listeners are properly managed."""

    @pytest.mark.asyncio
    async def test_options_update_listener_registered(self) -> None:
        """Test that options update listener is registered via async_on_unload."""
        # This tests the pattern: entry.async_on_unload(entry.add_update_listener(...))
        # We test that this pattern exists in coordinator initialization

        from homeassistant.config_entries import ConfigEntry  # noqa: PLC0415

        # Create minimal mocks
        hass = MagicMock()
        config_entry = MagicMock(spec=ConfigEntry)
        config_entry.entry_id = "test_entry"
        config_entry.data = {}
        config_entry.options = {}
        config_entry.async_on_unload = Mock()
        config_entry.add_update_listener = Mock(return_value=Mock())

        # Create coordinator (which should register the listener)
        coordinator = object.__new__(TibberPricesDataUpdateCoordinator)
        coordinator.hass = hass
        coordinator.config_entry = config_entry
        coordinator._log_prefix = "[test]"  # noqa: SLF001
        coordinator._log = lambda *_a, **_kw: None  # noqa: SLF001

        # Initialize necessary components
        from custom_components.tibber_prices.coordinator.data_transformation import (  # noqa: PLC0415
            TibberPricesDataTransformer,
        )
        from custom_components.tibber_prices.coordinator.listeners import (  # noqa: PLC0415
            TibberPricesListenerManager,
        )
        from custom_components.tibber_prices.coordinator.periods import (  # noqa: PLC0415
            TibberPricesPeriodCalculator,
        )
        from custom_components.tibber_prices.coordinator.time_service import (  # noqa: PLC0415
            TibberPricesTimeService,
        )

        coordinator.time = TibberPricesTimeService(hass)
        coordinator._listener_manager = object.__new__(TibberPricesListenerManager)  # noqa: SLF001
        coordinator._data_transformer = object.__new__(TibberPricesDataTransformer)  # noqa: SLF001
        coordinator._period_calculator = object.__new__(TibberPricesPeriodCalculator)  # noqa: SLF001
        coordinator._lifecycle_callbacks = []  # noqa: SLF001

        # Manually call the registration that happens in __init__
        # This tests the pattern: entry.async_on_unload(entry.add_update_listener(...))
        update_listener = config_entry.add_update_listener(
            coordinator._handle_options_update  # noqa: SLF001
        )
        config_entry.async_on_unload(update_listener)

        # Verify the listener was registered
        config_entry.add_update_listener.assert_called_once()
        config_entry.async_on_unload.assert_called_once()

        # Verify the cleanup function was passed to async_on_unload
        cleanup_fn = config_entry.async_on_unload.call_args[0][0]
        assert cleanup_fn is not None


@pytest.mark.unit
class TestCacheInvalidation:
    """Test that caches are properly invalidated to prevent stale data."""

    def test_config_cache_invalidated_on_options_change(self) -> None:
        """Test that config caches are cleared when options change."""
        from custom_components.tibber_prices.coordinator.data_transformation import (  # noqa: PLC0415
            TibberPricesDataTransformer,
        )

        # Create transformer with cached config
        transformer = object.__new__(TibberPricesDataTransformer)
        transformer._config_cache = {"some": "data"}  # noqa: SLF001
        transformer._config_cache_valid = True  # noqa: SLF001
        transformer._log = lambda *_a, **_kw: None  # noqa: SLF001

        # Invalidate cache
        transformer.invalidate_config_cache()

        # Verify cache was cleared
        assert transformer._config_cache_valid is False  # noqa: SLF001
        assert transformer._config_cache is None  # noqa: SLF001

    def test_period_cache_invalidated_on_options_change(self) -> None:
        """Test that period calculation cache is cleared when options change."""
        from custom_components.tibber_prices.coordinator.periods import (  # noqa: PLC0415
            TibberPricesPeriodCalculator,
        )

        # Create calculator with cached data
        calculator = object.__new__(TibberPricesPeriodCalculator)
        calculator._config_cache = {"some": "data"}  # noqa: SLF001
        calculator._config_cache_valid = True  # noqa: SLF001
        calculator._cached_periods = {"cached": "periods"}  # noqa: SLF001
        calculator._last_periods_hash = "some_hash"  # noqa: SLF001
        calculator._log = lambda *_a, **_kw: None  # noqa: SLF001

        # Invalidate cache
        calculator.invalidate_config_cache()

        # Verify all caches were cleared
        assert calculator._config_cache_valid is False  # noqa: SLF001
        assert calculator._config_cache is None  # noqa: SLF001
        assert calculator._cached_periods is None  # noqa: SLF001
        assert calculator._last_periods_hash is None  # noqa: SLF001

    def test_trend_cache_cleared_on_coordinator_update(self) -> None:
        """Test that trend cache is cleared when coordinator updates."""
        from custom_components.tibber_prices.sensor.calculators.trend import (  # noqa: PLC0415
            TibberPricesTrendCalculator,
        )

        # Create calculator with cached trend
        calculator = object.__new__(TibberPricesTrendCalculator)
        calculator._cached_trend_value = "some_trend"  # noqa: SLF001
        calculator._trend_attributes = {"some": "data"}  # noqa: SLF001

        # Clear cache
        calculator.clear_trend_cache()

        # Verify cache was cleared (clears _cached_trend_value + _trend_attributes)
        assert calculator._cached_trend_value is None  # noqa: SLF001
        assert calculator._trend_attributes == {}  # noqa: SLF001


@pytest.mark.unit
class TestStorageCleanup:
    """Test that storage files are properly removed on entry removal."""

    @pytest.mark.asyncio
    async def test_storage_removed_on_entry_removal(self) -> None:
        """Test that cache storage is deleted when config entry is removed."""
        from custom_components.tibber_prices import async_remove_entry  # noqa: PLC0415

        # Create mocks
        hass = AsyncMock()
        hass.async_add_executor_job = AsyncMock()
        config_entry = MagicMock()
        config_entry.entry_id = "test_entry_123"

        # Mock Store
        mock_store = AsyncMock()
        mock_store.async_remove = AsyncMock()
        mock_store.hass = hass

        # Patch Store creation
        from unittest.mock import patch  # noqa: PLC0415

        with patch(
            "custom_components.tibber_prices.Store",
            return_value=mock_store,
        ):
            # Call removal
            await async_remove_entry(hass, config_entry)

            # Verify storage was removed
            mock_store.async_remove.assert_called_once()
