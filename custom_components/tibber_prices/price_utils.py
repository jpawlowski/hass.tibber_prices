"""Utility functions for price data calculations."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

MINUTES_PER_INTERVAL = 15


def calculate_trailing_average_for_interval(
    interval_start: datetime,
    all_prices: list[dict[str, Any]],
) -> float | None:
    """
    Calculate the trailing 24-hour average price for a specific interval.

    Args:
        interval_start: The start time of the interval we're calculating for
        all_prices: List of all available price intervals (yesterday + today + tomorrow)

    Returns:
        The average price of all intervals in the 24 hours before interval_start,
        or None if insufficient data is available.

    """
    if not all_prices:
        return None

    # Calculate the lookback period: 24 hours before this interval
    lookback_start = interval_start - timedelta(hours=24)

    # Collect all prices that fall within the 24-hour lookback window
    matching_prices = []

    for price_data in all_prices:
        starts_at_str = price_data.get("startsAt")
        if not starts_at_str:
            continue

        # Parse the timestamp
        price_time = dt_util.parse_datetime(starts_at_str)
        if price_time is None:
            continue

        # Convert to local timezone for comparison
        price_time = dt_util.as_local(price_time)

        # Check if this price falls within our lookback window
        # Include prices that start >= lookback_start and start < interval_start
        if lookback_start <= price_time < interval_start:
            total_price = price_data.get("total")
            if total_price is not None:
                matching_prices.append(float(total_price))

    if not matching_prices:
        _LOGGER.debug(
            "No prices found in 24-hour lookback window for interval starting at %s (lookback: %s to %s)",
            interval_start,
            lookback_start,
            interval_start,
        )
        return None

    # Calculate and return the average
    average = sum(matching_prices) / len(matching_prices)
    _LOGGER.debug(
        "Calculated trailing 24h average for interval %s: %.6f from %d prices",
        interval_start,
        average,
        len(matching_prices),
    )
    return average


def calculate_difference_percentage(
    current_price: float,
    trailing_average: float | None,
) -> float | None:
    """
    Calculate the difference percentage between current price and trailing average.

    This mimics the API's "difference" field from priceRating endpoint.

    Args:
        current_price: The current interval's price
        trailing_average: The 24-hour trailing average price

    Returns:
        The percentage difference: ((current - average) / average) * 100
        or None if trailing_average is None or zero.

    """
    if trailing_average is None or trailing_average == 0:
        return None

    return ((current_price - trailing_average) / trailing_average) * 100


def calculate_rating_level(
    difference: float | None,
    threshold_low: float,
    threshold_high: float,
) -> str | None:
    """
    Calculate the rating level based on difference percentage and thresholds.

    This mimics the API's "level" field from priceRating endpoint.

    Args:
        difference: The difference percentage (from calculate_difference_percentage)
        threshold_low: The low threshold percentage (typically -100 to 0)
        threshold_high: The high threshold percentage (typically 0 to 100)

    Returns:
        "LOW" if difference <= threshold_low
        "HIGH" if difference >= threshold_high
        "NORMAL" otherwise
        None if difference is None

    """
    if difference is None:
        return None

    # If difference falls in both ranges (shouldn't normally happen), return NORMAL
    if difference <= threshold_low and difference >= threshold_high:
        return "NORMAL"

    # Classify based on thresholds
    if difference <= threshold_low:
        return "LOW"

    if difference >= threshold_high:
        return "HIGH"

    return "NORMAL"


def _process_price_interval(
    price_interval: dict[str, Any],
    all_prices: list[dict[str, Any]],
    threshold_low: float,
    threshold_high: float,
    day_label: str,
) -> None:
    """
    Process a single price interval and add difference and rating_level.

    Args:
        price_interval: The price interval to process (modified in place)
        all_prices: All available price intervals for lookback calculation
        threshold_low: Low threshold percentage
        threshold_high: High threshold percentage
        day_label: Label for logging ("today" or "tomorrow")

    """
    starts_at_str = price_interval.get("startsAt")
    if not starts_at_str:
        return

    starts_at = dt_util.parse_datetime(starts_at_str)
    if starts_at is None:
        return

    starts_at = dt_util.as_local(starts_at)
    current_price = price_interval.get("total")

    if current_price is None:
        return

    # Calculate trailing average
    trailing_avg = calculate_trailing_average_for_interval(starts_at, all_prices)

    # Calculate and set the difference and rating_level
    if trailing_avg is not None:
        difference = calculate_difference_percentage(float(current_price), trailing_avg)
        price_interval["difference"] = difference

        # Calculate rating_level based on difference
        rating_level = calculate_rating_level(difference, threshold_low, threshold_high)
        price_interval["rating_level"] = rating_level

        _LOGGER.debug(
            "Set difference and rating_level for %s interval %s: difference=%.2f%%, level=%s (price: %.6f, avg: %.6f)",
            day_label,
            starts_at,
            difference if difference is not None else 0,
            rating_level,
            float(current_price),
            trailing_avg,
        )
    else:
        # Set to None if we couldn't calculate
        price_interval["difference"] = None
        price_interval["rating_level"] = None
        _LOGGER.debug(
            "Could not calculate trailing average for %s interval %s",
            day_label,
            starts_at,
        )


def enrich_price_info_with_differences(
    price_info: dict[str, Any],
    threshold_low: float | None = None,
    threshold_high: float | None = None,
) -> dict[str, Any]:
    """
    Enrich price info with calculated 'difference' and 'rating_level' values.

    Computes the trailing 24-hour average, difference percentage, and rating level
    for each interval in today and tomorrow (excluding yesterday since it's historical).

    Args:
        price_info: Dictionary with 'yesterday', 'today', 'tomorrow' keys
        threshold_low: Low threshold percentage for rating_level (defaults to -10)
        threshold_high: High threshold percentage for rating_level (defaults to 10)

    Returns:
        Updated price_info dict with 'difference' and 'rating_level' added

    """
    if threshold_low is None:
        threshold_low = -10
    if threshold_high is None:
        threshold_high = 10

    yesterday_prices = price_info.get("yesterday", [])
    today_prices = price_info.get("today", [])
    tomorrow_prices = price_info.get("tomorrow", [])

    # Combine all prices for lookback calculation
    all_prices = yesterday_prices + today_prices + tomorrow_prices

    _LOGGER.debug(
        "Enriching price info with differences and rating levels: "
        "yesterday=%d, today=%d, tomorrow=%d, thresholds: low=%.2f, high=%.2f",
        len(yesterday_prices),
        len(today_prices),
        len(tomorrow_prices),
        threshold_low,
        threshold_high,
    )

    # Process today's prices
    for price_interval in today_prices:
        _process_price_interval(price_interval, all_prices, threshold_low, threshold_high, "today")

    # Process tomorrow's prices
    for price_interval in tomorrow_prices:
        _process_price_interval(price_interval, all_prices, threshold_low, threshold_high, "tomorrow")

    return price_info


def find_price_data_for_interval(price_info: Any, target_time: datetime) -> dict | None:
    """
    Find the price data for a specific 15-minute interval timestamp.

    Args:
        price_info: The price info dictionary from Tibber API
        target_time: The target timestamp to find price data for

    Returns:
        Price data dict if found, None otherwise

    """
    day_key = "tomorrow" if target_time.date() > dt_util.now().date() else "today"
    search_days = [day_key, "tomorrow" if day_key == "today" else "today"]

    for search_day in search_days:
        day_prices = price_info.get(search_day, [])
        if not day_prices:
            continue

        for price_data in day_prices:
            starts_at = dt_util.parse_datetime(price_data["startsAt"])
            if starts_at is None:
                continue

            starts_at = dt_util.as_local(starts_at)
            interval_end = starts_at + timedelta(minutes=MINUTES_PER_INTERVAL)
            if starts_at <= target_time < interval_end and starts_at.date() == target_time.date():
                return price_data

    return None
