"""Attributes that only repeat or derive other data stay out of the recorder database."""

from __future__ import annotations

import json
from pathlib import Path
import re

import pytest

from custom_components.tibber_prices.binary_sensor.core import TibberPricesBinarySensor
from custom_components.tibber_prices.sensor.core import TibberPricesSensor
from custom_components.tibber_prices.sensor.definitions import ENTITY_DESCRIPTIONS, TREND_HOURS

NAMES = json.loads((Path(__file__).parent.parent / "scripts" / "i18n" / "attribute-names.json").read_text("utf-8"))[
    "names"
]
UNRECORDED = TibberPricesSensor._unrecorded_attributes  # noqa: SLF001
UNRECORDED_BINARY = TibberPricesBinarySensor._unrecorded_attributes  # noqa: SLF001


@pytest.mark.unit
def test_trend_hours_match_the_trend_sensors() -> None:
    """TREND_HOURS lists exactly the hour counts of the outlook and trajectory sensors."""
    outlook = {int(m[1]) for d in ENTITY_DESCRIPTIONS if (m := re.fullmatch(r"price_outlook_(\d+)h", d.key))}
    trajectory = {int(m[1]) for d in ENTITY_DESCRIPTIONS if (m := re.fullmatch(r"price_trajectory_(\d+)h", d.key))}
    assert set(TREND_HOURS) == outlook
    assert trajectory <= outlook


@pytest.mark.unit
@pytest.mark.parametrize("hours", TREND_HOURS)
def test_derived_trend_hour_attributes_are_not_recorded(hours: int) -> None:
    """The half-window averages and their differences are excluded for every hour count; the trend itself is kept."""
    for key in (
        f"first_half_{hours}h_avg",
        f"second_half_{hours}h_avg",
        f"first_half_{hours}h_diff_from_current_percent",
        f"second_half_{hours}h_diff_from_current_percent",
    ):
        assert key in UNRECORDED
    assert f"trend_{hours}h_percent" not in UNRECORDED
    assert f"trajectory_{hours}h_percent" not in UNRECORDED


@pytest.mark.unit
def test_every_unrecorded_key_with_a_name_is_a_real_attribute_name() -> None:
    """A typo in an exclusion would silently record the attribute: keys that look like names must exist there."""
    templates = [re.compile("^" + re.escape(n).replace(r"\{h\}", r"\d+") + "$") for n in NAMES]
    for key in UNRECORDED | UNRECORDED_BINARY:
        if key in NAMES or any(t.match(key) for t in templates):
            continue
        # Entries kept for older attributes or other platforms are listed by hand
        assert key in {
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
            "last_successful_update",
        }, f"unknown attribute in an exclusion list: {key}"
