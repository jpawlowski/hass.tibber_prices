"""Unit tests for charging deadline resolution and two-pass scheduling."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.tibber_prices.services.charging.deadline_solver import (
    build_deadline_schedule,
    get_deadline_events,
    resolve_deadline,
)

HOME_TZ = ZoneInfo("Europe/Berlin")
NOW = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)


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


# ---------------------------------------------------------------------------
# resolve_deadline
# ---------------------------------------------------------------------------


def test_get_deadline_events_lists_supported_values() -> None:
    """The selector's valid values must match what resolve_deadline() accepts."""
    assert get_deadline_events() == frozenset({"midnight", "next_peak_period", "next_best_period_end"})


def test_neither_input_resolves_to_no_deadline() -> None:
    """No deadline requested means no deadline resolved."""
    assert resolve_deadline(coordinator_data={}, now=NOW, home_tz=HOME_TZ) == (None, None)


def test_explicit_deadline_is_localized_to_home_timezone() -> None:
    """An explicit deadline is converted into the home's timezone, not left as-is."""
    explicit = datetime(2026, 1, 1, 5, 0, tzinfo=UTC)

    deadline, source = resolve_deadline(coordinator_data={}, now=NOW, home_tz=HOME_TZ, must_reach_by=explicit)

    assert deadline == datetime(2026, 1, 1, 6, 0, tzinfo=HOME_TZ)  # Berlin is UTC+1 in January
    assert source == "explicit"


def test_explicit_and_event_together_are_rejected() -> None:
    """A caller must not be able to supply both an absolute deadline and an event."""
    with pytest.raises(ValueError, match="deadline_conflict"):
        resolve_deadline(
            coordinator_data={},
            now=NOW,
            home_tz=HOME_TZ,
            must_reach_by=datetime(2026, 1, 1, 5, 0, tzinfo=UTC),
            must_reach_by_event="midnight",
        )


def test_unknown_event_is_rejected() -> None:
    """An event outside the supported set must fail clearly, not silently resolve to None."""
    with pytest.raises(ValueError, match="deadline_event_not_available"):
        resolve_deadline(coordinator_data={}, now=NOW, home_tz=HOME_TZ, must_reach_by_event="sunrise")


def test_midnight_event_resolves_to_next_local_midnight() -> None:
    """The 'midnight' event means the next midnight in the home timezone, not UTC."""
    deadline, source = resolve_deadline(coordinator_data={}, now=NOW, home_tz=HOME_TZ, must_reach_by_event="midnight")

    assert deadline == datetime(2026, 1, 2, 0, 0, tzinfo=HOME_TZ)
    assert source == "midnight"


def test_next_peak_period_skips_periods_that_already_started() -> None:
    """Only a peak period that starts in the future counts as the deadline."""
    coordinator_data = {
        "pricePeriods": {
            "peak_price": {
                "periods": [
                    {"start": NOW - timedelta(hours=1), "end": NOW - timedelta(minutes=30)},  # already passed
                    {"start": NOW + timedelta(hours=1), "end": NOW + timedelta(hours=2)},
                ]
            }
        }
    }

    deadline, source = resolve_deadline(
        coordinator_data=coordinator_data, now=NOW, home_tz=HOME_TZ, must_reach_by_event="next_peak_period"
    )

    assert deadline == NOW + timedelta(hours=1)
    assert source == "next_peak_period"


def test_next_peak_period_without_a_future_period_is_rejected() -> None:
    """If price periods haven't been calculated yet (or none remain), the event can't resolve."""
    with pytest.raises(ValueError, match="deadline_event_not_available"):
        resolve_deadline(coordinator_data={}, now=NOW, home_tz=HOME_TZ, must_reach_by_event="next_peak_period")


def test_next_best_period_end_uses_the_end_timestamp() -> None:
    """The deadline is the END of the next best-price period, not its start."""
    coordinator_data = {
        "pricePeriods": {
            "best_price": {
                "periods": [
                    {"start": NOW + timedelta(minutes=30), "end": NOW + timedelta(hours=1)},
                ]
            }
        }
    }

    deadline, source = resolve_deadline(
        coordinator_data=coordinator_data, now=NOW, home_tz=HOME_TZ, must_reach_by_event="next_best_period_end"
    )

    assert deadline == NOW + timedelta(hours=1)
    assert source == "next_best_period_end"


