"""Type definitions and constants for period calculation."""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple, TypedDict

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

# Low absolute price threshold for quality gate bypass (in major currency unit, e.g. EUR/NOK)
# When the MEAN price of a period is below this level, the CV quality gate is bypassed.
# Relative CV is unreliable at very low absolute prices: a range of 1-4 ct shows CV≈50%
# but is practically homogeneous from a cost perspective.
# Value: 10 ct / 100 = 0.10 EUR/NOK
LOW_PRICE_QUALITY_BYPASS_THRESHOLD = 0.10  # EUR/NOK major unit (= 10 ct/øre)

# Cross-Day Extension: Time window constants
# When a period ends late in the day and tomorrow data is available,
# we can extend it past midnight if prices remain favorable
CROSS_DAY_LATE_PERIOD_START_HOUR = 20  # Consider periods starting at 20:00 or later for extension
CROSS_DAY_MAX_EXTENSION_HOUR = 8  # Don't extend beyond 08:00 next day (covers typical night low)
CROSS_DAY_MAX_EXTENSION_INTERVALS = 16  # Hard cap: max 4 hours of extension (16 × 15-minute intervals)
CROSS_DAY_PROPORTIONAL_EXTENSION_FACTOR = 2.0  # Extension ≤ 2× original period length
CROSS_DAY_MAX_PRICE_DEVIATION = 0.15  # Stop if price deviates >15% from original period mean

# Cross-Day Supersession: When tomorrow data arrives, late-night periods that are
# worse than early-morning tomorrow periods become obsolete
# A today period is "superseded" if tomorrow has a significantly better alternative
SUPERSESSION_PRICE_IMPROVEMENT_PCT = 10.0  # Tomorrow must be at least 10% cheaper to supersede

# Peak Price Quality: Minimum premium above daily average to qualify as genuine peak
# A peak period whose mean price is barely above the daily average is likely a
# cross-day artifact rather than a genuine high-price window.
# Example: daily_avg=28ct, premium=10% → peak must average ≥ 30.8ct
PEAK_MIN_PREMIUM_ABOVE_AVG_PCT = 10.0  # Peak mean must be ≥ 10% above daily average

# Cross-Day Boundary Validation: overnight intervals must pass dual-day check
# For peak periods, intervals between 00:00 and this hour must ALSO qualify
# against the previous day's reference price. This prevents artifacts where
# overnight prices (e.g., 30ct) become "peak" against tomorrow's lower max
# but weren't peak against today's higher max.
CROSS_DAY_OVERNIGHT_VALIDATION_HOUR = 6  # Validate 00:00-05:59 against previous day too

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
    extend_to_extreme: bool = False  # Extend periods into adjacent VERY_CHEAP/VERY_EXPENSIVE intervals
    max_extension_intervals: int = 0  # Max intervals this extension may add per side (0 = disabled)
    geometric_extra_flex: float = 0.0  # Extra flex (decimal) for intervals inside the valley/peak zone (0.0 = disabled)
    segment_forcing: bool = False  # Force at least segment_min_periods in each W/M-shape segment
    segment_min_periods: int = 1  # Minimum periods required per segment when segment_forcing is True


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


# ─── Day pattern constants ─────────────────────────────────────────────────────

DAY_PATTERN_VALLEY = "valley"  # Single price minimum (U/V-shape)
DAY_PATTERN_PEAK = "peak"  # Single price maximum (Λ-shape)
DAY_PATTERN_DOUBLE_DIP = "double_dip"  # Two minima, W-shape
DAY_PATTERN_DUCK_CURVE = "duck_curve"  # Two peaks with midday valley (solar duck curve)
DAY_PATTERN_FLAT = "flat"  # No significant variation
DAY_PATTERN_RISING = "rising"  # Persistently rising throughout the day
DAY_PATTERN_FALLING = "falling"  # Persistently falling throughout the day
DAY_PATTERN_MIXED = "mixed"  # Multiple extrema with no clear pattern

# Ordered list used to populate SensorDeviceClass.ENUM options=
ALL_DAY_PATTERNS: list[str] = [
    DAY_PATTERN_VALLEY,
    DAY_PATTERN_PEAK,
    DAY_PATTERN_DOUBLE_DIP,
    DAY_PATTERN_DUCK_CURVE,
    DAY_PATTERN_FLAT,
    DAY_PATTERN_RISING,
    DAY_PATTERN_FALLING,
    DAY_PATTERN_MIXED,
]

# Segment type constants
DAY_SEGMENT_RISING = "rising"
DAY_SEGMENT_FALLING = "falling"
DAY_SEGMENT_FLAT = "flat"


# ─── Day pattern TypedDicts ────────────────────────────────────────────────────


class SegmentDict(TypedDict):
    """One monotone price segment within a calendar day."""

    type: str  # "rising" | "falling" | "flat"
    start: str | None  # ISO datetime of first interval in segment
    end: str | None  # ISO datetime of last interval in segment
    price_min: float  # Minimum price in segment
    price_max: float  # Maximum price in segment
    price_mean: float  # Mean price in segment


class DayPatternDict(TypedDict):
    """Detected price pattern for one calendar day."""

    pattern: str  # One of the DAY_PATTERN_* constants
    confidence: float  # 0.0 - 1.0
    day_cv_percent: float  # Coefficient of variation for the day (%)
    segments: list[SegmentDict]  # Monotone segments
    extreme_time: str | None  # ISO datetime of primary extremum (valley/peak)
    valley_start: str | None  # ISO datetime of left knee (VALLEY pattern only)
    valley_end: str | None  # ISO datetime of right knee (VALLEY pattern only)
    peak_start: str | None  # ISO datetime of left knee  (PEAK pattern only)
    peak_end: str | None  # ISO datetime of right knee (PEAK pattern only)
