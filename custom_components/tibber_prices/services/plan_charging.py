"""Service handler for the plan_charging service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time as dt_time, timedelta
import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from custom_components.tibber_prices.const import DOMAIN, get_display_unit_factor, get_display_unit_string
from custom_components.tibber_prices.utils.price_window import (
    calculate_window_statistics,
    find_cheapest_n_intervals,
    group_intervals_into_segments,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .charging import (
    apply_segment_constraints,
    build_deadline_schedule,
    build_power_schedule,
    build_soc_progression_from_schedule,
    calculate_energy_needed,
    calculate_plan_economics,
    determine_power_mode,
    energy_for_power,
    filter_intervals_by_profitability,
    get_deadline_events,
    resolve_deadline,
    soc_percent_to_kwh,
)
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

PLAN_CHARGING_SERVICE_NAME = "plan_charging"

_CHARGING_ENTITY_PARAMS: dict[str, type] = {
    "battery_capacity_kwh": float,
    "current_soc_percent": float,
    "current_soc_kwh": float,
    "target_soc_percent": float,
    "target_soc_kwh": float,
    "must_reach_soc_percent": float,
    "must_reach_soc_kwh": float,
    "max_charge_power_w": int,
    "min_charge_power_w": int,
    "grid_import_limit_w": int,
    "charging_efficiency": float,
    "discharging_efficiency": float,
    "expected_discharge_price": float,
    "max_cost_per_kwh": float,
    "min_charge_duration_minutes": int,
    "max_cycles_per_day": int,
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
    "must_reach_by": datetime,
}

PLAN_CHARGING_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id", default=""): cv.string,
        vol.Optional("battery_capacity_kwh"): or_entity_ref(
            vol.All(vol.Coerce(float), vol.Range(min=0.1, max=1000.0)),
        ),
        vol.Optional("current_soc_percent"): or_entity_ref(
            vol.All(vol.Coerce(float), vol.Range(min=0.0, max=100.0)),
        ),
        vol.Optional("current_soc_kwh"): or_entity_ref(vol.All(vol.Coerce(float), vol.Range(min=0.0))),
        vol.Optional("target_soc_percent"): or_entity_ref(
            vol.All(vol.Coerce(float), vol.Range(min=0.0, max=100.0)),
        ),
        vol.Optional("target_soc_kwh"): or_entity_ref(vol.All(vol.Coerce(float), vol.Range(min=0.0))),
        vol.Optional("must_reach_soc_percent"): or_entity_ref(
            vol.All(vol.Coerce(float), vol.Range(min=0.0, max=100.0)),
        ),
        vol.Optional("must_reach_soc_kwh"): or_entity_ref(vol.All(vol.Coerce(float), vol.Range(min=0.0))),
        vol.Required("max_charge_power_w"): or_entity_ref(
            vol.All(vol.Coerce(int), vol.Range(min=1, max=100000)),
        ),
        vol.Optional("min_charge_power_w"): or_entity_ref(
            vol.All(vol.Coerce(int), vol.Range(min=1, max=100000)),
        ),
        vol.Optional("charge_power_steps_w"): vol.All(
            [vol.All(vol.Coerce(int), vol.Range(min=1, max=100000))],
            vol.Length(min=1, max=20),
        ),
        vol.Optional("grid_import_limit_w"): or_entity_ref(
            vol.All(vol.Coerce(int), vol.Range(min=1, max=100000)),
        ),
        vol.Optional("charging_efficiency", default=1.0): or_entity_ref(
            vol.All(vol.Coerce(float), vol.Range(min=0.5, max=1.0)),
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
        vol.Optional("include_current_interval", default=True): cv.boolean,
        vol.Optional("must_finish_by"): or_entity_ref(cv.datetime),
        vol.Optional("must_reach_by"): or_entity_ref(cv.datetime),
        vol.Optional("must_reach_by_event"): vol.In(sorted(get_deadline_events())),
        vol.Optional("max_price_level"): vol.In([level.lower() for level in PRICE_LEVEL_ORDER]),
        vol.Optional("min_price_level"): vol.In([level.lower() for level in PRICE_LEVEL_ORDER]),
        vol.Optional("include_comparison_details", default=False): cv.boolean,
        vol.Optional("use_base_unit", default=False): cv.boolean,
        vol.Optional("smooth_outliers", default=True): cv.boolean,
        vol.Optional("min_distance_from_avg"): or_entity_ref(
            vol.All(vol.Coerce(float), vol.Range(min=0.1, max=50.0)),
        ),
        vol.Optional("allow_relaxation", default=True): cv.boolean,
        vol.Optional("duration_flexibility_minutes"): or_entity_ref(
            vol.All(vol.Coerce(int), vol.Range(min=0, max=120)),
        ),
        vol.Optional("discharging_efficiency", default=1.0): or_entity_ref(
            vol.All(vol.Coerce(float), vol.Range(min=0.5, max=1.0)),
        ),
        vol.Optional("expected_discharge_price"): or_entity_ref(
            vol.All(vol.Coerce(float), vol.Range(min=0.0, max=100000.0)),
        ),
        vol.Optional("reserve_for_discharge", default=False): cv.boolean,
        vol.Optional("max_cost_per_kwh"): or_entity_ref(
            vol.All(vol.Coerce(float), vol.Range(min=0.0, max=100000.0)),
        ),
        vol.Optional("min_charge_duration_minutes"): or_entity_ref(
            vol.All(vol.Coerce(int), vol.Range(min=15, max=240)),
        ),
        vol.Optional("max_cycles_per_day"): or_entity_ref(
            vol.All(vol.Coerce(int), vol.Range(min=1, max=20)),
        ),
    }
)


def _interval_start(interval: dict[str, Any]) -> datetime:
    starts_at = interval["startsAt"]
    return datetime.fromisoformat(starts_at) if isinstance(starts_at, str) else starts_at


def _translate_error_key(error_key: str) -> ServiceValidationError:
    return ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key=error_key,
    )


def _resolve_soc_value(
    data: dict[str, Any],
    *,
    percent_key: str,
    kwh_key: str,
    capacity_kwh: float | None,
    field_name: str,
    required: bool,
) -> float | None:
    has_percent = percent_key in data
    has_kwh = kwh_key in data

    if has_percent and has_kwh:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="ambiguous_soc_input",
            translation_placeholders={"field": field_name},
        )

    if not has_percent and not has_kwh:
        if required:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key=f"missing_{field_name}",
            )
        return None

    if has_percent:
        if capacity_kwh is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="capacity_required_for_percent",
            )
        return soc_percent_to_kwh(float(data[percent_key]), capacity_kwh)

    return float(data[kwh_key])


def _validate_soc_inputs(data: dict[str, Any]) -> dict[str, float | None]:
    capacity_kwh = float(data["battery_capacity_kwh"]) if "battery_capacity_kwh" in data else None
    current_soc_kwh = _resolve_soc_value(
        data,
        percent_key="current_soc_percent",
        kwh_key="current_soc_kwh",
        capacity_kwh=capacity_kwh,
        field_name="current_soc",
        required=True,
    )
    target_soc_kwh = _resolve_soc_value(
        data,
        percent_key="target_soc_percent",
        kwh_key="target_soc_kwh",
        capacity_kwh=capacity_kwh,
        field_name="target_soc",
        required=True,
    )
    must_reach_soc_kwh = _resolve_soc_value(
        data,
        percent_key="must_reach_soc_percent",
        kwh_key="must_reach_soc_kwh",
        capacity_kwh=capacity_kwh,
        field_name="must_reach_soc",
        required=False,
    )

    if capacity_kwh is not None and target_soc_kwh is not None and target_soc_kwh > capacity_kwh + 1e-6:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="target_exceeds_capacity",
            translation_placeholders={
                "target_soc_kwh": f"{target_soc_kwh:.2f}",
                "capacity_kwh": f"{capacity_kwh:.2f}",
            },
        )

    if must_reach_soc_kwh is not None and "must_reach_by" not in data and "must_reach_by_event" not in data:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="missing_deadline_for_must_reach",
        )

    if must_reach_soc_kwh is None and ("must_reach_by" in data or "must_reach_by_event" in data):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="missing_must_reach_soc",
        )

    if current_soc_kwh is not None and target_soc_kwh is not None and must_reach_soc_kwh is not None:
        if must_reach_soc_kwh < current_soc_kwh - 1e-6 or must_reach_soc_kwh > target_soc_kwh + 1e-6:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_must_reach_soc",
            )

    return {
        "capacity_kwh": capacity_kwh,
        "current_soc_kwh": current_soc_kwh,
        "target_soc_kwh": target_soc_kwh,
        "must_reach_soc_kwh": must_reach_soc_kwh,
    }


def _build_candidate_intervals(
    price_info: list[dict[str, Any]],
    *,
    max_price_level: str | None,
    min_price_level: str | None,
    smooth_outliers: bool,
    charging_efficiency: float,
    discharging_efficiency: float,
    expected_discharge_price_base: float | None,
    reserve_for_discharge: bool,
    max_cost_per_kwh_base: float | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    filtered_by_level = filter_intervals_by_price_level(price_info, min_price_level, max_price_level)
    candidates = [dict(interval) for interval in filtered_by_level]

    if smooth_outliers and candidates:
        from .helpers import smooth_service_intervals  # noqa: PLC0415

        smoothed = smooth_service_intervals([dict(interval) for interval in candidates])
        smoothed_map = {interval["startsAt"]: float(interval["total"]) for interval in smoothed}
        for candidate in candidates:
            candidate["_sort_total"] = smoothed_map.get(candidate["startsAt"], float(candidate["total"]))

    candidates, economics_filter = filter_intervals_by_profitability(
        candidates,
        charging_efficiency=charging_efficiency,
        discharging_efficiency=discharging_efficiency,
        expected_discharge_price=expected_discharge_price_base,
        reserve_for_discharge=reserve_for_discharge,
        max_cost_per_kwh=max_cost_per_kwh_base,
    )
    return candidates, filtered_by_level, economics_filter


def _build_charging_interval(
    interval: dict[str, Any],
    *,
    unit_factor: int,
    rating_lookup: dict[str, str | None],
) -> dict[str, Any]:
    response = build_response_interval(interval, unit_factor, rating_lookup)
    response["power_w"] = interval.get("power_w")
    response["grid_energy_kwh"] = interval.get("grid_energy_kwh")
    response["energy_kwh"] = interval.get("energy_kwh")
    response["stored_energy_kwh"] = interval.get("stored_energy_kwh")
    response["soc_after_kwh"] = interval.get("soc_after_kwh")
    if "soc_after_percent" in interval:
        response["soc_after_percent"] = interval["soc_after_percent"]
    return response


def _build_response_segments(
    scheduled_intervals: list[dict[str, Any]],
    *,
    unit_factor: int,
    rating_lookup: dict[str, str | None],
) -> list[dict[str, Any]]:
    response_segments: list[dict[str, Any]] = []
    for segment in group_intervals_into_segments(scheduled_intervals):
        seg_stats = calculate_window_statistics(
            segment["intervals"],
            unit_factor=unit_factor,
            round_decimals=4,
            power_profile=[int(interval["power_w"]) for interval in segment["intervals"]],
        )
        segment_end = _interval_start(segment["intervals"][-1]) + timedelta(minutes=INTERVAL_MINUTES)
        response_segments.append(
            {
                "start": segment["start"],
                "end": segment_end.isoformat(),
                "duration_minutes": segment["duration_minutes"],
                "interval_count": segment["interval_count"],
                "price_mean": seg_stats.get("price_mean"),
                "intervals": [
                    _build_charging_interval(interval, unit_factor=unit_factor, rating_lookup=rating_lookup)
                    for interval in segment["intervals"]
                ],
            }
        )
    return response_segments


def _build_battery_info(
    *,
    current_soc_kwh: float,
    target_soc_kwh: float,
    capacity_kwh: float | None,
    requested_energy_needed_kwh: float,
    charging_efficiency: float,
    achieved_soc_kwh: float,
    must_reach_soc_kwh: float | None,
) -> dict[str, Any]:
    info: dict[str, Any] = {
        "current_soc_kwh": round(current_soc_kwh, 4),
        "target_soc_kwh": round(target_soc_kwh, 4),
        "energy_needed_kwh": round(requested_energy_needed_kwh, 4),
        "charging_efficiency": charging_efficiency,
        "achieved_soc_kwh": round(achieved_soc_kwh, 4),
        "target_met": achieved_soc_kwh >= target_soc_kwh - 1e-6,
    }
    if must_reach_soc_kwh is not None:
        info["must_reach_soc_kwh"] = round(must_reach_soc_kwh, 4)
    if capacity_kwh is not None and capacity_kwh > 0:
        info["capacity_kwh"] = round(capacity_kwh, 4)
        info["current_soc_percent"] = round(current_soc_kwh / capacity_kwh * 100.0, 2)
        info["target_soc_percent"] = round(target_soc_kwh / capacity_kwh * 100.0, 2)
        info["achieved_soc_percent"] = round(achieved_soc_kwh / capacity_kwh * 100.0, 2)
        if must_reach_soc_kwh is not None:
            info["must_reach_soc_percent"] = round(must_reach_soc_kwh / capacity_kwh * 100.0, 2)
    return info


@dataclass(frozen=True)
class _PlanContext:
    """Inputs that stay constant across relaxation attempts."""

    price_info: list[dict[str, Any]]
    current_soc_kwh: float
    target_soc_kwh: float
    capacity_kwh: float | None
    must_reach_soc_kwh: float | None
    deadline: datetime | None
    charging_efficiency: float
    discharging_efficiency: float
    max_charge_power_w: int
    min_charge_power_w: int | None
    charge_power_steps_w: list[int] | None
    grid_import_limit_w: int | None
    min_charge_duration_minutes: int | None
    max_cycles_per_day: int | None
    smooth_outliers: bool
    expected_discharge_price_base: float | None
    reserve_for_discharge: bool
    max_cost_per_kwh_base: float | None
    unit_factor: int

    @property
    def economic_filter_active(self) -> bool:
        """Whether any economic filter param was supplied by the user."""
        return (
            self.expected_discharge_price_base is not None
            or self.max_cost_per_kwh_base is not None
            or self.reserve_for_discharge
        )


def _classify_empty_candidates(
    ctx: _PlanContext,
    filtered_by_level: list[dict[str, Any]],
    economics_filter: dict[str, Any],
    *,
    max_price_level: str | None,
    min_price_level: str | None,
) -> str:
    """Return a stable reason code when no candidate intervals remain."""
    level_filter_active = min_price_level is not None or max_price_level is not None
    if not ctx.price_info:
        return "no_data_in_range"
    if level_filter_active and not filtered_by_level:
        return "no_intervals_matching_level_filter"
    if economics_filter.get("filtered_out_by_cost") or economics_filter.get("filtered_out_by_profitability"):
        return "no_intervals_after_economic_filter"
    return "energy_unreachable"


def _build_raw_schedule(
    ctx: _PlanContext,
    candidates: list[dict[str, Any]],
    effective_energy_needed_grid_kwh: float,
) -> tuple[dict[str, Any] | None, str]:
    """Run the deadline-aware or single-pass scheduler and return a schedule dict."""
    if ctx.deadline is not None and ctx.must_reach_soc_kwh is not None:
        energy_needed_by_deadline = min(
            effective_energy_needed_grid_kwh,
            calculate_energy_needed(ctx.current_soc_kwh, ctx.must_reach_soc_kwh, ctx.charging_efficiency),
        )
        schedule = build_deadline_schedule(
            candidates,
            total_energy_needed_grid_kwh=effective_energy_needed_grid_kwh,
            energy_needed_by_deadline_grid_kwh=energy_needed_by_deadline,
            deadline=ctx.deadline,
            max_charge_power_w=ctx.max_charge_power_w,
            charging_efficiency=ctx.charging_efficiency,
            min_charge_power_w=ctx.min_charge_power_w,
            charge_power_steps_w=ctx.charge_power_steps_w,
            grid_import_limit_w=ctx.grid_import_limit_w,
            interval_minutes=INTERVAL_MINUTES,
        )
        if schedule["deadline_unallocated_grid_energy_kwh"] > 1e-6:
            return None, "energy_unreachable_by_deadline"
        return schedule, ""

    schedule = build_power_schedule(
        candidates,
        effective_energy_needed_grid_kwh,
        max_charge_power_w=ctx.max_charge_power_w,
        charging_efficiency=ctx.charging_efficiency,
        min_charge_power_w=ctx.min_charge_power_w,
        charge_power_steps_w=ctx.charge_power_steps_w,
        grid_import_limit_w=ctx.grid_import_limit_w,
        interval_minutes=INTERVAL_MINUTES,
    )
    return schedule, ""


def _selection_passes_distance_check(
    ctx: _PlanContext,
    scheduled_intervals: list[dict[str, Any]],
    min_distance_from_avg: float | None,
) -> bool:
    """Return True if the selection meets min_distance_from_avg (or the check is disabled)."""
    if min_distance_from_avg is None or not scheduled_intervals:
        return True
    range_avg = calculate_search_range_avg(ctx.price_info)
    if range_avg is None:
        return True
    selection_mean = sum(float(interval["total"]) for interval in scheduled_intervals) / len(scheduled_intervals)
    return check_min_distance_from_avg(selection_mean, range_avg, min_distance_from_avg, reverse=False)


def _build_deadline_info(
    ctx: _PlanContext,
    scheduled_intervals: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Compute deadline adherence by splitting the constrained intervals at the deadline."""
    if ctx.deadline is None or ctx.must_reach_soc_kwh is None:
        return None
    pre_stored_kwh = sum(
        float(interval.get("stored_energy_kwh", 0.0))
        for interval in scheduled_intervals
        if _interval_start(interval) < ctx.deadline
    )
    achieved_by_deadline = ctx.current_soc_kwh + pre_stored_kwh
    return {
        "must_reach_by": ctx.deadline.isoformat(),
        "must_reach_soc_kwh": round(ctx.must_reach_soc_kwh, 4),
        "achieved_soc_kwh": round(achieved_by_deadline, 4),
        "deadline_met": achieved_by_deadline >= ctx.must_reach_soc_kwh - 1e-6,
    }


