"""Tests for the plan_charging service handler."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall

import pytest

from custom_components.tibber_prices.services import plan_charging as charging_module
from custom_components.tibber_prices.services.plan_charging import handle_plan_charging
from homeassistant.exceptions import ServiceValidationError


class _FakePool:
    """Minimal async interval pool for plan_charging tests."""

    def __init__(self, intervals: list[dict[str, Any]]) -> None:
        self._intervals = intervals

    async def get_intervals(self, **_kwargs: object) -> tuple[list[dict[str, Any]], bool]:
        return self._intervals, False


def _make_intervals(prices: list[float], start: datetime | None = None) -> list[dict[str, Any]]:
    """Create quarter-hour intervals for tests."""
    base = start or datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    return [
        {
            "startsAt": (base + timedelta(minutes=15 * index)).isoformat(),
            "total": price,
            "level": "NORMAL",
        }
        for index, price in enumerate(prices)
    ]


def _build_fake_entry_and_coordinator(
    intervals: list[dict[str, Any]],
    *,
    price_periods: dict[str, Any] | None = None,
) -> tuple[SimpleNamespace, SimpleNamespace, dict]:
    """Build a minimal entry/coordinator/data tuple used by service handlers."""
    pool = _FakePool(intervals)
    entry = SimpleNamespace(
        data={"home_id": "home_1", "currency": "EUR"},
        runtime_data=SimpleNamespace(interval_pool=pool),
    )
    coordinator = SimpleNamespace(
        api=object(),
        _cached_user_data={"viewer": {"homes": [{"id": "home_1", "timeZone": "UTC"}]}},
    )
    data = {"priceInfo": intervals, "pricePeriods": price_periods or {}}
    return entry, coordinator, data


@pytest.mark.asyncio
async def test_plan_charging_returns_schedule_with_soc_progression(monkeypatch: pytest.MonkeyPatch) -> None:
    """Service should calculate duration and return cheapest intervals with SoC progression."""
    intervals = _make_intervals([0.50, 0.10, 0.11, 0.60, 0.12])
    fake_tuple = _build_fake_entry_and_coordinator(intervals)

    monkeypatch.setattr(charging_module, "get_entry_and_data", lambda _hass, _entry_id: fake_tuple)
    monkeypatch.setattr(charging_module, "resolve_home_timezone", lambda _coord, _home_id: "UTC")
    monkeypatch.setattr(
        charging_module,
        "resolve_search_range",
        lambda _call_data, _now, _home_tz: (
            datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
            datetime(2026, 1, 1, 2, 0, tzinfo=UTC),
        ),
    )
    monkeypatch.setattr(charging_module, "get_display_unit_factor", lambda _entry: 1)
    monkeypatch.setattr(charging_module, "get_display_unit_string", lambda _entry, _currency: "EUR/kWh")
    monkeypatch.setattr(charging_module.dt_util, "now", lambda: datetime(2026, 1, 1, 0, 0, tzinfo=UTC))

    call = SimpleNamespace(
        hass=object(),
        data={
            "battery_capacity_kwh": 10.0,
            "current_soc_percent": 20.0,
            "target_soc_percent": 40.0,
            "max_charge_power_w": 4000,
            "charging_efficiency": 1.0,
            "use_base_unit": True,
            "allow_relaxation": False,
        },
    )

    response = cast("dict[str, Any]", await handle_plan_charging(cast("ServiceCall", call)))

    assert response["intervals_found"] is True
    assert response["battery"]["current_soc_kwh"] == 2.0
    assert response["battery"]["target_soc_kwh"] == 4.0
    assert response["charging"]["total_duration_minutes"] == 30
    assert response["charging"]["total_energy_kwh"] == 2.0
    assert response["charging"]["schedule"]["segment_count"] == 1

    scheduled_intervals = cast("list[dict[str, Any]]", response["charging"]["schedule"]["intervals"])
    assert [iv["price"] for iv in scheduled_intervals] == [0.1, 0.11]
    assert scheduled_intervals[0]["soc_after_kwh"] == 3.0
    assert scheduled_intervals[1]["soc_after_kwh"] == 4.0
    assert scheduled_intervals[1]["soc_after_percent"] == 40.0


@pytest.mark.asyncio
async def test_plan_charging_returns_already_at_target(monkeypatch: pytest.MonkeyPatch) -> None:
    """Service should return a stable reason when no charging is needed."""
    intervals = _make_intervals([0.10, 0.12, 0.14])
    fake_tuple = _build_fake_entry_and_coordinator(intervals)

    monkeypatch.setattr(charging_module, "get_entry_and_data", lambda _hass, _entry_id: fake_tuple)
    monkeypatch.setattr(charging_module, "get_display_unit_string", lambda _entry, _currency: "EUR/kWh")

    call = SimpleNamespace(
        hass=object(),
        data={
            "battery_capacity_kwh": 10.0,
            "current_soc_percent": 80.0,
            "target_soc_percent": 60.0,
            "max_charge_power_w": 4000,
            "use_base_unit": True,
        },
    )

    response = cast("dict[str, Any]", await handle_plan_charging(cast("ServiceCall", call)))

    assert response["intervals_found"] is False
    assert response["reason"] == "already_at_target"
    assert response["charging"] is None


@pytest.mark.asyncio
async def test_plan_charging_requires_current_soc() -> None:
    """Service should reject requests without current SoC input."""
    call = SimpleNamespace(
        hass=object(),
        data={
            "battery_capacity_kwh": 10.0,
            "target_soc_percent": 80.0,
            "max_charge_power_w": 4000,
        },
    )

    with pytest.raises(ServiceValidationError):
        await handle_plan_charging(cast("ServiceCall", call))


@pytest.mark.asyncio
async def test_plan_charging_can_meet_deadline_before_peak_period(monkeypatch: pytest.MonkeyPatch) -> None:
    """Service should split charging so the required minimum SoC is reached before the next peak period."""
    intervals = _make_intervals([0.50, 0.40, 0.10, 0.12, 0.11, 0.60])
    price_periods = {
        "peak_price": {
            "periods": [
                {
                    "start": datetime(2026, 1, 1, 1, 0, tzinfo=UTC),
                    "end": datetime(2026, 1, 1, 1, 30, tzinfo=UTC),
                }
            ]
        }
    }
    fake_tuple = _build_fake_entry_and_coordinator(intervals, price_periods=price_periods)

    monkeypatch.setattr(charging_module, "get_entry_and_data", lambda _hass, _entry_id: fake_tuple)
    monkeypatch.setattr(charging_module, "resolve_home_timezone", lambda _coord, _home_id: "UTC")
    monkeypatch.setattr(
        charging_module,
        "resolve_search_range",
        lambda _call_data, _now, _home_tz: (
            datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
            datetime(2026, 1, 1, 2, 0, tzinfo=UTC),
        ),
    )
    monkeypatch.setattr(charging_module, "get_display_unit_factor", lambda _entry: 1)
    monkeypatch.setattr(charging_module, "get_display_unit_string", lambda _entry, _currency: "EUR/kWh")
    monkeypatch.setattr(charging_module.dt_util, "now", lambda: datetime(2026, 1, 1, 0, 0, tzinfo=UTC))

    call = SimpleNamespace(
        hass=object(),
        data={
            "battery_capacity_kwh": 10.0,
            "current_soc_percent": 20.0,
            "target_soc_percent": 60.0,
            "must_reach_soc_percent": 40.0,
            "must_reach_by_event": "next_peak_period",
            "max_charge_power_w": 4000,
            "charging_efficiency": 1.0,
            "use_base_unit": True,
            "allow_relaxation": False,
        },
    )

    response = cast("dict[str, Any]", await handle_plan_charging(cast("ServiceCall", call)))

    assert response["intervals_found"] is True
    assert response["deadline"]["deadline_met"] is True
    assert response["deadline"]["must_reach_soc_kwh"] == 4.0
    assert response["deadline"]["achieved_soc_kwh"] >= 4.0


@pytest.mark.asyncio
async def test_plan_charging_can_filter_by_profitability(monkeypatch: pytest.MonkeyPatch) -> None:
    """Economic filtering should keep only profitable intervals when reserve_for_discharge is enabled."""
    intervals = _make_intervals([0.05, 0.08, 0.12, 0.15])
    fake_tuple = _build_fake_entry_and_coordinator(intervals)

    monkeypatch.setattr(charging_module, "get_entry_and_data", lambda _hass, _entry_id: fake_tuple)
    monkeypatch.setattr(charging_module, "resolve_home_timezone", lambda _coord, _home_id: "UTC")
    monkeypatch.setattr(
        charging_module,
        "resolve_search_range",
        lambda _call_data, _now, _home_tz: (
            datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
            datetime(2026, 1, 1, 2, 0, tzinfo=UTC),
        ),
    )
    monkeypatch.setattr(charging_module, "get_display_unit_factor", lambda _entry: 1)
    monkeypatch.setattr(charging_module, "get_display_unit_string", lambda _entry, _currency: "EUR/kWh")

    call = SimpleNamespace(
        hass=object(),
        data={
            "battery_capacity_kwh": 10.0,
            "current_soc_percent": 20.0,
            "target_soc_percent": 40.0,
            "max_charge_power_w": 4000,
            "charging_efficiency": 1.0,
            "discharging_efficiency": 0.5,
            "expected_discharge_price": 0.20,
            "reserve_for_discharge": True,
            "use_base_unit": True,
            "allow_relaxation": False,
        },
    )

    response = cast("dict[str, Any]", await handle_plan_charging(cast("ServiceCall", call)))

    assert response["intervals_found"] is True
    assert response["economics"]["break_even_price"] == 0.1
    prices = [interval["price"] for interval in response["charging"]["schedule"]["intervals"]]
    assert prices == [0.05, 0.08]


@pytest.mark.asyncio
async def test_plan_charging_respects_min_charge_duration(monkeypatch: pytest.MonkeyPatch) -> None:
    """A single cheap interval should be extended to satisfy minimum charge duration."""
    intervals = _make_intervals([0.50, 0.10, 0.20, 0.70])
    fake_tuple = _build_fake_entry_and_coordinator(intervals)

    monkeypatch.setattr(charging_module, "get_entry_and_data", lambda _hass, _entry_id: fake_tuple)
    monkeypatch.setattr(charging_module, "resolve_home_timezone", lambda _coord, _home_id: "UTC")
    monkeypatch.setattr(
        charging_module,
        "resolve_search_range",
        lambda _call_data, _now, _home_tz: (
            datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
            datetime(2026, 1, 1, 2, 0, tzinfo=UTC),
        ),
    )
    monkeypatch.setattr(charging_module, "get_display_unit_factor", lambda _entry: 1)
    monkeypatch.setattr(charging_module, "get_display_unit_string", lambda _entry, _currency: "EUR/kWh")

    call = SimpleNamespace(
        hass=object(),
        data={
            "battery_capacity_kwh": 10.0,
            "current_soc_percent": 20.0,
            "target_soc_percent": 30.0,
            "max_charge_power_w": 4000,
            "min_charge_duration_minutes": 30,
            "charging_efficiency": 1.0,
            "use_base_unit": True,
            "allow_relaxation": False,
        },
    )

    response = cast("dict[str, Any]", await handle_plan_charging(cast("ServiceCall", call)))

    assert response["intervals_found"] is True
    assert response["charging"]["total_duration_minutes"] == 30
    assert response["charging"]["schedule"]["segment_count"] == 1

    scheduled = cast("list[dict[str, Any]]", response["charging"]["schedule"]["intervals"])
    assert [interval["price"] for interval in scheduled] == [0.1, 0.2]
    assert response["warnings"] is None


@pytest.mark.asyncio
async def test_plan_charging_respects_max_cycles_per_day(monkeypatch: pytest.MonkeyPatch) -> None:
    """Multiple cheap isolated intervals should be bridged to satisfy max cycle limits."""
    intervals = _make_intervals([0.10, 0.80, 0.11, 0.90, 0.12, 0.95, 0.50, 0.60])
    fake_tuple = _build_fake_entry_and_coordinator(intervals)

    monkeypatch.setattr(charging_module, "get_entry_and_data", lambda _hass, _entry_id: fake_tuple)
    monkeypatch.setattr(charging_module, "resolve_home_timezone", lambda _coord, _home_id: "UTC")
    monkeypatch.setattr(
        charging_module,
        "resolve_search_range",
        lambda _call_data, _now, _home_tz: (
            datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
            datetime(2026, 1, 1, 2, 0, tzinfo=UTC),
        ),
    )
    monkeypatch.setattr(charging_module, "get_display_unit_factor", lambda _entry: 1)
    monkeypatch.setattr(charging_module, "get_display_unit_string", lambda _entry, _currency: "EUR/kWh")

    call = SimpleNamespace(
        hass=object(),
        data={
            "battery_capacity_kwh": 10.0,
            "current_soc_percent": 20.0,
            "target_soc_percent": 50.0,
            "max_charge_power_w": 4000,
            "max_cycles_per_day": 1,
            "charging_efficiency": 1.0,
            "use_base_unit": True,
            "allow_relaxation": False,
        },
    )

    response = cast("dict[str, Any]", await handle_plan_charging(cast("ServiceCall", call)))

    assert response["intervals_found"] is True
    assert response["charging"]["schedule"]["segment_count"] == 1

    scheduled = cast("list[dict[str, Any]]", response["charging"]["schedule"]["intervals"])
    assert [interval["price"] for interval in scheduled[:5]] == [0.1, 0.8, 0.11, 0.9, 0.12]
    assert response["warnings"] is None
