---
name: ha-entity-platform
description: >-
  Add or change a Home Assistant entity platform or an individual entity in this custom integration — sensor,
  binary_sensor, switch, button, number, select, fan, climate, cover, light, lock, and friends. Use when asked to
  "add a sensor", "add a new entity", "add a platform", "expose <value> as an entity", "add an entity to the
  device", "make this entity diagnostic", or when changing EntityDescription metadata, device classes, state
  classes, entity categories, or availability. Covers the platform directory layout, the coordinator-backed entity
  contract, unique IDs, device grouping, and the translation and validation steps that must follow. SYMPTOMS —
  load this if you are about to: hardcode `name=` or `icon=` in an EntityDescription instead of `translation_key`;
  omit `state_class` on a numeric measurement; call the API client from an entity property; set `_attr_unique_id`
  or `_attr_device_info` in a platform entity; or put two entity classes in one file.
---

# Add or change an entity platform

Entities are the user-visible surface of the integration. Getting the metadata right at creation time matters more than
usual: unique IDs, device classes, and entity IDs are effectively permanent once a user has installed the integration.

**Read [`blueprint.entities.instructions.md`](../../instructions/blueprint.entities.instructions.md) first** —
it holds the rules this procedure assumes: base-class inheritance and MRO, required `EntityDescription` fields, the
coordinator-only data rule, availability, device info fields, `PARALLEL_UPDATES`, and device registry ownership. Copilot
injects it automatically when you edit an entity file; other agents must open it. Python style is in
[`blueprint.python.instructions.md`](../../instructions/blueprint.python.instructions.md).

This skill is the procedure and the decisions — it does not restate those rules.

Before implementing a platform, read its row — required members and the trap it carries:

| File                                                                           | Platforms                                                                                                                                                     |
| ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`references/sensors.md`](references/sensors.md)                               | `sensor`, `binary_sensor` — state class and unit rules                                                                                                        |
| [`references/controls.md`](references/controls.md)                             | `switch`, `button`, `number`, `select`, `text`, `date`, `datetime`, `time`, `scene`, `siren`, `cover`, `valve`, `lock`, `alarm_control_panel`, `fan`, `light` |
| [`references/climate-and-appliances.md`](references/climate-and-appliances.md) | `climate`, `water_heater`, `humidifier`, `vacuum`, `lawn_mower`, `media_player`                                                                               |
| [`references/other-platforms.md`](references/other-platforms.md)               | `event`, `update`, `image`, `camera`, `device_tracker`, `notify`, `todo`, infrared and radio frequency consumers                                              |

Lifecycle hooks beyond `async_added_to_hass` — any platform: [`references/lifecycle.md`](references/lifecycle.md).

## Before you write code

Clarify — ask the developer if any of this is missing:

