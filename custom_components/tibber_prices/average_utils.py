"""Utility functions for calculating price averages."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.util import dt as dt_util

# Constants
INTERVALS_PER_DAY = 96  # 24 hours * 4 intervals per hour


def round_to_nearest_quarter_hour(dt: datetime) -> datetime:
    """
    Round datetime to nearest 15-minute boundary with smart tolerance.

    This handles edge cases where HA schedules us slightly before the boundary
    (e.g., 14:59:59.500), while avoiding premature rounding during normal operation.

    Strategy:
    - If within ±2 seconds of a boundary → round to that boundary
    - Otherwise → floor to current interval start

    Examples:
    - 14:59:57.999 → 15:00:00 (within 2s of boundary)
    - 14:59:59.999 → 15:00:00 (within 2s of boundary)
    - 14:59:30.000 → 14:45:00 (NOT within 2s, stay in current)
    - 15:00:00.000 → 15:00:00 (exact boundary)
    - 15:00:01.500 → 15:00:00 (within 2s of boundary)

    Args:
        dt: Datetime to round

    Returns:
        Datetime rounded to appropriate 15-minute boundary

    """
    # Calculate current interval start (floor)
    total_seconds = dt.hour * 3600 + dt.minute * 60 + dt.second + dt.microsecond / 1_000_000
    interval_index = int(total_seconds // (15 * 60))  # Floor division
    interval_start_seconds = interval_index * 15 * 60

    # Calculate next interval start
    next_interval_index = (interval_index + 1) % INTERVALS_PER_DAY
    next_interval_start_seconds = next_interval_index * 15 * 60

    # Distance to current interval start and next interval start
    distance_to_current = total_seconds - interval_start_seconds
    if next_interval_index == 0:  # Midnight wrap
        distance_to_next = (24 * 3600) - total_seconds
    else:
        distance_to_next = next_interval_start_seconds - total_seconds

    # Tolerance: If within 2 seconds of a boundary, snap to it
    boundary_tolerance_seconds = 2.0

    if distance_to_next <= boundary_tolerance_seconds:
        # Very close to next boundary → use next interval
        target_interval_index = next_interval_index
    elif distance_to_current <= boundary_tolerance_seconds:
        # Very close to current boundary (shouldn't happen in practice, but handle it)
        target_interval_index = interval_index
    else:
        # Normal case: stay in current interval
        target_interval_index = interval_index

    # Convert back to time
    target_minutes = target_interval_index * 15
    target_hour = int(target_minutes // 60)
    target_minute = int(target_minutes % 60)

    return dt.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)


def calculate_trailing_24h_avg(all_prices: list[dict], interval_start: datetime) -> float:
    """
    Calculate trailing 24-hour average price for a given interval.

    Args:
        all_prices: List of all price data (yesterday, today, tomorrow combined)
        interval_start: Start time of the interval to calculate average for

    Returns:
        Average price for the 24 hours preceding the interval (not including the interval itself)

    """
    # Define the 24-hour window: from 24 hours before interval_start up to interval_start
    window_start = interval_start - timedelta(hours=24)
    window_end = interval_start

    # Filter prices within the 24-hour window
    prices_in_window = []
    for price_data in all_prices:
        starts_at = dt_util.parse_datetime(price_data["startsAt"])
        if starts_at is None:
            continue
        starts_at = dt_util.as_local(starts_at)
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

    Returns:
        Average price for up to 24 hours following the interval (including the interval itself)

    """
    # Define the 24-hour window: from interval_start up to 24 hours after
    window_start = interval_start
    window_end = interval_start + timedelta(hours=24)

    # Filter prices within the 24-hour window
    prices_in_window = []
    for price_data in all_prices:
        starts_at = dt_util.parse_datetime(price_data["startsAt"])
        if starts_at is None:
            continue
        starts_at = dt_util.as_local(starts_at)
        # Include intervals that start within the window
        if window_start <= starts_at < window_end:
            prices_in_window.append(float(price_data["total"]))

    # Calculate average
    if prices_in_window:
        return sum(prices_in_window) / len(prices_in_window)
    return 0.0


