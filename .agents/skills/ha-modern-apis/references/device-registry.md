# Device registry — single owner, child devices, lookups

Verified against the Home Assistant version pinned in this devcontainer. When an entry here disagrees with the installed
source, the source wins:

```bash
rg -n "breaks_in_ha_version" .venv/lib/python*/site-packages/homeassistant/helpers/device_registry.py
```

Docs: <https://contributors.home-assistant.io/core/integrations/device-registry/index.md>. They follow Home Assistant's
development branch, so they can describe an API the pinned version does not have yet — check the source before using it.

## The model

- A device is owned by **exactly one** config entry and at most one config subentry.
- Identifiers and connections are unique only **within** the owning entry — two entries can register the same
  identifier, and each gets its own device.
- Every config subentry gets its own device; two subentries never share one. Assigning an existing device to another
  subentry through `async_get_or_create` or shared entities silently moves it and is reported (breaks 2027.8) — move it
  explicitly with `async_update_device(new_config_subentry_id=…)`.
- Never attach this config entry to a device owned by another integration.

These rules hold in migrations, repairs, diagnostics, registry listeners **and tests**.

## Looking a device up

| You need                                                 | Call                                                                                                                                        |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| The device of the entity you are in                      | `self.device_entry`                                                                                                                         |
| A device by identifier                                   | `device_registry.async_get_device_by_identifier((DOMAIN, serial), entry.entry_id)`                                                          |
| A device by connection                                   | `device_registry.async_get_device_by_connection((dr.CONNECTION_NETWORK_MAC, mac), entry.entry_id)`                                          |
| Only the device **id**, to pass as `via_device_id`       | `dr.async_get_device_id_by_identifier(hass, (DOMAIN, hub_id), config_entry_id=entry.entry_id)` — raises `ValueError` when it does not exist |
| A device from a `device_id` in an action, with its entry | `dr.async_get_device_and_config_entry_for_domain(hass, device_id, domain=DOMAIN)` — `(None, None)` unknown, `(device, None)` not ours       |
| All devices of the entry                                 | `dr.async_entries_for_config_entry(device_registry, entry.entry_id)`                                                                        |
| A child device / all children of a device                | `async_get_child_device_by_identifier(identifier, entry.entry_id)` / `dr.async_entries_for_parent_device(device_registry, parent_id)`       |
| Every device with an identifier, across entries          | `device_registry.async_get_devices(identifiers=…)` — rarely right in an integration                                                         |

`device_registry.async_get(device_id)` returns main **and** child devices, and by default also a read-only stand-in for
the id of a pre-2026.8 composite device; `include_child_devices=False` / `include_composite_devices=False` narrow it.

## Hub or parts: `via_device_id` versus child devices

Two different relations — do not mix them up:

| The device is…                                                                    | Model it as                                                                                                                               |
| --------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| A **separate product** reached through another one — bulbs behind a bridge        | Its own device with `via_device_id=<hub device id>`. Connectivity only; register the hub first                                            |
| A **part of one product** — an outlet of a power strip, one gang of a wall switch | A child device: `ChildDeviceInfo(identifiers=…, name=…, parent_device_id=parent.id)`, or `device_registry.async_get_or_create_child(...)` |
| A hub or account with config-subentry devices                                     | Separate devices; each subentry device points at the hub with `via_device_id`                                                             |

A child device has no identity of its own — no `connections`, `via_device_id`, manufacturer, model, firmware or serial
number; those stay on the parent. It belongs to the parent's config entry **and** subentry (pass `config_subentry_id`,
it is not inherited), cannot have children, inherits the parent's area unless it has its own, and is removed and
disabled with its parent. The parent must already be registered: the registry raises `DeviceInfoError` otherwise.

An existing normal device whose identifiers match a new child device of the same entry becomes that child and keeps its
id, so automations keep working — provided the entry has not registered it as a normal device since it was set up. Do
not leave a `DeviceInfo` for the part on any entity. The reverse needs `async_remove_device` and a fresh
`async_get_or_create`, which removes the device's entity registry entries.

Passing **both** `via_device` and `via_device_id` raises. The id of a pre-2026.8 composite device as `via_device_id` is
reported (breaks 2027.8) — pass the id of one device.

## Removing devices

- Users delete a device from the UI only when `async_remove_config_entry_device` in `__init__.py` returns `True`.
- The integration removes a device it no longer has with `device_registry.async_remove_device(device.id)`. Removing a
  parent removes its children. Find stale devices by comparing `async_entries_for_config_entry` with the coordinator
  data at setup — never with an unscoped lookup.

## Helper entities on another integration's device

