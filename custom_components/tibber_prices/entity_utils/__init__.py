"""
Home Assistant entity-specific utilities for Tibber Prices integration.

This package contains HA entity integration logic:
- Dynamic icon selection based on state/price levels
- Icon color mapping for visual feedback
- Attribute builders (timestamps, descriptions, periods)
- Translation-aware formatting

These functions depend on Home Assistant concepts:
- Entity states and attributes
- Translation systems (custom_translations/)
- Configuration entries and coordinator data
- User-configurable options (CONF_EXTENDED_DESCRIPTIONS, etc.)

For pure data transformation (no HA dependencies), see utils/ package.
"""

from __future__ import annotations

from .attributes import (
    add_description_attributes,
    async_add_description_attributes,
    build_period_attributes,
    build_timestamp_attribute,
)
from .colors import add_icon_color_attribute, get_icon_color
from .helpers import (
    find_rolling_hour_center_index,
    get_price_value,
    translate_level,
    translate_rating_level,
)
from .icons import (
    get_binary_sensor_icon,
    get_dynamic_icon,
    get_level_sensor_icon,
    get_price_level_for_icon,
    get_price_sensor_icon,
    get_rating_sensor_icon,
    get_trend_icon,
    get_volatility_sensor_icon,
)

__all__ = [
    "add_description_attributes",
    "add_icon_color_attribute",
    "async_add_description_attributes",
    "build_period_attributes",
    "build_timestamp_attribute",
    "find_rolling_hour_center_index",
    "get_binary_sensor_icon",
    "get_dynamic_icon",
    "get_icon_color",
    "get_level_sensor_icon",
    "get_price_level_for_icon",
    "get_price_sensor_icon",
    "get_price_value",
    "get_rating_sensor_icon",
    "get_trend_icon",
    "get_volatility_sensor_icon",
    "translate_level",
    "translate_rating_level",
]
