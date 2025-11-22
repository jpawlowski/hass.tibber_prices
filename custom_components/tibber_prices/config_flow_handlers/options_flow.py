"""Options flow for tibber_prices integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from collections.abc import Mapping

from custom_components.tibber_prices.config_flow_handlers.schemas import (
    get_best_price_schema,
    get_chart_data_export_schema,
    get_options_init_schema,
    get_peak_price_schema,
    get_price_rating_schema,
    get_price_trend_schema,
    get_volatility_schema,
)
from custom_components.tibber_prices.config_flow_handlers.validators import (
    validate_best_price_distance_percentage,
    validate_distance_percentage,
    validate_flex_percentage,
    validate_gap_count,
    validate_min_periods,
    validate_period_length,
    validate_price_rating_threshold_high,
    validate_price_rating_threshold_low,
    validate_price_rating_thresholds,
    validate_price_trend_falling,
    validate_price_trend_rising,
    validate_relaxation_attempts,
    validate_volatility_threshold_high,
    validate_volatility_threshold_moderate,
    validate_volatility_threshold_very_high,
    validate_volatility_thresholds,
)
from custom_components.tibber_prices.const import (
    CONF_BEST_PRICE_FLEX,
    CONF_BEST_PRICE_MAX_LEVEL_GAP_COUNT,
    CONF_BEST_PRICE_MIN_DISTANCE_FROM_AVG,
    CONF_BEST_PRICE_MIN_PERIOD_LENGTH,
    CONF_MIN_PERIODS_BEST,
    CONF_MIN_PERIODS_PEAK,
    CONF_PEAK_PRICE_FLEX,
    CONF_PEAK_PRICE_MAX_LEVEL_GAP_COUNT,
    CONF_PEAK_PRICE_MIN_DISTANCE_FROM_AVG,
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
    DEFAULT_VOLATILITY_THRESHOLD_HIGH,
    DEFAULT_VOLATILITY_THRESHOLD_MODERATE,
    DEFAULT_VOLATILITY_THRESHOLD_VERY_HIGH,
    DOMAIN,
)
from homeassistant.config_entries import ConfigFlowResult, OptionsFlow

_LOGGER = logging.getLogger(__name__)


class TibberPricesOptionsFlowHandler(OptionsFlow):
    """Handle options for tibber_prices entries."""

    # Step progress tracking
    _TOTAL_STEPS: ClassVar[int] = 7
    _STEP_INFO: ClassVar[dict[str, int]] = {
        "init": 1,
        "current_interval_price_rating": 2,
        "volatility": 3,
        "best_price": 4,
        "peak_price": 5,
        "price_trend": 6,
        "chart_data_export": 7,
    }

    def __init__(self) -> None:
        """Initialize options flow."""
        self._options: dict[str, Any] = {}

    def _migrate_config_options(self, options: Mapping[str, Any]) -> dict[str, Any]:
        """
        Migrate deprecated config options to current format.

        This removes obsolete keys and renames changed keys to maintain
        compatibility with older config entries.

        Args:
            options: Original options dict from config_entry

        Returns:
            Migrated options dict with deprecated keys removed/renamed

        """
        migrated = dict(options)
        migration_performed = False

        # Migration 1: Rename relaxation_step_* to relaxation_attempts_*
        # (Changed in v0.6.0 - commit 5a5c8ca)
        if "relaxation_step_best" in migrated:
            migrated["relaxation_attempts_best"] = migrated.pop("relaxation_step_best")
            migration_performed = True
            _LOGGER.info(
                "Migrated config option: relaxation_step_best -> relaxation_attempts_best (value: %s)",
                migrated["relaxation_attempts_best"],
            )

        if "relaxation_step_peak" in migrated:
            migrated["relaxation_attempts_peak"] = migrated.pop("relaxation_step_peak")
            migration_performed = True
            _LOGGER.info(
                "Migrated config option: relaxation_step_peak -> relaxation_attempts_peak (value: %s)",
                migrated["relaxation_attempts_peak"],
            )

        # Migration 2: Remove obsolete volatility filter options
        # (Removed in v0.9.0 - volatility filter feature removed)
        obsolete_keys = [
            "best_price_min_volatility",
            "peak_price_min_volatility",
            "min_volatility_for_periods",
        ]

        for key in obsolete_keys:
            if key in migrated:
                old_value = migrated.pop(key)
                migration_performed = True
                _LOGGER.info(
                    "Removed obsolete config option: %s (was: %s)",
                    key,
                    old_value,
                )

        if migration_performed:
            _LOGGER.info("Config migration completed - deprecated options cleaned up")

        return migrated

    def _get_step_description_placeholders(self, step_id: str) -> dict[str, str]:
        """Get description placeholders with step progress."""
        if step_id not in self._STEP_INFO:
            return {}

        step_num = self._STEP_INFO[step_id]

        # Get translations loaded by Home Assistant
        standard_translations_key = f"{DOMAIN}_standard_translations_{self.hass.config.language}"
        translations = self.hass.data.get(standard_translations_key, {})

        # Get step progress text from translations with placeholders
        step_progress_template = translations.get("common", {}).get("step_progress", "Step {step_num} of {total_steps}")
        step_progress = step_progress_template.format(step_num=step_num, total_steps=self._TOTAL_STEPS)

        return {
            "step_progress": step_progress,
        }

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the options - General Settings."""
        # Initialize options from config_entry on first call
        if not self._options:
            # Migrate deprecated config options before processing
            self._options = self._migrate_config_options(self.config_entry.options)

        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_current_interval_price_rating()

        return self.async_show_form(
            step_id="init",
            data_schema=get_options_init_schema(self.config_entry.options),
            description_placeholders={
                **self._get_step_description_placeholders("init"),
                "user_login": self.config_entry.data.get("user_login", "N/A"),
            },
        )

    async def async_step_current_interval_price_rating(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure price rating thresholds."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate low price rating threshold
            if CONF_PRICE_RATING_THRESHOLD_LOW in user_input and not validate_price_rating_threshold_low(
                user_input[CONF_PRICE_RATING_THRESHOLD_LOW]
            ):
                errors[CONF_PRICE_RATING_THRESHOLD_LOW] = "invalid_price_rating_low"

            # Validate high price rating threshold
            if CONF_PRICE_RATING_THRESHOLD_HIGH in user_input and not validate_price_rating_threshold_high(
                user_input[CONF_PRICE_RATING_THRESHOLD_HIGH]
            ):
                errors[CONF_PRICE_RATING_THRESHOLD_HIGH] = "invalid_price_rating_high"

            # Cross-validate both thresholds together (LOW must be < HIGH)
            if not errors and not validate_price_rating_thresholds(
                user_input.get(
                    CONF_PRICE_RATING_THRESHOLD_LOW, self._options.get(CONF_PRICE_RATING_THRESHOLD_LOW, -10)
                ),
                user_input.get(
                    CONF_PRICE_RATING_THRESHOLD_HIGH, self._options.get(CONF_PRICE_RATING_THRESHOLD_HIGH, 10)
                ),
            ):
                # This should never happen given the range constraints, but add error for safety
                errors["base"] = "invalid_price_rating_thresholds"

            if not errors:
                self._options.update(user_input)
                return await self.async_step_volatility()

        return self.async_show_form(
            step_id="current_interval_price_rating",
            data_schema=get_price_rating_schema(self.config_entry.options),
            description_placeholders=self._get_step_description_placeholders("current_interval_price_rating"),
            errors=errors,
        )

    async def async_step_best_price(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Configure best price period settings."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate period length
            if CONF_BEST_PRICE_MIN_PERIOD_LENGTH in user_input and not validate_period_length(
                user_input[CONF_BEST_PRICE_MIN_PERIOD_LENGTH]
            ):
                errors[CONF_BEST_PRICE_MIN_PERIOD_LENGTH] = "invalid_period_length"

            # Validate flex percentage
            if CONF_BEST_PRICE_FLEX in user_input and not validate_flex_percentage(user_input[CONF_BEST_PRICE_FLEX]):
                errors[CONF_BEST_PRICE_FLEX] = "invalid_flex"

            # Validate distance from average (Best Price uses negative values)
            if CONF_BEST_PRICE_MIN_DISTANCE_FROM_AVG in user_input and not validate_best_price_distance_percentage(
                user_input[CONF_BEST_PRICE_MIN_DISTANCE_FROM_AVG]
            ):
                errors[CONF_BEST_PRICE_MIN_DISTANCE_FROM_AVG] = "invalid_best_price_distance"

            # Validate minimum periods count
            if CONF_MIN_PERIODS_BEST in user_input and not validate_min_periods(user_input[CONF_MIN_PERIODS_BEST]):
                errors[CONF_MIN_PERIODS_BEST] = "invalid_min_periods"

            # Validate gap count
            if CONF_BEST_PRICE_MAX_LEVEL_GAP_COUNT in user_input and not validate_gap_count(
                user_input[CONF_BEST_PRICE_MAX_LEVEL_GAP_COUNT]
            ):
                errors[CONF_BEST_PRICE_MAX_LEVEL_GAP_COUNT] = "invalid_gap_count"

            # Validate relaxation attempts
            if CONF_RELAXATION_ATTEMPTS_BEST in user_input and not validate_relaxation_attempts(
                user_input[CONF_RELAXATION_ATTEMPTS_BEST]
            ):
                errors[CONF_RELAXATION_ATTEMPTS_BEST] = "invalid_relaxation_attempts"

            if not errors:
                self._options.update(user_input)
                return await self.async_step_peak_price()

        return self.async_show_form(
            step_id="best_price",
            data_schema=get_best_price_schema(self.config_entry.options),
            description_placeholders=self._get_step_description_placeholders("best_price"),
            errors=errors,
        )

    async def async_step_peak_price(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Configure peak price period settings."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate period length
            if CONF_PEAK_PRICE_MIN_PERIOD_LENGTH in user_input and not validate_period_length(
                user_input[CONF_PEAK_PRICE_MIN_PERIOD_LENGTH]
            ):
                errors[CONF_PEAK_PRICE_MIN_PERIOD_LENGTH] = "invalid_period_length"

            # Validate flex percentage (peak uses negative values)
            if CONF_PEAK_PRICE_FLEX in user_input and not validate_flex_percentage(user_input[CONF_PEAK_PRICE_FLEX]):
                errors[CONF_PEAK_PRICE_FLEX] = "invalid_flex"

            # Validate distance from average (Peak Price uses positive values)
            if CONF_PEAK_PRICE_MIN_DISTANCE_FROM_AVG in user_input and not validate_distance_percentage(
                user_input[CONF_PEAK_PRICE_MIN_DISTANCE_FROM_AVG]
            ):
                errors[CONF_PEAK_PRICE_MIN_DISTANCE_FROM_AVG] = "invalid_peak_price_distance"

            # Validate minimum periods count
            if CONF_MIN_PERIODS_PEAK in user_input and not validate_min_periods(user_input[CONF_MIN_PERIODS_PEAK]):
                errors[CONF_MIN_PERIODS_PEAK] = "invalid_min_periods"

            # Validate gap count
            if CONF_PEAK_PRICE_MAX_LEVEL_GAP_COUNT in user_input and not validate_gap_count(
                user_input[CONF_PEAK_PRICE_MAX_LEVEL_GAP_COUNT]
            ):
                errors[CONF_PEAK_PRICE_MAX_LEVEL_GAP_COUNT] = "invalid_gap_count"

            # Validate relaxation attempts
            if CONF_RELAXATION_ATTEMPTS_PEAK in user_input and not validate_relaxation_attempts(
                user_input[CONF_RELAXATION_ATTEMPTS_PEAK]
            ):
                errors[CONF_RELAXATION_ATTEMPTS_PEAK] = "invalid_relaxation_attempts"

            if not errors:
                self._options.update(user_input)
                return await self.async_step_price_trend()

        return self.async_show_form(
            step_id="peak_price",
            data_schema=get_peak_price_schema(self.config_entry.options),
            description_placeholders=self._get_step_description_placeholders("peak_price"),
            errors=errors,
        )

    async def async_step_price_trend(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Configure price trend thresholds."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate rising trend threshold
            if CONF_PRICE_TREND_THRESHOLD_RISING in user_input and not validate_price_trend_rising(
                user_input[CONF_PRICE_TREND_THRESHOLD_RISING]
            ):
                errors[CONF_PRICE_TREND_THRESHOLD_RISING] = "invalid_price_trend_rising"

            # Validate falling trend threshold
            if CONF_PRICE_TREND_THRESHOLD_FALLING in user_input and not validate_price_trend_falling(
                user_input[CONF_PRICE_TREND_THRESHOLD_FALLING]
            ):
                errors[CONF_PRICE_TREND_THRESHOLD_FALLING] = "invalid_price_trend_falling"

            if not errors:
                self._options.update(user_input)
                return await self.async_step_chart_data_export()

        return self.async_show_form(
            step_id="price_trend",
            data_schema=get_price_trend_schema(self.config_entry.options),
            description_placeholders=self._get_step_description_placeholders("price_trend"),
            errors=errors,
        )

    async def async_step_chart_data_export(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Info page for chart data export sensor."""
        if user_input is not None:
            # No validation needed - just an info page
            return self.async_create_entry(title="", data=self._options)

        # Show info-only form (no input fields)
        return self.async_show_form(
            step_id="chart_data_export",
            data_schema=get_chart_data_export_schema(self.config_entry.options),
            description_placeholders=self._get_step_description_placeholders("chart_data_export"),
        )

    async def async_step_volatility(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Configure volatility thresholds and period filtering."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate moderate volatility threshold
            if CONF_VOLATILITY_THRESHOLD_MODERATE in user_input and not validate_volatility_threshold_moderate(
                user_input[CONF_VOLATILITY_THRESHOLD_MODERATE]
            ):
                errors[CONF_VOLATILITY_THRESHOLD_MODERATE] = "invalid_volatility_threshold_moderate"

            # Validate high volatility threshold
            if CONF_VOLATILITY_THRESHOLD_HIGH in user_input and not validate_volatility_threshold_high(
                user_input[CONF_VOLATILITY_THRESHOLD_HIGH]
            ):
                errors[CONF_VOLATILITY_THRESHOLD_HIGH] = "invalid_volatility_threshold_high"

            # Validate very high volatility threshold
            if CONF_VOLATILITY_THRESHOLD_VERY_HIGH in user_input and not validate_volatility_threshold_very_high(
                user_input[CONF_VOLATILITY_THRESHOLD_VERY_HIGH]
            ):
                errors[CONF_VOLATILITY_THRESHOLD_VERY_HIGH] = "invalid_volatility_threshold_very_high"

            # Cross-validation: Ensure MODERATE < HIGH < VERY_HIGH
            if not errors:
                existing_options = self.config_entry.options
                moderate = user_input.get(
                    CONF_VOLATILITY_THRESHOLD_MODERATE,
                    existing_options.get(CONF_VOLATILITY_THRESHOLD_MODERATE, DEFAULT_VOLATILITY_THRESHOLD_MODERATE),
                )
                high = user_input.get(
                    CONF_VOLATILITY_THRESHOLD_HIGH,
                    existing_options.get(CONF_VOLATILITY_THRESHOLD_HIGH, DEFAULT_VOLATILITY_THRESHOLD_HIGH),
                )
                very_high = user_input.get(
                    CONF_VOLATILITY_THRESHOLD_VERY_HIGH,
                    existing_options.get(CONF_VOLATILITY_THRESHOLD_VERY_HIGH, DEFAULT_VOLATILITY_THRESHOLD_VERY_HIGH),
                )

                if not validate_volatility_thresholds(moderate, high, very_high):
                    errors["base"] = "invalid_volatility_thresholds"

            if not errors:
                self._options.update(user_input)
                return await self.async_step_best_price()

        return self.async_show_form(
            step_id="volatility",
            data_schema=get_volatility_schema(self.config_entry.options),
            description_placeholders=self._get_step_description_placeholders("volatility"),
            errors=errors,
        )
