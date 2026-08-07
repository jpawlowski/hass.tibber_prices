"""Custom types for tibber_prices."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry, ConfigSubentry
    from homeassistant.loader import Integration

    from .api import TibberPricesApiClient
    from .coordinator import TibberPricesDataUpdateCoordinator
    from .interval_pool import TibberPricesIntervalPool


@dataclass
class TibberPricesSubentryData:
    """Runtime data of a single time-travel subentry."""

    subentry: ConfigSubentry
    coordinator: TibberPricesDataUpdateCoordinator
    interval_pool: TibberPricesIntervalPool
    # Copy of subentry.data as it was when this view was set up. Home Assistant
    # mutates ConfigSubentry in place on reconfigure, so `subentry.data` already
    # shows the new values by the time the update listener runs - comparing
    # against it would never detect a change.
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class TibberPricesData:
    """Data for the tibber_prices integration."""

    client: TibberPricesApiClient
    coordinator: TibberPricesDataUpdateCoordinator
    integration: Integration
    interval_pool: TibberPricesIntervalPool  # Shared interval pool per config entry
    # Time-travel views, keyed by subentry ID. Each runs its own coordinator on a
    # shifted clock with its own pool - see time_travel.py.
    subentries: dict[str, TibberPricesSubentryData] = field(default_factory=dict)


if TYPE_CHECKING:
    type TibberPricesConfigEntry = ConfigEntry[TibberPricesData]
