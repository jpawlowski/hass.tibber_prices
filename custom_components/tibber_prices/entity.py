"""TibberPricesEntity class."""

from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, get_translation
from .coordinator import TibberPricesDataUpdateCoordinator
from .device import build_device_info
from .utils.attribute_specs import declared_keys, excluded_keys

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigSubentry
    from homeassistant.helpers.entity import EntityDescription


class TibberPricesEntity(CoordinatorEntity[TibberPricesDataUpdateCoordinator]):
    """TibberPricesEntity class."""

    _attr_has_entity_name = True
    entity_description: EntityDescription

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

    @cached_property
    def _declared_attribute_keys(self) -> frozenset[str]:
        """Return the attribute keys this entity's description declares (worked out once)."""
        return declared_keys(self.entity_description)

    def _apply_recorder_exclusions(self, *extra: str) -> None:
        """
        Leave the attributes out of the recorder that this entity's description doesn't keep.

        Every declared attribute is excluded unless it is declared `history=True`, so what the
        recorder stores is decided per entity, where the attribute is declared. Home Assistant sets
        `_state_info` for each entity (`async_internal_added_to_hass`, before `async_added_to_hass`)
        and reads it on every state write; this adds to the set it started with. A class-level
        `_unrecorded_attributes` would apply to every entity of the class alike.
        """
        info = self._state_info
        self._state_info = {
            **info,
            "unrecorded_attributes": info["unrecorded_attributes"]
            | excluded_keys(self.entity_description)
            | set(extra),
        }

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
