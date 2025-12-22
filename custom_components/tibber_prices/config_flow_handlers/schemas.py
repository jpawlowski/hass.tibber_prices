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


def get_best_price_schema(options: Mapping[str, Any]) -> vol.Schema:
    """Return schema for best price period configuration with collapsible sections."""
    period_settings = options.get("period_settings", {})
    return vol.Schema(
        {
            vol.Required("period_settings"): section(
                vol.Schema(
                    {
                        vol.Optional(
                            CONF_BEST_PRICE_MIN_PERIOD_LENGTH,
                            default=int(
                                period_settings.get(
                                    CONF_BEST_PRICE_MIN_PERIOD_LENGTH,
                                    DEFAULT_BEST_PRICE_MIN_PERIOD_LENGTH,
                                )
                            ),
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=MIN_PERIOD_LENGTH,
                                max=MAX_MIN_PERIOD_LENGTH,
                                step=15,
                                unit_of_measurement="min",
                                mode=NumberSelectorMode.SLIDER,
                            ),
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
                            default=int(
                                period_settings.get(
                                    CONF_BEST_PRICE_MAX_LEVEL_GAP_COUNT,
                                    DEFAULT_BEST_PRICE_MAX_LEVEL_GAP_COUNT,
                                )
                            ),
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=MIN_GAP_COUNT,
                                max=MAX_GAP_COUNT,
                                step=1,
                                mode=NumberSelectorMode.SLIDER,
                            ),
                        ),
                    }
                ),
                {"collapsed": False},
            ),
            vol.Required("flexibility_settings"): section(
                vol.Schema(
                    {
                        vol.Optional(
                            CONF_BEST_PRICE_FLEX,
                            default=int(
                                options.get("flexibility_settings", {}).get(
                                    CONF_BEST_PRICE_FLEX,
                                    DEFAULT_BEST_PRICE_FLEX,
                                )
                            ),
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=0,
                                max=50,
                                step=1,
                                unit_of_measurement="%",
                                mode=NumberSelectorMode.SLIDER,
                            ),
                        ),
                        vol.Optional(
                            CONF_BEST_PRICE_MIN_DISTANCE_FROM_AVG,
                            default=int(
                                options.get("flexibility_settings", {}).get(
                                    CONF_BEST_PRICE_MIN_DISTANCE_FROM_AVG,
                                    DEFAULT_BEST_PRICE_MIN_DISTANCE_FROM_AVG,
                                )
                            ),
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=-50,
                                max=0,
                                step=1,
                                unit_of_measurement="%",
                                mode=NumberSelectorMode.SLIDER,
                            ),
                        ),
                    }
                ),
                {"collapsed": True},
            ),
            vol.Required("relaxation_and_target_periods"): section(
                vol.Schema(
                    {
                        vol.Optional(
                            CONF_ENABLE_MIN_PERIODS_BEST,
                            default=options.get("relaxation_and_target_periods", {}).get(
                                CONF_ENABLE_MIN_PERIODS_BEST,
                                DEFAULT_ENABLE_MIN_PERIODS_BEST,
                            ),
                        ): BooleanSelector(),
                        vol.Optional(
                            CONF_MIN_PERIODS_BEST,
                            default=int(
                                options.get("relaxation_and_target_periods", {}).get(
                                    CONF_MIN_PERIODS_BEST,
                                    DEFAULT_MIN_PERIODS_BEST,
                                )
                            ),
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=1,
                                max=MAX_MIN_PERIODS,
                                step=1,
                                mode=NumberSelectorMode.SLIDER,
                            ),
                        ),
                        vol.Optional(
                            CONF_RELAXATION_ATTEMPTS_BEST,
                            default=int(
                                options.get("relaxation_and_target_periods", {}).get(
                                    CONF_RELAXATION_ATTEMPTS_BEST,
                                    DEFAULT_RELAXATION_ATTEMPTS_BEST,
                                )
                            ),
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=MIN_RELAXATION_ATTEMPTS,
                                max=MAX_RELAXATION_ATTEMPTS,
                                step=1,
                                mode=NumberSelectorMode.SLIDER,
                            ),
                        ),
                    }
                ),
                {"collapsed": True},
            ),
        }
    )


