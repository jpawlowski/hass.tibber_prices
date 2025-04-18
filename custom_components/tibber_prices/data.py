"""Custom types for tibber_prices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .api import TibberPricesApiClient
    from .coordinator import TibberPricesDataUpdateCoordinator


type TibberPricesConfigEntry = ConfigEntry[TibberPricesData]


@dataclass
class TibberPricesData:
    """Data for the Blueprint integration."""

    client: TibberPricesApiClient
    coordinator: TibberPricesDataUpdateCoordinator
    integration: Integration
