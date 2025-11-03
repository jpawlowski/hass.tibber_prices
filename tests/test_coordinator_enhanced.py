"""Test enhanced coordinator functionality."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.tibber_prices.api import TibberPricesApiClientCommunicationError
from custom_components.tibber_prices.const import DOMAIN
from custom_components.tibber_prices.coordinator import (
    TibberPricesDataUpdateCoordinator,
)


class TestEnhancedCoordinator:
    """Test enhanced coordinator functionality."""

    @pytest.fixture
    def mock_config_entry(self) -> Mock:
        """Create a mock config entry."""
        config_entry = Mock()
        config_entry.unique_id = "test_home_id_123"
        config_entry.entry_id = "test_entry_id"
        config_entry.data = {"access_token": "test_token"}
        return config_entry

    @pytest.fixture
    def mock_hass(self) -> Mock:
        """Create a mock Home Assistant instance."""
        hass = Mock()
        hass.data = {}
        # Mock the event loop for time tracking
        hass.loop = asyncio.get_event_loop()
        return hass

    @pytest.fixture
    def mock_store(self) -> Mock:
        """Create a mock store."""
        store = Mock()
        store.async_load = AsyncMock(return_value=None)
        store.async_save = AsyncMock()
        return store

    @pytest.fixture
    def mock_api(self) -> Mock:
        """Create a mock API client."""
        api = Mock()
        api.async_get_viewer_details = AsyncMock(return_value={"homes": []})
        api.async_get_price_info = AsyncMock(return_value={"homes": {}})
        api.async_get_hourly_price_rating = AsyncMock(return_value={"homes": {}})
        api.async_get_daily_price_rating = AsyncMock(return_value={"homes": {}})
        api.async_get_monthly_price_rating = AsyncMock(return_value={"homes": {}})
        return api

    @pytest.fixture
    def coordinator(
        self, mock_hass: Mock, mock_config_entry: Mock, mock_store: Mock, mock_api: Mock
    ) -> TibberPricesDataUpdateCoordinator:
        """Create a coordinator for testing."""
        mock_session = Mock()
        with (
            patch(
                "custom_components.tibber_prices.coordinator.aiohttp_client.async_get_clientsession",
                return_value=mock_session,
            ),
            patch(
                "custom_components.tibber_prices.coordinator.Store",
                return_value=mock_store,
            ),
        ):
            coordinator = TibberPricesDataUpdateCoordinator(
                hass=mock_hass,
                config_entry=mock_config_entry,
            )
            # Replace the API instance with our mock
            coordinator.api = mock_api
            return coordinator

    @pytest.mark.asyncio
    async def test_main_subentry_pattern(self, mock_hass: Mock, mock_store: Mock) -> None:
        """Test main/subentry coordinator pattern."""
        # Create main coordinator first
        main_config_entry = Mock()
        main_config_entry.unique_id = "main_home_id"
        main_config_entry.entry_id = "main_entry_id"
        main_config_entry.data = {"access_token": "test_token"}

        mock_session = Mock()
        with (
            patch(
                "custom_components.tibber_prices.coordinator.aiohttp_client.async_get_clientsession",
                return_value=mock_session,
            ),
            patch(
                "custom_components.tibber_prices.coordinator.Store",
                return_value=mock_store,
            ),
        ):
            main_coordinator = TibberPricesDataUpdateCoordinator(
                hass=mock_hass,
                config_entry=main_config_entry,
            )

        # Verify main coordinator is marked as main entry
        assert main_coordinator.is_main_entry()  # noqa: S101

        # Create subentry coordinator
        sub_config_entry = Mock()
        sub_config_entry.unique_id = "sub_home_id"
        sub_config_entry.entry_id = "sub_entry_id"
        sub_config_entry.data = {"access_token": "test_token", "home_id": "sub_home_id"}

        # Set up domain data to simulate main coordinator being already registered
        mock_hass.data[DOMAIN] = {"main_entry_id": main_coordinator}

        with (
            patch(
                "custom_components.tibber_prices.coordinator.aiohttp_client.async_get_clientsession",
                return_value=mock_session,
            ),
            patch(
                "custom_components.tibber_prices.coordinator.Store",
                return_value=mock_store,
            ),
        ):
            sub_coordinator = TibberPricesDataUpdateCoordinator(
                hass=mock_hass,
                config_entry=sub_config_entry,
            )

        # Verify subentry coordinator is not marked as main entry
        assert not sub_coordinator.is_main_entry()  # noqa: S101

    @pytest.mark.asyncio
    async def test_user_data_functionality(self, coordinator: TibberPricesDataUpdateCoordinator) -> None:
        """Test user data related functionality."""
        # Mock user data API
        mock_user_data = {
            "homes": [
                {"id": "home1", "appNickname": "Home 1"},
                {"id": "home2", "appNickname": "Home 2"},
            ]
        }
        coordinator.api.async_get_viewer_details = AsyncMock(return_value=mock_user_data)

        # Test refresh user data
        result = await coordinator.refresh_user_data()
        assert result  # noqa: S101

        # Test get user profile
        profile = coordinator.get_user_profile()
        assert isinstance(profile, dict)  # noqa: S101
        assert "last_updated" in profile  # noqa: S101
        assert "cached_user_data" in profile  # noqa: S101

        # Test get user homes
        homes = coordinator.get_user_homes()
        assert isinstance(homes, list)  # noqa: S101

    @pytest.mark.asyncio
    async def test_data_update_with_multi_home_response(self, coordinator: TibberPricesDataUpdateCoordinator) -> None:
        """Test coordinator handling multi-home API response."""
        # Mock API responses
        mock_price_response = {
            "homes": {
                "test_home_id_123": {
                    "priceInfo": {
                        "today": [{"startsAt": "2025-05-25T00:00:00Z", "total": 0.25}],
                        "tomorrow": [],
                        "yesterday": [],
                    }
                },
                "other_home_id": {
                    "priceInfo": {
                        "today": [{"startsAt": "2025-05-25T00:00:00Z", "total": 0.30}],
                        "tomorrow": [],
                        "yesterday": [],
                    }
                },
            }
        }

        mock_hourly_rating = {"homes": {"test_home_id_123": {"hourly": []}}}
        mock_daily_rating = {"homes": {"test_home_id_123": {"daily": []}}}
        mock_monthly_rating = {"homes": {"test_home_id_123": {"monthly": []}}}

        # Mock all API methods
        coordinator.api.async_get_price_info = AsyncMock(return_value=mock_price_response)
        coordinator.api.async_get_hourly_price_rating = AsyncMock(return_value=mock_hourly_rating)
        coordinator.api.async_get_daily_price_rating = AsyncMock(return_value=mock_daily_rating)
        coordinator.api.async_get_monthly_price_rating = AsyncMock(return_value=mock_monthly_rating)

        # Update the coordinator to fetch data
        await coordinator.async_refresh()

        # Verify coordinator has data
        assert coordinator.data is not None  # noqa: S101
        assert "priceInfo" in coordinator.data  # noqa: S101
        assert "priceRating" in coordinator.data  # noqa: S101

        # Test public API methods work
        intervals = coordinator.get_all_intervals()
        assert isinstance(intervals, list)  # noqa: S101

    @pytest.mark.asyncio
    async def test_error_handling_with_cache_fallback(self, coordinator: TibberPricesDataUpdateCoordinator) -> None:
        """Test error handling with fallback to cached data."""
        # Set up cached data using the store mechanism
        test_cached_data = {
            "timestamp": "2025-05-25T00:00:00Z",
            "homes": {
                "test_home_id_123": {
                    "price_info": {"today": [], "tomorrow": [], "yesterday": []},
                    "hourly_rating": {},
                    "daily_rating": {},
                    "monthly_rating": {},
                }
            },
        }

        # Mock store to return cached data
        coordinator._store.async_load = AsyncMock(  # noqa: SLF001
            return_value={
                "price_data": test_cached_data,
                "user_data": None,
                "last_price_update": "2025-05-25T00:00:00Z",
                "last_user_update": None,
            }
        )

        # Load the cache
        await coordinator._load_cache()  # noqa: SLF001

        # Mock API to raise communication error
        coordinator.api.async_get_price_info = AsyncMock(
            side_effect=TibberPricesApiClientCommunicationError("Network error")
        )

        # Should not raise exception but use cached data
        await coordinator.async_refresh()

        # Verify coordinator has fallback data
        assert coordinator.data is not None  # noqa: S101

    @pytest.mark.asyncio
    async def test_cache_persistence(self, coordinator: TibberPricesDataUpdateCoordinator) -> None:
        """Test that data is properly cached and persisted."""
        # Mock API responses
        mock_price_response = {
            "homes": {"test_home_id_123": {"priceInfo": {"today": [], "tomorrow": [], "yesterday": []}}}
        }

        coordinator.api.async_get_price_info = AsyncMock(return_value=mock_price_response)
        coordinator.api.async_get_hourly_price_rating = AsyncMock(return_value={"homes": {"test_home_id_123": {}}})
        coordinator.api.async_get_daily_price_rating = AsyncMock(return_value={"homes": {"test_home_id_123": {}}})
        coordinator.api.async_get_monthly_price_rating = AsyncMock(return_value={"homes": {"test_home_id_123": {}}})

        # Update the coordinator
        await coordinator.async_refresh()

        # Verify data was cached (store should have been called)
        coordinator._store.async_save.assert_called()  # noqa: SLF001
