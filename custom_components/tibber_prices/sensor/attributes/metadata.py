"""Metadata attribute builders for Tibber Prices sensors."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from custom_components.tibber_prices.utils.price import find_price_data_for_interval

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator.core import (
        TibberPricesDataUpdateCoordinator,
    )
    from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService


def get_current_interval_data(
    coordinator: TibberPricesDataUpdateCoordinator,
    *,
    time: TibberPricesTimeService,
) -> dict | None:
    """
    Get current interval's price data.

    Args:
        coordinator: The data update coordinator
        time: TibberPricesTimeService instance (required)

    Returns:
        Current interval data or None if not found

    """
    if not coordinator.data:
        return None

    now = time.now()

    return find_price_data_for_interval(coordinator.data, now, time=time)


def get_day_pattern_attributes(
    coordinator: TibberPricesDataUpdateCoordinator,
    day: str,
) -> dict[str, Any] | None:
    """
    Build attributes for a day_pattern_* sensor.

    Returns the full DayPatternDict fields (except "pattern" which is the sensor
    state) plus ISO-formatted datetime fields.

    Args:
        coordinator: The data update coordinator.
        day:         One of "yesterday", "today", "tomorrow".
        time:        TibberPricesTimeService instance.

    Returns:
        Attribute dict or None if pattern data is unavailable.

    """
    if not coordinator.data:
        return None

    day_patterns = coordinator.data.get("dayPatterns")
    if not day_patterns:
        return None

    day_data: dict[str, Any] | None = day_patterns.get(day)
    if not day_data:
        return None

    def _iso(val: object) -> str | None:
        """Convert datetime to ISO string, pass strings through, return None otherwise."""
        if val is None:
            return None
        if isinstance(val, str):
            return val
        if hasattr(val, "isoformat"):
            return val.isoformat()  # type: ignore[return-value]
        return None

    attrs: dict[str, Any] = {
        "confidence": day_data.get("confidence"),
        "day_cv_percent": day_data.get("day_cv_percent"),
    }

    # Optional primary extreme time
    extreme_time = _iso(day_data.get("extreme_time"))
    if extreme_time is not None:
        attrs["extreme_time"] = extreme_time

    # VALLEY-specific knee points
    valley_start = _iso(day_data.get("valley_start"))
    valley_end = _iso(day_data.get("valley_end"))
    if valley_start is not None:
        attrs["valley_start"] = valley_start
    if valley_end is not None:
        attrs["valley_end"] = valley_end

    # PEAK-specific knee points
    peak_start = _iso(day_data.get("peak_start"))
    peak_end = _iso(day_data.get("peak_end"))
    if peak_start is not None:
        attrs["peak_start"] = peak_start
    if peak_end is not None:
        attrs["peak_end"] = peak_end

    # Segments (list of monotone regions)
    segments = day_data.get("segments")
    if segments:
        attrs["segments"] = segments

    return attrs or None
