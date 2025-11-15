"""Sensor platform for Tibber Prices integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .core import TibberPricesSensor
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
    """Set up Tibber Prices sensor based on a config entry."""
    coordinator = entry.runtime_data.coordinator

    async_add_entities(
        TibberPricesSensor(
            coordinator=coordinator,
            entity_description=entity_description,
        )
        for entity_description in ENTITY_DESCRIPTIONS
    )
