"""Common attribute utilities for Tibber Prices entities."""

from __future__ import annotations


def build_timestamp_attribute(interval_data: dict | None) -> str | None:
    """
    Build timestamp attribute from interval data.

    Extracts startsAt field consistently across all sensors.

    Args:
        interval_data: Interval data dictionary containing startsAt field

    Returns:
        ISO format timestamp string or None

    """
    if not interval_data:
        return None
    return interval_data.get("startsAt")


def build_period_attributes(period_data: dict) -> dict:
    """
    Build common period attributes (start, end, duration, timestamp).

    Used by binary sensors for period-based entities.

    Args:
        period_data: Period data dictionary

    Returns:
        Dictionary with common period attributes

    """
    return {
        "start": period_data.get("start"),
        "end": period_data.get("end"),
        "duration_minutes": period_data.get("duration_minutes"),
        "timestamp": period_data.get("start"),  # Timestamp = period start
    }
