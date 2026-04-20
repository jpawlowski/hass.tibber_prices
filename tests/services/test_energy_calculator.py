"""Unit tests for charging energy calculation helpers."""

from __future__ import annotations

from custom_components.tibber_prices.services.charging.energy_calculator import (
    build_soc_progression,
    calculate_duration_intervals,
    calculate_energy_needed,
    soc_percent_to_kwh,
)


def test_soc_percent_to_kwh() -> None:
    """Convert percent SoC to kWh."""
    assert soc_percent_to_kwh(25.0, 12.0) == 3.0


def test_calculate_energy_needed_accounts_for_efficiency() -> None:
    """Grid energy should include charging losses."""
    assert calculate_energy_needed(2.0, 6.0, 0.8) == 5.0


def test_calculate_duration_intervals_rounds_up() -> None:
    """Charging duration should round up to the next full interval."""
    assert calculate_duration_intervals(2.1, 4000) == 3


def test_build_soc_progression_adds_soc_fields() -> None:
    """Each interval should include power, energy, and SoC after charging."""
    intervals = [
        {"startsAt": "2026-01-01T00:00:00+00:00", "total": 0.10, "level": "NORMAL"},
        {"startsAt": "2026-01-01T00:15:00+00:00", "total": 0.12, "level": "NORMAL"},
    ]

    result = build_soc_progression(
        intervals,
        power_w=4000,
        start_soc_kwh=2.0,
        capacity_kwh=10.0,
        charging_efficiency=1.0,
    )

    assert result[0]["power_w"] == 4000
    assert result[0]["energy_kwh"] == 1.0
    assert result[0]["soc_after_kwh"] == 3.0
    assert result[0]["soc_after_percent"] == 30.0
    assert result[1]["soc_after_kwh"] == 4.0
    assert result[1]["soc_after_percent"] == 40.0
