"""
Sensor entity definitions for Tibber Prices.

This module contains all SensorEntityDescription definitions organized by
calculation method. Sensor definitions are declarative and independent of
the implementation logic.

Organization by calculation pattern:
    1. Interval-based: Time offset from current interval
    2. Rolling hour: 5-interval aggregation windows
    3. Daily statistics: Calendar day min/max/avg
    4. 24h windows: Trailing/leading statistics
    5. Future forecast: N-hour windows from next interval
    6. Volatility: Price variation analysis
    7. Best/Peak Price timing: Period-based time tracking
    8. Diagnostic: System metadata
"""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime

# ============================================================================
# SENSOR DEFINITIONS - Grouped by calculation method
# ============================================================================
#
# Sensors are organized by HOW they calculate values, not WHAT they display.
# This groups sensors that share common logic and enables code reuse through
# unified handler methods.
#
# Calculation patterns:
#   1. Interval-based: Use time offset from current interval
#   2. Rolling hour: Aggregate 5-interval window (2 before + center + 2 after)
#   3. Daily statistics: Min/max/avg within calendar day boundaries
#   4. 24h windows: Trailing/leading from current interval
#   5. Future forecast: N-hour windows starting from next interval
#   6. Volatility: Statistical analysis of price variation
#   7. Best/Peak Price timing: Period-based time tracking (requires minute updates)
#   8. Diagnostic: System information and metadata
# ============================================================================

# ----------------------------------------------------------------------------
# 1. INTERVAL-BASED SENSORS (offset: -1, 0, +1 from current interval)
# ----------------------------------------------------------------------------
# All use find_price_data_for_interval() with time offset
# Shared handler: _get_interval_value(interval_offset, value_type)

INTERVAL_PRICE_SENSORS = (
    SensorEntityDescription(
        key="current_interval_price",
        translation_key="current_interval_price",
        name="Current Electricity Price",
        icon="mdi:cash",  # Dynamic: shows cash-multiple/plus/cash/minus/remove based on price level
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,  # MONETARY requires TOTAL or None
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="current_interval_price_major",
        translation_key="current_interval_price_major",
        name="Current Electricity Price (Energy Dashboard)",
        icon="mdi:cash",  # Dynamic: shows cash-multiple/plus/cash/minus/remove based on price level
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,  # MONETARY requires TOTAL or None for Energy Dashboard
        suggested_display_precision=4,  # More precision for major currency (e.g., 0.2534 EUR/kWh)
    ),
    SensorEntityDescription(
        key="next_interval_price",
        translation_key="next_interval_price",
        name="Next Price",
        icon="mdi:cash",  # Dynamic: shows cash-multiple/plus/cash/minus/remove based on price level
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,  # MONETARY requires TOTAL or None
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="previous_interval_price",
        translation_key="previous_interval_price",
        name="Previous Electricity Price",
        icon="mdi:cash-refund",  # Static: arrow back indicates "past"
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,  # MONETARY requires TOTAL or None
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
    ),
)

# NOTE: Enum options are defined inline (not imported from const.py) to avoid
# import timing issues with Home Assistant's entity platform initialization.
# Keep in sync with PRICE_LEVEL_OPTIONS in const.py!
INTERVAL_LEVEL_SENSORS = (
    SensorEntityDescription(
        key="current_interval_price_level",
        translation_key="current_interval_price_level",
        name="Current Price Level",
        icon="mdi:gauge",  # Dynamic: shows gauge/gauge-empty/gauge-low/gauge-full based on level value
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["very_cheap", "cheap", "normal", "expensive", "very_expensive"],
    ),
    SensorEntityDescription(
        key="next_interval_price_level",
        translation_key="next_interval_price_level",
        name="Next Price Level",
        icon="mdi:gauge",  # Dynamic: shows gauge/gauge-empty/gauge-low/gauge-full based on level value
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["very_cheap", "cheap", "normal", "expensive", "very_expensive"],
    ),
    SensorEntityDescription(
        key="previous_interval_price_level",
        translation_key="previous_interval_price_level",
        name="Previous Price Level",
        icon="mdi:gauge",  # Dynamic: shows gauge/gauge-empty/gauge-low/gauge-full based on level value
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["very_cheap", "cheap", "normal", "expensive", "very_expensive"],
    ),
)

