"""
Type definitions for Tibber Prices sensor attributes.

These TypedDict definitions serve as **documentation** of the attribute structure
for each sensor type. They enable IDE autocomplete and type checking when working
with attribute dictionaries.

NOTE: In function signatures, we still use dict[str, Any] for flexibility,
but these TypedDict definitions document what keys and types are expected.

IMPORTANT: The Literal types defined here should be kept in sync with the
string constants in const.py, which are the single source of truth for runtime values.
"""

from __future__ import annotations

from typing import Literal, TypedDict

# ============================================================================
# Literal Type Definitions
# ============================================================================
# SYNC: Keep these in sync with constants in const.py
#
# const.py defines the runtime constants (single source of truth):
#   - PRICE_LEVEL_VERY_CHEAP, PRICE_LEVEL_CHEAP, etc.
#   - PRICE_RATING_LOW, PRICE_RATING_NORMAL, etc.
#   - VOLATILITY_LOW, VOLATILITY_MODERATE, etc.
#
# These Literal types should mirror those constants for type safety.

# Price level literals (from Tibber API)
PriceLevel = Literal[
    "VERY_CHEAP",
    "CHEAP",
    "NORMAL",
    "EXPENSIVE",
    "VERY_EXPENSIVE",
]

# Price rating literals (calculated values)
PriceRating = Literal[
    "LOW",
    "NORMAL",
    "HIGH",
]

# Volatility level literals (based on coefficient of variation)
VolatilityLevel = Literal[
    "LOW",
    "MODERATE",
    "HIGH",
    "VERY_HIGH",
]

# Data completeness literals
DataCompleteness = Literal[
    "complete",
    "partial_yesterday",
    "partial_today",
    "partial_tomorrow",
    "missing_yesterday",
    "missing_today",
    "missing_tomorrow",
]


# ============================================================================
# TypedDict Definitions
# ============================================================================


class BaseAttributes(TypedDict, total=False):
    """
    Base attributes common to all sensors.

    All sensor attributes include at minimum:
    - timestamp: ISO 8601 string indicating when the state/attributes are valid
    - error: Optional error message if something went wrong
    """

    timestamp: str
    error: str


class IntervalPriceAttributes(BaseAttributes, total=False):
    """
    Attributes for interval price sensors (current/next/previous).

    These sensors show price information for a specific 15-minute interval.
    """

    level_value: int  # Numeric value for price level (1-5)
    level_id: PriceLevel  # String identifier for price level
    icon_color: str  # Optional icon color based on level


class IntervalLevelAttributes(BaseAttributes, total=False):
    """
    Attributes for interval level sensors.

    These sensors show the price level classification for an interval.
    """

    icon_color: str  # Icon color based on level


class IntervalRatingAttributes(BaseAttributes, total=False):
    """
    Attributes for interval rating sensors.

    These sensors show the price rating (LOW/NORMAL/HIGH) for an interval.
    """

    rating_value: int  # Numeric value for price rating (1-3)
    rating_id: PriceRating  # String identifier for price rating
    icon_color: str  # Optional icon color based on rating


class RollingHourAttributes(BaseAttributes, total=False):
    """
    Attributes for rolling hour sensors.

    These sensors aggregate data across 5 intervals (2 before + current + 2 after).
    """

    icon_color: str  # Optional icon color based on aggregated level


class DailyStatPriceAttributes(BaseAttributes, total=False):
    """
    Attributes for daily statistics price sensors (min/max/avg).

    These sensors show price statistics for a full calendar day.
    """

    # No additional attributes for daily price stats beyond base


class DailyStatRatingAttributes(BaseAttributes, total=False):
    """
    Attributes for daily statistics rating sensors.

    These sensors show rating statistics for a full calendar day.
    """

    diff_percent: str  # Key is actually "diff_%" - percentage difference
    level_id: PriceRating  # Rating level identifier
    level_value: int  # Numeric rating value (1-3)


class Window24hAttributes(BaseAttributes, total=False):
    """
    Attributes for 24-hour window sensors (trailing/leading).

    These sensors analyze price data across a 24-hour window from current time.
    """

    interval_count: int  # Number of intervals in the window


class VolatilityAttributes(BaseAttributes, total=False):
    """
    Attributes for volatility sensors.

    These sensors analyze price variation and spread across time periods.
    """

    today_spread: float  # Price range for today (max - min)
    today_volatility: str  # Volatility level for today
    interval_count_today: int  # Number of intervals analyzed today
    tomorrow_spread: float  # Price range for tomorrow (max - min)
    tomorrow_volatility: str  # Volatility level for tomorrow
    interval_count_tomorrow: int  # Number of intervals analyzed tomorrow


class TrendAttributes(BaseAttributes, total=False):
    """
    Attributes for trend sensors.

    These sensors analyze price trends and forecast future movements.
    Trend attributes are complex and may vary based on trend type.
    """

    # Trend attributes are dynamic and vary by sensor type
    # Keep flexible with total=False


class TimingAttributes(BaseAttributes, total=False):
    """
    Attributes for period timing sensors (best_price/peak_price timing).

    These sensors track timing information for best/peak price periods.
    """

    icon_color: str  # Icon color based on timing status


class FutureAttributes(BaseAttributes, total=False):
    """
    Attributes for future forecast sensors.

    These sensors provide N-hour forecasts starting from next interval.
    """

    interval_count: int  # Number of intervals in forecast
    hours: int  # Number of hours in forecast window


class LifecycleAttributes(BaseAttributes, total=False):
    """
    Attributes for lifecycle/diagnostic sensors.

    These sensors provide system information and cache status.
    """

    cache_age: str  # Human-readable cache age
    cache_age_minutes: int  # Cache age in minutes
    cache_validity: str  # Cache validity status
    last_api_fetch: str  # ISO 8601 timestamp of last API fetch
    last_cache_update: str  # ISO 8601 timestamp of last cache update
    data_completeness: DataCompleteness  # Data completeness status
    yesterday_available: bool  # Whether yesterday data exists
    today_available: bool  # Whether today data exists
    tomorrow_available: bool  # Whether tomorrow data exists
    tomorrow_expected_after: str  # Time when tomorrow data expected
    next_api_poll: str  # ISO 8601 timestamp of next API poll
    next_midnight_turnover: str  # ISO 8601 timestamp of next midnight turnover
    updates_today: int  # Number of API updates today
    last_turnover: str  # ISO 8601 timestamp of last midnight turnover
    last_error: str  # Last error message if any


class MetadataAttributes(BaseAttributes, total=False):
    """
    Attributes for metadata sensors (home info, metering point).

    These sensors provide Tibber account and home metadata.
    Metadata attributes vary by sensor type.
    """

    # Metadata attributes are dynamic and vary by sensor type
    # Keep flexible with total=False


# Union type for all sensor attributes (for documentation purposes)
# In actual code, use dict[str, Any] for flexibility
SensorAttributes = (
    IntervalPriceAttributes
    | IntervalLevelAttributes
    | IntervalRatingAttributes
    | RollingHourAttributes
    | DailyStatPriceAttributes
    | DailyStatRatingAttributes
    | Window24hAttributes
    | VolatilityAttributes
    | TrendAttributes
    | TimingAttributes
    | FutureAttributes
    | LifecycleAttributes
    | MetadataAttributes
)
