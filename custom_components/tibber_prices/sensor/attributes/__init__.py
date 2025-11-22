"""
Attribute builders for Tibber Prices sensors.

This package contains attribute building functions organized by sensor calculation type.
The main entry point is build_sensor_attributes() which routes to the appropriate
specialized attribute builder.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from custom_components.tibber_prices.entity_utils import (
    add_description_attributes,
    add_icon_color_attribute,
)
from custom_components.tibber_prices.sensor.types import (
    DailyStatPriceAttributes,
    DailyStatRatingAttributes,
    FutureAttributes,
    IntervalLevelAttributes,
    # Import all types for re-export
    IntervalPriceAttributes,
    IntervalRatingAttributes,
    LifecycleAttributes,
    MetadataAttributes,
    SensorAttributes,
    TimingAttributes,
    TrendAttributes,
    VolatilityAttributes,
    Window24hAttributes,
)

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator.core import (
        TibberPricesDataUpdateCoordinator,
    )
    from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService
    from custom_components.tibber_prices.data import TibberPricesConfigEntry
    from homeassistant.core import HomeAssistant

# Import from specialized modules
from .daily_stat import add_statistics_attributes
from .future import add_next_avg_attributes, get_future_prices
from .interval import add_current_interval_price_attributes
from .lifecycle import build_lifecycle_attributes
from .timing import _is_timing_or_volatility_sensor
from .trend import _add_cached_trend_attributes, _add_timing_or_volatility_attributes
from .volatility import add_volatility_type_attributes, get_prices_for_volatility
from .window_24h import add_average_price_attributes

__all__ = [
    "DailyStatPriceAttributes",
    "DailyStatRatingAttributes",
    "FutureAttributes",
    "IntervalLevelAttributes",
    "IntervalPriceAttributes",
    "IntervalRatingAttributes",
    "LifecycleAttributes",
    "MetadataAttributes",
    # Type exports
    "SensorAttributes",
    "TimingAttributes",
    "TrendAttributes",
    "VolatilityAttributes",
    "Window24hAttributes",
    "add_volatility_type_attributes",
    "build_extra_state_attributes",
    "build_sensor_attributes",
    "get_future_prices",
    "get_prices_for_volatility",
]


def build_sensor_attributes(
    key: str,
    coordinator: TibberPricesDataUpdateCoordinator,
    native_value: Any,
    cached_data: dict,
) -> dict[str, Any] | None:
    """
    Build attributes for a sensor based on its key.

    Routes to specialized attribute builders based on sensor type.

    Args:
        key: The sensor entity key
        coordinator: The data update coordinator
        native_value: The current native value of the sensor
        cached_data: Dictionary containing cached sensor data

    Returns:
        Dictionary of attributes or None if no attributes should be added

    """
    time = coordinator.time
    if not coordinator.data:
        return None

    try:
        attributes: dict[str, Any] = {}

        # For trend sensors, use cached attributes
        _add_cached_trend_attributes(attributes, key, cached_data)

        # Group sensors by type and delegate to specific handlers
        if key in [
            "current_interval_price",
            "current_interval_price_level",
            "next_interval_price",
            "previous_interval_price",
            "current_hour_average_price",
            "next_hour_average_price",
            "next_interval_price_level",
            "previous_interval_price_level",
            "current_hour_price_level",
            "next_hour_price_level",
            "next_interval_price_rating",
            "previous_interval_price_rating",
            "current_hour_price_rating",
            "next_hour_price_rating",
        ]:
            add_current_interval_price_attributes(
                attributes=attributes,
                key=key,
                coordinator=coordinator,
                native_value=native_value,
                cached_data=cached_data,
                time=time,
            )
        elif key in [
            "trailing_price_average",
            "leading_price_average",
            "trailing_price_min",
            "trailing_price_max",
            "leading_price_min",
            "leading_price_max",
        ]:
            add_average_price_attributes(attributes=attributes, key=key, coordinator=coordinator, time=time)
        elif key.startswith("next_avg_"):
            add_next_avg_attributes(attributes=attributes, key=key, coordinator=coordinator, time=time)
        elif any(
            pattern in key
            for pattern in [
                "_price_today",
                "_price_tomorrow",
                "_price_yesterday",
                "yesterday_price_level",
                "today_price_level",
                "tomorrow_price_level",
                "yesterday_price_rating",
                "today_price_rating",
                "tomorrow_price_rating",
                "rating",
                "data_timestamp",
            ]
        ):
            add_statistics_attributes(
                attributes=attributes,
                key=key,
                cached_data=cached_data,
                time=time,
            )
        elif key == "data_lifecycle_status":
            # Lifecycle sensor uses dedicated builder with calculator
            lifecycle_calculator = cached_data.get("lifecycle_calculator")
            if lifecycle_calculator:
                lifecycle_attrs = build_lifecycle_attributes(coordinator, lifecycle_calculator)
                attributes.update(lifecycle_attrs)
        elif _is_timing_or_volatility_sensor(key):
            _add_timing_or_volatility_attributes(attributes, key, cached_data, native_value, time=time)

        # For current_interval_price_level, add the original level as attribute
        if key == "current_interval_price_level" and cached_data.get("last_price_level") is not None:
            attributes["level_id"] = cached_data["last_price_level"]

        # Add icon_color for daily level and rating sensors (uses native_value)
        if key in [
            "yesterday_price_level",
            "today_price_level",
            "tomorrow_price_level",
            "yesterday_price_rating",
            "today_price_rating",
            "tomorrow_price_rating",
        ]:
            add_icon_color_attribute(attributes, key=key, state_value=native_value)

    except (KeyError, ValueError, TypeError) as ex:
        coordinator.logger.exception(
            "Error getting sensor attributes",
            extra={
                "error": str(ex),
                "entity": key,
            },
        )
        return None
    else:
        return attributes if attributes else None


def build_extra_state_attributes(  # noqa: PLR0913
    entity_key: str,
    translation_key: str | None,
    hass: HomeAssistant,
    *,
    config_entry: TibberPricesConfigEntry,
    coordinator_data: dict,
    sensor_attrs: dict[str, Any] | None = None,
    time: TibberPricesTimeService,
) -> dict[str, Any] | None:
    """
    Build extra state attributes for sensors.

    This function implements the unified attribute building pattern:
    1. Generate default timestamp (current time rounded to nearest quarter hour)
    2. Merge sensor-specific attributes (may override timestamp)
    3. Preserve timestamp ordering (always FIRST in dict)
    4. Add description attributes (always LAST)

    Args:
        entity_key: Entity key (e.g., "current_interval_price")
        translation_key: Translation key for entity
        hass: Home Assistant instance
        config_entry: Config entry with options (keyword-only)
        coordinator_data: Coordinator data dict (keyword-only)
        sensor_attrs: Sensor-specific attributes (keyword-only)
        time: TibberPricesTimeService instance (required)

    Returns:
        Complete attributes dict or None if no data available

    """
    if not coordinator_data:
        return None

    # Calculate default timestamp: current time rounded to nearest quarter hour
    # This ensures all sensors have a consistent reference time for when calculations were made
    # Individual sensors can override this if they need a different timestamp
    now = time.now()
    default_timestamp = time.round_to_nearest_quarter(now)

    # Special handling for chart_data_export: metadata → descriptions → service data
    if entity_key == "chart_data_export":
        attributes: dict[str, Any] = {
            "timestamp": default_timestamp,
        }

        # Step 1: Add metadata (timestamp + error if present)
        if sensor_attrs:
            if "timestamp" in sensor_attrs and sensor_attrs["timestamp"] is not None:
                # Chart data has its own timestamp (when service was last called)
                attributes["timestamp"] = sensor_attrs["timestamp"]

            if "error" in sensor_attrs:
                attributes["error"] = sensor_attrs["error"]

        # Step 2: Add descriptions before service data (via central utility)
        add_description_attributes(
            attributes,
            "sensor",
            translation_key,
            hass,
            config_entry,
            position="before_service_data",
        )

        # Step 3: Add service data (everything except metadata)
        if sensor_attrs:
            attributes.update({k: v for k, v in sensor_attrs.items() if k not in ("timestamp", "error")})

        return attributes if attributes else None

    # For all other sensors: standard behavior
    # Start with default timestamp (datetime object - HA serializes automatically)
    attributes: dict[str, Any] = {
        "timestamp": default_timestamp,
    }

    # Add sensor-specific attributes (may override timestamp)
    if sensor_attrs:
        # Extract timestamp override if present
        timestamp_override = sensor_attrs.pop("timestamp", None)

        # Add all other sensor attributes
        attributes.update(sensor_attrs)

        # If sensor wants to override timestamp, rebuild dict with timestamp FIRST
        if timestamp_override is not None:
            temp_attrs = dict(attributes)
            attributes.clear()
            attributes["timestamp"] = timestamp_override
            for key, value in temp_attrs.items():
                if key != "timestamp":
                    attributes[key] = value

    # Add description attributes (always last, via central utility)
    add_description_attributes(
        attributes,
        "sensor",
        translation_key,
        hass,
        config_entry,
        position="end",
    )

    return attributes if attributes else None
