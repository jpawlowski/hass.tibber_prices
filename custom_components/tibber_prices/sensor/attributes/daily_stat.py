"""Daily statistics attribute builders for Tibber Prices sensors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.tibber_prices.const import (
    PRICE_RATING_MAPPING,
    get_display_unit_factor,
    get_price_round_decimals,
)
from custom_components.tibber_prices.coordinator.helpers import (
    get_intervals_for_day_offsets,
)
from homeassistant.const import PERCENTAGE

if TYPE_CHECKING:
    from datetime import datetime

    from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService
    from custom_components.tibber_prices.data import TibberPricesConfigEntry

from .helpers import add_alternate_average_attribute


def _add_energy_tax_from_interval(
    attributes: dict,
    interval_data: dict,
    *,
    config_entry: TibberPricesConfigEntry,
) -> None:
    """Add energy_price and tax from a single interval dict."""
    factor = get_display_unit_factor(config_entry)
    decimals = get_price_round_decimals(config_entry)
    energy = interval_data.get("energy")
    if energy is not None:
        attributes["energy_price"] = round(float(energy) * factor, decimals)
    tax = interval_data.get("tax")
    if tax is not None:
        attributes["tax"] = round(float(tax) * factor, decimals)


def _add_energy_tax_averages_from_cache(
    attributes: dict,
    cached_data: dict,
    *,
    config_entry: TibberPricesConfigEntry,
) -> None:
    """Add cached mean/median energy_price and tax values."""
    energy_mean, energy_median, tax_mean, tax_median = cached_data.get(
        "last_energy_tax_averages", (None, None, None, None)
    )
    factor = get_display_unit_factor(config_entry)
    decimals = get_price_round_decimals(config_entry)
    if energy_mean is not None:
        attributes["energy_price_mean"] = round(float(energy_mean) * factor, decimals)
    if energy_median is not None:
        attributes["energy_price_median"] = round(float(energy_median) * factor, decimals)
    if tax_mean is not None:
        attributes["tax_mean"] = round(float(tax_mean) * factor, decimals)
    if tax_median is not None:
        attributes["tax_median"] = round(float(tax_median) * factor, decimals)


def _get_day_midnight_timestamp(key: str, *, time: TibberPricesTimeService) -> datetime:
    """Get midnight timestamp for a given day sensor key (returns datetime object)."""
    # Determine which day based on sensor key
    if key.startswith("yesterday") or key == "average_price_yesterday":
        day = "yesterday"
    elif key.startswith("tomorrow") or key == "average_price_tomorrow":
        day = "tomorrow"
    else:
        day = "today"

    # Use TimeService to get midnight for that day
    local_midnight, _ = time.get_day_boundaries(day)
    return local_midnight


def _get_day_key_from_sensor_key(key: str) -> str:
    """
    Extract day key (yesterday/today/tomorrow) from sensor key.

    Args:
        key: The sensor entity key

    Returns:
        Day key: "yesterday", "today", or "tomorrow"

    """
    if "yesterday" in key:
        return "yesterday"
    if "tomorrow" in key:
        return "tomorrow"
    return "today"


def _add_fallback_timestamp(
    attributes: dict,
    key: str,
    price_info: dict,
) -> None:
    """
    Add fallback timestamp to attributes based on the day in the sensor key.

    Args:
        attributes: Dictionary to add timestamp to
        key: The sensor entity key
        price_info: Price info dictionary from coordinator data (flat structure)

    """
    day_key = _get_day_key_from_sensor_key(key)

    # Use helper to get intervals for this day
    # Build minimal coordinator_data structure for helper
    coordinator_data = {"priceInfo": price_info}
    # Map day key to offset: yesterday=-1, today=0, tomorrow=1
    day_offset = {"yesterday": -1, "today": 0, "tomorrow": 1}[day_key]
    day_intervals = get_intervals_for_day_offsets(coordinator_data, [day_offset])

    # Use first interval's timestamp if available
    if day_intervals:
        attributes["timestamp"] = day_intervals[0].get("startsAt")


def add_statistics_attributes(
    attributes: dict,
    key: str,
    cached_data: dict,
    *,
    time: TibberPricesTimeService,
    config_entry: TibberPricesConfigEntry,
) -> None:
    """
    Add attributes for statistics and rating sensors.

    Args:
        attributes: Dictionary to add attributes to
        key: The sensor entity key
        cached_data: Dictionary containing cached sensor data
        time: TibberPricesTimeService instance (required)
        config_entry: Config entry for user preferences

    """
    # Data timestamp sensor - shows API fetch time
    if key == "data_timestamp":
        latest_timestamp = cached_data.get("data_timestamp")
        if latest_timestamp:
            attributes["timestamp"] = latest_timestamp
        return

    # Current interval price rating - add rating attributes
    if key == "current_interval_price_rating":
        if cached_data.get("last_rating_difference") is not None:
            attributes["diff_" + PERCENTAGE] = cached_data["last_rating_difference"]
        if cached_data.get("last_rating_level") is not None:
            attributes["level_id"] = cached_data["last_rating_level"]
            attributes["level_value"] = PRICE_RATING_MAPPING.get(
                cached_data["last_rating_level"], cached_data["last_rating_level"]
            )
        return

    # Extreme value sensors - show when the extreme occurs + energy/tax breakdown
    extreme_sensors = {
        "lowest_price_today",
        "highest_price_today",
        "lowest_price_tomorrow",
        "highest_price_tomorrow",
    }
    if key in extreme_sensors:
        extreme_interval = cached_data.get("last_extreme_interval")
        if extreme_interval:
            extreme_starts_at = extreme_interval.get("startsAt")
            if extreme_starts_at:
                attributes["timestamp"] = extreme_starts_at
            # Add energy_price and tax from the extreme interval
            _add_energy_tax_from_interval(attributes, extreme_interval, config_entry=config_entry)
        return

    # Daily average sensors - show midnight to indicate whole day + add alternate value
    daily_avg_sensors = {"average_price_today", "average_price_tomorrow"}
    if key in daily_avg_sensors:
        attributes["timestamp"] = _get_day_midnight_timestamp(key, time=time)
        # Add alternate average attribute
        add_alternate_average_attribute(
            attributes,
            cached_data,
            key,  # base_key = key itself ("average_price_today" or "average_price_tomorrow")
            config_entry=config_entry,
        )
        # Add energy/tax averages from cached calculator data
        _add_energy_tax_averages_from_cache(attributes, cached_data, config_entry=config_entry)
        return

    # Daily aggregated level/rating sensors - show midnight to indicate whole day
    daily_aggregated_sensors = {
        "yesterday_price_level",
        "today_price_level",
        "tomorrow_price_level",
        "yesterday_price_rating",
        "today_price_rating",
        "tomorrow_price_rating",
    }
    if key in daily_aggregated_sensors:
        attributes["timestamp"] = _get_day_midnight_timestamp(key, time=time)
        return

    # All other statistics sensors - keep default timestamp (when calculation was made)
