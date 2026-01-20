"""Options flow for tibber_prices integration."""

from __future__ import annotations

import logging
from copy import deepcopy
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

from custom_components.tibber_prices.config_flow_handlers.schemas import (
    get_best_price_schema,
    get_chart_data_export_schema,
    get_display_settings_schema,
    get_options_init_schema,
    get_peak_price_schema,
    get_price_level_schema,
    get_price_rating_schema,
    get_price_trend_schema,
    get_reset_to_defaults_schema,
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
    validate_price_trend_strongly_falling,
    validate_price_trend_strongly_rising,
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
    CONF_PRICE_TREND_THRESHOLD_STRONGLY_FALLING,
    CONF_PRICE_TREND_THRESHOLD_STRONGLY_RISING,
    CONF_RELAXATION_ATTEMPTS_BEST,
    CONF_RELAXATION_ATTEMPTS_PEAK,
    CONF_VOLATILITY_THRESHOLD_HIGH,
    CONF_VOLATILITY_THRESHOLD_MODERATE,
    CONF_VOLATILITY_THRESHOLD_VERY_HIGH,
    DEFAULT_VOLATILITY_THRESHOLD_HIGH,
    DEFAULT_VOLATILITY_THRESHOLD_MODERATE,
    DEFAULT_VOLATILITY_THRESHOLD_VERY_HIGH,
    DOMAIN,
    get_default_options,
)
from homeassistant.config_entries import ConfigFlowResult, OptionsFlow

_LOGGER = logging.getLogger(__name__)