def get_peak_price_schema(options: Mapping[str, Any]) -> vol.Schema:
    """Return schema for peak price period configuration with collapsible sections."""
    period_settings = options.get("period_settings", {})
    return vol.Schema(
        {
            vol.Required("period_settings"): section(
                vol.Schema(
                    {
                        vol.Optional(
                            CONF_PEAK_PRICE_MIN_PERIOD_LENGTH,
                            default=int(
                                period_settings.get(
                                    CONF_PEAK_PRICE_MIN_PERIOD_LENGTH,
                                    DEFAULT_PEAK_PRICE_MIN_PERIOD_LENGTH,
                                )
                            ),
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=MIN_PERIOD_LENGTH,
                                max=MAX_MIN_PERIOD_LENGTH,
                                step=15,
                                unit_of_measurement="min",
                                mode=NumberSelectorMode.SLIDER,
                            ),
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
                            default=int(
                                period_settings.get(
                                    CONF_PEAK_PRICE_MAX_LEVEL_GAP_COUNT,
                                    DEFAULT_PEAK_PRICE_MAX_LEVEL_GAP_COUNT,
                                )
                            ),
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=MIN_GAP_COUNT,
                                max=MAX_GAP_COUNT,
                                step=1,
                                mode=NumberSelectorMode.SLIDER,
                            ),
                        ),
                    }
                ),
                {"collapsed": False},
            ),
            vol.Required("flexibility_settings"): section(
                vol.Schema(
                    {
                        vol.Optional(
                            CONF_PEAK_PRICE_FLEX,
                            default=int(
                                options.get("flexibility_settings", {}).get(
                                    CONF_PEAK_PRICE_FLEX,
                                    DEFAULT_PEAK_PRICE_FLEX,
                                )
                            ),
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=-50,
                                max=0,
                                step=1,
                                unit_of_measurement="%",
                                mode=NumberSelectorMode.SLIDER,
                            ),
                        ),
                        vol.Optional(
                            CONF_PEAK_PRICE_MIN_DISTANCE_FROM_AVG,
                            default=int(
                                options.get("flexibility_settings", {}).get(
                                    CONF_PEAK_PRICE_MIN_DISTANCE_FROM_AVG,
                                    DEFAULT_PEAK_PRICE_MIN_DISTANCE_FROM_AVG,
                                )
                            ),
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=0,
                                max=50,
                                step=1,
                                unit_of_measurement="%",
                                mode=NumberSelectorMode.SLIDER,
                            ),
                        ),
                    }
                ),
                {"collapsed": True},
            ),
            vol.Required("relaxation_and_target_periods"): section(
                vol.Schema(
                    {
                        vol.Optional(
                            CONF_ENABLE_MIN_PERIODS_PEAK,
                            default=options.get("relaxation_and_target_periods", {}).get(
                                CONF_ENABLE_MIN_PERIODS_PEAK,
                                DEFAULT_ENABLE_MIN_PERIODS_PEAK,
                            ),
                        ): BooleanSelector(),
                        vol.Optional(
                            CONF_MIN_PERIODS_PEAK,
                            default=int(
                                options.get("relaxation_and_target_periods", {}).get(
                                    CONF_MIN_PERIODS_PEAK,
                                    DEFAULT_MIN_PERIODS_PEAK,
                                )
                            ),
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=1,
                                max=MAX_MIN_PERIODS,
                                step=1,
                                mode=NumberSelectorMode.SLIDER,
                            ),
                        ),
                        vol.Optional(
                            CONF_RELAXATION_ATTEMPTS_PEAK,
                            default=int(
                                options.get("relaxation_and_target_periods", {}).get(
                                    CONF_RELAXATION_ATTEMPTS_PEAK,
                                    DEFAULT_RELAXATION_ATTEMPTS_PEAK,
                                )
                            ),
                        ): NumberSelector(
                            NumberSelectorConfig(
                                min=MIN_RELAXATION_ATTEMPTS,
                                max=MAX_RELAXATION_ATTEMPTS,
                                step=1,
                                mode=NumberSelectorMode.SLIDER,
                            ),
                        ),
                    }
                ),
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
