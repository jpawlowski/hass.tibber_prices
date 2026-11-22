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

from dataclasses import dataclass

from custom_components.tibber_prices.sensor.attribute_sets import (
    CHART_DATA_EXPORT,
    CHART_METADATA,
    CURRENT_INTERVAL_PRICE,
    CURRENT_PRICE_LEVEL,
    CURRENT_PRICE_TREND,
    DAILY_STATISTICS,
    DATA_LIFECYCLE,
    DAY_PATTERN,
    HOUR_AVERAGE_PRICE,
    HOUR_PRICE_LEVEL,
    HOUR_PRICE_RATING,
    INTERVAL_PRICE,
    NEXT_AVERAGE,
    PERIOD_TIMING,
    PHASE_TIMING,
    PRICE_LEVEL,
    PRICE_PHASE,
    PRICE_RATING,
    TODAY_TOMORROW_VOLATILITY,
    TREND_CHANGE,
    VOLATILITY,
    WINDOW_STATISTICS,
    outlook_attributes,
    rank_attributes,
    trajectory_attributes,
)
from custom_components.tibber_prices.utils.attribute_specs import TibberPricesAttribute
from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription, SensorStateClass
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfArea, UnitOfElectricCurrent, UnitOfEnergy, UnitOfTime


@dataclass(frozen=True, kw_only=True)
class TibberPricesSensorDescription(SensorEntityDescription):
    """
    A sensor description that also declares the attributes the sensor exposes.

    `attributes` lists what the attribute builders add beyond the common ones (see
    utils/attribute_specs.py). `open_attributes` is for the one sensor whose attributes are
    a service's result and can't be listed (chart_data_export).
    """

    attributes: tuple[TibberPricesAttribute, ...] = ()
    open_attributes: bool = False
    # The state is a mean or median price: the attribute of the same average is left out of the recorder (see
    # TibberPricesSensor._configure_average_sensor_exclusions), so the value isn't stored twice
    state_is_average: bool = False


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
    TibberPricesSensorDescription(
        key="current_interval_price",
        translation_key="current_interval_price",
        attributes=CURRENT_INTERVAL_PRICE,
        icon="mdi:cash",  # Dynamic: shows cash-multiple/plus/cash/minus/remove based on price level
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,  # MONETARY requires TOTAL or None
        suggested_display_precision=2,
    ),
    TibberPricesSensorDescription(
        key="current_interval_price_base",
        translation_key="current_interval_price_base",
        attributes=INTERVAL_PRICE,
        icon="mdi:cash",  # Dynamic: shows cash-multiple/plus/cash/minus/remove based on price level
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,  # MONETARY requires TOTAL or None for Energy Dashboard
        suggested_display_precision=4,  # More precision for base currency (e.g., 0.2534 EUR/kWh)
    ),
    TibberPricesSensorDescription(
        key="next_interval_price",
        translation_key="next_interval_price",
        attributes=INTERVAL_PRICE,
        icon="mdi:cash",  # Dynamic: shows cash-multiple/plus/cash/minus/remove based on price level
        device_class=SensorDeviceClass.MONETARY,
        state_class=None,  # Future value: historical chart not useful
        suggested_display_precision=2,
    ),
    TibberPricesSensorDescription(
        key="previous_interval_price",
        translation_key="previous_interval_price",
        attributes=INTERVAL_PRICE,
        icon="mdi:cash-refund",  # Static: arrow back indicates "past"
        device_class=SensorDeviceClass.MONETARY,
        state_class=None,  # Past snapshot: historical chart not useful
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
    ),
)

# NOTE: Enum options are defined inline (not imported from const.py) to avoid
# import timing issues with Home Assistant's entity platform initialization.
# Keep in sync with PRICE_LEVEL_* constants in const.py!
INTERVAL_LEVEL_SENSORS = (
    TibberPricesSensorDescription(
        key="current_interval_price_level",
        translation_key="current_interval_price_level",
        attributes=CURRENT_PRICE_LEVEL,
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["very_cheap", "cheap", "normal", "expensive", "very_expensive"],
    ),
    TibberPricesSensorDescription(
        key="next_interval_price_level",
        translation_key="next_interval_price_level",
        attributes=PRICE_LEVEL,
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["very_cheap", "cheap", "normal", "expensive", "very_expensive"],
    ),
    TibberPricesSensorDescription(
        key="previous_interval_price_level",
        translation_key="previous_interval_price_level",
        attributes=PRICE_LEVEL,
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["very_cheap", "cheap", "normal", "expensive", "very_expensive"],
    ),
)

