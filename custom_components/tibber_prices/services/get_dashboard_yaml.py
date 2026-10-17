"""
Dashboard YAML generation service handler.

`tibber_prices.get_dashboard_yaml` returns a dashboard view for one home as a starting point:
users paste it into one of their own dashboards and adapt them from there. Nothing is
written to any dashboard, and nothing changes on its own after an update - calling the
action again gives the current version.

The view comes from dashboard_template.yaml; its placeholders are resolved here:
entities by translation key (so the template works in any language), the device of such an
entity (`device:<key>`, for cards set up by the home, like the forecast card), labels from the
`dashboard` area of custom_translations, chart cards from get_apexcharts_yaml.

Service: tibber_prices.get_dashboard_yaml
Response: {"views": [...]} plus, where something is missing, `missing_entities` (disabled sensors
whose cards were left out), `removed_entities` (sensors gone from the registry), `optional_entities`
(sensors the views work without, but better with) and `missing_cards` (custom cards to install)
"""

from __future__ import annotations

import logging
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any, Final

import voluptuous as vol
import yaml

from custom_components.tibber_prices.const import (
    DOMAIN,
    TRANSLATION_LANGUAGES,
    async_load_translations,
    get_translation,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .get_apexcharts_yaml import CUSTOM_CARDS, async_build_apexcharts_card, check_custom_cards_installed
from .helpers import resolve_service_target

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall

    from .helpers import ServiceTarget

DASHBOARD_YAML_SERVICE_NAME: Final = "get_dashboard_yaml"

TEMPLATE_PATH: Final = Path(__file__).parent / "dashboard_template.yaml"

# The sensor the charts read their scale from (they work without it)
CHART_METADATA_KEY: Final = "chart_metadata"

# Chart name in the template -> `day` of get_apexcharts_yaml; a "_hourly" suffix asks for hourly resolution
CHARTS: Final = {
    "outlook": "rolling_window_autozoom",
    "today": "today",
    "tomorrow": "tomorrow",
    "two_days": "rolling_window",
}

RESOLUTIONS: Final = ("interval", "hourly")

DASHBOARD_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id", default=""): cv.string,
        vol.Optional("view_id", default=""): cv.string,
        # Default: every chart, each with both resolutions (switchable in the card)
        vol.Optional("charts", default=list(CHARTS)): vol.All(cv.ensure_list, [vol.In(list(CHARTS))]),
        vol.Optional("chart_resolutions", default=list(RESOLUTIONS)): vol.All(
            cv.ensure_list, [vol.In(list(RESOLUTIONS))]
        ),
        vol.Optional("language"): vol.In(TRANSLATION_LANGUAGES),
    }
)

INLINE = re.compile(r"\[\[(entity|device|label):([a-z0-9_]+)\]\]")
WHOLE = re.compile(r"(entity|device|label):([a-z0-9_]+)")

# A missing entity in a visibility condition drops the card, not just the condition:
# without it the card would show in every state
_STRICT_LISTS: Final = frozenset({"visibility", "conditions"})


class _DroppedError(Exception):
    """This node is left out; the nearest enclosing list drops the item that contains it."""


class _MissingEntityError(_DroppedError):
    """A placeholder names an entity the home doesn't have (disabled or removed)."""


