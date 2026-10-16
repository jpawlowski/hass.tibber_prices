"""Interval attribute builders for Tibber Prices sensors."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from custom_components.tibber_prices.const import (
    CHEAP_PRICE_LEVELS,
    EXPENSIVE_PRICE_LEVELS,
    PRICE_LEVEL_MAPPING,
    PRICE_RATING_MAPPING,
    get_display_precision,
    get_display_unit_factor,
)
from custom_components.tibber_prices.coordinator.helpers import get_intervals_for_day_offsets
from custom_components.tibber_prices.entity_utils import add_icon_color_attribute, get_rolling_hour_window
from custom_components.tibber_prices.sensor.definitions import ROLLING_HOUR_SENSOR_WINDOWS
from custom_components.tibber_prices.sensor.helpers import aggregate_average_data
from custom_components.tibber_prices.utils.average import clock_hour_bounds, clock_hour_key
from custom_components.tibber_prices.utils.price import find_level_run_times, find_price_data_for_interval

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator.core import TibberPricesDataUpdateCoordinator
    from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService
    from custom_components.tibber_prices.data import TibberPricesConfigEntry

from .helpers import add_alternate_average_attribute
from .metadata import get_current_interval_data


def _get_interval_data_for_attributes(
    key: str,
    coordinator: TibberPricesDataUpdateCoordinator,
    attributes: dict,
    *,
    time: TibberPricesTimeService,
) -> dict | None:
    """
    Get interval data and set timestamp based on sensor type.

    Refactored to reduce branch complexity in main function.

    Args:
        key: The sensor entity key
        coordinator: The data update coordinator
        attributes: Attributes dict to update with timestamp if needed
        time: TibberPricesTimeService instance

    Returns:
        Interval data if found, None otherwise

    """
    now = time.now()

    # Current/next price sensors - override timestamp with interval's startsAt
    next_sensors = ["next_interval_price", "next_interval_price_level", "next_interval_price_rating"]
    prev_sensors = ["previous_interval_price", "previous_interval_price_level", "previous_interval_price_rating"]
    next_hour = ["next_hour_average_price", "next_hour_price_level", "next_hour_price_rating"]
    curr_interval = ["current_interval_price", "current_interval_price_base"]
    curr_hour = ["current_hour_average_price", "current_hour_price_level", "current_hour_price_rating"]

    if key in next_sensors:
        target_time = time.get_next_interval_start()
        interval_data = find_price_data_for_interval(coordinator.data, target_time, time=time)
        if interval_data:
            attributes["timestamp"] = interval_data["startsAt"]
        return interval_data

    if key in prev_sensors:
        target_time = time.get_interval_offset_time(-1)
        interval_data = find_price_data_for_interval(coordinator.data, target_time, time=time)
        if interval_data:
            attributes["timestamp"] = interval_data["startsAt"]
        return interval_data

    if key in next_hour:
        target_time = now + timedelta(hours=1)
        interval_data = find_price_data_for_interval(coordinator.data, target_time, time=time)
        if interval_data:
            attributes["timestamp"] = interval_data["startsAt"]
        return interval_data

    # Current interval sensors (both variants)
    if key in curr_interval:
        interval_data = get_current_interval_data(coordinator, time=time)
        if interval_data and "startsAt" in interval_data:
            attributes["timestamp"] = interval_data["startsAt"]
        return interval_data

    # Current hour sensors - keep default timestamp
    if key in curr_hour:
        return get_current_interval_data(coordinator, time=time)

    return None


ROLLING_HOUR_OFFSETS = {key: hour_offset for key, (hour_offset, _) in ROLLING_HOUR_SENSOR_WINDOWS.items()}


def _add_rolling_window_attributes(
    attributes: dict,
    all_prices: list[dict],
    hour_offset: int,
    *,
    time: TibberPricesTimeService,
) -> None:
    """
    Add window_start/window_end: the span a rolling hour value is calculated from.

    The rolling hour is centered on the current interval (2 before + current + 2 after),
    not the clock hour, so users need to see which 75 minutes it covers.

    Args:
        attributes: Dictionary to add attributes to
        all_prices: Price intervals in chronological order (yesterday, today, tomorrow)
        hour_offset: 0 (current hour), 1 (next hour)
        time: TibberPricesTimeService instance (required)

    """
    window = get_rolling_hour_window(all_prices, time.now(), hour_offset, time=time)
    if not window:
        return
    first, last = time.get_interval_time(window[0]), time.get_interval_time(window[-1])
    if first is None or last is None:
        return
    attributes["window_start"] = first.isoformat()
    attributes["window_end"] = (last + time.get_interval_duration()).isoformat()


def _add_clock_hour_attributes(
    attributes: dict,
    all_prices: list[dict],
    hour_offset: int,
    *,
    time: TibberPricesTimeService,
    config_entry: TibberPricesConfigEntry,
) -> None:
    """
    Add the average of the clock hour (:00-:59), like the Tibber app shows it.

    The sensor state stays the rolling hour (smoother, no jump at the full hour); these
    attributes give automations the clock hour value without an extra entity.

    Args:
        attributes: Dictionary to add attributes to
        all_prices: Price intervals (yesterday, today, tomorrow)
        hour_offset: 0 (clock hour containing now), 1 (next clock hour)
        time: TibberPricesTimeService instance (required)
        config_entry: Config entry for display unit and precision

    """
    hour_start, hour_end = clock_hour_bounds(time.get_current_interval_start(), hour_offset)
    target = clock_hour_key(hour_start)
    hour_intervals = [
        interval
        for interval in all_prices
        if (starts_at := time.get_interval_time(interval)) is not None and clock_hour_key(starts_at) == target
    ]
    mean, median = aggregate_average_data(hour_intervals, config_entry)
    if mean is None:
        return
    attributes["clock_hour_start"] = hour_start.isoformat()
    attributes["clock_hour_end"] = hour_end.isoformat()
    attributes["clock_hour_price_mean"] = mean
    attributes["clock_hour_price_median"] = median


def _add_energy_tax_attributes(
    attributes: dict,
    interval_data: dict | None,
    *,
    config_entry: TibberPricesConfigEntry,
) -> None:
    """
    Add energy_price and tax attributes from interval data.

    The API provides `energy` (raw spot price) and `tax` (tax component) in base
    currency. These are converted to display units using the same factor as `total`.

    Args:
        attributes: Dictionary to add attributes to
        interval_data: Price interval data dict (may contain energy/tax fields)
        config_entry: Config entry for display unit preference

    """
    if not interval_data:
        return

    factor = get_display_unit_factor(config_entry)
    precision = get_display_precision(config_entry)

    energy = interval_data.get("energy")
    if energy is not None:
        attributes["energy_price"] = round(float(energy) * factor, precision)

    tax = interval_data.get("tax")
    if tax is not None:
        attributes["tax"] = round(float(tax) * factor, precision)


def add_current_interval_price_attributes(
    attributes: dict,
    key: str,
    coordinator: TibberPricesDataUpdateCoordinator,
    native_value: Any,
    cached_data: dict,
    *,
    time: TibberPricesTimeService,
    config_entry: TibberPricesConfigEntry,
) -> None:
    """
    Add attributes for current interval price sensors.

    Args:
        attributes: Dictionary to add attributes to
        key: The sensor entity key
        coordinator: The data update coordinator
        native_value: The current native value of the sensor
        cached_data: Dictionary containing cached sensor data
        time: TibberPricesTimeService instance (required)
        config_entry: Config entry for user preferences

    """
    # Get interval data and handle timestamp overrides
    interval_data = _get_interval_data_for_attributes(key, coordinator, attributes, time=time)

    # Rolling hour sensors: the exact time span their value covers
    hour_offset = ROLLING_HOUR_OFFSETS.get(key)
    if hour_offset is not None:
        all_prices = get_intervals_for_day_offsets(coordinator.data, [-1, 0, 1])
        _add_rolling_window_attributes(attributes, all_prices, hour_offset, time=time)
        if key in ("current_hour_average_price", "next_hour_average_price"):
            # The clock hour (:00-:59) alongside, for those who want both
            _add_clock_hour_attributes(attributes, all_prices, hour_offset, time=time, config_entry=config_entry)

    # Add icon_color for price sensors (based on their price level)
    if key in [
        "current_interval_price",
        "current_interval_price_base",
        "next_interval_price",
        "previous_interval_price",
    ]:
        # For interval-based price sensors, get level from interval_data
        if interval_data and "level" in interval_data:
            level = interval_data["level"]
            add_icon_color_attribute(attributes, key="price_level", state_value=level)

        # Add energy_price and tax attributes from raw API data
        _add_energy_tax_attributes(attributes, interval_data, config_entry=config_entry)
    elif key in ["current_hour_average_price", "next_hour_average_price"]:
        # For hour-based price sensors, get level from cached_data
        level = cached_data.get("rolling_hour_level")
        if level:
            add_icon_color_attribute(attributes, key="price_level", state_value=level)

        # Add alternate average attribute for rolling hour average price sensors
        add_alternate_average_attribute(
            attributes,
            cached_data,
            f"rolling_hour_{ROLLING_HOUR_OFFSETS[key]}",
            config_entry=config_entry,
        )

    # Add price level attributes for all level sensors
    add_level_attributes_for_sensor(
        attributes=attributes,
        key=key,
        interval_data=interval_data,
        coordinator=coordinator,
        native_value=native_value,
        time=time,
    )

    # Add price rating attributes for all rating sensors
    add_rating_attributes_for_sensor(
        attributes=attributes,
        key=key,
        interval_data=interval_data,
        coordinator=coordinator,
        native_value=native_value,
        time=time,
    )


def add_level_attributes_for_sensor(
    attributes: dict,
    key: str,
    interval_data: dict | None,
    coordinator: TibberPricesDataUpdateCoordinator,
    native_value: Any,
    *,
    time: TibberPricesTimeService,
) -> None:
    """
    Add price level attributes based on sensor type.

    Args:
        attributes: Dictionary to add attributes to
        key: The sensor entity key
        interval_data: Interval data for next/previous sensors
        coordinator: The data update coordinator
        native_value: The current native value of the sensor
        time: TibberPricesTimeService instance (required)

    """
    # For interval-based level sensors (next/previous), use interval data
    if key in ["next_interval_price_level", "previous_interval_price_level"]:
        if interval_data and "level" in interval_data:
            add_price_level_attributes(attributes, interval_data["level"])
    # For hour-aggregated level sensors, use native_value
    elif key in ["current_hour_price_level", "next_hour_price_level"]:
        level_value = native_value
        if level_value and isinstance(level_value, str):
            add_price_level_attributes(attributes, level_value.upper())
    # For current price level sensor
    elif key == "current_interval_price_level":
        current_interval_data = get_current_interval_data(coordinator, time=time)
        if current_interval_data and "level" in current_interval_data:
            add_price_level_attributes(attributes, current_interval_data["level"])
            _add_level_run_attributes(attributes, coordinator, current_interval_data, time=time)


def _add_level_run_attributes(
    attributes: dict,
    coordinator: TibberPricesDataUpdateCoordinator,
    current_interval_data: dict,
    *,
    time: TibberPricesTimeService,
) -> None:
    """
    Add how long prices stay cheap/expensive and when the next such stretch starts.

    Complements the best/peak price periods: those can end while prices are still
    cheap, or start after prices already turned cheap.

    Args:
        attributes: Dictionary to add attributes to
        coordinator: The data update coordinator
        current_interval_data: Price data of the current interval
        time: TibberPricesTimeService instance (required)

    """
    current_start = time.get_interval_time(current_interval_data)
    if current_start is None:
        return
    intervals = get_intervals_for_day_offsets(coordinator.data, [-1, 0, 1])
    runs = find_level_run_times(
        intervals, current_start, {"cheap": CHEAP_PRICE_LEVELS, "expensive": EXPENSIVE_PRICE_LEVELS}, time=time
    )
    for prefix, (until, next_start) in runs.items():
        attributes[f"{prefix}_until"] = until.isoformat() if until else None
        attributes[f"next_{prefix}_start"] = next_start.isoformat() if next_start else None


def add_price_level_attributes(attributes: dict, level: str) -> None:
    """
    Add price level specific attributes.

    Args:
        attributes: Dictionary to add attributes to
        level: The price level value (e.g., VERY_CHEAP, NORMAL, etc.)

    """
    if level in PRICE_LEVEL_MAPPING:
        attributes["level_value"] = PRICE_LEVEL_MAPPING[level]
    attributes["level_id"] = level

    # Add icon_color for dynamic styling
    add_icon_color_attribute(attributes, key="price_level", state_value=level)


def add_rating_attributes_for_sensor(
    attributes: dict,
    key: str,
    interval_data: dict | None,
    coordinator: TibberPricesDataUpdateCoordinator,
    native_value: Any,
    *,
    time: TibberPricesTimeService,
) -> None:
    """
    Add price rating attributes based on sensor type.

    Args:
        attributes: Dictionary to add attributes to
        key: The sensor entity key
        interval_data: Interval data for next/previous sensors
        coordinator: The data update coordinator
        native_value: The current native value of the sensor
        time: TibberPricesTimeService instance (required)

    """
    # For interval-based rating sensors (next/previous), use interval data
    if key in ["next_interval_price_rating", "previous_interval_price_rating"]:
        if interval_data and "rating_level" in interval_data:
            add_price_rating_attributes(attributes, interval_data["rating_level"])
    # For hour-aggregated rating sensors, use native_value
    elif key in ["current_hour_price_rating", "next_hour_price_rating"]:
        rating_value = native_value
        if rating_value and isinstance(rating_value, str):
            add_price_rating_attributes(attributes, rating_value.upper())
    # For current price rating sensor
    elif key == "current_interval_price_rating":
        current_interval_data = get_current_interval_data(coordinator, time=time)
        if current_interval_data and "rating_level" in current_interval_data:
            add_price_rating_attributes(attributes, current_interval_data["rating_level"])


def add_price_rating_attributes(attributes: dict, rating: str) -> None:
    """
    Add price rating specific attributes.

    Args:
        attributes: Dictionary to add attributes to
        rating: The price rating value (e.g., LOW, NORMAL, HIGH)

    """
    if rating in PRICE_RATING_MAPPING:
        attributes["rating_value"] = PRICE_RATING_MAPPING[rating]
    attributes["rating_id"] = rating

    # Add icon_color for dynamic styling
    add_icon_color_attribute(attributes, key="price_rating", state_value=rating)
