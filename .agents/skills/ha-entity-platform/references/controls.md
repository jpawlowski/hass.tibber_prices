# Controls

Only what differs per platform — read your platform's row; the general rules are in
[`blueprint.entities`](../../../instructions/blueprint.entities.instructions.md).

**A `supported_features` flag gates the action, not just the UI.** Home Assistant refuses an action whose feature flag
is not set, whether or not you implemented the method — set the flag and the method together.

## Switches, buttons and values

| Platform   | Required                                           | Notes                                                                                                                      |
| ---------- | -------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `switch`   | `is_on`, `async_turn_on`, `async_turn_off`         | refresh after write                                                                                                        |
| `button`   | `async_press`                                      | stateless; no `is_on`. `ButtonDeviceClass.IDENTIFY` belongs in `DIAGNOSTIC`                                                |
| `number`   | `native_value`, `async_set_native_value`           | `native_min_value` (0), `native_max_value` (100), `native_step`; `mode` is `auto`/`box`/`slider` and `auto` is recommended |
| `select`   | `current_option`, `options`, `async_select_option` | options are translated via `state` keys, in `snake_case`                                                                   |
| `text`     | `native_value`, `async_set_value`                  | `native_min`, `native_max`, `pattern`, `mode` (`text` or `password`)                                                       |
| `date`     | `native_value`, `async_set_value`                  | takes and returns a `datetime.date`                                                                                        |
| `datetime` | `native_value`, `async_set_value`                  | a naive `datetime` raises when the state is written — always return one with `tzinfo`                                      |
| `time`     | `native_value`, `async_set_value`                  | takes a `datetime.time`                                                                                                    |
| `scene`    | `async_activate`                                   | subclass `Scene`; the state is the timestamp of the last activation and the base class keeps it — do not set a state       |
| `siren`    | `is_on`, `async_turn_on`, `async_turn_off`         | `TONES` needs `available_tones`; `VOLUME_SET` and `DURATION` arrive as `async_turn_on` keyword arguments                   |

## Openings and access

| Platform              | Required                                             | Notes                                                                                                                                                                                                                                      |
| --------------------- | ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `cover`               | `is_closed`, `supported_features`                    | implement `async_open_cover` / `async_close_cover` **only** with the matching `CoverEntityFeature`; use `number` for something that is not an opening                                                                                      |
| `valve`               | `reports_position`, `supported_features`             | `current_valve_position` is required when `reports_position` is `True`. With `SET_POSITION`, still declare `OPEN` and `CLOSE` — the actions are gated on them — but implement only `async_set_valve_position`; HA maps open/close to 100/0 |
| `lock`                | `is_locked`, `async_lock`, `async_unlock`            | `is_open` is only relevant with `LockEntityFeature.OPEN`                                                                                                                                                                                   |
| `alarm_control_panel` | `alarm_state`, `supported_features`, `async_alarm_*` | return `AlarmControlPanelState`, never a string. `code_arm_required` defaults to `True` — set it `False` when the panel arms without a code; `code_format` is `CodeFormat.NUMBER`/`TEXT`, or `None` when no code is used                   |

## Fan and light

| Platform | Required                                                            | Notes                                                                                                                                                      |
| -------- | ------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `fan`    | `is_on`, `percentage`, `async_set_percentage`, `supported_features` | `preset_modes` must not contain speeds; `speed_count` defaults to 100; `async_turn_on`/`off` need the explicit `FanEntityFeature.TURN_ON`/`TURN_OFF` flags |
| `light`  | `is_on`, `supported_color_modes`, `color_mode`                      | see below                                                                                                                                                  |

`supported_color_modes` is required — **a light that does not set it raises when its state is written.** `color_mode`
must be one of the declared modes. `async_turn_on` receives exactly one colour attribute, already translated into the
mode you declared. An active effect may narrow `color_mode` to `ONOFF` or `BRIGHTNESS`.

Colour temperature is **kelvin only**: `color_temp_kelvin`, `_attr_min_color_temp_kelvin`,
`_attr_max_color_temp_kelvin`. The mired attributes are gone. With `ColorMode.COLOR_TEMP`, set the minimum and maximum
to the device's real range — the defaults (2000–6535 K) are a placeholder, and never set either to `None`. See
[`deprecations.md`](../../ha-modern-apis/references/deprecations.md).
