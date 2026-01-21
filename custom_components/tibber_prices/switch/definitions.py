"""
Switch entity definitions for Tibber Prices configuration overrides.

These switch entities allow runtime configuration of boolean settings
for Best Price and Peak Price period calculations.

When enabled, the entity value takes precedence over the options flow setting.
When disabled (default), the options flow setting is used.
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.const import EntityCategory


@dataclass(frozen=True, kw_only=True)
class TibberPricesSwitchEntityDescription(SwitchEntityDescription):
    """Describes a Tibber Prices switch entity for config overrides."""

    # The config key this entity overrides (matches CONF_* constants)
    config_key: str
    # The section in options where this setting is stored
    config_section: str
    # Whether this is for best_price (False) or peak_price (True)
    is_peak_price: bool = False
    # Default value from const.py
    default_value: bool = True


# ============================================================================
# BEST PRICE PERIOD CONFIGURATION OVERRIDES (Boolean)
# ============================================================================

BEST_PRICE_SWITCH_ENTITIES = (
    SwitchEntityDescription(
        key="best_price_enable_relaxation_override",
        translation_key="best_price_enable_relaxation_override",
        name="Best Price: Achieve Minimum Count",
        icon="mdi:arrow-down-bold-circle",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
)

# Custom descriptions with extra fields
BEST_PRICE_SWITCH_ENTITY_DESCRIPTIONS = (
    TibberPricesSwitchEntityDescription(
        key="best_price_enable_relaxation_override",
        translation_key="best_price_enable_relaxation_override",
        name="Best Price: Achieve Minimum Count",
        icon="mdi:arrow-down-bold-circle",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        config_key="enable_min_periods_best",
        config_section="relaxation_and_target_periods",
        is_peak_price=False,
        default_value=True,  # DEFAULT_ENABLE_MIN_PERIODS_BEST
    ),
)

# ============================================================================
# PEAK PRICE PERIOD CONFIGURATION OVERRIDES (Boolean)
# ============================================================================

PEAK_PRICE_SWITCH_ENTITY_DESCRIPTIONS = (
    TibberPricesSwitchEntityDescription(
        key="peak_price_enable_relaxation_override",
        translation_key="peak_price_enable_relaxation_override",
        name="Peak Price: Achieve Minimum Count",
        icon="mdi:arrow-up-bold-circle",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        config_key="enable_min_periods_peak",
        config_section="relaxation_and_target_periods",
        is_peak_price=True,
        default_value=True,  # DEFAULT_ENABLE_MIN_PERIODS_PEAK
    ),
)

# All switch entity descriptions combined
SWITCH_ENTITY_DESCRIPTIONS = BEST_PRICE_SWITCH_ENTITY_DESCRIPTIONS + PEAK_PRICE_SWITCH_ENTITY_DESCRIPTIONS