class _Resolver:
    """Resolve the template's placeholders for one home."""

    def __init__(
        self,
        hass: HomeAssistant,
        chart_data: dict[str, Any],
        entities: dict[str, str],
        labels: dict[str, str],
        installed_cards: dict[str, bool],
        *,
        devices: dict[str, str],
        charts: frozenset[str] = frozenset(CHARTS),
        resolutions: frozenset[str] = frozenset(RESOLUTIONS),
        target: ServiceTarget | None = None,
    ) -> None:
        self.hass = hass
        # The home, resolved once for all charts (None: each chart resolves it from chart_data)
        self.target = target
        self.charts = charts
        self.resolutions = resolutions
        self.chart_data = chart_data
        self.entities = entities
        self.devices = devices
        self.labels = labels
        self.installed_cards = installed_cards
        self.missing_entities: set[str] = set()
        # Sensors nothing is left out without, though they help (the charts' scale)
        self.optional_entities: set[str] = set()
        self.missing_cards: set[str] = set()

    def lookup(self, kind: str, key: str) -> str:
        """Return the entity ID, its device's ID or the label for a placeholder key."""
        if kind == "label":
            return self.labels[key]  # KeyError: template and translations out of sync
        found = self.devices if kind == "device" else self.entities
        if key not in found:
            # An enabled sensor without a device isn't one to enable: leave its card out quietly
            # instead of telling the user to enable it
            if kind == "device" and key in self.entities:
                _LOGGER.warning("%s has no device; the cards set up by its device are left out", self.entities[key])
            else:
                self.missing_entities.add(key)
            raise _MissingEntityError(key)
        return found[key]

    def string(self, value: str) -> str:
        """Resolve a whole-string placeholder or the inline ones inside a string."""
        if match := WHOLE.fullmatch(value):
            return self.lookup(match.group(1), match.group(2))
        return INLINE.sub(lambda match: self.lookup(match.group(1), match.group(2)), value)

    async def resolve(self, node: Any, key: str | None = None) -> Any:
        """Resolve placeholders anywhere in a parsed YAML node."""
        if isinstance(node, dict):
            if "$chart" in node:
                return await self.chart(node)
            if node.get("type") == "custom:tabdeck-card":
                return await self.tabdeck(node)
            resolved = {name: await self.resolve(value, name) for name, value in node.items()}
            # A section or stack with nothing left in it goes as well
            if node.get("cards") and not resolved["cards"]:
                raise _DroppedError
            return resolved
        if isinstance(node, list):
            items = []
            for item in node:
                try:
                    items.append(await self.resolve(item))
                except _DroppedError:
                    if key in _STRICT_LISTS:
                        raise
            return items
        if isinstance(node, str):
            return self.string(node)
        return node

    async def tabdeck(self, node: dict[str, Any]) -> dict[str, Any]:
        """
        Resolve a tab group, leaving out tabs whose content was dropped.

        One tab left needs no tab bar: its card stands alone. Without TabDeck, the first
        tab that remains stands in for the group.
        """
        installed = self.installed_cards["tabdeck-card"]
        tabs = []
        for tab in node["tabs"]:
            try:
                tabs.append(await self.resolve(tab))
            except _DroppedError:
                continue
            if not installed:
                break
        if not tabs:
            raise _DroppedError
        if len(tabs) == 1:
            if not installed and len(node["tabs"]) > 1:
                self.missing_cards.add("tabdeck-card")
            card = tabs[0]["card"]
            if "visibility" in tabs[0]:  # e.g. Tomorrow only once its prices exist
                # Both must hold: the tab's conditions and the card's own (a list means "and")
                card["visibility"] = [*tabs[0]["visibility"], *card.get("visibility", [])]
            return card
        return {
            **{name: await self.resolve(value, name) for name, value in node.items() if name != "tabs"},
            "tabs": tabs,
        }

    async def chart(self, node: dict[str, Any]) -> dict[str, Any]:
        """Build a chart card with get_apexcharts_yaml, or a hint if its cards are missing."""
        name: str = node["$chart"]
        resolution = "hourly" if name.endswith("_hourly") else "interval"
        chart = name.removesuffix("_hourly")
        if chart not in self.charts or resolution not in self.resolutions:
            raise _DroppedError
        day = CHARTS[chart]
        # Rolling modes wrap the ApexCharts card in a config-template-card
        needed = ["apexcharts-card"] + (["config-template-card"] if day.startswith("rolling_window") else [])
        if missing := [card for card in needed if not self.installed_cards[card]]:
            self.missing_cards.update(missing)
            card = self.missing_card_hint(missing)
        else:
            # Its own notifications stay off: this action reports what's missing once, below
            card = await async_build_apexcharts_card(
                self.hass,
                {
                    **self.chart_data,
                    "day": day,
                    "resolution": resolution,
                    # Price level, so the chart colors match the verdict above it
                    "level_type": "level",
                    "highlight_best_price": True,
                    "highlight_peak_price": True,
                },
                notify=False,
                target=self.target,
            )
            # The charts work without the Chart Metadata sensor, but scale better with it
            if CHART_METADATA_KEY not in self.entities:
                self.optional_entities.add(CHART_METADATA_KEY)
            if node.get("hide_title"):
                card.get("card", card).setdefault("header", {})["show"] = False
        # Custom cards default to half a section; charts should use its full width
        card["grid_options"] = {"columns": "full"}
        if "visibility" in node:
            card["visibility"] = await self.resolve(node["visibility"], "visibility")
        return card

    def missing_card_hint(self, cards: list[str]) -> dict[str, Any]:
        """Markdown card that names the custom cards to install, with their HACS links."""
        links = ", ".join(f'<a href="{CUSTOM_CARDS[card]}">{card}</a>' for card in cards)
        text = self.labels["missing_card"].format(card=links)
        return {"type": "markdown", "text_only": True, "content": f'<ha-alert alert-type="warning">{text}</ha-alert>'}


