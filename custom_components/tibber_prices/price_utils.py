"""Utility functions for price data calculations."""

from __future__ import annotations

import logging
import statistics
from datetime import datetime, timedelta
from typing import Any

from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_VOLATILITY_THRESHOLD_HIGH,
    DEFAULT_VOLATILITY_THRESHOLD_MODERATE,
    DEFAULT_VOLATILITY_THRESHOLD_VERY_HIGH,
    PRICE_LEVEL_MAPPING,
    PRICE_LEVEL_NORMAL,
    PRICE_RATING_NORMAL,
    VOLATILITY_HIGH,
    VOLATILITY_LOW,
    VOLATILITY_MODERATE,
    VOLATILITY_VERY_HIGH,
)

_LOGGER = logging.getLogger(__name__)

MINUTES_PER_INTERVAL = 15
MIN_PRICES_FOR_VOLATILITY = 2  # Minimum number of price values needed for volatility calculation

# Volatility factors for adaptive trend thresholds
# These multipliers adjust the base trend thresholds based on price volatility.
# The volatility *ranges* are user-configurable (threshold_moderate, threshold_high),
# but the *reaction strength* (factors) is fixed for predictable behavior.
# This separation allows users to adjust volatility classification without
# unexpectedly changing trend sensitivity.
#
# Factor selection based on lookahead volatility:
# - Below moderate threshold (e.g., <15%): Use 0.6 → 40% more sensitive
# - Moderate to high (e.g., 15-30%): Use 1.0 → as configured by user
# - High and above (e.g., ≥30%): Use 1.4 → 40% less sensitive (filters noise)
VOLATILITY_FACTOR_SENSITIVE = 0.6  # Low volatility → more responsive
VOLATILITY_FACTOR_NORMAL = 1.0  # Moderate volatility → baseline
VOLATILITY_FACTOR_INSENSITIVE = 1.4  # High volatility → noise filtering


def calculate_volatility_level(
    prices: list[float],
    threshold_moderate: float | None = None,
    threshold_high: float | None = None,
    threshold_very_high: float | None = None,
) -> str:
    """
    Calculate volatility level from price list using coefficient of variation.

    Volatility indicates how much prices fluctuate during a period, which helps
    determine whether active load shifting is worthwhile. Uses the coefficient
    of variation (CV = std_dev / mean * 100%) for relative comparison that works
    across different price levels and period lengths.

    Args:
        prices: List of price values (in any unit, typically major currency units like EUR or NOK)
        threshold_moderate: Custom threshold for MODERATE level (default: use DEFAULT_VOLATILITY_THRESHOLD_MODERATE)
        threshold_high: Custom threshold for HIGH level (default: use DEFAULT_VOLATILITY_THRESHOLD_HIGH)
        threshold_very_high: Custom threshold for VERY_HIGH level (default: use DEFAULT_VOLATILITY_THRESHOLD_VERY_HIGH)

    Returns:
        Volatility level: "LOW", "MODERATE", "HIGH", or "VERY_HIGH" (uppercase)

    Examples:
        - CV < 15%: LOW → minimal optimization potential, prices relatively stable
        - 15% ≤ CV < 30%: MODERATE → some optimization worthwhile, noticeable variation
        - 30% ≤ CV < 50%: HIGH → strong optimization recommended, significant swings
        - CV ≥ 50%: VERY_HIGH → maximum optimization potential, extreme volatility

    Note:
        Requires at least 2 price values for calculation. Returns LOW if insufficient data.
        Works identically for short periods (2-3 intervals) and long periods (96 intervals/day).

    """
    # Need at least 2 values for standard deviation
    if len(prices) < MIN_PRICES_FOR_VOLATILITY:
        return VOLATILITY_LOW

    # Use provided thresholds or fall back to constants
    t_moderate = threshold_moderate if threshold_moderate is not None else DEFAULT_VOLATILITY_THRESHOLD_MODERATE
    t_high = threshold_high if threshold_high is not None else DEFAULT_VOLATILITY_THRESHOLD_HIGH
    t_very_high = threshold_very_high if threshold_very_high is not None else DEFAULT_VOLATILITY_THRESHOLD_VERY_HIGH

    # Calculate coefficient of variation
    mean = statistics.mean(prices)
    if mean <= 0:
        # Avoid division by zero or negative mean (shouldn't happen with prices)
        return VOLATILITY_LOW

    std_dev = statistics.stdev(prices)
    coefficient_of_variation = (std_dev / mean) * 100  # As percentage

    # Classify based on thresholds
    if coefficient_of_variation < t_moderate:
        return VOLATILITY_LOW
    if coefficient_of_variation < t_high:
        return VOLATILITY_MODERATE
    if coefficient_of_variation < t_very_high:
        return VOLATILITY_HIGH
    return VOLATILITY_VERY_HIGH


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
    return sum(matching_prices) / len(matching_prices)


