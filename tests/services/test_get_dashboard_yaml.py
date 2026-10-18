"""Tests for the get_dashboard_yaml template resolution."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol

from custom_components.tibber_prices.services import get_dashboard_yaml
from custom_components.tibber_prices.services.get_dashboard_yaml import (
    CHART_CARDS,
    CHART_METADATA_KEY,
    CHARTS,
    CUSTOM_CARDS,
    RESOLUTIONS,
    _async_notify,
    _load_template,
    _merged,
    _Resolver,
)

TRANSLATIONS = Path(get_dashboard_yaml.__file__).parents[1] / "custom_translations"
LANGUAGES = ("en", "de", "nb", "nl", "sv")
TEMPLATE_TEXT = get_dashboard_yaml.TEMPLATE_PATH.read_text(encoding="utf-8")
ENTITY_KEYS = sorted(set(re.findall(r"(?:entity|device):([a-z0-9_]+)", TEMPLATE_TEXT)))
# The integration's own cards, set up by the home (its device) like in the visual editor
OWN_CARDS = ("custom:tibber-prices-forecast-card", "custom:tibber-prices-now-card")
CHART_CARD = "custom:tibber-prices-chart-card"
LABEL_KEYS = sorted(set(re.findall(r"label:([a-z0-9_]+)", TEMPLATE_TEXT)))


def _labels(language: str) -> dict[str, str]:
    return json.loads((TRANSLATIONS / f"{language}.json").read_text(encoding="utf-8"))["dashboard"]


def _walk(node: Any) -> list[Any]:
    """Every dict, list and scalar in a node."""
    if isinstance(node, dict):
        return [node, *(item for value in node.values() for item in _walk(value))]
    if isinstance(node, list):
        return [node, *(item for value in node for item in _walk(value))]
    return [node]


def _entities(*without: str) -> dict[str, str]:
    """Every entity the template and charts use, except `without` (disabled or removed)."""
    return {key: f"sensor.home_{key}" for key in [*ENTITY_KEYS, CHART_METADATA_KEY] if key not in without}


async def _resolve(
    entities: dict[str, str] | None = None,
    cards: dict[str, bool] | None = None,
    devices: dict[str, str] | None = None,
    chart_card: str = "apexcharts",
) -> tuple[_Resolver, list[Any]]:
    entities = _entities() if entities is None else entities
    cards = dict.fromkeys(CUSTOM_CARDS, True) if cards is None else cards
    # One home: every entity on its device
    devices = dict.fromkeys(entities, "home_device") if devices is None else devices
    resolver = _Resolver(
        MagicMock(),
        {"entry_id": "abc", "view_id": ""},
        entities,
        _labels("en"),
        cards,
        devices=devices,
        chart_card=chart_card,
    )
    chart = AsyncMock(side_effect=lambda _hass, data, **_: {"type": "custom:apexcharts-card", "day": data["day"]})
    with patch.object(get_dashboard_yaml, "async_build_apexcharts_card", chart):
        views = [await resolver.resolve(view) for view in _load_template()["views"]]
    return resolver, views


@pytest.mark.unit
@pytest.mark.parametrize("language", LANGUAGES)
def test_every_label_is_translated(language: str) -> None:
    """Each label the template uses exists in every language (no silent English fallback)."""
    labels = _labels(language)
    assert [key for key in LABEL_KEYS if key not in labels] == []
    assert set(labels) == set(_labels("en"))
    assert set(labels["notification"]) == set(_labels("en")["notification"])


@pytest.mark.unit
@pytest.mark.parametrize("language", LANGUAGES)
def test_labels_have_no_ascii_quotes(language: str) -> None:
    """Labels are inserted inside Jinja string literals and HTML attributes, where a quote breaks them."""
    labels = {key: text for key, text in _labels(language).items() if isinstance(text, str)}
    assert [key for key, text in labels.items() if "'" in text or '"' in text] == []


@pytest.mark.unit
@pytest.mark.parametrize("chart_card", CHART_CARDS)
async def test_template_resolves_completely(chart_card: str) -> None:
    """With every entity and card present, no placeholder survives and nothing is dropped."""
    resolver, views = await _resolve(chart_card=chart_card)
    strings = [item for item in _walk(views) if isinstance(item, str)]

    assert [s for s in strings if "[[" in s or re.fullmatch(r"(entity|device|label):[a-z0-9_]+", s)] == []
    # The integration's cards are set up by the home, like in the visual editor
    own = [item for item in _walk(views) if isinstance(item, dict) and item.get("type") in OWN_CARDS]
    assert {card["type"] for card in own} == set(OWN_CARDS)
    assert all(card["device_id"] == "home_device" for card in own)
    assert not any(isinstance(item, dict) and ("$chart" in item or "$chart_card" in item) for item in _walk(views))
    assert resolver.missing_entities == set()
    assert resolver.missing_cards == set()
    assert [view["path"] for view in views] == ["tibber-prices", "tibber-prices-compact"]


@pytest.mark.unit
async def test_missing_entity_drops_only_its_card() -> None:
    """A disabled sensor removes the cards that show it, not the section around them."""
    resolver, views = await _resolve(_entities("current_interval_price"))
    text = json.dumps(views)

    assert resolver.missing_entities == {"current_interval_price"}
    assert not any(card in text for card in OWN_CARDS)
    assert "sensor.home_connection" in text  # The alert beside the now card stays


@pytest.mark.unit
async def test_missing_entity_in_visibility_drops_the_card() -> None:
    """A card whose visibility condition can't be resolved goes, instead of showing in every state."""
    _, views = await _resolve(_entities("tomorrow_data_available"))
    text = json.dumps(views)

    days = [item["day"] for item in _walk(views) if isinstance(item, dict) and "day" in item]

    assert "tomorrow" not in days  # The tab shown only once tomorrow's prices exist
    assert "today" in days
    assert "tomorrow_data_available" not in text