# NOTE: Enum options are defined inline (not imported from const.py) to avoid
# import timing issues with Home Assistant's entity platform initialization.
# Keep in sync with PRICE_RATING_OPTIONS in const.py!
INTERVAL_RATING_SENSORS = (
    SensorEntityDescription(
        key="current_interval_price_rating",
        translation_key="current_interval_price_rating",
        name="Current Price Rating",
        icon="mdi:thumbs-up-down",  # Dynamic: shows thumbs-up/thumbs-up-down/thumbs-down based on rating value
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["low", "normal", "high"],
        entity_registry_enabled_default=False,  # Level is more commonly used
    ),
    SensorEntityDescription(
        key="next_interval_price_rating",
        translation_key="next_interval_price_rating",
        name="Next Price Rating",
        icon="mdi:thumbs-up-down",  # Dynamic: shows thumbs-up/thumbs-up-down/thumbs-down based on rating value
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["low", "normal", "high"],
        entity_registry_enabled_default=False,  # Level is more commonly used
    ),
    SensorEntityDescription(
        key="previous_interval_price_rating",
        translation_key="previous_interval_price_rating",
        name="Previous Price Rating",
        icon="mdi:thumbs-up-down",  # Dynamic: shows thumbs-up/thumbs-up-down/thumbs-down based on rating value
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["low", "normal", "high"],
    ),
)

# ----------------------------------------------------------------------------
# 2. ROLLING HOUR SENSORS (5-interval window: 2 before + center + 2 after)
# ----------------------------------------------------------------------------
# All aggregate data from rolling 5-interval window around a specific hour
# Shared handler: _get_rolling_hour_value(hour_offset, value_type)

ROLLING_HOUR_PRICE_SENSORS = (
    SensorEntityDescription(
        key="current_hour_average_price",
        translation_key="current_hour_average_price",
        name="Current Hour Average Price",
        icon="mdi:cash",  # Dynamic: shows cash-multiple/plus/cash/minus/remove based on aggregated price level
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,  # MONETARY requires TOTAL or None
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="next_hour_average_price",
        translation_key="next_hour_average_price",
        name="Next Hour Average Price",
        icon="mdi:cash-fast",  # Dynamic: shows cash-multiple/plus/cash/minus/remove based on aggregated price level
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,  # MONETARY requires TOTAL or None
        suggested_display_precision=1,
    ),
)

# NOTE: Enum options are defined inline (not imported from const.py) to avoid
# import timing issues with Home Assistant's entity platform initialization.
# Keep in sync with PRICE_LEVEL_OPTIONS in const.py!
ROLLING_HOUR_LEVEL_SENSORS = (
    SensorEntityDescription(
        key="current_hour_price_level",
        translation_key="current_hour_price_level",
        name="Current Hour Price Level",
        icon="mdi:gauge",  # Dynamic: shows gauge/gauge-empty/gauge-low/gauge-full based on aggregated level value
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["very_cheap", "cheap", "normal", "expensive", "very_expensive"],
    ),
    SensorEntityDescription(
        key="next_hour_price_level",
        translation_key="next_hour_price_level",
        name="Next Hour Price Level",
        icon="mdi:gauge",  # Dynamic: shows gauge/gauge-empty/gauge-low/gauge-full based on aggregated level value
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["very_cheap", "cheap", "normal", "expensive", "very_expensive"],
    ),
)

# NOTE: Enum options are defined inline (not imported from const.py) to avoid
# import timing issues with Home Assistant's entity platform initialization.
# Keep in sync with PRICE_RATING_OPTIONS in const.py!
ROLLING_HOUR_RATING_SENSORS = (
    SensorEntityDescription(
        key="current_hour_price_rating",
        translation_key="current_hour_price_rating",
        name="Current Hour Price Rating",
        # Dynamic: shows thumbs-up/thumbs-up-down/thumbs-down based on aggregated rating value
        icon="mdi:thumbs-up-down",
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["low", "normal", "high"],
        entity_registry_enabled_default=False,  # Level is more commonly used
    ),
    SensorEntityDescription(
        key="next_hour_price_rating",
        translation_key="next_hour_price_rating",
        name="Next Hour Price Rating",
        # Dynamic: shows thumbs-up/thumbs-up-down/thumbs-down based on aggregated rating value
        icon="mdi:thumbs-up-down",
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["low", "normal", "high"],
        entity_registry_enabled_default=False,  # Level is more commonly used
    ),
)

# ----------------------------------------------------------------------------
# 3. DAILY STATISTICS SENSORS (min/max/avg for calendar day boundaries)
# ----------------------------------------------------------------------------
# Calculate statistics for specific calendar days (today/tomorrow)

