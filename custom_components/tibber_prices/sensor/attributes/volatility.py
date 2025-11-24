"""Volatility attribute builders for Tibber Prices sensors."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from custom_components.tibber_prices.coordinator.helpers import get_intervals_for_day_offsets
from custom_components.tibber_prices.utils.price import calculate_volatility_level

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService


def add_volatility_attributes(
    attributes: dict,
    cached_data: dict,
    *,
    time: TibberPricesTimeService,  # noqa: ARG001
) -> None:
    """
    Add attributes for volatility sensors.

    Args:
        attributes: Dictionary to add attributes to
        cached_data: Dictionary containing cached sensor data
        time: TibberPricesTimeService instance (required)

    """
    if cached_data.get("volatility_attributes"):
        attributes.update(cached_data["volatility_attributes"])


def get_prices_for_volatility(
    volatility_type: str,
    coordinator_data: dict,
    *,
    time: TibberPricesTimeService,
) -> list[float]:
    """
    Get price list for volatility calculation based on type.

    Args:
        volatility_type: One of "today", "tomorrow", "next_24h", "today_tomorrow"
        coordinator_data: Coordinator data dict
        time: TibberPricesTimeService instance (required)

    Returns:
        List of prices to analyze

    """
    # Get all intervals (yesterday, today, tomorrow) via helper
    all_intervals = get_intervals_for_day_offsets(coordinator_data, [-1, 0, 1])

    if volatility_type == "today":
        # Filter for today's intervals
        today_date = time.now().date()
        return [
            float(p["total"])
            for p in all_intervals
            if "total" in p and p.get("startsAt") and p["startsAt"].date() == today_date
        ]

    if volatility_type == "tomorrow":
        # Filter for tomorrow's intervals
        tomorrow_date = (time.now() + timedelta(days=1)).date()
        return [
            float(p["total"])
            for p in all_intervals
            if "total" in p and p.get("startsAt") and p["startsAt"].date() == tomorrow_date
        ]

    if volatility_type == "next_24h":
        # Rolling 24h from now
        now = time.now()
        end_time = now + timedelta(hours=24)
        prices = []

        for price_data in all_intervals:
            starts_at = price_data.get("startsAt")  # Already datetime in local timezone
            if starts_at is None:
                continue

            if time.is_in_future(starts_at) and starts_at < end_time and "total" in price_data:
                prices.append(float(price_data["total"]))
        return prices

    if volatility_type == "today_tomorrow":
        # Combined today + tomorrow
        today_date = time.now().date()
        tomorrow_date = (time.now() + timedelta(days=1)).date()
        prices = []
        for price_data in all_intervals:
            starts_at = price_data.get("startsAt")
            if starts_at and starts_at.date() in [today_date, tomorrow_date] and "total" in price_data:
                prices.append(float(price_data["total"]))
        return prices

    return []


def add_volatility_type_attributes(
    volatility_attributes: dict,
    volatility_type: str,
    coordinator_data: dict,
    thresholds: dict,
    *,
    time: TibberPricesTimeService,
) -> None:
    """
    Add type-specific attributes for volatility sensors.

    Args:
        volatility_attributes: Dictionary to add type-specific attributes to
        volatility_type: Type of volatility calculation
        coordinator_data: Coordinator data dict
        thresholds: Volatility thresholds configuration
        time: TibberPricesTimeService instance (required)

    """
    # Get all intervals (yesterday, today, tomorrow) via helper
    all_intervals = get_intervals_for_day_offsets(coordinator_data, [-1, 0, 1])
    now = time.now()
    today_date = now.date()
    tomorrow_date = (now + timedelta(days=1)).date()

    # Add timestamp for calendar day volatility sensors (midnight of the day)
    if volatility_type == "today":
        today_data = [p for p in all_intervals if p.get("startsAt") and p["startsAt"].date() == today_date]
        if today_data:
            volatility_attributes["timestamp"] = today_data[0].get("startsAt")
    elif volatility_type == "tomorrow":
        tomorrow_data = [p for p in all_intervals if p.get("startsAt") and p["startsAt"].date() == tomorrow_date]
        if tomorrow_data:
            volatility_attributes["timestamp"] = tomorrow_data[0].get("startsAt")
    elif volatility_type == "today_tomorrow":
        # For combined today+tomorrow, use today's midnight
        today_data = [p for p in all_intervals if p.get("startsAt") and p["startsAt"].date() == today_date]
        if today_data:
            volatility_attributes["timestamp"] = today_data[0].get("startsAt")

        # Add breakdown for today vs tomorrow
        today_prices = [
            float(p["total"])
            for p in all_intervals
            if "total" in p and p.get("startsAt") and p["startsAt"].date() == today_date
        ]
        tomorrow_prices = [
            float(p["total"])
            for p in all_intervals
            if "total" in p and p.get("startsAt") and p["startsAt"].date() == tomorrow_date
        ]

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
        now = time.now()
        volatility_attributes["timestamp"] = now
