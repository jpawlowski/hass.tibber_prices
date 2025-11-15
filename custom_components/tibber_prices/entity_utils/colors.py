"""Color utilities for Tibber Prices entities."""

from __future__ import annotations

from typing import Any

from custom_components.tibber_prices.const import (
    BINARY_SENSOR_COLOR_MAPPING,
    PRICE_LEVEL_COLOR_MAPPING,
    PRICE_RATING_COLOR_MAPPING,
    VOLATILITY_COLOR_MAPPING,
)


def add_icon_color_attribute(
    attributes: dict,
    key: str,
    state_value: Any = None,
    *,
    is_on: bool | None = None,
) -> None:
    """
    Add icon_color attribute if color mapping exists.

    Used by both sensor and binary_sensor platforms.

    Args:
        attributes: Attribute dictionary to update
        key: Entity description key
        state_value: Sensor value (for sensors) or None (for binary sensors)
        is_on: Binary sensor state (for binary sensors) or None (for sensors)

    """
    color = get_icon_color(key, state_value, is_on=is_on)
    if color:
        attributes["icon_color"] = color


def get_icon_color(
    key: str,
    state_value: Any = None,
    *,
    is_on: bool | None = None,
) -> str | None:
    """
    Get icon color from various mappings.

    Args:
        key: Entity description key
        state_value: Sensor value (for sensors)
        is_on: Binary sensor state (for binary sensors)

    Returns:
        CSS color variable string or None

    """
    # Binary sensor colors (based on on/off state)
    if key in BINARY_SENSOR_COLOR_MAPPING and is_on is not None:
        state_key = "on" if is_on else "off"
        return BINARY_SENSOR_COLOR_MAPPING[key].get(state_key)

    # Trend sensor colors (based on trend state)
    if key.startswith("price_trend_") and isinstance(state_value, str):
        trend_colors = {
            "rising": "var(--error-color)",  # Red/Orange for rising prices
            "falling": "var(--success-color)",  # Green for falling prices
            "stable": "var(--state-icon-color)",  # Default gray for stable
        }
        return trend_colors.get(state_value)

    # Price level/rating/volatility colors (based on uppercase value)
    if isinstance(state_value, str):
        return (
            PRICE_LEVEL_COLOR_MAPPING.get(state_value.upper())
            or PRICE_RATING_COLOR_MAPPING.get(state_value.upper())
            or VOLATILITY_COLOR_MAPPING.get(state_value.upper())
        )

    return None