A helper (a derived sensor, a threshold) shows up on the source device without owning it: set
`self.device_entry = async_entity_id_to_device(hass, source_entity_id)` from `homeassistant.helpers.device`. Never put
the source device's identifiers into this integration's `DeviceInfo` — that used to add this config entry to the source
device, which a single-owner device cannot represent. Clean up devices a helper created for earlier source devices with
`homeassistant.helpers.helper_integration.async_remove_helper_devices(..., remove_all_devices=True)`.

## Deprecated — still works in the pinned version, logs a warning

These are logged and keep working until the version in the last column. How tests catch them:
[`ha-testing`](../../ha-testing/SKILL.md#two-settings-that-surprise-people).

| Do not use                                                                                                  | Use instead                                                                        | Removed in |
| ----------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | ---------- |
| `async_get_device(identifiers=… / connections=…)` (unscoped)                                                | `async_get_device_by_identifier` / `async_get_device_by_connection` with the entry | 2027.8     |
| `via_device=(DOMAIN, identifier)`, `ATTR_VIA_DEVICE`                                                        | `via_device_id=<device id>`                                                        | 2027.8     |
| `async_update_device(add_config_entry_id=… / remove_config_entry_id=…)` and the `_subentry_id` pair         | `new_config_entry_id=…` / `new_config_subentry_id=…`, or `async_remove_device`     | 2027.8     |
| `disabled_by=None` on a device of a disabled entry, `CONFIG_ENTRY` on an enabled one                        | Leave `disabled_by` unset; the registry follows the entry                          | 2027.8     |
| A `device_info` on an entity without a unique ID or config entry                                            | Give the entity a unique ID, or drop the device info                               | 2027.8     |
| `async_device_info_to_link_from_entity` / `_from_device_id` (already return `None`)                         | `self.device_entry = async_entity_id_to_device(hass, source_entity_id)`            | 2027.8     |
| `async_remove_stale_devices_links_keep_entity_device` / `_keep_current_device` (already do nothing)         | `helper_integration.async_remove_helper_devices(..., remove_all_devices=True)`     | 2027.8     |
| `helper_integration.async_remove_helper_config_entry_from_source_device`                                    | `helper_integration.async_remove_helper_devices`                                   | 2027.8     |
| `device_registry.devices` as a mapping (`[id]`, `.get`, …), `device_registry.deleted_devices`               | Iterate it, or `async_get` / `async_entries_for_config_entry`                      | 2027.9     |
| `default_manufacturer`, `default_model`, `default_name`, `created_at`, `modified_at` in device info         | `manufacturer`, `model`, `name`; drop the timestamps                               | 2027.9     |
| `async_update_device(merge_identifiers=… / merge_connections=…)`                                            | The full set as `new_identifiers=` / `new_connections=`                            | 2027.9     |
| `async_is_composite_device_id(device_id)`                                                                   | `async_get(device_id, include_composite_devices=False)`                            | 2027.9     |
| An attribute a `ChildDeviceEntry` does not have (`connections`, `manufacturer`, …)                          | Read it from the parent                                                            | 2027.9     |
| `DeviceEntry.config_entries`, `.config_entries_subentries`, `.primary_config_entry`                         | `DeviceEntry.config_entry_id`, `.config_subentry_id`                               | 2027.10    |
| A non-string value (an `int` firmware version, an enum) for `sw_version`, `model`, … — coerced with `str()` | Pass a `str`                                                                       | 2026.12    |

## Overdue — past its removal version, can disappear in any release

| Do not use                               | Use instead                                                  | Was due |
| ---------------------------------------- | ------------------------------------------------------------ | ------- |
| **Reading** `DeviceEntry.suggested_area` | `area_id`, or `dr.async_get_effective_area_id(hass, device)` | 2026.9  |
| `async_update_device(suggested_area=…)`  | Nothing — the user moves devices between areas               | 2026.9  |

Setting `suggested_area` in `DeviceInfo`, `ChildDeviceInfo` or `async_get_or_create` is **not** deprecated: it places a
new device in that area when it is first registered.

## `DeviceInfo` and `ChildDeviceInfo` are dataclasses

Construct them with keyword arguments — `DeviceInfo(identifiers=…, name=…)`. Subscript access, `.get()` and
`.update()` keep working through a compatibility layer; a dict literal, `DeviceInfo({...})`, unknown keys, `.copy()`,
`|` and `isinstance(x, dict)` do not. An unset field reads as `UNDEFINED`, not `None`. Serialize with
`device_info.as_dict()`. A held `DeviceInfo` is registered with `async_get_or_create_from_info` /
`async_get_or_create_child_from_info` instead of `**device_info`.
