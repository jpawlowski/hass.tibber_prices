"""Utility functions for calculating price averages."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from custom_components.tibber_prices.coordinator.helpers import get_intervals_for_day_offsets

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService


def calculate_median(prices: list[float]) -> float | None:
    """
    Calculate median from a list of prices.

    Args:
        prices: List of price values

    Returns:
        Median price, or None if list is empty

    """
    if not prices:
        return None

    sorted_prices = sorted(prices)
    n = len(sorted_prices)

    if n % 2 == 0:
        # Even number of elements: average of middle two
        return (sorted_prices[n // 2 - 1] + sorted_prices[n // 2]) / 2
    # Odd number of elements: middle element
    return sorted_prices[n // 2]


def calculate_mean(prices: list[float]) -> float:
    """
    Calculate arithmetic mean (average) from a list of prices.

    Args:
        prices: List of price values (must not be empty)

    Returns:
        Mean price

    Raises:
        ValueError: If prices list is empty

    """
    if not prices:
        msg = "Cannot calculate mean of empty list"
        raise ValueError(msg)

    return sum(prices) / len(prices)


def calculate_trailing_24h_mean(
    all_prices: list[dict],
    interval_start: datetime,
    *,
    time: TibberPricesTimeService,
) -> tuple[float | None, float | None]:
    """
    Calculate trailing 24-hour mean and median price for a given interval.

    Args:
        all_prices: List of all price data (yesterday, today, tomorrow combined)
        interval_start: Start time of the interval to calculate mean for
        time: TibberPricesTimeService instance (required)

    Returns:
        Tuple of (mean price, median price) for the 24 hours preceding the interval,
        or (None, None) if no data in window

    """
    # Define the 24-hour window: from 24 hours before interval_start up to interval_start
    window_start = interval_start - timedelta(hours=24)
    window_end = interval_start

    # Filter prices within the 24-hour window
    prices_in_window = []
    for price_data in all_prices:
        starts_at = time.get_interval_time(price_data)
        if starts_at is None:
            continue
        # Include intervals that start within the window (not including the current interval's end)
        if window_start <= starts_at < window_end:
            prices_in_window.append(float(price_data["total"]))

    # Calculate mean and median
    # CRITICAL: Return None instead of 0.0 when no data available
    # With negative prices, 0.0 could be misinterpreted as a real mean value
    if prices_in_window:
        mean = calculate_mean(prices_in_window)
        median = calculate_median(prices_in_window)
        return mean, median
    return None, None


def calculate_leading_24h_mean(
    all_prices: list[dict],
    interval_start: datetime,
    *,
    time: TibberPricesTimeService,
) -> tuple[float | None, float | None]:
    """
    Calculate leading 24-hour mean and median price for a given interval.

    Args:
        all_prices: List of all price data (yesterday, today, tomorrow combined)
        interval_start: Start time of the interval to calculate mean for
        time: TibberPricesTimeService instance (required)

    Returns:
        Tuple of (mean price, median price) for up to 24 hours following the interval,
        or (None, None) if no data in window

    """
    # Define the 24-hour window: from interval_start up to 24 hours after
    window_start = interval_start
    window_end = interval_start + timedelta(hours=24)

    # Filter prices within the 24-hour window
    prices_in_window = []
    for price_data in all_prices:
        starts_at = time.get_interval_time(price_data)
        if starts_at is None:
            continue
        # Include intervals that start within the window
        if window_start <= starts_at < window_end:
            prices_in_window.append(float(price_data["total"]))

    # Calculate mean and median
    # CRITICAL: Return None instead of 0.0 when no data available
    # With negative prices, 0.0 could be misinterpreted as a real mean value
    if prices_in_window:
        mean = calculate_mean(prices_in_window)
        median = calculate_median(prices_in_window)
        return mean, median
    return None, None


def calculate_current_trailing_mean(
    coordinator_data: dict,
    *,
    time: TibberPricesTimeService,
) -> tuple[float | None, float | None]:
    """
    Calculate the trailing 24-hour mean and median for the current time.

    Args:
        coordinator_data: The coordinator data containing priceInfo
        time: TibberPricesTimeService instance (required)

    Returns:
        Tuple of (mean price, median price), or (None, None) if unavailable

    """
    if not coordinator_data:
        return None, None

    # Get all intervals (yesterday, today, tomorrow) via helper
    all_prices = get_intervals_for_day_offsets(coordinator_data, [-1, 0, 1])
    if not all_prices:
        return None, None

    now = time.now()
    # calculate_trailing_24h_mean returns (mean, median) tuple
    return calculate_trailing_24h_mean(all_prices, now, time=time)


def calculate_current_leading_mean(
    coordinator_data: dict,
    *,
    time: TibberPricesTimeService,
) -> tuple[float | None, float | None]:
    """
    Calculate the leading 24-hour mean and median for the current time.

    Args:
        coordinator_data: The coordinator data containing priceInfo
        time: TibberPricesTimeService instance (required)

    Returns:
        Tuple of (mean price, median price), or (None, None) if unavailable

    """
    if not coordinator_data:
        return None, None

    # Get all intervals (yesterday, today, tomorrow) via helper
    all_prices = get_intervals_for_day_offsets(coordinator_data, [-1, 0, 1])
    if not all_prices:
        return None, None

    now = time.now()
    # calculate_leading_24h_mean returns (mean, median) tuple
    return calculate_leading_24h_mean(all_prices, now, time=time)


def calculate_trailing_24h_min(
    all_prices: list[dict],
    interval_start: datetime,
    *,
    time: TibberPricesTimeService,
) -> float | None:
    """
    Calculate trailing 24-hour minimum price for a given interval.

    Args:
        all_prices: List of all price data (yesterday, today, tomorrow combined)
        interval_start: Start time of the interval to calculate minimum for
        time: TibberPricesTimeService instance (required)

    Returns:
        Minimum price for the 24 hours preceding the interval, or None if no data in window

    """
    # Define the 24-hour window: from 24 hours before interval_start up to interval_start
    window_start = interval_start - timedelta(hours=24)
    window_end = interval_start

    # Filter prices within the 24-hour window
    prices_in_window = []
    for price_data in all_prices:
        starts_at = time.get_interval_time(price_data)
        if starts_at is None:
            continue
        # Include intervals that start within the window (not including the current interval's end)
        if window_start <= starts_at < window_end:
            prices_in_window.append(float(price_data["total"]))

    # Calculate minimum
    # CRITICAL: Return None instead of 0.0 when no data available
    # With negative prices, 0.0 could be misinterpreted as a maximum value
    if prices_in_window:
        return min(prices_in_window)
    return None


def calculate_trailing_24h_max(
    all_prices: list[dict],
    interval_start: datetime,
    *,
    time: TibberPricesTimeService,
) -> float | None:
    """
    Calculate trailing 24-hour maximum price for a given interval.

    Args:
        all_prices: List of all price data (yesterday, today, tomorrow combined)
        interval_start: Start time of the interval to calculate maximum for
        time: TibberPricesTimeService instance (required)

    Returns:
        Maximum price for the 24 hours preceding the interval, or None if no data in window

    """
    # Define the 24-hour window: from 24 hours before interval_start up to interval_start
    window_start = interval_start - timedelta(hours=24)
    window_end = interval_start

    # Filter prices within the 24-hour window
    prices_in_window = []
    for price_data in all_prices:
        starts_at = time.get_interval_time(price_data)
        if starts_at is None:
            continue
        # Include intervals that start within the window (not including the current interval's end)
        if window_start <= starts_at < window_end:
            prices_in_window.append(float(price_data["total"]))

    # Calculate maximum
    # CRITICAL: Return None instead of 0.0 when no data available
    # With negative prices, 0.0 could be misinterpreted as a real price value
    if prices_in_window:
        return max(prices_in_window)
    return None


def calculate_leading_24h_min(
    all_prices: list[dict],
    interval_start: datetime,
    *,
    time: TibberPricesTimeService,
) -> float | None:
    """
    Calculate leading 24-hour minimum price for a given interval.

    Args:
        all_prices: List of all price data (yesterday, today, tomorrow combined)
        interval_start: Start time of the interval to calculate minimum for
        time: TibberPricesTimeService instance (required)

    Returns:
        Minimum price for up to 24 hours following the interval, or None if no data in window

    """
    # Define the 24-hour window: from interval_start up to 24 hours after
    window_start = interval_start
    window_end = interval_start + timedelta(hours=24)

    # Filter prices within the 24-hour window
    prices_in_window = []
    for price_data in all_prices:
        starts_at = time.get_interval_time(price_data)
        if starts_at is None:
            continue
        # Include intervals that start within the window
        if window_start <= starts_at < window_end:
            prices_in_window.append(float(price_data["total"]))

    # Calculate minimum
    # CRITICAL: Return None instead of 0.0 when no data available
    # With negative prices, 0.0 could be misinterpreted as a maximum value
    if prices_in_window:
        return min(prices_in_window)
    return None


def calculate_leading_24h_max(
    all_prices: list[dict],
    interval_start: datetime,
    *,
    time: TibberPricesTimeService,
) -> float | None:
    """
    Calculate leading 24-hour maximum price for a given interval.

    Args:
        all_prices: List of all price data (yesterday, today, tomorrow combined)
        interval_start: Start time of the interval to calculate maximum for
        time: TibberPricesTimeService instance (required)

    Returns:
        Maximum price for up to 24 hours following the interval, or None if no data in window

    """
    # Define the 24-hour window: from interval_start up to 24 hours after
    window_start = interval_start
    window_end = interval_start + timedelta(hours=24)

    # Filter prices within the 24-hour window
    prices_in_window = []
    for price_data in all_prices:
        starts_at = time.get_interval_time(price_data)
        if starts_at is None:
            continue
        # Include intervals that start within the window
        if window_start <= starts_at < window_end:
            prices_in_window.append(float(price_data["total"]))

    # Calculate maximum
    # CRITICAL: Return None instead of 0.0 when no data available
    # With negative prices, 0.0 could be misinterpreted as a real price value
    if prices_in_window:
        return max(prices_in_window)
    return None


def calculate_current_trailing_min(
    coordinator_data: dict,
    *,
    time: TibberPricesTimeService,
) -> float | None:
    """
    Calculate the trailing 24-hour minimum for the current time.

    Args:
        coordinator_data: The coordinator data containing priceInfo
        time: TibberPricesTimeService instance (required)

    Returns:
        Current trailing 24-hour minimum price, or None if unavailable

    """
    if not coordinator_data:
        return None

    # Get all intervals (yesterday, today, tomorrow) via helper
    all_prices = get_intervals_for_day_offsets(coordinator_data, [-1, 0, 1])
    if not all_prices:
        return None

    now = time.now()
    return calculate_trailing_24h_min(all_prices, now, time=time)


def calculate_current_trailing_max(
    coordinator_data: dict,
    *,
    time: TibberPricesTimeService,
) -> float | None:
    """
    Calculate the trailing 24-hour maximum for the current time.

    Args:
        coordinator_data: The coordinator data containing priceInfo
        time: TibberPricesTimeService instance (required)

    Returns:
        Current trailing 24-hour maximum price, or None if unavailable

    """
    if not coordinator_data:
        return None

    # Get all intervals (yesterday, today, tomorrow) via helper
    all_prices = get_intervals_for_day_offsets(coordinator_data, [-1, 0, 1])
    if not all_prices:
        return None

    now = time.now()
    return calculate_trailing_24h_max(all_prices, now, time=time)


def calculate_current_leading_min(
    coordinator_data: dict,
    *,
    time: TibberPricesTimeService,
) -> float | None:
    """
    Calculate the leading 24-hour minimum for the current time.

    Args:
        coordinator_data: The coordinator data containing priceInfo
        time: TibberPricesTimeService instance (required)

    Returns:
        Current leading 24-hour minimum price, or None if unavailable

    """
    if not coordinator_data:
        return None

    # Get all intervals (yesterday, today, tomorrow) via helper
    all_prices = get_intervals_for_day_offsets(coordinator_data, [-1, 0, 1])
    if not all_prices:
        return None

    now = time.now()
    return calculate_leading_24h_min(all_prices, now, time=time)


def calculate_current_leading_max(
    coordinator_data: dict,
    *,
    time: TibberPricesTimeService,
) -> float | None:
    """
    Calculate the leading 24-hour maximum for the current time.

    Args:
        coordinator_data: The coordinator data containing priceInfo
        time: TibberPricesTimeService instance (required)

    Returns:
        Current leading 24-hour maximum price, or None if unavailable

    """
    if not coordinator_data:
        return None

    # Get all intervals (yesterday, today, tomorrow) via helper
    all_prices = get_intervals_for_day_offsets(coordinator_data, [-1, 0, 1])
    if not all_prices:
        return None

    now = time.now()
    return calculate_leading_24h_max(all_prices, now, time=time)


def calculate_next_n_hours_mean(
    coordinator_data: dict,
    hours: int,
    *,
    time: TibberPricesTimeService,
) -> tuple[float | None, float | None]:
    """
    Calculate mean and median price for the next N hours starting from the next interval.

    This function computes the mean and median of all 15-minute intervals starting from
    the next interval (not current) up to N hours into the future.

    Args:
        coordinator_data: The coordinator data containing priceInfo
        hours: Number of hours to look ahead (1, 2, 3, 4, 5, 6, 8, 12, etc.)
        time: TibberPricesTimeService instance (required)

    Returns:
        Tuple of (mean price, median price) for the next N hours,
        or (None, None) if insufficient data

    """
    if not coordinator_data or hours <= 0:
        return None, None

    # Get all intervals (yesterday, today, tomorrow) via helper
    all_prices = get_intervals_for_day_offsets(coordinator_data, [-1, 0, 1])
    if not all_prices:
        return None, None

    # Find the current interval index
    current_idx = None
    for idx, price_data in enumerate(all_prices):
        starts_at = time.get_interval_time(price_data)
        if starts_at is None:
            continue
        interval_end = starts_at + time.get_interval_duration()

        if time.is_current_interval(starts_at, interval_end):
            current_idx = idx
            break

    if current_idx is None:
        return None, None

    # Calculate how many intervals are in N hours
    intervals_needed = time.minutes_to_intervals(hours * 60)

    # Collect prices starting from NEXT interval (current_idx + 1)
    prices_in_window = []
    for offset in range(1, intervals_needed + 1):
        idx = current_idx + offset
        if idx >= len(all_prices):
            # Not enough future data available
            break
        price = all_prices[idx].get("total")
        if price is not None:
            prices_in_window.append(float(price))

    # Return None if no data at all
    if not prices_in_window:
        return None, None

    # Return mean and median (prefer full period, but allow graceful degradation)
    mean = calculate_mean(prices_in_window)
    median = calculate_median(prices_in_window)
    return mean, median
