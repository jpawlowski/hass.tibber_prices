"""
Service handler for plan_charging service.

This service creates a charging plan for energy storage devices
(EV, house battery, balcony battery) within a time window.

The algorithm:
1. Calculates required intervals based on energy target or duration
2. Finds optimal intervals (contiguous or split based on allow_split)
3. Merges adjacent intervals into slots
4. Optionally reduces last slot power for precise energy targeting

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
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

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

PLAN_CHARGING_SERVICE_NAME = "plan_charging"

# Schema for plan_charging service - FLAT structure
# Note: services.yaml sections are UI-only groupings, HA sends data flat
PLAN_CHARGING_SERVICE_SCHEMA = vol.Schema(
    {
        # General / entry_id (optional - auto-resolved if single entry)
        vol.Optional("entry_id"): cv.string,
        # Window section (UI grouping only)
        vol.Optional("start"): cv.string,
        vol.Optional("end"): cv.string,
        vol.Optional("horizon_hours", default=DEFAULT_HORIZON_HOURS): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=72)
        ),
        # Charge section (UI grouping only)
        vol.Exclusive("energy_target_kwh", "charge_mode"): vol.All(vol.Coerce(float), vol.Range(min=0.01, max=200)),
        vol.Exclusive("duration_minutes", "charge_mode"): vol.All(vol.Coerce(int), vol.Range(min=15, max=1440)),
        vol.Required("max_power_w"): vol.All(vol.Coerce(float), vol.Range(min=1, max=50000)),
        vol.Optional("min_power_w", default=0): vol.All(vol.Coerce(float), vol.Range(min=0, max=50000)),
        vol.Optional("allow_split", default=False): cv.boolean,
        vol.Optional("rounding", default="ceil"): vol.In(["nearest", "floor", "ceil"]),
        vol.Optional("efficiency", default=1.0): vol.All(vol.Coerce(float), vol.Range(min=0.01, max=1.0)),
        # PV section (UI grouping only) - reserved for future use
        vol.Optional("pv_entity_id"): cv.entity_id,
        # Preferences section (UI grouping only)
        vol.Optional("prefer_fewer_splits", default=True): cv.boolean,
        vol.Optional("prefer_earlier_completion", default=True): cv.boolean,
        vol.Optional("include_current_interval", default=True): cv.boolean,
    }
)


async def handle_plan_charging(  # noqa: PLR0912, PLR0915
    call: ServiceCall,
) -> ServiceResponse:
    """
    Handle plan_charging service call.

    Creates a charging plan for energy storage within a time window.

    Args:
        call: Service call with parameters

    Returns:
        Dict with charging plan including slots, energy, and cost details

    """
    hass: HomeAssistant = call.hass
    entry_id: str | None = call.data.get("entry_id")

    # Extract parameters (flat structure - HA sends all fields at top level)
    # Window parameters
    start = call.data.get("start")
    end = call.data.get("end")
    horizon_hours = call.data.get("horizon_hours", DEFAULT_HORIZON_HOURS)

    # Charge parameters
    energy_target_kwh = call.data.get("energy_target_kwh")
    duration_minutes = call.data.get("duration_minutes")
    max_power_w = call.data["max_power_w"]
    min_power_w = call.data.get("min_power_w", 0)
    allow_split = call.data.get("allow_split", False)
    rounding = call.data.get("rounding", "ceil")
    efficiency = call.data.get("efficiency", 1.0)

    # PV parameters (reserved for future use)
    _pv_entity_id = call.data.get("pv_entity_id")

    # Preferences
    _prefer_fewer_splits = call.data.get("prefer_fewer_splits", True)
    prefer_earlier = call.data.get("prefer_earlier_completion", True)
    include_current = call.data.get("include_current_interval", True)

    # Validate: exactly one of energy_target_kwh or duration_minutes must be set
    if energy_target_kwh is None and duration_minutes is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_parameters",
        )

    # Validate min_power <= max_power
    if min_power_w > max_power_w:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_parameters",
        )

    # Validate and get entry data (auto-resolves entry_id if single entry)
    entry, _coordinator, data = get_entry_and_data(hass, entry_id)
    resolved_entry_id = entry.entry_id  # Use resolved entry_id

    # Get currency from coordinator data
    currency = data.get("currency", "EUR")

    # Get currency display settings from config
    display_factor = get_display_unit_factor(entry)
    price_unit = get_display_unit_string(entry, currency)

    # Calculate duration if energy target provided
    if energy_target_kwh is not None:
        # Calculate needed charge energy (accounting for efficiency)
        needed_charge_kwh = energy_target_kwh / efficiency
        # Energy per interval at max power
        interval_kwh = (max_power_w / 1000) * (RESOLUTION_MINUTES / 60)
        # Intervals needed
        intervals_needed = calculate_intervals_needed(
            int((needed_charge_kwh / interval_kwh) * RESOLUTION_MINUTES),
            rounding,
        )
        # Recalculate duration from intervals
        effective_duration_minutes = intervals_needed * RESOLUTION_MINUTES
    else:
        # Type guard: We already validated that at least one of energy_target_kwh or duration_minutes is set
        # This assert satisfies the type checker
        assert duration_minutes is not None  # noqa: S101
        intervals_needed = calculate_intervals_needed(duration_minutes, rounding)
        effective_duration_minutes = duration_minutes
        needed_charge_kwh = None

    # Parse window
    parsed_window = parse_window(
        hass,
        start,
        end,
        horizon_hours=horizon_hours,
        duration_minutes=effective_duration_minutes,
    )

    # Create response envelope
    response = create_response_envelope(
        service_name=f"{DOMAIN}.{PLAN_CHARGING_SERVICE_NAME}",
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

    # Check if we have enough intervals
    if len(window_intervals) < intervals_needed:
        response.warnings.append("some_prices_missing_used_partial_window")
        # Adjust intervals_needed to what's available
        intervals_needed = len(window_intervals)

    # Get PV power if entity provided
    pv_power_w = 0.0
    pv_source = "none"
    if _pv_entity_id:
        pv_state = hass.states.get(_pv_entity_id)
        if pv_state and pv_state.state not in ("unknown", "unavailable"):
            try:
                pv_power_w = float(pv_state.state)
                pv_source = _pv_entity_id
            except (ValueError, TypeError):
                response.warnings.append("pv_entity_unavailable_used_zero")
        else:
            response.warnings.append("pv_entity_unavailable_used_zero")

    # Select intervals based on allow_split
    if allow_split:
        selected_intervals = _select_cheapest_intervals(
            window_intervals, intervals_needed, prefer_earlier=prefer_earlier
        )
    else:
        selected_intervals = _find_best_contiguous_block(
            window_intervals, intervals_needed, prefer_earlier=prefer_earlier
        )

    if not selected_intervals:
        response.ok = False
        response.errors.append("no_price_data_available_in_window")
        return response.to_dict()

    # Merge adjacent intervals into slots
    slots = _merge_intervals_to_slots(
        selected_intervals,
        max_power_w,
        min_power_w,
        pv_power_w,
        energy_target_kwh,
        efficiency,
    )

    # Build result
    response.result = _build_result(
        slots=slots,
        selected_intervals=selected_intervals,
        energy_target_kwh=energy_target_kwh,
        _needed_charge_kwh=needed_charge_kwh,
        efficiency=efficiency,
        pv_source=pv_source,
        display_factor=display_factor,
        price_unit=price_unit,
    )

    return response.to_dict()


def _select_cheapest_intervals(
    intervals: list[dict[str, Any]],
    count: int,
    *,
    prefer_earlier: bool,
) -> list[dict[str, Any]]:
    """
    Select the N cheapest intervals (for allow_split=true).

    Args:
        intervals: Available intervals
        count: Number to select
        prefer_earlier: Prefer earlier intervals on tie

    Returns:
        Selected intervals sorted by time

    """

    # Sort by price, then by time for tie-breaking
    def sort_key(iv: dict[str, Any]) -> tuple[float, float]:
        price = iv.get("total", 0)
        starts_at = iv.get("startsAt", "")
        if isinstance(starts_at, str):
            try:
                ts = datetime.fromisoformat(starts_at).timestamp()
            except ValueError:
                ts = 0
        else:
            ts = starts_at.timestamp() if starts_at else 0
        return (price, ts if prefer_earlier else -ts)

    sorted_intervals = sorted(intervals, key=sort_key)
    selected = sorted_intervals[:count]

    # Re-sort by time for output
    def time_key(iv: dict[str, Any]) -> float:
        starts_at = iv.get("startsAt", "")
        if isinstance(starts_at, str):
            try:
                return datetime.fromisoformat(starts_at).timestamp()
            except ValueError:
                return 0
        return starts_at.timestamp() if starts_at else 0

    return sorted(selected, key=time_key)


def _find_best_contiguous_block(  # noqa: PLR0912
    intervals: list[dict[str, Any]],
    count: int,
    *,
    prefer_earlier: bool,
) -> list[dict[str, Any]]:
    """
    Find the best contiguous block of N intervals (for allow_split=false).

    Args:
        intervals: Available intervals (should be sorted by time)
        count: Number of contiguous intervals needed
        prefer_earlier: Prefer earlier block on tie

    Returns:
        Best contiguous block of intervals

    """
    if len(intervals) < count:
        return []

    # Sort intervals by time
    def time_key(iv: dict[str, Any]) -> float:
        starts_at = iv.get("startsAt", "")
        if isinstance(starts_at, str):
            try:
                return datetime.fromisoformat(starts_at).timestamp()
            except ValueError:
                return 0
        return starts_at.timestamp() if starts_at else 0

    sorted_intervals = sorted(intervals, key=time_key)

    # Find all contiguous blocks
    blocks: list[list[dict[str, Any]]] = []
    current_block: list[dict[str, Any]] = []

    for i, interval in enumerate(sorted_intervals):
        if not current_block:
            current_block = [interval]
        else:
            # Check if this interval is contiguous with previous
            prev_start = sorted_intervals[i - 1].get("startsAt", "")
            curr_start = interval.get("startsAt", "")

            prev_dt = datetime.fromisoformat(prev_start) if isinstance(prev_start, str) else prev_start
            curr_dt = datetime.fromisoformat(curr_start) if isinstance(curr_start, str) else curr_start

            expected_next = prev_dt + timedelta(minutes=RESOLUTION_MINUTES)

            if curr_dt == expected_next:
                current_block.append(interval)
            else:
                # Gap found, start new block
                if len(current_block) >= count:
                    blocks.append(current_block)
                current_block = [interval]

    # Don't forget the last block
    if len(current_block) >= count:
        blocks.append(current_block)

    if not blocks:
        return []

    # For each block, find the best sub-block of exactly 'count' intervals
    best_candidates: list[tuple[float, float, list[dict[str, Any]]]] = []

    for block in blocks:
        for i in range(len(block) - count + 1):
            sub_block = block[i : i + count]
            avg_price = sum(iv.get("total", 0) for iv in sub_block) / count

            # Get start time for tie-breaking
            first_start = sub_block[0].get("startsAt", "")
            if isinstance(first_start, str):
                try:
                    ts = datetime.fromisoformat(first_start).timestamp()
                except ValueError:
                    ts = 0
            else:
                ts = first_start.timestamp() if first_start else 0

            best_candidates.append((avg_price, ts if prefer_earlier else -ts, sub_block))

    # Sort by price, then by time
    best_candidates.sort(key=lambda x: (x[0], x[1]))

    return best_candidates[0][2] if best_candidates else []


def _merge_intervals_to_slots(  # noqa: PLR0913
    intervals: list[dict[str, Any]],
    max_power_w: float,
    min_power_w: float,
    pv_power_w: float,
    energy_target_kwh: float | None,
    efficiency: float,
) -> list[dict[str, Any]]:
    """
    Merge adjacent intervals into charging slots.

    Args:
        intervals: Selected intervals (sorted by time)
        max_power_w: Maximum charging power
        min_power_w: Minimum charging power
        pv_power_w: Current PV power
        energy_target_kwh: Target energy (if set)
        efficiency: Charging efficiency

    Returns:
        List of slots with merged intervals

    """
    if not intervals:
        return []

    slots: list[dict[str, Any]] = []
    current_slot_intervals: list[dict[str, Any]] = []

    for _i, interval in enumerate(intervals):
        if not current_slot_intervals:
            current_slot_intervals = [interval]
        else:
            # Check if contiguous
            prev_start = current_slot_intervals[-1].get("startsAt", "")
            curr_start = interval.get("startsAt", "")

            prev_dt = datetime.fromisoformat(prev_start) if isinstance(prev_start, str) else prev_start
            curr_dt = datetime.fromisoformat(curr_start) if isinstance(curr_start, str) else curr_start

            expected_next = prev_dt + timedelta(minutes=RESOLUTION_MINUTES)

            if curr_dt == expected_next:
                current_slot_intervals.append(interval)
            else:
                # Gap found, finalize current slot
                slots.append(_create_slot(current_slot_intervals, max_power_w, pv_power_w))
                current_slot_intervals = [interval]

    # Finalize last slot
    if current_slot_intervals:
        slots.append(_create_slot(current_slot_intervals, max_power_w, pv_power_w))

    # Adjust last slot power for energy target if needed
    if energy_target_kwh is not None and slots:
        _adjust_last_slot_power(slots, energy_target_kwh, efficiency, max_power_w, min_power_w)

    return slots


def _create_slot(
    intervals: list[dict[str, Any]],
    power_w: float,
    pv_power_w: float,
) -> dict[str, Any]:
    """Create a slot from a list of contiguous intervals."""
    first_start = intervals[0].get("startsAt", "")
    last_start = intervals[-1].get("startsAt", "")

    # Calculate end time (last interval start + 15 min)
    last_dt = datetime.fromisoformat(last_start) if isinstance(last_start, str) else last_start
    end_dt = last_dt + timedelta(minutes=RESOLUTION_MINUTES)

    # Calculate average price (raw, in base currency)
    prices = [iv.get("total", 0) for iv in intervals]
    avg_price = sum(prices) / len(prices) if prices else 0

    # Calculate expected grid power (reduced by PV)
    expected_grid_w = max(power_w - pv_power_w, 0)

    return {
        "start": first_start if isinstance(first_start, str) else first_start.isoformat(),
        "end": end_dt.isoformat(),
        "duration_minutes": len(intervals) * RESOLUTION_MINUTES,
        "intervals": len(intervals),
        "target_power_w": power_w,
        "expected_pv_w": pv_power_w,
        "expected_grid_w": expected_grid_w,
        "_avg_price": avg_price,  # Raw price for later formatting
        "_interval_prices": prices,  # Keep for calculations, remove later
    }


def _adjust_last_slot_power(
    slots: list[dict[str, Any]],
    energy_target_kwh: float,
    efficiency: float,
    max_power_w: float,
    min_power_w: float,
) -> None:
    """Adjust last slot power to achieve precise energy target."""
    # Calculate total energy from all slots except last
    total_energy = 0
    for slot in slots[:-1]:
        slot_hours = slot["duration_minutes"] / 60
        slot_energy = (slot["target_power_w"] / 1000) * slot_hours * efficiency
        total_energy += slot_energy

    # Calculate remaining energy needed
    remaining_kwh = energy_target_kwh - total_energy

    if remaining_kwh <= 0:
        # Already have enough, remove last slot
        slots.pop()
        return

    # Calculate needed power for last slot
    last_slot = slots[-1]
    last_slot_hours = last_slot["duration_minutes"] / 60

    # Account for efficiency: needed_charge = remaining / efficiency
    needed_charge_kwh = remaining_kwh / efficiency
    needed_power_w = (needed_charge_kwh / last_slot_hours) * 1000

    # Clamp to min/max
    adjusted_power = max(min_power_w, min(max_power_w, needed_power_w))

    # Update last slot
    last_slot["target_power_w"] = round(adjusted_power, 0)
    last_slot["expected_grid_w"] = max(adjusted_power - last_slot["expected_pv_w"], 0)


def _build_result(  # noqa: PLR0913
    slots: list[dict[str, Any]],
    selected_intervals: list[dict[str, Any]],
    energy_target_kwh: float | None,
    _needed_charge_kwh: float | None,  # Reserved for future use
    efficiency: float,
    pv_source: str,
    display_factor: int,
    price_unit: str,
) -> dict[str, Any]:
    """Build the result dictionary."""
    # Clean up slots (remove internal fields) and add formatted prices
    clean_slots = []
    for slot in slots:
        clean_slot = {k: v for k, v in slot.items() if not k.startswith("_")}
        # Add formatted avg_price
        avg_price = slot.get("_avg_price", 0)
        clean_slot["avg_price_per_kwh"] = round(avg_price * display_factor, 4)
        clean_slots.append(clean_slot)

    # Calculate totals
    total_charge_kwh = 0
    total_grid_kwh = 0
    total_cost = 0
    all_prices = []

    for slot in slots:
        slot_hours = slot["duration_minutes"] / 60
        slot_charge_kwh = (slot["target_power_w"] / 1000) * slot_hours
        slot_grid_kwh = (slot["expected_grid_w"] / 1000) * slot_hours

        total_charge_kwh += slot_charge_kwh
        total_grid_kwh += slot_grid_kwh

        # Calculate cost per interval in this slot
        interval_prices = slot.get("_interval_prices", [])
        interval_hours = RESOLUTION_MINUTES / 60
        interval_kwh = (slot["expected_grid_w"] / 1000) * interval_hours

        for price in interval_prices:
            total_cost += interval_kwh * price
            all_prices.append(price)

    # Calculate average and worst price
    avg_price = sum(all_prices) / len(all_prices) if all_prices else 0
    worst_price = max(all_prices) if all_prices else 0

    # Determine next slot start
    next_slot_start = clean_slots[0]["start"] if clean_slots else None

    result: dict[str, Any] = {
        "plan": {
            "mode": "CHARGE",
            "slots": clean_slots,
            "total_slots": len(clean_slots),
            "next_slot_start": next_slot_start,
        },
        "price_unit": price_unit,
        "energy": {
            "target_kwh": energy_target_kwh,
            "expected_charge_kwh": round(total_charge_kwh, 4),
            "expected_grid_kwh": round(total_grid_kwh, 4),
            "efficiency_applied": efficiency,
        },
        "cost": {
            "expected_cost": round(total_cost * display_factor, 4),
            "avg_price_per_kwh": round(avg_price * display_factor, 4),
            "worst_price_per_kwh": round(worst_price * display_factor, 4),
        },
        "debug": {
            "intervals_selected": len(selected_intervals),
            "missing_price_intervals": 0,
            "split_count": len(clean_slots),
            "pv_source": pv_source,
        },
    }

    return result
