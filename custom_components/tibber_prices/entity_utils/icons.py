"""Icon utilities for Tibber Prices entities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService

from custom_components.tibber_prices.const import (
    BINARY_SENSOR_ICON_MAPPING,
    PRICE_LEVEL_CASH_ICON_MAPPING,
    PRICE_LEVEL_ICON_MAPPING,
    PRICE_RATING_ICON_MAPPING,
    VOLATILITY_ICON_MAPPING,
)
from custom_components.tibber_prices.coordinator.helpers import get_intervals_for_day_offsets
from custom_components.tibber_prices.entity_utils.helpers import find_rolling_hour_center_index
from custom_components.tibber_prices.sensor.helpers import aggregate_level_data
from custom_components.tibber_prices.utils.price import find_price_data_for_interval

# Icon update logic uses timedelta directly (cosmetic, independent - allowed per AGENTS.md)
_INTERVAL_MINUTES = 15  # Tibber's 15-minute intervals


@dataclass
class TibberPricesIconContext:
    """Context data for dynamic icon selection."""

    is_on: bool | None = None
    coordinator_data: dict | None = None
    has_future_periods_callback: Callable[[], bool] | None = None
    period_is_active_callback: Callable[[], bool] | None = None
    time: TibberPricesTimeService | None = None


if TYPE_CHECKING:
    from collections.abc import Callable

# Timing sensor icon thresholds (in minutes)
TIMING_URGENT_THRESHOLD = 15  # ≤15 min: Alert icon
TIMING_SOON_THRESHOLD = 60  # ≤1 hour: Timer icon
TIMING_MEDIUM_THRESHOLD = 180  # ≤3 hours: Sand timer icon
# >3 hours: Outline timer icon

# Progress sensor constants
PROGRESS_MAX = 100  # Maximum progress value (100%)


def get_dynamic_icon(
    key: str,
    value: Any,
    *,
    context: TibberPricesIconContext | None = None,
) -> str | None:
    """
    Get dynamic icon based on sensor state.

    Unified function for both sensor and binary_sensor platforms.

    Args:
        key: Entity description key
        value: Native value of the sensor
        context: Optional context with is_on state, coordinator_data, and callbacks

    Returns:
        Icon string or None if no dynamic icon applies

    """
    ctx = context or TibberPricesIconContext()

    # Try various icon sources in order
    return (
        get_trend_icon(key, value)
        or get_timing_sensor_icon(key, value, period_is_active_callback=ctx.period_is_active_callback)
        or get_price_sensor_icon(key, ctx.coordinator_data, time=ctx.time)
        or get_level_sensor_icon(key, value)
        or get_rating_sensor_icon(key, value)
        or get_volatility_sensor_icon(key, value)
        or get_binary_sensor_icon(key, is_on=ctx.is_on, has_future_periods_callback=ctx.has_future_periods_callback)
    )


def get_trend_icon(key: str, value: Any) -> str | None:
    """Get icon for trend sensors using 5-level trend scale."""
    # Handle next_price_trend_change TIMESTAMP sensor differently
    # (icon based on attributes, not value which is a timestamp)
    if key == "next_price_trend_change":
        return None  # Will be handled by sensor's icon property using attributes

    if not key.startswith("price_trend_") and key != "current_price_trend":
        return None

    if not isinstance(value, str):
        return None

    # 5-level trend icons: strongly uses double arrows, normal uses single
    trend_icons = {
        "strongly_rising": "mdi:chevron-double-up",  # Strong upward movement
        "rising": "mdi:trending-up",  # Normal upward trend
        "stable": "mdi:trending-neutral",  # No significant change
        "falling": "mdi:trending-down",  # Normal downward trend
        "strongly_falling": "mdi:chevron-double-down",  # Strong downward movement
    }
    return trend_icons.get(value)


def get_timing_sensor_icon(
    key: str,
    value: Any,
    *,
    period_is_active_callback: Callable[[], bool] | None = None,
) -> str | None:
    """
    Get dynamic icon for best_price/peak_price timing sensors.

    Progress sensors: Different icons based on period state
      - No period: mdi:help-circle-outline (Unknown/gray)
      - Waiting (0%, period not active): mdi:timer-pause-outline (paused/waiting)
      - Active (0%, period running): mdi:circle-outline (just started)
      - Progress 1-99%: mdi:circle-slice-1 to mdi:circle-slice-7
      - Complete (100%): mdi:circle-slice-8

    Remaining/Next-in sensors: Different timer icons based on time remaining
    Timestamp sensors: Static icons (handled by entity description)

    Args:
        key: Entity description key
        value: Sensor value (percentage for progress, minutes for countdown)
        period_is_active_callback: Callback to check if related period is currently active

    Returns:
        Icon string or None if not a timing sensor with dynamic icon

    """
    # Unknown state: Show help icon for all timing sensors
    if value is None and key.startswith(("best_price_", "peak_price_")):
        return "mdi:help-circle-outline"

    # Progress sensors: Circle-slice icons for visual progress indication
    # mdi:circle-slice-N where N represents filled portions (1=12.5%, 8=100%)
    if key.endswith("_progress") and isinstance(value, (int, float)):
        # Special handling for 0%: Distinguish between waiting and active
        if value <= 0:
            # Check if period is currently active via callback
            is_active = (
                period_is_active_callback()
                if (period_is_active_callback and callable(period_is_active_callback))
                else True
            )
            # Period just started (0% but running) vs waiting for next
            return "mdi:circle-outline" if is_active else "mdi:timer-pause-outline"

        # Calculate slice based on progress percentage
        slice_num = 8 if value >= PROGRESS_MAX else min(7, max(1, int((value / PROGRESS_MAX) * 8)))
        return f"mdi:circle-slice-{slice_num}"

    # Remaining/Next-in minutes sensors: Timer icons based on urgency thresholds
    if key.endswith(("_remaining_minutes", "_next_in_minutes")) and isinstance(value, (int, float)):
        # Map time remaining to appropriate timer icon
        urgency_map = [
            (0, "mdi:timer-off-outline"),  # Exactly 0 minutes
            (TIMING_URGENT_THRESHOLD, "mdi:timer-alert"),  # < 15 min: urgent
            (TIMING_SOON_THRESHOLD, "mdi:timer"),  # < 60 min: soon
            (TIMING_MEDIUM_THRESHOLD, "mdi:timer-sand"),  # < 180 min: medium
        ]
        for threshold, icon in urgency_map:
            if value <= threshold:
                return icon
        return "mdi:timer-outline"  # >= 180 min: far away

    # Timestamp sensors use static icons from entity description
    return None


def get_price_sensor_icon(
    key: str,
    coordinator_data: dict | None,
    *,
    time: TibberPricesTimeService | None,
) -> str | None:
    """
    Get icon for current price sensors (dynamic based on price level).

    Dynamic icons for: current_interval_price, next_interval_price,
                      current_hour_average_price, next_hour_average_price
    Other price sensors (previous interval) use static icons from entity description.

    Args:
        key: Entity description key
        coordinator_data: Coordinator data for price level lookups
        time: TibberPricesTimeService instance (required for determining current interval)

    Returns:
        Icon string or None if not a current price sensor

    """
    # Early exit if coordinator_data or time not available
    if not coordinator_data or time is None:
        return None

    # Only current price sensors get dynamic icons
    if key in ("current_interval_price", "current_interval_price_base"):
        level = get_price_level_for_icon(coordinator_data, interval_offset=0, time=time)
        if level:
            return PRICE_LEVEL_CASH_ICON_MAPPING.get(level.upper())
    elif key == "next_interval_price":
        # For next interval, use the next interval price level to determine icon
        level = get_price_level_for_icon(coordinator_data, interval_offset=1, time=time)
        if level:
            return PRICE_LEVEL_CASH_ICON_MAPPING.get(level.upper())
    elif key == "current_hour_average_price":
        # For current hour average, use the current hour price level to determine icon
        level = get_rolling_hour_price_level_for_icon(coordinator_data, hour_offset=0, time=time)
        if level:
            return PRICE_LEVEL_CASH_ICON_MAPPING.get(level.upper())
    elif key == "next_hour_average_price":
        # For next hour average, use the next hour price level to determine icon
        level = get_rolling_hour_price_level_for_icon(coordinator_data, hour_offset=1, time=time)
        if level:
            return PRICE_LEVEL_CASH_ICON_MAPPING.get(level.upper())

    # For all other price sensors, let entity description handle the icon
    return None


def get_level_sensor_icon(key: str, value: Any) -> str | None:
    """Get icon for price level sensors."""
    if key not in [
        "current_interval_price_level",
        "next_interval_price_level",
        "previous_interval_price_level",
        "current_hour_price_level",
        "next_hour_price_level",
        "yesterday_price_level",
        "today_price_level",
        "tomorrow_price_level",
    ] or not isinstance(value, str):
        return None

    return PRICE_LEVEL_ICON_MAPPING.get(value.upper())


def get_rating_sensor_icon(key: str, value: Any) -> str | None:
    """Get icon for price rating sensors."""
    if key not in [
        "current_interval_price_rating",
        "next_interval_price_rating",
        "previous_interval_price_rating",
        "current_hour_price_rating",
        "next_hour_price_rating",
        "yesterday_price_rating",
        "today_price_rating",
        "tomorrow_price_rating",
    ] or not isinstance(value, str):
        return None

    return PRICE_RATING_ICON_MAPPING.get(value.upper())


def get_volatility_sensor_icon(key: str, value: Any) -> str | None:
    """Get icon for volatility sensors."""
    if not key.endswith("_volatility") or not isinstance(value, str):
        return None

    return VOLATILITY_ICON_MAPPING.get(value.upper())


def get_binary_sensor_icon(
    key: str,
    *,
    is_on: bool | None,
    has_future_periods_callback: Callable[[], bool] | None = None,
) -> str | None:
    """
    Get icon for binary sensors with dynamic state-based icons.

    Args:
        key: Entity description key
        is_on: Binary sensor state
        has_future_periods_callback: Callback to check if future periods exist

    Returns:
        Icon string or None if not a binary sensor with dynamic icons

    """
    if key not in BINARY_SENSOR_ICON_MAPPING or is_on is None:
        return None

    if is_on:
        # Sensor is ON - use "on" icon
        return BINARY_SENSOR_ICON_MAPPING[key].get("on")

    # Sensor is OFF - check if future periods exist
    has_future_periods = has_future_periods_callback() if has_future_periods_callback else False

    if has_future_periods:
        return BINARY_SENSOR_ICON_MAPPING[key].get("off")

    return BINARY_SENSOR_ICON_MAPPING[key].get("off_no_future")


def get_price_level_for_icon(
    coordinator_data: dict,
    *,
    interval_offset: int | None = None,
    time: TibberPricesTimeService,
) -> str | None:
    """
    Get the price level for icon determination.

    Supports interval-based lookups (current/next/previous interval).

    Args:
        coordinator_data: Coordinator data
        interval_offset: Interval offset (0=current, 1=next, -1=previous)
        time: TibberPricesTimeService instance (required)

    Returns:
        Price level string or None if not found

    """
    if not coordinator_data or interval_offset is None:
        return None

    now = time.now()

    # Interval-based lookup
    target_time = now + timedelta(minutes=_INTERVAL_MINUTES * interval_offset)
    interval_data = find_price_data_for_interval(coordinator_data, target_time, time=time)

    if not interval_data or "level" not in interval_data:
        return None

    return interval_data["level"]


def get_rolling_hour_price_level_for_icon(
    coordinator_data: dict,
    *,
    hour_offset: int = 0,
    time: TibberPricesTimeService,
) -> str | None:
    """
    Get the aggregated price level for rolling hour icon determination.

    Uses the same logic as the sensor platform: 5-interval rolling window
    (2 before + center + 2 after) to determine the price level.

    This ensures icon calculation matches the actual sensor value calculation.

    Args:
        coordinator_data: Coordinator data
        hour_offset: Hour offset (0=current hour, 1=next hour)
        time: TibberPricesTimeService instance (required)

    Returns:
        Aggregated price level string or None if not found

    """
    if not coordinator_data:
        return None

    # Get all intervals (yesterday, today, tomorrow) via helper
    all_prices = get_intervals_for_day_offsets(coordinator_data, [-1, 0, 1])

    if not all_prices:
        return None

    # Find center index using the same helper function as the sensor platform
    now = time.now()
    center_idx = find_rolling_hour_center_index(all_prices, now, hour_offset, time=time)

    if center_idx is None:
        return None

    # Collect data from 5-interval window (-2, -1, 0, +1, +2) - same as sensor platform
    window_data = []
    for offset in range(-2, 3):
        idx = center_idx + offset
        if 0 <= idx < len(all_prices):
            window_data.append(all_prices[idx])

    if not window_data:
        return None

    # Use the same aggregation function as the sensor platform
    return aggregate_level_data(window_data)
