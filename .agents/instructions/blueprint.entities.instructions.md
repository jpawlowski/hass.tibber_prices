---
name: "Entity Platforms"
description: "Entity descriptions, translation keys, device registry ownership, and platform members"
applyTo: "custom_components/**/alarm_control_panel/**/*.py, custom_components/**/binary_sensor/**/*.py, custom_components/**/button/**/*.py, custom_components/**/camera/**/*.py, custom_components/**/climate/**/*.py, custom_components/**/cover/**/*.py, custom_components/**/date/**/*.py, custom_components/**/datetime/**/*.py, custom_components/**/device_tracker/**/*.py, custom_components/**/event/**/*.py, custom_components/**/fan/**/*.py, custom_components/**/humidifier/**/*.py, custom_components/**/image/**/*.py, custom_components/**/lawn_mower/**/*.py, custom_components/**/light/**/*.py, custom_components/**/lock/**/*.py, custom_components/**/media_player/**/*.py, custom_components/**/notify/**/*.py, custom_components/**/number/**/*.py, custom_components/**/scene/**/*.py, custom_components/**/select/**/*.py, custom_components/**/sensor/**/*.py, custom_components/**/siren/**/*.py, custom_components/**/switch/**/*.py, custom_components/**/text/**/*.py, custom_components/**/time/**/*.py, custom_components/**/todo/**/*.py, custom_components/**/update/**/*.py, custom_components/**/vacuum/**/*.py, custom_components/**/valve/**/*.py, custom_components/**/water_heater/**/*.py, custom_components/**/entity/**/*.py, custom_components/**/entity_utils/**/*.py"
paths:
  - "custom_components/**/alarm_control_panel/**/*.py"
  - "custom_components/**/binary_sensor/**/*.py"
  - "custom_components/**/button/**/*.py"
  - "custom_components/**/camera/**/*.py"
  - "custom_components/**/climate/**/*.py"
  - "custom_components/**/cover/**/*.py"
  - "custom_components/**/date/**/*.py"
  - "custom_components/**/datetime/**/*.py"
  - "custom_components/**/device_tracker/**/*.py"
  - "custom_components/**/event/**/*.py"
  - "custom_components/**/fan/**/*.py"
  - "custom_components/**/humidifier/**/*.py"
  - "custom_components/**/image/**/*.py"
  - "custom_components/**/lawn_mower/**/*.py"
  - "custom_components/**/light/**/*.py"
  - "custom_components/**/lock/**/*.py"
  - "custom_components/**/media_player/**/*.py"
  - "custom_components/**/notify/**/*.py"
  - "custom_components/**/number/**/*.py"
  - "custom_components/**/scene/**/*.py"
  - "custom_components/**/select/**/*.py"
  - "custom_components/**/sensor/**/*.py"
  - "custom_components/**/siren/**/*.py"
  - "custom_components/**/switch/**/*.py"
  - "custom_components/**/text/**/*.py"
  - "custom_components/**/time/**/*.py"
  - "custom_components/**/todo/**/*.py"
  - "custom_components/**/update/**/*.py"
  - "custom_components/**/vacuum/**/*.py"
  - "custom_components/**/valve/**/*.py"
  - "custom_components/**/water_heater/**/*.py"
  - "custom_components/**/entity/**/*.py"
  - "custom_components/**/entity_utils/**/*.py"
---

# Entity Platform Instructions

**Procedure:** [`ha-entity-platform`](../skills/ha-entity-platform/SKILL.md) — load it before adding a platform or an
entity. This file is the rule set; the skill is the order the layers get built in and the decisions that rule set
assumes have already been made.

**Applies to:** All entity platform implementations (sensor, binary_sensor, switch, etc.), entity base classes, and entity utilities

## Shared Infrastructure

