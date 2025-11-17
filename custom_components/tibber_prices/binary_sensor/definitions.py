"""Binary sensor entity descriptions for tibber_prices."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory

# Constants
MINUTES_PER_INTERVAL = 15
MIN_TOMORROW_INTERVALS_15MIN = 96

# Look-ahead window for future period detection (hours)
# Icons will show "waiting" state if a period starts within this window
PERIOD_LOOKAHEAD_HOURS = 6

ENTITY_DESCRIPTIONS = (
    BinarySensorEntityDescription(
        key="peak_price_period",
        translation_key="peak_price_period",
        name="Peak Price Interval",
        icon="mdi:clock-alert",
    ),
    BinarySensorEntityDescription(
        key="best_price_period",
        translation_key="best_price_period",
        name="Best Price Interval",
        icon="mdi:clock-check",
    ),
    BinarySensorEntityDescription(
        key="connection",
        translation_key="connection",
        name="Tibber API Connection",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BinarySensorEntityDescription(
        key="tomorrow_data_available",
        translation_key="tomorrow_data_available",
        name="Tomorrow's Data Available",
        icon="mdi:calendar-check",
        device_class=None,  # No specific device_class = shows generic "On/Off"
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BinarySensorEntityDescription(
        key="has_ventilation_system",
        translation_key="has_ventilation_system",
        name="Has Ventilation System",
        icon="mdi:air-filter",
        device_class=None,  # No specific device_class = shows generic "On/Off"
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    BinarySensorEntityDescription(
        key="realtime_consumption_enabled",
        translation_key="realtime_consumption_enabled",
        name="Realtime Consumption Enabled",
        icon="mdi:speedometer",
        device_class=None,  # No specific device_class = shows generic "On/Off"
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)
