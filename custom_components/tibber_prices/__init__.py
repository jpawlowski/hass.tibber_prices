"""
Custom integration to integrate tibber_prices with Home Assistant.

For more details about this integration, please refer to
https://github.com/jpawlowski/hass.tibber_prices
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.loader import async_get_loaded_integration

from .api import TibberPricesApiClient
from .const import (
    DATA_CHART_CONFIG,
    DATA_CHART_METADATA_CONFIG,
    DOMAIN,
    LOGGER,
    async_load_standard_translations,
    async_load_translations,
)
from .coordinator import STORAGE_VERSION, TibberPricesDataUpdateCoordinator
from .data import TibberPricesData
from .interval_pool import (
    TibberPricesIntervalPool,
    async_load_pool_state,
    async_remove_pool_storage,
    async_save_pool_state,
)
from .services import async_setup_services

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import TibberPricesConfigEntry

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]

# Configuration schema for configuration.yaml
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional("chart_export"): vol.Schema(
                    {
                        vol.Optional("day"): vol.All(vol.Any(str, list), vol.Coerce(list)),
                        vol.Optional("resolution"): str,
                        vol.Optional("output_format"): str,
                        vol.Optional("minor_currency"): bool,
                        vol.Optional("round_decimals"): vol.All(int, vol.Range(min=0, max=10)),
                        vol.Optional("include_level"): bool,
                        vol.Optional("include_rating_level"): bool,
                        vol.Optional("include_average"): bool,
                        vol.Optional("level_filter"): vol.All(vol.Any(str, list), vol.Coerce(list)),
                        vol.Optional("rating_level_filter"): vol.All(vol.Any(str, list), vol.Coerce(list)),
                        vol.Optional("period_filter"): str,
                        vol.Optional("insert_nulls"): str,
                        vol.Optional("add_trailing_null"): bool,
                        vol.Optional("array_fields"): str,
                        vol.Optional("start_time_field"): str,
                        vol.Optional("end_time_field"): str,
                        vol.Optional("price_field"): str,
                        vol.Optional("level_field"): str,
                        vol.Optional("rating_level_field"): str,
                        vol.Optional("average_field"): str,
                        vol.Optional("data_key"): str,
                    }
                ),
            }
        ),
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the Tibber Prices component from configuration.yaml."""
    # Store chart export configuration in hass.data for sensor access
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    # Extract chart_export config if present
    domain_config = config.get(DOMAIN, {})
    chart_config = domain_config.get("chart_export", {})

    if chart_config:
        LOGGER.debug("Loaded chart_export configuration from configuration.yaml")
        hass.data[DOMAIN][DATA_CHART_CONFIG] = chart_config
    else:
        LOGGER.debug("No chart_export configuration found in configuration.yaml")
        hass.data[DOMAIN][DATA_CHART_CONFIG] = {}

    # Extract chart_metadata config if present
    chart_metadata_config = domain_config.get("chart_metadata", {})

    if chart_metadata_config:
        LOGGER.debug("Loaded chart_metadata configuration from configuration.yaml")
        hass.data[DOMAIN][DATA_CHART_METADATA_CONFIG] = chart_metadata_config
    else:
        LOGGER.debug("No chart_metadata configuration found in configuration.yaml")
        hass.data[DOMAIN][DATA_CHART_METADATA_CONFIG] = {}

    return True