@pytest.mark.unit
async def test_without_tabdeck_each_tab_group_shows_its_first_tab() -> None:
    """Without TabDeck there are no tabs: the first tab's card stands in for the group."""
    resolver, views = await _resolve(cards={**dict.fromkeys(CUSTOM_CARDS, True), "tabdeck-card": False})
    types = [item.get("type") for item in _walk(views) if isinstance(item, dict)]
    days = [item["day"] for item in _walk(views) if isinstance(item, dict) and "day" in item]

    assert "custom:tabdeck-card" not in types
    assert days == ["rolling_window_autozoom"]  # Outlook, 15 minutes
    assert resolver.missing_cards == {"tabdeck-card"}


@pytest.mark.unit
async def test_without_config_template_card_rolling_charts_become_hints() -> None:
    """Rolling charts need config-template-card; fixed days still get a chart."""
    resolver, views = await _resolve(cards={**dict.fromkeys(CUSTOM_CARDS, True), "config-template-card": False})
    days = {item["day"] for item in _walk(views) if isinstance(item, dict) and "day" in item}
    hints = [s for s in _walk(views) if isinstance(s, str) and CUSTOM_CARDS["config-template-card"] in s]

    assert days == {"today", "tomorrow"}
    assert len(hints) == 4  # Outlook and 2 days, each 15 minutes and hourly
    assert resolver.missing_cards == {"config-template-card"}


@pytest.mark.unit
async def test_notification_lists_missing_parts_and_is_dismissed_when_complete() -> None:
    """Missing cards and sensors are reported once per home; a complete result clears the notice."""
    hass = MagicMock()
    hass.services.async_call = AsyncMock()
    labels = _labels("en")
    response = {
        "views": [],
        "missing_cards": {"tabdeck-card": CUSTOM_CARDS["tabdeck-card"]},
        "missing_entities": ["sensor.home_best_price_remaining_minutes"],
    }

    await _async_notify(hass, "tibber_prices_dashboard_abc", labels, response)
    domain, service, data = hass.services.async_call.call_args.args
    assert (domain, service, data["notification_id"]) == (
        "persistent_notification",
        "create",
        "tibber_prices_dashboard_abc",
    )
    assert CUSTOM_CARDS["tabdeck-card"] in data["message"]
    assert "`sensor.home_best_price_remaining_minutes`" in data["message"]

    await _async_notify(hass, "tibber_prices_dashboard_abc", labels, {"views": []})
    assert hass.services.async_call.call_args.args[:2] == ("persistent_notification", "dismiss")


@pytest.mark.unit
async def test_notification_tells_removed_and_optional_sensors_apart() -> None:
    """A removed sensor can't be enabled, an optional one left nothing out: each gets its own words."""
    hass = MagicMock()
    hass.services.async_call = AsyncMock()
    labels = _labels("en")
    response = {"views": [], "removed_entities": ["tomorrow_data_available"], "optional_entities": ["sensor.meta"]}

    await _async_notify(hass, "tibber_prices_dashboard_abc", labels, response)
    message = hass.services.async_call.call_args.args[2]["message"]

    assert labels["notification"]["removed"].split("\n")[0] in message
    assert labels["notification"]["optional"].split("\n")[0] in message
    assert labels["notification"]["entities"].split("\n")[0] not in message


@pytest.mark.unit
def test_language_is_limited_to_translated_languages() -> None:
    """Only languages with translation files are accepted; without one, the system language applies."""
    assert get_dashboard_yaml.DASHBOARD_SERVICE_SCHEMA({"language": "de"})["language"] == "de"
    assert "language" not in get_dashboard_yaml.DASHBOARD_SERVICE_SCHEMA({})
    with pytest.raises(vol.Invalid):
        get_dashboard_yaml.DASHBOARD_SERVICE_SCHEMA({"language": "fr"})


