"""Attributes that only repeat or derive other data stay out of the recorder database."""

from __future__ import annotations

import json
from pathlib import Path
import re

import pytest

from custom_components.tibber_prices.binary_sensor.core import TibberPricesBinarySensor
from custom_components.tibber_prices.sensor.core import TibberPricesSensor
from custom_components.tibber_prices.sensor.definitions import ENTITY_DESCRIPTIONS, TREND_HOURS

SOURCE = json.loads(
    (Path(__file__).parent.parent / "scripts" / "i18n" / "attribute-names.json").read_text(encoding="utf-8")
)
NAMES = SOURCE["names"]
HOUR_NAMES = [name for name in NAMES if "{h}" in name]
HOUR_PATTERNS = [re.compile("^" + re.escape(name).replace(r"\{h\}", r"\d+") + "$") for name in HOUR_NAMES]


def has_name(key: str) -> bool:
    """Return True if `key` is an attribute with a name, hour variants included (`trend_4h_percent`)."""
    return key in NAMES or any(pattern.match(key) for pattern in HOUR_PATTERNS)


UNRECORDED = TibberPricesSensor._unrecorded_attributes  # noqa: SLF001
UNRECORDED_BINARY = TibberPricesBinarySensor._unrecorded_attributes  # noqa: SLF001

# Exclusions that are no attribute names: nested structures, cache and lifecycle diagnostics
NOT_NAMED = {
    "trend_attributes",
    "current_trend_attributes",
    "trend_change_attributes",
    "volatility_attributes",
    "data",
    "cache_age",
    "cache_validity",
    "data_completeness",
    "tomorrow_expected_after",
    "next_midnight_turnover",
    "last_update",
}


@pytest.mark.unit
def test_trend_hours_match_the_trend_sensors() -> None:
    """TREND_HOURS lists exactly the hour counts of the outlook sensors, and the trajectory ones are among them."""
    outlook = {int(m[1]) for d in ENTITY_DESCRIPTIONS if (m := re.fullmatch(r"price_outlook_(\d+)h", d.key))}
    trajectory = {int(m[1]) for d in ENTITY_DESCRIPTIONS if (m := re.fullmatch(r"price_trajectory_(\d+)h", d.key))}
    assert set(TREND_HOURS) == outlook
    assert trajectory <= outlook


@pytest.mark.unit
@pytest.mark.parametrize("name", HOUR_NAMES)
def test_attributes_with_an_hour_count_are_not_recorded(name: str) -> None:
    """Every hour-bound attribute is computed from the recorded prices: a new one is excluded for every hour count."""
    for hours in TREND_HOURS:
        assert name.replace("{h}", str(hours)) in UNRECORDED


@pytest.mark.unit
def test_every_unrecorded_key_is_a_real_attribute_name() -> None:
    """A typo in an exclusion would silently record the attribute."""
    for key in UNRECORDED | UNRECORDED_BINARY:
        assert key in NOT_NAMED or has_name(key), f"unknown attribute in an exclusion list: {key}"
