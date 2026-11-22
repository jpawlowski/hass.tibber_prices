# UX patterns — implementation

For [`ha-user-experience`](../SKILL.md). Each pattern: what it is, what it costs, and the minimum code. Check every
API named here against the installed Home Assistant source before relying on it.

## Ordinal beside an enum

The state stays the translated enum; an attribute carries a number an automation can compare.

```python
_LEVEL_ORDER = {"very_low": -2, "low": -1, "normal": 0, "high": 1, "very_high": 2}

@property
def extra_state_attributes(self) -> dict[str, Any]:
    level = self.native_value
    return {"level_value": _LEVEL_ORDER.get(level) if level is not None else None}
```

An automation then uses a `numeric_state` trigger or condition with `attribute: level_value` and `above: 0`,
instead of listing values; while the value is `None`, it simply does not match. Keep the mapping in one place and
never renumber it — automations depend on the numbers.

## Timestamp and minutes-until

For an upcoming event, `next_start` as an ISO 8601 timestamp (a `TIMESTAMP` sensor or an attribute) is the default:
it changes only when the event moves, and a template or `time` trigger can test against it. A
`next_start_in_minutes` value for a numeric-state trigger costs a timer and a state write every minute, unrecorded or
not — offer it as its own disabled-by-default sensor, never as an attribute on an entity that otherwise changes
rarely.

## Units without a converter

```python
from homeassistant.const import CURRENCY_EURO, UnitOfEnergy

# const.py — main and subunit symbol per ISO 4217 code
CURRENCY_SYMBOLS: dict[str, tuple[str, str]] = {"EUR": (CURRENCY_EURO, "ct"), "NOK": ("kr", "øre")}


def price_unit(currency: str, *, subunit: bool) -> str:
    main, sub = CURRENCY_SYMBOLS.get(currency, (currency, currency))
    return f"{sub if subunit else main}/{UnitOfEnergy.KILO_WATT_HOUR}"
```

- `hass.config.currency` (or the account's currency from the API) is an ISO 4217 code, not a symbol. Home Assistant
  has constants for a few symbols (`CURRENCY_EURO`, `CURRENCY_DOLLAR`, `CURRENCY_CENT`) and none for most subunits;
  keep the mapping in one place and fall back to the code.
- Scale the value in the same place the unit is chosen (`price * 100` for the subunit), so the two never disagree.
- The option changes the state value and the unit together — a breaking change for recorded statistics once
  released. Decide the default before the first release.
- The energy dashboard entity is a separate one, disabled by default, and stays in the main unit whatever the option
  says
  (`homeassistant/components/energy/sensor.py`, `_get_energy_price`, ignores the currency part of the unit).

## Color hints

```python
_LEVEL_COLOR = {"low": "var(--success-color)", "high": "var(--warning-color)", "very_high": "var(--error-color)"}
_unrecorded_attributes = frozenset({"icon_color"})
```

- Theme variables only; a hex value ignores the user's theme and dark mode.
- `icon_color` is a community convention for card templates, not a Home Assistant attribute. Say so in the
  documentation, and do not rely on it for meaning — the state and the icon carry that.

## Context in a form

A description placeholder can carry text that depends on the user's setup. Compute it in the step, and keep an
empty string when nothing applies, so the translation still reads.

```python
placeholders = {"entity_warning": ""}
if not any(_is_enabled(self.hass, uid) for uid in affected_unique_ids):
    placeholders["entity_warning"] = await _translated(self.hass, "entity_warning", names=...)
return self.async_show_form(step_id="pricing", data_schema=schema, description_placeholders=placeholders)
```

The translation holds `{entity_warning}` in the step `description`. Every language needs the same placeholder set
([`blueprint.translations`](../../../instructions/blueprint.translations.instructions.md)).

## Entity descriptions

Home Assistant has no "what is this entity for" slot, and the translation files have no key for it. The workaround:

- The integration's own JSON per language beside `translations/` (for example `custom_translations/<lang>.json`),
  loaded once in the executor and cached — not read on every state write.
- A `description` attribute from it in `hass.config.language`, falling back to English; an option switches to a long
  form plus usage tips.
- All of them in `_unrecorded_attributes`.

Costs to state plainly: the text follows the server's language, not each user's; it is a second translation set to
keep complete; and the frontend shows it only as an attribute.

## Menu-based options flow

```python
class {ClassPrefix}OptionsFlow(config_entries.OptionsFlowWithReload):
    def __init__(self) -> None:
        self._options: dict[str, Any] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        if not self._options:
            self._options = dict(self.config_entry.options)
        return self.async_show_menu(step_id="init", menu_options=["general", "notifications", "save"])

    async def async_step_general(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_init()
        return self.async_show_form(step_id="general", data_schema=..., description_placeholders=...)

    async def async_step_save(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        return self.async_create_entry(data=self._options)
```

- Each topic step returns to the menu; only `save` stores. Nothing is written when the user closes the dialog.
- `menu_option_descriptions` under `options.step.init` (an options flow translates under `options`, not `config`)
  explains each entry; a "reset to defaults" entry is cheap to
  add and saves support questions.
- A `section()` nests its data under the section key — merge it back accordingly
  ([`blueprint.config_flow`](../../../instructions/blueprint.config_flow.instructions.md)).

## Settings automations can change

- One entity per setting, `EntityCategory.CONFIG`, disabled by default, on the platform that fits (`number`,
  `switch`, `select`).
- While the entity is enabled, its value wins over the option; the coordinator reads the effective value from one
  helper, so entities and options never disagree in code.
- The options form says which fields an entity currently controls, through a description placeholder — the user
  otherwise edits a field that has no effect.

## Response data

```python
return {
    "currency": "EUR",
    "intervals": [
        {"start": start.isoformat(), "end": end.isoformat(), "price": 0.231},
    ],
}
```

- Lists of objects with the same keys; timestamps through `.isoformat()`; the unit once at the top or in the key.
- If both a compact and a verbose shape are useful (a chart wants arrays, a template objects), add an explicit
  `output_format` parameter instead of guessing.
- `SupportsResponse.OPTIONAL`: check `call.return_response` and skip the work of building data nobody asked for.
- Document the shape where users look — the action's description and `docs/user/` — because automations are built
  against it.

## Shipped cards

```python
async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    await hass.http.async_register_static_paths(
        [StaticPathConfig(f"/{DOMAIN}/cards", str(Path(__file__).parent / "frontend"), cache_headers=True)]
    )
    add_extra_js_url(hass, f"/{DOMAIN}/cards/{DOMAIN}-cards.js?v={VERSION}")
    return True
```

- `async_setup()`, not `async_setup_entry()`: it runs once per start. Per entry, a second registration of the same
  route raises and the script URL is added twice.
- `"dependencies": ["frontend", "http"]` in `manifest.json`: `add_extra_js_url` writes into data the `frontend`
  setup creates, and fails with a `KeyError` before it.
- The version in the URL busts the browser cache after an update.
- The cards are JavaScript the integration now maintains, with its own translations and editor — a project in its own
  right. Bundle them in `script/hooks/build.post.sh` rather than committing the bundle
  ([build hook](../../blueprint-tooling/references/hooks.md#the-build-hook)).

## Shipped blueprints

Home Assistant's own `async_populate` copies an integration's blueprints only when the target folder does not exist.
Follow that: copy a file only when it is missing, or when it still matches a copy the integration shipped earlier
(compare a hash). Overwriting on every start discards whatever the user changed. Write in the executor, not in the
event loop.