async def _resolve_charts(charts: set[str], resolutions: set[str], chart_card: str = "apexcharts") -> list[Any]:
    entities = _entities()
    resolver = _Resolver(
        MagicMock(),
        {"entry_id": "abc", "view_id": ""},
        entities,
        _labels("en"),
        dict.fromkeys(CUSTOM_CARDS, True),
        devices=dict.fromkeys(entities, "home_device"),
        charts=frozenset(charts),
        resolutions=frozenset(resolutions),
        chart_card=chart_card,
    )
    chart = AsyncMock(
        side_effect=lambda _hass, data, **_: {
            "type": "custom:apexcharts-card",
            "day": data["day"],
            "res": data["resolution"],
        }
    )
    with patch.object(get_dashboard_yaml, "async_build_apexcharts_card", chart):
        return [await resolver.resolve(view) for view in _load_template()["views"]]


def _charts(views: list[Any]) -> list[tuple[str, str]]:
    return [(item["day"], item["res"]) for item in _walk(views) if isinstance(item, dict) and "day" in item]


def _tab_names(views: list[Any]) -> list[list[str]]:
    return [
        [tab["name"] for tab in item["tabs"]]
        for item in _walk(views)
        if isinstance(item, dict) and item.get("type") == "custom:tabdeck-card"
    ]


@pytest.mark.unit
async def test_one_resolution_drops_the_resolution_switch() -> None:
    """With only hourly charts, the zoom tabs stay but each tab holds the chart directly."""
    views = await _resolve_charts(set(CHARTS), {"hourly"})

    assert {res for _, res in _charts(views)} == {"hourly"}
    assert len(_charts(views)) == 4
    assert ["15 min", "60 min"] not in _tab_names(views)
    assert ["Outlook", "Today", "Tomorrow", "2 days"] in _tab_names(views)


@pytest.mark.unit
async def test_single_chart_needs_no_tabs_and_keeps_its_visibility() -> None:
    """Only Tomorrow: no zoom tabs, and the chart still waits for tomorrow's prices."""
    views = await _resolve_charts({"tomorrow"}, {"interval"})
    chart = next(item for item in _walk(views) if isinstance(item, dict) and item.get("day") == "tomorrow")

    assert _charts(views) == [("tomorrow", "interval")]
    assert ["Outlook", "Today", "Tomorrow", "2 days"] not in _tab_names(views)
    assert chart["visibility"][0]["entity"] == "sensor.home_tomorrow_data_available"


@pytest.mark.unit
async def test_no_charts_drops_the_chart_section() -> None:
    """Without charts the section that held them goes, the others stay."""
    views = await _resolve_charts(set(), set(RESOLUTIONS))

    assert _charts(views) == []
    assert all(section["cards"] for view in views for section in view["sections"])
    assert len(views[0]["sections"]) == 2  # verdict, course of the day


def _chart_cards(views: list[Any]) -> list[dict[str, Any]]:
    return [item for item in _walk(views) if isinstance(item, dict) and item.get("type") == CHART_CARD]


@pytest.mark.unit
async def test_chart_card_by_default_needs_no_custom_cards() -> None:
    """By default the integration's chart card draws the charts: no ApexCharts, no tabs, nothing to install."""
    resolver, views = await _resolve(cards=dict.fromkeys(CUSTOM_CARDS, False), chart_card=CHART_CARDS[0])
    types = {item.get("type") for item in _walk(views) if isinstance(item, dict)}
    (card,) = _chart_cards(views)

    assert CHART_CARDS[0] == "tibber_prices"
    assert "custom:tabdeck-card" not in types
    assert not any(isinstance(item, dict) and "day" in item for item in _walk(views))
    assert card["device_id"] == "home_device"
    assert card["views"] == list(CHARTS)
    # Until tomorrow's prices are in, Yesterday stands in for Tomorrow
    assert card["tomorrow_pending"] == "yesterday"
    # The template's styles stay, the resolution asked for joins them
    assert card["all_views"]["resolution"] == "switch"
    assert card["all_views"]["style_switch"] is True
    assert resolver.missing_cards == set()
    assert resolver.optional_entities == set()


@pytest.mark.unit
@pytest.mark.parametrize(
    ("resolutions", "resolution"),
    [({"interval"}, "quarter_hour"), ({"hourly"}, "hour"), (set(RESOLUTIONS), "switch")],
)
async def test_chart_card_takes_charts_and_resolutions(resolutions: set[str], resolution: str) -> None:
    """The chart card offers the charts asked for, in the template's order, and their resolutions."""
    views = await _resolve_charts({"two_days", "today"}, resolutions, chart_card="tibber_prices")
    (card,) = _chart_cards(views)

    assert card["views"] == ["today", "two_days"]
    assert card["all_views"]["resolution"] == resolution


