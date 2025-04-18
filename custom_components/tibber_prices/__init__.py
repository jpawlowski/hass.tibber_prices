"""
Custom integration to integrate tibber_prices with Home Assistant.

For more details about this integration, please refer to
https://github.com/jpawlowski/hass.tibber_prices
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.loader import async_get_loaded_integration

from .api import TibberPricesApiClient
from .const import DOMAIN, LOGGER
from .coordinator import STORAGE_VERSION, TibberPricesDataUpdateCoordinator
from .data import TibberPricesData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import TibberPricesConfigEntry

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
]


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(
    hass: HomeAssistant,
    entry: TibberPricesConfigEntry,
) -> bool:
    """Set up this integration using UI."""
    coordinator = TibberPricesDataUpdateCoordinator(
        hass=hass,
        entry=entry,
        logger=LOGGER,
        name=DOMAIN,
        update_interval=timedelta(minutes=5),
    )
    entry.runtime_data = TibberPricesData(
        client=TibberPricesApiClient(
            access_token=entry.data[CONF_ACCESS_TOKEN],
            session=async_get_clientsession(hass),
        ),
        integration=async_get_loaded_integration(hass, entry.domain),
        coordinator=coordinator,
    )

    # https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: TibberPricesConfigEntry,
) -> bool:
    """Handle unload of an entry."""
    await entry.runtime_data.coordinator.shutdown()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(
    hass: HomeAssistant,
    entry: TibberPricesConfigEntry,
) -> None:
    """Handle removal of an entry."""
    if storage := Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"):
        await storage.async_remove()


async def async_reload_entry(
    hass: HomeAssistant,
    entry: TibberPricesConfigEntry,
) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