def _get_access_token(hass: HomeAssistant, entry: ConfigEntry) -> str:
    """
    Get access token from entry or parent entry.

    For parent entries, the token is stored in entry.data.
    For subentries, we need to find the parent entry and get its token.

    Args:
        hass: HomeAssistant instance
        entry: Config entry (parent or subentry)

    Returns:
        Access token string

    Raises:
        ConfigEntryAuthFailed: If no access token found

    """
    # Try to get token from this entry (works for parent)
    if CONF_ACCESS_TOKEN in entry.data:
        return entry.data[CONF_ACCESS_TOKEN]

    # This is a subentry, find parent entry
    # Parent entry is the one without subentries in its data structure
    # and has the same domain
    for potential_parent in hass.config_entries.async_entries(DOMAIN):
        # Parent has ACCESS_TOKEN and is not the current entry
        if potential_parent.entry_id != entry.entry_id and CONF_ACCESS_TOKEN in potential_parent.data:
            # Check if this entry is actually a subentry of this parent
            # (HA Core manages this relationship internally)
            return potential_parent.data[CONF_ACCESS_TOKEN]

    # No token found anywhere
    msg = f"No access token found for entry {entry.entry_id}"
    raise ConfigEntryAuthFailed(msg)


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(
    hass: HomeAssistant,
    entry: TibberPricesConfigEntry,
) -> bool:
    """Set up this integration using UI."""
    LOGGER.debug(f"[tibber_prices] async_setup_entry called for entry_id={entry.entry_id}")
    # Preload translations to populate the cache
    await async_load_translations(hass, "en")
    await async_load_standard_translations(hass, "en")

    # Try to load translations for the user's configured language if not English
    if hass.config.language and hass.config.language != "en":
        await async_load_translations(hass, hass.config.language)
        await async_load_standard_translations(hass, hass.config.language)

    # Register services when a config entry is loaded
    async_setup_services(hass)

    integration = async_get_loaded_integration(hass, entry.domain)

    # Get access token (from this entry if parent, from parent if subentry)
    access_token = _get_access_token(hass, entry)

    # Create API client
    api_client = TibberPricesApiClient(
        access_token=access_token,
        session=async_get_clientsession(hass),
        version=str(integration.version) if integration.version else "unknown",
    )

    # Get home_id from config entry (required for single-home pool architecture)
    home_id = entry.data.get("home_id")
    if not home_id:
        msg = f"[{entry.title}] Config entry missing home_id (required for interval pool)"
        raise ConfigEntryAuthFailed(msg)

    # Create or load interval pool for this config entry (single-home architecture)
    pool_state = await async_load_pool_state(hass, entry.entry_id)
    if pool_state:
        interval_pool = TibberPricesIntervalPool.from_dict(
            pool_state,
            api=api_client,
            hass=hass,
            entry_id=entry.entry_id,
        )
        if interval_pool is None:
            # Old multi-home format or corrupted → create new pool
            LOGGER.info(
                "[%s] Interval pool storage invalid/corrupted, creating new pool (will rebuild from API)",
                entry.title,
            )
            interval_pool = TibberPricesIntervalPool(
                home_id=home_id,
                api=api_client,
                hass=hass,
                entry_id=entry.entry_id,
            )
        else:
            LOGGER.debug("[%s] Interval pool restored from storage (auto-save enabled)", entry.title)
    else:
        interval_pool = TibberPricesIntervalPool(
            home_id=home_id,
            api=api_client,
            hass=hass,
            entry_id=entry.entry_id,
        )
        LOGGER.debug("[%s] Created new interval pool (auto-save enabled)", entry.title)

    coordinator = TibberPricesDataUpdateCoordinator(
        hass=hass,
        config_entry=entry,
        api_client=api_client,
        interval_pool=interval_pool,
    )

    # CRITICAL: Load cache BEFORE first refresh to ensure user_data is available
    # for metadata sensors (grid_company, estimated_annual_consumption, etc.)
    # This prevents sensors from being marked as "unavailable" on first setup
    await coordinator.load_cache()

    entry.runtime_data = TibberPricesData(
        client=api_client,
        integration=integration,
        coordinator=coordinator,
        interval_pool=interval_pool,
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
    # Save interval pool state before unloading
    if entry.runtime_data is not None and entry.runtime_data.interval_pool is not None:
        pool_state = entry.runtime_data.interval_pool.to_dict()
        await async_save_pool_state(hass, entry.entry_id, pool_state)
        LOGGER.debug("[%s] Interval pool state saved on unload", entry.title)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok and entry.runtime_data is not None:
        await entry.runtime_data.coordinator.async_shutdown()

    # Unregister services if this was the last config entry
    if not hass.config_entries.async_entries(DOMAIN):
        for service in [
            "get_chartdata",
            "get_apexcharts_yaml",
            "refresh_user_data",
        ]:
            if hass.services.has_service(DOMAIN, service):
                hass.services.async_remove(DOMAIN, service)

    return unload_ok


async def async_remove_entry(
    hass: HomeAssistant,
    entry: TibberPricesConfigEntry,
) -> None:
    """Handle removal of an entry."""
    # Remove coordinator cache storage
    if storage := Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"):
        LOGGER.debug(f"[tibber_prices] async_remove_entry removing cache store for entry_id={entry.entry_id}")
        await storage.async_remove()

    # Remove interval pool storage
    await async_remove_pool_storage(hass, entry.entry_id)
    LOGGER.debug(f"[tibber_prices] async_remove_entry removed interval pool storage for entry_id={entry.entry_id}")


async def async_reload_entry(
    hass: HomeAssistant,
    entry: TibberPricesConfigEntry,
) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
