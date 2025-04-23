"""TibberPricesEntity class."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import TibberPricesDataUpdateCoordinator


class TibberPricesEntity(CoordinatorEntity[TibberPricesDataUpdateCoordinator]):
    """TibberPricesEntity class."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(self, coordinator: TibberPricesDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)

        # Get home name from Tibber API if available
        home_name = None
        if coordinator.data:
            try:
                home = coordinator.data["data"]["viewer"]["homes"][0]
                home_name = home.get("address", {}).get("address1", "Tibber Home")
            except (KeyError, IndexError):
                home_name = "Tibber Home"
        else:
            home_name = "Tibber Home"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name=home_name,
            manufacturer="Tibber",
            model="Price API",
            sw_version=str(coordinator.config_entry.version),
        )
