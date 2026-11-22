"""
Entities expose only the attributes their description declares.

Runs every sensor and binary sensor against sample prices and checks what it really exposes with the same
check that logs undeclared attributes in production (strict here: it raises). A new attribute that no
description declares fails this test. Parts of the coordinator that sample prices can't provide (lifecycle,
user data, time travel) are stand-ins, so those entities are checked for what they expose, not for the values.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest

from custom_components.tibber_prices.binary_sensor.core import TibberPricesBinarySensor
from custom_components.tibber_prices.binary_sensor.definitions import ENTITY_DESCRIPTIONS as BINARY_DESCRIPTIONS
from custom_components.tibber_prices.const import CONF_AVERAGE_SENSOR_DISPLAY, get_default_options
from custom_components.tibber_prices.coordinator.core import TibberPricesDataUpdateCoordinator
from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService
from custom_components.tibber_prices.sensor.core import TibberPricesSensor
from custom_components.tibber_prices.sensor.definitions import ENTITY_DESCRIPTIONS as SENSOR_DESCRIPTIONS
from custom_components.tibber_prices.utils import attribute_specs
from custom_components.tibber_prices.utils.price import enrich_price_info_with_differences

BERLIN = ZoneInfo("Europe/Berlin")
NOW = datetime(2026, 11, 24, 14, 10, tzinfo=BERLIN)
LEVELS = ("VERY_CHEAP", "CHEAP", "NORMAL", "EXPENSIVE", "VERY_EXPENSIVE")


class _Coordinator(TibberPricesDataUpdateCoordinator):
    """The real coordinator's lookups on sample data; whatever else is asked for is a stand-in."""

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__"):
            raise AttributeError(name)
        return Mock()


