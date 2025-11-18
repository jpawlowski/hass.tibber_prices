"""
Sensor platform for Tibber Prices integration.

Provides electricity price sensors organized by calculation method:
- Interval-based: Current/next/previous price intervals
- Rolling hour: 5-interval sliding windows (2h 30m periods)
- Daily statistics: Min/max/avg within calendar day boundaries
- 24h windows: Trailing/leading statistics from current interval
- Future forecast: N-hour price predictions
- Volatility: Price variation analysis
- Diagnostic: System information and metadata

See definitions.py for complete sensor catalog.
"""

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
