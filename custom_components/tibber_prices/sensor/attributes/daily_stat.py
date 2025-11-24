"""Daily statistics attribute builders for Tibber Prices sensors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.tibber_prices.const import PRICE_RATING_MAPPING
from custom_components.tibber_prices.coordinator.helpers import (
    get_intervals_for_day_offsets,
)
from homeassistant.const import PERCENTAGE

if TYPE_CHECKING:
    from datetime import datetime

    from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService


def _get_day_midnight_timestamp(key: str, *, time: TibberPricesTimeService) -> datetime:
    """Get midnight timestamp for a given day sensor key (returns datetime object)."""
    # Determine which day based on sensor key
    if key.startswith("yesterday") or key == "average_price_yesterday":
        day = "yesterday"
    elif key.startswith("tomorrow") or key == "average_price_tomorrow":
        day = "tomorrow"
    else:
        day = "today"

    # Use TimeService to get midnight for that day
    local_midnight, _ = time.get_day_boundaries(day)
    return local_midnight


def _get_day_key_from_sensor_key(key: str) -> str:
    """
    Extract day key (yesterday/today/tomorrow) from sensor key.

    Args:
        key: The sensor entity key

    Returns:
        Day key: "yesterday", "today", or "tomorrow"

    """
    if "yesterday" in key:
        return "yesterday"
    if "tomorrow" in key:
        return "tomorrow"
    return "today"


def _add_fallback_timestamp(
    attributes: dict,
    key: str,
    price_info: dict,
) -> None:
    """
    Add fallback timestamp to attributes based on the day in the sensor key.

    Args:
        attributes: Dictionary to add timestamp to
        key: The sensor entity key
        price_info: Price info dictionary from coordinator data (flat structure)

    """
    day_key = _get_day_key_from_sensor_key(key)

    # Use helper to get intervals for this day
    # Build minimal coordinator_data structure for helper
    coordinator_data = {"priceInfo": price_info}
    # Map day key to offset: yesterday=-1, today=0, tomorrow=1
    day_offset = {"yesterday": -1, "today": 0, "tomorrow": 1}[day_key]
    day_intervals = get_intervals_for_day_offsets(coordinator_data, [day_offset])

    # Use first interval's timestamp if available
    if day_intervals:
        attributes["timestamp"] = day_intervals[0].get("startsAt")


def add_statistics_attributes(
    attributes: dict,
    key: str,
    cached_data: dict,
    *,
    time: TibberPricesTimeService,
) -> None:
    """
    Add attributes for statistics and rating sensors.

    Args:
        attributes: Dictionary to add attributes to
        key: The sensor entity key
        cached_data: Dictionary containing cached sensor data
        time: TibberPricesTimeService instance (required)

    """
    # Data timestamp sensor - shows API fetch time
    if key == "data_timestamp":
        latest_timestamp = cached_data.get("data_timestamp")
        if latest_timestamp:
            attributes["timestamp"] = latest_timestamp
        return

    # Current interval price rating - add rating attributes
    if key == "current_interval_price_rating":
        if cached_data.get("last_rating_difference") is not None:
            attributes["diff_" + PERCENTAGE] = cached_data["last_rating_difference"]
        if cached_data.get("last_rating_level") is not None:
            attributes["level_id"] = cached_data["last_rating_level"]
            attributes["level_value"] = PRICE_RATING_MAPPING.get(
                cached_data["last_rating_level"], cached_data["last_rating_level"]
            )
        return

    # Extreme value sensors - show when the extreme occurs
    extreme_sensors = {
        "lowest_price_today",
        "highest_price_today",
        "lowest_price_tomorrow",
        "highest_price_tomorrow",
    }
    if key in extreme_sensors:
        if cached_data.get("last_extreme_interval"):
            extreme_starts_at = cached_data["last_extreme_interval"].get("startsAt")
            if extreme_starts_at:
                attributes["timestamp"] = extreme_starts_at
        return

    # Daily average sensors - show midnight to indicate whole day
    daily_avg_sensors = {"average_price_today", "average_price_tomorrow"}
    if key in daily_avg_sensors:
        attributes["timestamp"] = _get_day_midnight_timestamp(key, time=time)
        return

    # Daily aggregated level/rating sensors - show midnight to indicate whole day
    daily_aggregated_sensors = {
        "yesterday_price_level",
        "today_price_level",
        "tomorrow_price_level",
        "yesterday_price_rating",
        "today_price_rating",
        "tomorrow_price_rating",
    }
    if key in daily_aggregated_sensors:
        attributes["timestamp"] = _get_day_midnight_timestamp(key, time=time)
        return

    # All other statistics sensors - keep default timestamp (when calculation was made)
