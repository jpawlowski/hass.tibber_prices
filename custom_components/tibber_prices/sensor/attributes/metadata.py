"""Metadata attribute builders for Tibber Prices sensors."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from custom_components.tibber_prices.utils.price import find_price_data_for_interval

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator.core import TibberPricesDataUpdateCoordinator
    from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService


def _find_current_segment_in_data(
    coordinator_data: dict,
    *,
    time: TibberPricesTimeService,
) -> tuple[int, list[dict[str, Any]]] | tuple[None, None]:
    """
    Find the currently active segment in today's day pattern data.

    Shared helper for all phase-related attribute/value lookups.

    Args:
        coordinator_data: Coordinator's data dict (must not be None).
        time: TibberPricesTimeService instance.

    Returns:
        Tuple of (current_index, segments) or (None, None) if unavailable.

    """
    day_patterns = coordinator_data.get("dayPatterns")
    if not day_patterns:
        return None, None

    today_data: dict[str, Any] | None = day_patterns.get("today")
    if not today_data:
        return None, None

    segments: list[dict[str, Any]] | None = today_data.get("segments")
    if not segments:
        return None, None

    from homeassistant.util.dt import parse_datetime  # noqa: PLC0415

    now = time.now()
    current_index: int | None = None
    for i, segment in enumerate(segments):
        seg_start_str: str | None = segment.get("start")
        if not seg_start_str:
            continue
        seg_start = parse_datetime(seg_start_str)
        if seg_start is not None and now >= seg_start:
            current_index = i

    if current_index is None:
        return None, None

    return current_index, segments


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


def get_current_price_phase_attributes(
    coordinator: TibberPricesDataUpdateCoordinator,
    *,
    time: TibberPricesTimeService,
) -> dict[str, Any] | None:
    """
    Build attributes for the current_price_phase sensor.

    Returns details of the monotone segment that covers the current time,
    plus contextual position info and the full list of all today's segments.

    Args:
        coordinator: The data update coordinator.
        time:        TibberPricesTimeService instance.

    Returns:
        Attribute dict or None if data is unavailable.

    """
    if not coordinator.data:
        return None

    current_index, segments = _find_current_segment_in_data(coordinator.data, time=time)
    if current_index is None or segments is None:
        return None

    seg = segments[current_index]
    attrs: dict[str, Any] = {
        "start": seg.get("start"),
        "end": seg.get("end"),
        "price_min": seg.get("price_min"),
        "price_max": seg.get("price_max"),
        "price_mean": seg.get("price_mean"),
        "segment_index": current_index,
        "segment_count": len(segments),
        "all_segments": segments,
    }
    return attrs


def get_next_price_phase_attributes(
    coordinator: TibberPricesDataUpdateCoordinator,
    *,
    time: TibberPricesTimeService,
) -> dict[str, Any] | None:
    """
    Build attributes for the next_price_phase sensor.

    Returns details of the segment that follows the currently active one.
    If today's current segment is the last, falls back to tomorrow's first segment.

    Args:
        coordinator: The data update coordinator.
        time:        TibberPricesTimeService instance.

    Returns:
        Attribute dict or None if no next segment exists.

    """
    if not coordinator.data:
        return None

    current_index, segments = _find_current_segment_in_data(coordinator.data, time=time)
    if current_index is None or segments is None:
        return None

    # Next segment in today
    if current_index + 1 < len(segments):
        next_seg = segments[current_index + 1]
        attrs: dict[str, Any] = {
            "start": next_seg.get("start"),
            "end": next_seg.get("end"),
            "price_min": next_seg.get("price_min"),
            "price_max": next_seg.get("price_max"),
            "price_mean": next_seg.get("price_mean"),
            "segment_index": current_index + 1,
            "segment_count": len(segments),
        }
        return attrs

    # Fall back to tomorrow's first segment
    day_patterns = coordinator.data.get("dayPatterns")
    if not day_patterns:
        return None
    tomorrow_data = day_patterns.get("tomorrow")
    if not tomorrow_data:
        return None
    tomorrow_segments: list[dict[str, Any]] = tomorrow_data.get("segments", [])
    if not tomorrow_segments:
        return None
    next_seg = tomorrow_segments[0]
    return {
        "start": next_seg.get("start"),
        "end": next_seg.get("end"),
        "price_min": next_seg.get("price_min"),
        "price_max": next_seg.get("price_max"),
        "price_mean": next_seg.get("price_mean"),
        "segment_index": 0,
        "segment_count": len(tomorrow_segments),
        "is_tomorrow": True,
    }
