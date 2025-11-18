"""Volatility attribute builders for Tibber Prices sensors."""

from __future__ import annotations

from datetime import timedelta

from custom_components.tibber_prices.utils.price import calculate_volatility_level
from homeassistant.util import dt as dt_util


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
    # Add timestamp for calendar day volatility sensors (midnight of the day)
    if volatility_type == "today":
        today_data = price_info.get("today", [])
        if today_data:
            volatility_attributes["timestamp"] = today_data[0].get("startsAt")
    elif volatility_type == "tomorrow":
        tomorrow_data = price_info.get("tomorrow", [])
        if tomorrow_data:
            volatility_attributes["timestamp"] = tomorrow_data[0].get("startsAt")
    elif volatility_type == "today_tomorrow":
        # For combined today+tomorrow, use today's midnight
        today_data = price_info.get("today", [])
        if today_data:
            volatility_attributes["timestamp"] = today_data[0].get("startsAt")

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