DAILY_STAT_SENSORS = (
    SensorEntityDescription(
        key="lowest_price_today",
        translation_key="lowest_price_today",
        name="Today's Lowest Price",
        icon="mdi:arrow-collapse-down",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,  # MONETARY requires TOTAL or None
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="highest_price_today",
        translation_key="highest_price_today",
        name="Today's Highest Price",
        icon="mdi:arrow-collapse-up",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,  # MONETARY requires TOTAL or None
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="average_price_today",
        translation_key="average_price_today",
        name="Today's Average Price",
        icon="mdi:chart-line",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,  # MONETARY requires TOTAL or None
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="lowest_price_tomorrow",
        translation_key="lowest_price_tomorrow",
        name="Tomorrow's Lowest Price",
        icon="mdi:arrow-collapse-down",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,  # MONETARY requires TOTAL or None
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="highest_price_tomorrow",
        translation_key="highest_price_tomorrow",
        name="Tomorrow's Highest Price",
        icon="mdi:arrow-collapse-up",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,  # MONETARY requires TOTAL or None
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="average_price_tomorrow",
        translation_key="average_price_tomorrow",
        name="Tomorrow's Average Price",
        icon="mdi:chart-line",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,  # MONETARY requires TOTAL or None
        suggested_display_precision=1,
    ),
)

# NOTE: Enum options are defined inline (not imported from const.py) to avoid
# import timing issues with Home Assistant's entity platform initialization.
# Keep in sync with PRICE_LEVEL_OPTIONS in const.py!
DAILY_LEVEL_SENSORS = (
    SensorEntityDescription(
        key="yesterday_price_level",
        translation_key="yesterday_price_level",
        name="Yesterday's Price Level",
        icon="mdi:gauge",  # Dynamic: shows gauge/gauge-empty/gauge-low/gauge-full based on daily level value
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["very_cheap", "cheap", "normal", "expensive", "very_expensive"],
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="today_price_level",
        translation_key="today_price_level",
        name="Today's Price Level",
        icon="mdi:gauge",  # Dynamic: shows gauge/gauge-empty/gauge-low/gauge-full based on daily level value
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["very_cheap", "cheap", "normal", "expensive", "very_expensive"],
    ),
    SensorEntityDescription(
        key="tomorrow_price_level",
        translation_key="tomorrow_price_level",
        name="Tomorrow's Price Level",
        icon="mdi:gauge",  # Dynamic: shows gauge/gauge-empty/gauge-low/gauge-full based on daily level value
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["very_cheap", "cheap", "normal", "expensive", "very_expensive"],
    ),
)

# NOTE: Enum options are defined inline (not imported from const.py) to avoid
# import timing issues with Home Assistant's entity platform initialization.
# Keep in sync with PRICE_RATING_OPTIONS in const.py!
DAILY_RATING_SENSORS = (
    SensorEntityDescription(
        key="yesterday_price_rating",
        translation_key="yesterday_price_rating",
        name="Yesterday's Price Rating",
        # Dynamic: shows thumbs-up/thumbs-up-down/thumbs-down based on daily rating value
        icon="mdi:thumbs-up-down",
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["low", "normal", "high"],
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="today_price_rating",
        translation_key="today_price_rating",
        name="Today's Price Rating",
        # Dynamic: shows thumbs-up/thumbs-up-down/thumbs-down based on daily rating value
        icon="mdi:thumbs-up-down",
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["low", "normal", "high"],
        entity_registry_enabled_default=False,  # Level is more commonly used
    ),
    SensorEntityDescription(
        key="tomorrow_price_rating",
        translation_key="tomorrow_price_rating",
        name="Tomorrow's Price Rating",
        # Dynamic: shows thumbs-up/thumbs-up-down/thumbs-down based on daily rating value
        icon="mdi:thumbs-up-down",
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["low", "normal", "high"],
        entity_registry_enabled_default=False,  # Level is more commonly used
    ),
)

# ----------------------------------------------------------------------------
# 4. 24H WINDOW SENSORS (trailing/leading from current interval)
# ----------------------------------------------------------------------------
# Calculate statistics over sliding 24-hour windows

