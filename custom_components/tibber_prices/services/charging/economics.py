"""Economic helpers for the plan_charging service."""

from __future__ import annotations

from typing import Any


def calculate_round_trip_efficiency(charging_efficiency: float, discharging_efficiency: float) -> float:
    """Return the round-trip efficiency as a fraction."""
    return round(charging_efficiency * discharging_efficiency, 6)


def calculate_break_even_price(expected_discharge_price: float, round_trip_efficiency: float) -> float:
    """Return the maximum profitable charge price in base currency per kWh."""
    return round(expected_discharge_price * round_trip_efficiency, 6)


def filter_intervals_by_profitability(
    intervals: list[dict[str, Any]],
    *,
    charging_efficiency: float,
    discharging_efficiency: float,
    expected_discharge_price: float | None = None,
    reserve_for_discharge: bool = False,
    max_cost_per_kwh: float | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Filter candidate intervals by hard ceiling and optional profitability."""
    filtered = list(intervals)
    metadata: dict[str, Any] = {
        "reserve_for_discharge": reserve_for_discharge,
        "expected_discharge_price": expected_discharge_price,
        "max_cost_per_kwh": max_cost_per_kwh,
        "break_even_price": None,
        "filtered_out_by_cost": 0,
        "filtered_out_by_profitability": 0,
    }

    if max_cost_per_kwh is not None:
        before = len(filtered)
        filtered = [interval for interval in filtered if float(interval["total"]) <= max_cost_per_kwh]
        metadata["filtered_out_by_cost"] = before - len(filtered)

    if expected_discharge_price is not None:
        round_trip_efficiency = calculate_round_trip_efficiency(charging_efficiency, discharging_efficiency)
        break_even_price = calculate_break_even_price(expected_discharge_price, round_trip_efficiency)
        metadata["break_even_price"] = break_even_price
        if reserve_for_discharge:
            before = len(filtered)
            filtered = [interval for interval in filtered if float(interval["total"]) <= break_even_price]
            metadata["filtered_out_by_profitability"] = before - len(filtered)

    return filtered, metadata


def calculate_plan_economics(
    scheduled_intervals: list[dict[str, Any]],
    *,
    charging_efficiency: float,
    discharging_efficiency: float,
    expected_discharge_price: float | None,
    unit_factor: int,
    max_cost_per_kwh: float | None = None,
    reserve_for_discharge: bool = False,
) -> dict[str, Any] | None:
    """Calculate round-trip economics for the selected charging plan."""
    if expected_discharge_price is None and max_cost_per_kwh is None and not reserve_for_discharge:
        return None

    round_trip_efficiency = calculate_round_trip_efficiency(charging_efficiency, discharging_efficiency)
    break_even_price = (
        calculate_break_even_price(expected_discharge_price, round_trip_efficiency)
        if expected_discharge_price is not None
        else None
    )

    total_grid_energy_kwh = sum(float(interval.get("grid_energy_kwh", 0.0)) for interval in scheduled_intervals)
    total_stored_energy_kwh = sum(float(interval.get("stored_energy_kwh", 0.0)) for interval in scheduled_intervals)
    total_cost_base = sum(
        float(interval["total"]) * float(interval.get("grid_energy_kwh", 0.0)) for interval in scheduled_intervals
    )

    expected_revenue_base = None
    expected_net_savings_base = None
    if expected_discharge_price is not None:
        expected_revenue_base = total_stored_energy_kwh * discharging_efficiency * expected_discharge_price
        expected_net_savings_base = expected_revenue_base - total_cost_base

    return {
        "reserve_for_discharge": reserve_for_discharge,
        "round_trip_efficiency": round(round_trip_efficiency, 6),
        "expected_discharge_price": round(expected_discharge_price * unit_factor, 4)
        if expected_discharge_price is not None
        else None,
        "break_even_price": round(break_even_price * unit_factor, 4) if break_even_price is not None else None,
        "max_cost_per_kwh": round(max_cost_per_kwh * unit_factor, 4) if max_cost_per_kwh is not None else None,
        "expected_revenue": round(expected_revenue_base * unit_factor, 4)
        if expected_revenue_base is not None
        else None,
        "expected_net_savings": round(expected_net_savings_base * unit_factor, 4)
        if expected_net_savings_base is not None
        else None,
        "total_grid_energy_kwh": round(total_grid_energy_kwh, 6),
        "total_stored_energy_kwh": round(total_stored_energy_kwh, 6),
    }
