"""Attribute builders for binary sensors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.tibber_prices.const import (
    CONF_EXTENDED_DESCRIPTIONS,
    DEFAULT_EXTENDED_DESCRIPTIONS,
    async_get_entity_description,
    get_entity_description,
)
from custom_components.tibber_prices.entity_utils import add_icon_color_attribute
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from datetime import datetime

    from custom_components.tibber_prices.data import TibberPricesConfigEntry
    from homeassistant.core import HomeAssistant

from .definitions import MIN_TOMORROW_INTERVALS_15MIN


def get_tomorrow_data_available_attributes(coordinator_data: dict) -> dict | None:
    """
    Build attributes for tomorrow_data_available sensor.

    Args:
        coordinator_data: Coordinator data dict

    Returns:
        Attributes dict with intervals_available and data_status

    """
    if not coordinator_data:
        return None

    price_info = coordinator_data.get("priceInfo", {})
    tomorrow_prices = price_info.get("tomorrow", [])
    interval_count = len(tomorrow_prices)

    if interval_count == 0:
        status = "none"
    elif interval_count == MIN_TOMORROW_INTERVALS_15MIN:
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
        reverse_sort: True for peak_price (highest first), False for best_price (lowest first)

    Returns:
        Attributes dict with current/next period and all periods list

    """
    if not coordinator_data:
        return build_no_periods_result()

    # Get precomputed period summaries from coordinator
    periods_data = coordinator_data.get("periods", {})
    period_type = "peak_price" if reverse_sort else "best_price"
    period_data = periods_data.get(period_type)

    if not period_data:
        return build_no_periods_result()

    period_summaries = period_data.get("periods", [])
    if not period_summaries:
        return build_no_periods_result()

    # Find current or next period based on current time
    now = dt_util.now()
    current_period = None

    # First pass: find currently active period
    for period in period_summaries:
        start = period.get("start")
        end = period.get("end")
        if start and end and start <= now < end:
            current_period = period
            break

    # Second pass: find next future period if none is active
    if not current_period:
        for period in period_summaries:
            start = period.get("start")
            if start and start > now:
                current_period = period
                break

    # Build final attributes
    return build_final_attributes_simple(current_period, period_summaries)


def build_no_periods_result() -> dict:
    """
    Build result when no periods exist (not filtered, just none available).

    Returns:
        A dict with empty periods and timestamp.

    """
    # Calculate timestamp: current time rounded down to last quarter hour
    now = dt_util.now()
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

    Returns:
        Complete attributes dict with all fields

    """
    now = dt_util.now()
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
    config_entry: TibberPricesConfigEntry,
    dynamic_attrs: dict | None = None,
    is_on: bool | None = None,
) -> dict | None:
    """
    Build async extra state attributes for binary sensors.

    Adds icon_color and translated descriptions.

    Args:
        entity_key: Entity key (e.g., "best_price_period")
        translation_key: Translation key for entity
        hass: Home Assistant instance
        config_entry: Config entry with options (keyword-only)
        dynamic_attrs: Dynamic attributes from attribute getter (keyword-only)
        is_on: Binary sensor state (keyword-only)

    Returns:
        Complete attributes dict with descriptions

    """
    attributes = {}

    # Add dynamic attributes first
    if dynamic_attrs:
        # Copy and remove internal fields before exposing to user
        clean_attrs = {k: v for k, v in dynamic_attrs.items() if not k.startswith("_")}
        attributes.update(clean_attrs)

    # Add icon_color for best/peak price period sensors using shared utility
    add_icon_color_attribute(attributes, entity_key, is_on=is_on)

    # Add description from the custom translations file
    if translation_key and hass is not None:
        # Get user's language preference
        language = hass.config.language if hass.config.language else "en"

        # Add basic description
        description = await async_get_entity_description(
            hass,
            "binary_sensor",
            translation_key,
            language,
            "description",
        )
        if description:
            attributes["description"] = description

        # Check if extended descriptions are enabled in the config
        extended_descriptions = config_entry.options.get(
            CONF_EXTENDED_DESCRIPTIONS,
            config_entry.data.get(CONF_EXTENDED_DESCRIPTIONS, DEFAULT_EXTENDED_DESCRIPTIONS),
        )

        # Add extended descriptions if enabled
        if extended_descriptions:
            # Add long description if available
            long_desc = await async_get_entity_description(
                hass,
                "binary_sensor",
                translation_key,
                language,
                "long_description",
            )
            if long_desc:
                attributes["long_description"] = long_desc

            # Add usage tips if available
            usage_tips = await async_get_entity_description(
                hass,
                "binary_sensor",
                translation_key,
                language,
                "usage_tips",
            )
            if usage_tips:
                attributes["usage_tips"] = usage_tips

    return attributes if attributes else None


def build_sync_extra_state_attributes(  # noqa: PLR0913
    entity_key: str,
    translation_key: str | None,
    hass: HomeAssistant,
    *,
    config_entry: TibberPricesConfigEntry,
    dynamic_attrs: dict | None = None,
    is_on: bool | None = None,
) -> dict | None:
    """
    Build synchronous extra state attributes for binary sensors.

    Adds icon_color and cached translated descriptions.

    Args:
        entity_key: Entity key (e.g., "best_price_period")
        translation_key: Translation key for entity
        hass: Home Assistant instance
        config_entry: Config entry with options (keyword-only)
        dynamic_attrs: Dynamic attributes from attribute getter (keyword-only)
        is_on: Binary sensor state (keyword-only)

    Returns:
        Complete attributes dict with cached descriptions

    """
    attributes = {}

    # Add dynamic attributes first
    if dynamic_attrs:
        # Copy and remove internal fields before exposing to user
        clean_attrs = {k: v for k, v in dynamic_attrs.items() if not k.startswith("_")}
        attributes.update(clean_attrs)

    # Add icon_color for best/peak price period sensors using shared utility
    add_icon_color_attribute(attributes, entity_key, is_on=is_on)

    # Add descriptions from the cache (non-blocking)
    if translation_key and hass is not None:
        # Get user's language preference
        language = hass.config.language if hass.config.language else "en"

        # Add basic description from cache
        description = get_entity_description(
            "binary_sensor",
            translation_key,
            language,
            "description",
        )
        if description:
            attributes["description"] = description

        # Check if extended descriptions are enabled in the config
        extended_descriptions = config_entry.options.get(
            CONF_EXTENDED_DESCRIPTIONS,
            config_entry.data.get(CONF_EXTENDED_DESCRIPTIONS, DEFAULT_EXTENDED_DESCRIPTIONS),
        )

        # Add extended descriptions if enabled
        if extended_descriptions:
            # Add long description from cache
            long_desc = get_entity_description(
                "binary_sensor",
                translation_key,
                language,
                "long_description",
            )
            if long_desc:
                attributes["long_description"] = long_desc

            # Add usage tips from cache
            usage_tips = get_entity_description(
                "binary_sensor",
                translation_key,
                language,
                "usage_tips",
            )
            if usage_tips:
                attributes["usage_tips"] = usage_tips

    return attributes if attributes else None
