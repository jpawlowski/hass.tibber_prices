"""Power allocation helpers for the plan_charging service."""

from __future__ import annotations

from datetime import datetime, timedelta
from itertools import pairwise
import math
from typing import Any

from custom_components.tibber_prices.utils.price_window import group_intervals_into_segments

_INTERVAL_TOLERANCE = 1e-9


def determine_power_mode(
    *,
    max_charge_power_w: int,
    min_charge_power_w: int | None = None,
    charge_power_steps_w: list[int] | None = None,
    grid_import_limit_w: int | None = None,
) -> tuple[str, int, list[int] | None]:
    """Resolve the active power mode and effective power limits.

    Returns:
        Tuple of ``(mode, effective_max_power_w, allowed_steps)``.

    Raises:
        ValueError: If power settings are mutually exclusive or impossible.
    """
    if min_charge_power_w is not None and charge_power_steps_w:
        raise ValueError("power_strategy_conflict")

    effective_max_power_w = min(max_charge_power_w, grid_import_limit_w) if grid_import_limit_w else max_charge_power_w
    if effective_max_power_w <= 0:
        raise ValueError("grid_limit_too_low")

    if charge_power_steps_w:
        allowed_steps = sorted({int(step) for step in charge_power_steps_w if 0 < int(step) <= effective_max_power_w})
        if not allowed_steps:
            raise ValueError("grid_limit_too_low")
        return "stepped", effective_max_power_w, allowed_steps

    if min_charge_power_w is not None:
        if min_charge_power_w > effective_max_power_w:
            raise ValueError("grid_limit_too_low")
        return "continuous", effective_max_power_w, None

    return "fixed", effective_max_power_w, None


def energy_for_power(power_w: float, interval_minutes: int = 15) -> float:
    """Return grid energy in kWh for an interval at the given power."""
    return float(power_w) / 1000.0 * (interval_minutes / 60.0)


def minimum_operating_power_w(
    *,
    mode: str,
    effective_max_power_w: int,
    min_charge_power_w: int | None = None,
    allowed_steps: list[int] | None = None,
) -> int:
    """Return the minimum usable power for the selected power mode."""
    if mode == "continuous":
        return min_charge_power_w or effective_max_power_w
    if mode == "stepped":
        return min(allowed_steps or [effective_max_power_w])
    return effective_max_power_w


def _interval_start(interval: dict[str, Any]) -> datetime:
    starts_at = interval["startsAt"]
    return datetime.fromisoformat(starts_at) if isinstance(starts_at, str) else starts_at


def _sort_price(interval: dict[str, Any]) -> float:
    return float(interval.get("_sort_total", interval["total"]))


def _choose_power_for_remaining_energy(
    remaining_grid_energy_kwh: float,
    *,
    mode: str,
    effective_max_power_w: int,
    min_charge_power_w: int | None,
    allowed_steps: list[int] | None,
    interval_minutes: int,
) -> int:
    """Choose the power assignment for the next interval."""
    max_interval_energy = energy_for_power(effective_max_power_w, interval_minutes)
    if remaining_grid_energy_kwh > max_interval_energy + _INTERVAL_TOLERANCE:
        return effective_max_power_w

    if mode == "continuous":
        interval_hours = interval_minutes / 60.0
        exact_power = math.ceil(remaining_grid_energy_kwh / interval_hours * 1000.0)
        if min_charge_power_w is not None:
            return max(min_charge_power_w, min(exact_power, effective_max_power_w))
        return min(exact_power, effective_max_power_w)

    if mode == "stepped":
        needed_power = remaining_grid_energy_kwh / (interval_minutes / 60.0) * 1000.0
        for step in allowed_steps or []:
            if step >= needed_power - _INTERVAL_TOLERANCE:
                return step
        return (allowed_steps or [effective_max_power_w])[-1]

    return effective_max_power_w


def _build_assignment(
    interval: dict[str, Any],
    *,
    power_w: int,
    charging_efficiency: float,
    interval_minutes: int,
) -> dict[str, Any]:
    """Attach charging assignment fields to an interval."""
    grid_energy_kwh = round(energy_for_power(power_w, interval_minutes), 6)
    stored_energy_kwh = round(grid_energy_kwh * charging_efficiency, 6)

    assigned = dict(interval)
    assigned["power_w"] = power_w
    assigned["grid_energy_kwh"] = grid_energy_kwh
    assigned["stored_energy_kwh"] = stored_energy_kwh
    return assigned


