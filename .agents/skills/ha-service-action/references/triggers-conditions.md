# Triggers and conditions

How an integration offers its own automation triggers ("Device reported a fault") and conditions ("Device is
charging"): a `trigger.py` / `condition.py` platform, described in `triggers.yaml` / `conditions.yaml`. Upstream
reference: <https://contributors.home-assistant.io/core/integrations/triggers-and-conditions/>.

**This API is young and still moves.** The helpers recently moved into `homeassistant.helpers.trigger` and
`homeassistant.helpers.condition`, and the trigger runner gained an argument. Before writing one, read the installed
source and one current implementation instead of trusting this page or an older integration:

```bash
rg -n "class Trigger\b|def async_attach_runner|def async_validate_config" .venv/lib/python*/site-packages/homeassistant/helpers/trigger/
rg -n "class Condition\b|def _async_check|def _async_setup|def _async_unload" .venv/lib/python*/site-packages/homeassistant/helpers/condition*
```

`device_trigger.py`, `device_condition.py` and `device_action.py` are the frozen predecessor — never add them.

## What users write

The key is relative to the domain (`fault` becomes `<domain>.fault`). Settings go under `options`, the entities,
devices or areas under `target` — and that is also the shape `async_validate_config` receives:

```yaml
triggers:
  - trigger: <domain>.fault_reported
    options:
      device_id: 0c5ac1d9e3f8a4b2c6d7e8f9a0b1c2d3
conditions:
  - condition: <domain>.is_charging
    target:
      entity_id: sensor.example_battery
```

## Trigger

```python
import probatio

from homeassistant.const import ATTR_DEVICE_ID, CONF_OPTIONS
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.trigger import (
    Trigger,
    TriggerActionRunner,
    TriggerConfig,
    TriggerNotTriggeredReporter,
)
from homeassistant.helpers.typing import ConfigType

_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_OPTIONS): {
            probatio.Required(ATTR_DEVICE_ID): probatio.All(cv.ensure_list, [cv.string]),
        },
    },
)


class {ClassPrefix}FaultReportedTrigger(Trigger):
    """Trigger when a device reports a fault."""

    @classmethod
    async def async_validate_config(cls, hass: HomeAssistant, config: ConfigType) -> ConfigType:
        """Validate the options and target of the trigger."""
        return _SCHEMA(config)

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Keep the validated options."""
        super().__init__(hass, config)
        assert config.options is not None
        self._device_ids: list[str] = config.options[ATTR_DEVICE_ID]

    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,
    ) -> CALLBACK_TYPE:
        """Start listening; the returned callback stops it."""

        @callback
        def _async_fault(device_id: str) -> None:
            if device_id in self._device_ids:
                run_action({ATTR_DEVICE_ID: device_id}, "fault reported")

        return async_dispatcher_connect(self._hass, SIGNAL_FAULT_REPORTED, _async_fault)


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers of this integration."""
    return {"fault_reported": {ClassPrefix}FaultReportedTrigger}
```

- `async_validate_config` is a **class method**, and it gets only `options` and `target` — Home Assistant strips and
  validates the generic keys (`alias`, `id`) itself.
- `run_action(payload, description)`: the payload is merged into the automation's `trigger` variable, the description
  appears in the trace and the logbook.
- `did_not_trigger` is optional; call it with a `NotTriggeredInfo` when a change was looked at and deliberately not
  fired on, so the trace shows why.
- The listener reads what the coordinator or a dispatcher signal delivers — a trigger never polls the API itself.

## Condition

```python
from typing import Unpack

from homeassistant.helpers.condition import Condition, ConditionCheckParams, ConditionConfig


class {ClassPrefix}IsChargingCondition(Condition):
    """Test if a device is charging."""

    @classmethod
    async def async_validate_config(cls, hass: HomeAssistant, config: ConfigType) -> ConfigType:
        """Validate the options and target of the condition."""
        return _IS_CHARGING_SCHEMA(config)

    def __init__(self, hass: HomeAssistant, config: ConditionConfig) -> None:
        """Keep the validated options."""
        super().__init__(hass, config)
        self._target = config.target

    def _async_check(self, **kwargs: Unpack[ConditionCheckParams]) -> bool:
        """Return whether the condition holds right now."""
        ...


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the conditions of this integration."""
    return {"is_charging": {ClassPrefix}IsChargingCondition}
```

- Implement `_async_check`, never `async_check` — the public one is `@final` and wraps it in tracing. It runs on every
  evaluation: no I/O, read state that is already in memory.
- `_async_setup()` (async) and `_async_unload()` are optional hooks for a condition that subscribes to something.

## Entity-state factories

For triggers and conditions that only follow entity states, `homeassistant.helpers.trigger` has
`make_entity_target_state_trigger(domain, to_states)` and friends, and `homeassistant.helpers.condition` has
`make_entity_state_condition(domain, states)`, `make_entity_numerical_condition` and base classes such as
`EntityNumericalConditionBase`. They select entities by **entity domain** (`light`), not by integration, which is why
Core's entity domains use them; a custom integration usually needs its own class. `homeassistant/components/light/`
`trigger.py` and `condition.py` are the reference implementations.

## Description, text and icons

- `triggers.yaml` / `conditions.yaml` use the `services.yaml` format: `target`, `fields`, selectors. A trigger with
  neither is `fault_reported: {}`. Top-level keys starting with `.` are ignored, for YAML anchors. Hassfest requires
  the file once the platform registers anything.
- Strings in `translations/en.json` under `triggers` / `conditions`: `name`, `description`, and a `name` per field. No
  `sections`. See [`ha-translations`](../../ha-translations/SKILL.md).
- Icons in `icons.json`: `"triggers": {"fault_reported": {"trigger": "mdi:alert"}}` and
  `"conditions": {"is_charging": {"condition": "mdi:battery-charging"}}`.

## Naming

Users see every integration's triggers side by side. Pick one noun for the device type and use it in every trigger,
condition and action of the integration.

| Kind      | Title                                                                           | Key                                          | Description                                          |
| --------- | ------------------------------------------------------------------------------- | -------------------------------------------- | ---------------------------------------------------- |
| Trigger   | Device type first, an event that just happened: "Charger started charging"      | `started_charging`, `fault_reported`         | "Triggers when one or more chargers start charging." |
| Condition | "[Device type] is [state]", "… is not …"; for values "[Device type] [property]" | `is_charging`, `is_not_charging`, `is_level` | "Tests if one or more chargers are charging."        |

- Activities take "started" / "stopped"; a bare state ("Battery low") is not a trigger title — "Battery became low" is.
- Condition keys start with `is_`; a subtype goes in front (`blind_is_open`).
- Keys are `snake_case` and never repeat the domain — `fault_reported`, not `<domain>_fault_reported`.