# ---------------------------------------------------------------------------
# build_deadline_schedule
# ---------------------------------------------------------------------------


def test_two_pass_schedule_prioritizes_deadline_energy_first() -> None:
    """The deadline pass must fill from candidates before the deadline, the rest from the remainder.

    Scenario: 8 quarter-hour candidates, a deadline at the 5th interval, needing 1.5 kWh
    before the deadline and 3.0 kWh in total. Fixed power mode (4000 W = 1 kWh/interval)
    cannot split a single interval, so the deadline pass overshoots to 2.0 kWh using the
    two cheapest pre-deadline intervals; the remaining-energy pass must then only ask for
    the leftover 1.0 kWh from the rest of the range, and never reuse an interval already
    spent on the deadline.
    """
    candidates = _make_intervals([0.50, 0.10, 0.60, 0.11, 0.70, 0.12, 0.80, 0.13])
    deadline = datetime(2026, 1, 1, 1, 0, tzinfo=UTC)  # excludes the 5th interval onward

    result = build_deadline_schedule(
        candidates,
        total_energy_needed_grid_kwh=3.0,
        energy_needed_by_deadline_grid_kwh=1.5,
        deadline=deadline,
        max_charge_power_w=4000,
        charging_efficiency=1.0,
    )

    assert result["pre_deadline"]["total_grid_energy_kwh"] == 2.0
    assert result["post_deadline"]["total_grid_energy_kwh"] == 1.0
    assert result["total_grid_energy_kwh"] == 3.0
    assert result["total_stored_energy_kwh"] == 3.0
    assert result["deadline_unallocated_grid_energy_kwh"] == 0.0
    assert result["unallocated_grid_energy_kwh"] == 0.0
    assert result["deadline"] == deadline
    assert result["mode"] == "fixed"
    assert result["effective_max_power_w"] == 4000
    assert result["minimum_power_w"] == 4000

    # The two cheapest pre-deadline intervals (0.10, 0.11), then the cheapest remaining
    # interval overall (0.12) which sits after the deadline - none reused, none skipped.
    assert [interval["total"] for interval in result["intervals"]] == [0.10, 0.11, 0.12]
    # Combined list stays chronologically sorted even though it was assembled from two passes.
    starts = [interval["startsAt"] for interval in result["intervals"]]
    assert starts == sorted(starts)


def test_deadline_pass_reports_shortfall_when_unreachable() -> None:
    """When the pre-deadline candidates can't cover the required energy, the shortfall must surface.

    A real bug here would silently under-report the shortfall (or hide it in the combined
    total), letting the service claim `deadline_met` when it wasn't.
    """
    candidates = _make_intervals([0.50, 0.10, 0.60, 0.11, 0.70, 0.12, 0.80, 0.13])
    deadline = datetime(2026, 1, 1, 1, 0, tzinfo=UTC)

    result = build_deadline_schedule(
        candidates,
        total_energy_needed_grid_kwh=3.0,
        energy_needed_by_deadline_grid_kwh=10.0,  # far more than the 4 pre-deadline intervals can supply
        deadline=deadline,
        max_charge_power_w=4000,
        charging_efficiency=1.0,
    )

    # All 4 pre-deadline intervals get used (1 kWh each = 4 kWh) and 6 kWh is still missing.
    assert result["pre_deadline"]["total_grid_energy_kwh"] == 4.0
    assert result["deadline_unallocated_grid_energy_kwh"] == 6.0
    assert {interval["total"] for interval in result["pre_deadline"]["intervals"]} == {0.50, 0.10, 0.60, 0.11}


def test_charging_efficiency_reduces_stored_but_not_grid_energy() -> None:
    """Losses must show up in stored energy only - grid energy reflects what's actually drawn."""
    candidates = _make_intervals([0.10, 0.11, 0.12, 0.13])
    deadline = datetime(2026, 1, 1, 0, 30, tzinfo=UTC)

    result = build_deadline_schedule(
        candidates,
        total_energy_needed_grid_kwh=2.0,
        energy_needed_by_deadline_grid_kwh=1.0,
        deadline=deadline,
        max_charge_power_w=4000,
        charging_efficiency=0.9,
    )

    assert result["total_grid_energy_kwh"] == 2.0
    assert result["total_stored_energy_kwh"] == pytest.approx(1.8)