def calculate_difference_percentage(
    current_interval_price: float,
    trailing_average: float | None,
) -> float | None:
    """
    Calculate the difference percentage between current price and trailing average.

    This mimics the API's "difference" field from priceRating endpoint.

    Args:
        current_interval_price: The current interval's price
        trailing_average: The 24-hour trailing average price

    Returns:
        The percentage difference: ((current - average) / average) * 100
        or None if trailing_average is None or zero.

    """
    if trailing_average is None or trailing_average == 0:
        return None

    return ((current_interval_price - trailing_average) / trailing_average) * 100


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
        return PRICE_RATING_NORMAL

    # Classify based on thresholds
    if difference <= threshold_low:
        return "LOW"

    if difference >= threshold_high:
        return "HIGH"

    return PRICE_RATING_NORMAL


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
    current_interval_price = price_interval.get("total")

    if current_interval_price is None:
        return

    # Calculate trailing average
    trailing_avg = calculate_trailing_average_for_interval(starts_at, all_prices)

    # Calculate and set the difference and rating_level
    if trailing_avg is not None:
        difference = calculate_difference_percentage(float(current_interval_price), trailing_avg)
        price_interval["difference"] = difference

        # Calculate rating_level based on difference
        rating_level = calculate_rating_level(difference, threshold_low, threshold_high)
        price_interval["rating_level"] = rating_level
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


def aggregate_price_levels(levels: list[str]) -> str:
    """
    Aggregate multiple price levels into a single representative level using median.

    Takes a list of price level strings (e.g., "VERY_CHEAP", "NORMAL", "EXPENSIVE")
    and returns the median level after sorting by numeric values. This naturally
    tends toward "NORMAL" when levels are mixed.

    Args:
        levels: List of price level strings from intervals

    Returns:
        The median price level string, or PRICE_LEVEL_NORMAL if input is empty

    """
    if not levels:
        return PRICE_LEVEL_NORMAL

    # Convert levels to numeric values and sort
    numeric_values = [PRICE_LEVEL_MAPPING.get(level, 0) for level in levels]
    numeric_values.sort()

    # Get median (middle value for odd length, lower-middle for even length)
    median_idx = len(numeric_values) // 2
    median_value = numeric_values[median_idx]

    # Convert back to level string
    for level, value in PRICE_LEVEL_MAPPING.items():
        if value == median_value:
            return level

    return PRICE_LEVEL_NORMAL


def aggregate_price_rating(differences: list[float], threshold_low: float, threshold_high: float) -> tuple[str, float]:
    """
    Aggregate multiple price differences into a single rating level.

    Calculates the average difference percentage across multiple intervals
    and applies thresholds to determine the overall rating level.

    Args:
        differences: List of difference percentages from intervals
        threshold_low: The low threshold percentage for LOW rating
        threshold_high: The high threshold percentage for HIGH rating

    Returns:
        Tuple of (rating_level, average_difference)
        rating_level: "LOW", "NORMAL", or "HIGH"
        average_difference: The averaged difference percentage

    """
    if not differences:
        return PRICE_RATING_NORMAL, 0.0

    # Filter out None values
    valid_differences = [d for d in differences if d is not None]
    if not valid_differences:
        return PRICE_RATING_NORMAL, 0.0

    # Calculate average difference
    avg_difference = sum(valid_differences) / len(valid_differences)

    # Apply thresholds
    rating_level = calculate_rating_level(avg_difference, threshold_low, threshold_high)

    return rating_level or PRICE_RATING_NORMAL, avg_difference