WINDOW_24H_SENSORS = (
    SensorEntityDescription(
        key="trailing_price_average",
        translation_key="trailing_price_average",
        name="Trailing 24h Average Price",
        icon="mdi:chart-line",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,  # MONETARY requires TOTAL or None
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="leading_price_average",
        translation_key="leading_price_average",
        name="Leading 24h Average Price",
        icon="mdi:chart-line-variant",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,  # MONETARY requires TOTAL or None
        entity_registry_enabled_default=False,  # Advanced use case
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="trailing_price_min",
        translation_key="trailing_price_min",
        name="Trailing 24h Minimum Price",
        icon="mdi:arrow-collapse-down",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,  # MONETARY requires TOTAL or None
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="trailing_price_max",
        translation_key="trailing_price_max",
        name="Trailing 24h Maximum Price",
        icon="mdi:arrow-collapse-up",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,  # MONETARY requires TOTAL or None
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="leading_price_min",
        translation_key="leading_price_min",
        name="Leading 24h Minimum Price",
        icon="mdi:arrow-collapse-down",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,  # MONETARY requires TOTAL or None
        entity_registry_enabled_default=False,  # Advanced use case
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="leading_price_max",
        translation_key="leading_price_max",
        name="Leading 24h Maximum Price",
        icon="mdi:arrow-collapse-up",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,  # MONETARY requires TOTAL or None
        entity_registry_enabled_default=False,  # Advanced use case
        suggested_display_precision=1,
    ),
)

# ----------------------------------------------------------------------------
# 5. FUTURE FORECAST SENSORS (N-hour windows starting from next interval)
# ----------------------------------------------------------------------------
# Calculate averages and trends for upcoming time windows

FUTURE_AVG_SENSORS = (
    # Default enabled: 1h-5h
    SensorEntityDescription(
        key="next_avg_1h",
        translation_key="next_avg_1h",
        name="Next 1h Average Price",
        icon="mdi:chart-line",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,  # MONETARY requires TOTAL or None
        suggested_display_precision=1,
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="next_avg_2h",
        translation_key="next_avg_2h",
        name="Next 2h Average Price",
        icon="mdi:chart-line",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,  # MONETARY requires TOTAL or None
        suggested_display_precision=1,
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="next_avg_3h",
        translation_key="next_avg_3h",
        name="Next 3h Average Price",
        icon="mdi:chart-line",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,  # MONETARY requires TOTAL or None
        suggested_display_precision=1,
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="next_avg_4h",
        translation_key="next_avg_4h",
        name="Next 4h Average Price",
        icon="mdi:chart-line",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,  # MONETARY requires TOTAL or None
        suggested_display_precision=1,
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="next_avg_5h",
        translation_key="next_avg_5h",
        name="Next 5h Average Price",
        icon="mdi:chart-line",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,  # MONETARY requires TOTAL or None
        suggested_display_precision=1,
        entity_registry_enabled_default=True,
    ),
    # Disabled by default: 6h, 8h, 12h (advanced use cases)
    SensorEntityDescription(
        key="next_avg_6h",
        translation_key="next_avg_6h",
        name="Next 6h Average Price",
        icon="mdi:chart-line",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,  # MONETARY requires TOTAL or None
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="next_avg_8h",
        translation_key="next_avg_8h",
        name="Next 8h Average Price",
        icon="mdi:chart-line",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,  # MONETARY requires TOTAL or None
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="next_avg_12h",
        translation_key="next_avg_12h",
        name="Next 12h Average Price",
        icon="mdi:chart-line",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,  # MONETARY requires TOTAL or None
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
    ),
)

