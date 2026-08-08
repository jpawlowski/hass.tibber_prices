"""Unit tests for charging round-trip economics helpers."""

from __future__ import annotations

from custom_components.tibber_prices.services.charging.economics import (
    calculate_break_even_price,
    calculate_plan_economics,
    calculate_round_trip_efficiency,
    filter_intervals_by_profitability,
)


def test_round_trip_efficiency_multiplies_both_legs() -> None:
    """Round-trip efficiency is charge loss times discharge loss, not their sum or average."""
    assert calculate_round_trip_efficiency(0.9, 0.9) == 0.81


def test_break_even_price_scales_by_round_trip_efficiency() -> None:
    """The break-even charge price must shrink by exactly the round-trip efficiency."""
    assert calculate_break_even_price(0.30, 0.81) == 0.243


# ---------------------------------------------------------------------------
# filter_intervals_by_profitability
# ---------------------------------------------------------------------------


def test_max_cost_ceiling_filters_without_touching_profitability() -> None:
    """A hard price ceiling alone must not require an expected discharge price."""
    intervals = [{"total": price} for price in (0.05, 0.10, 0.15, 0.20)]

    filtered, metadata = filter_intervals_by_profitability(
        intervals,
        charging_efficiency=1.0,
        discharging_efficiency=1.0,
        max_cost_per_kwh=0.12,
    )

    assert [interval["total"] for interval in filtered] == [0.05, 0.10]
    assert metadata["filtered_out_by_cost"] == 2
    assert metadata["filtered_out_by_profitability"] == 0
    assert metadata["break_even_price"] is None


def test_reserve_for_discharge_drops_unprofitable_intervals() -> None:
    """With reserve_for_discharge on, only intervals at or below break-even survive.

    charging_efficiency=1.0, discharging_efficiency=0.5 -> round-trip 0.5;
    expected_discharge_price=0.20 -> break-even 0.10.
    """
    intervals = [{"total": price} for price in (0.05, 0.08, 0.12, 0.15)]

    filtered, metadata = filter_intervals_by_profitability(
        intervals,
        charging_efficiency=1.0,
        discharging_efficiency=0.5,
        expected_discharge_price=0.20,
        reserve_for_discharge=True,
    )

    assert [interval["total"] for interval in filtered] == [0.05, 0.08]
    assert metadata["break_even_price"] == 0.1
    assert metadata["filtered_out_by_profitability"] == 2


def test_expected_price_without_reserve_only_reports_break_even() -> None:
    """Without reserve_for_discharge, the break-even price is informational only - nothing is dropped."""
    intervals = [{"total": price} for price in (0.05, 0.08, 0.12, 0.15)]

    filtered, metadata = filter_intervals_by_profitability(
        intervals,
        charging_efficiency=1.0,
        discharging_efficiency=0.5,
        expected_discharge_price=0.20,
        reserve_for_discharge=False,
    )

    assert filtered == intervals
    assert metadata["break_even_price"] == 0.1
    assert metadata["filtered_out_by_profitability"] == 0


def test_cost_ceiling_and_profitability_filters_compose() -> None:
    """The cost ceiling is applied first, then profitability narrows what's left further."""
    intervals = [{"total": price} for price in (0.05, 0.08, 0.12, 0.15, 0.25)]

    filtered, metadata = filter_intervals_by_profitability(
        intervals,
        charging_efficiency=1.0,
        discharging_efficiency=0.5,
        max_cost_per_kwh=0.15,
        expected_discharge_price=0.20,
        reserve_for_discharge=True,
    )

    assert [interval["total"] for interval in filtered] == [0.05, 0.08]
    assert metadata["filtered_out_by_cost"] == 1  # drops 0.25
    assert metadata["filtered_out_by_profitability"] == 2  # drops 0.12 and 0.15


# ---------------------------------------------------------------------------
# calculate_plan_economics
# ---------------------------------------------------------------------------


def test_no_economic_inputs_means_no_economics_block() -> None:
    """Without any of the three opt-in inputs, the response has nothing to compute."""
    scheduled = [{"total": 0.10, "grid_energy_kwh": 1.0, "stored_energy_kwh": 0.9}]

    result = calculate_plan_economics(
        scheduled,
        charging_efficiency=0.9,
        discharging_efficiency=0.9,
        expected_discharge_price=None,
        unit_factor=100,
        max_cost_per_kwh=None,
        reserve_for_discharge=False,
    )

    assert result is None


def test_full_economics_block_with_expected_discharge_price() -> None:
    """Every derived value must be present and scaled by unit_factor when a discharge price is given."""
    scheduled = [
        {"total": 0.10, "grid_energy_kwh": 1.0, "stored_energy_kwh": 0.9},
        {"total": 0.12, "grid_energy_kwh": 1.0, "stored_energy_kwh": 0.9},
    ]

    result = calculate_plan_economics(
        scheduled,
        charging_efficiency=0.9,
        discharging_efficiency=0.9,
        expected_discharge_price=0.30,
        unit_factor=100,
    )

    assert result is not None
    assert result["round_trip_efficiency"] == 0.81
    assert result["expected_discharge_price"] == 30.0
    assert result["break_even_price"] == 24.3
    assert result["max_cost_per_kwh"] is None
    assert result["total_grid_energy_kwh"] == 2.0
    assert result["total_stored_energy_kwh"] == 1.8
    # revenue = stored_kwh * discharge_efficiency * price = 1.8 * 0.9 * 0.30 = 0.486
    # cost    = sum(price * grid_kwh)                    = 0.10 + 0.12       = 0.22
    assert result["expected_revenue"] == 48.6
    assert result["expected_net_savings"] == 26.6


def test_max_cost_ceiling_alone_omits_discharge_fields() -> None:
    """A bare cost ceiling (no expected discharge price) must not fabricate revenue numbers."""
    scheduled = [{"total": 0.10, "grid_energy_kwh": 1.0, "stored_energy_kwh": 0.9}]

    result = calculate_plan_economics(
        scheduled,
        charging_efficiency=0.9,
        discharging_efficiency=0.9,
        expected_discharge_price=None,
        unit_factor=100,
        max_cost_per_kwh=0.15,
    )

    assert result is not None
    assert result["max_cost_per_kwh"] == 15.0
    assert result["expected_discharge_price"] is None
    assert result["break_even_price"] is None
    assert result["expected_revenue"] is None
    assert result["expected_net_savings"] is None
    # Round-trip efficiency is still meaningful even without a discharge price.
    assert result["round_trip_efficiency"] == 0.81


def test_reserve_for_discharge_flag_is_echoed_back() -> None:
    """The response must reflect whether reserve_for_discharge was actually requested."""
    scheduled = [{"total": 0.10, "grid_energy_kwh": 1.0, "stored_energy_kwh": 0.9}]

    result = calculate_plan_economics(
        scheduled,
        charging_efficiency=1.0,
        discharging_efficiency=1.0,
        expected_discharge_price=None,
        unit_factor=1,
        reserve_for_discharge=True,
    )

    assert result is not None
    assert result["reserve_for_discharge"] is True
