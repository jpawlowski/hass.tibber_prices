"""
Service handler for find_cheapest_schedule service.

Finds optimal non-overlapping blocks for multiple tasks within a search range.
Uses a greedy algorithm: tasks are sorted by duration (longest first), then
each task claims the cheapest available contiguous window in the remaining pool.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from custom_components.tibber_prices.const import (
    DOMAIN,
    get_display_unit_factor,
    get_display_unit_string,
)
from custom_components.tibber_prices.utils.price_window import (
    calculate_window_statistics,
    find_cheapest_contiguous_window,
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

FIND_CHEAPEST_SCHEDULE_SERVICE_NAME = "find_cheapest_schedule"

_TASK_SCHEMA = vol.Schema(
    {
        vol.Required("name"): cv.string,
        vol.Required("duration"): vol.All(
            cv.positive_time_period,
            vol.Range(min=timedelta(minutes=1), max=timedelta(hours=12)),
        ),
        vol.Optional("power_profile"): vol.All(
            [vol.All(vol.Coerce(int), vol.Range(min=1, max=100000))],
            vol.Length(min=1, max=48),
        ),
    }
)

FIND_CHEAPEST_SCHEDULE_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id", default=""): cv.string,
        vol.Required("tasks"): vol.All(
            [_TASK_SCHEMA],
            vol.Length(min=1, max=4),
        ),
        vol.Optional("gap_minutes", default=0): vol.All(vol.Coerce(int), vol.Range(min=0, max=120)),
        vol.Optional("search_start"): cv.datetime,
        vol.Optional("search_end"): cv.datetime,
        vol.Optional("search_start_time"): cv.time,
        vol.Optional("search_start_day_offset", default=0): vol.All(vol.Coerce(int), vol.Range(min=-7, max=2)),
        vol.Optional("search_end_time"): cv.time,
        vol.Optional("search_end_day_offset", default=0): vol.All(vol.Coerce(int), vol.Range(min=-7, max=2)),
        vol.Optional("search_start_offset_minutes"): vol.All(vol.Coerce(int), vol.Range(min=-10080, max=10080)),
        vol.Optional("search_end_offset_minutes"): vol.All(vol.Coerce(int), vol.Range(min=-10080, max=10080)),
        vol.Optional("search_scope"): vol.In(VALID_SEARCH_SCOPES),
        vol.Optional("max_price_level"): vol.In([lvl.lower() for lvl in PRICE_LEVEL_ORDER]),
        vol.Optional("min_price_level"): vol.In([lvl.lower() for lvl in PRICE_LEVEL_ORDER]),
        vol.Optional("include_comparison_details", default=False): cv.boolean,
        vol.Optional("use_base_unit", default=False): cv.boolean,
    }
)


def _compute_task_price_comparison(
    task_intervals: list[dict[str, Any]],
    full_price_info: list[dict[str, Any]],
    unit_factor: int,
    *,
    include_details: bool,
) -> dict[str, float | str | None] | None:
    """Compute per-task comparison against most expensive window of same duration."""
    duration_intervals = len(task_intervals)
    comparison_result = find_cheapest_contiguous_window(full_price_info, duration_intervals, reverse=True)
    if comparison_result is None:
        return None

    task_stats = calculate_window_statistics(task_intervals, unit_factor=unit_factor, round_decimals=4)
    comparison_stats = calculate_window_statistics(
        comparison_result["intervals"], unit_factor=unit_factor, round_decimals=4
    )
    task_mean = task_stats.get("price_mean")
    comparison_mean = comparison_stats.get("price_mean")
    if task_mean is None or comparison_mean is None:
        return None

    comparison_window_start = comparison_result["intervals"][0]["startsAt"]
    if not isinstance(comparison_window_start, str):
        comparison_window_start = comparison_window_start.isoformat()

    result: dict[str, float | str | None] = {
        "comparison_price_mean": comparison_mean,
        "price_difference": abs(round(float(comparison_mean) - float(task_mean), 4)),
        "comparison_window_start": comparison_window_start,
    }

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


def _determine_schedule_reason(
    *,
    all_tasks_scheduled: bool,
    assignments_count: int,
    price_info: list[dict[str, Any]],
    filtered_price_info: list[dict[str, Any]],
    level_filter_active: bool,
) -> str | None:
    """Classify schedule outcome reason for automation-friendly no-result handling."""
    if all_tasks_scheduled:
        return None
    if not price_info:
        return "no_data_in_range"
    if level_filter_active and not filtered_price_info:
        return "no_intervals_matching_level_filter"
    if assignments_count == 0:
        return "insufficient_contiguous_window"
    return "insufficient_contiguous_window_for_some_tasks"


def _find_cheapest_window_in_pool(
    pool: list[dict[str, Any]],
    duration_intervals: int,
    available: list[bool],
) -> tuple[int, int] | None:
    """
    Find the cheapest contiguous window of `duration_intervals` in available pool slots.

    Args:
        pool: Full sorted interval list.
        duration_intervals: Required contiguous count.
        available: Boolean mask, same length as pool. True = still available.

    Returns:
        (start_index, end_index_exclusive) of the best window, or None if not found.

    """
    n = len(pool)
    best_sum: float | None = None
    best_start: int = -1

    i = 0
    while i <= n - duration_intervals:
        # Check if a contiguous block starting at i is fully available
        # and all intervals are contiguous in time (no gaps)
        block: list[dict[str, Any]] = []
        j = i
        while j < n and len(block) < duration_intervals:
            if not available[j]:
                break
            if block:
                # Check temporal contiguity
                prev_start = block[-1]["startsAt"]
                curr_start = pool[j]["startsAt"]
                prev_dt = datetime.fromisoformat(prev_start) if isinstance(prev_start, str) else prev_start
                curr_dt = datetime.fromisoformat(curr_start) if isinstance(curr_start, str) else curr_start
                if curr_dt - prev_dt != timedelta(minutes=INTERVAL_MINUTES):
                    # Gap in time — can't extend this block, skip to j+1
                    break
            block.append(pool[j])
            j += 1

        if len(block) == duration_intervals:
            window_sum = sum(iv["total"] for iv in block)
            if best_sum is None or window_sum < best_sum:
                best_sum = window_sum
                best_start = i
            i += 1
        else:
            # Skip past the blocking unavailable/non-contiguous slot
            i = j + 1

    if best_start == -1:
        return None

    return (best_start, best_start + duration_intervals)


async def handle_find_cheapest_schedule(call: ServiceCall) -> ServiceResponse:  # noqa: PLR0915
    """Handle find_cheapest_schedule service call."""
    service_label = "find_cheapest_schedule"
    hass: HomeAssistant = call.hass
    entry_id: str = call.data.get("entry_id", "")
    tasks_raw: list[dict[str, Any]] = call.data["tasks"]
    gap_minutes: int = call.data.get("gap_minutes", 0)
    use_base_unit: bool = call.data.get("use_base_unit", False)
    max_price_level: str | None = call.data.get("max_price_level")
    min_price_level: str | None = call.data.get("min_price_level")
    include_comparison_details: bool = call.data.get("include_comparison_details", False)
    level_filter_active = min_price_level is not None or max_price_level is not None

    # Validate task names are unique (before any expensive operations)
    task_names = [t["name"] for t in tasks_raw]
    duplicate_names = sorted({n for n in task_names if task_names.count(n) > 1})
    if duplicate_names:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="duplicate_task_names",
            translation_placeholders={"names": ", ".join(duplicate_names)},
        )

    # Round gap up to nearest quarter interval
    gap_intervals = math.ceil(gap_minutes / INTERVAL_MINUTES) if gap_minutes > 0 else 0

    entry, coordinator, data = get_entry_and_data(hass, entry_id)
    rating_lookup = build_rating_lookup(data)

    home_id = entry.data.get("home_id")
    if not home_id:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="missing_home_id",
        )

    home_timezone = resolve_home_timezone(coordinator, home_id)
    home_tz: ZoneInfo
    from zoneinfo import ZoneInfo  # noqa: PLC0415

    home_tz = ZoneInfo(home_timezone)

    now = dt_utils.now().astimezone(home_tz)
    search_start, search_end = resolve_search_range(call.data, now, home_tz)

    # Resolve task durations (round up to intervals)
    tasks: list[dict[str, Any]] = []
    for task in tasks_raw:
        dur_td: timedelta = task["duration"]
        dur_minutes_req = int(dur_td.total_seconds() / 60)
        dur_minutes = math.ceil(dur_minutes_req / INTERVAL_MINUTES) * INTERVAL_MINUTES
        dur_intervals = dur_minutes // INTERVAL_MINUTES
        validate_power_profile_length(task.get("power_profile"), dur_intervals)
        tasks.append(
            {
                "name": task["name"],
                "duration_minutes_requested": dur_minutes_req,
                "duration_minutes": dur_minutes,
                "duration_intervals": dur_intervals,
                "power_profile": task.get("power_profile"),
            }
        )

    # Validate parameter combinations
    validate_price_level_range(min_price_level, max_price_level)

    # Validate that total task time + gaps fits within the search window
    window_minutes = int((search_end - search_start).total_seconds() / 60)
    total_task_minutes = sum(t["duration_minutes"] for t in tasks)
    total_gap_minutes = gap_intervals * INTERVAL_MINUTES * max(0, len(tasks) - 1)
    required_minutes = total_task_minutes + total_gap_minutes
    if required_minutes > window_minutes:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="tasks_exceed_search_window",
            translation_placeholders={
                "total_minutes": str(required_minutes),
                "window_minutes": str(window_minutes),
            },
        )

    _LOGGER.info(
        "%s called: %d tasks, gap=%dmin, range=%s to %s",
        service_label,
        len(tasks),
        gap_minutes,
        search_start,
        search_end,
    )

    # Fetch intervals
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

    currency = entry.data.get("currency", "EUR")
    unit_factor = 1 if use_base_unit else get_display_unit_factor(entry)
    price_unit = f"{currency}/kWh" if use_base_unit else get_display_unit_string(entry, currency)

    # Apply optional level filter
    filtered_price_info = filter_intervals_by_price_level(price_info, min_price_level, max_price_level)

    if not filtered_price_info:
        reason = _determine_schedule_reason(
            all_tasks_scheduled=False,
            assignments_count=0,
            price_info=price_info,
            filtered_price_info=filtered_price_info,
            level_filter_active=level_filter_active,
        )
        return {
            "home_id": home_id,
            "search_start": search_start.isoformat(),
            "search_end": search_end.isoformat(),
            "currency": currency,
            "price_unit": price_unit,
            "all_tasks_scheduled": False,
            "reason": reason,
            "tasks": [],
            "total_estimated_cost": None,
        }

    # Greedy assignment: longest task first
    tasks_sorted = sorted(tasks, key=lambda t: t["duration_intervals"], reverse=True)
    available = [True] * len(filtered_price_info)
    assignments: list[dict[str, Any]] = []
    unscheduled: list[str] = []

    for task in tasks_sorted:
        dur_intervals = task["duration_intervals"]
        window = _find_cheapest_window_in_pool(filtered_price_info, dur_intervals, available)

        if window is None:
            _LOGGER.info("%s: no window found for task '%s'", service_label, task["name"])
            unscheduled.append(task["name"])
            continue

        start_idx, end_idx = window
        task_intervals = filtered_price_info[start_idx:end_idx]

        # Mark task intervals + trailing gap as unavailable
        gap_end = min(end_idx + gap_intervals, len(filtered_price_info))
        for k in range(start_idx, gap_end):
            available[k] = False

        stats = calculate_window_statistics(
            task_intervals,
            unit_factor=unit_factor,
            round_decimals=4,
            power_profile=task.get("power_profile"),
        )

        first_start = task_intervals[0]["startsAt"]
        last_start = task_intervals[-1]["startsAt"]
        first_dt = datetime.fromisoformat(first_start) if isinstance(first_start, str) else first_start
        last_dt = datetime.fromisoformat(last_start) if isinstance(last_start, str) else last_start
        end_dt = last_dt + timedelta(minutes=INTERVAL_MINUTES)

        # Build enriched interval list for this task
        task_response_intervals = [build_response_interval(iv, unit_factor, rating_lookup) for iv in task_intervals]

        assignments.append(
            {
                "name": task["name"],
                "start": first_dt.isoformat(),
                "end": end_dt.isoformat(),
                "duration_minutes_requested": task["duration_minutes_requested"],
                "duration_minutes": task["duration_minutes"],
                **stats,
                "intervals": task_response_intervals,
                "price_comparison": _compute_task_price_comparison(
                    task_intervals,
                    price_info,
                    unit_factor,
                    include_details=include_comparison_details,
                ),
            }
        )

    # Sort final assignments by start time
    assignments.sort(key=lambda a: a["start"])

    # Sum estimated costs
    total_cost_values: list[float] = [
        a["estimated_total_cost"] for a in assignments if a.get("estimated_total_cost") is not None
    ]
    total_estimated_cost = round(sum(total_cost_values), 4) if total_cost_values else None

    all_scheduled = len(unscheduled) == 0
    reason = _determine_schedule_reason(
        all_tasks_scheduled=all_scheduled,
        assignments_count=len(assignments),
        price_info=price_info,
        filtered_price_info=filtered_price_info,
        level_filter_active=level_filter_active,
    )

    _LOGGER.info(
        "%s: scheduled %d/%d tasks, total_cost=%s",
        service_label,
        len(assignments),
        len(tasks),
        total_estimated_cost,
    )

    result: dict[str, Any] = {
        "home_id": home_id,
        "search_start": search_start.isoformat(),
        "search_end": search_end.isoformat(),
        "currency": currency,
        "price_unit": price_unit,
        "all_tasks_scheduled": all_scheduled,
        "reason": reason,
        "unscheduled_tasks": unscheduled or None,
        "tasks": assignments,
        "total_estimated_cost": total_estimated_cost,
    }
    return result
