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

from .metadata import get_current_interval_data


def add_current_interval_price_attributes(  # noqa: PLR0913
    attributes: dict,
    key: str,
    coordinator: TibberPricesDataUpdateCoordinator,
    native_value: Any,
    cached_data: dict,
    *,
    time: TibberPricesTimeService,
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

    """
    price_info = coordinator.data.get("priceInfo", {}) if coordinator.data else {}
    now = time.now()

    # Determine which interval to use based on sensor type
    next_interval_sensors = [
        "next_interval_price",
        "next_interval_price_level",
        "next_interval_price_rating",
    ]
    previous_interval_sensors = [
        "previous_interval_price",
        "previous_interval_price_level",
        "previous_interval_price_rating",
    ]
    next_hour_sensors = [
        "next_hour_average_price",
        "next_hour_price_level",
        "next_hour_price_rating",
    ]
    current_hour_sensors = [
        "current_hour_average_price",
        "current_hour_price_level",
        "current_hour_price_rating",
    ]

    # Set interval data based on sensor type
    # For sensors showing data from OTHER intervals (next/previous), override timestamp with that interval's startsAt
    # For current interval sensors, keep the default platform timestamp (calculation time)
    interval_data = None
    if key in next_interval_sensors:
        target_time = time.get_next_interval_start()
        interval_data = find_price_data_for_interval(price_info, target_time, time=time)
        # Override timestamp with the NEXT interval's startsAt (when that interval starts)
        if interval_data:
            attributes["timestamp"] = interval_data["startsAt"]
    elif key in previous_interval_sensors:
        target_time = time.get_interval_offset_time(-1)
        interval_data = find_price_data_for_interval(price_info, target_time, time=time)
        # Override timestamp with the PREVIOUS interval's startsAt
        if interval_data:
            attributes["timestamp"] = interval_data["startsAt"]
    elif key in next_hour_sensors:
        target_time = now + timedelta(hours=1)
        interval_data = find_price_data_for_interval(price_info, target_time, time=time)
        # Override timestamp with the center of the next rolling hour window
        if interval_data:
            attributes["timestamp"] = interval_data["startsAt"]
    elif key in current_hour_sensors:
        current_interval_data = get_current_interval_data(coordinator, time=time)
        # Keep default timestamp (when calculation was made) for current hour sensors
    else:
        current_interval_data = get_current_interval_data(coordinator, time=time)
        interval_data = current_interval_data  # Use current_interval_data as interval_data for current_interval_price
        # Keep default timestamp (current calculation time) for current interval sensors

    # Add icon_color for price sensors (based on their price level)
    if key in ["current_interval_price", "next_interval_price", "previous_interval_price"]:
        # For interval-based price sensors, get level from interval_data
        if interval_data and "level" in interval_data:
            level = interval_data["level"]
            add_icon_color_attribute(attributes, key="price_level", state_value=level)
    elif key in ["current_hour_average_price", "next_hour_average_price"]:
        # For hour-based price sensors, get level from cached_data
        level = cached_data.get("rolling_hour_level")
        if level:
            add_icon_color_attribute(attributes, key="price_level", state_value=level)

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
