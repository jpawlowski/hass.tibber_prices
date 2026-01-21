"""Schema definitions for tibber_prices config flow."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

import voluptuous as vol

from custom_components.tibber_prices.const import (
    BEST_PRICE_MAX_LEVEL_OPTIONS,
    CONF_AVERAGE_SENSOR_DISPLAY,
    CONF_BEST_PRICE_FLEX,
    CONF_BEST_PRICE_MAX_LEVEL,
    CONF_BEST_PRICE_MAX_LEVEL_GAP_COUNT,
    CONF_BEST_PRICE_MIN_DISTANCE_FROM_AVG,
    CONF_BEST_PRICE_MIN_PERIOD_LENGTH,
    CONF_CURRENCY_DISPLAY_MODE,
    CONF_ENABLE_MIN_PERIODS_BEST,
    CONF_ENABLE_MIN_PERIODS_PEAK,
    CONF_EXTENDED_DESCRIPTIONS,
    CONF_MIN_PERIODS_BEST,
    CONF_MIN_PERIODS_PEAK,
    CONF_PEAK_PRICE_FLEX,
    CONF_PEAK_PRICE_MAX_LEVEL_GAP_COUNT,
    CONF_PEAK_PRICE_MIN_DISTANCE_FROM_AVG,
    CONF_PEAK_PRICE_MIN_LEVEL,
    CONF_PEAK_PRICE_MIN_PERIOD_LENGTH,
    CONF_PRICE_LEVEL_GAP_TOLERANCE,
    CONF_PRICE_RATING_GAP_TOLERANCE,
    CONF_PRICE_RATING_HYSTERESIS,
    CONF_PRICE_RATING_THRESHOLD_HIGH,
    CONF_PRICE_RATING_THRESHOLD_LOW,
    CONF_PRICE_TREND_THRESHOLD_FALLING,
    CONF_PRICE_TREND_THRESHOLD_RISING,
    CONF_PRICE_TREND_THRESHOLD_STRONGLY_FALLING,
    CONF_PRICE_TREND_THRESHOLD_STRONGLY_RISING,
    CONF_RELAXATION_ATTEMPTS_BEST,
    CONF_RELAXATION_ATTEMPTS_PEAK,
    CONF_VIRTUAL_TIME_OFFSET_DAYS,
    CONF_VIRTUAL_TIME_OFFSET_HOURS,
    CONF_VIRTUAL_TIME_OFFSET_MINUTES,
    CONF_VOLATILITY_THRESHOLD_HIGH,
    CONF_VOLATILITY_THRESHOLD_MODERATE,
    CONF_VOLATILITY_THRESHOLD_VERY_HIGH,
    DEFAULT_AVERAGE_SENSOR_DISPLAY,
    DEFAULT_BEST_PRICE_FLEX,
    DEFAULT_BEST_PRICE_MAX_LEVEL,
    DEFAULT_BEST_PRICE_MAX_LEVEL_GAP_COUNT,
    DEFAULT_BEST_PRICE_MIN_DISTANCE_FROM_AVG,
    DEFAULT_BEST_PRICE_MIN_PERIOD_LENGTH,
    DEFAULT_ENABLE_MIN_PERIODS_BEST,
    DEFAULT_ENABLE_MIN_PERIODS_PEAK,
    DEFAULT_EXTENDED_DESCRIPTIONS,
    DEFAULT_MIN_PERIODS_BEST,
    DEFAULT_MIN_PERIODS_PEAK,
    DEFAULT_PEAK_PRICE_FLEX,
    DEFAULT_PEAK_PRICE_MAX_LEVEL_GAP_COUNT,
    DEFAULT_PEAK_PRICE_MIN_DISTANCE_FROM_AVG,
    DEFAULT_PEAK_PRICE_MIN_LEVEL,
    DEFAULT_PEAK_PRICE_MIN_PERIOD_LENGTH,
    DEFAULT_PRICE_LEVEL_GAP_TOLERANCE,
    DEFAULT_PRICE_RATING_GAP_TOLERANCE,
    DEFAULT_PRICE_RATING_HYSTERESIS,
    DEFAULT_PRICE_RATING_THRESHOLD_HIGH,
    DEFAULT_PRICE_RATING_THRESHOLD_LOW,
    DEFAULT_PRICE_TREND_THRESHOLD_FALLING,
    DEFAULT_PRICE_TREND_THRESHOLD_RISING,
    DEFAULT_PRICE_TREND_THRESHOLD_STRONGLY_FALLING,
    DEFAULT_PRICE_TREND_THRESHOLD_STRONGLY_RISING,
    DEFAULT_RELAXATION_ATTEMPTS_BEST,
    DEFAULT_RELAXATION_ATTEMPTS_PEAK,
    DEFAULT_VIRTUAL_TIME_OFFSET_DAYS,
    DEFAULT_VIRTUAL_TIME_OFFSET_HOURS,
    DEFAULT_VIRTUAL_TIME_OFFSET_MINUTES,
    DEFAULT_VOLATILITY_THRESHOLD_HIGH,
    DEFAULT_VOLATILITY_THRESHOLD_MODERATE,
    DEFAULT_VOLATILITY_THRESHOLD_VERY_HIGH,
    DISPLAY_MODE_BASE,
    DISPLAY_MODE_SUBUNIT,
    MAX_GAP_COUNT,
    MAX_MIN_PERIOD_LENGTH,
    MAX_MIN_PERIODS,
    MAX_PRICE_LEVEL_GAP_TOLERANCE,
    MAX_PRICE_RATING_GAP_TOLERANCE,
    MAX_PRICE_RATING_HYSTERESIS,
    MAX_PRICE_RATING_THRESHOLD_HIGH,
    MAX_PRICE_RATING_THRESHOLD_LOW,
    MAX_PRICE_TREND_FALLING,
    MAX_PRICE_TREND_RISING,
    MAX_PRICE_TREND_STRONGLY_FALLING,
    MAX_PRICE_TREND_STRONGLY_RISING,
    MAX_RELAXATION_ATTEMPTS,
    MAX_VOLATILITY_THRESHOLD_HIGH,
    MAX_VOLATILITY_THRESHOLD_MODERATE,
    MAX_VOLATILITY_THRESHOLD_VERY_HIGH,
    MIN_GAP_COUNT,
    MIN_PERIOD_LENGTH,
    MIN_PRICE_LEVEL_GAP_TOLERANCE,
    MIN_PRICE_RATING_GAP_TOLERANCE,
    MIN_PRICE_RATING_HYSTERESIS,
    MIN_PRICE_RATING_THRESHOLD_HIGH,
    MIN_PRICE_RATING_THRESHOLD_LOW,
    MIN_PRICE_TREND_FALLING,
    MIN_PRICE_TREND_RISING,
    MIN_PRICE_TREND_STRONGLY_FALLING,
    MIN_PRICE_TREND_STRONGLY_RISING,
    MIN_RELAXATION_ATTEMPTS,
    MIN_VOLATILITY_THRESHOLD_HIGH,
    MIN_VOLATILITY_THRESHOLD_MODERATE,
    MIN_VOLATILITY_THRESHOLD_VERY_HIGH,
    PEAK_PRICE_MIN_LEVEL_OPTIONS,
    get_default_currency_display,
)
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.data_entry_flow import section
from homeassistant.helpers import selector
from homeassistant.helpers.selector import (
    BooleanSelector,
    ConstantSelector,
    ConstantSelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

# Type alias for config override structure: {section: {config_key: value}}
ConfigOverrides = dict[str, dict[str, Any]]


def is_field_overridden(
    config_key: str,
    config_section: str,  # noqa: ARG001 - kept for API compatibility
    overrides: ConfigOverrides | None,
) -> bool:
    """
    Check if a config field has an active runtime override.

    Args:
        config_key: The configuration key to check (e.g., "best_price_flex")
        config_section: Unused, kept for API compatibility
        overrides: Dictionary of active overrides (with "_enabled" key)

    Returns:
        True if this field is being overridden by a config entity, False otherwise

    """
    if overrides is None:
        return False
    # Check if key is in the _enabled section (from entity registry check)
    return config_key in overrides.get("_enabled", {})


# Override translations structure from common section
# This will be loaded at runtime and passed to schema functions
OverrideTranslations = dict[str, Any]  # Type alias

# Fallback labels when translations not available
# Used only as fallback - translations should be loaded from common.override_field_labels
DEFAULT_FIELD_LABELS: dict[str, str] = {
    # Best Price
    CONF_BEST_PRICE_MIN_PERIOD_LENGTH: "Minimum Period Length",
    CONF_BEST_PRICE_MAX_LEVEL_GAP_COUNT: "Gap Tolerance",
    CONF_BEST_PRICE_FLEX: "Flexibility",
    CONF_BEST_PRICE_MIN_DISTANCE_FROM_AVG: "Minimum Distance",
    CONF_ENABLE_MIN_PERIODS_BEST: "Achieve Minimum Count",
    CONF_MIN_PERIODS_BEST: "Minimum Periods",
    CONF_RELAXATION_ATTEMPTS_BEST: "Relaxation Attempts",
    # Peak Price
    CONF_PEAK_PRICE_MIN_PERIOD_LENGTH: "Minimum Period Length",
    CONF_PEAK_PRICE_MAX_LEVEL_GAP_COUNT: "Gap Tolerance",
    CONF_PEAK_PRICE_FLEX: "Flexibility",
    CONF_PEAK_PRICE_MIN_DISTANCE_FROM_AVG: "Minimum Distance",
    CONF_ENABLE_MIN_PERIODS_PEAK: "Achieve Minimum Count",
    CONF_MIN_PERIODS_PEAK: "Minimum Periods",
    CONF_RELAXATION_ATTEMPTS_PEAK: "Relaxation Attempts",
}

# Section to config keys mapping for override detection
SECTION_CONFIG_KEYS: dict[str, dict[str, list[str]]] = {
    "best_price": {
        "period_settings": [
            CONF_BEST_PRICE_MIN_PERIOD_LENGTH,
            CONF_BEST_PRICE_MAX_LEVEL_GAP_COUNT,
        ],
        "flexibility_settings": [
            CONF_BEST_PRICE_FLEX,
            CONF_BEST_PRICE_MIN_DISTANCE_FROM_AVG,
        ],
        "relaxation_and_target_periods": [
            CONF_ENABLE_MIN_PERIODS_BEST,
            CONF_MIN_PERIODS_BEST,
            CONF_RELAXATION_ATTEMPTS_BEST,
        ],
    },
    "peak_price": {
        "period_settings": [
            CONF_PEAK_PRICE_MIN_PERIOD_LENGTH,
            CONF_PEAK_PRICE_MAX_LEVEL_GAP_COUNT,
        ],
        "flexibility_settings": [
            CONF_PEAK_PRICE_FLEX,
            CONF_PEAK_PRICE_MIN_DISTANCE_FROM_AVG,
        ],
        "relaxation_and_target_periods": [
            CONF_ENABLE_MIN_PERIODS_PEAK,
            CONF_MIN_PERIODS_PEAK,
            CONF_RELAXATION_ATTEMPTS_PEAK,
        ],
    },
}


def get_section_override_warning(
    step_id: str,
    section_id: str,
    overrides: ConfigOverrides | None,
    translations: OverrideTranslations | None = None,
) -> dict[vol.Optional, ConstantSelector] | None:
    """
    Return a warning constant selector if any fields in the section are overridden.

    Args:
        step_id: The step ID (best_price or peak_price)
        section_id: The section ID within the step
        overrides: Active runtime overrides from coordinator
        translations: Override translations from common section (optional)

    Returns:
        Dict with override warning selector if any fields overridden, None otherwise

    """
    if not overrides:
        return None

    section_keys = SECTION_CONFIG_KEYS.get(step_id, {}).get(section_id, [])
    overridden_fields = []

    for config_key in section_keys:
        if is_field_overridden(config_key, section_id, overrides):
            # Try to get translated label from flat keys, fallback to DEFAULT_FIELD_LABELS
            translation_key = f"override_field_label_{config_key}"
            label = (translations.get(translation_key) if translations else None) or DEFAULT_FIELD_LABELS.get(
                config_key, config_key
            )
            overridden_fields.append(label)

    if not overridden_fields:
        return None

    # Get translated "and" connector or use fallback
    and_connector = " and "
    if translations and "override_warning_and" in translations:
        and_connector = f" {translations['override_warning_and']} "

    # Build warning message with list of overridden fields
    if len(overridden_fields) == 1:
        fields_text = overridden_fields[0]
    else:
        fields_text = ", ".join(overridden_fields[:-1]) + and_connector + overridden_fields[-1]

    # Get translated warning template or use fallback
    warning_template = "⚠️ {fields} controlled by config entity"
    if translations and "override_warning_template" in translations:
        warning_template = translations["override_warning_template"]

    return {
        vol.Optional("_override_warning"): ConstantSelector(
            ConstantSelectorConfig(
                value=True,
                label=warning_template.format(fields=fields_text),
            )
        ),
    }


def get_user_schema(access_token: str | None = None) -> vol.Schema:
    """Return schema for user step (API token input)."""
    return vol.Schema(
        {
            vol.Required(
                CONF_ACCESS_TOKEN,
                default=access_token if access_token is not None else vol.UNDEFINED,
            ): TextSelector(
                TextSelectorConfig(
                    type=TextSelectorType.TEXT,
                ),
            ),
        }
    )


def get_reauth_confirm_schema() -> vol.Schema:
    """Return schema for reauth confirmation step."""
    return vol.Schema(
        {
            vol.Required(CONF_ACCESS_TOKEN): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT),
            ),
        }
    )


def get_select_home_schema(home_options: list[SelectOptionDict]) -> vol.Schema:
    """Return schema for home selection step."""
    return vol.Schema(
        {
            vol.Required("home_id"): SelectSelector(
                SelectSelectorConfig(
                    options=home_options,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            )
        }
    )


def get_subentry_init_schema(
    *,
    extended_descriptions: bool = DEFAULT_EXTENDED_DESCRIPTIONS,
    offset_days: int = DEFAULT_VIRTUAL_TIME_OFFSET_DAYS,
    offset_hours: int = DEFAULT_VIRTUAL_TIME_OFFSET_HOURS,
    offset_minutes: int = DEFAULT_VIRTUAL_TIME_OFFSET_MINUTES,
) -> vol.Schema:
    """Return schema for subentry init step (includes time-travel settings)."""
    return vol.Schema(
        {
            vol.Optional(
                CONF_EXTENDED_DESCRIPTIONS,
                default=extended_descriptions,
            ): BooleanSelector(),
            vol.Optional(
                CONF_VIRTUAL_TIME_OFFSET_DAYS,
                default=offset_days,
            ): NumberSelector(
                NumberSelectorConfig(
                    mode=NumberSelectorMode.BOX,
                    min=-365,  # Max 1 year back
                    max=0,  # Only past days allowed
                    step=1,
                )
            ),
            vol.Optional(
                CONF_VIRTUAL_TIME_OFFSET_HOURS,
                default=offset_hours,
            ): NumberSelector(
                NumberSelectorConfig(
                    mode=NumberSelectorMode.BOX,
                    min=-23,
                    max=23,
                    step=1,
                )
            ),
            vol.Optional(
                CONF_VIRTUAL_TIME_OFFSET_MINUTES,
                default=offset_minutes,
            ): NumberSelector(
                NumberSelectorConfig(
                    mode=NumberSelectorMode.BOX,
                    min=-59,
                    max=59,
                    step=1,
                )
            ),
        }
    )


def get_options_init_schema(options: Mapping[str, Any]) -> vol.Schema:
    """Return schema for options init step (general settings)."""
    return vol.Schema(
        {
            vol.Optional(
                CONF_EXTENDED_DESCRIPTIONS,
                default=options.get(CONF_EXTENDED_DESCRIPTIONS, DEFAULT_EXTENDED_DESCRIPTIONS),
            ): BooleanSelector(),
            vol.Optional(
                CONF_AVERAGE_SENSOR_DISPLAY,
                default=str(
                    options.get(
                        CONF_AVERAGE_SENSOR_DISPLAY,
                        DEFAULT_AVERAGE_SENSOR_DISPLAY,
                    )
                ),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=["median", "mean"],
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key="average_sensor_display",
                ),
            ),
        }
    )


def get_display_settings_schema(options: Mapping[str, Any], currency_code: str | None) -> vol.Schema:
    """Return schema for display settings configuration."""
    default_display_mode = get_default_currency_display(currency_code)

    return vol.Schema(
        {
            vol.Optional(
                CONF_CURRENCY_DISPLAY_MODE,
                default=str(
                    options.get(
                        CONF_CURRENCY_DISPLAY_MODE,
                        default_display_mode,
                    )
                ),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[DISPLAY_MODE_BASE, DISPLAY_MODE_SUBUNIT],
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key="currency_display_mode",
                ),
            ),
        }
    )


def get_price_rating_schema(options: Mapping[str, Any]) -> vol.Schema:
    """Return schema for price rating configuration (thresholds and stabilization)."""
    return vol.Schema(
        {
            vol.Optional(
                CONF_PRICE_RATING_THRESHOLD_LOW,
                default=int(
                    options.get(
                        CONF_PRICE_RATING_THRESHOLD_LOW,
                        DEFAULT_PRICE_RATING_THRESHOLD_LOW,
                    )
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_PRICE_RATING_THRESHOLD_LOW,
                    max=MAX_PRICE_RATING_THRESHOLD_LOW,
                    unit_of_measurement="%",
                    step=1,
                    mode=NumberSelectorMode.SLIDER,
                ),
            ),
            vol.Optional(
                CONF_PRICE_RATING_THRESHOLD_HIGH,
                default=int(
                    options.get(
                        CONF_PRICE_RATING_THRESHOLD_HIGH,
                        DEFAULT_PRICE_RATING_THRESHOLD_HIGH,
                    )
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_PRICE_RATING_THRESHOLD_HIGH,
                    max=MAX_PRICE_RATING_THRESHOLD_HIGH,
                    unit_of_measurement="%",
                    step=1,
                    mode=NumberSelectorMode.SLIDER,
                ),
            ),
            vol.Optional(
                CONF_PRICE_RATING_HYSTERESIS,
                default=float(
                    options.get(
                        CONF_PRICE_RATING_HYSTERESIS,
                        DEFAULT_PRICE_RATING_HYSTERESIS,
                    )
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_PRICE_RATING_HYSTERESIS,
                    max=MAX_PRICE_RATING_HYSTERESIS,
                    unit_of_measurement="%",
                    step=0.5,
                    mode=NumberSelectorMode.SLIDER,
                ),
            ),
            vol.Optional(
                CONF_PRICE_RATING_GAP_TOLERANCE,
                default=int(
                    options.get(
                        CONF_PRICE_RATING_GAP_TOLERANCE,
                        DEFAULT_PRICE_RATING_GAP_TOLERANCE,
                    )
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_PRICE_RATING_GAP_TOLERANCE,
                    max=MAX_PRICE_RATING_GAP_TOLERANCE,
                    step=1,
                    mode=NumberSelectorMode.SLIDER,
                ),
            ),
        }
    )


def get_price_level_schema(options: Mapping[str, Any]) -> vol.Schema:
    """Return schema for Tibber price level stabilization (gap tolerance for API level field)."""
    return vol.Schema(
        {
            vol.Optional(
                CONF_PRICE_LEVEL_GAP_TOLERANCE,
                default=int(
                    options.get(
                        CONF_PRICE_LEVEL_GAP_TOLERANCE,
                        DEFAULT_PRICE_LEVEL_GAP_TOLERANCE,
                    )
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_PRICE_LEVEL_GAP_TOLERANCE,
                    max=MAX_PRICE_LEVEL_GAP_TOLERANCE,
                    step=1,
                    mode=NumberSelectorMode.SLIDER,
                ),
            ),
        }
    )


def get_volatility_schema(options: Mapping[str, Any]) -> vol.Schema:
    """Return schema for volatility thresholds configuration."""
    return vol.Schema(
        {
            vol.Optional(
                CONF_VOLATILITY_THRESHOLD_MODERATE,
                default=float(
                    options.get(
                        CONF_VOLATILITY_THRESHOLD_MODERATE,
                        DEFAULT_VOLATILITY_THRESHOLD_MODERATE,
                    )
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_VOLATILITY_THRESHOLD_MODERATE,
                    max=MAX_VOLATILITY_THRESHOLD_MODERATE,
                    step=1.0,
                    unit_of_measurement="%",
                    mode=NumberSelectorMode.SLIDER,
                ),
            ),
            vol.Optional(
                CONF_VOLATILITY_THRESHOLD_HIGH,
                default=float(
                    options.get(
                        CONF_VOLATILITY_THRESHOLD_HIGH,
                        DEFAULT_VOLATILITY_THRESHOLD_HIGH,
                    )
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_VOLATILITY_THRESHOLD_HIGH,
                    max=MAX_VOLATILITY_THRESHOLD_HIGH,
                    step=1.0,
                    unit_of_measurement="%",
                    mode=NumberSelectorMode.SLIDER,
                ),
            ),
            vol.Optional(
                CONF_VOLATILITY_THRESHOLD_VERY_HIGH,
                default=float(
                    options.get(
                        CONF_VOLATILITY_THRESHOLD_VERY_HIGH,
                        DEFAULT_VOLATILITY_THRESHOLD_VERY_HIGH,
                    )
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_VOLATILITY_THRESHOLD_VERY_HIGH,
                    max=MAX_VOLATILITY_THRESHOLD_VERY_HIGH,
                    step=1.0,
                    unit_of_measurement="%",
                    mode=NumberSelectorMode.SLIDER,
                ),
            ),
        }
    )


def get_best_price_schema(
    options: Mapping[str, Any],
    overrides: ConfigOverrides | None = None,
    translations: OverrideTranslations | None = None,
) -> vol.Schema:
    """
    Return schema for best price period configuration with collapsible sections.

    Args:
        options: Current options from config entry
        overrides: Active runtime overrides from coordinator. Fields with active
                   overrides will be replaced with a constant placeholder.
        translations: Override translations from common section (optional)

    Returns:
        Voluptuous schema for the best price configuration form

    """
    period_settings = options.get("period_settings", {})
    flexibility_settings = options.get("flexibility_settings", {})
    relaxation_settings = options.get("relaxation_and_target_periods", {})

    # Get current values for override display
    min_period_length = int(
        period_settings.get(CONF_BEST_PRICE_MIN_PERIOD_LENGTH, DEFAULT_BEST_PRICE_MIN_PERIOD_LENGTH)
    )
    max_level_gap_count = int(
        period_settings.get(CONF_BEST_PRICE_MAX_LEVEL_GAP_COUNT, DEFAULT_BEST_PRICE_MAX_LEVEL_GAP_COUNT)
    )
    best_price_flex = int(flexibility_settings.get(CONF_BEST_PRICE_FLEX, DEFAULT_BEST_PRICE_FLEX))
    min_distance = int(
        flexibility_settings.get(CONF_BEST_PRICE_MIN_DISTANCE_FROM_AVG, DEFAULT_BEST_PRICE_MIN_DISTANCE_FROM_AVG)
    )
    enable_min_periods = relaxation_settings.get(CONF_ENABLE_MIN_PERIODS_BEST, DEFAULT_ENABLE_MIN_PERIODS_BEST)
    min_periods = int(relaxation_settings.get(CONF_MIN_PERIODS_BEST, DEFAULT_MIN_PERIODS_BEST))
    relaxation_attempts = int(relaxation_settings.get(CONF_RELAXATION_ATTEMPTS_BEST, DEFAULT_RELAXATION_ATTEMPTS_BEST))

    # Build section schemas with optional override warnings
    period_warning = get_section_override_warning("best_price", "period_settings", overrides, translations) or {}
    period_fields: dict[vol.Optional | vol.Required, Any] = {
        **period_warning,  # type: ignore[misc]
        vol.Optional(
            CONF_BEST_PRICE_MIN_PERIOD_LENGTH,
            default=min_period_length,
        ): NumberSelector(
            NumberSelectorConfig(
                min=MIN_PERIOD_LENGTH,
                max=MAX_MIN_PERIOD_LENGTH,
                step=15,
                unit_of_measurement="min",
                mode=NumberSelectorMode.SLIDER,
            )
        ),
        vol.Optional(
            CONF_BEST_PRICE_MAX_LEVEL,
            default=period_settings.get(
                CONF_BEST_PRICE_MAX_LEVEL,
                DEFAULT_BEST_PRICE_MAX_LEVEL,
            ),
        ): SelectSelector(
            SelectSelectorConfig(
                options=BEST_PRICE_MAX_LEVEL_OPTIONS,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="current_interval_price_level",
            ),
        ),
        vol.Optional(
            CONF_BEST_PRICE_MAX_LEVEL_GAP_COUNT,
            default=max_level_gap_count,
        ): NumberSelector(
            NumberSelectorConfig(
                min=MIN_GAP_COUNT,
                max=MAX_GAP_COUNT,
                step=1,
                mode=NumberSelectorMode.SLIDER,
            )
        ),
    }

    flexibility_warning = (
        get_section_override_warning("best_price", "flexibility_settings", overrides, translations) or {}
    )
    flexibility_fields: dict[vol.Optional | vol.Required, Any] = {
        **flexibility_warning,  # type: ignore[misc]
        vol.Optional(
            CONF_BEST_PRICE_FLEX,
            default=best_price_flex,
        ): NumberSelector(
            NumberSelectorConfig(
                min=0,
                max=50,
                step=1,
                unit_of_measurement="%",
                mode=NumberSelectorMode.SLIDER,
            )
        ),
        vol.Optional(
            CONF_BEST_PRICE_MIN_DISTANCE_FROM_AVG,
            default=min_distance,
        ): NumberSelector(
            NumberSelectorConfig(
                min=-50,
                max=0,
                step=1,
                unit_of_measurement="%",
                mode=NumberSelectorMode.SLIDER,
            )
        ),
    }

    relaxation_warning = (
        get_section_override_warning("best_price", "relaxation_and_target_periods", overrides, translations) or {}
    )
    relaxation_fields: dict[vol.Optional | vol.Required, Any] = {
        **relaxation_warning,  # type: ignore[misc]
        vol.Optional(
            CONF_ENABLE_MIN_PERIODS_BEST,
            default=enable_min_periods,
        ): BooleanSelector(selector.BooleanSelectorConfig()),
        vol.Optional(
            CONF_MIN_PERIODS_BEST,
            default=min_periods,
        ): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=MAX_MIN_PERIODS,
                step=1,
                mode=NumberSelectorMode.SLIDER,
            )
        ),
        vol.Optional(
            CONF_RELAXATION_ATTEMPTS_BEST,
            default=relaxation_attempts,
        ): NumberSelector(
            NumberSelectorConfig(
                min=MIN_RELAXATION_ATTEMPTS,
                max=MAX_RELAXATION_ATTEMPTS,
                step=1,
                mode=NumberSelectorMode.SLIDER,
            )
        ),
    }

    return vol.Schema(
        {
            vol.Required("period_settings"): section(
                vol.Schema(period_fields),
                {"collapsed": False},
            ),
            vol.Required("flexibility_settings"): section(
                vol.Schema(flexibility_fields),
                {"collapsed": True},
            ),
            vol.Required("relaxation_and_target_periods"): section(
                vol.Schema(relaxation_fields),
                {"collapsed": True},
            ),
        }
    )


def get_peak_price_schema(
    options: Mapping[str, Any],
    overrides: ConfigOverrides | None = None,
    translations: OverrideTranslations | None = None,
) -> vol.Schema:
    """
    Return schema for peak price period configuration with collapsible sections.

    Args:
        options: Current options from config entry
        overrides: Active runtime overrides from coordinator. Fields with active
                   overrides will be replaced with a constant placeholder.
        translations: Override translations from common section (optional)

    Returns:
        Voluptuous schema for the peak price configuration form

    """
    period_settings = options.get("period_settings", {})
    flexibility_settings = options.get("flexibility_settings", {})
    relaxation_settings = options.get("relaxation_and_target_periods", {})

    # Get current values for override display
    min_period_length = int(
        period_settings.get(CONF_PEAK_PRICE_MIN_PERIOD_LENGTH, DEFAULT_PEAK_PRICE_MIN_PERIOD_LENGTH)
    )
    max_level_gap_count = int(
        period_settings.get(CONF_PEAK_PRICE_MAX_LEVEL_GAP_COUNT, DEFAULT_PEAK_PRICE_MAX_LEVEL_GAP_COUNT)
    )
    peak_price_flex = int(flexibility_settings.get(CONF_PEAK_PRICE_FLEX, DEFAULT_PEAK_PRICE_FLEX))
    min_distance = int(
        flexibility_settings.get(CONF_PEAK_PRICE_MIN_DISTANCE_FROM_AVG, DEFAULT_PEAK_PRICE_MIN_DISTANCE_FROM_AVG)
    )
    enable_min_periods = relaxation_settings.get(CONF_ENABLE_MIN_PERIODS_PEAK, DEFAULT_ENABLE_MIN_PERIODS_PEAK)
    min_periods = int(relaxation_settings.get(CONF_MIN_PERIODS_PEAK, DEFAULT_MIN_PERIODS_PEAK))
    relaxation_attempts = int(relaxation_settings.get(CONF_RELAXATION_ATTEMPTS_PEAK, DEFAULT_RELAXATION_ATTEMPTS_PEAK))

    # Build section schemas with optional override warnings
    period_warning = get_section_override_warning("peak_price", "period_settings", overrides, translations) or {}
    period_fields: dict[vol.Optional | vol.Required, Any] = {
        **period_warning,  # type: ignore[misc]
        vol.Optional(
            CONF_PEAK_PRICE_MIN_PERIOD_LENGTH,
            default=min_period_length,
        ): NumberSelector(
            NumberSelectorConfig(
                min=MIN_PERIOD_LENGTH,
                max=MAX_MIN_PERIOD_LENGTH,
                step=15,
                unit_of_measurement="min",
                mode=NumberSelectorMode.SLIDER,
            )
        ),
        vol.Optional(
            CONF_PEAK_PRICE_MIN_LEVEL,
            default=period_settings.get(
                CONF_PEAK_PRICE_MIN_LEVEL,
                DEFAULT_PEAK_PRICE_MIN_LEVEL,
            ),
        ): SelectSelector(
            SelectSelectorConfig(
                options=PEAK_PRICE_MIN_LEVEL_OPTIONS,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="current_interval_price_level",
            ),
        ),
        vol.Optional(
            CONF_PEAK_PRICE_MAX_LEVEL_GAP_COUNT,
            default=max_level_gap_count,
        ): NumberSelector(
            NumberSelectorConfig(
                min=MIN_GAP_COUNT,
                max=MAX_GAP_COUNT,
                step=1,
                mode=NumberSelectorMode.SLIDER,
            )
        ),
    }

    flexibility_warning = (
        get_section_override_warning("peak_price", "flexibility_settings", overrides, translations) or {}
    )
    flexibility_fields: dict[vol.Optional | vol.Required, Any] = {
        **flexibility_warning,  # type: ignore[misc]
        vol.Optional(
            CONF_PEAK_PRICE_FLEX,
            default=peak_price_flex,
        ): NumberSelector(
            NumberSelectorConfig(
                min=-50,
                max=0,
                step=1,
                unit_of_measurement="%",
                mode=NumberSelectorMode.SLIDER,
            )
        ),
        vol.Optional(
            CONF_PEAK_PRICE_MIN_DISTANCE_FROM_AVG,
            default=min_distance,
        ): NumberSelector(
            NumberSelectorConfig(
                min=0,
                max=50,
                step=1,
                unit_of_measurement="%",
                mode=NumberSelectorMode.SLIDER,
            )
        ),
    }

    relaxation_warning = (
        get_section_override_warning("peak_price", "relaxation_and_target_periods", overrides, translations) or {}
    )
    relaxation_fields: dict[vol.Optional | vol.Required, Any] = {
        **relaxation_warning,  # type: ignore[misc]
        vol.Optional(
            CONF_ENABLE_MIN_PERIODS_PEAK,
            default=enable_min_periods,
        ): BooleanSelector(selector.BooleanSelectorConfig()),
        vol.Optional(
            CONF_MIN_PERIODS_PEAK,
            default=min_periods,
        ): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=MAX_MIN_PERIODS,
                step=1,
                mode=NumberSelectorMode.SLIDER,
            )
        ),
        vol.Optional(
            CONF_RELAXATION_ATTEMPTS_PEAK,
            default=relaxation_attempts,
        ): NumberSelector(
            NumberSelectorConfig(
                min=MIN_RELAXATION_ATTEMPTS,
                max=MAX_RELAXATION_ATTEMPTS,
                step=1,
                mode=NumberSelectorMode.SLIDER,
            )
        ),
    }

    return vol.Schema(
        {
            vol.Required("period_settings"): section(
                vol.Schema(period_fields),
                {"collapsed": False},
            ),
            vol.Required("flexibility_settings"): section(
                vol.Schema(flexibility_fields),
                {"collapsed": True},
            ),
            vol.Required("relaxation_and_target_periods"): section(
                vol.Schema(relaxation_fields),
                {"collapsed": True},
            ),
        }
    )


def get_price_trend_schema(options: Mapping[str, Any]) -> vol.Schema:
    """Return schema for price trend thresholds configuration."""
    return vol.Schema(
        {
            vol.Optional(
                CONF_PRICE_TREND_THRESHOLD_RISING,
                default=int(
                    options.get(
                        CONF_PRICE_TREND_THRESHOLD_RISING,
                        DEFAULT_PRICE_TREND_THRESHOLD_RISING,
                    )
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_PRICE_TREND_RISING,
                    max=MAX_PRICE_TREND_RISING,
                    step=1,
                    unit_of_measurement="%",
                    mode=NumberSelectorMode.SLIDER,
                ),
            ),
            vol.Optional(
                CONF_PRICE_TREND_THRESHOLD_STRONGLY_RISING,
                default=int(
                    options.get(
                        CONF_PRICE_TREND_THRESHOLD_STRONGLY_RISING,
                        DEFAULT_PRICE_TREND_THRESHOLD_STRONGLY_RISING,
                    )
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_PRICE_TREND_STRONGLY_RISING,
                    max=MAX_PRICE_TREND_STRONGLY_RISING,
                    step=1,
                    unit_of_measurement="%",
                    mode=NumberSelectorMode.SLIDER,
                ),
            ),
            vol.Optional(
                CONF_PRICE_TREND_THRESHOLD_FALLING,
                default=int(
                    options.get(
                        CONF_PRICE_TREND_THRESHOLD_FALLING,
                        DEFAULT_PRICE_TREND_THRESHOLD_FALLING,
                    )
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_PRICE_TREND_FALLING,
                    max=MAX_PRICE_TREND_FALLING,
                    step=1,
                    unit_of_measurement="%",
                    mode=NumberSelectorMode.SLIDER,
                ),
            ),
            vol.Optional(
                CONF_PRICE_TREND_THRESHOLD_STRONGLY_FALLING,
                default=int(
                    options.get(
                        CONF_PRICE_TREND_THRESHOLD_STRONGLY_FALLING,
                        DEFAULT_PRICE_TREND_THRESHOLD_STRONGLY_FALLING,
                    )
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_PRICE_TREND_STRONGLY_FALLING,
                    max=MAX_PRICE_TREND_STRONGLY_FALLING,
                    step=1,
                    unit_of_measurement="%",
                    mode=NumberSelectorMode.SLIDER,
                ),
            ),
        }
    )


def get_chart_data_export_schema(_options: Mapping[str, Any]) -> vol.Schema:
    """Return schema for chart data export info page (no input fields)."""
    # Empty schema - this is just an info page now
    return vol.Schema({})


def get_reset_to_defaults_schema() -> vol.Schema:
    """Return schema for reset to defaults confirmation step."""
    return vol.Schema(
        {
            vol.Required("confirm_reset", default=False): selector.BooleanSelector(),
        }
    )
