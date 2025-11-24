"""
Sensor platform-specific helper functions.

This module contains helper functions specific to the sensor platform:
- aggregate_price_data: Calculate average price from window data
- aggregate_level_data: Aggregate price levels from intervals
- aggregate_rating_data: Aggregate price ratings from intervals
- aggregate_window_data: Unified aggregation based on value type
- get_hourly_price_value: Get price for specific hour with offset

For shared helper functions (used by both sensor and binary_sensor platforms),
see entity_utils/helpers.py:
- get_price_value: Price unit conversion
- translate_level: Price level translation
- translate_rating_level: Rating level translation
- find_rolling_hour_center_index: Rolling hour window calculations
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService

from custom_components.tibber_prices.coordinator.helpers import get_intervals_for_day_offsets
from custom_components.tibber_prices.entity_utils.helpers import get_price_value
from custom_components.tibber_prices.utils.price import (
    aggregate_price_levels,
    aggregate_price_rating,
)

if TYPE_CHECKING:
    from collections.abc import Callable


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


def aggregate_window_data(
    window_data: list[dict],
    value_type: str,
    threshold_low: float,
    threshold_high: float,
) -> str | float | None:
    """
    Aggregate data from multiple intervals based on value type.

    Unified helper that routes to appropriate aggregation function.

    Args:
        window_data: List of price interval dictionaries
        value_type: Type of value to aggregate ('price', 'level', or 'rating')
        threshold_low: Low threshold for rating calculation
        threshold_high: High threshold for rating calculation

    Returns:
        Aggregated value (price as float, level/rating as str), or None if no data

    """
    # Map value types to aggregation functions
    aggregators: dict[str, Callable] = {
        "price": lambda data: aggregate_price_data(data),
        "level": lambda data: aggregate_level_data(data),
        "rating": lambda data: aggregate_rating_data(data, threshold_low, threshold_high),
    }

    aggregator = aggregators.get(value_type)
    if aggregator:
        return aggregator(window_data)
    return None


def get_hourly_price_value(
    coordinator_data: dict,
    *,
    hour_offset: int,
    in_euro: bool,
    time: TibberPricesTimeService,
) -> float | None:
    """
    Get price for current hour or with offset.

    Legacy helper for hourly price access (not used by Calculator Pattern).
    Kept for potential backward compatibility.

    Args:
        coordinator_data: Coordinator data dict
        hour_offset: Hour offset from current time (positive=future, negative=past)
        in_euro: If True, return price in major currency (EUR), else minor (cents/øre)
        time: TibberPricesTimeService instance (required)

    Returns:
        Price value, or None if not found

    """
    # Use TimeService to get the current time in the user's timezone
    now = time.now()

    # Calculate the exact target datetime (not just the hour)
    # This properly handles day boundaries
    target_datetime = now.replace(microsecond=0) + timedelta(hours=hour_offset)
    target_hour = target_datetime.hour
    target_date = target_datetime.date()

    # Get all intervals (yesterday, today, tomorrow) via helper
    all_intervals = get_intervals_for_day_offsets(coordinator_data, [-1, 0, 1])

    # Search through all intervals to find the matching hour
    for price_data in all_intervals:
        # Parse the timestamp and convert to local time
        starts_at = time.get_interval_time(price_data)
        if starts_at is None:
            continue

        # Compare using both hour and date for accuracy
        if starts_at.hour == target_hour and starts_at.date() == target_date:
            return get_price_value(float(price_data["total"]), in_euro=in_euro)

    return None