def _attempt_plan(
    ctx: _PlanContext,
    *,
    effective_energy_needed_grid_kwh: float,
    max_price_level: str | None,
    min_price_level: str | None,
    min_distance_from_avg: float | None,
) -> tuple[dict[str, Any] | None, str]:
    """Run one scheduling attempt with the provided (possibly relaxed) filters."""
    candidates, filtered_by_level, economics_filter = _build_candidate_intervals(
        ctx.price_info,
        max_price_level=max_price_level,
        min_price_level=min_price_level,
        smooth_outliers=ctx.smooth_outliers,
        charging_efficiency=ctx.charging_efficiency,
        discharging_efficiency=ctx.discharging_efficiency,
        expected_discharge_price_base=ctx.expected_discharge_price_base,
        reserve_for_discharge=ctx.reserve_for_discharge,
        max_cost_per_kwh_base=ctx.max_cost_per_kwh_base,
    )

    if not candidates:
        reason = _classify_empty_candidates(
            ctx,
            filtered_by_level,
            economics_filter,
            max_price_level=max_price_level,
            min_price_level=min_price_level,
        )
        return None, reason

    schedule, reason = _build_raw_schedule(ctx, candidates, effective_energy_needed_grid_kwh)
    if schedule is None:
        return None, reason
    if schedule["unallocated_grid_energy_kwh"] > 1e-6:
        return None, "energy_unreachable"

    schedule, warnings = apply_segment_constraints(
        schedule,
        candidates,
        charging_efficiency=ctx.charging_efficiency,
        min_charge_duration_minutes=ctx.min_charge_duration_minutes,
        max_cycles_per_day=ctx.max_cycles_per_day,
        interval_minutes=INTERVAL_MINUTES,
    )
    scheduled_intervals = build_soc_progression_from_schedule(
        schedule["intervals"], ctx.current_soc_kwh, ctx.capacity_kwh
    )

    if not _selection_passes_distance_check(ctx, scheduled_intervals, min_distance_from_avg):
        return None, "selection_above_distance_threshold"

    economics = calculate_plan_economics(
        scheduled_intervals,
        charging_efficiency=ctx.charging_efficiency,
        discharging_efficiency=ctx.discharging_efficiency,
        expected_discharge_price=ctx.expected_discharge_price_base,
        unit_factor=ctx.unit_factor,
        max_cost_per_kwh=ctx.max_cost_per_kwh_base,
        reserve_for_discharge=ctx.reserve_for_discharge,
    )

    return (
        {
            "schedule": schedule,
            "scheduled_intervals": scheduled_intervals,
            "achieved_soc_kwh": ctx.current_soc_kwh + schedule["total_stored_energy_kwh"],
            "deadline": _build_deadline_info(ctx, scheduled_intervals),
            "economics": economics,
            "warnings": warnings,
            "economics_filter": economics_filter if ctx.economic_filter_active else None,
        },
        "",
    )


