"""Interval attribute builders for Tibber Prices sensors."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from custom_components.tibber_prices.const import (
    PRICE_LEVEL_MAPPING,
    PRICE_RATING_MAPPING,
)
from custom_components.tibber_prices.entity_utils import add_icon_color_attribute
from custom_components.tibber_prices.utils.price import find_price_data_for_interval

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator.core import (
        TibberPricesDataUpdateCoordinator,
    )
    from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService
    from custom_components.tibber_prices.data import TibberPricesConfigEntry

from .helpers import add_alternate_average_attribute
from .metadata import get_current_interval_data


def _get_interval_data_for_attributes(
    key: str,
    coordinator: TibberPricesDataUpdateCoordinator,
    attributes: dict,
    *,
    time: TibberPricesTimeService,
) -> dict | None:
    """
    Get interval data and set timestamp based on sensor type.

    Refactored to reduce branch complexity in main function.

    Args:
        key: The sensor entity key
        coordinator: The data update coordinator
        attributes: Attributes dict to update with timestamp if needed
        time: TibberPricesTimeService instance

    Returns:
        Interval data if found, None otherwise

    """
    now = time.now()

    # Current/next price sensors - override timestamp with interval's startsAt
    next_sensors = ["next_interval_price", "next_interval_price_level", "next_interval_price_rating"]
    prev_sensors = ["previous_interval_price", "previous_interval_price_level", "previous_interval_price_rating"]
    next_hour = ["next_hour_average_price", "next_hour_price_level", "next_hour_price_rating"]
    curr_interval = ["current_interval_price", "current_interval_price_base"]
    curr_hour = ["current_hour_average_price", "current_hour_price_level", "current_hour_price_rating"]

    if key in next_sensors:
        target_time = time.get_next_interval_start()
        interval_data = find_price_data_for_interval(coordinator.data, target_time, time=time)
        if interval_data:
            attributes["timestamp"] = interval_data["startsAt"]
        return interval_data

    if key in prev_sensors:
        target_time = time.get_interval_offset_time(-1)
        interval_data = find_price_data_for_interval(coordinator.data, target_time, time=time)
        if interval_data:
            attributes["timestamp"] = interval_data["startsAt"]
        return interval_data

    if key in next_hour:
        target_time = now + timedelta(hours=1)
        interval_data = find_price_data_for_interval(coordinator.data, target_time, time=time)
        if interval_data:
            attributes["timestamp"] = interval_data["startsAt"]
        return interval_data

    # Current interval sensors (both variants)
    if key in curr_interval:
        interval_data = get_current_interval_data(coordinator, time=time)
        if interval_data and "startsAt" in interval_data:
            attributes["timestamp"] = interval_data["startsAt"]
        return interval_data

    # Current hour sensors - keep default timestamp
    if key in curr_hour:
        return get_current_interval_data(coordinator, time=time)

    return None


def add_current_interval_price_attributes(  # noqa: PLR0913
    attributes: dict,
    key: str,
    coordinator: TibberPricesDataUpdateCoordinator,
    native_value: Any,
    cached_data: dict,
    *,
    time: TibberPricesTimeService,
    config_entry: TibberPricesConfigEntry,
) -> None:
    """
    Add attributes for current interval price sensors.

    Args:
        attributes: Dictionary to add attributes to
        key: The sensor entity key
        coordinator: The data update coordinator
        native_value: The current native value of the sensor
        cached_data: Dictionary containing cached sensor data
        time: TibberPricesTimeService instance (required)
        config_entry: Config entry for user preferences

    """
    # Get interval data and handle timestamp overrides
    interval_data = _get_interval_data_for_attributes(key, coordinator, attributes, time=time)

    # Add icon_color for price sensors (based on their price level)
    if key in [
        "current_interval_price",
        "current_interval_price_base",
        "next_interval_price",
        "previous_interval_price",
    ]:
        # For interval-based price sensors, get level from interval_data
        if interval_data and "level" in interval_data:
            level = interval_data["level"]
            add_icon_color_attribute(attributes, key="price_level", state_value=level)
    elif key in ["current_hour_average_price", "next_hour_average_price"]:
        # For hour-based price sensors, get level from cached_data
        level = cached_data.get("rolling_hour_level")
        if level:
            add_icon_color_attribute(attributes, key="price_level", state_value=level)

        # Add alternate average attribute for rolling hour average price sensors
        base_key = "rolling_hour_0" if key == "current_hour_average_price" else "rolling_hour_1"
        add_alternate_average_attribute(
            attributes,
            cached_data,
            base_key,
            config_entry=config_entry,
        )

    # Add price level attributes for all level sensors
    add_level_attributes_for_sensor(
        attributes=attributes,
        key=key,
        interval_data=interval_data,
        coordinator=coordinator,
        native_value=native_value,
        time=time,
    )

    # Add price rating attributes for all rating sensors
    add_rating_attributes_for_sensor(
        attributes=attributes,
        key=key,
        interval_data=interval_data,
        coordinator=coordinator,
        native_value=native_value,
        time=time,
    )


def add_level_attributes_for_sensor(  # noqa: PLR0913
    attributes: dict,
    key: str,
    interval_data: dict | None,
    coordinator: TibberPricesDataUpdateCoordinator,
    native_value: Any,
    *,
    time: TibberPricesTimeService,
) -> None:
    """
    Add price level attributes based on sensor type.

    Args:
        attributes: Dictionary to add attributes to
        key: The sensor entity key
        interval_data: Interval data for next/previous sensors
        coordinator: The data update coordinator
        native_value: The current native value of the sensor
        time: TibberPricesTimeService instance (required)

    """
    # For interval-based level sensors (next/previous), use interval data
    if key in ["next_interval_price_level", "previous_interval_price_level"]:
        if interval_data and "level" in interval_data:
            add_price_level_attributes(attributes, interval_data["level"])
    # For hour-aggregated level sensors, use native_value
    elif key in ["current_hour_price_level", "next_hour_price_level"]:
        level_value = native_value
        if level_value and isinstance(level_value, str):
            add_price_level_attributes(attributes, level_value.upper())
    # For current price level sensor
    elif key == "current_interval_price_level":
        current_interval_data = get_current_interval_data(coordinator, time=time)
        if current_interval_data and "level" in current_interval_data:
            add_price_level_attributes(attributes, current_interval_data["level"])


def add_price_level_attributes(attributes: dict, level: str) -> None:
    """
    Add price level specific attributes.

    Args:
        attributes: Dictionary to add attributes to
        level: The price level value (e.g., VERY_CHEAP, NORMAL, etc.)

    """
    if level in PRICE_LEVEL_MAPPING:
        attributes["level_value"] = PRICE_LEVEL_MAPPING[level]
    attributes["level_id"] = level

    # Add icon_color for dynamic styling
    add_icon_color_attribute(attributes, key="price_level", state_value=level)


def add_rating_attributes_for_sensor(  # noqa: PLR0913
    attributes: dict,
    key: str,
    interval_data: dict | None,
    coordinator: TibberPricesDataUpdateCoordinator,
    native_value: Any,
    *,
    time: TibberPricesTimeService,
) -> None:
    """
    Add price rating attributes based on sensor type.

    Args:
        attributes: Dictionary to add attributes to
        key: The sensor entity key
        interval_data: Interval data for next/previous sensors
        coordinator: The data update coordinator
        native_value: The current native value of the sensor
        time: TibberPricesTimeService instance (required)

    """
    # For interval-based rating sensors (next/previous), use interval data
    if key in ["next_interval_price_rating", "previous_interval_price_rating"]:
        if interval_data and "rating_level" in interval_data:
            add_price_rating_attributes(attributes, interval_data["rating_level"])
    # For hour-aggregated rating sensors, use native_value
    elif key in ["current_hour_price_rating", "next_hour_price_rating"]:
        rating_value = native_value
        if rating_value and isinstance(rating_value, str):
            add_price_rating_attributes(attributes, rating_value.upper())
    # For current price rating sensor
    elif key == "current_interval_price_rating":
        current_interval_data = get_current_interval_data(coordinator, time=time)
        if current_interval_data and "rating_level" in current_interval_data:
            add_price_rating_attributes(attributes, current_interval_data["rating_level"])


def add_price_rating_attributes(attributes: dict, rating: str) -> None:
    """
    Add price rating specific attributes.

    Args:
        attributes: Dictionary to add attributes to
        rating: The price rating value (e.g., LOW, NORMAL, HIGH)

    """
    if rating in PRICE_RATING_MAPPING:
        attributes["rating_value"] = PRICE_RATING_MAPPING[rating]
    attributes["rating_id"] = rating

    # Add icon_color for dynamic styling
    add_icon_color_attribute(attributes, key="price_rating", state_value=rating)
