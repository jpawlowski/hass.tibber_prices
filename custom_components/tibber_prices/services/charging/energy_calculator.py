"""
Pure energy and state-of-charge calculations for the plan_charging service.

All functions are stateless and have no Home Assistant dependencies.
They operate on plain Python types and are designed for unit testing.
"""

from __future__ import annotations

import math
from typing import Any

# Quarter-hour interval duration in hours
_INTERVAL_HOURS = 0.25


def soc_percent_to_kwh(soc_percent: float, capacity_kwh: float) -> float:
    """Convert state of charge from percent to kilowatt-hours.

    Args:
        soc_percent: State of charge as a percentage (0–100).
        capacity_kwh: Total usable battery capacity in kWh.

    Returns:
        Absolute energy stored in kWh.

    """
    return soc_percent / 100.0 * capacity_kwh


def calculate_energy_needed(
    current_soc_kwh: float,
    target_soc_kwh: float,
    charging_efficiency: float = 1.0,
) -> float:
    """Calculate the grid energy required to reach the target SoC.

    Accounts for charging losses: to store X kWh in the battery, the grid must
    supply X / efficiency kWh.

    Args:
        current_soc_kwh: Current battery energy in kWh.
        target_soc_kwh: Desired battery energy in kWh.
        charging_efficiency: Round-trip charging efficiency (0.5–1.0).
            A value of 0.92 means 8% loss during charging.

    Returns:
        Grid energy required in kWh. Returns 0.0 if already at or above target.

    """
    net_energy = target_soc_kwh - current_soc_kwh
    if net_energy <= 0.0:
        return 0.0
    return net_energy / charging_efficiency


def calculate_duration_intervals(
    energy_kwh: float,
    power_w: int,
    interval_minutes: int = 15,
) -> int:
    """Calculate the number of intervals needed to charge a given energy.

    Always rounds up to the nearest full interval so the charging target
    is always met or exceeded.

    Args:
        energy_kwh: Energy to be charged from the grid in kWh.
        power_w: Charging power in watts.
        interval_minutes: Duration of each interval in minutes (default 15).

    Returns:
        Number of intervals required (≥ 1 if energy > 0, else 0).

    """
    if energy_kwh <= 0.0:
        return 0
    interval_hours = interval_minutes / 60.0
    energy_per_interval_kwh = (power_w / 1000.0) * interval_hours
    return math.ceil(energy_kwh / energy_per_interval_kwh)


def build_soc_progression(
    intervals: list[dict[str, Any]],
    power_w: int,
    start_soc_kwh: float,
    capacity_kwh: float | None,
    charging_efficiency: float = 1.0,
    interval_minutes: int = 15,
) -> list[dict[str, Any]]:
    """Build a per-interval SoC progression for a fixed-power charging session.

    For each interval, calculates:
    - ``power_w``: Charging power applied (same as input, Phase 1 fixed).
    - ``energy_kwh``: Energy stored in the battery during this interval.
    - ``soc_after_kwh``: Absolute SoC after this interval.
    - ``soc_after_percent``: SoC as percentage (only if capacity_kwh provided).

    The function mutates nothing — it returns a new list of dicts augmented
    with the SoC fields.

    Args:
        intervals: Chronologically ordered interval dicts (with at least
            ``startsAt`` and ``total`` keys). Not mutated.
        power_w: Fixed charging power in watts.
        start_soc_kwh: Battery SoC at the beginning of the first interval.
        capacity_kwh: Total battery capacity for % calculation. Pass ``None``
            to omit ``soc_after_percent`` from output.
        charging_efficiency: Fraction of grid energy stored in the battery
            (0.5–1.0). Default is 1.0 (no losses).
        interval_minutes: Duration of each interval in minutes (default 15).

    Returns:
        New list of interval dicts, each augmented with ``power_w``,
        ``energy_kwh``, ``soc_after_kwh``, and optionally ``soc_after_percent``.

    """
    interval_hours = interval_minutes / 60.0
    energy_per_interval_kwh = (power_w / 1000.0) * interval_hours * charging_efficiency

    result: list[dict[str, Any]] = []
    current_soc_kwh = start_soc_kwh

    for iv in intervals:
        current_soc_kwh += energy_per_interval_kwh
        augmented: dict[str, Any] = dict(iv)
        augmented["power_w"] = power_w
        augmented["energy_kwh"] = round(energy_per_interval_kwh, 6)
        augmented["soc_after_kwh"] = round(current_soc_kwh, 6)
        if capacity_kwh is not None and capacity_kwh > 0:
            augmented["soc_after_percent"] = round(current_soc_kwh / capacity_kwh * 100.0, 2)
        result.append(augmented)

    return result


def build_soc_progression_from_schedule(
    scheduled_intervals: list[dict[str, Any]],
    start_soc_kwh: float,
    capacity_kwh: float | None,
) -> list[dict[str, Any]]:
    """Build SoC progression from a precomputed charging schedule.

    Each scheduled interval is expected to provide ``stored_energy_kwh`` and
    usually ``grid_energy_kwh`` plus ``power_w``. The returned intervals keep
    those fields and add the cumulative SoC state.
    """
    result: list[dict[str, Any]] = []
    current_soc_kwh = start_soc_kwh

    for interval in scheduled_intervals:
        stored_energy_kwh = float(interval.get("stored_energy_kwh", interval.get("energy_kwh", 0.0)))
        current_soc_kwh += stored_energy_kwh

        augmented: dict[str, Any] = dict(interval)
        # Preserve the historical Phase 1 response field name while also exposing
        # explicit grid/stored energy values for later phases.
        augmented["energy_kwh"] = round(stored_energy_kwh, 6)
        augmented["soc_after_kwh"] = round(current_soc_kwh, 6)
        if capacity_kwh is not None and capacity_kwh > 0:
            augmented["soc_after_percent"] = round(current_soc_kwh / capacity_kwh * 100.0, 2)
        result.append(augmented)

    return result