def _price_info(time: TibberPricesTimeService) -> list[dict]:
    """Return three days of enriched quarter-hour prices (yesterday, today, tomorrow)."""
    start = NOW.replace(hour=0, minute=0) - timedelta(days=1)
    intervals = []
    for i in range(96 * 3):
        price = 0.20 + 0.1 * ((i % 96) / 96) + 0.05 * ((i // 96) % 2) + (0.03 if 60 < i % 96 < 80 else 0)
        intervals.append(
            {
                "startsAt": start + timedelta(minutes=15 * i),
                "total": price,
                "energy": price * 0.8,
                "tax": price * 0.2,
                "level": LEVELS[(i // 7) % 5],
                "currency": "EUR",
            }
        )
    return enrich_price_info_with_differences(
        intervals,
        threshold_low=-10,
        threshold_high=10,
        hysteresis=2.0,
        gap_tolerance=1,
        level_gap_tolerance=1,
        time=time,
    )


def _period() -> dict:
    """Return a best price period around the sample time, with the statistics the sensor shows."""
    return {
        "start": NOW - timedelta(minutes=30),
        "end": NOW + timedelta(minutes=90),
        "duration_minutes": 120,
        "level": "CHEAP",
        "rating_level": "LOW",
        "rating_difference_percent": -15.0,
        "price_mean": 0.21,
        "price_median": 0.21,
        "price_min": 0.2,
        "price_max": 0.22,
        "price_spread": 0.02,
        "price_coefficient_variation_percent": 3.0,
        "volatility": "low",
        "period_price_diff_from_daily_min": 0.01,
        "period_price_diff_from_daily_min_percent": 5.0,
        "period_price_diff_from_daily_max": 0.1,
        "period_price_diff_from_daily_max_percent": -30.0,
        "day_volatility_percent": 20.0,
        "day_price_min": 0.2,
        "day_price_max": 0.35,
        "day_price_span": 0.15,
        "period_interval_count": 8,
        "period_position": 1,
        "period_count_total": 1,
        "period_count_remaining": 0,
        "relaxation_active": True,
        "relaxation_level": "flex_increased",
        "relaxation_threshold_original_percent": 15.0,
        "relaxation_threshold_applied_percent": 21.0,
    }


@pytest.fixture
def coordinator(monkeypatch: pytest.MonkeyPatch) -> TibberPricesDataUpdateCoordinator:
    """Return a coordinator with sample prices and one best price period."""
    monkeypatch.setattr(attribute_specs, "STRICT", True)
    time = TibberPricesTimeService(reference_time=NOW)
    coordinator = _Coordinator.__new__(_Coordinator)
    coordinator.time = time
    coordinator.data = {
        "referenceTime": NOW,
        "priceInfo": _price_info(time),
        "currency": "EUR",
        "home_id": "home",
        "pricePeriods": {
            "best_price": {"periods": [_period()], "metadata": {}},
            "peak_price": {"periods": [], "metadata": {}},
        },
    }
    coordinator.last_exception = None
    coordinator.last_update_success = True
    coordinator.hass = Mock()
    coordinator.hass.config.language = "en"
    coordinator.config_entry = Mock(data={}, entry_id="entry", unique_id="home", options=get_default_options("EUR"))
    coordinator.get_user_profile = lambda: {"home": {"appNickname": "Home", "type": "APARTMENT"}}
    coordinator.logger = Mock()
    return coordinator


@pytest.mark.unit
@pytest.mark.parametrize("description", SENSOR_DESCRIPTIONS, ids=lambda d: d.key)
def test_sensors_expose_only_declared_attributes(
    coordinator: TibberPricesDataUpdateCoordinator, description: Any
) -> None:
    """Every attribute a sensor shows is declared on its description."""
    sensor = TibberPricesSensor(coordinator, description)
    sensor.hass = coordinator.hass
    _ = sensor.native_value  # fills what the attribute builders read
    sensor.extra_state_attributes  # noqa: B018 - raises on an undeclared attribute (strict)


@pytest.mark.unit
@pytest.mark.parametrize("description", BINARY_DESCRIPTIONS, ids=lambda d: d.key)
def test_binary_sensors_expose_only_declared_attributes(
    coordinator: TibberPricesDataUpdateCoordinator, description: Any
) -> None:
    """Every attribute a binary sensor shows is declared on its description."""
    sensor = TibberPricesBinarySensor(coordinator, description)
    sensor.hass = coordinator.hass
    sensor.extra_state_attributes  # noqa: B018 - raises on an undeclared attribute (strict)


@pytest.mark.unit
def test_the_sample_data_exercises_the_builders(coordinator: TibberPricesDataUpdateCoordinator) -> None:
    """Guard against a vacuous test: most price sensors expose more than the timestamp on the sample data."""
    rich = 0
    for description in SENSOR_DESCRIPTIONS:
        sensor = TibberPricesSensor(coordinator, description)
        sensor.hass = coordinator.hass
        _ = sensor.native_value
        if len(sensor.extra_state_attributes or {}) > 1:
            rich += 1
    assert rich >= 60


@pytest.mark.unit
def test_an_undeclared_attribute_is_logged_once_outside_the_tests(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """In production an undeclared attribute is a log line, once per entity and key, never an error."""
    monkeypatch.setattr(attribute_specs, "STRICT", False)
    monkeypatch.setattr(attribute_specs, "_REPORTED", set())
    description = SENSOR_DESCRIPTIONS[0]

    declared = attribute_specs.declared_keys(description)
    attribute_specs.report_undeclared(description, ["timestamp", "surprise"], declared)
    attribute_specs.report_undeclared(description, ["timestamp", "surprise"], declared)

    assert [r.getMessage() for r in caplog.records if "surprise" in r.getMessage()] == [
        f"{description.key} exposes undeclared attributes ['surprise']: add them to the entity's attributes"
    ]


HOME_ASSISTANT_SEED = frozenset({"set_by_home_assistant"})


def _sensor(coordinator: TibberPricesDataUpdateCoordinator, key: str) -> TibberPricesSensor:
    """Return a sensor as Home Assistant hands it over: `_state_info` set before async_added_to_hass."""
    sensor = TibberPricesSensor(coordinator, next(d for d in SENSOR_DESCRIPTIONS if d.key == key))
    sensor._state_info = {"unrecorded_attributes": HOME_ASSISTANT_SEED}  # noqa: SLF001
    return sensor


@pytest.mark.unit
def test_a_sensor_adds_its_exclusions_to_what_home_assistant_set(
    coordinator: TibberPricesDataUpdateCoordinator,
) -> None:
    """The recorder set of an entity is Home Assistant's own plus what its description doesn't keep."""
    sensor = _sensor(coordinator, "price_outlook_4h")
    sensor._configure_recorder_exclusions()  # noqa: SLF001

    unrecorded = sensor._state_info["unrecorded_attributes"]  # noqa: SLF001
    assert unrecorded >= HOME_ASSISTANT_SEED
    assert {"trend_4h_percent", "next_4h_avg", "timestamp"} <= unrecorded
    # Another entity's hour count is none of its business
    assert "trend_8h_percent" not in unrecorded


@pytest.mark.unit
@pytest.mark.parametrize(
    ("mode", "left_out", "kept"), [("median", "price_median", "price_mean"), ("mean", "price_mean", "price_median")]
)
def test_an_average_sensor_leaves_out_the_average_its_state_shows(
    coordinator: TibberPricesDataUpdateCoordinator, mode: str, left_out: str, kept: str
) -> None:
    """The state is the mean or the median, so the attribute of that average isn't stored a second time."""
    coordinator.config_entry.options[CONF_AVERAGE_SENSOR_DISPLAY] = mode
    sensor = _sensor(coordinator, "average_price_today")
    sensor._configure_recorder_exclusions()  # noqa: SLF001

    unrecorded = sensor._state_info["unrecorded_attributes"]  # noqa: SLF001
    assert left_out in unrecorded
    assert kept not in unrecorded


@pytest.mark.unit
def test_a_binary_sensor_applies_its_own_declaration(coordinator: TibberPricesDataUpdateCoordinator) -> None:
    """Phase and period sensors share the key `start` and still differ in what is recorded."""
    unrecorded = {}
    for key in ("in_rising_price_phase", "best_price_period"):
        sensor = TibberPricesBinarySensor(coordinator, next(d for d in BINARY_DESCRIPTIONS if d.key == key))
        sensor._state_info = {"unrecorded_attributes": HOME_ASSISTANT_SEED}  # noqa: SLF001
        sensor._apply_recorder_exclusions()  # noqa: SLF001
        unrecorded[key] = sensor._state_info["unrecorded_attributes"]  # noqa: SLF001

    assert "start" in unrecorded["in_rising_price_phase"]
    assert "start" not in unrecorded["best_price_period"]
