"""Color utilities for Tibber Prices entities."""

from __future__ import annotations

from typing import Any

from custom_components.tibber_prices.const import (
    BINARY_SENSOR_COLOR_MAPPING,
    PRICE_LEVEL_COLOR_MAPPING,
    PRICE_RATING_COLOR_MAPPING,
    VOLATILITY_COLOR_MAPPING,
)

# Timing sensor color thresholds
TIMING_HIGH_PROGRESS_THRESHOLD = 75  # >=75%: High intensity color
TIMING_URGENT_THRESHOLD = 15  # <=15 min: Urgent
TIMING_SOON_THRESHOLD = 60  # <=60 min: Soon


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

    # Timing sensor colors (best_price = green, peak_price = red/orange)
    timing_color = get_timing_sensor_color(key, state_value)
    if timing_color:
        return timing_color

    # Price level/rating/volatility colors (based on uppercase value)
    if isinstance(state_value, str):
        return (
            PRICE_LEVEL_COLOR_MAPPING.get(state_value.upper())
            or PRICE_RATING_COLOR_MAPPING.get(state_value.upper())
            or VOLATILITY_COLOR_MAPPING.get(state_value.upper())
        )

    return None


def get_timing_sensor_color(key: str, state_value: Any) -> str | None:
    """
    Get color for best_price/peak_price timing sensors.

    Best price sensors: Green (good for user)
    Peak price sensors: Red/Orange (warning/alert)

    Args:
        key: Entity description key
        state_value: Sensor value (percentage or minutes)

    Returns:
        CSS color variable string or None

    """
    is_best_price = key.startswith("best_price_")

    if not (is_best_price or key.startswith("peak_price_")):
        return None

    # No data / zero value
    if state_value is None or (isinstance(state_value, (int, float)) and state_value == 0):
        return "var(--disabled-color)"

    # Progress sensors: Intensity based on completion
    if key.endswith("_progress") and isinstance(state_value, (int, float)):
        high_intensity = state_value >= TIMING_HIGH_PROGRESS_THRESHOLD
        if is_best_price:
            return "var(--success-color)" if high_intensity else "var(--info-color)"
        return "var(--error-color)" if high_intensity else "var(--warning-color)"

    # All other sensors: Simple period-type color
    return "var(--success-color)" if is_best_price else "var(--warning-color)"
