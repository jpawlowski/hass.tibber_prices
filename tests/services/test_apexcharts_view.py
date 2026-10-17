"""The ApexCharts card fetches its data from the same time-travel view it was generated for."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from custom_components.tibber_prices.services import get_apexcharts_yaml


def _registry() -> MagicMock:
    entities = {}
    for key in ("lowest_price_today", "average_price_today", "highest_price_today"):
        entity = MagicMock(config_entry_id="abc", config_subentry_id="view1", domain="sensor", unique_id=f"abc_{key}")
        entity.entity_id = f"sensor.view_{key}"
        entities[key] = entity
    return MagicMock(entities=entities)


async def _generators(view_id: str) -> list[str]:
    target = MagicMock()
    target.entry.entry_id = "abc"
    target.entry.options = {}
    target.subentry = MagicMock(subentry_id="view1") if view_id else None
    target.coordinator.headless = False
    target.coordinator.data = {"currency": "EUR"}
    hass = MagicMock()
    hass.config.language = "en"
    with (
        patch.object(get_apexcharts_yaml, "resolve_service_target", return_value=target),
        patch.object(get_apexcharts_yaml, "async_get_entity_registry", return_value=_registry()),
        patch.object(get_apexcharts_yaml, "async_load_translations"),
        patch.object(get_apexcharts_yaml, "async_load_standard_translations"),
        patch.object(get_apexcharts_yaml, "get_display_unit_string", return_value="ct/kWh"),
    ):
        card = await get_apexcharts_yaml.async_build_apexcharts_card(
            hass, {"entry_id": "abc", "view_id": view_id, "day": "today", "highlight_peak_price": True}
        )
    return [series["data_generator"] for series in card["series"]]


@pytest.mark.unit
async def test_chart_data_comes_from_the_view() -> None:
    """Every series, overlays included, asks get_chartdata for the view, not for live data."""
    generators = await _generators("device123")
    assert len(generators) == 5  # best + peak overlay, three rating levels
    assert all("view_id: 'device123'" in generator for generator in generators)


@pytest.mark.unit
async def test_live_chart_asks_for_no_view() -> None:
    """Without a view, the data calls stay as before."""
    assert not any("view_id" in generator for generator in await _generators(""))
