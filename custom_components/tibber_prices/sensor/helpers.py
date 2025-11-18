"""
Sensor platform-specific helper functions.

This module contains helper functions specific to the sensor platform:
- aggregate_price_data: Calculate average price from window data
- aggregate_level_data: Aggregate price levels from intervals
- aggregate_rating_data: Aggregate price ratings from intervals

For shared helper functions (used by both sensor and binary_sensor platforms),
see entity_utils/helpers.py:
- get_price_value: Price unit conversion
- translate_level: Price level translation
- translate_rating_level: Rating level translation
- find_rolling_hour_center_index: Rolling hour window calculations
"""

from __future__ import annotations

from custom_components.tibber_prices.utils.price import (
    aggregate_price_levels,
    aggregate_price_rating,
)


def aggregate_price_data(window_data: list[dict]) -> float | None:
    """
    Calculate average price from window data.

    Args:
        window_data: List of price interval dictionaries with 'total' key

    Returns:
        Average price in minor currency units (cents/øre), or None if no prices

    """
    prices = [float(i["total"]) for i in window_data if "total" in i]
    if not prices:
        return None
    # Return in minor currency units (cents/øre)
    return round((sum(prices) / len(prices)) * 100, 2)


def aggregate_level_data(window_data: list[dict]) -> str | None:
    """
    Aggregate price levels from window data.

    Args:
        window_data: List of price interval dictionaries with 'level' key

    Returns:
        Aggregated price level (lowercase), or None if no levels

    """
    levels = [i["level"] for i in window_data if "level" in i]
    if not levels:
        return None
    aggregated = aggregate_price_levels(levels)
    return aggregated.lower() if aggregated else None


def aggregate_rating_data(
    window_data: list[dict],
    threshold_low: float,
    threshold_high: float,
) -> str | None:
    """
    Aggregate price ratings from window data.

    Args:
        window_data: List of price interval dictionaries with 'difference' and 'rating_level'
        threshold_low: Low threshold for rating calculation
        threshold_high: High threshold for rating calculation

    Returns:
        Aggregated price rating (lowercase), or None if no ratings

    """
    differences = [i["difference"] for i in window_data if "difference" in i and "rating_level" in i]
    if not differences:
        return None

    aggregated, _ = aggregate_price_rating(differences, threshold_low, threshold_high)
    return aggregated.lower() if aggregated else None
