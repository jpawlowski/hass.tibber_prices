"""
Common helper functions for entities across platforms.

This module provides utility functions used by both sensor and binary_sensor platforms:
- Price value conversion (major/subunit currency units)
- Translation helpers (price levels, ratings)
- Time-based calculations (rolling hour center index)

These functions operate on entity-level concepts (states, translations) but are
platform-agnostic and can be used by both sensor and binary_sensor platforms.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.tibber_prices.const import get_display_unit_factor, get_price_level_translation

if TYPE_CHECKING:
    from datetime import datetime

    from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService
    from custom_components.tibber_prices.data import TibberPricesConfigEntry
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


def get_price_value(
    price: float,
    *,
    in_euro: bool | None = None,
    config_entry: ConfigEntry | TibberPricesConfigEntry | None = None,
) -> float:
    """
    Convert price based on unit.

    NOTE: This function supports two modes for backward compatibility:
    1. Legacy mode: in_euro=True/False (hardcoded conversion)
    2. New mode: config_entry (config-driven conversion)

    New code should use get_display_unit_factor(config_entry) directly.

    Args:
        price: Price value to convert.
        in_euro: (Legacy) If True, return in base currency; if False, in subunit currency.
        config_entry: (New) Config entry to get display unit configuration.

    Returns:
        Price in requested unit (major or subunit currency units).

    """
    # Legacy mode: use in_euro parameter
    if in_euro is not None:
        return price if in_euro else round(price * 100, 2)

    # New mode: use config_entry
    if config_entry is not None:
        factor = get_display_unit_factor(config_entry)
        return round(price * factor, 2)

    # Fallback: default to subunit currency (backward compatibility)
    return round(price * 100, 2)


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


def find_rolling_hour_center_index(
    all_prices: list[dict],
    current_time: datetime,
    hour_offset: int,
    *,
    time: TibberPricesTimeService,
) -> int | None:
    """
    Find the center index for the rolling hour window.

    Args:
        all_prices: List of all price interval dictionaries with 'startsAt' key
        current_time: Current datetime to find the current interval
        hour_offset: Number of hours to offset from current interval (can be negative)
        time: TibberPricesTimeService instance (required)

    Returns:
        Index of the center interval for the rolling hour window, or None if not found

    """
    # Round to nearest interval boundary to handle edge cases where HA schedules
    # us slightly before the boundary (e.g., 14:59:59.999 → 15:00:00)
    target_time = time.round_to_nearest_quarter(current_time)
    current_idx = None

    for idx, price_data in enumerate(all_prices):
        starts_at = time.get_interval_time(price_data)
        if starts_at is None:
            continue

        # Exact match after rounding
        if starts_at == target_time:
            current_idx = idx
            break

    if current_idx is None:
        return None

    return current_idx + (hour_offset * 4)
