"""Utility functions for calculating price averages."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator.time_service import TimeService


def calculate_trailing_24h_avg(all_prices: list[dict], interval_start: datetime) -> float:
    """
    Calculate trailing 24-hour average price for a given interval.

    Args:
        all_prices: List of all price data (yesterday, today, tomorrow combined)
        interval_start: Start time of the interval to calculate average for
        time: TimeService instance (required)

    Returns:
        Average price for the 24 hours preceding the interval (not including the interval itself)

    """
    # Define the 24-hour window: from 24 hours before interval_start up to interval_start
    window_start = interval_start - timedelta(hours=24)
    window_end = interval_start

    # Filter prices within the 24-hour window
    prices_in_window = []
    for price_data in all_prices:
        starts_at = price_data["startsAt"]  # Already datetime object in local timezone
        if starts_at is None:
            continue
        # Include intervals that start within the window (not including the current interval's end)
        if window_start <= starts_at < window_end:
            prices_in_window.append(float(price_data["total"]))

    # Calculate average
    if prices_in_window:
        return sum(prices_in_window) / len(prices_in_window)
    return 0.0


def calculate_leading_24h_avg(all_prices: list[dict], interval_start: datetime) -> float:
    """
    Calculate leading 24-hour average price for a given interval.

    Args:
        all_prices: List of all price data (yesterday, today, tomorrow combined)
        interval_start: Start time of the interval to calculate average for
        time: TimeService instance (required)

    Returns:
        Average price for up to 24 hours following the interval (including the interval itself)

    """
    # Define the 24-hour window: from interval_start up to 24 hours after
    window_start = interval_start
    window_end = interval_start + timedelta(hours=24)

    # Filter prices within the 24-hour window
    prices_in_window = []
    for price_data in all_prices:
        starts_at = price_data["startsAt"]  # Already datetime object in local timezone
        if starts_at is None:
            continue
        # Include intervals that start within the window
        if window_start <= starts_at < window_end:
            prices_in_window.append(float(price_data["total"]))

    # Calculate average
    if prices_in_window:
        return sum(prices_in_window) / len(prices_in_window)
    return 0.0


def calculate_current_trailing_avg(
    coordinator_data: dict,
    *,
    time: TimeService,
) -> float | None:
    """
    Calculate the trailing 24-hour average for the current time.

    Args:
        coordinator_data: The coordinator data containing priceInfo
        time: TimeService instance (required)

    Returns:
        Current trailing 24-hour average price, or None if unavailable

    """
    if not coordinator_data:
        return None

    price_info = coordinator_data.get("priceInfo", {})
    yesterday_prices = price_info.get("yesterday", [])
    today_prices = price_info.get("today", [])
    tomorrow_prices = price_info.get("tomorrow", [])

    all_prices = yesterday_prices + today_prices + tomorrow_prices
    if not all_prices:
        return None

    now = time.now()
    return calculate_trailing_24h_avg(all_prices, now)


def calculate_current_leading_avg(
    coordinator_data: dict,
    *,
    time: TimeService,
) -> float | None:
    """
    Calculate the leading 24-hour average for the current time.

    Args:
        coordinator_data: The coordinator data containing priceInfo
        time: TimeService instance (required)

    Returns:
        Current leading 24-hour average price, or None if unavailable

    """
    if not coordinator_data:
        return None

    price_info = coordinator_data.get("priceInfo", {})
    yesterday_prices = price_info.get("yesterday", [])
    today_prices = price_info.get("today", [])
    tomorrow_prices = price_info.get("tomorrow", [])

    all_prices = yesterday_prices + today_prices + tomorrow_prices
    if not all_prices:
        return None

    now = time.now()
    return calculate_leading_24h_avg(all_prices, now)


def calculate_trailing_24h_min(
    all_prices: list[dict],
    interval_start: datetime,
    *,
    time: TimeService,
) -> float:
    """
    Calculate trailing 24-hour minimum price for a given interval.

    Args:
        all_prices: List of all price data (yesterday, today, tomorrow combined)
        interval_start: Start time of the interval to calculate minimum for
        time: TimeService instance (required)

    Returns:
        Minimum price for the 24 hours preceding the interval (not including the interval itself)

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
    if prices_in_window:
        return min(prices_in_window)
    return 0.0


def calculate_trailing_24h_max(
    all_prices: list[dict],
    interval_start: datetime,
    *,
    time: TimeService,
) -> float:
    """
    Calculate trailing 24-hour maximum price for a given interval.

    Args:
        all_prices: List of all price data (yesterday, today, tomorrow combined)
        interval_start: Start time of the interval to calculate maximum for
        time: TimeService instance (required)

    Returns:
        Maximum price for the 24 hours preceding the interval (not including the interval itself)

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
    if prices_in_window:
        return max(prices_in_window)
    return 0.0


def calculate_leading_24h_min(
    all_prices: list[dict],
    interval_start: datetime,
    *,
    time: TimeService,
) -> float:
    """
    Calculate leading 24-hour minimum price for a given interval.

    Args:
        all_prices: List of all price data (yesterday, today, tomorrow combined)
        interval_start: Start time of the interval to calculate minimum for
        time: TimeService instance (required)

    Returns:
        Minimum price for up to 24 hours following the interval (including the interval itself)

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
    if prices_in_window:
        return min(prices_in_window)
    return 0.0


