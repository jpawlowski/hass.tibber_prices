"""Icon utilities for Tibber Prices entities."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from custom_components.tibber_prices.const import (
    BINARY_SENSOR_ICON_MAPPING,
    PRICE_LEVEL_CASH_ICON_MAPPING,
    PRICE_LEVEL_ICON_MAPPING,
    PRICE_RATING_ICON_MAPPING,
    VOLATILITY_ICON_MAPPING,
)
from custom_components.tibber_prices.price_utils import find_price_data_for_interval
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from collections.abc import Callable

# Constants imported from price_utils
MINUTES_PER_INTERVAL = 15


def get_dynamic_icon(
    key: str,
    value: Any,
    *,
    is_on: bool | None = None,
    coordinator_data: dict | None = None,
    has_future_periods_callback: Callable[[], bool] | None = None,
) -> str | None:
    """
    Get dynamic icon based on sensor state.

    Unified function for both sensor and binary_sensor platforms.

    Args:
        key: Entity description key
        value: Native value of the sensor
        is_on: Binary sensor state (None for regular sensors)
        coordinator_data: Coordinator data for price level lookups
        has_future_periods_callback: Callback to check if future periods exist (binary sensors)

    Returns:
        Icon string or None if no dynamic icon applies

    """
    # Try various icon sources in order
    return (
        get_trend_icon(key, value)
        or get_price_sensor_icon(key, coordinator_data)
        or get_level_sensor_icon(key, value)
        or get_rating_sensor_icon(key, value)
        or get_volatility_sensor_icon(key, value)
        or get_binary_sensor_icon(key, is_on=is_on, has_future_periods_callback=has_future_periods_callback)
    )


def get_trend_icon(key: str, value: Any) -> str | None:
    """Get icon for trend sensors."""
    if not key.startswith("price_trend_") or not isinstance(value, str):
        return None

    trend_icons = {
        "rising": "mdi:trending-up",
        "falling": "mdi:trending-down",
        "stable": "mdi:trending-neutral",
    }
    return trend_icons.get(value)


def get_price_sensor_icon(key: str, coordinator_data: dict | None) -> str | None:
    """
    Get icon for current price sensors (dynamic based on price level).

    Only current_interval_price and current_hour_average have dynamic icons.
    Other price sensors (next/previous) use static icons from entity description.

    Args:
        key: Entity description key
        coordinator_data: Coordinator data for price level lookups

    Returns:
        Icon string or None if not a current price sensor

    """
    if not coordinator_data:
        return None

    # Only current price sensors get dynamic icons
    if key == "current_interval_price":
        level = get_price_level_for_icon(coordinator_data, interval_offset=0)
        if level:
            return PRICE_LEVEL_CASH_ICON_MAPPING.get(level.upper())
    elif key == "current_hour_average":
        # For hour average, we cannot use this helper (needs sensor rolling hour logic)
        # Return None and let sensor handle it
        return None

    # For all other price sensors, let entity description handle the icon
    return None


def get_level_sensor_icon(key: str, value: Any) -> str | None:
    """Get icon for price level sensors."""
    if key not in [
        "current_interval_price_level",
        "next_interval_price_level",
        "previous_interval_price_level",
        "current_hour_price_level",
        "next_hour_price_level",
        "yesterday_price_level",
        "today_price_level",
        "tomorrow_price_level",
    ] or not isinstance(value, str):
        return None

    return PRICE_LEVEL_ICON_MAPPING.get(value.upper())


def get_rating_sensor_icon(key: str, value: Any) -> str | None:
    """Get icon for price rating sensors."""
    if key not in [
        "current_interval_price_rating",
        "next_interval_price_rating",
        "previous_interval_price_rating",
        "current_hour_price_rating",
        "next_hour_price_rating",
        "yesterday_price_rating",
        "today_price_rating",
        "tomorrow_price_rating",
    ] or not isinstance(value, str):
        return None

    return PRICE_RATING_ICON_MAPPING.get(value.upper())


def get_volatility_sensor_icon(key: str, value: Any) -> str | None:
    """Get icon for volatility sensors."""
    if not key.endswith("_volatility") or not isinstance(value, str):
        return None

    return VOLATILITY_ICON_MAPPING.get(value.upper())


def get_binary_sensor_icon(
    key: str,
    *,
    is_on: bool | None,
    has_future_periods_callback: Callable[[], bool] | None = None,
) -> str | None:
    """
    Get icon for binary sensors with dynamic state-based icons.

    Args:
        key: Entity description key
        is_on: Binary sensor state
        has_future_periods_callback: Callback to check if future periods exist

    Returns:
        Icon string or None if not a binary sensor with dynamic icons

    """
    if key not in BINARY_SENSOR_ICON_MAPPING or is_on is None:
        return None

    if is_on:
        # Sensor is ON - use "on" icon
        return BINARY_SENSOR_ICON_MAPPING[key].get("on")

    # Sensor is OFF - check if future periods exist
    has_future_periods = has_future_periods_callback() if has_future_periods_callback else False

    if has_future_periods:
        return BINARY_SENSOR_ICON_MAPPING[key].get("off")

    return BINARY_SENSOR_ICON_MAPPING[key].get("off_no_future")


def get_price_level_for_icon(
    coordinator_data: dict,
    *,
    interval_offset: int | None = None,
) -> str | None:
    """
    Get the price level for icon determination.

    Supports interval-based lookups (current/next/previous interval).

    Args:
        coordinator_data: Coordinator data
        interval_offset: Interval offset (0=current, 1=next, -1=previous)

    Returns:
        Price level string or None if not found

    """
    if not coordinator_data or interval_offset is None:
        return None

    price_info = coordinator_data.get("priceInfo", {})
    now = dt_util.now()

    # Interval-based lookup
    target_time = now + timedelta(minutes=MINUTES_PER_INTERVAL * interval_offset)
    interval_data = find_price_data_for_interval(price_info, target_time)

    if not interval_data or "level" not in interval_data:
        return None

    return interval_data["level"]
