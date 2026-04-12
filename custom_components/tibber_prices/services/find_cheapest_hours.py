"""
Service handler for find_cheapest_hours and find_most_expensive_hours services.

Finds the cheapest (or most expensive) N minutes of intervals within a search range.
Intervals need not be contiguous — designed for flexible loads
(battery charging, EV, water heater with thermostat).
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import voluptuous as vol

from custom_components.tibber_prices.const import (
    DOMAIN,
    get_display_unit_factor,
    get_display_unit_string,
)
from custom_components.tibber_prices.utils.price_window import (
    calculate_window_statistics,
    find_cheapest_n_intervals,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_utils

from .helpers import (
    INTERVAL_MINUTES,
    PRICE_LEVEL_ORDER,
    VALID_SEARCH_SCOPES,
    build_rating_lookup,
    build_response_interval,
    filter_intervals_by_price_level,
    get_entry_and_data,
    resolve_home_timezone,
    resolve_search_range,
    validate_power_profile_length,
    validate_price_level_range,
)

if TYPE_CHECKING:
    from zoneinfo import ZoneInfo

    from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse

_LOGGER = logging.getLogger(__name__)

FIND_CHEAPEST_HOURS_SERVICE_NAME = "find_cheapest_hours"

_COMMON_HOURS_SCHEMA = {
    vol.Optional("entry_id", default=""): cv.string,
    vol.Required("duration"): vol.All(
        cv.positive_time_period,
        vol.Range(min=timedelta(minutes=1), max=timedelta(hours=24)),
    ),
    vol.Optional("search_start"): cv.datetime,
    vol.Optional("search_end"): cv.datetime,
    vol.Optional("search_start_time"): cv.time,
    vol.Optional("search_start_day_offset", default=0): vol.All(vol.Coerce(int), vol.Range(min=-7, max=2)),
    vol.Optional("search_end_time"): cv.time,
    vol.Optional("search_end_day_offset", default=0): vol.All(vol.Coerce(int), vol.Range(min=-7, max=2)),
    vol.Optional("search_start_offset_minutes"): vol.All(vol.Coerce(int), vol.Range(min=-10080, max=10080)),
    vol.Optional("search_end_offset_minutes"): vol.All(vol.Coerce(int), vol.Range(min=-10080, max=10080)),
    vol.Optional("min_segment_duration"): vol.All(
        cv.positive_time_period,
        vol.Range(min=timedelta(minutes=1), max=timedelta(hours=4)),
    ),
    vol.Optional("search_scope"): vol.In(VALID_SEARCH_SCOPES),
    vol.Optional("max_price_level"): vol.In([lvl.lower() for lvl in PRICE_LEVEL_ORDER]),
    vol.Optional("min_price_level"): vol.In([lvl.lower() for lvl in PRICE_LEVEL_ORDER]),
    vol.Optional("include_comparison_details", default=False): cv.boolean,
    vol.Optional("power_profile"): vol.All(
        [vol.All(vol.Coerce(int), vol.Range(min=1, max=100000))],
        vol.Length(min=1, max=96),
    ),
    vol.Optional("include_current_interval", default=True): cv.boolean,
    vol.Optional("use_base_unit", default=False): cv.boolean,
}

FIND_CHEAPEST_HOURS_SERVICE_SCHEMA = vol.Schema(_COMMON_HOURS_SCHEMA)


def _determine_no_intervals_reason(
    price_info: list[dict],
    filtered_price_info: list[dict],
    total_intervals: int,
    *,
    level_filter_active: bool,
) -> str:
    """Classify why no interval selection could be found."""
    if not price_info:
        return "no_data_in_range"
    if level_filter_active and not filtered_price_info:
        return "no_intervals_matching_level_filter"
    if len(filtered_price_info) < total_intervals:
        return "insufficient_intervals_after_filter"
    return "insufficient_intervals_for_constraints"


def _build_found_response(  # noqa: PLR0913
    *,
    result: dict,
    comparison_result: dict | None,
    reverse: bool,
    home_id: str,
    search_start: datetime,
    search_end: datetime,
    total_minutes_requested: int,
    total_minutes: int,
    min_segment_minutes_requested: int,
    min_segment_minutes: int,
    currency: str,
    price_unit: str,
    unit_factor: int,
    service_label: str,
    rating_lookup: dict[str, str | None],
    include_comparison_details: bool = False,
    power_profile: list[int] | None = None,
) -> dict:
    """Build the service response when intervals are found."""
    stats = calculate_window_statistics(
        result["intervals"], unit_factor=unit_factor, round_decimals=4, power_profile=power_profile
    )

    # Calculate price comparison (difference to opposite-direction selection)
    price_comparison: dict[str, float | str | None] = {}
    if comparison_result is not None:
        comparison_stats = calculate_window_statistics(
            comparison_result["intervals"], unit_factor=unit_factor, round_decimals=4
        )
        own_mean = stats.get("price_mean")
        comp_mean = comparison_stats.get("price_mean")
        if own_mean is not None and comp_mean is not None:
            diff = round(float(comp_mean) - float(own_mean), 4)
            if reverse:
                diff = -diff
            price_comparison = {
                "comparison_price_mean": comp_mean,
                "price_difference": abs(round(diff, 4)),
            }
            if include_comparison_details:
                price_comparison["comparison_price_min"] = comparison_stats.get("price_min")
                price_comparison["comparison_price_max"] = comparison_stats.get("price_max")

    response_intervals = [build_response_interval(iv, unit_factor, rating_lookup) for iv in result["intervals"]]

    response_segments = []
    for seg in result["segments"]:
        seg_stats = calculate_window_statistics(seg["intervals"], unit_factor=unit_factor, round_decimals=4)
        last_start = seg["intervals"][-1]["startsAt"]
        if isinstance(last_start, str):
            seg_end = datetime.fromisoformat(last_start) + timedelta(minutes=INTERVAL_MINUTES)
        else:
            seg_end = last_start + timedelta(minutes=INTERVAL_MINUTES)

        response_segments.append(
            {
                "start": seg["start"],
                "end": seg_end.isoformat() if hasattr(seg_end, "isoformat") else seg_end,
                "duration_minutes": seg["duration_minutes"],
                "interval_count": seg["interval_count"],
                "price_mean": seg_stats.get("price_mean"),
                "intervals": [build_response_interval(iv, unit_factor, rating_lookup) for iv in seg["intervals"]],
            }
        )

    actual_minutes = len(result["intervals"]) * INTERVAL_MINUTES

    _LOGGER.info(
        "%s: found %d intervals in %d segments, mean=%.4f %s",
        service_label,
        len(result["intervals"]),
        len(response_segments),
        stats.get("price_mean", 0) or 0,
        price_unit,
    )

    return {
        "home_id": home_id,
        "search_start": search_start.isoformat(),
        "search_end": search_end.isoformat(),
        "total_minutes_requested": total_minutes_requested,
        "total_minutes": total_minutes,
        "min_segment_minutes_requested": min_segment_minutes_requested,
        "min_segment_minutes": min_segment_minutes,
        "currency": currency,
        "price_unit": price_unit,
        "intervals_found": True,
        "schedule": {
            "total_minutes": actual_minutes,
            "interval_count": len(result["intervals"]),
            **stats,
            "segment_count": len(response_segments),
            "segments": response_segments,
            "intervals": response_intervals,
        },
        "price_comparison": price_comparison or None,
    }


async def _handle_find_hours(
    call: ServiceCall,
    *,
    reverse: bool = False,
) -> ServiceResponse:
    """
    Core handler for finding price hours (cheapest or most expensive).

    Finds the cheapest/most expensive N intervals (not necessarily contiguous)
    within the search range. Results are grouped into contiguous segments for
    scheduling convenience.
    """
    service_label = "find_most_expensive_hours" if reverse else "find_cheapest_hours"
    hass: HomeAssistant = call.hass
    entry_id: str = call.data.get("entry_id", "")
    duration_td: timedelta = call.data["duration"]
    min_segment_td: timedelta | None = call.data.get("min_segment_duration")
    use_base_unit: bool = call.data.get("use_base_unit", False)
    max_price_level: str | None = call.data.get("max_price_level")
    min_price_level: str | None = call.data.get("min_price_level")
    include_comparison_details: bool = call.data.get("include_comparison_details", False)
    power_profile: list[int] | None = call.data.get("power_profile")
    level_filter_active = min_price_level is not None or max_price_level is not None

    total_minutes_requested = int(duration_td.total_seconds() / 60)
    min_segment_minutes_requested = int(min_segment_td.total_seconds() / 60) if min_segment_td else INTERVAL_MINUTES

    # Round up to nearest quarter-hour intervals
    total_minutes = math.ceil(total_minutes_requested / INTERVAL_MINUTES) * INTERVAL_MINUTES
    min_segment_minutes = math.ceil(min_segment_minutes_requested / INTERVAL_MINUTES) * INTERVAL_MINUTES

    entry, coordinator, data = get_entry_and_data(hass, entry_id)
    rating_lookup = build_rating_lookup(data)

    home_id = entry.data.get("home_id")
    if not home_id:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="missing_home_id",
        )

    # Resolve timezone
    home_timezone = resolve_home_timezone(coordinator, home_id)
    home_tz: ZoneInfo
    from zoneinfo import ZoneInfo  # noqa: PLC0415

    home_tz = ZoneInfo(home_timezone)

    # Resolve search range (priority: explicit datetime > time+offset > minutes offset > default)
    now = dt_utils.now().astimezone(home_tz)
    search_start, search_end = resolve_search_range(call.data, now, home_tz)

    total_intervals = total_minutes // INTERVAL_MINUTES
    min_segment_intervals = min_segment_minutes // INTERVAL_MINUTES

    # Validate parameter combinations
    validate_price_level_range(min_price_level, max_price_level)
    validate_power_profile_length(power_profile, total_intervals)

    _LOGGER.info(
        "%s called: total=%dmin, min_segment=%dmin, range=%s to %s",
        service_label,
        total_minutes,
        min_segment_minutes,
        search_start,
        search_end,
    )

    # Fetch intervals via pool
    api_client = coordinator.api
    user_data = coordinator._cached_user_data  # noqa: SLF001
    pool = entry.runtime_data.interval_pool

    try:
        price_info, _api_called = await pool.get_intervals(
            api_client=api_client,
            user_data=user_data,
            start_time=search_start,
            end_time=search_end,
        )
    except Exception as error:
        _LOGGER.exception("Error fetching price data for %s", service_label)
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="price_fetch_failed",
        ) from error

    # Determine currency and unit
    currency = entry.data.get("currency", "EUR")
    unit_factor = 1 if use_base_unit else get_display_unit_factor(entry)
    price_unit = f"{currency}/kWh" if use_base_unit else get_display_unit_string(entry, currency)

    # Apply optional price level filter (P5)
    filtered_price_info = filter_intervals_by_price_level(price_info, min_price_level, max_price_level)

    # Find cheapest/most expensive intervals
    result = find_cheapest_n_intervals(filtered_price_info, total_intervals, min_segment_intervals, reverse=reverse)

    if result is None:
        reason = _determine_no_intervals_reason(
            price_info,
            filtered_price_info,
            total_intervals,
            level_filter_active=level_filter_active,
        )
        _LOGGER.info(
            "%s: no interval selection found (reason=%s, need %d, have %d after level filter)",
            service_label,
            reason,
            total_intervals,
            len(filtered_price_info),
        )
        return {
            "home_id": home_id,
            "search_start": search_start.isoformat(),
            "search_end": search_end.isoformat(),
            "total_minutes_requested": total_minutes_requested,
            "total_minutes": total_minutes,
            "min_segment_minutes_requested": min_segment_minutes_requested,
            "min_segment_minutes": min_segment_minutes,
            "currency": currency,
            "price_unit": price_unit,
            "intervals_found": False,
            "reason": reason,
            "schedule": None,
        }

    # Find opposite-direction selection for price comparison (from full unfiltered list)
    comparison_result = find_cheapest_n_intervals(
        price_info, total_intervals, min_segment_intervals, reverse=not reverse
    )

    return _build_found_response(
        result=result,
        comparison_result=comparison_result,
        reverse=reverse,
        home_id=home_id,
        search_start=search_start,
        search_end=search_end,
        total_minutes_requested=total_minutes_requested,
        total_minutes=total_minutes,
        min_segment_minutes_requested=min_segment_minutes_requested,
        min_segment_minutes=min_segment_minutes,
        currency=currency,
        price_unit=price_unit,
        unit_factor=unit_factor,
        service_label=service_label,
        rating_lookup=rating_lookup,
        include_comparison_details=include_comparison_details,
        power_profile=power_profile,
    )


async def handle_find_cheapest_hours(call: ServiceCall) -> ServiceResponse:
    """Handle find_cheapest_hours service call."""
    return await _handle_find_hours(call, reverse=False)