def calculate_leading_24h_max(
    all_prices: list[dict],
    interval_start: datetime,
    *,
    time: TimeService,
) -> float:
    """
    Calculate leading 24-hour maximum price for a given interval.

    Args:
        all_prices: List of all price data (yesterday, today, tomorrow combined)
        interval_start: Start time of the interval to calculate maximum for
        time: TimeService instance (required)

    Returns:
        Maximum price for up to 24 hours following the interval (including the interval itself)

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
    if prices_in_window:
        return max(prices_in_window)
    return 0.0


def calculate_current_trailing_min(
    coordinator_data: dict,
    *,
    time: TimeService,
) -> float | None:
    """
    Calculate the trailing 24-hour minimum for the current time.

    Args:
        coordinator_data: The coordinator data containing priceInfo
        time: TimeService instance (required)

    Returns:
        Current trailing 24-hour minimum price, or None if unavailable

    """
    if not coordinator_data:
        return None

    price_info = coordinator_data.get("priceInfo", {})
    yesterday_prices = price_info.get("yesterday", [])
    today_prices = price_info.get("today", [])
    tomorrow_prices = price_info.get("tomorrow", [])

    all_prices = yesterday_prices + today_prices + tomorrow_prices
    if not all_prices:
        return None

    now = time.now()
    return calculate_trailing_24h_min(all_prices, now, time=time)


def calculate_current_trailing_max(
    coordinator_data: dict,
    *,
    time: TimeService,
) -> float | None:
    """
    Calculate the trailing 24-hour maximum for the current time.

    Args:
        coordinator_data: The coordinator data containing priceInfo
        time: TimeService instance (required)

    Returns:
        Current trailing 24-hour maximum price, or None if unavailable

    """
    if not coordinator_data:
        return None

    price_info = coordinator_data.get("priceInfo", {})
    yesterday_prices = price_info.get("yesterday", [])
    today_prices = price_info.get("today", [])
    tomorrow_prices = price_info.get("tomorrow", [])

    all_prices = yesterday_prices + today_prices + tomorrow_prices
    if not all_prices:
        return None

    now = time.now()
    return calculate_trailing_24h_max(all_prices, now, time=time)


def calculate_current_leading_min(
    coordinator_data: dict,
    *,
    time: TimeService,
) -> float | None:
    """
    Calculate the leading 24-hour minimum for the current time.

    Args:
        coordinator_data: The coordinator data containing priceInfo
        time: TimeService instance (required)

    Returns:
        Current leading 24-hour minimum price, or None if unavailable

    """
    if not coordinator_data:
        return None

    price_info = coordinator_data.get("priceInfo", {})
    yesterday_prices = price_info.get("yesterday", [])
    today_prices = price_info.get("today", [])
    tomorrow_prices = price_info.get("tomorrow", [])

    all_prices = yesterday_prices + today_prices + tomorrow_prices
    if not all_prices:
        return None

    now = time.now()
    return calculate_leading_24h_min(all_prices, now, time=time)


def calculate_current_leading_max(
    coordinator_data: dict,
    *,
    time: TimeService,
) -> float | None:
    """
    Calculate the leading 24-hour maximum for the current time.

    Args:
        coordinator_data: The coordinator data containing priceInfo
        time: TimeService instance (required)

    Returns:
        Current leading 24-hour maximum price, or None if unavailable

    """
    if not coordinator_data:
        return None

    price_info = coordinator_data.get("priceInfo", {})
    yesterday_prices = price_info.get("yesterday", [])
    today_prices = price_info.get("today", [])
    tomorrow_prices = price_info.get("tomorrow", [])

    all_prices = yesterday_prices + today_prices + tomorrow_prices
    if not all_prices:
        return None

    now = time.now()
    return calculate_leading_24h_max(all_prices, now, time=time)


def calculate_next_n_hours_avg(
    coordinator_data: dict,
    hours: int,
    *,
    time: TimeService,
) -> float | None:
    """
    Calculate average price for the next N hours starting from the next interval.

    This function computes the average of all 15-minute intervals starting from
    the next interval (not current) up to N hours into the future.

    Args:
        coordinator_data: The coordinator data containing priceInfo
        hours: Number of hours to look ahead (1, 2, 3, 4, 5, 6, 8, 12, etc.)
        time: TimeService instance (required)

    Returns:
        Average price for the next N hours, or None if insufficient data

    """
    if not coordinator_data or hours <= 0:
        return None

    price_info = coordinator_data.get("priceInfo", {})
    yesterday_prices = price_info.get("yesterday", [])
    today_prices = price_info.get("today", [])
    tomorrow_prices = price_info.get("tomorrow", [])

    all_prices = yesterday_prices + today_prices + tomorrow_prices
    if not all_prices:
        return None

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
        return None

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
        return None

    # Return average (prefer full period, but allow graceful degradation)
    return sum(prices_in_window) / len(prices_in_window)