async def handle_plan_charging(call: ServiceCall) -> ServiceResponse:
    """Handle the plan_charging service call."""
    hass: HomeAssistant = call.hass
    data, resolved_refs = resolve_entity_references(hass, call.data, _CHARGING_ENTITY_PARAMS)

    validated = _validate_soc_inputs(data)
    capacity_kwh = validated["capacity_kwh"]
    current_soc_value = validated["current_soc_kwh"]
    target_soc_value = validated["target_soc_kwh"]
    if current_soc_value is None or target_soc_value is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="missing_current_soc" if current_soc_value is None else "missing_target_soc",
        )

    current_soc_kwh = float(current_soc_value)
    target_soc_kwh = float(target_soc_value)
    must_reach_soc_value = validated["must_reach_soc_kwh"]
    must_reach_soc_kwh = float(must_reach_soc_value) if must_reach_soc_value is not None else None

    entry_id = data.get("entry_id", "")
    max_charge_power_w = int(data["max_charge_power_w"])
    min_charge_power_w = int(data["min_charge_power_w"]) if "min_charge_power_w" in data else None
    charge_power_steps_w = [int(step) for step in data.get("charge_power_steps_w", [])] or None
    grid_import_limit_w = int(data["grid_import_limit_w"]) if "grid_import_limit_w" in data else None
    charging_efficiency = float(data.get("charging_efficiency", 1.0))
    discharging_efficiency = float(data.get("discharging_efficiency", 1.0))
    use_base_unit = bool(data.get("use_base_unit", False))
    max_price_level = data.get("max_price_level")
    min_price_level = data.get("min_price_level")
    include_comparison_details = bool(data.get("include_comparison_details", False))
    smooth_outliers = bool(data.get("smooth_outliers", True))
    min_distance_from_avg = data.get("min_distance_from_avg")
    allow_relaxation = bool(data.get("allow_relaxation", True))
    duration_flexibility_minutes = data.get("duration_flexibility_minutes")
    reserve_for_discharge = bool(data.get("reserve_for_discharge", False))
    min_charge_duration_minutes = (
        int(data["min_charge_duration_minutes"]) if "min_charge_duration_minutes" in data else None
    )
    max_cycles_per_day = int(data["max_cycles_per_day"]) if "max_cycles_per_day" in data else None

    if current_soc_kwh >= target_soc_kwh - 1e-6:
        entry, _coordinator, _coordinator_data = get_entry_and_data(hass, entry_id)
        currency = entry.data.get("currency", "EUR")
        price_unit = f"{currency}/kWh" if use_base_unit else get_display_unit_string(entry, currency)
        response: dict[str, Any] = {
            "home_id": entry.data.get("home_id", ""),
            "intervals_found": False,
            "reason": "already_at_target",
            "battery": _build_battery_info(
                current_soc_kwh=current_soc_kwh,
                target_soc_kwh=target_soc_kwh,
                capacity_kwh=capacity_kwh,
                requested_energy_needed_kwh=0.0,
                charging_efficiency=charging_efficiency,
                achieved_soc_kwh=current_soc_kwh,
                must_reach_soc_kwh=must_reach_soc_kwh,
            ),
            "charging": None,
            "currency": currency,
            "price_unit": price_unit,
        }
        if resolved_refs:
            response["_resolved"] = resolved_refs
        return response

    requested_energy_needed_grid_kwh = calculate_energy_needed(current_soc_kwh, target_soc_kwh, charging_efficiency)

    entry, coordinator, coordinator_data = get_entry_and_data(hass, entry_id)
    rating_lookup = build_rating_lookup(coordinator_data)
    home_id = entry.data.get("home_id")
    if not home_id:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="missing_home_id",
        )

    validate_price_level_range(min_price_level, max_price_level)
    validate_search_params(data)
    home_timezone = resolve_home_timezone(coordinator, home_id)
    from zoneinfo import ZoneInfo  # noqa: PLC0415

    home_tz: ZoneInfo = ZoneInfo(home_timezone)
    effective_data, must_finish_by_dt = apply_must_finish_by(data, home_tz)
    now = dt_util.now().astimezone(home_tz)
    search_start, search_end = resolve_search_range(effective_data, now, home_tz)

    currency = entry.data.get("currency", "EUR")
    unit_factor = 1 if use_base_unit else get_display_unit_factor(entry)
    price_unit = f"{currency}/kWh" if use_base_unit else get_display_unit_string(entry, currency)
    expected_discharge_price_base = (
        float(data["expected_discharge_price"]) / unit_factor if "expected_discharge_price" in data else None
    )
    max_cost_per_kwh_base = float(data["max_cost_per_kwh"]) / unit_factor if "max_cost_per_kwh" in data else None

    try:
        _mode, effective_max_power_w, _allowed_steps = determine_power_mode(
            max_charge_power_w=max_charge_power_w,
            min_charge_power_w=min_charge_power_w,
            charge_power_steps_w=charge_power_steps_w,
            grid_import_limit_w=grid_import_limit_w,
        )
    except ValueError as error:
        raise _translate_error_key(str(error)) from error

    max_interval_energy = energy_for_power(effective_max_power_w, INTERVAL_MINUTES)
    requested_intervals = max(1, int((requested_energy_needed_grid_kwh / max_interval_energy) + 0.999999))

    try:
        deadline, deadline_source = resolve_deadline(
            coordinator_data=coordinator_data,
            now=now,
            home_tz=home_tz,
            must_reach_by=data.get("must_reach_by"),
            must_reach_by_event=data.get("must_reach_by_event"),
        )
    except ValueError as error:
        raise _translate_error_key(str(error)) from error

    if deadline is not None and (deadline <= search_start or deadline > search_end):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="deadline_outside_search_range",
        )

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
        _LOGGER.exception("Error fetching price data for %s", PLAN_CHARGING_SERVICE_NAME)
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="price_fetch_failed",
        ) from error

    plan_ctx = _PlanContext(
        price_info=price_info,
        current_soc_kwh=current_soc_kwh,
        target_soc_kwh=target_soc_kwh,
        capacity_kwh=capacity_kwh,
        must_reach_soc_kwh=must_reach_soc_kwh,
        deadline=deadline,
        charging_efficiency=charging_efficiency,
        discharging_efficiency=discharging_efficiency,
        max_charge_power_w=max_charge_power_w,
        min_charge_power_w=min_charge_power_w,
        charge_power_steps_w=charge_power_steps_w,
        grid_import_limit_w=grid_import_limit_w,
        min_charge_duration_minutes=min_charge_duration_minutes,
        max_cycles_per_day=max_cycles_per_day,
        smooth_outliers=smooth_outliers,
        expected_discharge_price_base=expected_discharge_price_base,
        reserve_for_discharge=reserve_for_discharge,
        max_cost_per_kwh_base=max_cost_per_kwh_base,
        unit_factor=unit_factor,
    )

    planning_result, reason = _attempt_plan(
        plan_ctx,
        effective_energy_needed_grid_kwh=requested_energy_needed_grid_kwh,
        max_price_level=max_price_level,
        min_price_level=min_price_level,
        min_distance_from_avg=min_distance_from_avg,
    )

    relaxation_applied = False
    relaxation_steps = 0
    warnings: list[str] = []

    if planning_result is None and allow_relaxation:
        max_reduction = calculate_max_duration_reduction_intervals(requested_intervals, duration_flexibility_minutes)
        steps = generate_relaxation_steps(
            min_distance_from_avg=min_distance_from_avg,
            max_price_level=max_price_level,
            min_price_level=min_price_level,
            total_intervals=requested_intervals,
            min_duration_intervals=max(MIN_RELAXED_DURATION_INTERVALS, 1),
            max_duration_reduction_intervals=max_reduction,
            reverse=False,
        )
        for step in steps:
            reduced_energy = max(
                calculate_energy_needed(current_soc_kwh, must_reach_soc_kwh, charging_efficiency)
                if must_reach_soc_kwh is not None
                else 0.0,
                requested_energy_needed_grid_kwh - (step.duration_reduction * max_interval_energy),
            )
            attempt, reason = _attempt_plan(
                plan_ctx,
                effective_energy_needed_grid_kwh=reduced_energy,
                max_price_level=step.max_price_level,
                min_price_level=step.min_price_level,
                min_distance_from_avg=step.min_distance_from_avg,
            )
            if attempt is not None:
                planning_result = attempt
                relaxation_applied = True
                relaxation_steps = step.step_number
                warnings.append("target_reduced_by_relaxation")
                break

    if planning_result is None:
        response: dict[str, Any] = {
            "home_id": home_id,
            "search_start": search_start.isoformat(),
            "search_end": search_end.isoformat(),
            "must_finish_by": must_finish_by_dt.isoformat() if must_finish_by_dt else None,
            "intervals_found": False,
            "reason": reason,
            "battery": _build_battery_info(
                current_soc_kwh=current_soc_kwh,
                target_soc_kwh=target_soc_kwh,
                capacity_kwh=capacity_kwh,
                requested_energy_needed_kwh=requested_energy_needed_grid_kwh,
                charging_efficiency=charging_efficiency,
                achieved_soc_kwh=current_soc_kwh,
                must_reach_soc_kwh=must_reach_soc_kwh,
            ),
            "charging": None,
            "deadline": {"must_reach_by": deadline.isoformat(), "source": deadline_source} if deadline else None,
            "economics": None,
            "currency": currency,
            "price_unit": price_unit,
            "relaxation_applied": relaxation_applied,
        }
        if relaxation_applied:
            response["relaxation_steps"] = relaxation_steps
        if resolved_refs:
            response["_resolved"] = resolved_refs
        return response

    scheduled_intervals = planning_result["scheduled_intervals"]
    schedule_data = planning_result["schedule"]
    warnings.extend(planning_result.get("warnings", []))
    achieved_soc_kwh = float(planning_result["achieved_soc_kwh"])

    response_intervals = [
        _build_charging_interval(interval, unit_factor=unit_factor, rating_lookup=rating_lookup)
        for interval in scheduled_intervals
    ]
    response_segments = _build_response_segments(
        scheduled_intervals,
        unit_factor=unit_factor,
        rating_lookup=rating_lookup,
    )
    power_profile = [int(interval["power_w"]) for interval in scheduled_intervals]
    stats = calculate_window_statistics(
        scheduled_intervals,
        unit_factor=unit_factor,
        round_decimals=4,
        power_profile=power_profile,
    )
    total_cost_base = sum(
        float(interval["total"]) * float(interval["grid_energy_kwh"]) for interval in scheduled_intervals
    )
    avg_price_per_kwh_base = (
        total_cost_base / schedule_data["total_grid_energy_kwh"] if schedule_data["total_grid_energy_kwh"] > 0 else 0.0
    )

    comparison_result = find_cheapest_n_intervals(price_info, len(scheduled_intervals), 1, reverse=True)
    price_comparison: dict[str, Any] = {}
    if comparison_result is not None:
        comparison_stats = calculate_window_statistics(
            comparison_result["intervals"],
            unit_factor=unit_factor,
            round_decimals=4,
        )
        own_mean = stats.get("price_mean")
        comparison_mean = comparison_stats.get("price_mean")
        if own_mean is not None and comparison_mean is not None:
            price_comparison = {
                "comparison_price_mean": comparison_mean,
                "price_difference": abs(round(float(comparison_mean) - float(own_mean), 4)),
            }
            if include_comparison_details:
                price_comparison["comparison_price_min"] = comparison_stats.get("price_min")
                price_comparison["comparison_price_max"] = comparison_stats.get("price_max")

    seconds_until_start = None
    seconds_until_end = None
    if response_segments:
        first_dt = datetime.fromisoformat(response_segments[0]["start"])
        last_dt = datetime.fromisoformat(response_segments[-1]["end"])
        seconds_until_start = max(0, int((first_dt - now).total_seconds()))
        seconds_until_end = max(0, int((last_dt - now).total_seconds()))

    battery_info = _build_battery_info(
        current_soc_kwh=current_soc_kwh,
        target_soc_kwh=target_soc_kwh,
        capacity_kwh=capacity_kwh,
        requested_energy_needed_kwh=requested_energy_needed_grid_kwh,
        charging_efficiency=charging_efficiency,
        achieved_soc_kwh=achieved_soc_kwh,
        must_reach_soc_kwh=must_reach_soc_kwh,
    )
    if relaxation_applied and achieved_soc_kwh < target_soc_kwh - 1e-6:
        battery_info["target_met"] = False

    deadline_info = planning_result.get("deadline")
    if deadline_info is not None:
        deadline_info = dict(deadline_info)
        deadline_info["source"] = deadline_source
        if capacity_kwh is not None and capacity_kwh > 0:
            deadline_info["achieved_soc_percent"] = round(deadline_info["achieved_soc_kwh"] / capacity_kwh * 100.0, 2)
            deadline_info["must_reach_soc_percent"] = round(
                deadline_info["must_reach_soc_kwh"] / capacity_kwh * 100.0, 2
            )

    response: dict[str, Any] = {
        "home_id": home_id,
        "search_start": search_start.isoformat(),
        "search_end": search_end.isoformat(),
        "must_finish_by": must_finish_by_dt.isoformat() if must_finish_by_dt else None,
        "intervals_found": True,
        "currency": currency,
        "price_unit": price_unit,
        "battery": battery_info,
        "charging": {
            "mode": schedule_data["mode"],
            "charge_power_w": max_charge_power_w,
            "min_charge_power_w": min_charge_power_w,
            "charge_power_steps_w": charge_power_steps_w,
            "grid_import_limit_w": grid_import_limit_w,
            "effective_max_charge_power_w": schedule_data["effective_max_power_w"],
            "total_duration_minutes": len(scheduled_intervals) * INTERVAL_MINUTES,
            "total_energy_kwh": round(schedule_data["total_grid_energy_kwh"], 6),
            "stored_energy_kwh": round(schedule_data["total_stored_energy_kwh"], 6),
            "total_cost": round(total_cost_base * unit_factor, 4),
            "avg_price_per_kwh": round(avg_price_per_kwh_base * unit_factor, 4),
            "schedule": {
                "segment_count": len(response_segments),
                "segments": response_segments,
                "intervals": response_intervals,
                "seconds_until_start": seconds_until_start,
                "seconds_until_end": seconds_until_end,
                **stats,
            },
        },
        "deadline": deadline_info,
        "economics": planning_result.get("economics"),
        "economics_filter": planning_result.get("economics_filter"),
        "price_comparison": price_comparison or None,
        "relaxation_applied": relaxation_applied,
        "warnings": warnings or None,
    }
    if relaxation_applied:
        response["relaxation_steps"] = relaxation_steps
    if resolved_refs:
        response["_resolved"] = resolved_refs
    return response
