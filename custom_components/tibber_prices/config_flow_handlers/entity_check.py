"""
Entity check utilities for options flow.

This module provides functions to check if relevant entities are enabled
for specific options flow steps. If no relevant entities are enabled,
a warning can be displayed to users.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from custom_components.tibber_prices.const import DOMAIN
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Maximum number of example sensors to show in warning message
MAX_EXAMPLE_SENSORS = 3
# Threshold for using "and" vs "," in formatted names
NAMES_SIMPLE_JOIN_THRESHOLD = 2

# Mapping of options flow steps to affected sensor keys
# These are the entity keys (from sensor/definitions.py and binary_sensor/definitions.py)
# that are affected by each settings page
STEP_TO_SENSOR_KEYS: dict[str, list[str]] = {
    # Price Rating settings affect all rating sensors
    "current_interval_price_rating": [
        # Interval rating sensors
        "current_interval_price_rating",
        "next_interval_price_rating",
        "previous_interval_price_rating",
        # Rolling hour rating sensors
        "current_hour_price_rating",
        "next_hour_price_rating",
        # Daily rating sensors
        "yesterday_price_rating",
        "today_price_rating",
        "tomorrow_price_rating",
    ],
    # Price Level settings affect level sensors and period binary sensors
    "price_level": [
        # Interval level sensors
        "current_interval_price_level",
        "next_interval_price_level",
        "previous_interval_price_level",
        # Rolling hour level sensors
        "current_hour_price_level",
        "next_hour_price_level",
        # Daily level sensors
        "yesterday_price_level",
        "today_price_level",
        "tomorrow_price_level",
        # Binary sensors that use level filtering
        "best_price_period",
        "peak_price_period",
    ],
    # Volatility settings affect volatility sensors
    "volatility": [
        "today_volatility",
        "tomorrow_volatility",
        "next_24h_volatility",
        "today_tomorrow_volatility",
        # Also affects trend sensors (adaptive thresholds)
        "current_price_trend",
        "next_price_trend_change",
        "price_trend_1h",
        "price_trend_2h",
        "price_trend_3h",
        "price_trend_4h",
        "price_trend_5h",
        "price_trend_6h",
        "price_trend_8h",
        "price_trend_12h",
    ],
    # Best Price settings affect best price binary sensor and timing sensors
    "best_price": [
        # Binary sensor
        "best_price_period",
        # Timing sensors
        "best_price_end_time",
        "best_price_period_duration",
        "best_price_remaining_minutes",
        "best_price_progress",
        "best_price_next_start_time",
        "best_price_next_in_minutes",
    ],
    # Peak Price settings affect peak price binary sensor and timing sensors
    "peak_price": [
        # Binary sensor
        "peak_price_period",
        # Timing sensors
        "peak_price_end_time",
        "peak_price_period_duration",
        "peak_price_remaining_minutes",
        "peak_price_progress",
        "peak_price_next_start_time",
        "peak_price_next_in_minutes",
    ],
    # Price Trend settings affect trend sensors
    "price_trend": [
        "current_price_trend",
        "next_price_trend_change",
        "price_trend_1h",
        "price_trend_2h",
        "price_trend_3h",
        "price_trend_4h",
        "price_trend_5h",
        "price_trend_6h",
        "price_trend_8h",
        "price_trend_12h",
    ],
}


def check_relevant_entities_enabled(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    step_id: str,
) -> tuple[bool, list[str]]:
    """
    Check if any relevant entities for a settings step are enabled.

    Args:
        hass: Home Assistant instance
        config_entry: Current config entry
        step_id: The options flow step ID

    Returns:
        Tuple of (has_enabled_entities, list_of_example_sensor_names)
        - has_enabled_entities: True if at least one relevant entity is enabled
        - list_of_example_sensor_names: List of example sensor keys for the warning message

    """
    sensor_keys = STEP_TO_SENSOR_KEYS.get(step_id)
    if not sensor_keys:
        # No mapping for this step - no check needed
        return True, []

    entity_registry = async_get_entity_registry(hass)
    entry_id = config_entry.entry_id

    enabled_count = 0
    example_sensors: list[str] = []

    for entity in entity_registry.entities.values():
        # Check if entity belongs to our integration and config entry
        if entity.config_entry_id != entry_id:
            continue
        if entity.platform != DOMAIN:
            continue

        # Extract the sensor key from unique_id
        # unique_id format: "{home_id}_{sensor_key}" or "{entry_id}_{sensor_key}"
        unique_id = entity.unique_id or ""
        # The sensor key is after the last underscore that separates the ID prefix
        # We check if any of our target keys is contained in the unique_id
        for sensor_key in sensor_keys:
            if unique_id.endswith(f"_{sensor_key}") or unique_id == sensor_key:
                # Found a matching entity
                if entity.disabled_by is None:
                    # Entity is enabled
                    enabled_count += 1
                    break
                # Entity is disabled - add to examples (max MAX_EXAMPLE_SENSORS)
                if len(example_sensors) < MAX_EXAMPLE_SENSORS and sensor_key not in example_sensors:
                    example_sensors.append(sensor_key)
                break

    # If we found enabled entities, return success
    if enabled_count > 0:
        return True, []

    # No enabled entities - return the example sensors for the warning
    # If we haven't collected any examples yet, use the first from the mapping
    if not example_sensors:
        example_sensors = sensor_keys[:MAX_EXAMPLE_SENSORS]

    return False, example_sensors


def format_sensor_names_for_warning(sensor_keys: list[str]) -> str:
    """
    Format sensor keys into human-readable names for warning message.

    Args:
        sensor_keys: List of sensor keys

    Returns:
        Formatted string like "Best Price Period, Best Price End Time, ..."

    """
    # Convert snake_case keys to Title Case names
    names = []
    for key in sensor_keys:
        # Replace underscores with spaces and title case
        name = key.replace("_", " ").title()
        names.append(name)

    if len(names) <= NAMES_SIMPLE_JOIN_THRESHOLD:
        return " and ".join(names)

    return ", ".join(names[:-1]) + ", and " + names[-1]


def check_chart_data_export_enabled(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> bool:
    """
    Check if the Chart Data Export sensor is enabled.

    Args:
        hass: Home Assistant instance
        config_entry: Current config entry

    Returns:
        True if the Chart Data Export sensor is enabled, False otherwise

    """
    entity_registry = async_get_entity_registry(hass)
    entry_id = config_entry.entry_id

    for entity in entity_registry.entities.values():
        # Check if entity belongs to our integration and config entry
        if entity.config_entry_id != entry_id:
            continue
        if entity.platform != DOMAIN:
            continue

        # Check for chart_data_export sensor
        unique_id = entity.unique_id or ""
        if unique_id.endswith("_chart_data_export") or unique_id == "chart_data_export":
            # Found the entity - check if enabled
            return entity.disabled_by is None

    # Entity not found (shouldn't happen, but treat as disabled)
    return False
