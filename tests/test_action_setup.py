"""Service actions are registered with the integration, not with a config entry (Quality Scale action-setup)."""

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.tibber_prices import async_setup
from custom_components.tibber_prices.const import DOMAIN
from homeassistant.core import HomeAssistant


@pytest.mark.integration
@pytest.mark.parametrize(
    "action", ["get_price", "get_chartdata", "get_apexcharts_yaml", "refresh_user_data", "find_cheapest_block"]
)
async def test_actions_exist_before_any_entry_is_loaded(hass: HomeAssistant, action: str) -> None:
    """An automation that calls an action validates even while no entry is set up."""
    # The card registration needs http and frontend, whose setup fails in this test environment (aiohttp AppKey warning).
    with patch("custom_components.tibber_prices.async_register_frontend", AsyncMock()):
        assert await async_setup(hass, {})

    assert not hass.config_entries.async_entries(DOMAIN)
    assert hass.services.has_service(DOMAIN, action)
