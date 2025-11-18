"""
Binary sensor platform for Tibber Prices integration.

Provides binary (on/off) sensors for price-based automation:
- Best price period detection (cheapest intervals)
- Peak price period detection (most expensive intervals)
- Price threshold indicators (below/above configured limits)
- Tomorrow data availability status

These sensors enable simple automations like "run dishwasher during
cheap periods" without complex template logic.

See definitions.py for complete binary sensor catalog.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .core import TibberPricesBinarySensor
from .definitions import ENTITY_DESCRIPTIONS

if TYPE_CHECKING:
    from custom_components.tibber_prices.data import TibberPricesConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: TibberPricesConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tibber Prices binary sensor based on a config entry."""
    async_add_entities(
        TibberPricesBinarySensor(
            coordinator=entry.runtime_data.coordinator,
            entity_description=entity_description,
        )
        for entity_description in ENTITY_DESCRIPTIONS
    )
