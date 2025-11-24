"""24-hour window attribute builders for Tibber Prices sensors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.tibber_prices.coordinator.helpers import get_intervals_for_day_offsets

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator.core import (
        TibberPricesDataUpdateCoordinator,
    )
    from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService


def _update_extreme_interval(extreme_interval: dict | None, price_data: dict, key: str) -> dict:
    """
    Update extreme interval for min/max sensors.

    Args:
        extreme_interval: Current extreme interval or None
        price_data: New price data to compare
        key: Sensor key to determine if min or max

    Returns:
        Updated extreme interval

    """
    if extreme_interval is None:
        return price_data

    price = price_data.get("total")
    extreme_price = extreme_interval.get("total")

    if price is None or extreme_price is None:
        return extreme_interval

    is_new_extreme = ("min" in key and price < extreme_price) or ("max" in key and price > extreme_price)

    return price_data if is_new_extreme else extreme_interval


def add_average_price_attributes(
    attributes: dict,
    key: str,
    coordinator: TibberPricesDataUpdateCoordinator,
    *,
    time: TibberPricesTimeService,
) -> None:
    """
    Add attributes for trailing and leading average/min/max price sensors.

    Args:
        attributes: Dictionary to add attributes to
        key: The sensor entity key
        coordinator: The data update coordinator
        time: TibberPricesTimeService instance (required)

    """
    # Determine if this is trailing or leading
    is_trailing = "trailing" in key

    # Get all intervals (yesterday, today, tomorrow) via helper
    all_prices = get_intervals_for_day_offsets(coordinator.data, [-1, 0, 1])

    if not all_prices:
        return

    # Calculate the time window using TimeService
    if is_trailing:
        window_start, window_end = time.get_trailing_window(hours=24)
    else:
        window_start, window_end = time.get_leading_window(hours=24)

    # Find all intervals in the window
    intervals_in_window = []
    extreme_interval = None  # Track interval with min/max for min/max sensors
    is_min_max_sensor = "min" in key or "max" in key

    for price_data in all_prices:
        starts_at = time.get_interval_time(price_data)
        if starts_at is None:
            continue
        if window_start <= starts_at < window_end:
            intervals_in_window.append(price_data)

            # Track extreme interval for min/max sensors
            if is_min_max_sensor:
                extreme_interval = _update_extreme_interval(extreme_interval, price_data, key)

    # Add timestamp attribute
    if intervals_in_window:
        # For min/max sensors: use the timestamp of the interval with extreme price
        # For average sensors: use first interval in the window
        if extreme_interval and is_min_max_sensor:
            attributes["timestamp"] = extreme_interval.get("startsAt")
        else:
            attributes["timestamp"] = intervals_in_window[0].get("startsAt")

        attributes["interval_count"] = len(intervals_in_window)
