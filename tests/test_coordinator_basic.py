"""Test basic coordinator functionality with the enhanced coordinator."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.tibber_prices.coordinator import TibberPricesDataUpdateCoordinator


class TestBasicCoordinator:
    """Test basic coordinator functionality."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock Home Assistant instance."""
        hass = Mock()
        hass.data = {}
        return hass

    @pytest.fixture
    def mock_config_entry(self):
        """Create a mock config entry."""
        config_entry = Mock()
        config_entry.unique_id = "test_home_123"
        config_entry.entry_id = "test_entry"
        config_entry.data = {"access_token": "test_token"}
        return config_entry

    @pytest.fixture
    def mock_session(self):
        """Create a mock session."""
        return Mock()

    @pytest.fixture
    def coordinator(self, mock_hass, mock_config_entry, mock_session):
        """Create a coordinator instance."""
        with (
            patch(
                "custom_components.tibber_prices.coordinator.aiohttp_client.async_get_clientsession",
                return_value=mock_session,
            ),
            patch("custom_components.tibber_prices.coordinator.Store") as mock_store_class,
        ):
            mock_store = Mock()
            mock_store.async_load = AsyncMock(return_value=None)
            mock_store.async_save = AsyncMock()
            mock_store_class.return_value = mock_store

            return TibberPricesDataUpdateCoordinator(mock_hass, mock_config_entry)

    def test_coordinator_creation(self, coordinator):
        """Test that coordinator can be created."""
        assert coordinator is not None
        assert hasattr(coordinator, "get_current_interval_data")
        assert hasattr(coordinator, "get_all_intervals")
        assert hasattr(coordinator, "get_user_profile")

    def test_is_main_entry(self, coordinator):
        """Test main entry detection."""
        # First coordinator should be main entry
        assert coordinator.is_main_entry() is True

    def test_get_user_profile_no_data(self, coordinator):
        """Test getting user profile when no data is cached."""
        profile = coordinator.get_user_profile()
        assert profile == {"last_updated": None, "cached_user_data": False}

    def test_get_user_homes_no_data(self, coordinator):
        """Test getting user homes when no data is cached."""
        homes = coordinator.get_user_homes()
        assert homes == []

    def test_get_current_interval_data_no_data(self, coordinator):
        """Test getting current interval data when no data is available."""
        current_data = coordinator.get_current_interval_data()
        assert current_data is None

    def test_get_all_intervals_no_data(self, coordinator):
        """Test getting all intervals when no data is available."""
        intervals = coordinator.get_all_intervals()
        assert intervals == []
