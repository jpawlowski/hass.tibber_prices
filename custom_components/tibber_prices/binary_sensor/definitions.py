"""Binary sensor entity descriptions for tibber_prices."""

from dataclasses import dataclass

from custom_components.tibber_prices.utils.attribute_specs import TibberPricesAttribute, attribute
from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntityDescription
from homeassistant.const import EntityCategory


@dataclass(frozen=True, kw_only=True)
class TibberPricesBinarySensorDescription(BinarySensorEntityDescription):
    """A binary sensor description that also declares the attributes the sensor exposes (see attribute_specs.py)."""

    attributes: tuple[TibberPricesAttribute, ...] = ()


# Best and peak price period: the current period, the day around it, and how the periods were found
PRICE_PERIOD = (
    attribute("intervals_available", history=True),
    attribute("data_status"),
    attribute("period_position", history=True),
    attribute("period_count_total"),
    attribute("period_count_remaining"),
    attribute("start", history=True),
    attribute("end", history=True),
    attribute("periods"),
    attribute("duration_minutes", history=True),
    attribute("level", history=True),
    attribute("rating_level", history=True),
    attribute("rating_difference_percent"),
    attribute("price_mean", history=True),
    attribute("price_median", history=True),
    attribute("price_min", history=True),
    attribute("price_max", history=True),
    attribute("price_spread"),
    attribute("price_coefficient_variation_percent", history=True),
    attribute("volatility"),
    attribute("day_volatility_percent"),
    attribute("period_price_diff_from_daily_min"),
    attribute("period_price_diff_from_daily_min_percent"),
    attribute("period_price_diff_from_daily_max"),
    attribute("period_price_diff_from_daily_max_percent"),
    attribute("day_price_min"),
    attribute("day_price_max"),
    attribute("day_price_span"),
    attribute("icon_color"),
    attribute("period_interval_count", history=True),
    attribute("period_count_today", history=True),
    attribute("period_count_tomorrow", history=True),
    attribute("relaxation_active", history=True),
    attribute("relaxation_level"),
    attribute("relaxation_threshold_original_percent"),
    attribute("relaxation_threshold_applied_percent"),
    attribute("min_periods_configured"),
    attribute("flat_days_detected"),
    attribute("relaxation_incomplete"),
)
# The price phases only say when the current phase starts and ends, which the price data already tells
PHASE_BOUNDS = (attribute("start"), attribute("end"))
CONNECTION = (
    attribute("using_cached_data", history=True),
    attribute("last_successful_update"),
    attribute("subscription_phase", history=True),
)
TOMORROW_DATA = (attribute("intervals_available", history=True), attribute("data_status"))

# Period lookahead removed - icons show "waiting" state if ANY future periods exist
# No artificial time limit - show all periods until midnight

# Diagnostic binary sensors that are built from prices and therefore wait for the subscription to start
PRICE_DEPENDENT_DIAGNOSTIC_KEYS = frozenset({"tomorrow_data_available"})

ENTITY_DESCRIPTIONS = (
    TibberPricesBinarySensorDescription(
        key="peak_price_period",
        translation_key="peak_price_period",
        attributes=PRICE_PERIOD,
        icon="mdi:clock-alert",
    ),
    TibberPricesBinarySensorDescription(
        key="best_price_period",
        translation_key="best_price_period",
        attributes=PRICE_PERIOD,
        icon="mdi:clock-check",
    ),
    # Price phase binary sensors — ON when current intra-day phase matches the type
    TibberPricesBinarySensorDescription(
        key="in_rising_price_phase",
        translation_key="in_rising_price_phase",
        attributes=PHASE_BOUNDS,
        icon="mdi:trending-up",
    ),
    TibberPricesBinarySensorDescription(
        key="in_falling_price_phase",
        translation_key="in_falling_price_phase",
        attributes=PHASE_BOUNDS,
        icon="mdi:trending-down",
    ),
    TibberPricesBinarySensorDescription(
        key="in_flat_price_phase",
        translation_key="in_flat_price_phase",
        attributes=PHASE_BOUNDS,
        icon="mdi:trending-neutral",
    ),
    TibberPricesBinarySensorDescription(
        key="connection",
        translation_key="connection",
        attributes=CONNECTION,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    TibberPricesBinarySensorDescription(
        key="tomorrow_data_available",
        translation_key="tomorrow_data_available",
        attributes=TOMORROW_DATA,
        icon="mdi:calendar-check",
        device_class=None,  # No specific device_class = shows generic "On/Off"
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=True,  # Critical for automations
    ),
    TibberPricesBinarySensorDescription(
        key="has_ventilation_system",
        translation_key="has_ventilation_system",
        icon="mdi:air-filter",
        device_class=None,  # No specific device_class = shows generic "On/Off"
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    TibberPricesBinarySensorDescription(
        key="realtime_consumption_enabled",
        translation_key="realtime_consumption_enabled",
        icon="mdi:speedometer",
        device_class=None,  # No specific device_class = shows generic "On/Off"
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)