def calculate_current_trailing_avg(coordinator_data: dict) -> float | None:
    """
    Calculate the trailing 24-hour average for the current time.

    Args:
        coordinator_data: The coordinator data containing priceInfo

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

    now = dt_util.now()
    return calculate_trailing_24h_avg(all_prices, now)


def calculate_current_leading_avg(coordinator_data: dict) -> float | None:
    """
    Calculate the leading 24-hour average for the current time.

    Args:
        coordinator_data: The coordinator data containing priceInfo

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

    now = dt_util.now()
    return calculate_leading_24h_avg(all_prices, now)


def calculate_trailing_24h_min(all_prices: list[dict], interval_start: datetime) -> float:
    """
    Calculate trailing 24-hour minimum price for a given interval.

    Args:
        all_prices: List of all price data (yesterday, today, tomorrow combined)
        interval_start: Start time of the interval to calculate minimum for

    Returns:
        Minimum price for the 24 hours preceding the interval (not including the interval itself)

    """
    # Define the 24-hour window: from 24 hours before interval_start up to interval_start
    window_start = interval_start - timedelta(hours=24)
    window_end = interval_start

    # Filter prices within the 24-hour window
    prices_in_window = []
    for price_data in all_prices:
        starts_at = dt_util.parse_datetime(price_data["startsAt"])
        if starts_at is None:
            continue
        starts_at = dt_util.as_local(starts_at)
        # Include intervals that start within the window (not including the current interval's end)
        if window_start <= starts_at < window_end:
            prices_in_window.append(float(price_data["total"]))

    # Calculate minimum
    if prices_in_window:
        return min(prices_in_window)
    return 0.0


def calculate_trailing_24h_max(all_prices: list[dict], interval_start: datetime) -> float:
    """
    Calculate trailing 24-hour maximum price for a given interval.

    Args:
        all_prices: List of all price data (yesterday, today, tomorrow combined)
        interval_start: Start time of the interval to calculate maximum for

    Returns:
        Maximum price for the 24 hours preceding the interval (not including the interval itself)

    """
    # Define the 24-hour window: from 24 hours before interval_start up to interval_start
    window_start = interval_start - timedelta(hours=24)
    window_end = interval_start

    # Filter prices within the 24-hour window
    prices_in_window = []
    for price_data in all_prices:
        starts_at = dt_util.parse_datetime(price_data["startsAt"])
        if starts_at is None:
            continue
        starts_at = dt_util.as_local(starts_at)
        # Include intervals that start within the window (not including the current interval's end)
        if window_start <= starts_at < window_end:
            prices_in_window.append(float(price_data["total"]))

    # Calculate maximum
    if prices_in_window:
        return max(prices_in_window)
    return 0.0


def calculate_leading_24h_min(all_prices: list[dict], interval_start: datetime) -> float:
    """
    Calculate leading 24-hour minimum price for a given interval.

    Args:
        all_prices: List of all price data (yesterday, today, tomorrow combined)
        interval_start: Start time of the interval to calculate minimum for

    Returns:
        Minimum price for up to 24 hours following the interval (including the interval itself)

    """
    # Define the 24-hour window: from interval_start up to 24 hours after
    window_start = interval_start
    window_end = interval_start + timedelta(hours=24)

    # Filter prices within the 24-hour window
    prices_in_window = []
    for price_data in all_prices:
        starts_at = dt_util.parse_datetime(price_data["startsAt"])
        if starts_at is None:
            continue
        starts_at = dt_util.as_local(starts_at)
        # Include intervals that start within the window
        if window_start <= starts_at < window_end:
            prices_in_window.append(float(price_data["total"]))

    # Calculate minimum
    if prices_in_window:
        return min(prices_in_window)
    return 0.0