def build_power_schedule(
    candidate_intervals: list[dict[str, Any]],
    energy_needed_grid_kwh: float,
    *,
    max_charge_power_w: int,
    charging_efficiency: float,
    min_charge_power_w: int | None = None,
    charge_power_steps_w: list[int] | None = None,
    grid_import_limit_w: int | None = None,
    interval_minutes: int = 15,
) -> dict[str, Any]:
    """Allocate required grid energy across the cheapest candidate intervals."""
    mode, effective_max_power_w, allowed_steps = determine_power_mode(
        max_charge_power_w=max_charge_power_w,
        min_charge_power_w=min_charge_power_w,
        charge_power_steps_w=charge_power_steps_w,
        grid_import_limit_w=grid_import_limit_w,
    )

    sorted_candidates = sorted(
        candidate_intervals, key=lambda interval: (_sort_price(interval), _interval_start(interval))
    )

    assignments: list[dict[str, Any]] = []
    remaining_grid_energy_kwh = max(0.0, energy_needed_grid_kwh)

    for interval in sorted_candidates:
        if remaining_grid_energy_kwh <= _INTERVAL_TOLERANCE:
            break

        power_w = _choose_power_for_remaining_energy(
            remaining_grid_energy_kwh,
            mode=mode,
            effective_max_power_w=effective_max_power_w,
            min_charge_power_w=min_charge_power_w,
            allowed_steps=allowed_steps,
            interval_minutes=interval_minutes,
        )
        assignment = _build_assignment(
            interval,
            power_w=power_w,
            charging_efficiency=charging_efficiency,
            interval_minutes=interval_minutes,
        )
        assignments.append(assignment)
        remaining_grid_energy_kwh = max(0.0, remaining_grid_energy_kwh - assignment["grid_energy_kwh"])

    assignments.sort(key=_interval_start)
    segments = group_intervals_into_segments(assignments)

    total_grid_energy_kwh = round(sum(interval["grid_energy_kwh"] for interval in assignments), 6)
    total_stored_energy_kwh = round(sum(interval["stored_energy_kwh"] for interval in assignments), 6)

    return {
        "mode": mode,
        "effective_max_power_w": effective_max_power_w,
        "allowed_steps": allowed_steps,
        "intervals": assignments,
        "segments": segments,
        "total_grid_energy_kwh": total_grid_energy_kwh,
        "total_stored_energy_kwh": total_stored_energy_kwh,
        "unallocated_grid_energy_kwh": round(remaining_grid_energy_kwh, 6),
        "minimum_power_w": minimum_operating_power_w(
            mode=mode,
            effective_max_power_w=effective_max_power_w,
            min_charge_power_w=min_charge_power_w,
            allowed_steps=allowed_steps,
        ),
    }


def _add_interval_if_available(
    selected_map: dict[str, dict[str, Any]],
    candidate_map: dict[str, dict[str, Any]],
    starts_at: str,
    *,
    power_w: int,
    charging_efficiency: float,
    interval_minutes: int,
) -> bool:
    """Add a candidate interval to the selection map if it is available."""
    if starts_at in selected_map or starts_at not in candidate_map:
        return False
    selected_map[starts_at] = _build_assignment(
        candidate_map[starts_at],
        power_w=power_w,
        charging_efficiency=charging_efficiency,
        interval_minutes=interval_minutes,
    )
    return True


