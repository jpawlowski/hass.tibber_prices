"""Service actions are registered with the integration, not with a config entry (Quality Scale action-setup)."""

import pytest

from custom_components.tibber_prices.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.mark.integration
@pytest.mark.parametrize(
    "action", ["get_price", "get_chartdata", "get_apexcharts_yaml", "refresh_user_data", "find_cheapest_block"]
)
async def test_actions_exist_before_any_entry_is_loaded(hass: HomeAssistant, action: str) -> None:
    """An automation that calls an action validates even while no entry is set up."""
    assert await async_setup_component(hass, DOMAIN, {})

    assert not hass.config_entries.async_entries(DOMAIN)
    assert hass.services.has_service(DOMAIN, action)