FUTURE_TREND_SENSORS = (
    # Default enabled: 1h-5h
    SensorEntityDescription(
        key="price_trend_1h",
        translation_key="price_trend_1h",
        name="Price Trend (1h)",
        icon="mdi:trending-up",  # Dynamic: shows trending-up/trending-down/trending-neutral based on trend value
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["rising", "falling", "stable"],
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="price_trend_2h",
        translation_key="price_trend_2h",
        name="Price Trend (2h)",
        icon="mdi:trending-up",  # Dynamic: shows trending-up/trending-down/trending-neutral based on trend value
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["rising", "falling", "stable"],
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="price_trend_3h",
        translation_key="price_trend_3h",
        name="Price Trend (3h)",
        icon="mdi:trending-up",  # Dynamic: shows trending-up/trending-down/trending-neutral based on trend value
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["rising", "falling", "stable"],
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="price_trend_4h",
        translation_key="price_trend_4h",
        name="Price Trend (4h)",
        icon="mdi:trending-up",  # Dynamic: shows trending-up/trending-down/trending-neutral based on trend value
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["rising", "falling", "stable"],
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="price_trend_5h",
        translation_key="price_trend_5h",
        name="Price Trend (5h)",
        icon="mdi:trending-up",  # Dynamic: shows trending-up/trending-down/trending-neutral based on trend value
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["rising", "falling", "stable"],
        entity_registry_enabled_default=True,
    ),
    # Disabled by default: 6h, 8h, 12h
    SensorEntityDescription(
        key="price_trend_6h",
        translation_key="price_trend_6h",
        name="Price Trend (6h)",
        icon="mdi:trending-up",  # Dynamic: shows trending-up/trending-down/trending-neutral based on trend value
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["rising", "falling", "stable"],
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="price_trend_8h",
        translation_key="price_trend_8h",
        name="Price Trend (8h)",
        icon="mdi:trending-up",  # Dynamic: shows trending-up/trending-down/trending-neutral based on trend value
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["rising", "falling", "stable"],
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="price_trend_12h",
        translation_key="price_trend_12h",
        name="Price Trend (12h)",
        icon="mdi:trending-up",  # Dynamic: shows trending-up/trending-down/trending-neutral based on trend value
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["rising", "falling", "stable"],
        entity_registry_enabled_default=False,
    ),
)

# ----------------------------------------------------------------------------
# 6. VOLATILITY SENSORS (coefficient of variation analysis)
# ----------------------------------------------------------------------------
# NOTE: Enum options are defined inline (not imported from const.py) to avoid
# import timing issues with Home Assistant's entity platform initialization.
# Keep in sync with VOLATILITY_OPTIONS in const.py!

VOLATILITY_SENSORS = (
    SensorEntityDescription(
        key="today_volatility",
        translation_key="today_volatility",
        name="Today's Price Volatility",
        # Dynamic: shows chart-bell-curve/chart-gantt/finance based on volatility level
        icon="mdi:chart-bell-curve-cumulative",
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["low", "moderate", "high", "very_high"],
    ),
    SensorEntityDescription(
        key="tomorrow_volatility",
        translation_key="tomorrow_volatility",
        name="Tomorrow's Price Volatility",
        # Dynamic: shows chart-bell-curve/chart-gantt/finance based on volatility level
        icon="mdi:chart-bell-curve-cumulative",
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["low", "moderate", "high", "very_high"],
        entity_registry_enabled_default=False,  # Today's volatility is usually sufficient
    ),
    SensorEntityDescription(
        key="next_24h_volatility",
        translation_key="next_24h_volatility",
        name="Next 24h Price Volatility",
        # Dynamic: shows chart-bell-curve/chart-gantt/finance based on volatility level
        icon="mdi:chart-bell-curve-cumulative",
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["low", "moderate", "high", "very_high"],
        entity_registry_enabled_default=False,  # Advanced use case
    ),
    SensorEntityDescription(
        key="today_tomorrow_volatility",
        translation_key="today_tomorrow_volatility",
        name="Today + Tomorrow Price Volatility",
        # Dynamic: shows chart-bell-curve/chart-gantt/finance based on volatility level
        icon="mdi:chart-bell-curve-cumulative",
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["low", "moderate", "high", "very_high"],
        entity_registry_enabled_default=False,  # Advanced use case
    ),
)

# ----------------------------------------------------------------------------
# 7. BEST/PEAK PRICE TIMING SENSORS (period-based time tracking)
# ----------------------------------------------------------------------------
# These sensors track time relative to best_price/peak_price binary sensor periods.
# They require minute-by-minute updates via async_track_time_interval.
#
# When period is active (binary_sensor ON):
#   - end_time: Timestamp when current period ends
#   - remaining_minutes: Minutes until period ends
#   - progress: Percentage of period completed (0-100%)
#
# When period is inactive (binary_sensor OFF):
#   - next_start_time: Timestamp when next period starts
#   - next_in_minutes: Minutes until next period starts
#
# All return None/Unknown when no period is active/scheduled.

