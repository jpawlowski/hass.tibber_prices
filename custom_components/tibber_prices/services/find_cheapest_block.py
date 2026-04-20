"""
Service handler for find_cheapest_block and find_most_expensive_block services.

Finds the cheapest (or most expensive) contiguous window of a given duration
within a search range. Designed for appliance scheduling (dishwasher, washing
machine, dryer).
"""

from __future__ import annotations

from datetime import datetime, time as dt_time, timedelta
import logging
import math
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from custom_components.tibber_prices.const import DOMAIN, get_display_unit_factor, get_display_unit_string
from custom_components.tibber_prices.utils.price_window import (
    calculate_window_statistics,
    find_cheapest_contiguous_window,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .entity_resolver import or_entity_ref, resolve_entity_references
from .helpers import (
    INTERVAL_MINUTES,
    PRICE_LEVEL_ORDER,
    VALID_SEARCH_SCOPES,
    apply_must_finish_by,
    build_rating_lookup,
    build_response_interval,
    calculate_search_range_avg,
    check_min_distance_from_avg,
    filter_intervals_by_price_level,
    get_entry_and_data,
    resolve_home_timezone,
    resolve_search_range,
    restore_original_prices,
    smooth_service_intervals,
    validate_power_profile_length,
    validate_price_level_range,
    validate_search_params,
)
from .relaxation import (
    MIN_RELAXED_DURATION_INTERVALS,
    calculate_max_duration_reduction_intervals,
    generate_relaxation_steps,
)

if TYPE_CHECKING:
    from zoneinfo import ZoneInfo

    from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse

_LOGGER = logging.getLogger(__name__)

FIND_CHEAPEST_BLOCK_SERVICE_NAME = "find_cheapest_block"

# Parameter types for entity reference resolution (param_name → expected Python type)
COMMON_BLOCK_ENTITY_PARAMS: dict[str, type] = {
    "duration": timedelta,
    "search_start": datetime,
    "search_end": datetime,
    "search_start_time": dt_time,
    "search_end_time": dt_time,
    "search_start_day_offset": int,
    "search_end_day_offset": int,
    "search_start_offset_minutes": int,
    "search_end_offset_minutes": int,
    "min_distance_from_avg": float,
    "duration_flexibility_minutes": int,
    "must_finish_by": datetime,
}

_COMMON_BLOCK_SCHEMA = {
    vol.Optional("entry_id", default=""): cv.string,
    vol.Required("duration"): or_entity_ref(
        vol.All(cv.positive_time_period, vol.Range(min=timedelta(minutes=1), max=timedelta(hours=12))),
    ),
    vol.Optional("search_start"): or_entity_ref(cv.datetime),
    vol.Optional("search_end"): or_entity_ref(cv.datetime),
    vol.Optional("search_start_time"): or_entity_ref(cv.time),
    vol.Optional("search_start_day_offset", default=0): or_entity_ref(
        vol.All(vol.Coerce(int), vol.Range(min=-7, max=2)),
    ),
    vol.Optional("search_end_time"): or_entity_ref(cv.time),
    vol.Optional("search_end_day_offset", default=0): or_entity_ref(
        vol.All(vol.Coerce(int), vol.Range(min=-7, max=2)),
    ),
    vol.Optional("search_start_offset_minutes"): or_entity_ref(
        vol.All(vol.Coerce(int), vol.Range(min=-10080, max=10080)),
    ),
    vol.Optional("search_end_offset_minutes"): or_entity_ref(
        vol.All(vol.Coerce(int), vol.Range(min=-10080, max=10080)),
    ),
    vol.Optional("search_scope"): vol.In(VALID_SEARCH_SCOPES),
    vol.Optional("max_price_level"): vol.In([lvl.lower() for lvl in PRICE_LEVEL_ORDER]),
    vol.Optional("min_price_level"): vol.In([lvl.lower() for lvl in PRICE_LEVEL_ORDER]),
    vol.Optional("include_comparison_details", default=False): cv.boolean,
    vol.Optional("power_profile"): vol.All(
        [vol.All(vol.Coerce(int), vol.Range(min=1, max=100000))],
        vol.Length(min=1, max=48),
    ),
    vol.Optional("include_current_interval", default=True): cv.boolean,
    vol.Optional("use_base_unit", default=False): cv.boolean,
    vol.Optional("smooth_outliers", default=True): cv.boolean,
    vol.Optional("min_distance_from_avg"): or_entity_ref(
        vol.All(vol.Coerce(float), vol.Range(min=0.1, max=50.0)),
    ),
    vol.Optional("allow_relaxation", default=True): cv.boolean,
    vol.Optional("duration_flexibility_minutes"): or_entity_ref(
        vol.All(vol.Coerce(int), vol.Range(min=0, max=120)),
    ),
    vol.Optional("must_finish_by"): or_entity_ref(cv.datetime),
}

FIND_CHEAPEST_BLOCK_SERVICE_SCHEMA = vol.Schema(_COMMON_BLOCK_SCHEMA)


def _compute_price_comparison(
    comparison_result: dict | None,
    unit_factor: int,
    stats: dict,
    *,
    reverse: bool,
    include_details: bool = False,
) -> dict[str, float | str | None] | None:
    """Compute price comparison between the selected and opposite-direction window."""
    if comparison_result is None:
        return None

    comparison_stats = calculate_window_statistics(
        comparison_result["intervals"], unit_factor=unit_factor, round_decimals=4
    )
    if stats.get("price_mean") is None or comparison_stats.get("price_mean") is None:
        return None

    diff = round(comparison_stats["price_mean"] - stats["price_mean"], 4)
    if reverse:
        diff = -diff

    result: dict[str, float | str | None] = {
        "comparison_price_mean": comparison_stats["price_mean"],
        "price_difference": abs(diff),
        "comparison_window_start": (
            comparison_result["intervals"][0]["startsAt"]
            if isinstance(comparison_result["intervals"][0]["startsAt"], str)
            else comparison_result["intervals"][0]["startsAt"].isoformat()
        ),
    }

    # Optional enrichment (P6)
    if include_details:
        result["comparison_price_min"] = comparison_stats.get("price_min")
        result["comparison_price_max"] = comparison_stats.get("price_max")
        last_start = comparison_result["intervals"][-1]["startsAt"]
        if not isinstance(last_start, str):
            last_start = last_start.isoformat()
        result["comparison_window_end"] = (
            datetime.fromisoformat(last_start) + timedelta(minutes=INTERVAL_MINUTES)
        ).isoformat()

    return result


def _determine_no_window_reason(
    price_info: list[dict],
    filtered_price_info: list[dict],
    duration_intervals: int,
    *,
    level_filter_active: bool,
) -> str:
    """Classify why no block window could be found."""
    if not price_info:
        return "no_data_in_range"
    if level_filter_active and not filtered_price_info:
        return "no_intervals_matching_level_filter"
    if len(filtered_price_info) < duration_intervals:
        return "insufficient_intervals_after_filter"
    return "insufficient_contiguous_window"


def _attempt_find_block(
    price_info: list[dict],
    *,
    max_price_level: str | None,
    min_price_level: str | None,
    duration_intervals: int,
    smooth_outliers: bool,
    min_distance_from_avg: float | None,
    reverse: bool,
) -> tuple[dict | None, str]:
    """Attempt to find a block with specific filter parameters.

    Returns:
        (result_dict, "") on success or (None, reason_code) on failure.

    """
    level_filter_active = min_price_level is not None or max_price_level is not None
    filtered = filter_intervals_by_price_level(price_info, min_price_level, max_price_level)

    if smooth_outliers and filtered:
        search_data = smooth_service_intervals(filtered)
    else:
        search_data = filtered

    result = find_cheapest_contiguous_window(search_data, duration_intervals, reverse=reverse)

    if result is None:
        return None, _determine_no_window_reason(
            price_info, filtered, duration_intervals, level_filter_active=level_filter_active
        )

    # Restore original prices (smoothing only affects window selection)
    if smooth_outliers:
        result["intervals"] = restore_original_prices(result["intervals"])

    # Check distance constraint
    if min_distance_from_avg is not None:
        range_avg = calculate_search_range_avg(price_info)
        window_mean = sum(iv["total"] for iv in result["intervals"]) / len(result["intervals"])
        if range_avg is not None and not check_min_distance_from_avg(
            window_mean, range_avg, min_distance_from_avg, reverse=reverse
        ):
            return None, "window_above_distance_threshold" if not reverse else "window_below_distance_threshold"

    return result, ""


async def _handle_find_block(
    call: ServiceCall,
    *,
    reverse: bool = False,
) -> ServiceResponse:
    """
    Core handler for finding price blocks (cheapest or most expensive).

    Finds the cheapest/most expensive contiguous window of the requested
    duration within the search range using a sliding window algorithm.
    """
    service_label = "find_most_expensive_block" if reverse else "find_cheapest_block"
    hass: HomeAssistant = call.hass

    # Resolve entity references (e.g., "input_number.wash_duration" → 90 minutes)
    data, resolved_refs = resolve_entity_references(hass, call.data, COMMON_BLOCK_ENTITY_PARAMS)

    entry_id: str = data.get("entry_id", "")
    duration_td: timedelta = data["duration"]
    use_base_unit: bool = data.get("use_base_unit", False)
    max_price_level: str | None = data.get("max_price_level")
    min_price_level: str | None = data.get("min_price_level")
    include_comparison_details: bool = data.get("include_comparison_details", False)
    power_profile: list[int] | None = data.get("power_profile")
    smooth_outliers: bool = data.get("smooth_outliers", True)
    min_distance_from_avg: float | None = data.get("min_distance_from_avg")
    allow_relaxation: bool = data.get("allow_relaxation", True)
    duration_flexibility_minutes: int | None = data.get("duration_flexibility_minutes")

    duration_minutes_requested = int(duration_td.total_seconds() / 60)
    # Round up to nearest quarter-hour interval
    duration_minutes = math.ceil(duration_minutes_requested / INTERVAL_MINUTES) * INTERVAL_MINUTES

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

    # Handle must_finish_by: convert deadline to search_end
    validate_search_params(data)
    effective_data, must_finish_by_dt = apply_must_finish_by(data, home_tz)

    # Resolve search range (priority: explicit datetime > time+offset > minutes offset > default)
    now = dt_util.now().astimezone(home_tz)
    search_start, search_end = resolve_search_range(effective_data, now, home_tz)

    duration_intervals = duration_minutes // INTERVAL_MINUTES

    # Validate parameter combinations
    validate_price_level_range(min_price_level, max_price_level)
    validate_power_profile_length(power_profile, duration_intervals)

    _LOGGER.info(
        "%s called: duration=%dmin, range=%s to %s",
        service_label,
        duration_minutes,
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

    # --- Attempt with original parameters ---
    effective_duration = duration_intervals
    result, reason = _attempt_find_block(
        price_info,
        max_price_level=max_price_level,
        min_price_level=min_price_level,
        duration_intervals=effective_duration,
        smooth_outliers=smooth_outliers,
        min_distance_from_avg=min_distance_from_avg,
        reverse=reverse,
    )

    relaxation_applied = False
    relaxation_steps = 0

    # --- Relaxation loop ---
    if result is None and allow_relaxation:
        max_reduction = calculate_max_duration_reduction_intervals(duration_intervals, duration_flexibility_minutes)
        steps = generate_relaxation_steps(
            min_distance_from_avg=min_distance_from_avg,
            max_price_level=max_price_level,
            min_price_level=min_price_level,
            total_intervals=duration_intervals,
            min_duration_intervals=MIN_RELAXED_DURATION_INTERVALS,
            max_duration_reduction_intervals=max_reduction,
            reverse=reverse,
        )
        for step in steps:
            effective_duration = duration_intervals - step.duration_reduction
            result, reason = _attempt_find_block(
                price_info,
                max_price_level=step.max_price_level,
                min_price_level=step.min_price_level,
                duration_intervals=effective_duration,
                smooth_outliers=smooth_outliers,
                min_distance_from_avg=step.min_distance_from_avg,
                reverse=reverse,
            )
            if result is not None:
                relaxation_applied = True
                relaxation_steps = step.step_number
                effective_duration_minutes = effective_duration * INTERVAL_MINUTES
                _LOGGER.info(
                    "%s: relaxation succeeded at step %d (phase=%s, duration=%dmin)",
                    service_label,
                    step.step_number,
                    step.phase,
                    effective_duration_minutes,
                )
                break
        else:
            reason = "relaxation_exhausted"

    if result is None:
        _LOGGER.info(
            "%s: no window found (reason=%s, need %d intervals, have %d in range)",
            service_label,
            reason,
            effective_duration,
            len(price_info),
        )
        response: dict[str, Any] = {
            "home_id": home_id,
            "search_start": search_start.isoformat(),
            "search_end": search_end.isoformat(),
            "must_finish_by": must_finish_by_dt.isoformat() if must_finish_by_dt else None,
            "duration_minutes_requested": duration_minutes_requested,
            "duration_minutes": effective_duration * INTERVAL_MINUTES,
            "currency": currency,
            "price_unit": price_unit,
            "window_found": False,
            "reason": reason,
            "relaxation_applied": relaxation_applied,
            "window": None,
        }
        if relaxation_applied:
            response["relaxation_steps"] = relaxation_steps
        if resolved_refs:
            response["_resolved"] = resolved_refs
        return response

    # Effective duration may differ from original if relaxation reduced it
    effective_duration_minutes = effective_duration * INTERVAL_MINUTES

    # Find the opposite-direction window for price comparison (from full unfiltered list)
    comparison_result = find_cheapest_contiguous_window(price_info, effective_duration, reverse=not reverse)

    # Calculate statistics and build response
    stats = calculate_window_statistics(
        result["intervals"], unit_factor=unit_factor, round_decimals=4, power_profile=power_profile
    )

    # Calculate price comparison (difference to opposite-direction window)
    price_comparison = _compute_price_comparison(
        comparison_result, unit_factor, stats, reverse=reverse, include_details=include_comparison_details
    )

    # Build interval list with converted prices
    response_intervals = [build_response_interval(iv, unit_factor, rating_lookup) for iv in result["intervals"]]

    # Calculate end time (last interval start + 15 min)
    last_start = result["intervals"][-1]["startsAt"]
    if isinstance(last_start, str):
        end_time = datetime.fromisoformat(last_start) + timedelta(minutes=INTERVAL_MINUTES)
    else:
        end_time = last_start + timedelta(minutes=INTERVAL_MINUTES)

    # Calculate seconds until window start for scheduling convenience
    window_start_str = (
        result["intervals"][0]["startsAt"]
        if isinstance(result["intervals"][0]["startsAt"], str)
        else result["intervals"][0]["startsAt"].isoformat()
    )
    window_start_dt = datetime.fromisoformat(window_start_str)
    seconds_until_start = max(0, int((window_start_dt - now).total_seconds()))
    end_time_dt = end_time if isinstance(end_time, datetime) else datetime.fromisoformat(end_time)
    seconds_until_end = max(0, int((end_time_dt - now).total_seconds()))

    response = {
        "home_id": home_id,
        "search_start": search_start.isoformat(),
        "search_end": search_end.isoformat(),
        "must_finish_by": must_finish_by_dt.isoformat() if must_finish_by_dt else None,
        "duration_minutes_requested": duration_minutes_requested,
        "duration_minutes": effective_duration_minutes,
        "currency": currency,
        "price_unit": price_unit,
        "window_found": True,
        "relaxation_applied": relaxation_applied,
        "window": {
            "start": window_start_str,
            "end": end_time.isoformat() if hasattr(end_time, "isoformat") else end_time,
            "seconds_until_start": seconds_until_start,
            "seconds_until_end": seconds_until_end,
            "duration_minutes": effective_duration_minutes,
            "interval_count": len(result["intervals"]),
            **stats,
            "intervals": response_intervals,
        },
        "price_comparison": price_comparison or None,
    }
    if relaxation_applied:
        response["relaxation_steps"] = relaxation_steps
    if resolved_refs:
        response["_resolved"] = resolved_refs

    _LOGGER.info(
        "%s: found window at %s, mean=%.4f %s",
        service_label,
        response["window"]["start"],
        stats.get("price_mean", 0) or 0,
        price_unit,
    )

    return response


async def handle_find_cheapest_block(call: ServiceCall) -> ServiceResponse:
    """Handle find_cheapest_block service call."""
    return await _handle_find_block(call, reverse=False)