- **`entity/`** - Base entity classes (inherit the integration's base entity class from `entity/base.py`)
- **`entity_utils/`** - Shared utilities (device info, state helpers) used by 3+ entity classes
- **`coordinator/`** - Data fetching (entities never call API directly)

## Base Entity Inheritance

**MUST inherit from:** `(PlatformEntity, {ClassPrefix}Entity)` — the integration's base entity class from `..entity`, order matters for MRO

**Base class provides:** Coordinator integration, device info, unique ID (`{entry_id}_{description.key}`), attribution, entity naming

`{entry_id}_{key}` is the documented **unique ID of last resort**. If the device or account exposes a serial, MAC or
account ID, switch to it **before the first release** — afterwards it is a breaking change needing a registry
migration ([`ha-breaking-changes`](../skills/ha-breaking-changes/SKILL.md)).

**You implement:** Platform-specific properties/methods (`native_value`, `is_on`, `async_press`, etc.)

**Imports pattern:** `from homeassistant.components.PLATFORM import PlatformEntity, PlatformEntityDescription` + `from custom_components.<domain>.entity import {ClassPrefix}Entity` — absolute, because Ruff rejects a relative import that reaches into a parent package (`blueprint.python`)

**Constructor:** Call `super().__init__(coordinator, entity_description)` - base handles setup

## Entity Descriptions

**Define at module level:** `ENTITY_DESCRIPTIONS: tuple[PlatformEntityDescription, ...]`

**Required fields:**

- `key` - Used in unique_id, must match coordinator data key. Never rename it after release.
- `translation_key` - Entity name comes from `translations/en.json`. **NEVER set `name=` to a translatable
  string** — the base entity sets `_attr_has_entity_name = True`, and a hardcoded name breaks localisation (quality
  scale `entity-translations`). Exceptions:
  - A name that is the same in every language — a proper noun, a model name, or a name the device or its library
    reports (a channel the user named in the vendor app) — is set with `name=` / `_attr_name` directly.
  - On `binary_sensor`, `button`, `event`, `number`, `sensor` and `update`, an entity whose `device_class` already
    produces the wanted name needs **no** `translation_key` — a `SensorDeviceClass.TEMPERATURE` sensor is named
    "Temperature" by itself. Adding one only creates a redundant key for translators. Not for
    `SensorDeviceClass.ENUM`, which is never named after its device class.
  - The entity that **is** the device's main feature (the light of a bulb, the fan of a purifier) sets `name=None`
    on its description, or `_attr_name = None` on the class. `friendly_name` then becomes the device name alone and
    the entity id is `<platform>.<device_name>` — without it the UI reads "Air Purifier Air Purifier".
- **`friendly_name` is legacy output, not an input.** Home Assistant computes it for compatibility
  (`async_get_legacy_friendly_name` in `helpers/entity_registry.py`); the frontend names entities from the registry —
  entity name, device, area (`formatEntityName`, 2026.4). Never set it, read it, or put the device or area name into
  an entity name — the frontend adds that context itself.
- Platform-specific: `device_class`, `state_class`, `native_unit_of_measurement`, `options`, etc.
- **Set `device_class` whenever one fits** - drives unit conversion, icons and voice assistants.
- **Set `state_class` on every numeric measurement or total** - without it there are no long-term statistics. A
  forecast, a value for a future time or a snapshot takes none. The allowed
  state classes and units per device class are `DEVICE_CLASS_STATE_CLASSES` and `DEVICE_CLASS_UNITS` in the installed
  `sensor/const.py` — meters never take `MEASUREMENT`, and some device classes take no state class at all. See
  [`sensors.md`](../skills/ha-entity-platform/references/sensors.md).
- A unit that is a word ("steps") is a translated unit, not a `native_unit_of_measurement` — see
  [`ha-translations`](../skills/ha-translations/SKILL.md).
- **NEVER set `icon=`** - icons belong in `icons.json` (quality scale `icon-translations`), including icons that
  follow the entity's own state (`state`, `range`). The one exception is an `icon` property whose icon depends on
  more than that state — the time, another value, a combination. It overrides `icons.json` and is written into
  every stored state.

**Value extraction:** Subclass the description dataclass with a `value_fn` rather than branching on `key` in the entity:

```python
@dataclass(frozen=True, kw_only=True)
class {ClassPrefix}SensorEntityDescription(SensorEntityDescription):
    """Describes a sensor and how to read it from coordinator data."""

    value_fn: Callable[[dict[str, Any]], StateType]
```

### Entity Categories

- `None` - What someone has the device or service for: its readings, its controls, the data it exists to deliver
- `EntityCategory.DIAGNOSTIC` - Information about the device or the integration itself, not about what it measures:
  signal strength, uptime, firmware, IP address, battery, last successful update, API or connection status, data
  age. Also an identify button.
- `EntityCategory.CONFIG` - An entity that changes a device setting, or an integration setting automations need to
  change — then disabled by default, and the options flow shows which fields it currently controls. `sensor` and
  `binary_sensor` **cannot** use it — adding one raises. `update` defaults to `CONFIG` without being told.

The test is what the value is **about**, not how often it is wanted: a secondary reading of the thing the device
measures stays primary — disabled by default if few need it — and is never made diagnostic to hide it. A category
leaves the entity out of auto-generated dashboards, out of voice assistants by default, and out of actions that
target a whole device or area (`primary_entities_only` in `helpers/target.py`); its state, history and triggers are
unaffected. Category and enabled-by-default are independent choices.

## Platform Setup

**Pattern:** `async_setup_entry()` creates entities from descriptions

- Import entity classes + DESCRIPTIONS from submodules
- Generator: `async_add_entities(EntityClass(entry.runtime_data.coordinator, desc) for desc in DESCRIPTIONS)`
- Combine multiple entity types in one platform
- Access coordinator: `entry.runtime_data.coordinator`

## Coordinator Data Access

**MUST use coordinator only:** `self.coordinator.data.get(self.entity_description.key)`

**NEVER call API directly:** No `self.coordinator.client` or `await api_call()` in entities

**Missing data is `unknown`, not `unavailable`.** The two are not interchangeable: `unavailable` hides the entity and
breaks templates that read its state, so it is only correct when the thing behind the entity is genuinely gone.

- The poll succeeded but one field is absent → return `None` from `native_value` / `is_on`. The state becomes
  `unknown` and the entity stays usable.
- The whole device or channel is gone → override `available`. Only do this when a missing key really means a missing
  sub-device; the base `CoordinatorEntity` already covers the whole-device case.
- A device in standby → `off` when Home Assistant can still turn it on (Wake-on-LAN, a power command over another
  connection); `unavailable` when nothing in Home Assistant can reach it.

**State limits:** a state is at most 255 characters — a longer one is logged as an error and replaced by `unknown`.
Long text belongs in an attribute or a different kind of entity.

## File Organization

**Group related entities:** `primary_entities.py`, `diagnostic.py`, `configuration.py`

**Split when:** Complex entity >100 lines → one file per entity class

## Custom State Attributes

**Entity or attribute — decide in this order:**

1. The value changes on its own, needs history or statistics, the energy dashboard, or is something users trigger
   on → **its own entity**.
2. It explains or uses the current state — when a period starts and ends, the source of a reading, a list a card
   draws that no 255-character state can hold → **an attribute**.
3. It is large, static, or changes on every update without meaning → an attribute in `_unrecorded_attributes`, or
   nothing.

Every attribute is written to the recorder on every state change unless it is excluded, so a frequently changing
attribute on a frequently changing entity multiplies database growth.

**Implementation:** use the `extra_state_attributes` property returning a dict, and exclude the volatile
ones from history with a **class-level** `_unrecorded_attributes: frozenset[str]` (instance attributes are ignored).
`MATCH_ALL` excludes everything except `device_class`, `state_class`, `unit_of_measurement` and `friendly_name`.

- **Attributes do not come and go.** An attribute the entity supports is always in the dict, with `None` while it has
  no value; one it does not support is absent. Never drop a key because this poll lacked it.
- Static facts — firmware, serial number, model — belong in the device info, not in an attribute.
- The recorder drops **all** attributes of a state, with a warning, once together they exceed 16 KiB.

**Shape and names** — the reasoning and the naming scheme are in
[`ha-user-experience`](../skills/ha-user-experience/SKILL.md#3-attributes):

- **Flat for what people read.** A value someone should see is a top-level attribute with a plain value. A dict or a
  list of objects is shown as raw YAML: keep those for bulk data machines read, in `_unrecorded_attributes`.
- **Every attribute has a display name**, `entity.<platform>.<translation_key>.state_attributes.<attr>.name`, so the
  entity needs a `translation_key` — also a main-feature entity with `name=None`, and one its device class would
  otherwise name. Without it the dialog shows the de-underscored English key in every language.
- **The key is stable and a translation key**: renaming it breaks automations, and hassfest allows only `[a-z0-9_-]`,
  so a unit is spelled out (`remaining_minutes`, `diff_from_daily_max_percent`) and the symbol goes into the display
  name ("Difference from daily maximum (%)").
- **A time attribute only when the state's own timestamps do not answer the question.** `last_changed`,
  `last_updated` and `last_reported` say when Home Assistant wrote the state, never what the value refers to. Add one
  for a value about another time than now (`interval_start`, `applies_to_date`), or one the source measured noticeably
  earlier (`measured_at`). Data age for the whole integration is one diagnostic `TIMESTAMP` sensor. Never a per-poll
  "fetched at": it duplicates `last_reported` and writes a state change each time. Name it for what it means, not
  `timestamp`.

**NEVER override `state_attributes` or `capability_attributes`** - reserved for base platform components (brightness,
color, etc.)

## Disabled and Hidden By Default

Two different things, and the wrong one is a common mistake:

- **Disabled** — registered disabled: it does not run, writes no state and fills no database until a user enables
  it. The answer for a noisy or rarely wanted entity (signal strength, a value changing every second).
  `_attr_entity_registry_enabled_default = False` on the class, or `entity_registry_enabled_default=False` on the
  description. Note the `_attr_` prefix on the class form: writing the bare property name silently does nothing.
- **Hidden** — runs and is recorded, but is left off auto-generated dashboards, voice assistants and device- or
  area-wide actions. `_attr_entity_registry_visible_default = False`. Only for an entity that is part of something
  bigger, such as a member of a group.

Both apply only when the entity is **first registered**; after that the user decides, and changing the default does
nothing for existing installs.

**Config-controlled visibility:** Conditionally add/remove entities in setup, NOT via `disabled_by`. When an option
turns a group off, also remove the stale registry entries (`er.async_remove(entity_id)`, and the device once it has no
entities left) — merely not creating them leaves entities the registry reports as `unavailable` forever.

## Device Info Fields

The base entity supplies `identifiers`, `name`, `manufacturer` and `model`. Fill in whatever else the source actually
knows — the Gold `devices` rule wants a complete device, and a `DeviceInfo` must match one of the registry's shapes
(Link: `connections` + `identifiers` only; Primary: the full metadata set; Secondary), never a partial mix.

| Field                                | Source                                                              |
| ------------------------------------ | ------------------------------------------------------------------- |
| `serial_number`                      | The device serial, when the API exposes one                         |
| `sw_version`, `hw_version`           | Firmware and hardware revision                                      |
| `model_id`                           | The machine-readable model code, next to the human-readable `model` |
| `configuration_url`                  | The device's own web UI; `homeassistant://<path>` to link inside HA |
| `entry_type=DeviceEntryType.SERVICE` | For a cloud account or service, which is not a physical device      |

Device info is only used when the entity is set up from a **config entry** and has a `unique_id`. Without one the
device is not attached, and returning `device_info` anyway is reported — do not do it.

Every text field of `DeviceInfo` (`model`, `sw_version`, `serial_number`, …) must be a `str` — convert a firmware
number or an integer serial yourself; a non-string value is reported. Dates for both: [`device-registry.md`](../skills/ha-modern-apis/references/device-registry.md).

**Never set `entity_id`** — an invalid one, or one whose domain is not the entity's platform, is reported
([`deprecations.md`](../skills/ha-modern-apis/references/deprecations.md)). Let Home Assistant build entity IDs from the names.

## Platform-Required Methods

Per-platform members and the trap each platform carries are in
[`ha-entity-platform/references/`](../skills/ha-entity-platform/SKILL.md), one file per platform family — the skill
lists which file covers which platform. Read the row for the platform you are adding.

**Write operations:** go through `self._async_write(lambda client: client.async_x(...), "translation_key")` on the base entity. It reaches the API client, turns a client error into a translated `HomeAssistantError` and then awaits `coordinator.async_request_refresh()`.
Never mutate local state and assume it took, with two exceptions — and in both, write the state only **after** the
command succeeded:

- The device is slow to confirm — a cloud service that lags, or a poll every few minutes. An optimistic update is
  fine; the next poll corrects it if the command did not stick.
- The device cannot report its state at all (one-way RF or IR). Also set `_attr_assumed_state = True`; the frontend
  then shows discrete on/off buttons instead of a toggle.

Failures follow the same split as everywhere else: `ServiceValidationError` for a value the user got wrong,
`HomeAssistantError` for a device or communication failure, both with a `translation_key`, never `ValueError`.

**Event subscriptions:** subscribe in `async_added_to_hass()` and release every subscription via `self.async_on_remove(...)`
(quality scale `entity-event-setup`). Call `await super().async_added_to_hass()` first — the base class needs it, and
subscribing earlier breaks any callback that touches `self.hass` or writes state. Never register a reference to an
entity object outside `async_added_to_hass`: a disabled entity is never added, and the reference would dangle.

**Lifecycle hooks** beyond these — `async_prepare_to_add_to_hass`, the `add_to_platform_*` internals, re-subscribing
on an entity ID rename: [`lifecycle.md`](../skills/ha-entity-platform/references/lifecycle.md).

**Runtime-varying metadata:** derive `supported_features` from coordinator data **once, at construction**, not in a
property that re-reads it every poll. `supported_features`, `device_class` and capability attributes may change, but
each change forces voice-assistant integrations to resynchronise with their cloud service.

**Reference:** [Entity Developer Docs](https://contributors.home-assistant.io/core/entities/entity-class/)

## Entity Utilities

**Add to `entity_utils/` when:**

- Used by 3+ entity classes
- Complex logic benefiting from testing
- Device info customization, state formatting

**Import pattern:** `from custom_components.<domain>.entity_utils.module import function`

## Device Registry Ownership

Home Assistant assigns every device to exactly one config entry and at most one config subentry.

**MUST:**

- Return `DeviceInfo` for a device owned by the entity's own config entry.
- Create a separate device for each config subentry; never share one device across subentries.
- Use `via_device_id` for a separate device reached through a hub, `ChildDeviceInfo` for a part of one product —
  which is which, and what a child device may carry: [`device-registry.md`](../skills/ha-modern-apis/references/device-registry.md).
- Use `self.device_entry` inside an entity when the registered device is needed.
- Scope explicit registry lookups with `async_get_device_by_identifier(identifier, config_entry_id)` or
  `async_get_device_by_connection(connection, config_entry_id)`.

**NEVER:**

- Use the unscoped `async_get_device()` lookup — it resolves ambiguously across entries and is reported.
- Use `via_device`, because identifiers are not globally unique across config entries. Passing **both** `via_device`
  and `via_device_id` raises at runtime, so a half-finished migration fails loudly — remove the old one.
- Add this integration's config entry to a device owned by another integration. Helper entities link to the source
  device by assigning `self.device_entry` instead of copying its identifiers or connections into `DeviceInfo`.
- Depend on a device being shared or merged across config entries.

## PARALLEL_UPDATES

Home Assistant reads `PARALLEL_UPDATES` from the platform module, so every platform `__init__.py` declares it as a
module-level literal — the same way Core integrations do. Do not import it from `const.py`: the value is a per-platform
decision, and a shared constant can only get it wrong for half the platforms.

```python
# Read-only platform: the coordinator already serializes the fetch.
PARALLEL_UPDATES = 0
```

**The value depends on whether the platform acts on the device**, because a coordinator only centralizes the inbound
fetch — it does not limit outbound calls:

| Value | Platforms                                                                                                                                                                                                                                                                                           |
| ----- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `0`   | Read-only: `sensor`, `binary_sensor`, `event`, `image`, `camera`, `device_tracker`. Throttling these only slows startup.                                                                                                                                                                            |
| `1`   | Everything that writes: `switch`, `light`, `number`, `select`, `button`, `climate`, `cover`, `fan`, `lock`, `valve`, `text`, `date`, `datetime`, `time`, `scene`, `siren`, `todo`, `update`, `notify`, `water_heater`, `humidifier`, `vacuum`, `lawn_mower`, `media_player`, `alarm_control_panel`. |

Missing it on a platform is a quality scale failure (`parallel-updates`).

## Dynamic Entity Creation

**Filter by available data:** Check `desc.key in coordinator.data` before creating entities

**Conditional features:** Use `self.coordinator.data.get("capability")` to determine `supported_features`

**Never log in a property getter** — they are called on every state read.