# NOTE: Enum options are defined inline (not imported from const.py) to avoid
# import timing issues with Home Assistant's entity platform initialization.
# Keep in sync with PRICE_RATING_* constants in const.py!
INTERVAL_RATING_SENSORS = (
    TibberPricesSensorDescription(
        key="current_interval_price_rating",
        translation_key="current_interval_price_rating",
        attributes=PRICE_RATING,
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["low", "normal", "high"],
        entity_registry_enabled_default=False,  # Level is more commonly used
    ),
    TibberPricesSensorDescription(
        key="next_interval_price_rating",
        translation_key="next_interval_price_rating",
        attributes=PRICE_RATING,
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["low", "normal", "high"],
        entity_registry_enabled_default=False,  # Level is more commonly used
    ),
    TibberPricesSensorDescription(
        key="previous_interval_price_rating",
        translation_key="previous_interval_price_rating",
        attributes=PRICE_RATING,
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
# Shared handler: TibberPricesRollingHourCalculator.get_rolling_hour_value(hour_offset, value_type)

# Hour offset and value type per rolling hour sensor: the single source for the value
# (value_getters.py) and the window attributes (attributes/interval.py)
ROLLING_HOUR_SENSOR_WINDOWS: dict[str, tuple[int, str]] = {
    "current_hour_average_price": (0, "price"),
    "current_hour_price_level": (0, "level"),
    "current_hour_price_rating": (0, "rating"),
    "next_hour_average_price": (1, "price"),
    "next_hour_price_level": (1, "level"),
    "next_hour_price_rating": (1, "rating"),
}

ROLLING_HOUR_PRICE_SENSORS = (
    TibberPricesSensorDescription(
        key="current_hour_average_price",
        translation_key="current_hour_average_price",
        attributes=HOUR_AVERAGE_PRICE,
        state_is_average=True,
        icon="mdi:cash",  # Dynamic: shows cash-multiple/plus/cash/minus/remove based on aggregated price level
        device_class=SensorDeviceClass.MONETARY,
        state_class=None,  # Rolling derived value: historical chart not useful
        suggested_display_precision=2,
    ),
    TibberPricesSensorDescription(
        key="next_hour_average_price",
        translation_key="next_hour_average_price",
        attributes=HOUR_AVERAGE_PRICE,
        state_is_average=True,
        icon="mdi:cash-fast",  # Dynamic: shows cash-multiple/plus/cash/minus/remove based on aggregated price level
        device_class=SensorDeviceClass.MONETARY,
        state_class=None,  # Future derived value: historical chart not useful
        suggested_display_precision=2,
    ),
)

# NOTE: Enum options are defined inline (not imported from const.py) to avoid
# import timing issues with Home Assistant's entity platform initialization.
# Keep in sync with PRICE_LEVEL_* constants in const.py!
ROLLING_HOUR_LEVEL_SENSORS = (
    TibberPricesSensorDescription(
        key="current_hour_price_level",
        translation_key="current_hour_price_level",
        attributes=HOUR_PRICE_LEVEL,
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["very_cheap", "cheap", "normal", "expensive", "very_expensive"],
    ),
    TibberPricesSensorDescription(
        key="next_hour_price_level",
        translation_key="next_hour_price_level",
        attributes=HOUR_PRICE_LEVEL,
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["very_cheap", "cheap", "normal", "expensive", "very_expensive"],
    ),
)

# NOTE: Enum options are defined inline (not imported from const.py) to avoid
# import timing issues with Home Assistant's entity platform initialization.
# Keep in sync with PRICE_RATING_* constants in const.py!
ROLLING_HOUR_RATING_SENSORS = (
    TibberPricesSensorDescription(
        key="current_hour_price_rating",
        translation_key="current_hour_price_rating",
        attributes=HOUR_PRICE_RATING,
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["low", "normal", "high"],
        entity_registry_enabled_default=False,  # Level is more commonly used
    ),
    TibberPricesSensorDescription(
        key="next_hour_price_rating",
        translation_key="next_hour_price_rating",
        attributes=HOUR_PRICE_RATING,
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
    TibberPricesSensorDescription(
        key="lowest_price_today",
        translation_key="lowest_price_today",
        attributes=DAILY_STATISTICS,
        icon="mdi:arrow-collapse-down",
        device_class=SensorDeviceClass.MONETARY,
        state_class=None,  # Daily snapshot: stays constant most of the day
        suggested_display_precision=2,
    ),
    TibberPricesSensorDescription(
        key="highest_price_today",
        translation_key="highest_price_today",
        attributes=DAILY_STATISTICS,
        icon="mdi:arrow-collapse-up",
        device_class=SensorDeviceClass.MONETARY,
        state_class=None,  # Daily snapshot: stays constant most of the day
        suggested_display_precision=2,
    ),
    TibberPricesSensorDescription(
        key="average_price_today",
        translation_key="average_price_today",
        attributes=DAILY_STATISTICS,
        state_is_average=True,
        icon="mdi:chart-line",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,  # Keep TOTAL: useful to track daily avg over weeks/months
        suggested_display_precision=2,
    ),
    TibberPricesSensorDescription(
        key="lowest_price_tomorrow",
        translation_key="lowest_price_tomorrow",
        attributes=DAILY_STATISTICS,
        icon="mdi:arrow-collapse-down",
        device_class=SensorDeviceClass.MONETARY,
        state_class=None,  # Future data: historical chart not useful
        suggested_display_precision=2,
    ),
    TibberPricesSensorDescription(
        key="highest_price_tomorrow",
        translation_key="highest_price_tomorrow",
        attributes=DAILY_STATISTICS,
        icon="mdi:arrow-collapse-up",
        device_class=SensorDeviceClass.MONETARY,
        state_class=None,  # Future data: historical chart not useful
        suggested_display_precision=2,
    ),
    TibberPricesSensorDescription(
        key="average_price_tomorrow",
        translation_key="average_price_tomorrow",
        attributes=DAILY_STATISTICS,
        state_is_average=True,
        icon="mdi:chart-line",
        device_class=SensorDeviceClass.MONETARY,
        state_class=None,  # Future data: historical chart not useful
        suggested_display_precision=2,
    ),
)

# NOTE: Enum options are defined inline (not imported from const.py) to avoid
# import timing issues with Home Assistant's entity platform initialization.
# Keep in sync with PRICE_LEVEL_* constants in const.py!
DAILY_LEVEL_SENSORS = (
    TibberPricesSensorDescription(
        key="yesterday_price_level",
        translation_key="yesterday_price_level",
        attributes=PRICE_LEVEL,
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["very_cheap", "cheap", "normal", "expensive", "very_expensive"],
        entity_registry_enabled_default=False,
    ),
    TibberPricesSensorDescription(
        key="today_price_level",
        translation_key="today_price_level",
        attributes=PRICE_LEVEL,
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["very_cheap", "cheap", "normal", "expensive", "very_expensive"],
    ),
    TibberPricesSensorDescription(
        key="tomorrow_price_level",
        translation_key="tomorrow_price_level",
        attributes=PRICE_LEVEL,
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["very_cheap", "cheap", "normal", "expensive", "very_expensive"],
    ),
)

# NOTE: Enum options are defined inline (not imported from const.py) to avoid
# import timing issues with Home Assistant's entity platform initialization.
# Keep in sync with PRICE_RATING_* constants in const.py!
DAILY_RATING_SENSORS = (
    TibberPricesSensorDescription(
        key="yesterday_price_rating",
        translation_key="yesterday_price_rating",
        attributes=PRICE_RATING,
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["low", "normal", "high"],
        entity_registry_enabled_default=False,
    ),
    TibberPricesSensorDescription(
        key="today_price_rating",
        translation_key="today_price_rating",
        attributes=PRICE_RATING,
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["low", "normal", "high"],
        entity_registry_enabled_default=False,  # Level is more commonly used
    ),
    TibberPricesSensorDescription(
        key="tomorrow_price_rating",
        translation_key="tomorrow_price_rating",
        attributes=PRICE_RATING,
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
    TibberPricesSensorDescription(
        key="trailing_price_average",
        translation_key="trailing_price_average",
        attributes=WINDOW_STATISTICS,
        state_is_average=True,
        icon="mdi:chart-line",
        device_class=SensorDeviceClass.MONETARY,
        state_class=None,  # Rolling window: value shifts every 15min, history chart misleading
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
    ),
    TibberPricesSensorDescription(
        key="leading_price_average",
        translation_key="leading_price_average",
        attributes=WINDOW_STATISTICS,
        state_is_average=True,
        icon="mdi:chart-line-variant",
        device_class=SensorDeviceClass.MONETARY,
        state_class=None,  # Rolling window: value shifts every 15min, history chart misleading
        entity_registry_enabled_default=False,  # Advanced use case
        suggested_display_precision=2,
    ),
    TibberPricesSensorDescription(
        key="trailing_price_min",
        translation_key="trailing_price_min",
        attributes=WINDOW_STATISTICS,
        icon="mdi:arrow-collapse-down",
        device_class=SensorDeviceClass.MONETARY,
        state_class=None,  # Rolling window: value shifts every 15min, history chart misleading
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
    ),
    TibberPricesSensorDescription(
        key="trailing_price_max",
        translation_key="trailing_price_max",
        attributes=WINDOW_STATISTICS,
        icon="mdi:arrow-collapse-up",
        device_class=SensorDeviceClass.MONETARY,
        state_class=None,  # Rolling window: value shifts every 15min, history chart misleading
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
    ),
    TibberPricesSensorDescription(
        key="leading_price_min",
        translation_key="leading_price_min",
        attributes=WINDOW_STATISTICS,
        icon="mdi:arrow-collapse-down",
        device_class=SensorDeviceClass.MONETARY,
        state_class=None,  # Rolling window: value shifts every 15min, history chart misleading
        entity_registry_enabled_default=False,  # Advanced use case
        suggested_display_precision=2,
    ),
    TibberPricesSensorDescription(
        key="leading_price_max",
        translation_key="leading_price_max",
        attributes=WINDOW_STATISTICS,
        icon="mdi:arrow-collapse-up",
        device_class=SensorDeviceClass.MONETARY,
        state_class=None,  # Rolling window: value shifts every 15min, history chart misleading
        entity_registry_enabled_default=False,  # Advanced use case
        suggested_display_precision=2,
    ),
)

# ----------------------------------------------------------------------------
# 5. FUTURE FORECAST SENSORS (N-hour windows starting from next interval)
# ----------------------------------------------------------------------------
# Calculate averages and trends for upcoming time windows

FUTURE_MEAN_SENSORS = (
    # Default enabled: 1h-5h
    TibberPricesSensorDescription(
        key="next_avg_1h",
        translation_key="next_avg_1h",
        attributes=NEXT_AVERAGE,
        state_is_average=True,
        icon="mdi:chart-line",
        device_class=SensorDeviceClass.MONETARY,
        state_class=None,  # Future forecast: historical chart not useful
        suggested_display_precision=2,
        entity_registry_enabled_default=True,
    ),
    TibberPricesSensorDescription(
        key="next_avg_2h",
        translation_key="next_avg_2h",
        attributes=NEXT_AVERAGE,
        state_is_average=True,
        icon="mdi:chart-line",
        device_class=SensorDeviceClass.MONETARY,
        state_class=None,  # Future forecast: historical chart not useful
        suggested_display_precision=2,
        entity_registry_enabled_default=True,
    ),
    TibberPricesSensorDescription(
        key="next_avg_3h",
        translation_key="next_avg_3h",
        attributes=NEXT_AVERAGE,
        state_is_average=True,
        icon="mdi:chart-line",
        device_class=SensorDeviceClass.MONETARY,
        state_class=None,  # Future forecast: historical chart not useful
        suggested_display_precision=2,
        entity_registry_enabled_default=True,
    ),
    TibberPricesSensorDescription(
        key="next_avg_4h",
        translation_key="next_avg_4h",
        attributes=NEXT_AVERAGE,
        state_is_average=True,
        icon="mdi:chart-line",
        device_class=SensorDeviceClass.MONETARY,
        state_class=None,  # Future forecast: historical chart not useful
        suggested_display_precision=2,
        entity_registry_enabled_default=True,
    ),
    TibberPricesSensorDescription(
        key="next_avg_5h",
        translation_key="next_avg_5h",
        attributes=NEXT_AVERAGE,
        state_is_average=True,
        icon="mdi:chart-line",
        device_class=SensorDeviceClass.MONETARY,
        state_class=None,  # Future forecast: historical chart not useful
        suggested_display_precision=2,
        entity_registry_enabled_default=True,
    ),
    # Disabled by default: 6h, 8h, 12h (advanced use cases)
    TibberPricesSensorDescription(
        key="next_avg_6h",
        translation_key="next_avg_6h",
        attributes=NEXT_AVERAGE,
        state_is_average=True,
        icon="mdi:chart-line",
        device_class=SensorDeviceClass.MONETARY,
        state_class=None,  # Future forecast: historical chart not useful
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    TibberPricesSensorDescription(
        key="next_avg_8h",
        translation_key="next_avg_8h",
        attributes=NEXT_AVERAGE,
        state_is_average=True,
        icon="mdi:chart-line",
        device_class=SensorDeviceClass.MONETARY,
        state_class=None,  # Future forecast: historical chart not useful
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    TibberPricesSensorDescription(
        key="next_avg_12h",
        translation_key="next_avg_12h",
        attributes=NEXT_AVERAGE,
        state_is_average=True,
        icon="mdi:chart-line",
        device_class=SensorDeviceClass.MONETARY,
        state_class=None,  # Future forecast: historical chart not useful
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
)

FUTURE_TREND_SENSORS = (
    # Current trend sensor (what is the trend right now, valid until next change?)
    TibberPricesSensorDescription(
        key="current_price_trend",
        translation_key="current_price_trend",
        attributes=CURRENT_PRICE_TREND,
        icon="mdi:trending-up",  # Dynamic: trending-up/trending-down/trending-neutral based on current trend
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["strongly_falling", "falling", "stable", "rising", "strongly_rising"],
        entity_registry_enabled_default=True,
    ),
    # Next trend change sensor (when will trend change?)
    TibberPricesSensorDescription(
        key="next_price_trend_change",
        translation_key="next_price_trend_change",
        attributes=TREND_CHANGE,
        icon="mdi:clock-alert",  # Dynamic: trending-up/trending-down/trending-neutral based on direction
        device_class=SensorDeviceClass.TIMESTAMP,
        state_class=None,  # Timestamp: no statistics
        entity_registry_enabled_default=True,
    ),
    # Trend change countdown sensor (how long until trend changes?)
    TibberPricesSensorDescription(
        key="next_price_trend_change_in",
        translation_key="next_price_trend_change_in",
        attributes=TREND_CHANGE,
        icon="mdi:timer-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        state_class=None,  # Countdown timer: no statistics
        suggested_display_precision=2,
        entity_registry_enabled_default=True,
    ),
    # Price outlook forecast sensors (is the average of the next Xh cheaper/more expensive than now?)
    # Default enabled: 1h-5h
    TibberPricesSensorDescription(
        key="price_outlook_1h",
        translation_key="price_outlook_1h",
        attributes=outlook_attributes(1),
        icon="mdi:trending-up",  # Dynamic: shows trending-up/trending-down/trending-neutral based on trend value
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["strongly_falling", "falling", "stable", "rising", "strongly_rising"],
        entity_registry_enabled_default=True,
    ),
    TibberPricesSensorDescription(
        key="price_outlook_2h",
        translation_key="price_outlook_2h",
        attributes=outlook_attributes(2),
        icon="mdi:trending-up",  # Dynamic: shows trending-up/trending-down/trending-neutral based on trend value
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["strongly_falling", "falling", "stable", "rising", "strongly_rising"],
        entity_registry_enabled_default=True,
    ),
    TibberPricesSensorDescription(
        key="price_outlook_3h",
        translation_key="price_outlook_3h",
        attributes=outlook_attributes(3),
        icon="mdi:trending-up",  # Dynamic: shows trending-up/trending-down/trending-neutral based on trend value
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["strongly_falling", "falling", "stable", "rising", "strongly_rising"],
        entity_registry_enabled_default=True,
    ),
    TibberPricesSensorDescription(
        key="price_outlook_4h",
        translation_key="price_outlook_4h",
        attributes=outlook_attributes(4),
        icon="mdi:trending-up",  # Dynamic: shows trending-up/trending-down/trending-neutral based on trend value
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["strongly_falling", "falling", "stable", "rising", "strongly_rising"],
        entity_registry_enabled_default=True,
    ),
    TibberPricesSensorDescription(
        key="price_outlook_5h",
        translation_key="price_outlook_5h",
        attributes=outlook_attributes(5),
        icon="mdi:trending-up",  # Dynamic: shows trending-up/trending-down/trending-neutral based on trend value
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["strongly_falling", "falling", "stable", "rising", "strongly_rising"],
        entity_registry_enabled_default=True,
    ),
    # Disabled by default: 6h, 8h, 12h
    TibberPricesSensorDescription(
        key="price_outlook_6h",
        translation_key="price_outlook_6h",
        attributes=outlook_attributes(6),
        icon="mdi:trending-up",  # Dynamic: shows trending-up/trending-down/trending-neutral based on trend value
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["strongly_falling", "falling", "stable", "rising", "strongly_rising"],
        entity_registry_enabled_default=False,
    ),
    TibberPricesSensorDescription(
        key="price_outlook_8h",
        translation_key="price_outlook_8h",
        attributes=outlook_attributes(8),
        icon="mdi:trending-up",  # Dynamic: shows trending-up/trending-down/trending-neutral based on trend value
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["strongly_falling", "falling", "stable", "rising", "strongly_rising"],
        entity_registry_enabled_default=False,
    ),
    TibberPricesSensorDescription(
        key="price_outlook_12h",
        translation_key="price_outlook_12h",
        attributes=outlook_attributes(12),
        icon="mdi:trending-up",  # Dynamic: shows trending-up/trending-down/trending-neutral based on trend value
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["strongly_falling", "falling", "stable", "rising", "strongly_rising"],
        entity_registry_enabled_default=False,
    ),
)

# ----------------------------------------------------------------------------
# 5b. PRICE TRAJECTORY SENSORS (first-half vs second-half window comparison)
# ----------------------------------------------------------------------------
# These sensors reveal turning points: is the price rising or falling WITHIN
# the window? Complements price_outlook_Xh sensors.
#
# Example at a price minimum (12:00):
# - price_outlook_4h: "strongly_falling" (Ø next 4h is below current high)
# - price_trajectory_4h: "rising" (second half avg > first half avg)
# → Combined: act now, reversal is coming within the window.
#
# Coverage starts at 2h (minimum for meaningful first/second half split).
# Default enabled: 2h-5h

PRICE_TRAJECTORY_SENSORS = (
    TibberPricesSensorDescription(
        key="price_trajectory_2h",
        translation_key="price_trajectory_2h",
        attributes=trajectory_attributes(2),
        icon="mdi:trending-up",  # Dynamic: shows trending-up/trending-down/trending-neutral based on trend value
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["strongly_falling", "falling", "stable", "rising", "strongly_rising"],
        entity_registry_enabled_default=True,
    ),
    TibberPricesSensorDescription(
        key="price_trajectory_3h",
        translation_key="price_trajectory_3h",
        attributes=trajectory_attributes(3),
        icon="mdi:trending-up",  # Dynamic: shows trending-up/trending-down/trending-neutral based on trend value
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["strongly_falling", "falling", "stable", "rising", "strongly_rising"],
        entity_registry_enabled_default=True,
    ),
    TibberPricesSensorDescription(
        key="price_trajectory_4h",
        translation_key="price_trajectory_4h",
        attributes=trajectory_attributes(4),
        icon="mdi:trending-up",  # Dynamic: shows trending-up/trending-down/trending-neutral based on trend value
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["strongly_falling", "falling", "stable", "rising", "strongly_rising"],
        entity_registry_enabled_default=True,
    ),
    TibberPricesSensorDescription(
        key="price_trajectory_5h",
        translation_key="price_trajectory_5h",
        attributes=trajectory_attributes(5),
        icon="mdi:trending-up",  # Dynamic: shows trending-up/trending-down/trending-neutral based on trend value
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["strongly_falling", "falling", "stable", "rising", "strongly_rising"],
        entity_registry_enabled_default=True,
    ),
    # Disabled by default: 6h, 8h, 12h
    TibberPricesSensorDescription(
        key="price_trajectory_6h",
        translation_key="price_trajectory_6h",
        attributes=trajectory_attributes(6),
        icon="mdi:trending-up",  # Dynamic: shows trending-up/trending-down/trending-neutral based on trend value
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["strongly_falling", "falling", "stable", "rising", "strongly_rising"],
        entity_registry_enabled_default=False,
    ),
    TibberPricesSensorDescription(
        key="price_trajectory_8h",
        translation_key="price_trajectory_8h",
        attributes=trajectory_attributes(8),
        icon="mdi:trending-up",  # Dynamic: shows trending-up/trending-down/trending-neutral based on trend value
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["strongly_falling", "falling", "stable", "rising", "strongly_rising"],
        entity_registry_enabled_default=False,
    ),
    TibberPricesSensorDescription(
        key="price_trajectory_12h",
        translation_key="price_trajectory_12h",
        attributes=trajectory_attributes(12),
        icon="mdi:trending-up",  # Dynamic: shows trending-up/trending-down/trending-neutral based on trend value
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["strongly_falling", "falling", "stable", "rising", "strongly_rising"],
        entity_registry_enabled_default=False,
    ),
)

# ----------------------------------------------------------------------------
# 6. VOLATILITY SENSORS (coefficient of variation analysis)
# ----------------------------------------------------------------------------
# NOTE: Enum options are defined inline (not imported from const.py) to avoid
# import timing issues with Home Assistant's entity platform initialization.
# Keep in sync with VOLATILITY_* constants in const.py!

VOLATILITY_SENSORS = (
    TibberPricesSensorDescription(
        key="today_volatility",
        translation_key="today_volatility",
        attributes=VOLATILITY,
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["low", "moderate", "high", "very_high"],
    ),
    TibberPricesSensorDescription(
        key="tomorrow_volatility",
        translation_key="tomorrow_volatility",
        attributes=VOLATILITY,
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["low", "moderate", "high", "very_high"],
        entity_registry_enabled_default=False,  # Today's volatility is usually sufficient
    ),
    TibberPricesSensorDescription(
        key="next_24h_volatility",
        translation_key="next_24h_volatility",
        attributes=VOLATILITY,
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["low", "moderate", "high", "very_high"],
        entity_registry_enabled_default=False,  # Advanced use case
    ),
    TibberPricesSensorDescription(
        key="today_tomorrow_volatility",
        translation_key="today_tomorrow_volatility",
        attributes=TODAY_TOMORROW_VOLATILITY,
        device_class=SensorDeviceClass.ENUM,
        state_class=None,  # Enum values: no statistics
        options=["low", "moderate", "high", "very_high"],
        entity_registry_enabled_default=False,  # Advanced use case
    ),
)

# ----------------------------------------------------------------------------
# 6b. PRICE PERCENTILE RANK SENSORS
# ----------------------------------------------------------------------------
# These sensors show where the current price ranks within a reference period.
# The state (0-100%) answers: "What percentage of reference prices are cheaper
# than the current price?"
#
# 0%  = current price is the cheapest in the reference period
# 50% = half the prices are cheaper (current price at median level)
# ~99% = almost everything is cheaper (current price near the maximum)
#
# Reference periods:
#   - today:           96 intervals of today (local calendar day)
#   - tomorrow:        96 intervals of tomorrow (once data is available)
#   - today_tomorrow:  192 combined intervals when tomorrow is available
#
# Use case: "Is now the right time to run a large appliance?"
# - current_interval_price_rank_today < 25 → bottom quartile, great time to use energy
# - current_interval_price_rank_today > 75 → top quartile, consider delaying consumption

PERCENTILE_RANK_SENSORS = (
    # ----------------------------------------------------------------
    # Current interval rank sensors
    # ----------------------------------------------------------------
    TibberPricesSensorDescription(
        key="current_interval_price_rank_today",
        translation_key="current_interval_price_rank_today",
        attributes=rank_attributes("current_price"),
        icon="mdi:percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=None,  # Position metric: no statistics
        suggested_display_precision=0,
    ),
    TibberPricesSensorDescription(
        key="current_interval_price_rank_tomorrow",
        translation_key="current_interval_price_rank_tomorrow",
        attributes=rank_attributes("current_price"),
        icon="mdi:percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=None,  # Position metric: no statistics
        suggested_display_precision=0,
        entity_registry_enabled_default=False,  # Available once tomorrow's data arrives
    ),
    TibberPricesSensorDescription(
        key="current_interval_price_rank_today_tomorrow",
        translation_key="current_interval_price_rank_today_tomorrow",
        attributes=rank_attributes("current_price"),
        icon="mdi:percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=None,  # Position metric: no statistics
        suggested_display_precision=0,
        entity_registry_enabled_default=False,  # Advanced overview use case
    ),
    # ----------------------------------------------------------------
    # Next interval rank sensors
    # ----------------------------------------------------------------
    TibberPricesSensorDescription(
        key="next_interval_price_rank_today",
        translation_key="next_interval_price_rank_today",
        attributes=rank_attributes("next_price"),
        icon="mdi:percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=None,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    TibberPricesSensorDescription(
        key="next_interval_price_rank_today_tomorrow",
        translation_key="next_interval_price_rank_today_tomorrow",
        attributes=rank_attributes("next_price"),
        icon="mdi:percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=None,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    # ----------------------------------------------------------------
    # Previous interval rank sensors
    # ----------------------------------------------------------------
    TibberPricesSensorDescription(
        key="previous_interval_price_rank_today",
        translation_key="previous_interval_price_rank_today",
        attributes=rank_attributes("previous_price"),
        icon="mdi:percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=None,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    TibberPricesSensorDescription(
        key="previous_interval_price_rank_today_tomorrow",
        translation_key="previous_interval_price_rank_today_tomorrow",
        attributes=rank_attributes("previous_price"),
        icon="mdi:percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=None,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    # ----------------------------------------------------------------
    # Rolling-hour rank sensors (rank of 1h rolling average)
    # ----------------------------------------------------------------
    TibberPricesSensorDescription(
        key="current_hour_price_rank_today",
        translation_key="current_hour_price_rank_today",
        attributes=rank_attributes("current_hour_avg_price"),
        icon="mdi:percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=None,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    TibberPricesSensorDescription(
        key="current_hour_price_rank_today_tomorrow",
        translation_key="current_hour_price_rank_today_tomorrow",
        attributes=rank_attributes("current_hour_avg_price"),
        icon="mdi:percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=None,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    TibberPricesSensorDescription(
        key="next_hour_price_rank_today",
        translation_key="next_hour_price_rank_today",
        attributes=rank_attributes("next_hour_avg_price"),
        icon="mdi:percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=None,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    TibberPricesSensorDescription(
        key="next_hour_price_rank_today_tomorrow",
        translation_key="next_hour_price_rank_today_tomorrow",
        attributes=rank_attributes("next_hour_avg_price"),
        icon="mdi:percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=None,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
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
    TibberPricesSensorDescription(
        key="best_price_end_time",
        translation_key="best_price_end_time",
        attributes=PERIOD_TIMING,
        icon="mdi:clock-end",
        device_class=SensorDeviceClass.TIMESTAMP,
        state_class=None,  # Timestamps: no statistics
    ),
    TibberPricesSensorDescription(
        key="best_price_period_duration",
        translation_key="best_price_period_duration",
        attributes=PERIOD_TIMING,
        icon="mdi:timer",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        state_class=None,  # Duration not needed in long-term statistics
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    TibberPricesSensorDescription(
        key="best_price_remaining_minutes",
        translation_key="best_price_remaining_minutes",
        attributes=PERIOD_TIMING,
        icon="mdi:timer-sand",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        state_class=None,  # Countdown timers excluded from statistics
        suggested_display_precision=2,
    ),
    TibberPricesSensorDescription(
        key="best_price_progress",
        translation_key="best_price_progress",
        attributes=PERIOD_TIMING,
        icon="mdi:percent",  # Dynamic: mdi:percent-0 to mdi:percent-100
        native_unit_of_measurement=PERCENTAGE,
        state_class=None,  # Progress counter: no statistics
        suggested_display_precision=0,
    ),
    TibberPricesSensorDescription(
        key="best_price_next_start_time",
        translation_key="best_price_next_start_time",
        attributes=PERIOD_TIMING,
        icon="mdi:clock-start",
        device_class=SensorDeviceClass.TIMESTAMP,
        state_class=None,  # Timestamps: no statistics
    ),
    TibberPricesSensorDescription(
        key="best_price_next_in_minutes",
        translation_key="best_price_next_in_minutes",
        attributes=PERIOD_TIMING,
        icon="mdi:timer-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        state_class=None,  # Next-start timers excluded from statistics
        suggested_display_precision=2,
    ),
)

PEAK_PRICE_TIMING_SENSORS = (
    TibberPricesSensorDescription(
        key="peak_price_end_time",
        translation_key="peak_price_end_time",
        attributes=PERIOD_TIMING,
        icon="mdi:clock-end",
        device_class=SensorDeviceClass.TIMESTAMP,
        state_class=None,  # Timestamps: no statistics
    ),
    TibberPricesSensorDescription(
        key="peak_price_period_duration",
        translation_key="peak_price_period_duration",
        attributes=PERIOD_TIMING,
        icon="mdi:timer",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        state_class=None,  # Duration not needed in long-term statistics
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    TibberPricesSensorDescription(
        key="peak_price_remaining_minutes",
        translation_key="peak_price_remaining_minutes",
        attributes=PERIOD_TIMING,
        icon="mdi:timer-sand",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        state_class=None,  # Countdown timers excluded from statistics
        suggested_display_precision=2,
    ),
    TibberPricesSensorDescription(
        key="peak_price_progress",
        translation_key="peak_price_progress",
        attributes=PERIOD_TIMING,
        icon="mdi:percent",  # Dynamic: mdi:percent-0 to mdi:percent-100
        native_unit_of_measurement=PERCENTAGE,
        state_class=None,  # Progress counter: no statistics
        suggested_display_precision=0,
    ),
    TibberPricesSensorDescription(
        key="peak_price_next_start_time",
        translation_key="peak_price_next_start_time",
        attributes=PERIOD_TIMING,
        icon="mdi:clock-start",
        device_class=SensorDeviceClass.TIMESTAMP,
        state_class=None,  # Timestamps: no statistics
    ),
    TibberPricesSensorDescription(
        key="peak_price_next_in_minutes",
        translation_key="peak_price_next_in_minutes",
        attributes=PERIOD_TIMING,
        icon="mdi:timer-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        state_class=None,  # Next-start timers excluded from statistics
        suggested_display_precision=2,
    ),
)

# 8. DAY PATTERN SENSORS (price shape classification per calendar day)
# ----------------------------------------------------------------------------

DAY_PATTERN_SENSORS = (
    TibberPricesSensorDescription(
        key="day_pattern_yesterday",
        translation_key="day_pattern_yesterday",
        attributes=DAY_PATTERN,
        icon="mdi:chart-bell-curve",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "valley",
            "peak",
            "double_dip",
            "duck_curve",
            "flat",
            "rising",
            "falling",
            "mixed",
        ],
        state_class=None,
        entity_registry_enabled_default=False,
    ),
    TibberPricesSensorDescription(
        key="day_pattern_today",
        translation_key="day_pattern_today",
        attributes=DAY_PATTERN,
        icon="mdi:chart-bell-curve",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "valley",
            "peak",
            "double_dip",
            "duck_curve",
            "flat",
            "rising",
            "falling",
            "mixed",
        ],
        state_class=None,
        entity_registry_enabled_default=True,
    ),
    TibberPricesSensorDescription(
        key="day_pattern_tomorrow",
        translation_key="day_pattern_tomorrow",
        attributes=DAY_PATTERN,
        icon="mdi:chart-bell-curve",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "valley",
            "peak",
            "double_dip",
            "duck_curve",
            "flat",
            "rising",
            "falling",
            "mixed",
        ],
        state_class=None,
        entity_registry_enabled_default=False,
    ),
)

# 8b. PRICE PHASE SENSORS (current/next intra-day price phase classification)
# ----------------------------------------------------------------------------

PRICE_PHASE_SENSORS = (
    TibberPricesSensorDescription(
        key="current_price_phase",
        translation_key="current_price_phase",
        attributes=PRICE_PHASE,
        icon="mdi:chart-timeline-variant",
        device_class=SensorDeviceClass.ENUM,
        options=["rising", "falling", "flat"],
        state_class=None,
        entity_registry_enabled_default=True,
    ),
    TibberPricesSensorDescription(
        key="next_price_phase",
        translation_key="next_price_phase",
        attributes=PRICE_PHASE,
        icon="mdi:chart-timeline-variant",
        device_class=SensorDeviceClass.ENUM,
        options=["rising", "falling", "flat"],
        state_class=None,
        entity_registry_enabled_default=True,
    ),
)

# 8c. PRICE PHASE TIMING SENSORS (current phase duration/progress + next-phase-by-type)
# ----------------------------------------------------------------------------
#
# When current phase is active:
#   - end_time:           Timestamp when current phase ends
#   - remaining_minutes:  Minutes until current phase ends
#   - duration:           Total length of current phase (disabled by default)
#   - progress:           Percentage of current phase completed (disabled by default)
#
# Next occurrence of a specific phase type (after current segment, today or tomorrow):
#   - next_*_phase_start_time:  Timestamp when next rising/falling/flat phase starts
#   - next_*_phase_in_minutes:  Minutes until that phase starts
#
# All return None/Unknown when no segment data is available.

PRICE_PHASE_TIMING_SENSORS = (
    TibberPricesSensorDescription(
        key="current_price_phase_end_time",
        translation_key="current_price_phase_end_time",
        attributes=PHASE_TIMING,
        icon="mdi:clock-end",
        device_class=SensorDeviceClass.TIMESTAMP,
        state_class=None,  # Timestamps: no statistics
    ),
    TibberPricesSensorDescription(
        key="current_price_phase_remaining_minutes",
        translation_key="current_price_phase_remaining_minutes",
        attributes=PHASE_TIMING,
        icon="mdi:timer-sand",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        state_class=None,  # Countdown timers excluded from statistics
        suggested_display_precision=2,
    ),
    TibberPricesSensorDescription(
        key="current_price_phase_duration",
        translation_key="current_price_phase_duration",
        attributes=PHASE_TIMING,
        icon="mdi:timer",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        state_class=None,  # Duration not needed in long-term statistics
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    TibberPricesSensorDescription(
        key="current_price_phase_progress",
        translation_key="current_price_phase_progress",
        attributes=PHASE_TIMING,
        icon="mdi:percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=None,  # Progress counter: no statistics
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
    # Next occurrence of each phase type (across remaining today + tomorrow)
    TibberPricesSensorDescription(
        key="next_rising_phase_start_time",
        translation_key="next_rising_phase_start_time",
        attributes=PHASE_TIMING,
        icon="mdi:trending-up",
        device_class=SensorDeviceClass.TIMESTAMP,
        state_class=None,
        entity_registry_enabled_default=False,
    ),
    TibberPricesSensorDescription(
        key="next_falling_phase_start_time",
        translation_key="next_falling_phase_start_time",
        attributes=PHASE_TIMING,
        icon="mdi:trending-down",
        device_class=SensorDeviceClass.TIMESTAMP,
        state_class=None,
        entity_registry_enabled_default=False,
    ),
    TibberPricesSensorDescription(
        key="next_flat_phase_start_time",
        translation_key="next_flat_phase_start_time",
        attributes=PHASE_TIMING,
        icon="mdi:trending-neutral",
        device_class=SensorDeviceClass.TIMESTAMP,
        state_class=None,
        entity_registry_enabled_default=False,
    ),
    TibberPricesSensorDescription(
        key="next_rising_phase_in_minutes",
        translation_key="next_rising_phase_in_minutes",
        attributes=PHASE_TIMING,
        icon="mdi:timer-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        state_class=None,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    TibberPricesSensorDescription(
        key="next_falling_phase_in_minutes",
        translation_key="next_falling_phase_in_minutes",
        attributes=PHASE_TIMING,
        icon="mdi:timer-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        state_class=None,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    TibberPricesSensorDescription(
        key="next_flat_phase_in_minutes",
        translation_key="next_flat_phase_in_minutes",
        attributes=PHASE_TIMING,
        icon="mdi:timer-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        state_class=None,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
)

# Diagnostic sensors that are built from prices and therefore wait for the subscription to start
PRICE_DEPENDENT_DIAGNOSTIC_KEYS = frozenset({"chart_data_export", "chart_metadata"})

# 9. DIAGNOSTIC SENSORS (data availability and metadata)
# ----------------------------------------------------------------------------

DIAGNOSTIC_SENSORS = (
    TibberPricesSensorDescription(
        key="data_lifecycle_status",
        translation_key="data_lifecycle_status",
        attributes=DATA_LIFECYCLE,
        icon="mdi:database-sync",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "cached",
            "fresh",
            "refreshing",
            "searching_tomorrow",
            "turnover_pending",
            "error",
            "awaiting_subscription",
            "subscription_ended",
        ],
        state_class=None,  # Status value: no statistics
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=True,  # Critical for debugging
    ),
    # Home metadata from user data
    TibberPricesSensorDescription(
        key="home_type",
        translation_key="home_type",
        icon="mdi:home-variant",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=["apartment", "rowhouse", "house", "cottage"],
        entity_registry_enabled_default=False,
    ),
    TibberPricesSensorDescription(
        key="home_size",
        translation_key="home_size",
        icon="mdi:ruler-square",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfArea.SQUARE_METERS,
        state_class=None,  # Static user metadata: no statistics useful
        entity_registry_enabled_default=False,
        suggested_display_precision=0,
    ),
    TibberPricesSensorDescription(
        key="main_fuse_size",
        translation_key="main_fuse_size",
        icon="mdi:fuse",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=None,  # Static user metadata: no statistics useful
        entity_registry_enabled_default=False,
        suggested_display_precision=0,
    ),
    TibberPricesSensorDescription(
        key="number_of_residents",
        translation_key="number_of_residents",
        icon="mdi:account-group",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=None,  # Static user metadata: no statistics useful
        entity_registry_enabled_default=False,
        suggested_display_precision=0,
    ),
    TibberPricesSensorDescription(
        key="primary_heating_source",
        translation_key="primary_heating_source",
        icon="mdi:heating-coil",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=[
            "air2air_heatpump",
            "air2water_heatpump",
            "boiler",
            "central_heating",
            "district_heating",
            "district_heating",
            "district",
            "electric_boiler",
            "electricity",
            "floor",
            "gas",
            "ground_heatpump",
            "ground",
            "oil",
            "other",
            "waste",
        ],
        entity_registry_enabled_default=False,
    ),
    # Metering point data
    TibberPricesSensorDescription(
        key="grid_company",
        translation_key="grid_company",
        icon="mdi:transmission-tower",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TibberPricesSensorDescription(
        key="grid_area_code",
        translation_key="grid_area_code",
        icon="mdi:map-marker",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TibberPricesSensorDescription(
        key="price_area_code",
        translation_key="price_area_code",
        icon="mdi:currency-eur",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TibberPricesSensorDescription(
        key="consumption_ean",
        translation_key="consumption_ean",
        icon="mdi:barcode",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TibberPricesSensorDescription(
        key="production_ean",
        translation_key="production_ean",
        icon="mdi:solar-power",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TibberPricesSensorDescription(
        key="energy_tax_type",
        translation_key="energy_tax_type",
        icon="mdi:cash",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TibberPricesSensorDescription(
        key="vat_type",
        translation_key="vat_type",
        icon="mdi:percent",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TibberPricesSensorDescription(
        key="estimated_annual_consumption",
        translation_key="estimated_annual_consumption",
        icon="mdi:lightning-bolt",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=None,  # Static Tibber estimate, not an actual accumulating counter
        suggested_display_precision=0,
    ),
    # Subscription data
    TibberPricesSensorDescription(
        key="subscription_status",
        translation_key="subscription_status",
        icon="mdi:file-document-check",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=["running", "ended", "pending", "awaiting_market", "unknown"],
        entity_registry_enabled_default=False,
    ),
    TibberPricesSensorDescription(
        key="chart_data_export",
        translation_key="chart_data_export",
        attributes=CHART_DATA_EXPORT,
        open_attributes=True,
        icon="mdi:database-export",
        device_class=SensorDeviceClass.ENUM,
        options=["pending", "ready", "error"],
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,  # Opt-in
    ),
    TibberPricesSensorDescription(
        key="chart_metadata",
        translation_key="chart_metadata",
        attributes=CHART_METADATA,
        icon="mdi:chart-box-outline",
        device_class=SensorDeviceClass.ENUM,
        options=["pending", "ready", "error"],
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=True,  # Critical for chart features
    ),
)

# 10. TIME-TRAVEL SENSORS (what a device is actually showing)
# ----------------------------------------------------------------------------
# Present on every device, live or historical: on a live device they report
# "live" / None, which is exactly the answer someone comparing two devices in a
# chart needs. All opt-in - they are configuration echoes, not measurements.

TIME_TRAVEL_SENSORS = (
    TibberPricesSensorDescription(
        key="entry_mode",
        translation_key="entry_mode",
        icon="mdi:clock-outline",
        device_class=SensorDeviceClass.ENUM,
        options=["live", "time_travel_days", "time_travel_yearly"],
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TibberPricesSensorDescription(
        key="time_travel_reference_time",
        translation_key="time_travel_reference_time",
        icon="mdi:calendar-clock",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TibberPricesSensorDescription(
        key="time_travel_days_offset",
        translation_key="time_travel_days_offset",
        icon="mdi:calendar-minus",
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=None,  # Configuration echo: no statistics
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TibberPricesSensorDescription(
        key="time_travel_years_offset",
        translation_key="time_travel_years_offset",
        icon="mdi:calendar-minus",
        state_class=None,  # Configuration echo: no statistics
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TibberPricesSensorDescription(
        key="time_travel_time_offset",
        translation_key="time_travel_time_offset",
        icon="mdi:clock-minus",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TibberPricesSensorDescription(
        key="headless_mode",
        translation_key="headless_mode",
        icon="mdi:eye-off-outline",
        device_class=SensorDeviceClass.ENUM,
        options=["on", "off"],
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
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
    *FUTURE_MEAN_SENSORS,
    *FUTURE_TREND_SENSORS,
    *PRICE_TRAJECTORY_SENSORS,
    *VOLATILITY_SENSORS,
    *PERCENTILE_RANK_SENSORS,
    *BEST_PRICE_TIMING_SENSORS,
    *PEAK_PRICE_TIMING_SENSORS,
    *DAY_PATTERN_SENSORS,
    *PRICE_PHASE_SENSORS,
    *PRICE_PHASE_TIMING_SENSORS,
    *DIAGNOSTIC_SENSORS,
    *TIME_TRAVEL_SENSORS,
)