- Which platform (`sensor`, `switch`, …) and whether it already exists in the integration. The most specific one
  that fits, not a sensor by habit: [`ha-user-experience`](../ha-user-experience/SKILL.md#the-platform-that-fits).
- Which field of `coordinator.data` backs the entity, and its unit and value range.
- Whether it is a primary entity or a diagnostic/config entity (`EntityCategory`).
- For writable platforms: which API method performs the write.

Then read the closest existing sibling — for a new sensor that is
`custom_components/<domain>/sensor/air_quality.py`. Match it rather than inventing a second style.

## Layout

Each platform is a package, one entity class per file:

```text
custom_components/<domain>/<platform>/
├── __init__.py        # async_setup_entry + aggregated ENTITY_DESCRIPTIONS
└── <group>.py         # ENTITY_DESCRIPTIONS + entity class for one logical group
```

Once a `value_fn` description carries the value lookup, one entity class serves every group on the platform, and
copying it per file would be the duplication `value_fn` exists to remove. Give it its own module and leave the group
files holding descriptions only — this is what `sensor/` does:

```text
custom_components/<domain>/sensor/
├── __init__.py        # async_setup_entry + aggregated ENTITY_DESCRIPTIONS
├── entity.py          # the description subclass and the single entity class
├── air_quality.py     # ENTITY_DESCRIPTIONS only
└── diagnostic.py      # ENTITY_DESCRIPTIONS only
```

Keep the first shape while a platform has one group, and split when a second class would otherwise be a copy of the
first.

## Procedure

### 1. Decide the metadata, then write the descriptions

The mechanical rules are in the instructions file. What this step actually costs you is judgement:

- **`key`** becomes part of the unique ID. Pick it once — renaming it later is a breaking change
  ([`ha-breaking-changes`](../ha-breaking-changes/SKILL.md)).
- **Primary, diagnostic or config?** The test is in
  [Entity Categories](../../instructions/blueprint.entities.instructions.md#entity-categories); disabled by default is
  a separate choice, hidden another. Which is which, and why the choice is final:
  [Disabled and Hidden By Default](../../instructions/blueprint.entities.instructions.md#disabled-and-hidden-by-default).
- **Is there a matching `device_class`?** Check the platform's enum before inventing units or icons. A device class
  buys unit conversion, correct icons and voice-assistant behaviour for free.
- **Is the value a measurement or a total?** Then it needs a `state_class`, or the user gets no long-term statistics.
- **Who reads it — a dashboard, an automation, or both?** That decides state versus attribute, the icon, and what
  goes beside the state: [`ha-user-experience`](../ha-user-experience/SKILL.md).

### 2. Entity class

Implement only the platform members and the value extraction; everything else comes from the base class.

```python
class {ClassPrefix}AirQualitySensor(SensorEntity, {ClassPrefix}Entity):
    """Air quality sensor."""

    entity_description: {ClassPrefix}SensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the current value."""
        return self.entity_description.value_fn(self.coordinator.data)
```

A value that is simply missing from this poll is `unknown`, not `unavailable` — returning `None` above already does
that, and it keeps the entity usable in templates and automations.

Only override `available` when a single entity can genuinely be **gone** while the rest of the device is fine — a
missing key that means a missing sub-device. The base `CoordinatorEntity` already handles the whole-device case:

```python
@property
def available(self) -> bool:
    """Return True if the backing sub-device is still present."""
    return super().available and self.entity_description.key in self.coordinator.data
```

### 3. Register the platform

For a brand-new platform only:

1. Add the `Platform.<NAME>` member to the `PLATFORMS` list in `custom_components/<domain>/__init__.py`
   (keep the list alphabetical).
2. Nothing else — `async_setup_entry` already forwards with `async_forward_entry_setups(entry, PLATFORMS)` and
   `async_unload_entry` already tears down with `async_unload_platforms_or_raise(entry, PLATFORMS)`.

### 4. Device grouping

The base entity places every entity on the config entry's device. Only deviate when the integration genuinely models
more than one device, and then decide whether each one is a part of one product (a child device) or a separate
product behind a hub (`via_device_id`) — the decision table and the single-owner rules are in
[`device-registry.md`](../ha-modern-apis/references/device-registry.md#hub-or-parts-via_device_id-versus-child-devices).

When devices come and go at runtime (`dynamic-devices`), add entities from a coordinator listener that diffs
`set(coordinator.data)` against a `known_devices` set. If the integration also removes devices that are gone
(`stale-devices`), drop each removed ID from `known_devices` too — otherwise a device that returns is never added
again until the entry reloads. Both rules: [`quality-scale-rules.md`](../ha-quality-review/references/quality-scale-rules.md).

### 5. Translations

Add the `translation_key` under `entity.<platform>.<key>.name` in `translations/en.json`, plus `state` keys for enum
sensors. Do not touch other language files. See [`ha-translations`](../ha-translations/SKILL.md).

### 6. Validate

```bash
script/lint && script/type-check
script/hassfest
script/test
```

Then restart Home Assistant (`./script/develop`) and confirm the entity appears with the expected name, unit, icon, and
category. If it does not appear at all, switch to [`ha-coordinator-debug`](../ha-coordinator-debug/SKILL.md).

## Something happened, rather than something is

For a button press, a doorbell ring, a fault report — anything that **occurs** instead of **holds** — reach for an
`event` entity, not a sensor.

**The anti-pattern: do not represent an event as entity state.** A binary sensor that is `on` for 30 seconds after a
doorbell ring is wrong in both directions — it invents a duration the device never reported, and it loses a second
ring inside the window. `event` entities exist for exactly this.

Firing on the event bus directly is the fallback for what does not fit an entity at all:

- Event type is `<domain>_event`; include the `device_id` from the device registry in the payload.
- The wiring belongs in `__init__.py`, not in an entity — an entity that is disabled would never subscribe.
- A device that **only** fires events still has to be registered in the device registry by hand; nothing else creates
  it.

Listening is the mirror image: prefer a helper from `homeassistant.helpers.event` over `hass.bus.async_listen`, and
wrap the unsubscribe callable every helper returns in `entry.async_on_unload(...)`.

## Do not

- Do not add an entity for data the coordinator does not already fetch — extend the coordinator first, or you will be
  tempted to call the API from the entity.
- Do not write `significant_change.py` or `reproduce_state.py` speculatively. The first only matters when the
  integration's entities are exported to Google Assistant or Alexa and are noisy enough to need filtering
  (`async_check_significant_change(hass, old_state, old_attrs, new_state, new_attrs, **kwargs) -> bool | None`). The
  second is only for an integration that defines its **own** domain — entities added to an existing platform inherit
  scene support from it for free.
- Do not rename an existing `key`, `translation_key`, or unique ID without reading
  [`ha-breaking-changes`](../ha-breaking-changes/SKILL.md).
- Do not skip the sibling-file read in step 0. Most "new" entities are a variation of one that already exists.
- Do not raise `ConfigEntryNotReady` from a platform's `async_setup_entry` — the config entry setup has already
  finished by then and nothing catches it.

The remaining hard rules are in
[`blueprint.entities.instructions.md`](../../instructions/blueprint.entities.instructions.md); the per-platform
members are in the `references/` files listed at the top.
