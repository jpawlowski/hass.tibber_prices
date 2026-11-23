# Deprecated Home Assistant APIs and their replacements

Verified against the Home Assistant version pinned in this devcontainer. Check with:

```bash
.venv/bin/python -c "from homeassistant.const import __version__; print(__version__)"
```

When an entry here disagrees with the installed source, the installed source wins — grep it:

```bash
rg -n "deprecated|breaks_in_ha_version" .venv/lib/python*/site-packages/homeassistant/helpers/<module>.py
```

The device registry has its own file: [`device-registry.md`](device-registry.md).

**How to read the "Removed in" column.** A version means the old form still works in the pinned version and logs a
warning until then — `breaks_in_ha_version` from the source. **gone** means it no longer exists in the pinned version,
so old code fails right away. **overdue** means the removal version has passed but the old form is still there; it can
vanish in any release. **—** means not deprecated upstream, but wrong in this project. How tests catch the logged
ones: [`ha-testing`](../../ha-testing/SKILL.md#two-settings-that-surprise-people).

## Schema validation — `voluptuous` replaced by `probatio`

The core validates with `probatio`, a drop-in replacement with the same API
(`Schema`, `Required`, `Optional`, `All`, `Coerce`, `Range`, …). `async_show_form`, `add_suggested_values_to_schema`
and service registration are typed against `probatio.Schema`, so a `voluptuous` schema fails type checking.
This blueprint writes `import probatio` and `probatio.Schema(...)`; `probatio` ships with Home Assistant and needs no
`manifest.json` requirement. An existing `import voluptuous as vol` still works at runtime, because Home Assistant aliases
the name to `probatio`, and only the type checker complains.

## Imports that moved

| Do not use                                                                                                                                   | Use instead                                                                                                            | Removed in |
| -------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- | ---------- |
| `BinarySensorDeviceClass`, `ButtonDeviceClass`, `FanEntityFeature` from the platform package                                                 | `homeassistant.components.<platform>.const` — the package no longer re-exports them, so Pyright rejects the old import | —          |
| `DhcpServiceInfo` / `SsdpServiceInfo` / `UsbServiceInfo` / `ZeroconfServiceInfo` from `homeassistant.components.<dhcp, ssdp, usb, zeroconf>` | `homeassistant.helpers.service_info.<dhcp, ssdp, usb, zeroconf>`                                                       | gone       |
| `homeassistant.components.diagnostics.util.async_redact_data`                                                                                | `homeassistant.helpers.redact.async_redact_data`                                                                       | —          |

## Config entry runtime state and setup

| Do not use                                                                                                                                       | Use instead                                                                                         | Removed in                 |
| ------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------- | -------------------------- |
| `hass.data[DOMAIN][entry.entry_id] = …`                                                                                                          | `entry.runtime_data = {ClassPrefix}Data(...)`                                                       | —                          |
| Untyped `ConfigEntry`                                                                                                                            | `type {ClassPrefix}ConfigEntry = ConfigEntry[{ClassPrefix}Data]`                                    | —                          |
| `async_forward_entry_setup` (singular)                                                                                                           | `async_forward_entry_setups(entry, PLATFORMS)`                                                      | gone                       |
| `entry.add_update_listener` without cleanup                                                                                                      | `entry.async_on_unload(entry.add_update_listener(...))`                                             | —                          |
| An update listener on an entry whose flow reloads it — `async_update_reload_and_abort`, `_abort_if_unique_id_configured` with its default reload | Drop the listener and let the flow reload; or `async_update_and_abort`, or `reload_on_update=False` | 2026.12 (error)            |
| An update listener together with `OptionsFlowWithReload`, or with the subentry reload helper                                                     | Drop the listener                                                                                   | gone — raises `ValueError` |
| `hass.async_add_job`                                                                                                                             | `entry.async_create_task` / `entry.async_create_background_task`                                    | overdue (2025.4)           |

## Config flow

| Do not use                                                                                              | Use instead                                                                                                                                                                                                                                                       | Removed in |
| ------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- |
| `FlowResult`                                                                                            | `ConfigFlowResult`                                                                                                                                                                                                                                                | —          |
| `self.hass.config_entries.async_get_entry(...)` in reauth                                               | `self._get_reauth_entry()` / `self._get_reconfigure_entry()`                                                                                                                                                                                                      | —          |
| Manual update + `async_abort` + reload                                                                  | `self.async_update_reload_and_abort(entry, data_updates=…)`                                                                                                                                                                                                       | —          |
| Manual unique-ID comparison                                                                             | `self._abort_if_unique_id_mismatch(reason="wrong_device")`                                                                                                                                                                                                        | —          |
| `config_entries.OptionsFlow` storing `self.config_entry`                                                | The base class provides `self.config_entry`                                                                                                                                                                                                                       | —          |
| `self.show_advanced_options` / `context["show_advanced_options"]`                                       | Always show the field; group rarely used ones in a form section. The property already returns `True`, the context key is gone                                                                                                                                     | 2027.6     |
| `async_show_form` / `async_show_menu` / `async_show_progress` / `async_external_step` without `step_id` | Pass `step_id` — the step method's name without `async_step_`                                                                                                                                                                                                     | 2027.5     |
| `return True` / `return False` from `async_setup_entry`, `async_unload_entry` or `async_migrate_entry`  | Return nothing and raise a `ConfigEntry*` exception on failure; `async_unload_platforms_or_raise(entry, PLATFORMS)` replaces `return await async_unload_platforms(...)`. A custom integration's boolean still works, `False` becomes a generic `ConfigEntryError` | —          |
| YAML `async_setup_platform` for a device/service integration                                            | Config flow only ([ADR-0010](https://github.com/home-assistant/architecture/blob/master/adr/0010-integration-configuration.md))                                                                                                                                   | —          |

## Entities

| Do not use                                                                         | Use instead                                                                                                | Removed in    |
| ---------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- | ------------- |
| `DEVICE_CLASS_*` module constants                                                  | `SensorDeviceClass.*`, `BinarySensorDeviceClass.*`, …                                                      | gone          |
| `EntityDescription(name="Temperature")`                                            | `translation_key="temperature"` + `translations/en.json`                                                   | —             |
| `EntityDescription(icon="mdi:x")`                                                  | `icons.json`                                                                                               | —             |
| `self.schedule_update_ha_state()` from async code                                  | `self.async_write_ha_state()`                                                                              | —             |
| A `DOORBELL` event entity whose `event_types` lack `DoorbellEventType.RING`        | List `DoorbellEventType.RING`                                                                              | 2027.4        |
| `async_update()` on a coordinator-backed entity                                    | Read `self.coordinator.data`                                                                               | —             |
| `_attr_name` when `has_entity_name` is set                                         | `translation_key`, or `_attr_name = None` for the main entity                                              | —             |
| Setting `entity_id` with an invalid format                                         | Do not set `entity_id`; Home Assistant derives it                                                          | 2027.2        |
| Setting `entity_id` with another platform's domain                                 | Same                                                                                                       | 2027.5        |
| `PERCENTAGE` as a unit of measurement                                              | `UnitOfRatio.PERCENTAGE` — deprecated in the docs, no runtime warning yet                                  | — (docs only) |
| `CONCENTRATION_GRAMS/MILLIGRAMS/MICROGRAMS_PER_CUBIC_METER`, `…_PER_CUBIC_FOOT`    | `UnitOfDensity.*`                                                                                          | 2027.8        |
| `CONCENTRATION_PARTS_PER_MILLION` / `…_PER_BILLION`                                | `UnitOfRatio.PARTS_PER_MILLION` / `PARTS_PER_BILLION`                                                      | 2027.8        |
| `TemperatureConverter.convert_interval`                                            | `TemperatureDeltaConverter.convert`                                                                        | 2026.12       |
| An add or remove hook (`async_added_to_hass`, …) without `async_entity_id_changed` | Implement `async_entity_id_changed`; otherwise a rename removes and re-adds the entity                     | 2027.11       |
| `RestoreStateData.last_states`                                                     | `RestoreStateData.async_get_stored_state(entity_id)`; `RestoreEntity.async_get_last_state()` is unaffected | gone          |
| `AirQualityEntity` (`air_quality` platform)                                        | One sensor per reading, with a device class (`PM25`, `OZONE`, `AQI`, …)                                    | — (docs only) |

### Per platform

| Platform                  | Do not use                                                                                                         | Use instead                                                                                             | Removed in       |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------- | ---------------- |
| `light`                   | Mireds — `color_temp`, `min_mireds`, `max_mireds`                                                                  | Kelvin only — `color_temp_kelvin`, `_attr_min/max_color_temp_kelvin`                                    | gone             |
| `light`                   | `_attr_min_color_temp_kelvin` / `_attr_max_color_temp_kelvin = None`                                               | A real value, e.g. `DEFAULT_MIN_KELVIN` / `DEFAULT_MAX_KELVIN`                                          | overdue (2026.8) |
| `vacuum`                  | `battery_level`, `VacuumEntityFeature.BATTERY`                                                                     | A separate battery sensor                                                                               | gone             |
| `media_player`            | `MediaPlayerState.STANDBY`                                                                                         | `MediaPlayerState.OFF` or `IDLE`                                                                        | overdue (2026.8) |
| `device_tracker`          | The legacy platform API (`get_scanner`, `setup_scanner` and their `async_` forms, the `device_tracker.see` action) | `TrackerEntity` / `ScannerEntity` from a config entry                                                   | 2027.5           |
| `device_tracker`          | `battery_level` on any tracker entity                                                                              | A separate battery sensor                                                                               | 2027.7           |
| `device_tracker`          | `location_name` on `TrackerEntity`                                                                                 | `in_zones` (zone entity IDs), or a separate sensor                                                      | 2027.7           |
| `device_tracker`          | `TrackerEntity`, `ScannerEntity`, `SourceType` from `device_tracker.config_entry`                                  | Import from `homeassistant.components.device_tracker`                                                   | 2027.6           |
| `device_tracker`          | `ATTR_LATITUDE` / `ATTR_LONGITUDE` from `device_tracker.const`                                                     | `EntityStateAttribute.LATITUDE` / `LONGITUDE`                                                           | 2027.2           |
| `climate`, `water_heater` | `current_temperature`, `target_temperature[_high\|_low]`, `temperature_unit` (and their `_attr_` forms)            | The same with a `native_` prefix; `min_temp`, `max_temp` and `target_temperature_step` keep their names | 2027.11          |

## Service actions, conditions and scripts

| Do not use                                                                                                                                                        | Use instead                                                                           | Removed in        |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- | ----------------- |
| `hass` as first argument to `verify_domain_control`, `extract_entity_ids`, `async_extract_entities`, `async_extract_entity_ids`, `async_extract_config_entry_ids` | Drop it — `call.hass` carries it, e.g. `@verify_domain_control(DOMAIN)`               | gone              |
| A `device:` filter under `target:` in `services.yaml`                                                                                                             | Remove it; filter on `entity:` only. Hassfest already rejects it                      | overdue (2026.11) |
| Calling a condition object, `condition(hass, variables)`                                                                                                          | `condition.async_check(variables=…)`, then `condition.async_unload()` when done       | 2027.1            |
| A `Script` you create and forget                                                                                                                                  | `await script.async_unload()` when it is no longer needed                             | —                 |
| `homeassistant.components.labs.async_listen`                                                                                                                      | `async_subscribe_preview_feature` (the listener is a coroutine taking the event data) | 2027.3            |

## Async, I/O and dependencies

| Do not use                                                                                    | Use instead                                                                                                                                                                          | Removed in                  |
| --------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------- |
| `requests`, `urllib`, blocking SDK calls                                                      | `aiohttp` via `async_get_clientsession(hass)`                                                                                                                                        | —                           |
| Creating your own `aiohttp.ClientSession`                                                     | `async_get_clientsession(hass)` (Platinum `inject-websession`)                                                                                                                       | —                           |
| `async_timeout.timeout(...)`                                                                  | `asyncio.timeout(...)`                                                                                                                                                               | —                           |
| `time.sleep`, `datetime.now()`                                                                | `asyncio.sleep`, `homeassistant.util.dt.utcnow()`                                                                                                                                    | —                           |
| `open()` / `json.load()` in the event loop                                                    | `await hass.async_add_executor_job(...)`                                                                                                                                             | —                           |
| An `async_*` API from a worker thread                                                         | Its thread-safe twin — table in [`async-rules.md`](../../ha-coordinator-debug/references/async-rules.md)                                                                             | —                           |
| `async_track_state_change`                                                                    | `async_track_state_change_event`                                                                                                                                                     | —                           |
| `hass.bus.async_listen(EVENT_STATE_CHANGED)`                                                  | `async_track_state_change_event`                                                                                                                                                     | —                           |
| `hass.bus.async_listen(EVENT_COMPONENT_LOADED)`                                               | `homeassistant.helpers.start.async_at_start`                                                                                                                                         | —                           |
| `pyserial`, `pyserial-asyncio`, `pyserial-asyncio-fast` (also inside a library you depend on) | `serialx` — import-compatible; construct ports with `serialx.serial_for_url()`                                                                                                       | 2027.2 (`pyserial-asyncio`) |
| `homeassistant.components.modbus.get_hub(hass, name)`                                         | `homeassistant.components.modbus.async_get_unit(hass, entry, params, unit_id)` with connection details from your own config flow; `params` come from the `modbus-connection` library | 2027.10                     |

## Recorder statistics

| Do not use                                                                                               | Use instead                     | Removed in        |
| -------------------------------------------------------------------------------------------------------- | ------------------------------- | ----------------- |
| `async_import_statistics` / `async_add_external_statistics` metadata without `mean_type` or `unit_class` | Set both in `StatisticMetaData` | overdue (2026.11) |
| `async_update_statistics_metadata(new_unit_of_measurement=…)` without `new_unit_class`                   | Pass `new_unit_class` as well   | overdue (2026.11) |
