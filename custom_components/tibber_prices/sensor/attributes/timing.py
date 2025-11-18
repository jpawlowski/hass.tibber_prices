"""Period timing attribute builders for Tibber Prices sensors."""

from __future__ import annotations

from typing import Any

from custom_components.tibber_prices.entity_utils import add_icon_color_attribute
from homeassistant.util import dt as dt_util


def _is_timing_or_volatility_sensor(key: str) -> bool:
    """Check if sensor is a timing or volatility sensor."""
    return key.endswith("_volatility") or (
        key.startswith(("best_price_", "peak_price_"))
        and any(
            suffix in key
            for suffix in [
                "end_time",
                "remaining_minutes",
                "progress",
                "next_start_time",
                "next_in_minutes",
            ]
        )
    )


def add_period_timing_attributes(
    attributes: dict,
    key: str,
    state_value: Any = None,
) -> None:
    """
    Add timestamp and icon_color attributes for best_price/peak_price timing sensors.

    The timestamp indicates when the sensor value was calculated:
    - Quarter-hour sensors (end_time, next_start_time): Timestamp of current 15-min interval
    - Minute-update sensors (remaining_minutes, progress, next_in_minutes): Current minute with :00 seconds

    Args:
        attributes: Dictionary to add attributes to
        key: The sensor entity key (e.g., "best_price_end_time")
        state_value: Current sensor value for icon_color calculation

    """
    # Determine if this is a quarter-hour or minute-update sensor
    is_quarter_hour_sensor = key.endswith(("_end_time", "_next_start_time"))

    now = dt_util.now()

    if is_quarter_hour_sensor:
        # Quarter-hour sensors: Use timestamp of current 15-minute interval
        # Round down to the nearest quarter hour (:00, :15, :30, :45)
        minute = (now.minute // 15) * 15
        timestamp = now.replace(minute=minute, second=0, microsecond=0)
    else:
        # Minute-update sensors: Use current minute with :00 seconds
        # This ensures clean timestamps despite timer fluctuations
        timestamp = now.replace(second=0, microsecond=0)

    attributes["timestamp"] = timestamp.isoformat()

    # Add icon_color for dynamic styling
    add_icon_color_attribute(attributes, key=key, state_value=state_value)
