"""Custom types for tibber_prices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .api import TibberPricesApiClient
    from .coordinator import TibberPricesDataUpdateCoordinator


@dataclass
class TibberPricesData:
    """Data for the tibber_prices integration."""

    client: TibberPricesApiClient
    coordinator: TibberPricesDataUpdateCoordinator
    integration: Integration


if TYPE_CHECKING:
    type TibberPricesConfigEntry = ConfigEntry[TibberPricesData]
