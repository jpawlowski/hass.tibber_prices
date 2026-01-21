"""
Number platform for Tibber Prices integration.

Provides configurable number entities for runtime overrides of Best Price
and Peak Price period calculation settings. These entities allow automation
of configuration parameters without using the options flow.

When enabled, these entities take precedence over the options flow settings.
When disabled (default), the options flow settings are used.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .core import TibberPricesConfigNumber
from .definitions import NUMBER_ENTITY_DESCRIPTIONS

if TYPE_CHECKING:
    from custom_components.tibber_prices.data import TibberPricesConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: TibberPricesConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tibber Prices number entities based on a config entry."""
    coordinator = entry.runtime_data.coordinator

    async_add_entities(
        TibberPricesConfigNumber(
            coordinator=coordinator,
            entity_description=entity_description,
        )
        for entity_description in NUMBER_ENTITY_DESCRIPTIONS
    )
