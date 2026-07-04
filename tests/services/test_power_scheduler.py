"""Unit tests for charging power scheduling helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from custom_components.tibber_prices.services.charging.deadline_solver import resolve_deadline
from custom_components.tibber_prices.services.charging.power_scheduler import (
    apply_segment_constraints,
    build_power_schedule,
)


def _make_intervals(prices: list[float]) -> list[dict[str, object]]:
    base = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    return [
        {
            "startsAt": (base + timedelta(minutes=15 * index)).isoformat(),
            "total": price,
            "level": "NORMAL",
        }
        for index, price in enumerate(prices)
    ]


def test_continuous_mode_uses_partial_last_interval_power() -> None:
    """Continuous mode should reduce the last interval power when possible."""
    result = build_power_schedule(
        _make_intervals([0.20, 0.10, 0.15]),
        2.5,
        max_charge_power_w=4000,
        min_charge_power_w=1000,
        charging_efficiency=1.0,
    )

    assert result["mode"] == "continuous"
    assert result["total_grid_energy_kwh"] == 2.5
    assert sorted(interval["power_w"] for interval in result["intervals"]) == [2000, 4000, 4000]


def test_stepped_mode_uses_smallest_sufficient_step() -> None:
    """Stepped mode should choose the smallest allowed step that finishes the plan."""
    result = build_power_schedule(
        _make_intervals([0.20, 0.10, 0.15]),
        2.5,
        max_charge_power_w=4000,
        charge_power_steps_w=[1000, 2000, 4000],
        charging_efficiency=1.0,
    )

    assert result["mode"] == "stepped"
    assert result["total_grid_energy_kwh"] == 2.5
    assert sorted(interval["power_w"] for interval in result["intervals"]) == [2000, 4000, 4000]


def test_apply_segment_constraints_bridges_and_trims_to_target() -> None:
    """Bridging isolated cheap intervals must not leave more energy than requested.

    Direct unit-level regression for the ``max_cycles_per_day`` overcharge bug: bridging
    fills the gaps between segments with extra (non-essential) intervals, and the
    subsequent trim step must remove exactly that surplus again.
    """
    candidates = _make_intervals([0.10, 0.80, 0.11, 0.90, 0.12, 0.95, 0.50, 0.60])
    schedule = build_power_schedule(candidates, 3.0, max_charge_power_w=4000, charging_efficiency=1.0)
    assert schedule["total_grid_energy_kwh"] == 3.0
    assert len(schedule["segments"]) == 3  # three isolated cheap intervals

    schedule, warnings = apply_segment_constraints(
        schedule,
        candidates,
        charging_efficiency=1.0,
        max_cycles_per_day=1,
        target_grid_energy_kwh=3.0,
        interval_minutes=15,
    )

    assert warnings == []
    assert len(schedule["segments"]) == 1
    assert schedule["total_grid_energy_kwh"] == 3.0
    assert [interval["total"] for interval in schedule["intervals"]] == [0.10, 0.80, 0.11]


def test_apply_segment_constraints_never_trims_below_target() -> None:
    """Trimming must never drop the plan below the required energy.

    Fixed-power mode cannot reduce the last interval's power, so it can legitimately
    overshoot the target by up to one interval's energy. This is expected physical
    behavior (not constraint bridging) and must survive trimming unchanged.
    """
    candidates = _make_intervals([0.10, 0.20])
    schedule = build_power_schedule(candidates, 1.5, max_charge_power_w=4000, charging_efficiency=1.0)
    assert schedule["total_grid_energy_kwh"] == 2.0  # rounded up from 1.5

    schedule, warnings = apply_segment_constraints(
        schedule,
        candidates,
        charging_efficiency=1.0,
        target_grid_energy_kwh=1.5,
        interval_minutes=15,
    )

    assert warnings == []
    assert schedule["total_grid_energy_kwh"] == 2.0  # both intervals kept
    assert len(schedule["intervals"]) == 2


def test_apply_segment_constraints_respects_protected_starts() -> None:
    """Protected intervals (e.g. deadline-critical) must survive trimming.

    Even when a protected interval is the most expensive edge of the merged segment,
    trimming must skip it and remove the next-best removable edge instead.
    """
    candidates = _make_intervals([0.80, 0.95, 0.95, 0.05])
    protected_start = candidates[0]["startsAt"]

    schedule = build_power_schedule(candidates, 2.0, max_charge_power_w=4000, charging_efficiency=1.0)
    assert [interval["total"] for interval in schedule["intervals"]] == [0.80, 0.05]

    schedule, warnings = apply_segment_constraints(
        schedule,
        candidates,
        charging_efficiency=1.0,
        max_cycles_per_day=1,
        target_grid_energy_kwh=2.0,
        protected_starts=frozenset({protected_start}),
        interval_minutes=15,
    )

    assert warnings == []
    assert schedule["total_grid_energy_kwh"] == 2.0
    starts = {interval["startsAt"] for interval in schedule["intervals"]}
    assert protected_start in starts


def test_resolve_deadline_next_peak_period() -> None:
    """Deadline helper should resolve the next future peak period start."""
    now = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    home_tz = ZoneInfo("UTC")
    coordinator_data = {
        "pricePeriods": {
            "peak_price": {
                "periods": [
                    {
                        "start": datetime(2026, 1, 1, 1, 0, tzinfo=UTC),
                        "end": datetime(2026, 1, 1, 2, 0, tzinfo=UTC),
                    }
                ]
            }
        }
    }

    deadline, source = resolve_deadline(
        coordinator_data=coordinator_data,
        now=now,
        home_tz=home_tz,
        must_reach_by_event="next_peak_period",
    )

    assert deadline == datetime(2026, 1, 1, 1, 0, tzinfo=UTC)
    assert source == "next_peak_period"
