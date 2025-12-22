"""Type definitions and constants for period calculation."""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from datetime import datetime

from custom_components.tibber_prices.const import (
    DEFAULT_PRICE_RATING_THRESHOLD_HIGH,
    DEFAULT_PRICE_RATING_THRESHOLD_LOW,
    DEFAULT_VOLATILITY_THRESHOLD_HIGH,
    DEFAULT_VOLATILITY_THRESHOLD_MODERATE,
    DEFAULT_VOLATILITY_THRESHOLD_VERY_HIGH,
)

# Quality Gate: Maximum coefficient of variation (CV) allowed within a period
# Periods with internal CV above this are considered too heterogeneous for "best price"
# A 25% CV means the std dev is 25% of the mean - beyond this, prices vary too much
# Example: Period with prices 0.7-0.99 kr has ~15% CV which is acceptable
#          Period with prices 0.5-1.0 kr has ~30% CV which would be rejected
PERIOD_MAX_CV = 25.0  # 25% max coefficient of variation within a period

# Cross-Day Extension: Time window constants
# When a period ends late in the day and tomorrow data is available,
# we can extend it past midnight if prices remain favorable
CROSS_DAY_LATE_PERIOD_START_HOUR = 20  # Consider periods starting at 20:00 or later for extension
CROSS_DAY_MAX_EXTENSION_HOUR = 8  # Don't extend beyond 08:00 next day (covers typical night low)

# Cross-Day Supersession: When tomorrow data arrives, late-night periods that are
# worse than early-morning tomorrow periods become obsolete
# A today period is "superseded" if tomorrow has a significantly better alternative
SUPERSESSION_PRICE_IMPROVEMENT_PCT = 10.0  # Tomorrow must be at least 10% cheaper to supersede

# Log indentation levels for visual hierarchy
INDENT_L0 = ""  # Top level (calculate_periods_with_relaxation)
INDENT_L1 = "  "  # Per-day loop
INDENT_L2 = "    "  # Flex/filter loop (_relax_single_day)
INDENT_L3 = "      "  # _resolve_period_overlaps function
INDENT_L4 = "        "  # Period-by-period analysis
INDENT_L5 = "          "  # Segment details


class TibberPricesPeriodConfig(NamedTuple):
    """Configuration for period calculation."""

    reverse_sort: bool
    flex: float
    min_distance_from_avg: float
    min_period_length: int
    threshold_low: float = DEFAULT_PRICE_RATING_THRESHOLD_LOW
    threshold_high: float = DEFAULT_PRICE_RATING_THRESHOLD_HIGH
    threshold_volatility_moderate: float = DEFAULT_VOLATILITY_THRESHOLD_MODERATE
    threshold_volatility_high: float = DEFAULT_VOLATILITY_THRESHOLD_HIGH
    threshold_volatility_very_high: float = DEFAULT_VOLATILITY_THRESHOLD_VERY_HIGH
    level_filter: str | None = None  # "any", "cheap", "expensive", etc. or None
    gap_count: int = 0  # Number of allowed consecutive deviating intervals


class TibberPricesPeriodData(NamedTuple):
    """Data for building a period summary."""

    start_time: datetime
    end_time: datetime
    period_length: int
    period_idx: int
    total_periods: int


class TibberPricesPeriodStatistics(NamedTuple):
    """Calculated statistics for a period."""

    aggregated_level: str | None
    aggregated_rating: str | None
    rating_difference_pct: float | None
    price_mean: float
    price_median: float
    price_min: float
    price_max: float
    price_spread: float
    volatility: str
    coefficient_of_variation: float | None  # CV as percentage (e.g., 15.0 for 15%)
    period_price_diff: float | None
    period_price_diff_pct: float | None


class TibberPricesThresholdConfig(NamedTuple):
    """Threshold configuration for period calculations."""

    threshold_low: float | None
    threshold_high: float | None
    threshold_volatility_moderate: float
    threshold_volatility_high: float
    threshold_volatility_very_high: float
    reverse_sort: bool


class TibberPricesIntervalCriteria(NamedTuple):
    """Criteria for checking if an interval qualifies for a period."""

    ref_price: float
    avg_price: float
    flex: float
    min_distance_from_avg: float
    reverse_sort: bool
