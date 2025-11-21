"""Schema definitions for tibber_prices config flow."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

import voluptuous as vol

from custom_components.tibber_prices.const import (
    BEST_PRICE_MAX_LEVEL_OPTIONS,
    CONF_BEST_PRICE_FLEX,
    CONF_BEST_PRICE_MAX_LEVEL,
    CONF_BEST_PRICE_MAX_LEVEL_GAP_COUNT,
    CONF_BEST_PRICE_MIN_DISTANCE_FROM_AVG,
    CONF_BEST_PRICE_MIN_PERIOD_LENGTH,
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
    CONF_PRICE_RATING_THRESHOLD_HIGH,
    CONF_PRICE_RATING_THRESHOLD_LOW,
    CONF_PRICE_TREND_THRESHOLD_FALLING,
    CONF_PRICE_TREND_THRESHOLD_RISING,
    CONF_RELAXATION_ATTEMPTS_BEST,
    CONF_RELAXATION_ATTEMPTS_PEAK,
    CONF_VOLATILITY_THRESHOLD_HIGH,
    CONF_VOLATILITY_THRESHOLD_MODERATE,
    CONF_VOLATILITY_THRESHOLD_VERY_HIGH,
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
    DEFAULT_PRICE_RATING_THRESHOLD_HIGH,
    DEFAULT_PRICE_RATING_THRESHOLD_LOW,
    DEFAULT_PRICE_TREND_THRESHOLD_FALLING,
    DEFAULT_PRICE_TREND_THRESHOLD_RISING,
    DEFAULT_RELAXATION_ATTEMPTS_BEST,
    DEFAULT_RELAXATION_ATTEMPTS_PEAK,
    DEFAULT_VOLATILITY_THRESHOLD_HIGH,
    DEFAULT_VOLATILITY_THRESHOLD_MODERATE,
    DEFAULT_VOLATILITY_THRESHOLD_VERY_HIGH,
    MAX_GAP_COUNT,
    MAX_MIN_PERIOD_LENGTH,
    MAX_MIN_PERIODS,
    MAX_PRICE_RATING_THRESHOLD_HIGH,
    MAX_PRICE_RATING_THRESHOLD_LOW,
    MAX_PRICE_TREND_FALLING,
    MAX_PRICE_TREND_RISING,
    MAX_RELAXATION_ATTEMPTS,
    MAX_VOLATILITY_THRESHOLD,
    MIN_GAP_COUNT,
    MIN_PERIOD_LENGTH,
    MIN_PRICE_RATING_THRESHOLD_HIGH,
    MIN_PRICE_RATING_THRESHOLD_LOW,
    MIN_PRICE_TREND_FALLING,
    MIN_PRICE_TREND_RISING,
    MIN_RELAXATION_ATTEMPTS,
    MIN_VOLATILITY_THRESHOLD,
    PEAK_PRICE_MIN_LEVEL_OPTIONS,
)
from homeassistant.const import CONF_ACCESS_TOKEN
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


def get_subentry_init_schema(*, extended_descriptions: bool = DEFAULT_EXTENDED_DESCRIPTIONS) -> vol.Schema:
    """Return schema for subentry init step."""
    return vol.Schema(
        {
            vol.Optional(
                CONF_EXTENDED_DESCRIPTIONS,
                default=extended_descriptions,
            ): BooleanSelector(),
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
        }
    )


def get_price_rating_schema(options: Mapping[str, Any]) -> vol.Schema:
    """Return schema for price rating thresholds configuration."""
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
                    min=MIN_VOLATILITY_THRESHOLD,
                    max=MAX_VOLATILITY_THRESHOLD,
                    step=0.1,
                    unit_of_measurement="%",
                    mode=NumberSelectorMode.BOX,
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
                    min=MIN_VOLATILITY_THRESHOLD,
                    max=MAX_VOLATILITY_THRESHOLD,
                    step=0.1,
                    unit_of_measurement="%",
                    mode=NumberSelectorMode.BOX,
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
                    min=MIN_VOLATILITY_THRESHOLD,
                    max=MAX_VOLATILITY_THRESHOLD,
                    step=0.1,
                    unit_of_measurement="%",
                    mode=NumberSelectorMode.BOX,
                ),
            ),
        }
    )


def get_best_price_schema(options: Mapping[str, Any]) -> vol.Schema:
    """Return schema for best price period configuration."""
    return vol.Schema(
        {
            vol.Optional(
                CONF_BEST_PRICE_MIN_PERIOD_LENGTH,
                default=int(
                    options.get(
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
                CONF_BEST_PRICE_FLEX,
                default=int(
                    options.get(
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
                    options.get(
                        CONF_BEST_PRICE_MIN_DISTANCE_FROM_AVG,
                        DEFAULT_BEST_PRICE_MIN_DISTANCE_FROM_AVG,
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
                CONF_BEST_PRICE_MAX_LEVEL,
                default=options.get(
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
                    options.get(
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
            vol.Optional(
                CONF_ENABLE_MIN_PERIODS_BEST,
                default=options.get(
                    CONF_ENABLE_MIN_PERIODS_BEST,
                    DEFAULT_ENABLE_MIN_PERIODS_BEST,
                ),
            ): BooleanSelector(),
            vol.Optional(
                CONF_MIN_PERIODS_BEST,
                default=int(
                    options.get(
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
                    options.get(
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
    )


def get_peak_price_schema(options: Mapping[str, Any]) -> vol.Schema:
    """Return schema for peak price period configuration."""
    return vol.Schema(
        {
            vol.Optional(
                CONF_PEAK_PRICE_MIN_PERIOD_LENGTH,
                default=int(
                    options.get(
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
                CONF_PEAK_PRICE_FLEX,
                default=int(
                    options.get(
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
                    options.get(
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
            vol.Optional(
                CONF_PEAK_PRICE_MIN_LEVEL,
                default=options.get(
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
                    options.get(
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
            vol.Optional(
                CONF_ENABLE_MIN_PERIODS_PEAK,
                default=options.get(
                    CONF_ENABLE_MIN_PERIODS_PEAK,
                    DEFAULT_ENABLE_MIN_PERIODS_PEAK,
                ),
            ): BooleanSelector(),
            vol.Optional(
                CONF_MIN_PERIODS_PEAK,
                default=int(
                    options.get(
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
                    options.get(
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
