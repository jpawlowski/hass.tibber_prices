"""TibberPricesEntity class."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, get_translation
from .coordinator import TibberPricesDataUpdateCoordinator
from .device import build_device_info

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigSubentry


class TibberPricesEntity(CoordinatorEntity[TibberPricesDataUpdateCoordinator]):
    """TibberPricesEntity class."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TibberPricesDataUpdateCoordinator,
        subentry: ConfigSubentry | None = None,
    ) -> None:
        """
        Initialize.

        Args:
            coordinator: Coordinator feeding this entity.
            subentry: Time-travel subentry this entity belongs to, if any. It
                gets its own device; the platform must additionally pass
                `config_subentry_id` to async_add_entities so Home Assistant
                files that device under the subentry.

        """
        super().__init__(coordinator)

        self.subentry = subentry

        # Get configured language
        language = coordinator.hass.config.language or "en"

        # Get translated attribution, fallback to constant if translation not found
        self._attr_attribution = get_translation(["attribution"], language) or ATTRIBUTION

        # Device info is shared across all platforms - see device.py
        self._attr_device_info = build_device_info(coordinator, subentry)

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