BEST_PRICE_TIMING_SENSORS = (
    SensorEntityDescription(
        key="best_price_end_time",
        translation_key="best_price_end_time",
        name="Best Price Period End",
        icon="mdi:clock-end",
        device_class=SensorDeviceClass.TIMESTAMP,
        state_class=None,  # Timestamps: no statistics
    ),
    SensorEntityDescription(
        key="best_price_period_duration",
        translation_key="best_price_period_duration",
        name="Best Price Period Duration",
        icon="mdi:timer",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=None,  # Changes with each period: no statistics
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="best_price_remaining_minutes",
        translation_key="best_price_remaining_minutes",
        name="Best Price Remaining Time",
        icon="mdi:timer-sand",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=None,  # Countdown timer: no statistics
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="best_price_progress",
        translation_key="best_price_progress",
        name="Best Price Progress",
        icon="mdi:percent",  # Dynamic: mdi:percent-0 to mdi:percent-100
        native_unit_of_measurement=PERCENTAGE,
        state_class=None,  # Progress counter: no statistics
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="best_price_next_start_time",
        translation_key="best_price_next_start_time",
        name="Best Price Next Period Start",
        icon="mdi:clock-start",
        device_class=SensorDeviceClass.TIMESTAMP,
        state_class=None,  # Timestamps: no statistics
    ),
    SensorEntityDescription(
        key="best_price_next_in_minutes",
        translation_key="best_price_next_in_minutes",
        name="Best Price Starts In",
        icon="mdi:timer-outline",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=None,  # Countdown timer: no statistics
        suggested_display_precision=0,
    ),
)

PEAK_PRICE_TIMING_SENSORS = (
    SensorEntityDescription(
        key="peak_price_end_time",
        translation_key="peak_price_end_time",
        name="Peak Price Period End",
        icon="mdi:clock-end",
        device_class=SensorDeviceClass.TIMESTAMP,
        state_class=None,  # Timestamps: no statistics
    ),
    SensorEntityDescription(
        key="peak_price_period_duration",
        translation_key="peak_price_period_duration",
        name="Peak Price Period Duration",
        icon="mdi:timer",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=None,  # Changes with each period: no statistics
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="peak_price_remaining_minutes",
        translation_key="peak_price_remaining_minutes",
        name="Peak Price Remaining Time",
        icon="mdi:timer-sand",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=None,  # Countdown timer: no statistics
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="peak_price_progress",
        translation_key="peak_price_progress",
        name="Peak Price Progress",
        icon="mdi:percent",  # Dynamic: mdi:percent-0 to mdi:percent-100
        native_unit_of_measurement=PERCENTAGE,
        state_class=None,  # Progress counter: no statistics
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="peak_price_next_start_time",
        translation_key="peak_price_next_start_time",
        name="Peak Price Next Period Start",
        icon="mdi:clock-start",
        device_class=SensorDeviceClass.TIMESTAMP,
        state_class=None,  # Timestamps: no statistics
    ),
    SensorEntityDescription(
        key="peak_price_next_in_minutes",
        translation_key="peak_price_next_in_minutes",
        name="Peak Price Starts In",
        icon="mdi:timer-outline",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=None,  # Countdown timer: no statistics
        suggested_display_precision=0,
    ),
)

# 8. DIAGNOSTIC SENSORS (data availability and metadata)
# ----------------------------------------------------------------------------

DIAGNOSTIC_SENSORS = (
    SensorEntityDescription(
        key="data_timestamp",
        translation_key="data_timestamp",
        name="Data Expiration",
        icon="mdi:clock-check",
        device_class=SensorDeviceClass.TIMESTAMP,
        state_class=None,  # Timestamps: no statistics
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="price_forecast",
        translation_key="price_forecast",
        name="Price Forecast",
        icon="mdi:chart-line",
        state_class=None,  # Text/status value: no statistics
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

# ----------------------------------------------------------------------------
# COMBINED SENSOR DEFINITIONS
# ----------------------------------------------------------------------------

ENTITY_DESCRIPTIONS = (
    *INTERVAL_PRICE_SENSORS,
    *INTERVAL_LEVEL_SENSORS,
    *INTERVAL_RATING_SENSORS,
    *ROLLING_HOUR_PRICE_SENSORS,
    *ROLLING_HOUR_LEVEL_SENSORS,
    *ROLLING_HOUR_RATING_SENSORS,
    *DAILY_STAT_SENSORS,
    *DAILY_LEVEL_SENSORS,
    *DAILY_RATING_SENSORS,
    *WINDOW_24H_SENSORS,
    *FUTURE_AVG_SENSORS,
    *FUTURE_TREND_SENSORS,
    *VOLATILITY_SENSORS,
    *BEST_PRICE_TIMING_SENSORS,
    *PEAK_PRICE_TIMING_SENSORS,
    *DIAGNOSTIC_SENSORS,
)
