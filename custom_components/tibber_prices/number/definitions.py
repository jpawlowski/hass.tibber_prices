"""
Number entity definitions for Tibber Prices configuration overrides.

These number entities allow runtime configuration of Best Price and Peak Price
period calculation settings. They are disabled by default - users can enable
individual entities to override specific settings at runtime.

When enabled, the entity value takes precedence over the options flow setting.
When disabled (default), the options flow setting is used.
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import PERCENTAGE, EntityCategory


@dataclass(frozen=True, kw_only=True)
class TibberPricesNumberEntityDescription(NumberEntityDescription):
    """Describes a Tibber Prices number entity for config overrides."""

    # The config key this entity overrides (matches CONF_* constants)
    config_key: str
    # The section in options where this setting is stored (e.g., "flexibility_settings")
    config_section: str
    # Whether this is for best_price (False) or peak_price (True)
    is_peak_price: bool = False
    # Default value from const.py
    default_value: float | int = 0


# ============================================================================
# BEST PRICE PERIOD CONFIGURATION OVERRIDES
# ============================================================================

BEST_PRICE_NUMBER_ENTITIES = (
    TibberPricesNumberEntityDescription(
        key="best_price_flex_override",
        translation_key="best_price_flex_override",
        name="Best Price: Flexibility",
        icon="mdi:arrow-down-bold-circle",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_min_value=0,
        native_max_value=50,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
        config_key="best_price_flex",
        config_section="flexibility_settings",
        is_peak_price=False,
        default_value=15,  # DEFAULT_BEST_PRICE_FLEX
    ),
    TibberPricesNumberEntityDescription(
        key="best_price_min_distance_override",
        translation_key="best_price_min_distance_override",
        name="Best Price: Minimum Distance",
        icon="mdi:arrow-down-bold-circle",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_min_value=-50,
        native_max_value=0,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
        config_key="best_price_min_distance_from_avg",
        config_section="flexibility_settings",
        is_peak_price=False,
        default_value=-5,  # DEFAULT_BEST_PRICE_MIN_DISTANCE_FROM_AVG
    ),
    TibberPricesNumberEntityDescription(
        key="best_price_min_period_length_override",
        translation_key="best_price_min_period_length_override",
        name="Best Price: Minimum Period Length",
        icon="mdi:arrow-down-bold-circle",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_min_value=15,
        native_max_value=180,
        native_step=15,
        native_unit_of_measurement="min",
        mode=NumberMode.SLIDER,
        config_key="best_price_min_period_length",
        config_section="period_settings",
        is_peak_price=False,
        default_value=60,  # DEFAULT_BEST_PRICE_MIN_PERIOD_LENGTH
    ),
    TibberPricesNumberEntityDescription(
        key="best_price_min_periods_override",
        translation_key="best_price_min_periods_override",
        name="Best Price: Minimum Periods",
        icon="mdi:arrow-down-bold-circle",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_min_value=1,
        native_max_value=10,
        native_step=1,
        mode=NumberMode.SLIDER,
        config_key="min_periods_best",
        config_section="relaxation_and_target_periods",
        is_peak_price=False,
        default_value=2,  # DEFAULT_MIN_PERIODS_BEST
    ),
    TibberPricesNumberEntityDescription(
        key="best_price_relaxation_attempts_override",
        translation_key="best_price_relaxation_attempts_override",
        name="Best Price: Relaxation Attempts",
        icon="mdi:arrow-down-bold-circle",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_min_value=1,
        native_max_value=12,
        native_step=1,
        mode=NumberMode.SLIDER,
        config_key="relaxation_attempts_best",
        config_section="relaxation_and_target_periods",
        is_peak_price=False,
        default_value=11,  # DEFAULT_RELAXATION_ATTEMPTS_BEST
    ),
    TibberPricesNumberEntityDescription(
        key="best_price_gap_count_override",
        translation_key="best_price_gap_count_override",
        name="Best Price: Gap Tolerance",
        icon="mdi:arrow-down-bold-circle",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_min_value=0,
        native_max_value=8,
        native_step=1,
        mode=NumberMode.SLIDER,
        config_key="best_price_max_level_gap_count",
        config_section="period_settings",
        is_peak_price=False,
        default_value=1,  # DEFAULT_BEST_PRICE_MAX_LEVEL_GAP_COUNT
    ),
)

# ============================================================================
# PEAK PRICE PERIOD CONFIGURATION OVERRIDES
# ============================================================================

PEAK_PRICE_NUMBER_ENTITIES = (
    TibberPricesNumberEntityDescription(
        key="peak_price_flex_override",
        translation_key="peak_price_flex_override",
        name="Peak Price: Flexibility",
        icon="mdi:arrow-up-bold-circle",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_min_value=-50,
        native_max_value=0,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
        config_key="peak_price_flex",
        config_section="flexibility_settings",
        is_peak_price=True,
        default_value=-20,  # DEFAULT_PEAK_PRICE_FLEX
    ),
    TibberPricesNumberEntityDescription(
        key="peak_price_min_distance_override",
        translation_key="peak_price_min_distance_override",
        name="Peak Price: Minimum Distance",
        icon="mdi:arrow-up-bold-circle",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_min_value=0,
        native_max_value=50,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
        config_key="peak_price_min_distance_from_avg",
        config_section="flexibility_settings",
        is_peak_price=True,
        default_value=5,  # DEFAULT_PEAK_PRICE_MIN_DISTANCE_FROM_AVG
    ),
    TibberPricesNumberEntityDescription(
        key="peak_price_min_period_length_override",
        translation_key="peak_price_min_period_length_override",
        name="Peak Price: Minimum Period Length",
        icon="mdi:arrow-up-bold-circle",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_min_value=15,
        native_max_value=180,
        native_step=15,
        native_unit_of_measurement="min",
        mode=NumberMode.SLIDER,
        config_key="peak_price_min_period_length",
        config_section="period_settings",
        is_peak_price=True,
        default_value=30,  # DEFAULT_PEAK_PRICE_MIN_PERIOD_LENGTH
    ),
    TibberPricesNumberEntityDescription(
        key="peak_price_min_periods_override",
        translation_key="peak_price_min_periods_override",
        name="Peak Price: Minimum Periods",
        icon="mdi:arrow-up-bold-circle",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_min_value=1,
        native_max_value=10,
        native_step=1,
        mode=NumberMode.SLIDER,
        config_key="min_periods_peak",
        config_section="relaxation_and_target_periods",
        is_peak_price=True,
        default_value=2,  # DEFAULT_MIN_PERIODS_PEAK
    ),
    TibberPricesNumberEntityDescription(
        key="peak_price_relaxation_attempts_override",
        translation_key="peak_price_relaxation_attempts_override",
        name="Peak Price: Relaxation Attempts",
        icon="mdi:arrow-up-bold-circle",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_min_value=1,
        native_max_value=12,
        native_step=1,
        mode=NumberMode.SLIDER,
        config_key="relaxation_attempts_peak",
        config_section="relaxation_and_target_periods",
        is_peak_price=True,
        default_value=11,  # DEFAULT_RELAXATION_ATTEMPTS_PEAK
    ),
    TibberPricesNumberEntityDescription(
        key="peak_price_gap_count_override",
        translation_key="peak_price_gap_count_override",
        name="Peak Price: Gap Tolerance",
        icon="mdi:arrow-up-bold-circle",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_min_value=0,
        native_max_value=8,
        native_step=1,
        mode=NumberMode.SLIDER,
        config_key="peak_price_max_level_gap_count",
        config_section="period_settings",
        is_peak_price=True,
        default_value=1,  # DEFAULT_PEAK_PRICE_MAX_LEVEL_GAP_COUNT
    ),
)

# All number entity descriptions combined
NUMBER_ENTITY_DESCRIPTIONS = BEST_PRICE_NUMBER_ENTITIES + PEAK_PRICE_NUMBER_ENTITIES
