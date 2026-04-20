"""Deadline helpers for the plan_charging service."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from custom_components.tibber_prices.services.helpers import localize_to_home_tz
from custom_components.tibber_prices.utils.price_window import group_intervals_into_segments

from .power_scheduler import build_power_schedule

if TYPE_CHECKING:
    from zoneinfo import ZoneInfo

_DEADLINE_EVENTS = frozenset({"next_peak_period", "next_best_period_end", "midnight"})


def get_deadline_events() -> frozenset[str]:
    """Return the supported deadline event selector values."""
    return _DEADLINE_EVENTS


def resolve_deadline(
    *,
    coordinator_data: dict[str, Any],
    now: datetime,
    home_tz: ZoneInfo,
    must_reach_by: datetime | None = None,
    must_reach_by_event: str | None = None,
) -> tuple[datetime | None, str | None]:
    """Resolve an absolute deadline from an explicit datetime or a known event."""
    if must_reach_by is not None and must_reach_by_event is not None:
        raise ValueError("deadline_conflict")

    if must_reach_by is not None:
        return localize_to_home_tz(must_reach_by, home_tz), "explicit"

    if must_reach_by_event is None:
        return None, None

    if must_reach_by_event not in _DEADLINE_EVENTS:
        raise ValueError("deadline_event_not_available")

    if must_reach_by_event == "midnight":
        next_day = (now + timedelta(days=1)).date()
        return datetime.combine(next_day, datetime.min.time(), tzinfo=home_tz), "midnight"

    periods_data = coordinator_data.get("pricePeriods", {})
    if must_reach_by_event == "next_peak_period":
        periods = periods_data.get("peak_price", {}).get("periods", [])
        for period in periods:
            start = period.get("start")
            if start and start > now:
                return start, "next_peak_period"
        raise ValueError("deadline_event_not_available")

    periods = periods_data.get("best_price", {}).get("periods", [])
    for period in periods:
        end = period.get("end")
        if end and end > now:
            return end, "next_best_period_end"
    raise ValueError("deadline_event_not_available")


def build_deadline_schedule(
    candidate_intervals: list[dict[str, Any]],
    *,
    total_energy_needed_grid_kwh: float,
    energy_needed_by_deadline_grid_kwh: float,
    deadline: datetime,
    max_charge_power_w: int,
    charging_efficiency: float,
    min_charge_power_w: int | None = None,
    charge_power_steps_w: list[int] | None = None,
    grid_import_limit_w: int | None = None,
    interval_minutes: int = 15,
) -> dict[str, Any]:
    """Build a two-pass schedule that satisfies a minimum SoC by a deadline."""
    deadline_intervals = [interval for interval in candidate_intervals if _interval_start(interval) < deadline]
    pre_deadline = build_power_schedule(
        deadline_intervals,
        energy_needed_by_deadline_grid_kwh,
        max_charge_power_w=max_charge_power_w,
        charging_efficiency=charging_efficiency,
        min_charge_power_w=min_charge_power_w,
        charge_power_steps_w=charge_power_steps_w,
        grid_import_limit_w=grid_import_limit_w,
        interval_minutes=interval_minutes,
    )

    used_timestamps = {interval["startsAt"] for interval in pre_deadline["intervals"]}
    remaining_candidates = [interval for interval in candidate_intervals if interval["startsAt"] not in used_timestamps]
    remaining_energy = max(0.0, total_energy_needed_grid_kwh - pre_deadline["total_grid_energy_kwh"])

    post_deadline = build_power_schedule(
        remaining_candidates,
        remaining_energy,
        max_charge_power_w=max_charge_power_w,
        charging_efficiency=charging_efficiency,
        min_charge_power_w=min_charge_power_w,
        charge_power_steps_w=charge_power_steps_w,
        grid_import_limit_w=grid_import_limit_w,
        interval_minutes=interval_minutes,
    )

    combined_intervals = sorted(
        [*pre_deadline["intervals"], *post_deadline["intervals"]],
        key=_interval_start,
    )

    return {
        "intervals": combined_intervals,
        "segments": group_intervals_into_segments(combined_intervals),
        "deadline": deadline,
        "pre_deadline": pre_deadline,
        "post_deadline": post_deadline,
        "total_grid_energy_kwh": round(
            pre_deadline["total_grid_energy_kwh"] + post_deadline["total_grid_energy_kwh"], 6
        ),
        "total_stored_energy_kwh": round(
            pre_deadline["total_stored_energy_kwh"] + post_deadline["total_stored_energy_kwh"], 6
        ),
        "unallocated_grid_energy_kwh": round(post_deadline["unallocated_grid_energy_kwh"], 6),
        "deadline_unallocated_grid_energy_kwh": round(pre_deadline["unallocated_grid_energy_kwh"], 6),
        "mode": pre_deadline["mode"],
        "effective_max_power_w": pre_deadline["effective_max_power_w"],
        "allowed_steps": pre_deadline["allowed_steps"],
        "minimum_power_w": pre_deadline["minimum_power_w"],
    }


def _interval_start(interval: dict[str, Any]) -> datetime:
    starts_at = interval["startsAt"]
    return datetime.fromisoformat(starts_at) if isinstance(starts_at, str) else starts_at
