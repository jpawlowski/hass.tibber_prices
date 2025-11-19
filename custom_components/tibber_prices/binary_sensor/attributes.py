"""Attribute builders for binary sensors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.tibber_prices.entity_utils import add_icon_color_attribute

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator.time_service import TimeService

if TYPE_CHECKING:
    from datetime import datetime

    from custom_components.tibber_prices.data import TibberPricesConfigEntry
    from homeassistant.core import HomeAssistant


def get_tomorrow_data_available_attributes(
    coordinator_data: dict,
    *,
    time: TimeService,
) -> dict | None:
    """
    Build attributes for tomorrow_data_available sensor.

    Args:
        coordinator_data: Coordinator data dict
        time: TimeService instance

    Returns:
        Attributes dict with intervals_available and data_status

    """
    if not coordinator_data:
        return None

    price_info = coordinator_data.get("priceInfo", {})
    tomorrow_prices = price_info.get("tomorrow", [])
    interval_count = len(tomorrow_prices)

    # Get expected intervals for tomorrow (handles DST)
    tomorrow_date = time.get_local_date(offset_days=1)
    expected_intervals = time.get_expected_intervals_for_day(tomorrow_date)

    if interval_count == 0:
        status = "none"
    elif interval_count == expected_intervals:
        status = "full"
    else:
        status = "partial"

    return {
        "intervals_available": interval_count,
        "data_status": status,
    }


def get_price_intervals_attributes(
    coordinator_data: dict,
    *,
    time: TimeService,
    reverse_sort: bool,
) -> dict | None:
    """
    Build attributes for period-based sensors (best/peak price).

    All data is already calculated in the coordinator - we just need to:
    1. Get period summaries from coordinator (already filtered and fully calculated)
    2. Add the current timestamp
    3. Find current or next period based on time

    Args:
        coordinator_data: Coordinator data dict
        time: TimeService instance (required)
        reverse_sort: True for peak_price (highest first), False for best_price (lowest first)

    Returns:
        Attributes dict with current/next period and all periods list

    """
    if not coordinator_data:
        return build_no_periods_result(time=time)

    # Get precomputed period summaries from coordinator
    periods_data = coordinator_data.get("periods", {})
    period_type = "peak_price" if reverse_sort else "best_price"
    period_data = periods_data.get(period_type)

    if not period_data:
        return build_no_periods_result(time=time)

    period_summaries = period_data.get("periods", [])
    if not period_summaries:
        return build_no_periods_result(time=time)

    # Find current or next period based on current time
    current_period = None

    # First pass: find currently active period
    for period in period_summaries:
        start = period.get("start")
        end = period.get("end")
        if start and end and time.is_current_interval(start, end):
            current_period = period
            break

    # Second pass: find next future period if none is active
    if not current_period:
        for period in period_summaries:
            start = period.get("start")
            if start and time.is_in_future(start):
                current_period = period
                break

    # Build final attributes
    return build_final_attributes_simple(current_period, period_summaries, time=time)


def build_no_periods_result(*, time: TimeService) -> dict:
    """
    Build result when no periods exist (not filtered, just none available).

    Returns:
        A dict with empty periods and timestamp.

    """
    # Calculate timestamp: current time rounded down to last quarter hour
    now = time.now()
    current_minute = (now.minute // 15) * 15
    timestamp = now.replace(minute=current_minute, second=0, microsecond=0)

    return {
        "timestamp": timestamp,
        "start": None,
        "end": None,
        "periods": [],
    }


def add_time_attributes(attributes: dict, current_period: dict, timestamp: datetime) -> None:
    """Add time-related attributes (priority 1)."""
    attributes["timestamp"] = timestamp
    if "start" in current_period:
        attributes["start"] = current_period["start"]
    if "end" in current_period:
        attributes["end"] = current_period["end"]
    if "duration_minutes" in current_period:
        attributes["duration_minutes"] = current_period["duration_minutes"]


def add_decision_attributes(attributes: dict, current_period: dict) -> None:
    """Add core decision attributes (priority 2)."""
    if "level" in current_period:
        attributes["level"] = current_period["level"]
    if "rating_level" in current_period:
        attributes["rating_level"] = current_period["rating_level"]
    if "rating_difference_%" in current_period:
        attributes["rating_difference_%"] = current_period["rating_difference_%"]


def add_price_attributes(attributes: dict, current_period: dict) -> None:
    """Add price statistics attributes (priority 3)."""
    if "price_avg" in current_period:
        attributes["price_avg"] = current_period["price_avg"]
    if "price_min" in current_period:
        attributes["price_min"] = current_period["price_min"]
    if "price_max" in current_period:
        attributes["price_max"] = current_period["price_max"]
    if "price_spread" in current_period:
        attributes["price_spread"] = current_period["price_spread"]
    if "volatility" in current_period:
        attributes["volatility"] = current_period["volatility"]


def add_comparison_attributes(attributes: dict, current_period: dict) -> None:
    """Add price comparison attributes (priority 4)."""
    if "period_price_diff_from_daily_min" in current_period:
        attributes["period_price_diff_from_daily_min"] = current_period["period_price_diff_from_daily_min"]
    if "period_price_diff_from_daily_min_%" in current_period:
        attributes["period_price_diff_from_daily_min_%"] = current_period["period_price_diff_from_daily_min_%"]


def add_detail_attributes(attributes: dict, current_period: dict) -> None:
    """Add detail information attributes (priority 5)."""
    if "period_interval_count" in current_period:
        attributes["period_interval_count"] = current_period["period_interval_count"]
    if "period_position" in current_period:
        attributes["period_position"] = current_period["period_position"]
    if "periods_total" in current_period:
        attributes["periods_total"] = current_period["periods_total"]
    if "periods_remaining" in current_period:
        attributes["periods_remaining"] = current_period["periods_remaining"]


def add_relaxation_attributes(attributes: dict, current_period: dict) -> None:
    """
    Add relaxation information attributes (priority 6).

    Only adds relaxation attributes if the period was actually relaxed.
    If relaxation_active is False or missing, no attributes are added.
    """
    if current_period.get("relaxation_active"):
        attributes["relaxation_active"] = True
        if "relaxation_level" in current_period:
            attributes["relaxation_level"] = current_period["relaxation_level"]
        if "relaxation_threshold_original_%" in current_period:
            attributes["relaxation_threshold_original_%"] = current_period["relaxation_threshold_original_%"]
        if "relaxation_threshold_applied_%" in current_period:
            attributes["relaxation_threshold_applied_%"] = current_period["relaxation_threshold_applied_%"]


def build_final_attributes_simple(
    current_period: dict | None,
    period_summaries: list[dict],
    *,
    time: TimeService,
) -> dict:
    """
    Build the final attributes dictionary from coordinator's period summaries.

    All calculations are done in the coordinator - this just:
    1. Adds the current timestamp (only thing calculated every 15min)
    2. Uses the current/next period from summaries
    3. Adds nested period summaries

    Attributes are ordered following the documented priority:
    1. Time information (timestamp, start, end, duration)
    2. Core decision attributes (level, rating_level, rating_difference_%)
    3. Price statistics (price_avg, price_min, price_max, price_spread, volatility)
    4. Price differences (period_price_diff_from_daily_min, period_price_diff_from_daily_min_%)
    5. Detail information (period_interval_count, period_position, periods_total, periods_remaining)
    6. Relaxation information (relaxation_active, relaxation_level, relaxation_threshold_original_%,
       relaxation_threshold_applied_%) - only if period was relaxed
    7. Meta information (periods list)

    Args:
        current_period: The current or next period (already complete from coordinator)
        period_summaries: All period summaries from coordinator
        time: TimeService instance (required)

    Returns:
        Complete attributes dict with all fields

    """
    now = time.now()
    current_minute = (now.minute // 15) * 15
    timestamp = now.replace(minute=current_minute, second=0, microsecond=0)

    if current_period:
        # Build attributes in priority order using helper methods
        attributes = {}

        # 1. Time information
        add_time_attributes(attributes, current_period, timestamp)

        # 2. Core decision attributes
        add_decision_attributes(attributes, current_period)

        # 3. Price statistics
        add_price_attributes(attributes, current_period)

        # 4. Price differences
        add_comparison_attributes(attributes, current_period)

        # 5. Detail information
        add_detail_attributes(attributes, current_period)

        # 6. Relaxation information (only if period was relaxed)
        add_relaxation_attributes(attributes, current_period)

        # 7. Meta information (periods array)
        attributes["periods"] = period_summaries

        return attributes

    # No current/next period found - return all periods with timestamp
    return {
        "timestamp": timestamp,
        "periods": period_summaries,
    }


async def build_async_extra_state_attributes(  # noqa: PLR0913
    entity_key: str,
    translation_key: str | None,
    hass: HomeAssistant,
    *,
    time: TimeService,
    config_entry: TibberPricesConfigEntry,
    sensor_attrs: dict | None = None,
    is_on: bool | None = None,
) -> dict | None:
    """
    Build async extra state attributes for binary sensors.

    Adds icon_color and translated descriptions.

    Args:
        entity_key: Entity key (e.g., "best_price_period")
        translation_key: Translation key for entity
        hass: Home Assistant instance
        time: TimeService instance (required)
        config_entry: Config entry with options (keyword-only)
        sensor_attrs: Sensor-specific attributes (keyword-only)
        is_on: Binary sensor state (keyword-only)

    Returns:
        Complete attributes dict with descriptions (synchronous)

    """
    # Calculate default timestamp: current time rounded to nearest quarter hour
    # This ensures all binary sensors have a consistent reference time for when calculations were made
    # Individual sensors can override this via sensor_attrs if needed
    now = time.now()
    default_timestamp = time.round_to_nearest_quarter(now)

    attributes = {
        "timestamp": default_timestamp,
    }

    # Add sensor-specific attributes (may override timestamp)
    if sensor_attrs:
        # Copy and remove internal fields before exposing to user
        clean_attrs = {k: v for k, v in sensor_attrs.items() if not k.startswith("_")}
        # Merge sensor attributes (can override default timestamp)
        attributes.update(clean_attrs)

    # Add icon_color for best/peak price period sensors using shared utility
    add_icon_color_attribute(attributes, entity_key, is_on=is_on)

    # Add description attributes (always last, via central utility)
    from ..entity_utils import async_add_description_attributes  # noqa: PLC0415, TID252

    await async_add_description_attributes(
        attributes,
        "binary_sensor",
        translation_key,
        hass,
        config_entry,
        position="end",
    )

    return attributes if attributes else None


def build_sync_extra_state_attributes(  # noqa: PLR0913
    entity_key: str,
    translation_key: str | None,
    hass: HomeAssistant,
    *,
    time: TimeService,
    config_entry: TibberPricesConfigEntry,
    sensor_attrs: dict | None = None,
    is_on: bool | None = None,
) -> dict | None:
    """
    Build synchronous extra state attributes for binary sensors.

    Adds icon_color and cached translated descriptions.

    Args:
        entity_key: Entity key (e.g., "best_price_period")
        translation_key: Translation key for entity
        hass: Home Assistant instance
        time: TimeService instance (required)
        config_entry: Config entry with options (keyword-only)
        sensor_attrs: Sensor-specific attributes (keyword-only)
        is_on: Binary sensor state (keyword-only)

    Returns:
        Complete attributes dict with cached descriptions

    """
    # Calculate default timestamp: current time rounded to nearest quarter hour
    # This ensures all binary sensors have a consistent reference time for when calculations were made
    # Individual sensors can override this via sensor_attrs if needed
    now = time.now()
    default_timestamp = time.round_to_nearest_quarter(now)

    attributes = {
        "timestamp": default_timestamp,
    }

    # Add sensor-specific attributes (may override timestamp)
    if sensor_attrs:
        # Copy and remove internal fields before exposing to user
        clean_attrs = {k: v for k, v in sensor_attrs.items() if not k.startswith("_")}
        # Merge sensor attributes (can override default timestamp)
        attributes.update(clean_attrs)

    # Add icon_color for best/peak price period sensors using shared utility
    add_icon_color_attribute(attributes, entity_key, is_on=is_on)

    # Add description attributes (always last, via central utility)
    from ..entity_utils import add_description_attributes  # noqa: PLC0415, TID252

    add_description_attributes(
        attributes,
        "binary_sensor",
        translation_key,
        hass,
        config_entry,
        position="end",
    )

    return attributes if attributes else None
