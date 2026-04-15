"""Binary sensor entity descriptions for tibber_prices."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntityDescription
from homeassistant.const import EntityCategory

# Period lookahead removed - icons show "waiting" state if ANY future periods exist
# No artificial time limit - show all periods until midnight

ENTITY_DESCRIPTIONS = (
    BinarySensorEntityDescription(
        key="peak_price_period",
        translation_key="peak_price_period",
        icon="mdi:clock-alert",
    ),
    BinarySensorEntityDescription(
        key="best_price_period",
        translation_key="best_price_period",
        icon="mdi:clock-check",
    ),
    # Price phase binary sensors — ON when current intra-day phase matches the type
    BinarySensorEntityDescription(
        key="in_rising_price_phase",
        translation_key="in_rising_price_phase",
        icon="mdi:trending-up",
    ),
    BinarySensorEntityDescription(
        key="in_falling_price_phase",
        translation_key="in_falling_price_phase",
        icon="mdi:trending-down",
    ),
    BinarySensorEntityDescription(
        key="in_flat_price_phase",
        translation_key="in_flat_price_phase",
        icon="mdi:trending-neutral",
    ),
    BinarySensorEntityDescription(
        key="connection",
        translation_key="connection",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BinarySensorEntityDescription(
        key="tomorrow_data_available",
        translation_key="tomorrow_data_available",
        icon="mdi:calendar-check",
        device_class=None,  # No specific device_class = shows generic "On/Off"
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=True,  # Critical for automations
    ),
    BinarySensorEntityDescription(
        key="has_ventilation_system",
        translation_key="has_ventilation_system",
        icon="mdi:air-filter",
        device_class=None,  # No specific device_class = shows generic "On/Off"
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    BinarySensorEntityDescription(
        key="realtime_consumption_enabled",
        translation_key="realtime_consumption_enabled",
        icon="mdi:speedometer",
        device_class=None,  # No specific device_class = shows generic "On/Off"
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)
