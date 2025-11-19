"""
Period calculation logic for the coordinator.

This module handles all period calculation including level filtering,
gap tolerance, and coordination of the period_handlers calculation functions.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from custom_components.tibber_prices import const as _const

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator.time_service import TimeService

from .period_handlers import (
    PeriodConfig,
    calculate_periods_with_relaxation,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)


class PeriodCalculator:
    """Handles period calculations with level filtering and gap tolerance."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        log_prefix: str,
    ) -> None:
        """Initialize the period calculator."""
        self.config_entry = config_entry
        self._log_prefix = log_prefix
        self.time: TimeService  # Set by coordinator before first use
        self._config_cache: dict[str, dict[str, Any]] | None = None
        self._config_cache_valid = False

        # Period calculation cache
        self._cached_periods: dict[str, Any] | None = None
        self._last_periods_hash: str | None = None

    def _log(self, level: str, message: str, *args: object, **kwargs: object) -> None:
        """Log with calculator-specific prefix."""
        prefixed_message = f"{self._log_prefix} {message}"
        getattr(_LOGGER, level)(prefixed_message, *args, **kwargs)

    def invalidate_config_cache(self) -> None:
        """Invalidate config cache when options change."""
        self._config_cache_valid = False
        self._config_cache = None
        # Also invalidate period calculation cache when config changes
        self._cached_periods = None
        self._last_periods_hash = None
        self._log("debug", "Period config cache and calculation cache invalidated")

    def _compute_periods_hash(self, price_info: dict[str, Any]) -> str:
        """
        Compute hash of price data and config for period calculation caching.

        Only includes data that affects period calculation:
        - Today's interval timestamps and enriched rating levels
        - Period calculation config (flex, min_distance, min_period_length)
        - Level filter overrides

        Returns:
            Hash string for cache key comparison.

        """
        # Get relevant price data
        today = price_info.get("today", [])
        today_signature = tuple((interval.get("startsAt"), interval.get("rating_level")) for interval in today)

        # Get period configs (both best and peak)
        best_config = self.get_period_config(reverse_sort=False)
        peak_config = self.get_period_config(reverse_sort=True)

        # Get level filter overrides from options
        options = self.config_entry.options
        best_level_filter = options.get(_const.CONF_BEST_PRICE_MAX_LEVEL, _const.DEFAULT_BEST_PRICE_MAX_LEVEL)
        peak_level_filter = options.get(_const.CONF_PEAK_PRICE_MIN_LEVEL, _const.DEFAULT_PEAK_PRICE_MIN_LEVEL)

        # Compute hash from all relevant data
        hash_data = (
            today_signature,
            tuple(best_config.items()),
            tuple(peak_config.items()),
            best_level_filter,
            peak_level_filter,
        )
        return str(hash(hash_data))

    def get_period_config(self, *, reverse_sort: bool) -> dict[str, Any]:
        """
        Get period calculation configuration from config options.

        Uses cached config to avoid multiple options.get() calls.
        Cache is invalidated when config_entry.options change.
        """
        cache_key = "peak" if reverse_sort else "best"

        # Return cached config if available
        if self._config_cache_valid and self._config_cache is not None and cache_key in self._config_cache:
            return self._config_cache[cache_key]

        # Build config (cache miss)
        if self._config_cache is None:
            self._config_cache = {}

        options = self.config_entry.options
        data = self.config_entry.data

        if reverse_sort:
            # Peak price configuration
            flex = options.get(
                _const.CONF_PEAK_PRICE_FLEX, data.get(_const.CONF_PEAK_PRICE_FLEX, _const.DEFAULT_PEAK_PRICE_FLEX)
            )
            min_distance_from_avg = options.get(
                _const.CONF_PEAK_PRICE_MIN_DISTANCE_FROM_AVG,
                data.get(_const.CONF_PEAK_PRICE_MIN_DISTANCE_FROM_AVG, _const.DEFAULT_PEAK_PRICE_MIN_DISTANCE_FROM_AVG),
            )
            min_period_length = options.get(
                _const.CONF_PEAK_PRICE_MIN_PERIOD_LENGTH,
                data.get(_const.CONF_PEAK_PRICE_MIN_PERIOD_LENGTH, _const.DEFAULT_PEAK_PRICE_MIN_PERIOD_LENGTH),
            )
        else:
            # Best price configuration
            flex = options.get(
                _const.CONF_BEST_PRICE_FLEX, data.get(_const.CONF_BEST_PRICE_FLEX, _const.DEFAULT_BEST_PRICE_FLEX)
            )
            min_distance_from_avg = options.get(
                _const.CONF_BEST_PRICE_MIN_DISTANCE_FROM_AVG,
                data.get(_const.CONF_BEST_PRICE_MIN_DISTANCE_FROM_AVG, _const.DEFAULT_BEST_PRICE_MIN_DISTANCE_FROM_AVG),
            )
            min_period_length = options.get(
                _const.CONF_BEST_PRICE_MIN_PERIOD_LENGTH,
                data.get(_const.CONF_BEST_PRICE_MIN_PERIOD_LENGTH, _const.DEFAULT_BEST_PRICE_MIN_PERIOD_LENGTH),
            )

        # Convert flex from percentage to decimal (e.g., 5 -> 0.05)
        try:
            flex = float(flex) / 100
        except (TypeError, ValueError):
            flex = _const.DEFAULT_BEST_PRICE_FLEX / 100 if not reverse_sort else _const.DEFAULT_PEAK_PRICE_FLEX / 100

        config = {
            "flex": flex,
            "min_distance_from_avg": float(min_distance_from_avg),
            "min_period_length": int(min_period_length),
        }

        # Cache the result
        self._config_cache[cache_key] = config
        self._config_cache_valid = True
        return config

    def should_show_periods(
        self,
        price_info: dict[str, Any],
        *,
        reverse_sort: bool,
        level_override: str | None = None,
    ) -> bool:
        """
        Check if periods should be shown based on level filter only.

        Args:
            price_info: Price information dict with today/yesterday/tomorrow data
            reverse_sort: If False (best_price), checks max_level filter.
                         If True (peak_price), checks min_level filter.
            level_override: Optional override for level filter ("any" to disable)

        Returns:
            True if periods should be displayed, False if they should be filtered out.

        """
        # Only check level filter (day-level check: "does today have any qualifying intervals?")
        return self.check_level_filter(
            price_info,
            reverse_sort=reverse_sort,
            override=level_override,
        )

    def split_at_gap_clusters(
        self,
        today_intervals: list[dict[str, Any]],
        level_order: int,
        min_period_length: int,
        *,
        reverse_sort: bool,
    ) -> list[list[dict[str, Any]]]:
        """
        Split intervals into sub-sequences at gap clusters.

        A gap cluster is 2+ consecutive intervals that don't meet the level requirement.
        This allows recovering usable periods from sequences that would otherwise be rejected.

        Args:
            today_intervals: List of price intervals for today
            level_order: Required level order from _const.PRICE_LEVEL_MAPPING
            min_period_length: Minimum number of intervals required for a valid sub-sequence
            reverse_sort: True for peak price, False for best price

        Returns:
            List of sub-sequences, each at least min_period_length long.

        """
        sub_sequences = []
        current_sequence = []
        consecutive_non_qualifying = 0

        for interval in today_intervals:
            interval_level = _const.PRICE_LEVEL_MAPPING.get(interval.get("level", "NORMAL"), 0)
            meets_requirement = interval_level >= level_order if reverse_sort else interval_level <= level_order

            if meets_requirement:
                # Qualifying interval - add to current sequence
                current_sequence.append(interval)
                consecutive_non_qualifying = 0
            elif consecutive_non_qualifying == 0:
                # First non-qualifying interval (single gap) - add to current sequence
                current_sequence.append(interval)
                consecutive_non_qualifying = 1
            else:
                # Second+ consecutive non-qualifying interval = gap cluster starts
                # Save current sequence if long enough (excluding the first gap we just added)
                if len(current_sequence) - 1 >= min_period_length:
                    sub_sequences.append(current_sequence[:-1])  # Exclude the first gap
                current_sequence = []
                consecutive_non_qualifying = 0

        # Don't forget last sequence
        if len(current_sequence) >= min_period_length:
            sub_sequences.append(current_sequence)

        return sub_sequences

    def check_short_period_strict(
        self,
        today_intervals: list[dict[str, Any]],
        level_order: int,
        *,
        reverse_sort: bool,
    ) -> bool:
        """
        Strict filtering for short periods (< 1.5h) without gap tolerance.

        All intervals must meet the requirement perfectly, or at least one does
        and all others are exact matches.

        Args:
            today_intervals: List of price intervals for today
            level_order: Required level order from _const.PRICE_LEVEL_MAPPING
            reverse_sort: True for peak price, False for best price

        Returns:
            True if all intervals meet requirement (with at least one qualifying), False otherwise.

        """
        has_qualifying = False
        for interval in today_intervals:
            interval_level = _const.PRICE_LEVEL_MAPPING.get(interval.get("level", "NORMAL"), 0)
            meets_requirement = interval_level >= level_order if reverse_sort else interval_level <= level_order
            if meets_requirement:
                has_qualifying = True
            elif interval_level != level_order:
                # Any deviation in short periods disqualifies the entire sequence
                return False
        return has_qualifying

    def check_level_filter_with_gaps(
        self,
        today_intervals: list[dict[str, Any]],
        level_order: int,
        max_gap_count: int,
        *,
        reverse_sort: bool,
    ) -> bool:
        """
        Check if intervals meet level requirements with gap tolerance and minimum distance.

        A "gap" is an interval that deviates by exactly 1 level step.
        For best price: CHEAP allows NORMAL as gap (but not EXPENSIVE).
        For peak price: EXPENSIVE allows NORMAL as gap (but not CHEAP).

        Gap tolerance is only applied to periods with at least _const.MIN_INTERVALS_FOR_GAP_TOLERANCE
        intervals (1.5h). Shorter periods use strict filtering (zero tolerance).

        Between gaps, there must be a minimum number of "good" intervals to prevent
        periods that are mostly interrupted by gaps.

        Args:
            today_intervals: List of price intervals for today
            level_order: Required level order from _const.PRICE_LEVEL_MAPPING
            max_gap_count: Maximum total gaps allowed
            reverse_sort: True for peak price, False for best price

        Returns:
            True if any qualifying sequence exists, False otherwise.

        """
        if not today_intervals:
            return False

        interval_count = len(today_intervals)

        # Periods shorter than _const.MIN_INTERVALS_FOR_GAP_TOLERANCE (1.5h) use strict filtering
        if interval_count < _const.MIN_INTERVALS_FOR_GAP_TOLERANCE:
            period_type = "peak" if reverse_sort else "best"
            self._log(
                "debug",
                "Using strict filtering for short %s period (%d intervals < %d min required for gap tolerance)",
                period_type,
                interval_count,
                _const.MIN_INTERVALS_FOR_GAP_TOLERANCE,
            )
            return self.check_short_period_strict(today_intervals, level_order, reverse_sort=reverse_sort)

        # Try normal gap tolerance check first
        if self.check_sequence_with_gap_tolerance(
            today_intervals, level_order, max_gap_count, reverse_sort=reverse_sort
        ):
            return True

        # Normal check failed - try splitting at gap clusters as fallback
        # Get minimum period length from config (convert minutes to intervals)
        if reverse_sort:
            min_period_minutes = self.config_entry.options.get(
                _const.CONF_PEAK_PRICE_MIN_PERIOD_LENGTH,
                _const.DEFAULT_PEAK_PRICE_MIN_PERIOD_LENGTH,
            )
        else:
            min_period_minutes = self.config_entry.options.get(
                _const.CONF_BEST_PRICE_MIN_PERIOD_LENGTH,
                _const.DEFAULT_BEST_PRICE_MIN_PERIOD_LENGTH,
            )

        min_period_intervals = self.time.minutes_to_intervals(min_period_minutes)

        sub_sequences = self.split_at_gap_clusters(
            today_intervals,
            level_order,
            min_period_intervals,
            reverse_sort=reverse_sort,
        )

        # Check if ANY sub-sequence passes gap tolerance
        for sub_seq in sub_sequences:
            if self.check_sequence_with_gap_tolerance(sub_seq, level_order, max_gap_count, reverse_sort=reverse_sort):
                return True

        return False

    def check_sequence_with_gap_tolerance(
        self,
        intervals: list[dict[str, Any]],
        level_order: int,
        max_gap_count: int,
        *,
        reverse_sort: bool,
    ) -> bool:
        """
        Check if a single interval sequence passes gap tolerance requirements.

        This is the core gap tolerance logic extracted for reuse with sub-sequences.

        Args:
            intervals: List of price intervals to check
            level_order: Required level order from _const.PRICE_LEVEL_MAPPING
            max_gap_count: Maximum total gaps allowed
            reverse_sort: True for peak price, False for best price

        Returns:
            True if sequence meets all gap tolerance requirements, False otherwise.

        """
        if not intervals:
            return False

        interval_count = len(intervals)

        # Calculate minimum distance between gaps dynamically.
        # Shorter periods require relatively larger distances.
        # Longer periods allow gaps closer together.
        # Distance is never less than 2 intervals between gaps.
        min_distance_between_gaps = max(2, (interval_count // max_gap_count) // 2)

        # Limit total gaps to max 25% of period length to prevent too many outliers.
        # This ensures periods remain predominantly "good" even when long.
        effective_max_gaps = min(max_gap_count, interval_count // 4)

        gap_count = 0
        consecutive_good_count = 0
        has_qualifying_interval = False

        for interval in intervals:
            interval_level = _const.PRICE_LEVEL_MAPPING.get(interval.get("level", "NORMAL"), 0)

            # Check if interval meets the strict requirement
            meets_requirement = interval_level >= level_order if reverse_sort else interval_level <= level_order

            if meets_requirement:
                has_qualifying_interval = True
                consecutive_good_count += 1
                continue

            # Check if this is a tolerable gap (exactly 1 step deviation)
            is_tolerable_gap = interval_level == level_order - 1 if reverse_sort else interval_level == level_order + 1

            if is_tolerable_gap:
                # If we already had gaps, check minimum distance
                if gap_count > 0 and consecutive_good_count < min_distance_between_gaps:
                    # Not enough "good" intervals between gaps
                    return False

                gap_count += 1
                if gap_count > effective_max_gaps:
                    return False

                # Reset counter for next gap
                consecutive_good_count = 0
            else:
                # Too far from required level (more than 1 step deviation)
                return False

        return has_qualifying_interval

    def check_level_filter(
        self,
        price_info: dict[str, Any],
        *,
        reverse_sort: bool,
        override: str | None = None,
    ) -> bool:
        """
        Check if today has any intervals that meet the level requirement with gap tolerance.

        Gap tolerance allows a configurable number of intervals within a qualifying sequence
        to deviate by one level step (e.g., CHEAP allows NORMAL, but not EXPENSIVE).

        Args:
            price_info: Price information dict with today data
            reverse_sort: If False (best_price), checks max_level (upper bound filter).
                         If True (peak_price), checks min_level (lower bound filter).
            override: Optional override value (e.g., "any" to disable filter)

        Returns:
            True if ANY sequence of intervals meets the level requirement
            (considering gap tolerance), False otherwise.

        """
        # Use override if provided
        if override is not None:
            level_config = override
        # Get appropriate config based on sensor type
        elif reverse_sort:
            # Peak price: minimum level filter (lower bound)
            level_config = self.config_entry.options.get(
                _const.CONF_PEAK_PRICE_MIN_LEVEL,
                _const.DEFAULT_PEAK_PRICE_MIN_LEVEL,
            )
        else:
            # Best price: maximum level filter (upper bound)
            level_config = self.config_entry.options.get(
                _const.CONF_BEST_PRICE_MAX_LEVEL,
                _const.DEFAULT_BEST_PRICE_MAX_LEVEL,
            )

        # "any" means no level filtering
        if level_config == "any":
            return True

        # Get today's intervals
        today_intervals = price_info.get("today", [])

        if not today_intervals:
            return True  # If no data, don't filter

        # Get gap tolerance configuration
        if reverse_sort:
            max_gap_count = self.config_entry.options.get(
                _const.CONF_PEAK_PRICE_MAX_LEVEL_GAP_COUNT,
                _const.DEFAULT_PEAK_PRICE_MAX_LEVEL_GAP_COUNT,
            )
        else:
            max_gap_count = self.config_entry.options.get(
                _const.CONF_BEST_PRICE_MAX_LEVEL_GAP_COUNT,
                _const.DEFAULT_BEST_PRICE_MAX_LEVEL_GAP_COUNT,
            )

        # Note: level_config is lowercase from selector, but _const.PRICE_LEVEL_MAPPING uses uppercase
        level_order = _const.PRICE_LEVEL_MAPPING.get(level_config.upper(), 0)

        # If gap tolerance is 0, use simple ANY check (backwards compatible)
        if max_gap_count == 0:
            if reverse_sort:
                # Peak price: level >= min_level (show if ANY interval is expensive enough)
                return any(
                    _const.PRICE_LEVEL_MAPPING.get(interval.get("level", "NORMAL"), 0) >= level_order
                    for interval in today_intervals
                )
            # Best price: level <= max_level (show if ANY interval is cheap enough)
            return any(
                _const.PRICE_LEVEL_MAPPING.get(interval.get("level", "NORMAL"), 0) <= level_order
                for interval in today_intervals
            )

        # Use gap-tolerant check
        return self.check_level_filter_with_gaps(
            today_intervals,
            level_order,
            max_gap_count,
            reverse_sort=reverse_sort,
        )

    def calculate_periods_for_price_info(
        self,
        price_info: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Calculate periods (best price and peak price) for the given price info.

        Applies volatility and level filtering based on user configuration.
        If filters don't match, returns empty period lists.

        Uses hash-based caching to avoid recalculating periods when price data
        and configuration haven't changed (~70% performance improvement).
        """
        # Check if we can use cached periods
        current_hash = self._compute_periods_hash(price_info)
        if self._cached_periods is not None and self._last_periods_hash == current_hash:
            self._log("debug", "Using cached period calculation results (hash match)")
            return self._cached_periods

        self._log("debug", "Calculating periods (cache miss or hash mismatch)")

        yesterday_prices = price_info.get("yesterday", [])
        today_prices = price_info.get("today", [])
        tomorrow_prices = price_info.get("tomorrow", [])
        all_prices = yesterday_prices + today_prices + tomorrow_prices

        # Get rating thresholds from config
        threshold_low = self.config_entry.options.get(
            _const.CONF_PRICE_RATING_THRESHOLD_LOW,
            _const.DEFAULT_PRICE_RATING_THRESHOLD_LOW,
        )
        threshold_high = self.config_entry.options.get(
            _const.CONF_PRICE_RATING_THRESHOLD_HIGH,
            _const.DEFAULT_PRICE_RATING_THRESHOLD_HIGH,
        )

        # Get volatility thresholds from config
        threshold_volatility_moderate = self.config_entry.options.get(
            _const.CONF_VOLATILITY_THRESHOLD_MODERATE,
            _const.DEFAULT_VOLATILITY_THRESHOLD_MODERATE,
        )
        threshold_volatility_high = self.config_entry.options.get(
            _const.CONF_VOLATILITY_THRESHOLD_HIGH,
            _const.DEFAULT_VOLATILITY_THRESHOLD_HIGH,
        )
        threshold_volatility_very_high = self.config_entry.options.get(
            _const.CONF_VOLATILITY_THRESHOLD_VERY_HIGH,
            _const.DEFAULT_VOLATILITY_THRESHOLD_VERY_HIGH,
        )

        # Get relaxation configuration for best price
        enable_relaxation_best = self.config_entry.options.get(
            _const.CONF_ENABLE_MIN_PERIODS_BEST,
            _const.DEFAULT_ENABLE_MIN_PERIODS_BEST,
        )

        # Check if best price periods should be shown
        # If relaxation is enabled, always calculate (relaxation will try "any" filter)
        # If relaxation is disabled, apply level filter check
        if enable_relaxation_best:
            show_best_price = bool(all_prices)
        else:
            show_best_price = self.should_show_periods(price_info, reverse_sort=False) if all_prices else False
        min_periods_best = self.config_entry.options.get(
            _const.CONF_MIN_PERIODS_BEST,
            _const.DEFAULT_MIN_PERIODS_BEST,
        )
        relaxation_attempts_best = self.config_entry.options.get(
            _const.CONF_RELAXATION_ATTEMPTS_BEST,
            _const.DEFAULT_RELAXATION_ATTEMPTS_BEST,
        )

        # Calculate best price periods (or return empty if filtered)
        if show_best_price:
            best_config = self.get_period_config(reverse_sort=False)
            # Get level filter configuration
            max_level_best = self.config_entry.options.get(
                _const.CONF_BEST_PRICE_MAX_LEVEL,
                _const.DEFAULT_BEST_PRICE_MAX_LEVEL,
            )
            gap_count_best = self.config_entry.options.get(
                _const.CONF_BEST_PRICE_MAX_LEVEL_GAP_COUNT,
                _const.DEFAULT_BEST_PRICE_MAX_LEVEL_GAP_COUNT,
            )
            best_period_config = PeriodConfig(
                reverse_sort=False,
                flex=best_config["flex"],
                min_distance_from_avg=best_config["min_distance_from_avg"],
                min_period_length=best_config["min_period_length"],
                threshold_low=threshold_low,
                threshold_high=threshold_high,
                threshold_volatility_moderate=threshold_volatility_moderate,
                threshold_volatility_high=threshold_volatility_high,
                threshold_volatility_very_high=threshold_volatility_very_high,
                level_filter=max_level_best,
                gap_count=gap_count_best,
            )
            best_periods, best_relaxation = calculate_periods_with_relaxation(
                all_prices,
                config=best_period_config,
                enable_relaxation=enable_relaxation_best,
                min_periods=min_periods_best,
                max_relaxation_attempts=relaxation_attempts_best,
                should_show_callback=lambda lvl: self.should_show_periods(
                    price_info,
                    reverse_sort=False,
                    level_override=lvl,
                ),
                time=self.time,
            )
        else:
            best_periods = {
                "periods": [],
                "intervals": [],
                "metadata": {"total_intervals": 0, "total_periods": 0, "config": {}},
            }
            best_relaxation = {"relaxation_active": False, "relaxation_attempted": False}

        # Get relaxation configuration for peak price
        enable_relaxation_peak = self.config_entry.options.get(
            _const.CONF_ENABLE_MIN_PERIODS_PEAK,
            _const.DEFAULT_ENABLE_MIN_PERIODS_PEAK,
        )

        # Check if peak price periods should be shown
        # If relaxation is enabled, always calculate (relaxation will try "any" filter)
        # If relaxation is disabled, apply level filter check
        if enable_relaxation_peak:
            show_peak_price = bool(all_prices)
        else:
            show_peak_price = self.should_show_periods(price_info, reverse_sort=True) if all_prices else False
        min_periods_peak = self.config_entry.options.get(
            _const.CONF_MIN_PERIODS_PEAK,
            _const.DEFAULT_MIN_PERIODS_PEAK,
        )
        relaxation_attempts_peak = self.config_entry.options.get(
            _const.CONF_RELAXATION_ATTEMPTS_PEAK,
            _const.DEFAULT_RELAXATION_ATTEMPTS_PEAK,
        )

        # Calculate peak price periods (or return empty if filtered)
        if show_peak_price:
            peak_config = self.get_period_config(reverse_sort=True)
            # Get level filter configuration
            min_level_peak = self.config_entry.options.get(
                _const.CONF_PEAK_PRICE_MIN_LEVEL,
                _const.DEFAULT_PEAK_PRICE_MIN_LEVEL,
            )
            gap_count_peak = self.config_entry.options.get(
                _const.CONF_PEAK_PRICE_MAX_LEVEL_GAP_COUNT,
                _const.DEFAULT_PEAK_PRICE_MAX_LEVEL_GAP_COUNT,
            )
            peak_period_config = PeriodConfig(
                reverse_sort=True,
                flex=peak_config["flex"],
                min_distance_from_avg=peak_config["min_distance_from_avg"],
                min_period_length=peak_config["min_period_length"],
                threshold_low=threshold_low,
                threshold_high=threshold_high,
                threshold_volatility_moderate=threshold_volatility_moderate,
                threshold_volatility_high=threshold_volatility_high,
                threshold_volatility_very_high=threshold_volatility_very_high,
                level_filter=min_level_peak,
                gap_count=gap_count_peak,
            )
            peak_periods, peak_relaxation = calculate_periods_with_relaxation(
                all_prices,
                config=peak_period_config,
                enable_relaxation=enable_relaxation_peak,
                min_periods=min_periods_peak,
                max_relaxation_attempts=relaxation_attempts_peak,
                should_show_callback=lambda lvl: self.should_show_periods(
                    price_info,
                    reverse_sort=True,
                    level_override=lvl,
                ),
                time=self.time,
            )
        else:
            peak_periods = {
                "periods": [],
                "intervals": [],
                "metadata": {"total_intervals": 0, "total_periods": 0, "config": {}},
            }
            peak_relaxation = {"relaxation_active": False, "relaxation_attempted": False}

        result = {
            "best_price": best_periods,
            "best_price_relaxation": best_relaxation,
            "peak_price": peak_periods,
            "peak_price_relaxation": peak_relaxation,
        }

        # Cache the result
        self._cached_periods = result
        self._last_periods_hash = current_hash

        return result
