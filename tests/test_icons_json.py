"""Icons that depend only on an entity's own state live in icons.json, not in the icon property."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from custom_components.tibber_prices.entity_utils.icons import get_dynamic_icon, uses_icons_json
from custom_components.tibber_prices.number.definitions import BEST_PRICE_NUMBER_ENTITIES, PEAK_PRICE_NUMBER_ENTITIES
from custom_components.tibber_prices.sensor.definitions import ENTITY_DESCRIPTIONS
from custom_components.tibber_prices.switch.definitions import (
    BEST_PRICE_SWITCH_ENTITY_DESCRIPTIONS,
    PEAK_PRICE_SWITCH_ENTITY_DESCRIPTIONS,
)

ICONS = json.loads(
    (Path(__file__).parent.parent / "custom_components/tibber_prices/icons.json").read_text(encoding="utf-8")
)
SENSORS = ICONS["entity"]["sensor"]
BY_KEY = {description.key: description for description in ENTITY_DESCRIPTIONS}


@pytest.mark.unit
@pytest.mark.parametrize("key", sorted(SENSORS))
def test_state_icons_cover_every_option(key: str) -> None:
    """Every enum option has an icon, and the description sets no static icon that would win over icons.json."""
    description = BY_KEY[key]
    assert description.icon is None, f"{key}: a static icon overrides icons.json"
    assert set(SENSORS[key]["state"]) == set(description.options or []), key
    assert SENSORS[key]["default"].startswith("mdi:")


@pytest.mark.unit
def test_all_level_rating_volatility_sensors_are_in_icons_json() -> None:
    """No level, rating or volatility enum sensor is left to the icon property."""
    expected = {
        key
        for key, description in BY_KEY.items()
        if key.endswith(("_price_level", "_price_rating", "_volatility")) and description.options
    }
    assert expected == set(SENSORS)


@pytest.mark.unit
@pytest.mark.parametrize("key", sorted(SENSORS))
def test_icon_property_logic_leaves_these_to_icons_json(key: str) -> None:
    """The dynamic icon helper returns nothing for them, so icons.json applies."""
    assert get_dynamic_icon(key, next(iter(SENSORS[key]["state"]))) is None


@pytest.mark.unit
def test_icon_property_skips_icons_json_sensors() -> None:
    """The icon property returns early for exactly the sensors icons.json serves."""
    assert {key for key in BY_KEY if uses_icons_json(key)} == set(SENSORS)


STATIC_ICON_DESCRIPTIONS = {
    "number": (*BEST_PRICE_NUMBER_ENTITIES, *PEAK_PRICE_NUMBER_ENTITIES),
    "switch": (*BEST_PRICE_SWITCH_ENTITY_DESCRIPTIONS, *PEAK_PRICE_SWITCH_ENTITY_DESCRIPTIONS),
}


@pytest.mark.unit
@pytest.mark.parametrize("platform", sorted(STATIC_ICON_DESCRIPTIONS))
def test_config_entities_take_their_icon_from_icons_json(platform: str) -> None:
    """Number and switch entities have no icon property, so their fixed icon is in icons.json only."""
    descriptions = STATIC_ICON_DESCRIPTIONS[platform]
    assert all(description.icon is None for description in descriptions), platform
    assert {description.translation_key for description in descriptions} == set(ICONS["entity"][platform])
    assert all(entry["default"].startswith("mdi:") for entry in ICONS["entity"][platform].values())
