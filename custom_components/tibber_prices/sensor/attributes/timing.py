"""Period timing attribute builders for Tibber Prices sensors."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from custom_components.tibber_prices.entity_utils import add_icon_color_attribute

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService

# Timer #3 triggers every 30 seconds
TIMER_30_SEC_BOUNDARY = 30


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
    *,
    time: TibberPricesTimeService,
) -> None:
    """
    Add timestamp and icon_color attributes for best_price/peak_price timing sensors.

    The timestamp indicates when the sensor value was calculated:
    - Quarter-hour sensors (end_time, next_start_time): Rounded to 15-min boundary (:00, :15, :30, :45)
    - 30-second update sensors (remaining_minutes, progress, next_in_minutes): Current time with seconds

    Args:
        attributes: Dictionary to add attributes to
        key: The sensor entity key (e.g., "best_price_end_time")
        state_value: Current sensor value for icon_color calculation
        time: TibberPricesTimeService instance (required)

    """
    # Determine if this is a quarter-hour or 30-second update sensor
    is_quarter_hour_sensor = key.endswith(("_end_time", "_next_start_time"))

    now = time.now()

    if is_quarter_hour_sensor:
        # Quarter-hour sensors: Use timestamp of current 15-minute interval
        # Round down to the nearest quarter hour (:00, :15, :30, :45)
        minute = (now.minute // 15) * 15
        timestamp = now.replace(minute=minute, second=0, microsecond=0)
    else:
        # 30-second update sensors: Round to nearest 30-second boundary (:00 or :30)
        # Timer triggers at :00 and :30, so round current time to these boundaries
        second = 0 if now.second < TIMER_30_SEC_BOUNDARY else TIMER_30_SEC_BOUNDARY
        timestamp = now.replace(second=second, microsecond=0)

    attributes["timestamp"] = timestamp

    # Add icon_color for dynamic styling
    add_icon_color_attribute(attributes, key=key, state_value=state_value)