def calculate_leading_24h_max(all_prices: list[dict], interval_start: datetime) -> float:
    """
    Calculate leading 24-hour maximum price for a given interval.

    Args:
        all_prices: List of all price data (yesterday, today, tomorrow combined)
        interval_start: Start time of the interval to calculate maximum for

    Returns:
        Maximum price for up to 24 hours following the interval (including the interval itself)

    """
    # Define the 24-hour window: from interval_start up to 24 hours after
    window_start = interval_start
    window_end = interval_start + timedelta(hours=24)

    # Filter prices within the 24-hour window
    prices_in_window = []
    for price_data in all_prices:
        starts_at = dt_util.parse_datetime(price_data["startsAt"])
        if starts_at is None:
            continue
        starts_at = dt_util.as_local(starts_at)
        # Include intervals that start within the window
        if window_start <= starts_at < window_end:
            prices_in_window.append(float(price_data["total"]))

    # Calculate maximum
    if prices_in_window:
        return max(prices_in_window)
    return 0.0


def calculate_current_trailing_min(coordinator_data: dict) -> float | None:
    """
    Calculate the trailing 24-hour minimum for the current time.

    Args:
        coordinator_data: The coordinator data containing priceInfo

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

    now = dt_util.now()
    return calculate_trailing_24h_min(all_prices, now)


def calculate_current_trailing_max(coordinator_data: dict) -> float | None:
    """
    Calculate the trailing 24-hour maximum for the current time.

    Args:
        coordinator_data: The coordinator data containing priceInfo

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

    now = dt_util.now()
    return calculate_trailing_24h_max(all_prices, now)


def calculate_current_leading_min(coordinator_data: dict) -> float | None:
    """
    Calculate the leading 24-hour minimum for the current time.

    Args:
        coordinator_data: The coordinator data containing priceInfo

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

    now = dt_util.now()
    return calculate_leading_24h_min(all_prices, now)


def calculate_current_leading_max(coordinator_data: dict) -> float | None:
    """
    Calculate the leading 24-hour maximum for the current time.

    Args:
        coordinator_data: The coordinator data containing priceInfo

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

    now = dt_util.now()
    return calculate_leading_24h_max(all_prices, now)


def calculate_next_n_hours_avg(coordinator_data: dict, hours: int) -> float | None:
    """
    Calculate average price for the next N hours starting from the next interval.

    This function computes the average of all 15-minute intervals starting from
    the next interval (not current) up to N hours into the future.

    Args:
        coordinator_data: The coordinator data containing priceInfo
        hours: Number of hours to look ahead (1, 2, 3, 4, 5, 6, 8, 12, etc.)

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

    now = dt_util.now()

    # Find the current interval index
    current_idx = None
    for idx, price_data in enumerate(all_prices):
        starts_at = dt_util.parse_datetime(price_data["startsAt"])
        if starts_at is None:
            continue
        starts_at = dt_util.as_local(starts_at)
        interval_end = starts_at + timedelta(minutes=15)

        if starts_at <= now < interval_end:
            current_idx = idx
            break

    if current_idx is None:
        return None

    # Calculate how many 15-minute intervals are in N hours
    intervals_needed = hours * 4  # 4 intervals per hour

    # Collect prices starting from NEXT interval (current_idx + 1)
    prices_in_window = []
    for offset in range(1, intervals_needed + 1):
        idx = current_idx + offset
        if idx < len(all_prices):
            price = all_prices[idx].get("total")
            if price is not None:
                prices_in_window.append(float(price))
        else:
            # Not enough future data available
            break

    # Only return average if we have data for the full requested period
    if len(prices_in_window) >= intervals_needed:
        return sum(prices_in_window) / len(prices_in_window)

    # If we don't have enough data for full period, return what we have
    # (allows graceful degradation when tomorrow's data isn't available yet)
    if prices_in_window:
        return sum(prices_in_window) / len(prices_in_window)

    return None
