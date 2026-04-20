"""Unit tests for charging power scheduling helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from custom_components.tibber_prices.services.charging.deadline_solver import resolve_deadline
from custom_components.tibber_prices.services.charging.power_scheduler import build_power_schedule


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


def test_resolve_deadline_next_peak_period() -> None:
    """Deadline helper should resolve the next future peak period start."""
    now = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
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
        home_tz=UTC,
        must_reach_by_event="next_peak_period",
    )

    assert deadline == datetime(2026, 1, 1, 1, 0, tzinfo=UTC)
    assert source == "next_peak_period"
