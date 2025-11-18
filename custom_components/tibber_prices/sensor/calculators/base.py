"""Base calculator class for all Tibber Prices sensor calculators."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator import (
        TibberPricesDataUpdateCoordinator,
    )
    from custom_components.tibber_prices.data import TibberPricesConfigEntry
    from homeassistant.core import HomeAssistant


class BaseCalculator:
    """
    Base class for all sensor value calculators.

    Provides common access patterns to coordinator data and configuration.
    All specialized calculators should inherit from this class.
    """

    def __init__(self, coordinator: TibberPricesDataUpdateCoordinator) -> None:
        """
        Initialize the calculator.

        Args:
            coordinator: The data update coordinator providing price and user data.

        """
        self._coordinator = coordinator

    @property
    def coordinator(self) -> TibberPricesDataUpdateCoordinator:
        """Get the coordinator instance."""
        return self._coordinator

    @property
    def hass(self) -> HomeAssistant:
        """Get Home Assistant instance."""
        return self._coordinator.hass

    @property
    def config_entry(self) -> TibberPricesConfigEntry:
        """Get config entry."""
        return self._coordinator.config_entry

    @property
    def config(self) -> Any:
        """Get configuration options."""
        return self.config_entry.options

    @property
    def coordinator_data(self) -> dict[str, Any]:
        """Get full coordinator data."""
        return self._coordinator.data

    @property
    def price_info(self) -> dict[str, Any]:
        """Get price information from coordinator data."""
        return self.coordinator_data.get("priceInfo", {})

    @property
    def user_data(self) -> dict[str, Any]:
        """Get user data from coordinator data."""
        return self.coordinator_data.get("user_data", {})

    @property
    def currency(self) -> str:
        """Get currency code from price info."""
        return self.price_info.get("currency", "EUR")
