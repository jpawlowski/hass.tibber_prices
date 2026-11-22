"""What the recorder keeps follows the attribute declarations of the entities."""

from __future__ import annotations

import pytest

from custom_components.tibber_prices.binary_sensor.definitions import ENTITY_DESCRIPTIONS as BINARY_DESCRIPTIONS
from custom_components.tibber_prices.sensor.definitions import ENTITY_DESCRIPTIONS as SENSOR_DESCRIPTIONS
from custom_components.tibber_prices.utils.attribute_specs import (
    COMMON_ATTRIBUTES,
    attribute,
    declared_attributes,
    excluded_keys,
)

SENSORS = {d.key: d for d in SENSOR_DESCRIPTIONS}
BINARY_SENSORS = {d.key: d for d in BINARY_DESCRIPTIONS}


@pytest.mark.unit
def test_everything_not_marked_history_is_excluded() -> None:
    """An attribute is left out of the recorder unless it is declared history=True."""
    description = SENSORS["today_volatility"]
    declared = {spec.key: spec for spec in declared_attributes(description)}
    excluded = excluded_keys(description)

    assert {key for key, spec in declared.items() if not spec.history} == excluded
    assert "price_spread" in excluded  # statistics of the same prices
    assert "price_coefficient_variation_percent" not in excluded  # the number behind the level


@pytest.mark.unit
def test_the_same_key_can_be_kept_by_one_entity_and_left_out_by_another() -> None:
    """Exclusion is per entity: the phase binary sensors leave out start and end, the period sensors keep them."""
    assert {"start", "end"} <= excluded_keys(BINARY_SENSORS["in_rising_price_phase"])
    assert not {"start", "end"} & excluded_keys(BINARY_SENSORS["best_price_period"])


@pytest.mark.unit
def test_attributes_with_an_hour_count_are_not_recorded() -> None:
    """The trend percentages and averages (one per hour count, strongly correlated) stay out of the database."""
    hour_bound = [spec for d in SENSOR_DESCRIPTIONS for spec in declared_attributes(d) if "{h}" in spec.name]
    assert hour_bound
    assert not [spec.key for spec in hour_bound if spec.history]


@pytest.mark.unit
def test_common_attributes_are_not_recorded() -> None:
    """Timestamp, description and usage tips are on every entity and never kept."""
    assert not [spec.key for spec in COMMON_ATTRIBUTES if spec.history]


@pytest.mark.unit
def test_an_attribute_needs_the_hour_its_name_asks_for() -> None:
    """A `{h}` template without an hour count, or an hour count without a template, is a mistake."""
    with pytest.raises(ValueError, match="hour count"):
        attribute("trend_{h}h_percent")
    with pytest.raises(ValueError, match="no"):
        attribute("price_mean", hours=4)
    assert attribute("trend_{h}h_percent", hours=4).key == "trend_4h_percent"