async def handle_dashboard_yaml(call: ServiceCall) -> dict[str, Any]:
    """
    Return the dashboard view for one home, ready to paste into a dashboard.

    See services.yaml for detailed parameter documentation.

    Raises:
        ServiceValidationError: If the home can't be resolved, or the view is headless

    """
    hass = call.hass
    target = resolve_service_target(hass, call.data.get("entry_id", ""), call.data.get("view_id", ""))
    # Every card references entities; a headless view has none
    if target.coordinator.headless:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="headless_view_has_no_entities")

    # Labels in the requested language, else the system language (not the viewer's profile language)
    language = call.data.get("language") or hass.config.language or "en"
    await async_load_translations(hass, "en")
    await async_load_translations(hass, language)
    # English fills whatever the language lacks, nested texts (the notification) included
    labels = _merged(get_translation(["dashboard"], "en") or {}, get_translation(["dashboard"], language) or {})

    subentry_id = target.subentry.subentry_id if target.subentry else None
    home_entries = {
        entity.translation_key: entity
        for entity in er.async_entries_for_config_entry(er.async_get(hass), target.entry.entry_id)
        if entity.config_subentry_id == subentry_id and entity.translation_key
    }
    # translation_key -> (entity_id, disabled)
    registry_entries = {key: (entity.entity_id, entity.disabled_by is not None) for key, entity in home_entries.items()}
    entities = {key: entity_id for key, (entity_id, disabled) in registry_entries.items() if not disabled}
    devices = {key: entity.device_id for key, entity in home_entries.items() if key in entities and entity.device_id}

    template = await hass.async_add_executor_job(_load_template)
    resolver = _Resolver(
        hass,
        {"entry_id": target.entry.entry_id, "view_id": call.data.get("view_id", ""), "language": language},
        entities,
        labels,
        check_custom_cards_installed(hass),
        devices=devices,
        charts=frozenset(call.data.get("charts", list(CHARTS))),
        resolutions=frozenset(call.data.get("chart_resolutions", list(RESOLUTIONS))),
        target=target,
    )
    views = [await resolver.resolve(view) for view in template["views"]]

    response: dict[str, Any] = {"views": views}
    # Disabled sensors by entity ID, so they can be found and enabled; removed ones (gone from the
    # registry, back after reloading the integration) by their key, as they have no ID to find
    lists = {
        "missing_entities": [registry_entries[key][0] for key in resolver.missing_entities if key in registry_entries],
        "removed_entities": [key for key in resolver.missing_entities if key not in registry_entries],
        "optional_entities": [registry_entries.get(key, (key,))[0] for key in resolver.optional_entities],
    }
    response.update({name: sorted(items) for name, items in lists.items() if items})
    if resolver.missing_cards:
        response["missing_cards"] = {card: CUSTOM_CARDS[card] for card in sorted(resolver.missing_cards)}
    await _async_notify(hass, f"tibber_prices_dashboard_{target.entry.entry_id}", labels, response)
    return response


async def _async_notify(hass: HomeAssistant, notification_id: str, labels: dict[str, Any], response: dict) -> None:
    """
    Tell the user what the views are missing, like get_apexcharts_yaml does.

    One notification per home: calling the action again replaces it, or dismisses it once
    nothing is missing any more.
    """
    texts = labels["notification"]
    parts = []
    if cards := response.get("missing_cards"):
        parts.append(texts["cards"].format(cards="\n".join(f"- [{card}]({url})" for card, url in cards.items())))
    for name, text in (
        ("missing_entities", "entities"),
        ("removed_entities", "removed"),
        ("optional_entities", "optional"),
    ):
        if entities := response.get(name):
            parts.append(texts[text].format(entities="\n".join(f"- `{entity}`" for entity in entities)))
    if not parts:
        await hass.services.async_call("persistent_notification", "dismiss", {"notification_id": notification_id})
        return
    await hass.services.async_call(
        "persistent_notification",
        "create",
        {
            "title": texts["title"],
            "message": "\n\n".join([texts["intro"], *parts]),
            "notification_id": notification_id,
        },
    )


def _merged(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Return `base` with `override` laid over it, dict by dict (a nested text set stays whole)."""
    result = dict(base)
    for key, value in override.items():
        result[key] = (
            _merged(result[key], value) if isinstance(value, dict) and isinstance(result.get(key), dict) else value
        )
    return result


def _load_template() -> dict[str, Any]:
    """Read the dashboard template (blocking, run in the executor)."""
    return yaml.safe_load(TEMPLATE_PATH.read_text(encoding="utf-8"))
