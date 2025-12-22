"""Data transformation and enrichment logic for the coordinator."""

from __future__ import annotations

import copy
import logging
from typing import TYPE_CHECKING, Any

from custom_components.tibber_prices import const as _const
from custom_components.tibber_prices.utils.price import enrich_price_info_with_differences

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from homeassistant.config_entries import ConfigEntry

    from .time_service import TibberPricesTimeService

_LOGGER = logging.getLogger(__name__)


class TibberPricesDataTransformer:
    """Handles data transformation, enrichment, and period calculations."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        log_prefix: str,
        calculate_periods_fn: Callable[[dict[str, Any]], dict[str, Any]],
        time: TibberPricesTimeService,
    ) -> None:
        """Initialize the data transformer."""
        self.config_entry = config_entry
        self._log_prefix = log_prefix
        self._calculate_periods_fn = calculate_periods_fn
        self.time: TibberPricesTimeService = time

        # Transformation cache
        self._cached_transformed_data: dict[str, Any] | None = None
        self._last_transformation_config: dict[str, Any] | None = None
        self._last_midnight_check: datetime | None = None
        self._last_source_data_timestamp: datetime | None = None  # Track when source data changed
        self._config_cache: dict[str, Any] | None = None
        self._config_cache_valid = False

    def _log(self, level: str, message: str, *args: object, **kwargs: object) -> None:
        """Log with coordinator-specific prefix."""
        prefixed_message = f"{self._log_prefix} {message}"
        getattr(_LOGGER, level)(prefixed_message, *args, **kwargs)

    def get_threshold_percentages(self) -> dict[str, int | float]:
        """
        Get threshold percentages, hysteresis and gap tolerance for RATING_LEVEL from config options.

        CRITICAL: This function is ONLY for rating_level (internal calculation: LOW/NORMAL/HIGH).
        Do NOT use for price level (Tibber API: VERY_CHEAP/CHEAP/NORMAL/EXPENSIVE/VERY_EXPENSIVE).
        """
        options = self.config_entry.options or {}
        return {
            "low": options.get(_const.CONF_PRICE_RATING_THRESHOLD_LOW, _const.DEFAULT_PRICE_RATING_THRESHOLD_LOW),
            "high": options.get(_const.CONF_PRICE_RATING_THRESHOLD_HIGH, _const.DEFAULT_PRICE_RATING_THRESHOLD_HIGH),
            "hysteresis": options.get(_const.CONF_PRICE_RATING_HYSTERESIS, _const.DEFAULT_PRICE_RATING_HYSTERESIS),
            "gap_tolerance": options.get(
                _const.CONF_PRICE_RATING_GAP_TOLERANCE, _const.DEFAULT_PRICE_RATING_GAP_TOLERANCE
            ),
        }

    def get_level_gap_tolerance(self) -> int:
        """
        Get gap tolerance for PRICE LEVEL (Tibber API) from config options.

        CRITICAL: This is separate from rating_level gap tolerance.
        Price level comes from Tibber API (VERY_CHEAP/CHEAP/NORMAL/EXPENSIVE/VERY_EXPENSIVE).
        Rating level is calculated internally (LOW/NORMAL/HIGH).
        """
        options = self.config_entry.options or {}
        return options.get(_const.CONF_PRICE_LEVEL_GAP_TOLERANCE, _const.DEFAULT_PRICE_LEVEL_GAP_TOLERANCE)

    def invalidate_config_cache(self) -> None:
        """
        Invalidate config cache AND transformation cache when options change.

        CRITICAL: When options like gap_tolerance, hysteresis, or price_level_gap_tolerance
        change, we must clear BOTH caches:
        1. Config cache (_config_cache) - forces config rebuild on next check
        2. Transformation cache (_cached_transformed_data) - forces data re-enrichment

        This ensures that the next call to transform_data() will re-calculate
        rating_levels and apply new gap tolerance settings to existing price data.
        """
        self._config_cache_valid = False
        self._config_cache = None
        self._cached_transformed_data = None  # Force re-transformation with new config
        self._last_transformation_config = None  # Force config comparison to trigger

    def _get_current_transformation_config(self) -> dict[str, Any]:
        """
        Get current configuration that affects data transformation.

        Uses cached config to avoid ~30 options.get() calls on every update check.
        Cache is invalidated when config_entry.options change.
        """
        if self._config_cache_valid and self._config_cache is not None:
            return self._config_cache

        # Build config dictionary (expensive operation)
        options = self.config_entry.options

        # Best/peak price remain nested (multi-section steps)
        best_period_section = options.get("period_settings", {})
        best_flex_section = options.get("flexibility_settings", {})
        best_relax_section = options.get("relaxation_and_target_periods", {})
        peak_period_section = options.get("period_settings", {})
        peak_flex_section = options.get("flexibility_settings", {})
        peak_relax_section = options.get("relaxation_and_target_periods", {})

        config = {
            "thresholds": self.get_threshold_percentages(),
            "level_gap_tolerance": self.get_level_gap_tolerance(),  # Separate: Tibber's price level smoothing
            # Volatility thresholds now flat (single-section step)
            "volatility_thresholds": {
                "moderate": options.get(_const.CONF_VOLATILITY_THRESHOLD_MODERATE, 15.0),
                "high": options.get(_const.CONF_VOLATILITY_THRESHOLD_HIGH, 25.0),
                "very_high": options.get(_const.CONF_VOLATILITY_THRESHOLD_VERY_HIGH, 40.0),
            },
            # Price trend thresholds now flat (single-section step)
            "price_trend_thresholds": {
                "rising": options.get(
                    _const.CONF_PRICE_TREND_THRESHOLD_RISING, _const.DEFAULT_PRICE_TREND_THRESHOLD_RISING
                ),
                "falling": options.get(
                    _const.CONF_PRICE_TREND_THRESHOLD_FALLING, _const.DEFAULT_PRICE_TREND_THRESHOLD_FALLING
                ),
            },
            "best_price_config": {
                "flex": best_flex_section.get(_const.CONF_BEST_PRICE_FLEX, 15.0),
                "max_level": best_period_section.get(_const.CONF_BEST_PRICE_MAX_LEVEL, "NORMAL"),
                "min_period_length": best_period_section.get(_const.CONF_BEST_PRICE_MIN_PERIOD_LENGTH, 4),
                "min_distance_from_avg": best_flex_section.get(_const.CONF_BEST_PRICE_MIN_DISTANCE_FROM_AVG, -5.0),
                "max_level_gap_count": best_period_section.get(_const.CONF_BEST_PRICE_MAX_LEVEL_GAP_COUNT, 0),
                "enable_min_periods": best_relax_section.get(_const.CONF_ENABLE_MIN_PERIODS_BEST, False),
                "min_periods": best_relax_section.get(_const.CONF_MIN_PERIODS_BEST, 2),
                "relaxation_attempts": best_relax_section.get(_const.CONF_RELAXATION_ATTEMPTS_BEST, 4),
            },
            "peak_price_config": {
                "flex": peak_flex_section.get(_const.CONF_PEAK_PRICE_FLEX, 15.0),
                "min_level": peak_period_section.get(_const.CONF_PEAK_PRICE_MIN_LEVEL, "HIGH"),
                "min_period_length": peak_period_section.get(_const.CONF_PEAK_PRICE_MIN_PERIOD_LENGTH, 4),
                "min_distance_from_avg": peak_flex_section.get(_const.CONF_PEAK_PRICE_MIN_DISTANCE_FROM_AVG, 5.0),
                "max_level_gap_count": peak_period_section.get(_const.CONF_PEAK_PRICE_MAX_LEVEL_GAP_COUNT, 0),
                "enable_min_periods": peak_relax_section.get(_const.CONF_ENABLE_MIN_PERIODS_PEAK, False),
                "min_periods": peak_relax_section.get(_const.CONF_MIN_PERIODS_PEAK, 2),
                "relaxation_attempts": peak_relax_section.get(_const.CONF_RELAXATION_ATTEMPTS_PEAK, 4),
            },
        }

        # Cache for future calls
        self._config_cache = config
        self._config_cache_valid = True
        return config

    def _should_retransform_data(self, current_time: datetime, source_data_timestamp: datetime | None = None) -> bool:
        """
        Check if data transformation should be performed.

        Args:
            current_time: Current time for midnight check
            source_data_timestamp: Timestamp of source data (if available)

        Returns:
            True if retransformation needed, False if cached data can be used

        """
        # No cached transformed data - must transform
        if self._cached_transformed_data is None:
            return True

        # Source data changed - must retransform
        # This detects when new API data was fetched (e.g., tomorrow data arrival)
        if source_data_timestamp is not None and source_data_timestamp != self._last_source_data_timestamp:
            self._log("debug", "Source data changed, retransforming data")
            return True

        # Configuration changed - must retransform
        current_config = self._get_current_transformation_config()
        config_changed = current_config != self._last_transformation_config

        if config_changed:
            return True

        # Check for midnight turnover
        now_local = self.time.as_local(current_time)
        current_date = now_local.date()

        if self._last_midnight_check is None:
            return True

        last_check_local = self.time.as_local(self._last_midnight_check)
        last_check_date = last_check_local.date()

        if current_date != last_check_date:
            self._log("debug", "Midnight turnover detected, retransforming data")
            return True

        return False

    def transform_data(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Transform raw data for main entry (single home view)."""
        current_time = self.time.now()
        source_data_timestamp = raw_data.get("timestamp")

        # Return cached transformed data if no retransformation needed
        should_retransform = self._should_retransform_data(current_time, source_data_timestamp)
        has_cache = self._cached_transformed_data is not None

        self._log(
            "info",
            "transform_data: should_retransform=%s, has_cache=%s",
            should_retransform,
            has_cache,
        )

        if not should_retransform and has_cache:
            self._log("debug", "Using cached transformed data (no transformation needed)")
            return self._cached_transformed_data

        self._log("debug", "Transforming price data (enrichment + period calculation)")

        # Extract data from single-home structure
        home_id = raw_data.get("home_id", "")
        # CRITICAL: Make a deep copy of intervals to avoid modifying cached raw data
        # The enrichment function modifies intervals in-place, which would corrupt
        # the original API data and make re-enrichment with different settings impossible
        all_intervals = copy.deepcopy(raw_data.get("price_info", []))
        currency = raw_data.get("currency", "EUR")

        if not all_intervals:
            return {
                "timestamp": raw_data.get("timestamp"),
                "home_id": home_id,
                "priceInfo": [],
                "pricePeriods": {
                    "best_price": [],
                    "peak_price": [],
                },
                "currency": currency,
            }

        # Enrich price info dynamically with calculated differences and rating levels
        # (Modifies all_intervals in-place, returns same list)
        thresholds = self.get_threshold_percentages()  # Only for rating_level
        level_gap_tolerance = self.get_level_gap_tolerance()  # Separate: for Tibber's price level

        enriched_intervals = enrich_price_info_with_differences(
            all_intervals,
            threshold_low=thresholds["low"],
            threshold_high=thresholds["high"],
            hysteresis=float(thresholds["hysteresis"]),
            gap_tolerance=int(thresholds["gap_tolerance"]),
            level_gap_tolerance=level_gap_tolerance,
            time=self.time,
        )

        # Store enriched intervals directly as priceInfo (flat list)
        transformed_data = {
            "home_id": home_id,
            "priceInfo": enriched_intervals,
            "currency": currency,
        }

        # Calculate periods (best price and peak price)
        if "priceInfo" in transformed_data:
            transformed_data["pricePeriods"] = self._calculate_periods_fn(transformed_data["priceInfo"])

        # Cache the transformed data
        self._cached_transformed_data = transformed_data
        self._last_transformation_config = self._get_current_transformation_config()
        self._last_midnight_check = current_time
        self._last_source_data_timestamp = source_data_timestamp

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
