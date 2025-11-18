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

# Constants
MINUTES_PER_INTERVAL = 15

# Log indentation levels for visual hierarchy
INDENT_L0 = ""  # Top level (calculate_periods_with_relaxation)
INDENT_L1 = "  "  # Per-day loop
INDENT_L2 = "    "  # Flex/filter loop (_relax_single_day)
INDENT_L3 = "      "  # _resolve_period_overlaps function
INDENT_L4 = "        "  # Period-by-period analysis
INDENT_L5 = "          "  # Segment details


class PeriodConfig(NamedTuple):
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


class PeriodData(NamedTuple):
    """Data for building a period summary."""

    start_time: datetime
    end_time: datetime
    period_length: int
    period_idx: int
    total_periods: int


class PeriodStatistics(NamedTuple):
    """Calculated statistics for a period."""

    aggregated_level: str | None
    aggregated_rating: str | None
    rating_difference_pct: float | None
    price_avg: float
    price_min: float
    price_max: float
    price_spread: float
    volatility: str
    period_price_diff: float | None
    period_price_diff_pct: float | None


class ThresholdConfig(NamedTuple):
    """Threshold configuration for period calculations."""

    threshold_low: float | None
    threshold_high: float | None
    threshold_volatility_moderate: float
    threshold_volatility_high: float
    threshold_volatility_very_high: float
    reverse_sort: bool


class IntervalCriteria(NamedTuple):
    """Criteria for checking if an interval qualifies for a period."""

    ref_price: float
    avg_price: float
    flex: float
    min_distance_from_avg: float
    reverse_sort: bool
