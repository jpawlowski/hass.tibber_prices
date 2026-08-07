"""TibberPricesEntity class."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, get_translation
from .coordinator import TibberPricesDataUpdateCoordinator
from .device import build_device_info


class TibberPricesEntity(CoordinatorEntity[TibberPricesDataUpdateCoordinator]):
    """TibberPricesEntity class."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TibberPricesDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)

        # Get configured language
        language = coordinator.hass.config.language or "en"

        # Get translated attribution, fallback to constant if translation not found
        self._attr_attribution = get_translation(["attribution"], language) or ATTRIBUTION

        # Device info is shared across all platforms - see device.py
        self._attr_device_info = build_device_info(coordinator)

    @property
    def available(self) -> bool:
        """
        Return if entity is available.

        Entity is unavailable when:
        - Coordinator has not completed first update (no data yet)
        - Coordinator has encountered an error (last_update_success = False)

        Note: Auth failures are handled by coordinator's update method,
        which raises ConfigEntryAuthFailed and triggers reauth flow.
        """
        # Return False if coordinator not ready or has errors
        # Return True if coordinator has data (bool conversion handles None/empty)
        return self.coordinator.last_update_success and bool(self.coordinator.data)
