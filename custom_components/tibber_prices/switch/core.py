"""
Switch entity implementation for Tibber Prices configuration overrides.

These entities allow runtime configuration of boolean period calculation settings.
When a config entity is enabled, its value takes precedence over the
options flow setting for period calculations.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from custom_components.tibber_prices.const import get_translation
from custom_components.tibber_prices.device import build_device_info
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import callback
from homeassistant.helpers.restore_state import RestoreEntity

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator import TibberPricesDataUpdateCoordinator

    from .definitions import TibberPricesSwitchEntityDescription

_LOGGER = logging.getLogger(__name__)


class TibberPricesConfigSwitch(RestoreEntity, SwitchEntity):
    """
    A switch entity for configuring boolean period calculation settings at runtime.

    When this entity is enabled, its value overrides the corresponding
    options flow setting. When disabled (default), the options flow
    setting is used for period calculations.

    The entity restores its value after Home Assistant restart.
    """

    _attr_has_entity_name = True
    entity_description: TibberPricesSwitchEntityDescription

    # Exclude all attributes from recorder history - config entities don't need history
    _unrecorded_attributes = frozenset(
        {
            "description",
            "long_description",
            "usage_tips",
            "friendly_name",
            "icon",
        }
    )

    def __init__(
        self,
        coordinator: TibberPricesDataUpdateCoordinator,
        entity_description: TibberPricesSwitchEntityDescription,
    ) -> None:
        """Initialize the config switch entity."""
        self.coordinator = coordinator
        self.entity_description = entity_description

        # Set unique ID
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id or coordinator.config_entry.entry_id}_{entity_description.key}"
        )

        # Initialize with None - will be set in async_added_to_hass
        self._attr_is_on: bool | None = None

        # Setup device info
        self._setup_device_info()

    def _setup_device_info(self) -> None:
        """Set up device information (shared across all platforms - see device.py)."""
        self._attr_device_info = build_device_info(self.coordinator)

    async def async_added_to_hass(self) -> None:
        """Handle entity which was added to Home Assistant."""
        await super().async_added_to_hass()

        # Try to restore previous state
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state in ("on", "off"):
            self._attr_is_on = last_state.state == "on"
            _LOGGER.debug(
                "Restored %s value: %s",
                self.entity_description.key,
                self._attr_is_on,
            )
        else:
            # Initialize with value from options flow (or default)
            self._attr_is_on = self._get_value_from_options()
            _LOGGER.debug(
                "Initialized %s from options: %s",
                self.entity_description.key,
                self._attr_is_on,
            )

        # Register override with coordinator if entity is enabled
        await self._sync_override_state()

    async def async_will_remove_from_hass(self) -> None:
        """Handle entity removal from Home Assistant."""
        # Remove override when entity is removed
        self.coordinator.remove_config_override(
            self.entity_description.config_key,
            self.entity_description.config_section,
        )
        await super().async_will_remove_from_hass()

    def _get_value_from_options(self) -> bool:
        """Get the current value from options flow or default."""
        options = self.coordinator.config_entry.options
        section = options.get(self.entity_description.config_section, {})
        value = section.get(
            self.entity_description.config_key,
            self.entity_description.default_value,
        )
        return bool(value)

    async def _sync_override_state(self) -> None:
        """Sync the override state with the coordinator based on entity enabled state."""
        # Check if entity is enabled in registry
        if self.registry_entry is not None and not self.registry_entry.disabled:
            # Entity is enabled - register the override
            if self._attr_is_on is not None:
                self.coordinator.set_config_override(
                    self.entity_description.config_key,
                    self.entity_description.config_section,
                    self._attr_is_on,
                )
        else:
            # Entity is disabled - remove override
            self.coordinator.remove_config_override(
                self.entity_description.config_key,
                self.entity_description.config_section,
            )

    async def async_turn_on(self, **_kwargs: Any) -> None:
        """Turn the switch on."""
        await self._set_value(is_on=True)

    async def async_turn_off(self, **_kwargs: Any) -> None:
        """Turn the switch off."""
        await self._set_value(is_on=False)

    async def _set_value(self, *, is_on: bool) -> None:
        """Update the current value and trigger recalculation."""
        self._attr_is_on = is_on

        # Update the coordinator's runtime override
        self.coordinator.set_config_override(
            self.entity_description.config_key,
            self.entity_description.config_section,
            is_on,
        )

        # Trigger period recalculation (same path as options update)
        await self.coordinator.async_handle_config_override_update()

        _LOGGER.debug(
            "Updated %s to %s, triggered period recalculation",
            self.entity_description.key,
            is_on,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return entity state attributes with description."""
        language = self.coordinator.hass.config.language or "en"

        # Try to get description from custom translations
        # Custom translations use direct path: switch.{key}.description
        translation_path = [
            "switch",
            self.entity_description.translation_key or self.entity_description.key,
            "description",
        ]
        description = get_translation(translation_path, language)

        attrs: dict[str, Any] = {}
        if description:
            attrs["description"] = description

        return attrs or None

    @callback
    def async_registry_entry_updated(self) -> None:
        """Handle entity registry update (enabled/disabled state change)."""
        # This is called when the entity is enabled/disabled in the UI
        self.hass.async_create_task(self._sync_override_state())
