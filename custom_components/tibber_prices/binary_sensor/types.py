"""
Type definitions for Tibber Prices binary sensor attributes.

These TypedDict definitions serve as **documentation** of the attribute structure
for each binary sensor type. They enable IDE autocomplete and type checking when
working with attribute dictionaries.

NOTE: In function signatures, we still use dict[str, Any] for flexibility,
but these TypedDict definitions document what keys and types are expected.

IMPORTANT: PriceLevel and PriceRating types are duplicated here to avoid
cross-platform dependencies. Keep in sync with sensor/types.py.
"""

from __future__ import annotations

from typing import Literal, TypedDict

# ============================================================================
# Literal Type Definitions (Duplicated from sensor/types.py)
# ============================================================================
# SYNC: Keep these in sync with:
#   1. sensor/types.py (Literal type definitions)
#   2. const.py (runtime string constants - single source of truth)
#
# const.py defines:
#   - PRICE_LEVEL_VERY_CHEAP, PRICE_LEVEL_CHEAP, etc.
#   - PRICE_RATING_LOW, PRICE_RATING_NORMAL, etc.
#
# These types are intentionally duplicated here to avoid cross-platform imports.
# Binary sensor attributes need these types for type safety without importing
# from sensor/ package (maintains platform separation).

# Price level literals (shared with sensor platform - keep in sync!)
PriceLevel = Literal[
    "VERY_CHEAP",
    "CHEAP",
    "NORMAL",
    "EXPENSIVE",
    "VERY_EXPENSIVE",
]

# Price rating literals (shared with sensor platform - keep in sync!)
PriceRating = Literal[
    "LOW",
    "NORMAL",
    "HIGH",
]


class BaseAttributes(TypedDict, total=False):
    """
    Base attributes common to all binary sensors.

    All binary sensor attributes include at minimum:
    - timestamp: ISO 8601 string indicating when the state/attributes are valid
    - error: Optional error message if something went wrong
    """

    timestamp: str
    error: str


class TomorrowDataAvailableAttributes(BaseAttributes, total=False):
    """
    Attributes for tomorrow_data_available binary sensor.

    Indicates whether tomorrow's price data is available from Tibber API.
    """

    intervals_available: int  # Number of intervals available for tomorrow
    data_status: Literal["none", "partial", "full"]  # Data completeness status


class PeriodSummary(TypedDict, total=False):
    """
    Structure for period summary nested in period attributes.

    Each period summary contains all calculated information about one period.
    """

    # Time information (priority 1)
    start: str  # ISO 8601 timestamp of period start
    end: str  # ISO 8601 timestamp of period end
    duration_minutes: int  # Duration in minutes

    # Core decision attributes (priority 2)
    level: PriceLevel  # Price level classification
    rating_level: PriceRating  # Price rating classification
    rating_difference_pct: float  # Difference from daily average (%)

    # Price statistics (priority 3)
    price_mean: float  # Arithmetic mean price in period
    price_median: float  # Median price in period
    price_min: float  # Minimum price in period
    price_max: float  # Maximum price in period
    price_spread: float  # Price spread (max - min)
    volatility: float  # Price volatility within period

    # Price comparison (priority 4)
    period_price_diff_from_daily_min: float  # Difference from daily min
    period_price_diff_from_daily_min_pct: float  # Difference from daily min (%)

    # Detail information (priority 5)
    period_interval_count: int  # Number of intervals in period
    period_position: int  # Period position (1-based)
    periods_total: int  # Total number of periods
    periods_remaining: int  # Remaining periods after this one

    # Relaxation information (priority 6 - only if period was relaxed)
    relaxation_active: bool  # Whether this period was found via relaxation
    relaxation_level: int  # Relaxation level used (1-based)
    relaxation_threshold_original_pct: float  # Original flex threshold (%)
    relaxation_threshold_applied_pct: float  # Applied flex threshold after relaxation (%)


class PeriodAttributes(BaseAttributes, total=False):
    """
    Attributes for period-based binary sensors (best_price_period, peak_price_period).

    These sensors indicate whether the current/next cheap/expensive period is active.

    Attributes follow priority ordering:
    1. Time information (timestamp, start, end, duration_minutes)
    2. Core decision attributes (level, rating_level, rating_difference_%)
    3. Price statistics (price_mean, price_median, price_min, price_max, price_spread, volatility)
    4. Price comparison (period_price_diff_from_daily_min, period_price_diff_from_daily_min_%)
    5. Detail information (period_interval_count, period_position, periods_total, periods_remaining)
    6. Relaxation information (only if period was relaxed)
    7. Meta information (periods list)
    """

    # Time information (priority 1) - start/end refer to current/next period
    start: str | None  # ISO 8601 timestamp of current/next period start
    end: str | None  # ISO 8601 timestamp of current/next period end
    duration_minutes: int  # Duration of current/next period in minutes

    # Core decision attributes (priority 2)
    level: PriceLevel  # Price level of current/next period
    rating_level: PriceRating  # Price rating of current/next period
    rating_difference_pct: float  # Difference from daily average (%)

    # Price statistics (priority 3)
    price_mean: float  # Arithmetic mean price in current/next period
    price_median: float  # Median price in current/next period
    price_min: float  # Minimum price in current/next period
    price_max: float  # Maximum price in current/next period
    price_spread: float  # Price spread (max - min) in current/next period
    volatility: float  # Price volatility within current/next period

    # Price comparison (priority 4)
    period_price_diff_from_daily_min: float  # Difference from daily min
    period_price_diff_from_daily_min_pct: float  # Difference from daily min (%)

    # Detail information (priority 5)
    period_interval_count: int  # Number of intervals in current/next period
    period_position: int  # Period position (1-based)
    periods_total: int  # Total number of periods found
    periods_remaining: int  # Remaining periods after current/next one

    # Relaxation information (priority 6 - only if period was relaxed)
    relaxation_active: bool  # Whether current/next period was found via relaxation
    relaxation_level: int  # Relaxation level used (1-based)
    relaxation_threshold_original_pct: float  # Original flex threshold (%)
    relaxation_threshold_applied_pct: float  # Applied flex threshold after relaxation (%)

    # Meta information (priority 7)
    periods: list[PeriodSummary]  # All periods found (sorted by start time)


# Union type for all binary sensor attributes (for documentation purposes)
# In actual code, use dict[str, Any] for flexibility
BinarySensorAttributes = TomorrowDataAvailableAttributes | PeriodAttributes