class TibberPricesOptionsFlowHandler(OptionsFlow):
    """Handle options for tibber_prices entries."""

    def __init__(self) -> None:
        """Initialize options flow."""
        self._options: dict[str, Any] = {}

    def _merge_section_data(self, user_input: dict[str, Any]) -> None:
        """
        Merge section data from form input into options.

        Home Assistant forms with section() return nested dicts like:
        {"section_name": {"setting1": value1, "setting2": value2}}

        We need to preserve this structure in config_entry.options.

        Args:
            user_input: Nested user input from form with sections

        """
        for section_key, section_data in user_input.items():
            if isinstance(section_data, dict):
                # This is a section - ensure the section exists in options
                if section_key not in self._options:
                    self._options[section_key] = {}
                # Update the section with new values
                self._options[section_key].update(section_data)
            else:
                # This is a direct value - keep it as is
                self._options[section_key] = section_data

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
        # CRITICAL: Use deepcopy to avoid modifying the original config_entry.options
        # If we use dict(options), nested dicts are still referenced, causing
        # self._options modifications to leak into config_entry.options
        migrated = deepcopy(dict(options))
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

    def _save_options_if_changed(self) -> bool:
        """
        Save options only if they actually changed.

        Returns:
            True if options were updated, False if no changes detected

        """
        # Compare old and new options
        if self.config_entry.options != self._options:
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                options=self._options,
            )
            return True
        return False

    async def async_step_init(self, _user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the options - show menu."""
        # Always reload options from config_entry to get latest saved state
        # This ensures changes from previous steps are visible
        self._options = self._migrate_config_options(self.config_entry.options)

        # Show menu with all configuration categories
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "general_settings",
                "display_settings",
                "current_interval_price_rating",
                "price_level",
                "volatility",
                "best_price",
                "peak_price",
                "price_trend",
                "chart_data_export",
                "reset_to_defaults",
                "finish",
            ],
        )

    async def async_step_reset_to_defaults(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Reset all settings to factory defaults."""
        if user_input is not None:
            # Check if user confirmed the reset
            if user_input.get("confirm_reset", False):
                # Get currency from config_entry.data (this is immutable and safe)
                currency_code = self.config_entry.data.get("currency", None)

                # Completely replace options with fresh defaults (factory reset)
                # This discards ALL old data including legacy structures
                self._options = get_default_options(currency_code)

                # Force save the new options
                self._save_options_if_changed()

                _LOGGER.info(
                    "Factory reset performed for config entry '%s' - all settings restored to defaults",
                    self.config_entry.title,
                )

                # Show success message and return to menu
                return self.async_abort(reason="reset_successful")

            # User didn't check the box - they want to cancel
            # Show info message (not error) and return to menu
            return self.async_abort(reason="reset_cancelled")

        # Show confirmation form with checkbox
        return self.async_show_form(
            step_id="reset_to_defaults",
            data_schema=get_reset_to_defaults_schema(),
        )

    async def async_step_finish(self, _user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Close the options flow."""
        # Use empty reason to close without any message
        return self.async_abort(reason="finished")

    async def async_step_general_settings(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Configure general settings."""
        if user_input is not None:
            # Update options with new values
            self._options.update(user_input)
            # Save options only if changed (triggers listeners automatically)
            self._save_options_if_changed()
            # Return to menu for more changes
            return await self.async_step_init()

        return self.async_show_form(
            step_id="general_settings",
            data_schema=get_options_init_schema(self.config_entry.options),
            description_placeholders={
                "user_login": self.config_entry.data.get("user_login", "N/A"),
            },
        )

    async def async_step_display_settings(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Configure currency display settings."""
        # Get currency from coordinator data (if available)
        # During options flow setup, integration might not be fully loaded yet
        currency_code = None
        if DOMAIN in self.hass.data and self.config_entry.entry_id in self.hass.data[DOMAIN]:
            tibber_data = self.hass.data[DOMAIN][self.config_entry.entry_id]
            if tibber_data.coordinator.data:
                currency_code = tibber_data.coordinator.data.get("currency")

        if user_input is not None:
            # Update options with new values
            self._options.update(user_input)
            # async_create_entry automatically handles change detection and listener triggering
            self._save_options_if_changed()
            # Return to menu for more changes
            return await self.async_step_init()

        return self.async_show_form(
            step_id="display_settings",
            data_schema=get_display_settings_schema(self.config_entry.options, currency_code),
        )

    async def async_step_current_interval_price_rating(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure price rating thresholds."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Schema is now flattened - fields come directly in user_input
            # But we still need to store them in nested structure for coordinator

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
            if not errors:
                # Get current values directly from options (now flat)
                low_val = user_input.get(
                    CONF_PRICE_RATING_THRESHOLD_LOW, self._options.get(CONF_PRICE_RATING_THRESHOLD_LOW, -10)
                )
                high_val = user_input.get(
                    CONF_PRICE_RATING_THRESHOLD_HIGH, self._options.get(CONF_PRICE_RATING_THRESHOLD_HIGH, 10)
                )
                if not validate_price_rating_thresholds(low_val, high_val):
                    # This should never happen given the range constraints, but add error for safety
                    errors["base"] = "invalid_price_rating_thresholds"

            if not errors:
                # Store flat data directly in options (no section wrapping)
                self._options.update(user_input)
                # async_create_entry automatically handles change detection and listener triggering
                self._save_options_if_changed()
            # Return to menu for more changes
            return await self.async_step_init()

        return self.async_show_form(
            step_id="current_interval_price_rating",
            data_schema=get_price_rating_schema(self.config_entry.options),
            errors=errors,
        )

    async def async_step_price_level(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Configure Tibber price level gap tolerance (smoothing for API 'level' field)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # No validation needed - slider constraints ensure valid range
            # Store flat data directly in options
            self._options.update(user_input)
            # async_create_entry automatically handles change detection and listener triggering
            self._save_options_if_changed()
            # Return to menu for more changes
            return await self.async_step_init()

        return self.async_show_form(
            step_id="price_level",
            data_schema=get_price_level_schema(self.config_entry.options),
            errors=errors,
        )

    async def async_step_best_price(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Configure best price period settings."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Extract settings from sections
            period_settings = user_input.get("period_settings", {})
            flexibility_settings = user_input.get("flexibility_settings", {})
            relaxation_settings = user_input.get("relaxation_and_target_periods", {})

            # Validate period length
            if CONF_BEST_PRICE_MIN_PERIOD_LENGTH in period_settings and not validate_period_length(
                period_settings[CONF_BEST_PRICE_MIN_PERIOD_LENGTH]
            ):
                errors[CONF_BEST_PRICE_MIN_PERIOD_LENGTH] = "invalid_period_length"

            # Validate flex percentage
            if CONF_BEST_PRICE_FLEX in flexibility_settings and not validate_flex_percentage(
                flexibility_settings[CONF_BEST_PRICE_FLEX]
            ):
                errors[CONF_BEST_PRICE_FLEX] = "invalid_flex"

            # Validate distance from average (Best Price uses negative values)
            if (
                CONF_BEST_PRICE_MIN_DISTANCE_FROM_AVG in flexibility_settings
                and not validate_best_price_distance_percentage(
                    flexibility_settings[CONF_BEST_PRICE_MIN_DISTANCE_FROM_AVG]
                )
            ):
                errors[CONF_BEST_PRICE_MIN_DISTANCE_FROM_AVG] = "invalid_best_price_distance"

            # Validate minimum periods count
            if CONF_MIN_PERIODS_BEST in relaxation_settings and not validate_min_periods(
                relaxation_settings[CONF_MIN_PERIODS_BEST]
            ):
                errors[CONF_MIN_PERIODS_BEST] = "invalid_min_periods"

            # Validate gap count
            if CONF_BEST_PRICE_MAX_LEVEL_GAP_COUNT in period_settings and not validate_gap_count(
                period_settings[CONF_BEST_PRICE_MAX_LEVEL_GAP_COUNT]
            ):
                errors[CONF_BEST_PRICE_MAX_LEVEL_GAP_COUNT] = "invalid_gap_count"

            # Validate relaxation attempts
            if CONF_RELAXATION_ATTEMPTS_BEST in relaxation_settings and not validate_relaxation_attempts(
                relaxation_settings[CONF_RELAXATION_ATTEMPTS_BEST]
            ):
                errors[CONF_RELAXATION_ATTEMPTS_BEST] = "invalid_relaxation_attempts"

            if not errors:
                # Merge section data into options
                self._merge_section_data(user_input)
                # async_create_entry automatically handles change detection and listener triggering
                self._save_options_if_changed()
            # Return to menu for more changes
            return await self.async_step_init()

        return self.async_show_form(
            step_id="best_price",
            data_schema=get_best_price_schema(self.config_entry.options),
            errors=errors,
        )

    async def async_step_peak_price(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Configure peak price period settings."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Extract settings from sections
            period_settings = user_input.get("period_settings", {})
            flexibility_settings = user_input.get("flexibility_settings", {})
            relaxation_settings = user_input.get("relaxation_and_target_periods", {})

            # Validate period length
            if CONF_PEAK_PRICE_MIN_PERIOD_LENGTH in period_settings and not validate_period_length(
                period_settings[CONF_PEAK_PRICE_MIN_PERIOD_LENGTH]
            ):
                errors[CONF_PEAK_PRICE_MIN_PERIOD_LENGTH] = "invalid_period_length"

            # Validate flex percentage (peak uses negative values)
            if CONF_PEAK_PRICE_FLEX in flexibility_settings and not validate_flex_percentage(
                flexibility_settings[CONF_PEAK_PRICE_FLEX]
            ):
                errors[CONF_PEAK_PRICE_FLEX] = "invalid_flex"

            # Validate distance from average (Peak Price uses positive values)
            if CONF_PEAK_PRICE_MIN_DISTANCE_FROM_AVG in flexibility_settings and not validate_distance_percentage(
                flexibility_settings[CONF_PEAK_PRICE_MIN_DISTANCE_FROM_AVG]
            ):
                errors[CONF_PEAK_PRICE_MIN_DISTANCE_FROM_AVG] = "invalid_peak_price_distance"

            # Validate minimum periods count
            if CONF_MIN_PERIODS_PEAK in relaxation_settings and not validate_min_periods(
                relaxation_settings[CONF_MIN_PERIODS_PEAK]
            ):
                errors[CONF_MIN_PERIODS_PEAK] = "invalid_min_periods"

            # Validate gap count
            if CONF_PEAK_PRICE_MAX_LEVEL_GAP_COUNT in period_settings and not validate_gap_count(
                period_settings[CONF_PEAK_PRICE_MAX_LEVEL_GAP_COUNT]
            ):
                errors[CONF_PEAK_PRICE_MAX_LEVEL_GAP_COUNT] = "invalid_gap_count"

            # Validate relaxation attempts
            if CONF_RELAXATION_ATTEMPTS_PEAK in relaxation_settings and not validate_relaxation_attempts(
                relaxation_settings[CONF_RELAXATION_ATTEMPTS_PEAK]
            ):
                errors[CONF_RELAXATION_ATTEMPTS_PEAK] = "invalid_relaxation_attempts"

            if not errors:
                # Merge section data into options
                self._merge_section_data(user_input)
                # async_create_entry automatically handles change detection and listener triggering
                self._save_options_if_changed()
            # Return to menu for more changes
            return await self.async_step_init()

        return self.async_show_form(
            step_id="peak_price",
            data_schema=get_peak_price_schema(self.config_entry.options),
            errors=errors,
        )

    async def async_step_price_trend(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Configure price trend thresholds."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Schema is now flattened - fields come directly in user_input
            # Store them flat in options (no nested structure)

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

            # Validate strongly rising trend threshold
            if CONF_PRICE_TREND_THRESHOLD_STRONGLY_RISING in user_input and not validate_price_trend_strongly_rising(
                user_input[CONF_PRICE_TREND_THRESHOLD_STRONGLY_RISING]
            ):
                errors[CONF_PRICE_TREND_THRESHOLD_STRONGLY_RISING] = "invalid_price_trend_strongly_rising"

            # Validate strongly falling trend threshold
            if CONF_PRICE_TREND_THRESHOLD_STRONGLY_FALLING in user_input and not validate_price_trend_strongly_falling(
                user_input[CONF_PRICE_TREND_THRESHOLD_STRONGLY_FALLING]
            ):
                errors[CONF_PRICE_TREND_THRESHOLD_STRONGLY_FALLING] = "invalid_price_trend_strongly_falling"

            # Cross-validation: Ensure rising < strongly_rising and falling > strongly_falling
            if not errors:
                rising = user_input.get(CONF_PRICE_TREND_THRESHOLD_RISING)
                strongly_rising = user_input.get(CONF_PRICE_TREND_THRESHOLD_STRONGLY_RISING)
                falling = user_input.get(CONF_PRICE_TREND_THRESHOLD_FALLING)
                strongly_falling = user_input.get(CONF_PRICE_TREND_THRESHOLD_STRONGLY_FALLING)

                if rising is not None and strongly_rising is not None and rising >= strongly_rising:
                    errors[CONF_PRICE_TREND_THRESHOLD_STRONGLY_RISING] = (
                        "invalid_trend_strongly_rising_less_than_rising"
                    )
                if falling is not None and strongly_falling is not None and falling <= strongly_falling:
                    errors[CONF_PRICE_TREND_THRESHOLD_STRONGLY_FALLING] = (
                        "invalid_trend_strongly_falling_greater_than_falling"
                    )

            if not errors:
                # Store flat data directly in options (no section wrapping)
                self._options.update(user_input)
                # async_create_entry automatically handles change detection and listener triggering
                self._save_options_if_changed()
            # Return to menu for more changes
            return await self.async_step_init()

        return self.async_show_form(
            step_id="price_trend",
            data_schema=get_price_trend_schema(self.config_entry.options),
            errors=errors,
        )

    async def async_step_chart_data_export(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Info page for chart data export sensor."""
        if user_input is not None:
            # No changes to save - just return to menu
            return await self.async_step_init()

        # Show info-only form (no input fields)
        return self.async_show_form(
            step_id="chart_data_export",
            data_schema=get_chart_data_export_schema(self.config_entry.options),
        )

    async def async_step_volatility(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Configure volatility thresholds and period filtering."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Schema is now flattened - fields come directly in user_input

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
                # Get current values directly from options (now flat)
                moderate = user_input.get(
                    CONF_VOLATILITY_THRESHOLD_MODERATE,
                    self._options.get(CONF_VOLATILITY_THRESHOLD_MODERATE, DEFAULT_VOLATILITY_THRESHOLD_MODERATE),
                )
                high = user_input.get(
                    CONF_VOLATILITY_THRESHOLD_HIGH,
                    self._options.get(CONF_VOLATILITY_THRESHOLD_HIGH, DEFAULT_VOLATILITY_THRESHOLD_HIGH),
                )
                very_high = user_input.get(
                    CONF_VOLATILITY_THRESHOLD_VERY_HIGH,
                    self._options.get(CONF_VOLATILITY_THRESHOLD_VERY_HIGH, DEFAULT_VOLATILITY_THRESHOLD_VERY_HIGH),
                )

                if not validate_volatility_thresholds(moderate, high, very_high):
                    errors["base"] = "invalid_volatility_thresholds"

            if not errors:
                # Store flat data directly in options (no section wrapping)
                self._options.update(user_input)
                # async_create_entry automatically handles change detection and listener triggering
                self._save_options_if_changed()
            # Return to menu for more changes
            return await self.async_step_init()

        return self.async_show_form(
            step_id="volatility",
            data_schema=get_volatility_schema(self.config_entry.options),
            errors=errors,
        )
