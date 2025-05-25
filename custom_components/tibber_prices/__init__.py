"""
Custom integration to integrate tibber_prices with Home Assistant.

For more details about this integration, please refer to
https://github.com/jpawlowski/hass.tibber_prices
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.loader import async_get_loaded_integration

from .api import TibberPricesApiClient
from .const import DOMAIN, LOGGER, async_load_translations
from .coordinator import STORAGE_VERSION, TibberPricesDataUpdateCoordinator
from .data import TibberPricesData
from .services import async_setup_services

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import TibberPricesConfigEntry

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(
    hass: HomeAssistant,
    entry: TibberPricesConfigEntry,
) -> bool:
    """Set up this integration using UI."""
    LOGGER.debug(f"[tibber_prices] async_setup_entry called for entry_id={entry.entry_id}")
    # Preload translations to populate the cache
    await async_load_translations(hass, "en")

    # Try to load translations for the user's configured language if not English
    if hass.config.language and hass.config.language != "en":
        await async_load_translations(hass, hass.config.language)

    # Register services when a config entry is loaded
    async_setup_services(hass)

    coordinator = TibberPricesDataUpdateCoordinator(
        hass=hass,
        config_entry=entry,
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
    if entry.state == ConfigEntryState.SETUP_IN_PROGRESS:
        await coordinator.async_config_entry_first_refresh()
        entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    else:
        await coordinator.async_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: TibberPricesConfigEntry,
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok and entry.runtime_data is not None:
        await entry.runtime_data.coordinator.async_shutdown()

    # Unregister services if this was the last config entry
    if not hass.config_entries.async_entries(DOMAIN):
        for service in ["get_price", "get_apexcharts_data", "get_apexcharts_yaml", "refresh_user_data"]:
            if hass.services.has_service(DOMAIN, service):
                hass.services.async_remove(DOMAIN, service)

    return unload_ok


async def async_remove_entry(
    hass: HomeAssistant,
    entry: TibberPricesConfigEntry,
) -> None:
    """Handle removal of an entry."""
    if storage := Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"):
        LOGGER.debug(f"[tibber_prices] async_remove_entry removing cache store for entry_id={entry.entry_id}")
        await storage.async_remove()


async def async_reload_entry(
    hass: HomeAssistant,
    entry: TibberPricesConfigEntry,
) -> None:
    """Reload config entry."""
    LOGGER.debug(f"[tibber_prices] async_reload_entry called for entry_id={entry.entry_id}")
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
