# Events, media, updates and trackers

Only what differs per platform — read your platform's row; the general rules are in
[`blueprint.entities`](../../../instructions/blueprint.entities.instructions.md).

| Platform         | Required                                                                                       | Notes                                                                                                                                                                                                                                                                                                                                                                |
| ---------------- | ---------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `event`          | `event_types`                                                                                  | drive state with `self._trigger_event(type, data)` + `async_write_ha_state()` from a callback registered in `async_added_to_hass`; firing an undeclared type raises `ValueError`. A `DOORBELL` entity must list `DoorbellEventType.RING` (see deprecations.md); buttons use `ButtonEventType.*`                                                                      |
| `update`         | `installed_version`, `latest_version`                                                          | `UpdateEntityFeature.INSTALL` only if it really installs; `PROGRESS` + `update_percentage`, `RELEASE_NOTES` + `async_release_notes()`, `BACKUP`, `SPECIFIC_VERSION`; `version_is_newer()` for non-semver schemes. Defaults to `EntityCategory.CONFIG`. `auto_update=True` for a device that updates itself — users then cannot skip a version. Upcoming extras below |
| `image`          | `async_image`                                                                                  | never bump `image_last_updated` inside `async_image` — set it from the coordinator; cache in `self._cached_image` and set it to `None` to invalidate. Needs the explicit constructor below                                                                                                                                                                           |
| `camera`         | `async_camera_image`, or `stream_source` + `CameraEntityFeature.STREAM`                        | needs the explicit constructor below                                                                                                                                                                                                                                                                                                                                 |
| `device_tracker` | `TrackerEntity`: `latitude`, `longitude`, `location_accuracy`; `ScannerEntity`: `is_connected` | `_attr_source_type` is a `SourceType` enum. Do not override `battery_level` or `location_name` (see deprecations.md) — battery is its own `sensor`. Upcoming `ScannerEntity` change below                                                                                                                                                                            |
| `notify`         | `async_send_message`                                                                           | stateless; the state is the timestamp of the last message. Only record notifications originating **inside** Home Assistant via `_async_record_notification()` — externally generated ones belong on an event entity                                                                                                                                                  |
| `todo`           | `todo_items`                                                                                   | state is the count of incomplete items; note `SET_DUE_DATE_ON_ITEM` vs `SET_DUE_DATETIME_ON_ITEM`                                                                                                                                                                                                                                                                    |

## Image and camera: call both constructors

`ImageEntity.__init__(hass, verify_ssl=False)` and `Camera.__init__()` take different arguments from the
integration's base entity and do not call `super().__init__()`. With the usual `(PlatformEntity, {ClassPrefix}Entity)`
order, a plain `super().__init__(coordinator, entity_description)` hands the coordinator to the platform constructor and
never runs the base entity's. Call both explicitly — for a camera, the second call is `Camera.__init__(self)`:

```python
def __init__(
    self,
    coordinator: {ClassPrefix}DataUpdateCoordinator,
    entity_description: ImageEntityDescription,
) -> None:
    """Initialize the image entity."""
    {ClassPrefix}Entity.__init__(self, coordinator, entity_description)
    ImageEntity.__init__(self, coordinator.hass)
```

## Update and device tracker

- `update`: override `has_update` when the device reports availability itself instead of comparable versions; set
  `restart_required=True` (attribute or description) when the update needs a Home Assistant restart.
- `ScannerEntity.device_info` can be overridden, and trackers are disabled by default. A tracker without device info
  stops getting an automatic device in 2027.11.

## Infrared and radio frequency devices

A device controlled through an IR or RF transmitter that **another** integration provides is a consumer: it creates
ordinary entities (`button`, `switch`, `media_player`, …), never an `infrared` or `radio_frequency` entity, and lets
the user pick the transmitter in the config flow (`infrared.async_get_emitters(hass)`,
`radio_frequency.async_get_transmitters(hass, frequency, modulation)`). Add the domain to `dependencies` in
`manifest.json`.

- Mix the consumer base class in **before** the platform class: `class Power(InfraredEmitterConsumerEntity,
ButtonEntity)`. Set `_infrared_emitter_entity_id` (receiving: `InfraredReceiverConsumerEntity`,
  `_infrared_receiver_entity_id`, `_handle_signal`), then `await self._send_command(command)`. RF:
  `RadioFrequencyTransmitterConsumerEntity` with `_rf_transmitter_entity_id_or_uuid`. The base class keeps the entity
  available only while the transmitter is.
- The device cannot report state, so a `switch` here is optimistic with `_attr_assumed_state = True`.
- These classes are recent and their attribute names are still moving — check `helpers.py` of the installed
  `components/infrared` / `components/radio_frequency` before writing one.
