"""Future price/trend attribute builders for Tibber Prices sensors."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator.core import (
        TibberPricesDataUpdateCoordinator,
    )
    from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService

# Constants
MAX_FORECAST_INTERVALS = 8  # Show up to 8 future intervals (2 hours with 15-min intervals)


def add_next_avg_attributes(
    attributes: dict,
    key: str,
    coordinator: TibberPricesDataUpdateCoordinator,
    *,
    time: TibberPricesTimeService,
) -> None:
    """
    Add attributes for next N hours average price sensors.

    Args:
        attributes: Dictionary to add attributes to
        key: The sensor entity key
        coordinator: The data update coordinator
        time: TibberPricesTimeService instance (required)

    """
    # Extract hours from sensor key (e.g., "next_avg_3h" -> 3)
    try:
        hours = int(key.split("_")[-1].replace("h", ""))
    except (ValueError, AttributeError):
        return

    # Use TimeService to get the N-hour window starting from next interval
    next_interval_start, window_end = time.get_next_n_hours_window(hours)

    # Get all price intervals
    price_info = coordinator.data.get("priceInfo", {})
    today_prices = price_info.get("today", [])
    tomorrow_prices = price_info.get("tomorrow", [])
    all_prices = today_prices + tomorrow_prices

    if not all_prices:
        return

    # Find all intervals in the window
    intervals_in_window = []
    for price_data in all_prices:
        starts_at = time.get_interval_time(price_data)
        if starts_at is None:
            continue
        if next_interval_start <= starts_at < window_end:
            intervals_in_window.append(price_data)

    # Add timestamp attribute (start of next interval - where calculation begins)
    if intervals_in_window:
        attributes["timestamp"] = intervals_in_window[0].get("startsAt")
        attributes["interval_count"] = len(intervals_in_window)
        attributes["hours"] = hours


def get_future_prices(
    coordinator: TibberPricesDataUpdateCoordinator,
    max_intervals: int | None = None,
    *,
    time: TibberPricesTimeService,
) -> list[dict] | None:
    """
    Get future price data for multiple upcoming intervals.

    Args:
        coordinator: The data update coordinator
        max_intervals: Maximum number of future intervals to return
        time: TibberPricesTimeService instance (required)

    Returns:
        List of upcoming price intervals with timestamps and prices

    """
    if not coordinator.data:
        return None

    price_info = coordinator.data.get("priceInfo", {})

    today_prices = price_info.get("today", [])
    tomorrow_prices = price_info.get("tomorrow", [])
    all_prices = today_prices + tomorrow_prices

    if not all_prices:
        return None

    # Initialize the result list
    future_prices = []

    # Track the maximum intervals to return
    intervals_to_return = MAX_FORECAST_INTERVALS if max_intervals is None else max_intervals

    for day_key in ["today", "tomorrow"]:
        for price_data in price_info.get(day_key, []):
            starts_at = time.get_interval_time(price_data)
            if starts_at is None:
                continue

            interval_end = starts_at + time.get_interval_duration()

            # Use TimeService to check if interval is in future
            if time.is_in_future(starts_at):
                future_prices.append(
                    {
                        "interval_start": starts_at,
                        "interval_end": interval_end,
                        "price": float(price_data["total"]),
                        "price_minor": round(float(price_data["total"]) * 100, 2),
                        "level": price_data.get("level", "NORMAL"),
                        "rating": price_data.get("difference", None),
                        "rating_level": price_data.get("rating_level"),
                        "day": day_key,
                    }
                )

    # Sort by start time
    future_prices.sort(key=lambda x: x["interval_start"])

    # Limit to the requested number of intervals
    return future_prices[:intervals_to_return] if future_prices else None
