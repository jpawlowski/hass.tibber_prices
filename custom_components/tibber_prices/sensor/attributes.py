"""
Attribute builders for Tibber Prices sensors.

This module contains all the attribute building logic extracted from TibberPricesSensor.
Each function takes explicit parameters instead of accessing instance variables.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from custom_components.tibber_prices.const import (
    PRICE_LEVEL_MAPPING,
    PRICE_RATING_MAPPING,
)
from custom_components.tibber_prices.entity_utils import add_icon_color_attribute
from custom_components.tibber_prices.price_utils import (
    MINUTES_PER_INTERVAL,
    calculate_volatility_level,
    find_price_data_for_interval,
)
from homeassistant.const import PERCENTAGE
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator import (
        TibberPricesDataUpdateCoordinator,
    )

# Constants
MAX_FORECAST_INTERVALS = 8  # Show up to 8 future intervals (2 hours with 15-min intervals)


def build_sensor_attributes(
    key: str,
    coordinator: TibberPricesDataUpdateCoordinator,
    native_value: Any,
    cached_data: dict,
) -> dict | None:
    """
    Build attributes for a sensor based on its key.

    Args:
        key: The sensor entity key
        coordinator: The data update coordinator
        native_value: The current native value of the sensor
        cached_data: Dictionary containing cached sensor data
                    (_last_extreme_interval, _trend_attributes, _volatility_attributes, etc.)

    Returns:
        Dictionary of attributes or None if no attributes should be added

    """
    if not coordinator.data:
        return None

    try:
        attributes: dict[str, Any] = {}

        # For trend sensors, use the cached _trend_attributes
        if key.startswith("price_trend_") and cached_data.get("trend_attributes"):
            attributes.update(cached_data["trend_attributes"])

        # Group sensors by type and delegate to specific handlers
        if key in [
            "current_interval_price",
            "current_interval_price_level",
            "next_interval_price",
            "previous_interval_price",
            "current_hour_average",
            "next_hour_average",
            "next_interval_price_level",
            "previous_interval_price_level",
            "current_hour_price_level",
            "next_hour_price_level",
            "next_interval_price_rating",
            "previous_interval_price_rating",
            "current_hour_price_rating",
            "next_hour_price_rating",
        ]:
            add_current_interval_price_attributes(
                attributes=attributes,
                key=key,
                coordinator=coordinator,
                native_value=native_value,
                cached_data=cached_data,
            )
        elif key in [
            "trailing_price_average",
            "leading_price_average",
            "trailing_price_min",
            "trailing_price_max",
            "leading_price_min",
            "leading_price_max",
        ]:
            add_average_price_attributes(attributes=attributes, key=key, coordinator=coordinator)
        elif key.startswith("next_avg_"):
            add_next_avg_attributes(attributes=attributes, key=key, coordinator=coordinator)
        elif any(pattern in key for pattern in ["_price_today", "_price_tomorrow", "rating", "data_timestamp"]):
            add_statistics_attributes(
                attributes=attributes,
                key=key,
                coordinator=coordinator,
                cached_data=cached_data,
            )
        elif key == "price_forecast":
            add_price_forecast_attributes(attributes=attributes, coordinator=coordinator)
        elif key.endswith("_volatility"):
            add_volatility_attributes(attributes=attributes, cached_data=cached_data)

        # For price_level, add the original level as attribute
        if key == "current_interval_price_level" and cached_data.get("last_price_level") is not None:
            attributes["level_id"] = cached_data["last_price_level"]

    except (KeyError, ValueError, TypeError) as ex:
        coordinator.logger.exception(
            "Error getting sensor attributes",
            extra={
                "error": str(ex),
                "entity": key,
            },
        )
        return None
    else:
        return attributes if attributes else None


def add_current_interval_price_attributes(
    attributes: dict,
    key: str,
    coordinator: TibberPricesDataUpdateCoordinator,
    native_value: Any,
    cached_data: dict,
) -> None:
    """
    Add attributes for current interval price sensors.

    Args:
        attributes: Dictionary to add attributes to
        key: The sensor entity key
        coordinator: The data update coordinator
        native_value: The current native value of the sensor
        cached_data: Dictionary containing cached sensor data

    """
    price_info = coordinator.data.get("priceInfo", {}) if coordinator.data else {}
    now = dt_util.now()

    # Determine which interval to use based on sensor type
    next_interval_sensors = [
        "next_interval_price",
        "next_interval_price_level",
        "next_interval_price_rating",
    ]
    previous_interval_sensors = [
        "previous_interval_price",
        "previous_interval_price_level",
        "previous_interval_price_rating",
    ]
    next_hour_sensors = [
        "next_hour_average",
        "next_hour_price_level",
        "next_hour_price_rating",
    ]
    current_hour_sensors = [
        "current_hour_average",
        "current_hour_price_level",
        "current_hour_price_rating",
    ]

    # Set timestamp and interval data based on sensor type
    interval_data = None
    if key in next_interval_sensors:
        target_time = now + timedelta(minutes=MINUTES_PER_INTERVAL)
        interval_data = find_price_data_for_interval(price_info, target_time)
        attributes["timestamp"] = interval_data["startsAt"] if interval_data else None
    elif key in previous_interval_sensors:
        target_time = now - timedelta(minutes=MINUTES_PER_INTERVAL)
        interval_data = find_price_data_for_interval(price_info, target_time)
        attributes["timestamp"] = interval_data["startsAt"] if interval_data else None
    elif key in next_hour_sensors:
        target_time = now + timedelta(hours=1)
        interval_data = find_price_data_for_interval(price_info, target_time)
        attributes["timestamp"] = interval_data["startsAt"] if interval_data else None
    elif key in current_hour_sensors:
        current_interval_data = get_current_interval_data(coordinator)
        attributes["timestamp"] = current_interval_data["startsAt"] if current_interval_data else None
    else:
        current_interval_data = get_current_interval_data(coordinator)
        attributes["timestamp"] = current_interval_data["startsAt"] if current_interval_data else None

    # Add icon_color for price sensors (based on their price level)
    if key in ["current_interval_price", "next_interval_price", "previous_interval_price"]:
        # For interval-based price sensors, get level from interval_data
        if interval_data and "level" in interval_data:
            level = interval_data["level"]
            add_icon_color_attribute(attributes, key="price_level", state_value=level)
    elif key in ["current_hour_average", "next_hour_average"]:
        # For hour-based price sensors, get level from cached_data
        level = cached_data.get("rolling_hour_level")
        if level:
            add_icon_color_attribute(attributes, key="price_level", state_value=level)

    # Add price level attributes for all level sensors
    add_level_attributes_for_sensor(
        attributes=attributes,
        key=key,
        interval_data=interval_data,
        coordinator=coordinator,
        native_value=native_value,
    )

    # Add price rating attributes for all rating sensors
    add_rating_attributes_for_sensor(
        attributes=attributes,
        key=key,
        interval_data=interval_data,
        coordinator=coordinator,
        native_value=native_value,
    )


def add_level_attributes_for_sensor(
    attributes: dict,
    key: str,
    interval_data: dict | None,
    coordinator: TibberPricesDataUpdateCoordinator,
    native_value: Any,
) -> None:
    """
    Add price level attributes based on sensor type.

    Args:
        attributes: Dictionary to add attributes to
        key: The sensor entity key
        interval_data: Interval data for next/previous sensors
        coordinator: The data update coordinator
        native_value: The current native value of the sensor

    """
    # For interval-based level sensors (next/previous), use interval data
    if key in ["next_interval_price_level", "previous_interval_price_level"]:
        if interval_data and "level" in interval_data:
            add_price_level_attributes(attributes, interval_data["level"])
    # For hour-aggregated level sensors, use native_value
    elif key in ["current_hour_price_level", "next_hour_price_level"]:
        level_value = native_value
        if level_value and isinstance(level_value, str):
            add_price_level_attributes(attributes, level_value.upper())
    # For current price level sensor
    elif key == "current_interval_price_level":
        current_interval_data = get_current_interval_data(coordinator)
        if current_interval_data and "level" in current_interval_data:
            add_price_level_attributes(attributes, current_interval_data["level"])


def add_price_level_attributes(attributes: dict, level: str) -> None:
    """
    Add price level specific attributes.

    Args:
        attributes: Dictionary to add attributes to
        level: The price level value (e.g., VERY_CHEAP, NORMAL, etc.)

    """
    if level in PRICE_LEVEL_MAPPING:
        attributes["level_value"] = PRICE_LEVEL_MAPPING[level]
    attributes["level_id"] = level

    # Add icon_color for dynamic styling
    add_icon_color_attribute(attributes, key="price_level", state_value=level)


def add_rating_attributes_for_sensor(
    attributes: dict,
    key: str,
    interval_data: dict | None,
    coordinator: TibberPricesDataUpdateCoordinator,
    native_value: Any,
) -> None:
    """
    Add price rating attributes based on sensor type.

    Args:
        attributes: Dictionary to add attributes to
        key: The sensor entity key
        interval_data: Interval data for next/previous sensors
        coordinator: The data update coordinator
        native_value: The current native value of the sensor

    """
    # For interval-based rating sensors (next/previous), use interval data
    if key in ["next_interval_price_rating", "previous_interval_price_rating"]:
        if interval_data and "rating_level" in interval_data:
            add_price_rating_attributes(attributes, interval_data["rating_level"])
    # For hour-aggregated rating sensors, use native_value
    elif key in ["current_hour_price_rating", "next_hour_price_rating"]:
        rating_value = native_value
        if rating_value and isinstance(rating_value, str):
            add_price_rating_attributes(attributes, rating_value.upper())
    # For current price rating sensor
    elif key == "current_interval_price_rating":
        current_interval_data = get_current_interval_data(coordinator)
        if current_interval_data and "rating_level" in current_interval_data:
            add_price_rating_attributes(attributes, current_interval_data["rating_level"])


def add_price_rating_attributes(attributes: dict, rating: str) -> None:
    """
    Add price rating specific attributes.

    Args:
        attributes: Dictionary to add attributes to
        rating: The price rating value (e.g., LOW, NORMAL, HIGH)

    """
    if rating in PRICE_RATING_MAPPING:
        attributes["rating_value"] = PRICE_RATING_MAPPING[rating]
    attributes["rating_id"] = rating

    # Add icon_color for dynamic styling
    add_icon_color_attribute(attributes, key="price_rating", state_value=rating)


def add_statistics_attributes(
    attributes: dict,
    key: str,
    coordinator: TibberPricesDataUpdateCoordinator,
    cached_data: dict,
) -> None:
    """
    Add attributes for statistics and rating sensors.

    Args:
        attributes: Dictionary to add attributes to
        key: The sensor entity key
        coordinator: The data update coordinator
        cached_data: Dictionary containing cached sensor data

    """
    price_info = coordinator.data.get("priceInfo", {})
    now = dt_util.now()

    if key == "data_timestamp":
        # For data_timestamp sensor, use the latest timestamp from cached_data
        latest_timestamp = cached_data.get("data_timestamp")
        if latest_timestamp:
            attributes["timestamp"] = latest_timestamp.isoformat()
    elif key == "current_interval_price_rating":
        interval_data = find_price_data_for_interval(price_info, now)
        attributes["timestamp"] = interval_data["startsAt"] if interval_data else None
        if cached_data.get("last_rating_difference") is not None:
            attributes["diff_" + PERCENTAGE] = cached_data["last_rating_difference"]
        if cached_data.get("last_rating_level") is not None:
            attributes["level_id"] = cached_data["last_rating_level"]
            attributes["level_value"] = PRICE_RATING_MAPPING.get(
                cached_data["last_rating_level"], cached_data["last_rating_level"]
            )
    elif key in [
        "lowest_price_today",
        "highest_price_today",
        "lowest_price_tomorrow",
        "highest_price_tomorrow",
    ]:
        # Use the timestamp from the interval that has the extreme price
        if cached_data.get("last_extreme_interval"):
            attributes["timestamp"] = cached_data["last_extreme_interval"].get("startsAt")
        else:
            # Fallback: use the first timestamp of the appropriate day
            day_key = "tomorrow" if "tomorrow" in key else "today"
            day_data = price_info.get(day_key, [])
            if day_data:
                attributes["timestamp"] = day_data[0].get("startsAt")
    else:
        # Fallback: use the first timestamp of the appropriate day
        day_key = "tomorrow" if "tomorrow" in key else "today"
        day_data = price_info.get(day_key, [])
        if day_data:
            attributes["timestamp"] = day_data[0].get("startsAt")


def add_average_price_attributes(
    attributes: dict,
    key: str,
    coordinator: TibberPricesDataUpdateCoordinator,
) -> None:
    """
    Add attributes for trailing and leading average price sensors.

    Args:
        attributes: Dictionary to add attributes to
        key: The sensor entity key
        coordinator: The data update coordinator

    """
    now = dt_util.now()

    # Determine if this is trailing or leading
    is_trailing = "trailing" in key

    # Get all price intervals
    price_info = coordinator.data.get("priceInfo", {})
    yesterday_prices = price_info.get("yesterday", [])
    today_prices = price_info.get("today", [])
    tomorrow_prices = price_info.get("tomorrow", [])
    all_prices = yesterday_prices + today_prices + tomorrow_prices

    if not all_prices:
        return

    # Calculate the time window
    if is_trailing:
        window_start = now - timedelta(hours=24)
        window_end = now
    else:
        window_start = now
        window_end = now + timedelta(hours=24)

    # Find all intervals in the window and get first/last timestamps
    intervals_in_window = []
    for price_data in all_prices:
        starts_at = dt_util.parse_datetime(price_data["startsAt"])
        if starts_at is None:
            continue
        starts_at = dt_util.as_local(starts_at)
        if window_start <= starts_at < window_end:
            intervals_in_window.append(price_data)

    # Add timestamp attribute (first interval in the window)
    if intervals_in_window:
        attributes["timestamp"] = intervals_in_window[0].get("startsAt")
        attributes["interval_count"] = len(intervals_in_window)


def add_next_avg_attributes(
    attributes: dict,
    key: str,
    coordinator: TibberPricesDataUpdateCoordinator,
) -> None:
    """
    Add attributes for next N hours average price sensors.

    Args:
        attributes: Dictionary to add attributes to
        key: The sensor entity key
        coordinator: The data update coordinator

    """
    now = dt_util.now()

    # Extract hours from sensor key (e.g., "next_avg_3h" -> 3)
    try:
        hours = int(key.replace("next_avg_", "").replace("h", ""))
    except (ValueError, AttributeError):
        return

    # Get next interval start time (this is where the calculation begins)
    next_interval_start = now + timedelta(minutes=MINUTES_PER_INTERVAL)

    # Calculate the end of the time window
    window_end = next_interval_start + timedelta(hours=hours)

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
        starts_at = dt_util.parse_datetime(price_data["startsAt"])
        if starts_at is None:
            continue
        starts_at = dt_util.as_local(starts_at)
        if next_interval_start <= starts_at < window_end:
            intervals_in_window.append(price_data)

    # Add timestamp attribute (start of next interval - where calculation begins)
    if intervals_in_window:
        attributes["timestamp"] = intervals_in_window[0].get("startsAt")
        attributes["interval_count"] = len(intervals_in_window)
        attributes["hours"] = hours


def add_price_forecast_attributes(
    attributes: dict,
    coordinator: TibberPricesDataUpdateCoordinator,
) -> None:
    """
    Add forecast attributes for the price forecast sensor.

    Args:
        attributes: Dictionary to add attributes to
        coordinator: The data update coordinator

    """
    future_prices = get_future_prices(coordinator, max_intervals=MAX_FORECAST_INTERVALS)
    if not future_prices:
        attributes["intervals"] = []
        attributes["intervals_by_hour"] = []
        attributes["data_available"] = False
        return

    # Add timestamp attribute (first future interval)
    if future_prices:
        attributes["timestamp"] = future_prices[0]["interval_start"]

    attributes["intervals"] = future_prices
    attributes["data_available"] = True

    # Group by hour for easier consumption in dashboards
    hours: dict[str, Any] = {}
    for interval in future_prices:
        starts_at = datetime.fromisoformat(interval["interval_start"])
        hour_key = starts_at.strftime("%Y-%m-%d %H")

        if hour_key not in hours:
            hours[hour_key] = {
                "hour": starts_at.hour,
                "day": interval["day"],
                "date": starts_at.date().isoformat(),
                "intervals": [],
                "min_price": None,
                "max_price": None,
                "avg_price": 0,
                "avg_rating": None,  # Initialize rating tracking
                "ratings_available": False,  # Track if any ratings are available
            }

        # Create interval data with both price and rating info
        interval_data = {
            "minute": starts_at.minute,
            "price": interval["price"],
            "price_minor": interval["price_minor"],
            "level": interval["level"],  # Price level from priceInfo
            "time": starts_at.strftime("%H:%M"),
        }

        # Add rating data if available
        if interval["rating"] is not None:
            interval_data["rating"] = interval["rating"]
            interval_data["rating_level"] = interval["rating_level"]
            hours[hour_key]["ratings_available"] = True

        hours[hour_key]["intervals"].append(interval_data)

        # Track min/max/avg for the hour
        price = interval["price"]
        if hours[hour_key]["min_price"] is None or price < hours[hour_key]["min_price"]:
            hours[hour_key]["min_price"] = price
        if hours[hour_key]["max_price"] is None or price > hours[hour_key]["max_price"]:
            hours[hour_key]["max_price"] = price

    # Calculate averages
    for hour_data in hours.values():
        prices = [interval["price"] for interval in hour_data["intervals"]]
        if prices:
            hour_data["avg_price"] = sum(prices) / len(prices)
            hour_data["min_price"] = hour_data["min_price"]
            hour_data["max_price"] = hour_data["max_price"]

            # Calculate average rating if ratings are available
            if hour_data["ratings_available"]:
                ratings = [interval.get("rating") for interval in hour_data["intervals"] if "rating" in interval]
                if ratings:
                    hour_data["avg_rating"] = sum(ratings) / len(ratings)

    # Convert to list sorted by hour
    attributes["intervals_by_hour"] = [hour_data for _, hour_data in sorted(hours.items())]


def add_volatility_attributes(
    attributes: dict,
    cached_data: dict,
) -> None:
    """
    Add attributes for volatility sensors.

    Args:
        attributes: Dictionary to add attributes to
        cached_data: Dictionary containing cached sensor data

    """
    if cached_data.get("volatility_attributes"):
        attributes.update(cached_data["volatility_attributes"])


def get_prices_for_volatility(
    volatility_type: str,
    price_info: dict,
) -> list[float]:
    """
    Get price list for volatility calculation based on type.

    Args:
        volatility_type: One of "today", "tomorrow", "next_24h", "today_tomorrow"
        price_info: Price information dictionary from coordinator data

    Returns:
        List of prices to analyze

    """
    if volatility_type == "today":
        return [float(p["total"]) for p in price_info.get("today", []) if "total" in p]

    if volatility_type == "tomorrow":
        return [float(p["total"]) for p in price_info.get("tomorrow", []) if "total" in p]

    if volatility_type == "next_24h":
        # Rolling 24h from now
        now = dt_util.now()
        end_time = now + timedelta(hours=24)
        prices = []

        for day_key in ["today", "tomorrow"]:
            for price_data in price_info.get(day_key, []):
                starts_at = dt_util.parse_datetime(price_data.get("startsAt"))
                if starts_at is None:
                    continue
                starts_at = dt_util.as_local(starts_at)

                if now <= starts_at < end_time and "total" in price_data:
                    prices.append(float(price_data["total"]))
        return prices

    if volatility_type == "today_tomorrow":
        # Combined today + tomorrow
        prices = []
        for day_key in ["today", "tomorrow"]:
            for price_data in price_info.get(day_key, []):
                if "total" in price_data:
                    prices.append(float(price_data["total"]))
        return prices

    return []


def add_volatility_type_attributes(
    volatility_attributes: dict,
    volatility_type: str,
    price_info: dict,
    thresholds: dict,
) -> None:
    """
    Add type-specific attributes for volatility sensors.

    Args:
        volatility_attributes: Dictionary to add type-specific attributes to
        volatility_type: Type of volatility calculation
        price_info: Price information dictionary from coordinator data
        thresholds: Volatility thresholds configuration

    """
    if volatility_type == "today_tomorrow":
        # Add breakdown for today vs tomorrow
        today_prices = [float(p["total"]) for p in price_info.get("today", []) if "total" in p]
        tomorrow_prices = [float(p["total"]) for p in price_info.get("tomorrow", []) if "total" in p]

        if today_prices:
            today_vol = calculate_volatility_level(today_prices, **thresholds)
            today_spread = (max(today_prices) - min(today_prices)) * 100
            volatility_attributes["today_spread"] = round(today_spread, 2)
            volatility_attributes["today_volatility"] = today_vol
            volatility_attributes["interval_count_today"] = len(today_prices)

        if tomorrow_prices:
            tomorrow_vol = calculate_volatility_level(tomorrow_prices, **thresholds)
            tomorrow_spread = (max(tomorrow_prices) - min(tomorrow_prices)) * 100
            volatility_attributes["tomorrow_spread"] = round(tomorrow_spread, 2)
            volatility_attributes["tomorrow_volatility"] = tomorrow_vol
            volatility_attributes["interval_count_tomorrow"] = len(tomorrow_prices)

    elif volatility_type == "next_24h":
        # Add time window info
        now = dt_util.now()
        volatility_attributes["timestamp"] = now.isoformat()


def get_future_prices(
    coordinator: TibberPricesDataUpdateCoordinator,
    max_intervals: int | None = None,
) -> list[dict] | None:
    """
    Get future price data for multiple upcoming intervals.

    Args:
        coordinator: The data update coordinator
        max_intervals: Maximum number of future intervals to return

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

    now = dt_util.now()

    # Initialize the result list
    future_prices = []

    # Track the maximum intervals to return
    intervals_to_return = MAX_FORECAST_INTERVALS if max_intervals is None else max_intervals

    for day_key in ["today", "tomorrow"]:
        for price_data in price_info.get(day_key, []):
            starts_at = dt_util.parse_datetime(price_data["startsAt"])
            if starts_at is None:
                continue

            starts_at = dt_util.as_local(starts_at)
            interval_end = starts_at + timedelta(minutes=MINUTES_PER_INTERVAL)

            if starts_at > now:
                future_prices.append(
                    {
                        "interval_start": starts_at.isoformat(),
                        "interval_end": interval_end.isoformat(),
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


def get_current_interval_data(
    coordinator: TibberPricesDataUpdateCoordinator,
) -> dict | None:
    """
    Get the current interval data from coordinator.

    Args:
        coordinator: The data update coordinator

    Returns:
        Current interval data dictionary or None

    """
    if not coordinator.data:
        return None

    price_info = coordinator.data.get("priceInfo", {})
    now = dt_util.now()
    return find_price_data_for_interval(price_info, now)
