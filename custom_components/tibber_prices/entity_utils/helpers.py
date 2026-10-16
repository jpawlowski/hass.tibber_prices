"""
Common helper functions for entities across platforms.

This module provides utility functions used by both sensor and binary_sensor platforms:
- Price value conversion (major/subunit currency units)

- Time-based calculations (rolling hour center index)

These functions operate on entity-level concepts (states, translations) but are
platform-agnostic and can be used by both sensor and binary_sensor platforms.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.tibber_prices.const import get_display_precision, get_display_unit_factor
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from datetime import datetime

    from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService
    from custom_components.tibber_prices.data import TibberPricesConfigEntry
    from homeassistant.config_entries import ConfigEntry


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
        precision = get_display_precision(config_entry)
        return round(price * factor, precision)

    # Fallback: default to subunit currency (backward compatibility)
    return round(price * 100, 2)


def _find_rolling_hour_center_index(
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
    # Compare in UTC: local times ignore the DST fold, so the repeated 02:15 at the
    # fall-back would match the first one
    target_time = dt_util.as_utc(time.round_to_nearest_quarter(current_time))
    current_idx = None

    for idx, price_data in enumerate(all_prices):
        starts_at = time.get_interval_time(price_data)
        if starts_at is None:
            continue

        # Exact match after rounding
        if dt_util.as_utc(starts_at) == target_time:
            current_idx = idx
            break

    if current_idx is None:
        return None

    return current_idx + (hour_offset * 4)


def get_rolling_hour_window(
    all_prices: list[dict],
    current_time: datetime,
    hour_offset: int,
    *,
    time: TibberPricesTimeService,
) -> list[dict]:
    """
    Return the intervals of a rolling hour window.

    The window is centered on the current interval (shifted by `hour_offset` hours):
    2 intervals before + center + 2 after = 5 intervals (75 minutes). It is the single
    source for both the rolling hour values and their window_start/window_end attributes.

    Args:
        all_prices: Price intervals in chronological order (yesterday, today, tomorrow)
        current_time: Current datetime
        hour_offset: 0 (current hour), 1 (next hour), etc.
        time: TibberPricesTimeService instance (required)

    Returns:
        Intervals of the window (fewer than 5 at the edges of the data), empty if the
        current interval or the shifted center is not in the data (e.g. the next hour
        before tomorrow's prices are published).

    """
    center_idx = _find_rolling_hour_center_index(all_prices, current_time, hour_offset, time=time)
    if center_idx is None or not 0 <= center_idx < len(all_prices):
        return []
    return [all_prices[idx] for idx in range(center_idx - 2, center_idx + 3) if 0 <= idx < len(all_prices)]
