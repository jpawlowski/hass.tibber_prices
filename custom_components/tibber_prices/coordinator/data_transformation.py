"""Data transformation and enrichment logic for the coordinator."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from custom_components.tibber_prices import const as _const
from custom_components.tibber_prices.price_utils import enrich_price_info_with_differences
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)


class DataTransformer:
    """Handles data transformation, enrichment, and period calculations."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        log_prefix: str,
        perform_turnover_fn: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> None:
        """Initialize the data transformer."""
        self.config_entry = config_entry
        self._log_prefix = log_prefix
        self._perform_turnover_fn = perform_turnover_fn

        # Transformation cache
        self._cached_transformed_data: dict[str, Any] | None = None
        self._last_transformation_config: dict[str, Any] | None = None
        self._last_midnight_check: datetime | None = None
        self._config_cache: dict[str, Any] | None = None
        self._config_cache_valid = False

    def _log(self, level: str, message: str, *args: object, **kwargs: object) -> None:
        """Log with coordinator-specific prefix."""
        prefixed_message = f"{self._log_prefix} {message}"
        getattr(_LOGGER, level)(prefixed_message, *args, **kwargs)

    def get_threshold_percentages(self) -> dict[str, int]:
        """Get threshold percentages from config options."""
        options = self.config_entry.options or {}
        return {
            "low": options.get(_const.CONF_PRICE_RATING_THRESHOLD_LOW, _const.DEFAULT_PRICE_RATING_THRESHOLD_LOW),
            "high": options.get(_const.CONF_PRICE_RATING_THRESHOLD_HIGH, _const.DEFAULT_PRICE_RATING_THRESHOLD_HIGH),
        }

    def invalidate_config_cache(self) -> None:
        """Invalidate config cache when options change."""
        self._config_cache_valid = False
        self._config_cache = None
        self._log("debug", "Config cache invalidated")

    def _get_current_transformation_config(self) -> dict[str, Any]:
        """
        Get current configuration that affects data transformation.

        Uses cached config to avoid ~30 options.get() calls on every update check.
        Cache is invalidated when config_entry.options change.
        """
        if self._config_cache_valid and self._config_cache is not None:
            return self._config_cache

        # Build config dictionary (expensive operation)
        config = {
            "thresholds": self.get_threshold_percentages(),
            "volatility_thresholds": {
                "moderate": self.config_entry.options.get(_const.CONF_VOLATILITY_THRESHOLD_MODERATE, 15.0),
                "high": self.config_entry.options.get(_const.CONF_VOLATILITY_THRESHOLD_HIGH, 25.0),
                "very_high": self.config_entry.options.get(_const.CONF_VOLATILITY_THRESHOLD_VERY_HIGH, 40.0),
            },
            "best_price_config": {
                "flex": self.config_entry.options.get(_const.CONF_BEST_PRICE_FLEX, 15.0),
                "max_level": self.config_entry.options.get(_const.CONF_BEST_PRICE_MAX_LEVEL, "NORMAL"),
                "min_period_length": self.config_entry.options.get(_const.CONF_BEST_PRICE_MIN_PERIOD_LENGTH, 4),
                "min_distance_from_avg": self.config_entry.options.get(
                    _const.CONF_BEST_PRICE_MIN_DISTANCE_FROM_AVG, -5.0
                ),
                "max_level_gap_count": self.config_entry.options.get(_const.CONF_BEST_PRICE_MAX_LEVEL_GAP_COUNT, 0),
                "enable_min_periods": self.config_entry.options.get(_const.CONF_ENABLE_MIN_PERIODS_BEST, False),
                "min_periods": self.config_entry.options.get(_const.CONF_MIN_PERIODS_BEST, 2),
                "relaxation_step": self.config_entry.options.get(_const.CONF_RELAXATION_STEP_BEST, 5.0),
                "relaxation_attempts": self.config_entry.options.get(_const.CONF_RELAXATION_ATTEMPTS_BEST, 4),
            },
            "peak_price_config": {
                "flex": self.config_entry.options.get(_const.CONF_PEAK_PRICE_FLEX, 15.0),
                "min_level": self.config_entry.options.get(_const.CONF_PEAK_PRICE_MIN_LEVEL, "HIGH"),
                "min_period_length": self.config_entry.options.get(_const.CONF_PEAK_PRICE_MIN_PERIOD_LENGTH, 4),
                "min_distance_from_avg": self.config_entry.options.get(
                    _const.CONF_PEAK_PRICE_MIN_DISTANCE_FROM_AVG, 5.0
                ),
                "max_level_gap_count": self.config_entry.options.get(_const.CONF_PEAK_PRICE_MAX_LEVEL_GAP_COUNT, 0),
                "enable_min_periods": self.config_entry.options.get(_const.CONF_ENABLE_MIN_PERIODS_PEAK, False),
                "min_periods": self.config_entry.options.get(_const.CONF_MIN_PERIODS_PEAK, 2),
                "relaxation_step": self.config_entry.options.get(_const.CONF_RELAXATION_STEP_PEAK, 5.0),
                "relaxation_attempts": self.config_entry.options.get(_const.CONF_RELAXATION_ATTEMPTS_PEAK, 4),
            },
        }

        # Cache for future calls
        self._config_cache = config
        self._config_cache_valid = True
        return config

    def _should_retransform_data(self, current_time: datetime) -> bool:
        """Check if data transformation should be performed."""
        # No cached transformed data - must transform
        if self._cached_transformed_data is None:
            return True

        # Configuration changed - must retransform
        current_config = self._get_current_transformation_config()
        if current_config != self._last_transformation_config:
            self._log("debug", "Configuration changed, retransforming data")
            return True

        # Check for midnight turnover
        now_local = dt_util.as_local(current_time)
        current_date = now_local.date()

        if self._last_midnight_check is None:
            return True

        last_check_local = dt_util.as_local(self._last_midnight_check)
        last_check_date = last_check_local.date()

        if current_date != last_check_date:
            self._log("debug", "Midnight turnover detected, retransforming data")
            return True

        return False

    def transform_data_for_main_entry(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Transform raw data for main entry (aggregated view of all homes)."""
        current_time = dt_util.now()

        # Return cached transformed data if no retransformation needed
        if not self._should_retransform_data(current_time) and self._cached_transformed_data is not None:
            self._log("debug", "Using cached transformed data (no transformation needed)")
            return self._cached_transformed_data

        self._log("debug", "Transforming price data (enrichment only, periods cached separately)")

        # For main entry, we can show data from the first home as default
        # or provide an aggregated view
        homes_data = raw_data.get("homes", {})
        if not homes_data:
            return {
                "timestamp": raw_data.get("timestamp"),
                "homes": {},
                "priceInfo": {},
            }

        # Use the first home's data as the main entry's data
        first_home_data = next(iter(homes_data.values()))
        price_info = first_home_data.get("price_info", {})

        # Perform midnight turnover if needed (handles day transitions)
        price_info = self._perform_turnover_fn(price_info)

        # Ensure all required keys exist (API might not return tomorrow data yet)
        price_info.setdefault("yesterday", [])
        price_info.setdefault("today", [])
        price_info.setdefault("tomorrow", [])
        price_info.setdefault("currency", "EUR")

        # Enrich price info dynamically with calculated differences and rating levels
        # This ensures enrichment is always up-to-date, especially after midnight turnover
        thresholds = self.get_threshold_percentages()
        price_info = enrich_price_info_with_differences(
            price_info,
            threshold_low=thresholds["low"],
            threshold_high=thresholds["high"],
        )

        # Note: Periods are calculated and cached separately by PeriodCalculator
        # to avoid redundant caching (periods were cached twice before)

        transformed_data = {
            "timestamp": raw_data.get("timestamp"),
            "homes": homes_data,
            "priceInfo": price_info,
        }

        # Cache the transformed data
        self._cached_transformed_data = transformed_data
        self._last_transformation_config = self._get_current_transformation_config()
        self._last_midnight_check = current_time

        return transformed_data

    def transform_data_for_subentry(self, main_data: dict[str, Any], home_id: str) -> dict[str, Any]:
        """Transform main coordinator data for subentry (home-specific view)."""
        current_time = dt_util.now()

        # Return cached transformed data if no retransformation needed
        if not self._should_retransform_data(current_time) and self._cached_transformed_data is not None:
            self._log("debug", "Using cached transformed data (no transformation needed)")
            return self._cached_transformed_data

        self._log("debug", "Transforming price data for home (enrichment only, periods cached separately)")

        if not home_id:
            return main_data

        homes_data = main_data.get("homes", {})
        home_data = homes_data.get(home_id, {})

        if not home_data:
            return {
                "timestamp": main_data.get("timestamp"),
                "priceInfo": {},
            }

        price_info = home_data.get("price_info", {})

        # Perform midnight turnover if needed (handles day transitions)
        price_info = self._perform_turnover_fn(price_info)

        # Ensure all required keys exist (API might not return tomorrow data yet)
        price_info.setdefault("yesterday", [])
        price_info.setdefault("today", [])
        price_info.setdefault("tomorrow", [])
        price_info.setdefault("currency", "EUR")

        # Enrich price info dynamically with calculated differences and rating levels
        # This ensures enrichment is always up-to-date, especially after midnight turnover
        thresholds = self.get_threshold_percentages()
        price_info = enrich_price_info_with_differences(
            price_info,
            threshold_low=thresholds["low"],
            threshold_high=thresholds["high"],
        )

        # Note: Periods are calculated and cached separately by PeriodCalculator
        # to avoid redundant caching (periods were cached twice before)

        transformed_data = {
            "timestamp": main_data.get("timestamp"),
            "priceInfo": price_info,
        }

        # Cache the transformed data
        self._cached_transformed_data = transformed_data
        self._last_transformation_config = self._get_current_transformation_config()
        self._last_midnight_check = current_time

        return transformed_data

    def invalidate_cache(self) -> None:
        """Invalidate transformation cache."""
        self._cached_transformed_data = None

    @property
    def last_midnight_check(self) -> datetime | None:
        """Get last midnight check timestamp."""
        return self._last_midnight_check

    @last_midnight_check.setter
    def last_midnight_check(self, value: datetime | None) -> None:
        """Set last midnight check timestamp."""
        self._last_midnight_check = value
