"""
Sensor platform-specific helper functions.

This module contains helper functions specific to the sensor platform:
- aggregate_price_data: Calculate average price from window data
- aggregate_level_data: Aggregate price levels from intervals
- aggregate_rating_data: Aggregate price ratings from intervals

For shared helper functions (used by both sensor and binary_sensor platforms),
see entity_utils/helpers.py:
- get_price_value: Price unit conversion
- find_rolling_hour_center_index: Rolling hour window calculations
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.tibber_prices.const import (
    get_display_unit_factor,
    get_price_round_decimals,
)
from custom_components.tibber_prices.utils.average import calculate_mean, calculate_median
from custom_components.tibber_prices.utils.price import (
    aggregate_price_levels,
    aggregate_price_rating,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry


def aggregate_average_data(
    window_data: list[dict],
    config_entry: ConfigEntry,
) -> tuple[float | None, float | None]:
    """
    Calculate average and median price from window data.

    Args:
        window_data: List of price interval dictionaries with 'total' key.
        config_entry: Config entry to get display unit configuration.

    Returns:
        Tuple of (average price, median price) in display currency units,
        or (None, None) if no prices.

    """
    prices = [float(i["total"]) for i in window_data if "total" in i]
    if not prices:
        return None, None
    # Calculate both mean and median
    mean = calculate_mean(prices)
    median = calculate_median(prices)
    # Convert to display currency unit based on configuration
    factor = get_display_unit_factor(config_entry)
    decimals = get_price_round_decimals(config_entry)
    return round(mean * factor, decimals), round(median * factor, decimals) if median is not None else None


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