def aggregate_period_levels(interval_data_list: list[dict[str, Any]]) -> str | None:
    """
    Aggregate price levels across multiple intervals in a period.

    Extracts "level" from each interval and uses the same logic as
    aggregate_price_levels() to determine the overall level for the period.

    Args:
        interval_data_list: List of price interval dictionaries with "level" keys

    Returns:
        The aggregated level string in lowercase (e.g., "very_cheap", "normal", "expensive"),
        or None if no valid levels found

    """
    levels: list[str] = []
    for interval in interval_data_list:
        level = interval.get("level")
        if level is not None and isinstance(level, str):
            levels.append(level)

    if not levels:
        return None

    aggregated = aggregate_price_levels(levels)
    # Convert to lowercase for consistency with other enum sensors
    return aggregated.lower() if aggregated else None


def aggregate_period_ratings(
    interval_data_list: list[dict[str, Any]],
    threshold_low: float,
    threshold_high: float,
) -> tuple[str | None, float | None]:
    """
    Aggregate price ratings across multiple intervals in a period.

    Extracts "difference" from each interval and uses the same logic as
    aggregate_price_rating() to determine the overall rating for the period.

    Args:
        interval_data_list: List of price interval dictionaries with "difference" keys
        threshold_low: The low threshold percentage for LOW rating
        threshold_high: The high threshold percentage for HIGH rating

    Returns:
        Tuple of (rating_level, average_difference)
        rating_level: "low", "normal", "high" (lowercase), or None if no valid data
        average_difference: The averaged difference percentage, or None if no valid data

    """
    differences: list[float] = []
    for interval in interval_data_list:
        diff = interval.get("difference")
        if diff is not None:
            differences.append(float(diff))

    if not differences:
        return None, None

    rating_level, avg_diff = aggregate_price_rating(differences, threshold_low, threshold_high)
    # Convert to lowercase for consistency with other enum sensors
    return rating_level.lower() if rating_level else None, avg_diff


def _calculate_lookahead_volatility_factor(
    all_intervals: list[dict[str, Any]],
    lookahead_intervals: int,
    volatility_threshold_moderate: float,
    volatility_threshold_high: float,
) -> float:
    """
    Calculate volatility factor for adaptive thresholds based on lookahead period.

    Uses the same volatility calculation (coefficient of variation) as volatility sensors,
    ensuring consistent volatility interpretation across the integration.

    Args:
        all_intervals: List of price intervals (today + tomorrow)
        lookahead_intervals: Number of intervals to analyze for volatility
        volatility_threshold_moderate: Threshold for moderate volatility (%, e.g., 15)
        volatility_threshold_high: Threshold for high volatility (%, e.g., 30)

    Returns:
        Multiplier for base threshold:
        - 0.6 for low volatility (< moderate threshold)
        - 1.0 for moderate volatility (moderate to high threshold)
        - 1.4 for high volatility (>= high threshold)

    """
    if len(all_intervals) < lookahead_intervals:
        _LOGGER.debug(
            "Insufficient data for volatility calculation: need %d intervals, have %d - using factor 1.0",
            lookahead_intervals,
            len(all_intervals),
        )
        return 1.0  # Fallback: no adjustment

    # Extract prices from next N intervals
    lookahead_prices = [
        float(interval["total"])
        for interval in all_intervals[:lookahead_intervals]
        if "total" in interval and interval["total"] is not None
    ]

    if not lookahead_prices:
        _LOGGER.debug("No valid prices in lookahead period - using factor 1.0")
        return 1.0

    # Use the same volatility calculation as volatility sensors (coefficient of variation)
    # This ensures consistent interpretation of volatility across the integration
    volatility_level = calculate_volatility_level(
        prices=lookahead_prices,
        threshold_moderate=volatility_threshold_moderate,
        threshold_high=volatility_threshold_high,
        # Note: We don't use VERY_HIGH threshold here, only LOW/MODERATE/HIGH matter for factor
    )

    # Map volatility level to adjustment factor
    if volatility_level == VOLATILITY_LOW:
        factor = VOLATILITY_FACTOR_SENSITIVE  # 0.6 → More sensitive trend detection
    elif volatility_level in (VOLATILITY_MODERATE, VOLATILITY_HIGH):
        # Treat MODERATE and HIGH the same for trend detection
        # HIGH volatility means noisy data, so we need less sensitive thresholds
        factor = VOLATILITY_FACTOR_NORMAL if volatility_level == VOLATILITY_MODERATE else VOLATILITY_FACTOR_INSENSITIVE
    else:  # VOLATILITY_VERY_HIGH (should not occur with our thresholds, but handle it)
        factor = VOLATILITY_FACTOR_INSENSITIVE  # 1.4 → Less sensitive (filter noise)

    _LOGGER.debug(
        "Volatility analysis: intervals=%d, prices=%d, "
        "level=%s, thresholds=(moderate:%.0f%%, high:%.0f%%), factor=%.2f",
        lookahead_intervals,
        len(lookahead_prices),
        volatility_level,
        volatility_threshold_moderate,
        volatility_threshold_high,
        factor,
    )

    return factor


