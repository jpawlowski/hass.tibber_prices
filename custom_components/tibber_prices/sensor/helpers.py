"""Helper functions for sensor platform."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from custom_components.tibber_prices.const import get_price_level_translation
from custom_components.tibber_prices.price_utils import (
    aggregate_price_levels,
    aggregate_price_rating,
)
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.core import HomeAssistant


def aggregate_price_data(window_data: list[dict]) -> float | None:
    """
    Calculate average price from window data.

    Args:
        window_data: List of price interval dictionaries with 'total' key

    Returns:
        Average price in minor currency units (cents/øre), or None if no prices

    """
    prices = [float(i["total"]) for i in window_data if "total" in i]
    if not prices:
        return None
    # Return in minor currency units (cents/øre)
    return round((sum(prices) / len(prices)) * 100, 2)


def aggregate_level_data(window_data: list[dict]) -> str | None:
    """
    Aggregate price levels from window data.

    Args:
        window_data: List of price interval dictionaries with 'level' key

    Returns:
        Aggregated price level (lowercase), or None if no levels

    """
    levels = [i["level"] for i in window_data if "level" in i]
    if not levels:
        return None
    aggregated = aggregate_price_levels(levels)
    return aggregated.lower() if aggregated else None


def aggregate_rating_data(
    window_data: list[dict],
    threshold_low: float,
    threshold_high: float,
) -> str | None:
    """
    Aggregate price ratings from window data.

    Args:
        window_data: List of price interval dictionaries with 'difference' and 'rating_level'
        threshold_low: Low threshold for rating calculation
        threshold_high: High threshold for rating calculation

    Returns:
        Aggregated price rating (lowercase), or None if no ratings

    """
    differences = [i["difference"] for i in window_data if "difference" in i and "rating_level" in i]
    if not differences:
        return None

    aggregated, _ = aggregate_price_rating(differences, threshold_low, threshold_high)
    return aggregated.lower() if aggregated else None


def find_rolling_hour_center_index(
    all_prices: list[dict],
    current_time: datetime,
    hour_offset: int,
) -> int | None:
    """
    Find the center index for the rolling hour window.

    Args:
        all_prices: List of all price interval dictionaries with 'startsAt' key
        current_time: Current datetime to find the current interval
        hour_offset: Number of hours to offset from current interval (can be negative)

    Returns:
        Index of the center interval for the rolling hour window, or None if not found

    """
    current_idx = None

    for idx, price_data in enumerate(all_prices):
        starts_at = dt_util.parse_datetime(price_data["startsAt"])
        if starts_at is None:
            continue
        starts_at = dt_util.as_local(starts_at)
        interval_end = starts_at + timedelta(minutes=15)

        if starts_at <= current_time < interval_end:
            current_idx = idx
            break

    if current_idx is None:
        return None

    return current_idx + (hour_offset * 4)


def translate_level(hass: HomeAssistant, level: str) -> str:
    """
    Translate price level to the user's language.

    Args:
        hass: HomeAssistant instance for language configuration
        level: Price level to translate (e.g., VERY_CHEAP, NORMAL, etc.)

    Returns:
        Translated level string, or original level if translation not found

    """
    if not hass:
        return level

    language = hass.config.language or "en"
    translated = get_price_level_translation(level, language)
    if translated:
        return translated

    if language != "en":
        fallback = get_price_level_translation(level, "en")
        if fallback:
            return fallback

    return level


def translate_rating_level(rating: str) -> str:
    """
    Translate price rating level to the user's language.

    Args:
        rating: Price rating to translate (e.g., LOW, NORMAL, HIGH)

    Returns:
        Translated rating string, or original rating if translation not found

    Note:
        Currently returns the rating as-is. Translation mapping for ratings
        can be added here when needed, similar to translate_level().

    """
    # For now, ratings are returned as-is
    # Add translation mapping here when needed
    return rating


def get_price_value(price: float, *, in_euro: bool) -> float:
    """
    Convert price based on unit.

    Args:
        price: Price value to convert
        in_euro: If True, return price in euros; if False, return in cents/øre

    Returns:
        Price in requested unit (euros or minor currency units)

    """
    return price if in_euro else round((price * 100), 2)
