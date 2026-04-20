"""
Charging-specific calculation modules for the plan_charging service.

Packages:
    energy_calculator: Pure SoC/energy math (Phase 1)
    power_scheduler:   Variable power distribution (Phase 2)
    deadline_solver:   Deadline constraint solving (Phase 3)
    economics:         Round-trip economic analysis (Phase 4)
"""

from __future__ import annotations

from .deadline_solver import build_deadline_schedule, get_deadline_events, resolve_deadline
from .economics import (
    calculate_break_even_price,
    calculate_plan_economics,
    calculate_round_trip_efficiency,
    filter_intervals_by_profitability,
)
from .energy_calculator import (
    build_soc_progression,
    build_soc_progression_from_schedule,
    calculate_duration_intervals,
    calculate_energy_needed,
    soc_percent_to_kwh,
)
from .power_scheduler import apply_segment_constraints, build_power_schedule, determine_power_mode, energy_for_power

__all__ = [
    "apply_segment_constraints",
    "build_deadline_schedule",
    "build_power_schedule",
    "build_soc_progression",
    "build_soc_progression_from_schedule",
    "calculate_break_even_price",
    "calculate_duration_intervals",
    "calculate_energy_needed",
    "calculate_plan_economics",
    "calculate_round_trip_efficiency",
    "determine_power_mode",
    "energy_for_power",
    "filter_intervals_by_profitability",
    "get_deadline_events",
    "resolve_deadline",
    "soc_percent_to_kwh",
]
