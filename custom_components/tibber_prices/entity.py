"""TibberPricesEntity class."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
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

        # enum of home types
        home_types = {
            "APARTMENT": "Apartment",
            "ROWHOUSE": "Rowhouse",
            "HOUSE": "House",
            "COTTAGE": "Cottage",
        }

        # Get home info from Tibber API if available
        home_name = "Tibber Home"
        home_id = self.coordinator.config_entry.unique_id
        home_type = None
        city = None
        app_nickname = None
        address1 = None
        if coordinator.data:
            try:
                home_id = self.unique_id
                address1 = str(coordinator.data.get("address", {}).get("address1", ""))
                city = str(coordinator.data.get("address", {}).get("city", ""))
                app_nickname = str(coordinator.data.get("appNickname", ""))
                home_type = str(coordinator.data.get("type", ""))
                # Compose a nice name
                home_name = "Tibber " + (app_nickname or address1 or "Home")
                if city:
                    home_name = f"{home_name}, {city}"
            except (KeyError, IndexError, TypeError):
                home_name = "Tibber Home"
        else:
            home_name = "Tibber Home"

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, coordinator.config_entry.unique_id or coordinator.config_entry.entry_id)},
            name=home_name,
            manufacturer="Tibber",
            model=home_types.get(home_type, "Unknown") if home_type else "Unknown",
            model_id=home_type if home_type else None,
            serial_number=home_id if home_id else None,
        )