@pytest.mark.unit
async def test_chart_card_without_charts_drops_the_chart_section() -> None:
    """No charts asked for: the chart card's section goes, like the ApexCharts one."""
    views = await _resolve_charts(set(), set(RESOLUTIONS), chart_card="tibber_prices")

    assert _chart_cards(views) == []
    assert len(views[0]["sections"]) == 2


@pytest.mark.unit
async def test_charts_leave_notifying_to_this_action() -> None:
    """Each chart is built without the ApexCharts action's own notifications (one report at the end)."""
    resolver = _Resolver(
        MagicMock(),
        {"entry_id": "abc", "view_id": ""},
        {key: f"sensor.home_{key}" for key in ENTITY_KEYS},
        _labels("en"),
        dict.fromkeys(CUSTOM_CARDS, True),
        devices={},
    )
    chart = AsyncMock(return_value={"type": "custom:apexcharts-card"})
    with patch.object(get_dashboard_yaml, "async_build_apexcharts_card", chart):
        await resolver.chart({"$chart": "today"})

    assert chart.call_args.kwargs["notify"] is False
    # Without the Chart Metadata sensor the chart still comes: the report names the sensor as
    # optional, not as one whose cards were left out
    assert resolver.optional_entities == {CHART_METADATA_KEY}
    assert resolver.missing_entities == set()


@pytest.mark.unit
def test_labels_fall_back_to_english_text_by_text() -> None:
    """A language lacking one notification text keeps the others and takes English for that one."""
    english = {"title": "Dashboard", "notification": {"title": "T", "entities": "E", "cards": "C"}}
    german = {"title": "Übersicht", "notification": {"title": "Titel", "cards": "Karten"}}

    assert _merged(english, german) == {
        "title": "Übersicht",
        "notification": {"title": "Titel", "entities": "E", "cards": "Karten"},
    }


@pytest.mark.unit
async def test_enabled_sensor_without_device_is_not_reported_as_missing() -> None:
    """A card set up by the device goes when the sensor has none, without asking to enable it."""
    resolver, views = await _resolve(devices={})

    assert not any(isinstance(item, dict) and item.get("type") in OWN_CARDS for item in _walk(views))
    assert resolver.missing_entities == set()


@pytest.mark.unit
async def test_single_tab_keeps_its_cards_own_visibility() -> None:
    """A tab group reduced to one card: the card shows only where both the tab and the card allow it."""
    resolver = _Resolver(
        MagicMock(), {"entry_id": "abc", "view_id": ""}, {}, {}, dict.fromkeys(CUSTOM_CARDS, True), devices={}
    )
    tab_condition = {"condition": "state", "entity": "binary_sensor.tomorrow", "state": "on"}
    card_condition = {"condition": "screen", "media_query": "(min-width: 600px)"}
    card = await resolver.tabdeck(
        {
            "tabs": [
                {
                    "name": "Tomorrow",
                    "visibility": [tab_condition],
                    "card": {"type": "markdown", "visibility": [card_condition]},
                }
            ]
        }
    )

    assert card["visibility"] == [tab_condition, card_condition]


def _compact_now_cards(views: list[Any]) -> list[dict[str, Any]]:
    (compact,) = [view for view in views if view["path"] == "tibber-prices-compact"]
    return [item for item in _walk(compact) if isinstance(item, dict) and item.get("type") == OWN_CARDS[1]]


@pytest.mark.unit
async def test_compact_view_opens_the_chart_card_in_a_window() -> None:
    """The compact view's now card opens the chart card from its icon, with the charts asked for."""
    views = await _resolve_charts({"today", "tomorrow"}, {"interval"}, chart_card=CHART_CARDS[0])
    (card,) = _compact_now_cards(views)

    assert card["tap_opens"] == "forecast"
    assert card["chart_button"] is True
    assert card["chart"] == {
        "tomorrow_pending": "yesterday",
        "views": ["today", "tomorrow"],
        "all_views": {"resolution": "quarter_hour"},
    }
    assert not any(isinstance(item, dict) and "$chart_into" in item for item in _walk(views))


@pytest.mark.unit
async def test_compact_view_without_chart_card() -> None:
    """With ApexCharts for the charts, or no charts at all, the now card stays, without the icon."""
    for views in (
        await _resolve_charts({"today"}, {"interval"}, chart_card="apexcharts"),
        await _resolve_charts(set(), {"interval"}, chart_card=CHART_CARDS[0]),
    ):
        (card,) = _compact_now_cards(views)
        assert card["tap_opens"] == "forecast"
        assert "chart_button" not in card
        assert "chart" not in card
