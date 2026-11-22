# Patterns to expect in imported code

Read this during phase 4. [`../../ha-modern-apis/SKILL.md`](../../ha-modern-apis/SKILL.md) is authoritative for
what is current — verify against the installed Home Assistant source rather than this table, which is a starting
point for what to look for.

## Deprecated or removed APIs

| Found in older integrations                                             | Replace with                                                                                                          |
| ----------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `hass.data[DOMAIN][entry.entry_id] = …`                                 | `entry.runtime_data`, with a typed config entry alias                                                                 |
| `hass.config_entries.async_setup_platforms(...)`                        | `await hass.config_entries.async_forward_entry_setups(...)`                                                           |
| `async_timeout.timeout(...)`                                            | `asyncio.timeout(...)`                                                                                                |
| `DEVICE_CLASS_*` / `STATE_CLASS_*` constants                            | the `SensorDeviceClass` / `SensorStateClass` enums                                                                    |
| `FlowResult`                                                            | `ConfigFlowResult`                                                                                                    |
| `aiohttp.ClientSession()` created by the integration                    | `async_get_clientsession(hass)`                                                                                       |
| `self._attr_name` on every entity, often with the device name inside it | `translation_key` plus `_attr_has_entity_name`; entity IDs stay, displayed names change — say so in the release notes |
| `async_get_device(identifiers=…)` unscoped                              | `async_get_device_by_identifier()` scoped to the owning entry                                                         |
| `entity_registry.async_get(hass).async_get_or_create(...)` in an entity | let the platform's `async_add_entities` do it                                                                         |
| `config_entry.async_on_unload` missing around listeners                 | register every listener through it                                                                                    |

Two more that do not raise a warning and are easy to miss:

- **Blocking I/O in the event loop** — `requests`, `open()`, `time.sleep()`, or a synchronous vendor library called
  directly from a coroutine. Home Assistant logs this as a blocking-call warning at runtime, not at import.
- **`async_config_entry_first_refresh()` missing** — an integration that calls `async_refresh()` during setup does not
  fail the entry cleanly when the device is offline.

## If the source is the upstream `ludeeus/integration_blueprint`

That template and this one share ancestry, which creates two specific traps:

- **Class names collide.** Both use the same `{ClassPrefix}` naming for the API client, coordinator and base entity.
  After `initialize.sh` has renamed the blueprint's classes, an imported file can define a class with the identical
  name in a different module. Replace the generated `custom_components/<domain>/` wholesale; never merge the two
  file by file.
- **The layout is flat.** `api.py`, `coordinator.py`, `entity.py`, `data.py` and one module per platform sit at the
  top level. That is valid — it becomes the phase 5 restructuring work, and is not a reason to touch it in phase 2.

Depending on the vintage of the fork, also expect: `hass.data[DOMAIN]` instead of `runtime_data`, no `icons.json`,
no `diagnostics.py`, no `repairs.py`, no `quality_scale` in the manifest, and no tests at all beyond the ones the
template shipped.

## What must survive all of it

Diff these explicitly against the phase 0 contract after every automated rename or bulk edit:

- `DOMAIN`, and every place it is used to build an ID
- the config entry `unique_id` and each entity's `unique_id`
- `EntityDescription.key` values — they usually feed the unique ID
- `translation_key` values, and the `en.json` keys that match them
- `entry.data` / `entry.options` key names, and `VERSION` / `MINOR_VERSION`
- service action names and their field names
- `Store` keys and anything else written under `.storage`
