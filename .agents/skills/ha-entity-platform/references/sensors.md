# Sensor and binary sensor

Only what differs per platform — read your platform's row; the general rules are in
[`blueprint.entities`](../../../instructions/blueprint.entities.instructions.md).

| Platform        | Required       | Notes                                                                  |
| --------------- | -------------- | ---------------------------------------------------------------------- |
| `sensor`        | `native_value` | `device_class` drives unit conversion; see the state-class rules below |
| `binary_sensor` | `is_on`        | Use `BinarySensorDeviceClass`, not icons                               |

Neither platform accepts `EntityCategory.CONFIG` — adding such an entity raises. A sensor is `None` or `DIAGNOSTIC`.

## State class and unit follow the device class

**Do not pick a state class from memory — look it up.** Home Assistant validates every sensor against two tables in
the installed `homeassistant/components/sensor/const.py`:

- `DEVICE_CLASS_STATE_CLASSES` — the state classes each device class allows. An empty set (`DATE`, `ENUM`,
  `TIMESTAMP`, `UPTIME`, …) means no state class at all. Meters (`ENERGY`, `GAS`, `WATER`, `VOLUME`, …) allow only
  `TOTAL` / `TOTAL_INCREASING`; `MONETARY` only `TOTAL`.
- `DEVICE_CLASS_UNITS` — the units each device class accepts. Use the `UnitOf…` constant it lists, never a string
  literal that looks the same.

```bash
rg -n -A3 "SensorDeviceClass.ENERGY:" .venv/lib/python*/site-packages/homeassistant/components/sensor/const.py
```

The blanket "set a state class on every number" rule produces an invalid combination exactly where the table says
otherwise. Beyond the tables:

- `TOTAL` without `last_reset` is the recommended default for a meter.
- `TOTAL_INCREASING` for a value that only rises and resets to zero — a drop of more than 10% is read as a new cycle.
- `MEASUREMENT_ANGLE` for an angle such as a wind direction, so statistics average it as a circular quantity.
- `SensorDeviceClass.ENUM` requires `options` and **cannot** carry `state_class` or `native_unit_of_measurement`. It
  is also not named after its device class — it needs a `translation_key`.
- `SensorDeviceClass.DURATION` must not change just because time passes.
- A unit that is a word ("steps", "cycles") is a translated unit: set no `native_unit_of_measurement` and add the
  `unit_of_measurement` key next to the entity's name — see [`ha-translations`](../../ha-translations/SKILL.md).

## Display and restore

- `suggested_display_precision` decides how the value renders. Without it, a sensor with a device class and unit gets
  the device class' default precision (`UNITS_PRECISION` in the same `const.py`); one without a device class is shown
  raw. Set it anyway — the default is a fallback, not a decision about this device.
- `suggested_unit_of_measurement` overrides the automatic conversion when the device class' default is wrong. It is
  stored in the registry the first time the sensor is seen.
- Restoring state after a restart needs `RestoreSensor` and `async_get_last_sensor_data()` — plain `RestoreEntity`
  stores the converted state, not `native_value`. Same for `RestoreNumber` / `async_get_last_number_data()`.
- `BinarySensorDeviceClass.UPDATE` should be avoided; use an `update` entity
  ([`other-platforms.md`](other-platforms.md)).
