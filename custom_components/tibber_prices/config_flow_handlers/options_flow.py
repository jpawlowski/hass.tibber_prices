"""Options flow for tibber_prices integration."""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from custom_components.tibber_prices.config_flow_handlers.schemas import (
    get_best_price_schema,
    get_chart_data_export_schema,
    get_options_init_schema,
    get_peak_price_schema,
    get_price_rating_schema,
    get_price_trend_schema,
    get_volatility_schema,
)
from custom_components.tibber_prices.const import DOMAIN
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
            self._options = dict(self.config_entry.options)

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
        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_volatility()

        return self.async_show_form(
            step_id="current_interval_price_rating",
            data_schema=get_price_rating_schema(self.config_entry.options),
            description_placeholders=self._get_step_description_placeholders("current_interval_price_rating"),
        )

    async def async_step_best_price(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Configure best price period settings."""
        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_peak_price()

        return self.async_show_form(
            step_id="best_price",
            data_schema=get_best_price_schema(self.config_entry.options),
            description_placeholders=self._get_step_description_placeholders("best_price"),
        )

    async def async_step_peak_price(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Configure peak price period settings."""
        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_price_trend()

        return self.async_show_form(
            step_id="peak_price",
            data_schema=get_peak_price_schema(self.config_entry.options),
            description_placeholders=self._get_step_description_placeholders("peak_price"),
        )

    async def async_step_price_trend(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Configure price trend thresholds."""
        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_chart_data_export()

        return self.async_show_form(
            step_id="price_trend",
            data_schema=get_price_trend_schema(self.config_entry.options),
            description_placeholders=self._get_step_description_placeholders("price_trend"),
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
        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_best_price()

        return self.async_show_form(
            step_id="volatility",
            data_schema=get_volatility_schema(self.config_entry.options),
            description_placeholders=self._get_step_description_placeholders("volatility"),
        )
