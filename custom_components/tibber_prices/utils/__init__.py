"""
Pure data transformation utilities for Tibber Prices integration.

This package contains stateless, pure functions for data processing:
- Time-window calculations (trailing/leading averages, min/max)
- Price enrichment (differences, volatility, rating levels)
- Statistical analysis (aggregation, trends)

These functions operate on raw data structures (dicts, lists) and do NOT depend on:
- Home Assistant entities or state management
- Configuration entries or coordinators
- Translation systems or UI-specific logic

For entity-specific utilities (icons, colors, attributes), see entity_utils/ package.
"""

from __future__ import annotations

from .average import (
    calculate_current_leading_max,
    calculate_current_leading_mean,
    calculate_current_leading_min,
    calculate_current_trailing_max,
    calculate_current_trailing_mean,
    calculate_current_trailing_min,
    calculate_mean,
    calculate_median,
    calculate_next_n_hours_mean,
)
from .price import (
    aggregate_period_levels,
    aggregate_period_ratings,
    aggregate_price_levels,
    aggregate_price_rating,
    calculate_coefficient_of_variation,
    calculate_difference_percentage,
    calculate_price_trend,
    calculate_rating_level,
    calculate_trailing_average_for_interval,
    calculate_volatility_level,
    calculate_volatility_with_cv,
    enrich_price_info_with_differences,
    find_price_data_for_interval,
)

__all__ = [
    "aggregate_period_levels",
    "aggregate_period_ratings",
    "aggregate_price_levels",
    "aggregate_price_rating",
    "calculate_coefficient_of_variation",
    "calculate_current_leading_max",
    "calculate_current_leading_mean",
    "calculate_current_leading_min",
    "calculate_current_trailing_max",
    "calculate_current_trailing_mean",
    "calculate_current_trailing_min",
    "calculate_difference_percentage",
    "calculate_mean",
    "calculate_median",
    "calculate_next_n_hours_mean",
    "calculate_price_trend",
    "calculate_rating_level",
    "calculate_trailing_average_for_interval",
    "calculate_volatility_level",
    "calculate_volatility_with_cv",
    "enrich_price_info_with_differences",
    "find_price_data_for_interval",
]