def apply_segment_constraints(
    schedule: dict[str, Any],
    candidate_intervals: list[dict[str, Any]],
    *,
    charging_efficiency: float,
    min_charge_duration_minutes: int | None = None,
    max_cycles_per_day: int | None = None,
    interval_minutes: int = 15,
) -> tuple[dict[str, Any], list[str]]:
    """Extend/bridge selected intervals to satisfy segment duration and cycle constraints."""
    warnings: list[str] = []
    selected_map = {interval["startsAt"]: dict(interval) for interval in schedule["intervals"]}
    candidate_map = {interval["startsAt"]: interval for interval in candidate_intervals}
    candidates_sorted = sorted(candidate_intervals, key=_interval_start)
    candidate_index = {interval["startsAt"]: index for index, interval in enumerate(candidates_sorted)}
    minimum_power_w = int(schedule["minimum_power_w"])

    if min_charge_duration_minutes:
        required_intervals = max(1, math.ceil(min_charge_duration_minutes / interval_minutes))
        progress = True
        while progress:
            progress = False
            selected_intervals = sorted(selected_map.values(), key=_interval_start)
            segments = group_intervals_into_segments(selected_intervals)
            for segment in segments:
                if segment["interval_count"] >= required_intervals:
                    continue
                while segment["interval_count"] < required_intervals:
                    first = segment["intervals"][0]["startsAt"]
                    last = segment["intervals"][-1]["startsAt"]
                    first_index = candidate_index[first]
                    last_index = candidate_index[last]

                    prev_interval = candidates_sorted[first_index - 1] if first_index > 0 else None
                    next_interval = (
                        candidates_sorted[last_index + 1] if last_index + 1 < len(candidates_sorted) else None
                    )

                    prev_contiguous = False
                    next_contiguous = False
                    if prev_interval is not None:
                        prev_contiguous = _interval_start(candidate_map[first]) - _interval_start(
                            prev_interval
                        ) == timedelta(minutes=interval_minutes)
                    if next_interval is not None:
                        next_contiguous = _interval_start(next_interval) - _interval_start(
                            candidate_map[last]
                        ) == timedelta(minutes=interval_minutes)

                    options: list[dict[str, Any]] = []
                    if prev_interval is not None and prev_contiguous and prev_interval["startsAt"] not in selected_map:
                        options.append(prev_interval)
                    if next_interval is not None and next_contiguous and next_interval["startsAt"] not in selected_map:
                        options.append(next_interval)
                    if not options:
                        warnings.append("min_charge_duration_unreachable")
                        break

                    cheapest = min(options, key=lambda interval: (_sort_price(interval), _interval_start(interval)))
                    added = _add_interval_if_available(
                        selected_map,
                        candidate_map,
                        cheapest["startsAt"],
                        power_w=minimum_power_w,
                        charging_efficiency=charging_efficiency,
                        interval_minutes=interval_minutes,
                    )
                    if not added:
                        break
                    progress = True
                    selected_intervals = sorted(selected_map.values(), key=_interval_start)
                    segment = next(
                        seg
                        for seg in group_intervals_into_segments(selected_intervals)
                        if first in {iv["startsAt"] for iv in seg["intervals"]}
                    )

    if max_cycles_per_day:
        while True:
            selected_intervals = sorted(selected_map.values(), key=_interval_start)
            segments = group_intervals_into_segments(selected_intervals)
            if len(segments) <= max_cycles_per_day:
                break

            best_gap: tuple[float, list[dict[str, Any]]] | None = None
            for left, right in pairwise(segments):
                left_end_index = candidate_index[left["intervals"][-1]["startsAt"]]
                right_start_index = candidate_index[right["intervals"][0]["startsAt"]]
                gap = candidates_sorted[left_end_index + 1 : right_start_index]
                if not gap:
                    continue
                if any(interval["startsAt"] in selected_map for interval in gap):
                    continue
                if any(
                    _interval_start(gap[index + 1]) - _interval_start(gap[index]) != timedelta(minutes=interval_minutes)
                    for index in range(len(gap) - 1)
                ):
                    continue
                penalty = sum(_sort_price(interval) for interval in gap)
                if best_gap is None or penalty < best_gap[0]:
                    best_gap = (penalty, gap)

            if best_gap is None:
                warnings.append("max_cycles_unreachable")
                break

            for interval in best_gap[1]:
                _add_interval_if_available(
                    selected_map,
                    candidate_map,
                    interval["startsAt"],
                    power_w=minimum_power_w,
                    charging_efficiency=charging_efficiency,
                    interval_minutes=interval_minutes,
                )

    selected_intervals = sorted(selected_map.values(), key=_interval_start)
    segments = group_intervals_into_segments(selected_intervals)
    schedule["intervals"] = selected_intervals
    schedule["segments"] = segments
    schedule["total_grid_energy_kwh"] = round(sum(interval["grid_energy_kwh"] for interval in selected_intervals), 6)
    schedule["total_stored_energy_kwh"] = round(
        sum(interval["stored_energy_kwh"] for interval in selected_intervals), 6
    )
    schedule["constraint_warnings"] = warnings
    return schedule, warnings
