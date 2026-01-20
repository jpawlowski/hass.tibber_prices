"""
Service handler for find_best_start service.

This service finds the optimal start time for run-once devices
(e.g., washing machine, dishwasher, dryer) within a time window.

The algorithm:
1. Generates all possible start times on 15-min boundaries
2. Scores each candidate by average price (or expected cost if energy estimate provided)
3. Returns the best candidate with lowest cost/price

"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from custom_components.tibber_prices.const import (
    DOMAIN,
    get_display_unit_factor,
    get_display_unit_string,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .common import (
    DEFAULT_HORIZON_HOURS,
    RESOLUTION_MINUTES,
    calculate_intervals_needed,
    create_response_envelope,
    get_intervals_in_window,
    parse_window,
    round_to_quarter,
)
from .helpers import get_entry_and_data

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse

_LOGGER = logging.getLogger(__name__)

FIND_BEST_START_SERVICE_NAME = "find_best_start"

# Schema for find_best_start service - FLAT structure
# Note: services.yaml sections are UI-only groupings, HA sends data flat
FIND_BEST_START_SERVICE_SCHEMA = vol.Schema(
    {
        # General / entry_id (optional - auto-resolved if single entry)
        vol.Optional("entry_id"): cv.string,
        # Window section (UI grouping only)
        vol.Optional("start"): cv.string,
        vol.Optional("end"): cv.string,
        vol.Optional("horizon_hours", default=DEFAULT_HORIZON_HOURS): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=72)
        ),
        # Job section (UI grouping only)
        vol.Required("duration_minutes"): vol.All(vol.Coerce(int), vol.Range(min=15, max=1440)),
        vol.Optional("rounding", default="ceil"): vol.In(["nearest", "floor", "ceil"]),
        # Costing section (UI grouping only)
        vol.Optional("estimate_energy_kwh"): vol.All(vol.Coerce(float), vol.Range(min=0.01, max=100)),
        vol.Optional("estimate_avg_power_w"): vol.All(vol.Coerce(float), vol.Range(min=1, max=50000)),
        # PV section (UI grouping only) - reserved for future use
        vol.Optional("pv_entity_id"): cv.entity_id,
        # Preferences section (UI grouping only)
        vol.Optional("prefer_earlier_start_on_tie", default=True): cv.boolean,
        vol.Optional("include_current_interval", default=True): cv.boolean,
    }
)


async def handle_find_best_start(  # noqa: PLR0915
    call: ServiceCall,
) -> ServiceResponse:
    """
    Handle find_best_start service call.

    Finds the optimal start time for a run-once device within a time window.

    Args:
        call: Service call with parameters

    Returns:
        Dict with recommended start time and scoring details

    """
    hass: HomeAssistant = call.hass
    entry_id: str | None = call.data.get("entry_id")

    # Extract parameters (flat structure - HA sends all fields at top level)
    # Window parameters
    start = call.data.get("start")
    end = call.data.get("end")
    horizon_hours = call.data.get("horizon_hours", DEFAULT_HORIZON_HOURS)

    # Job parameters
    duration_minutes = call.data["duration_minutes"]
    rounding = call.data.get("rounding", "ceil")

    # Costing parameters
    estimate_energy_kwh = call.data.get("estimate_energy_kwh")
    estimate_avg_power_w = call.data.get("estimate_avg_power_w")

    # PV parameters (reserved for future use)
    _pv_entity_id = call.data.get("pv_entity_id")

    # Preferences
    prefer_earlier = call.data.get("prefer_earlier_start_on_tie", True)
    include_current = call.data.get("include_current_interval", True)

    # Derive energy from power if only power provided
    if estimate_energy_kwh is None and estimate_avg_power_w is not None:
        duration_hours = duration_minutes / 60
        estimate_energy_kwh = (estimate_avg_power_w * duration_hours) / 1000

    # Validate and get entry data (auto-resolves entry_id if single entry)
    entry, _coordinator, data = get_entry_and_data(hass, entry_id)
    resolved_entry_id = entry.entry_id  # Use resolved entry_id

    # Get currency from coordinator data
    currency = data.get("currency", "EUR")

    # Get currency display settings from config
    display_factor = get_display_unit_factor(entry)
    price_unit = get_display_unit_string(entry, currency)

    # Parse window
    parsed_window = parse_window(
        hass,
        start,
        end,
        horizon_hours=horizon_hours,
        duration_minutes=duration_minutes,
    )

    # Create response envelope
    response = create_response_envelope(
        service_name=f"{DOMAIN}.{FIND_BEST_START_SERVICE_NAME}",
        entry_id=resolved_entry_id,
        currency=currency,
        window_start=parsed_window.start,
        window_end=parsed_window.end,
    )

    # Add any parsing warnings/errors
    response.warnings.extend(parsed_window.warnings)
    response.errors.extend(parsed_window.errors)

    # If there were parsing errors, return early
    if parsed_window.errors:
        response.ok = False
        return response.to_dict()

    # Round window to quarter boundaries
    # If include_current_interval is True, use floor to include the current interval
    # (e.g., 14:05 -> 14:00), otherwise ceil to start at next interval (14:05 -> 14:15)
    start_rounding = "floor" if include_current else "ceil"
    window_start = round_to_quarter(parsed_window.start, start_rounding)
    window_end = round_to_quarter(parsed_window.end, "floor")

    # Update response with rounded window
    response.window_start = window_start.isoformat()
    response.window_end = window_end.isoformat()

    # Get price intervals from coordinator
    all_intervals = data.get("priceInfo", [])
    if not all_intervals:
        response.ok = False
        response.errors.append("no_price_data_available_in_window")
        return response.to_dict()

    # Filter intervals to window
    window_intervals = get_intervals_in_window(all_intervals, window_start, window_end)

    if not window_intervals:
        response.ok = False
        response.errors.append("no_price_data_available_in_window")
        return response.to_dict()

    # Calculate number of intervals needed
    intervals_needed = calculate_intervals_needed(duration_minutes, rounding)

    # Get PV power if entity provided
    pv_power_w = 0.0
    if _pv_entity_id:
        pv_state = hass.states.get(_pv_entity_id)
        if pv_state and pv_state.state not in ("unknown", "unavailable"):
            try:
                pv_power_w = float(pv_state.state)
            except (ValueError, TypeError):
                response.warnings.append("pv_entity_unavailable_used_zero")
        else:
            response.warnings.append("pv_entity_unavailable_used_zero")

    # Generate and score candidates
    candidates = _generate_candidates(
        window_intervals=window_intervals,
        window_start=window_start,
        window_end=window_end,
        intervals_needed=intervals_needed,
        duration_minutes=duration_minutes,
        estimate_energy_kwh=estimate_energy_kwh,
        pv_power_w=pv_power_w,
    )

    if not candidates:
        response.ok = False
        response.errors.append("no_price_data_available_in_window")
        response.warnings.append("some_prices_missing_used_partial_window")
        return response.to_dict()

    # Sort and select best candidate (prefers future starts, closest to now if all past)
    now = dt_util.now()
    best_candidate = _select_best_candidate(candidates, prefer_earlier=prefer_earlier, now=now)

    # Warn if recommended start is in the past
    recommended_start: datetime = best_candidate["start"]
    if recommended_start < now:
        response.warnings.append("recommended_start_in_past")

    # Build result
    response.result = _build_result(
        candidate=best_candidate,
        total_candidates=len(candidates),
        duration_minutes=duration_minutes,
        display_factor=display_factor,
        price_unit=price_unit,
    )

    return response.to_dict()


def _generate_candidates(  # noqa: PLR0913
    window_intervals: list[dict[str, Any]],
    window_start: datetime,
    window_end: datetime,
    intervals_needed: int,
    duration_minutes: int,
    estimate_energy_kwh: float | None,
    pv_power_w: float,
) -> list[dict[str, Any]]:
    """
    Generate all possible start time candidates with scoring.

    Args:
        window_intervals: Available price intervals in window
        window_start: Start of window
        window_end: End of window
        intervals_needed: Number of 15-min intervals for the job
        duration_minutes: Job duration in minutes
        estimate_energy_kwh: Optional energy estimate for cost calculation
        pv_power_w: Current PV power in watts

    Returns:
        List of scored candidates

    """
    candidates = []

    # Build lookup for intervals by start time
    interval_lookup: dict[str, dict[str, Any]] = {}
    for interval in window_intervals:
        starts_at = interval.get("startsAt", "")
        if starts_at:
            # Normalize to ISO string for lookup
            key = starts_at.isoformat() if isinstance(starts_at, datetime) else starts_at
            interval_lookup[key] = interval

    # Generate candidates on 15-min boundaries
    current_start = window_start
    duration_delta = timedelta(minutes=duration_minutes)

    while current_start + duration_delta <= window_end:
        # Collect intervals for this candidate
        candidate_intervals = []
        slot_start = current_start

        for i in range(intervals_needed):
            slot_time = slot_start + timedelta(minutes=i * RESOLUTION_MINUTES)
            slot_key = slot_time.isoformat()

            # Also try without microseconds
            slot_key_no_micro = slot_time.replace(microsecond=0).isoformat()

            interval = interval_lookup.get(slot_key) or interval_lookup.get(slot_key_no_micro)

            if interval:
                candidate_intervals.append(interval)

        # Only consider candidates with all intervals available
        if len(candidate_intervals) == intervals_needed:
            # Calculate average price
            prices = [iv.get("total", 0) for iv in candidate_intervals]
            avg_price = sum(prices) / len(prices) if prices else 0

            # Calculate expected cost if energy estimate provided
            expected_cost = None
            expected_grid_kwh = None

            if estimate_energy_kwh is not None:
                # Distribute energy evenly across intervals
                energy_per_interval = estimate_energy_kwh / intervals_needed
                pv_kwh_per_interval = (pv_power_w / 1000) * (RESOLUTION_MINUTES / 60)

                total_grid_kwh = 0
                total_cost = 0

                for interval in candidate_intervals:
                    price = interval.get("total", 0)
                    grid_kwh = max(energy_per_interval - pv_kwh_per_interval, 0)
                    total_grid_kwh += grid_kwh
                    total_cost += grid_kwh * price

                expected_cost = total_cost
                expected_grid_kwh = total_grid_kwh

            candidate_end = current_start + duration_delta

            candidates.append(
                {
                    "start": current_start,
                    "end": candidate_end,
                    "intervals": candidate_intervals,
                    "avg_price": avg_price,
                    "expected_cost": expected_cost,
                    "expected_grid_kwh": expected_grid_kwh,
                    "expected_energy_kwh": estimate_energy_kwh,
                }
            )

        # Move to next 15-min slot
        current_start += timedelta(minutes=RESOLUTION_MINUTES)

    return candidates


def _select_best_candidate(
    candidates: list[dict[str, Any]],
    *,
    prefer_earlier: bool,
    now: datetime | None = None,
) -> dict[str, Any]:
    """
    Select the best candidate from scored list.

    Selection priority:
    1. Prefer candidates starting in the future over past candidates
    2. Among future candidates: lowest cost/price wins
    3. Among past candidates: closest to now wins (to minimize "too late" impact)
    4. Tie-breaker: earlier or later start based on prefer_earlier

    Args:
        candidates: List of scored candidates
        prefer_earlier: If True, earlier start wins ties
        now: Current time (defaults to dt_util.now())

    Returns:
        Best candidate

    """
    current_time = now if now is not None else dt_util.now()

    # Separate future and past candidates
    future_candidates = [c for c in candidates if c["start"] >= current_time]
    past_candidates = [c for c in candidates if c["start"] < current_time]

    # Sort by expected_cost (if available) or avg_price
    # Secondary sort by start time for tie-breaking
    def sort_key_by_price(c: dict[str, Any]) -> tuple[float, float]:
        cost = c.get("expected_cost")
        primary = cost if cost is not None else c["avg_price"]

        # Use timestamp for tie-breaking
        start: datetime = c["start"]
        secondary = start.timestamp() if prefer_earlier else -start.timestamp()
        return (primary, secondary)

    # If we have future candidates, pick best by price among them
    if future_candidates:
        sorted_candidates = sorted(future_candidates, key=sort_key_by_price)
        return sorted_candidates[0]

    # All candidates are in the past - pick the one closest to now
    # (minimizes how late the recommendation is)
    def sort_key_closest_to_now(c: dict[str, Any]) -> tuple[float, float]:
        start: datetime = c["start"]
        # Primary: distance from now (smaller = better, so closest to now wins)
        distance_from_now = abs((start - current_time).total_seconds())
        # Secondary: still prefer lower price for ties
        cost = c.get("expected_cost")
        price = cost if cost is not None else c["avg_price"]
        return (distance_from_now, price)

    sorted_past = sorted(past_candidates, key=sort_key_closest_to_now)
    return sorted_past[0]


def _build_result(
    candidate: dict[str, Any],
    total_candidates: int,
    duration_minutes: int,
    display_factor: int,
    price_unit: str,
) -> dict[str, Any]:
    """
    Build the result dictionary from best candidate.

    Args:
        candidate: Best candidate
        total_candidates: Total number of candidates considered
        duration_minutes: Job duration
        display_factor: Currency display factor (1 for base, 100 for subunit)
        price_unit: Currency unit string (e.g., 'ct/kWh' or '€/kWh')

    Returns:
        Result dictionary

    """
    start: datetime = candidate["start"]
    end: datetime = candidate["end"]
    avg_price = candidate["avg_price"]
    expected_cost = candidate.get("expected_cost")
    expected_grid_kwh = candidate.get("expected_grid_kwh")
    expected_energy_kwh = candidate.get("expected_energy_kwh")
    intervals = candidate["intervals"]

    # Build intervals list for response
    response_intervals = []
    for iv in intervals:
        price = iv.get("total", 0)
        response_intervals.append(
            {
                "start": iv.get("startsAt"),
                "end": _calculate_interval_end(iv.get("startsAt")),
                "price_per_kwh": round(price * display_factor, 4),
            }
        )

    result: dict[str, Any] = {
        "recommended_start": start.isoformat(),
        "recommended_end": end.isoformat(),
        "duration_minutes": duration_minutes,
        "price_unit": price_unit,
        "score": {
            "avg_price_per_kwh": round(avg_price * display_factor, 4),
            "rank": f"1/{total_candidates}",
            "tie_breaker": "earlier_start",
        },
        "intervals": response_intervals,
        "debug": {
            "candidates_considered": total_candidates,
            "missing_price_intervals": 0,
        },
    }

    # Add cost info if available
    if expected_cost is not None:
        result["cost"] = {
            "expected_energy_kwh": round(expected_energy_kwh, 4) if expected_energy_kwh else None,
            "expected_grid_energy_kwh": round(expected_grid_kwh, 4) if expected_grid_kwh else None,
            "expected_cost": round(expected_cost * display_factor, 4),
        }

    return result


def _calculate_interval_end(starts_at: str | None) -> str | None:
    """Calculate interval end time (start + 15 minutes)."""
    if not starts_at:
        return None
    try:
        start = datetime.fromisoformat(starts_at)
        end = start + timedelta(minutes=RESOLUTION_MINUTES)
        return end.isoformat()
    except (ValueError, TypeError):
        return None