def calculate_price_trend(  # noqa: PLR0913 - All parameters are necessary for volatility-adaptive calculation
    current_interval_price: float,
    future_average: float,
    threshold_rising: float = 3.0,
    threshold_falling: float = -3.0,
    *,
    volatility_adjustment: bool = True,
    lookahead_intervals: int | None = None,
    all_intervals: list[dict[str, Any]] | None = None,
    volatility_threshold_moderate: float = DEFAULT_VOLATILITY_THRESHOLD_MODERATE,
    volatility_threshold_high: float = DEFAULT_VOLATILITY_THRESHOLD_HIGH,
) -> tuple[str, float]:
    """
    Calculate price trend by comparing current price with future average.

    Supports volatility-adaptive thresholds: when enabled, the effective threshold
    is adjusted based on price volatility in the lookahead period. This makes the
    trend detection more sensitive during stable periods and less noisy during
    volatile periods.

    Uses the same volatility thresholds as configured for volatility sensors,
    ensuring consistent volatility interpretation across the integration.

    Args:
        current_interval_price: Current interval price
        future_average: Average price of future intervals
        threshold_rising: Base threshold for rising trend (%, positive, default 3%)
        threshold_falling: Base threshold for falling trend (%, negative, default -3%)
        volatility_adjustment: Enable volatility-adaptive thresholds (default True)
        lookahead_intervals: Number of intervals in trend period for volatility calc
        all_intervals: Price intervals (today + tomorrow) for volatility calculation
        volatility_threshold_moderate: User-configured moderate volatility threshold (%)
        volatility_threshold_high: User-configured high volatility threshold (%)

    Returns:
        Tuple of (trend_state, difference_percentage)
        trend_state: "rising" | "falling" | "stable"
        difference_percentage: % change from current to future ((future - current) / current * 100)

    Note:
        Volatility adjustment factor:
        - Low volatility (<15%): factor 0.6 → more sensitive (e.g., 3% → 1.8%)
        - Moderate volatility (15-35%): factor 1.0 → as configured (3%)
        - High volatility (>35%): factor 1.4 → less sensitive (e.g., 3% → 4.2%)

    """
    if current_interval_price == 0:
        # Avoid division by zero
        _LOGGER.debug("Current price is zero - returning stable trend")
        return "stable", 0.0

    # Apply volatility adjustment if enabled and data available
    effective_rising = threshold_rising
    effective_falling = threshold_falling
    volatility_factor = 1.0

    if volatility_adjustment and lookahead_intervals and all_intervals:
        volatility_factor = _calculate_lookahead_volatility_factor(
            all_intervals, lookahead_intervals, volatility_threshold_moderate, volatility_threshold_high
        )
        effective_rising = threshold_rising * volatility_factor
        effective_falling = threshold_falling * volatility_factor

        _LOGGER.debug(
            "Trend threshold adjustment: base_rising=%.1f%%, base_falling=%.1f%%, "
            "lookahead_intervals=%d, volatility_factor=%.2f, "
            "effective_rising=%.1f%%, effective_falling=%.1f%%",
            threshold_rising,
            threshold_falling,
            lookahead_intervals,
            volatility_factor,
            effective_rising,
            effective_falling,
        )

    # Calculate percentage difference from current to future
    diff_pct = ((future_average - current_interval_price) / current_interval_price) * 100

    # Determine trend based on effective thresholds
    if diff_pct >= effective_rising:
        trend = "rising"
    elif diff_pct <= effective_falling:
        trend = "falling"
    else:
        trend = "stable"

    _LOGGER.debug(
        "Trend calculation: current=%.4f, future_avg=%.4f, diff=%.1f%%, "
        "threshold_rising=%.1f%%, threshold_falling=%.1f%%, trend=%s",
        current_interval_price,
        future_average,
        diff_pct,
        effective_rising,
        effective_falling,
        trend,
    )

    return trend, diff_pct
