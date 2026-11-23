---
name: "Service Action Implementation"
description: "Registration in async_setup(), schemas, exceptions, and response data"
applyTo: "custom_components/**/service_actions/**/*.py"
paths:
  - "custom_components/**/service_actions/**/*.py"
---

# Service Actions Instructions

**Procedure:** [`ha-service-action`](../skills/ha-service-action/SKILL.md) — load it before adding, changing or
removing an action. This file is the rule set; the skill is the order of operations and the design decisions, and it
covers the `services.yaml` half of the change too.

**Applies to:** Service action implementation files

**Reference:** [Home Assistant Service Actions Documentation](https://contributors.home-assistant.io/core/integrations/actions/)

## Critical Rules

**Registration location (Bronze Quality Scale requirement `action-setup`):**

- ✅ Register service actions in `async_setup()` (component level)
- ❌ Never register in `async_setup_entry()` (per config entry)
- Check `hass.services.has_service(DOMAIN, "action_name")` before registering

**Service naming:**

- Format: `<integration_domain>.<action_name>`
- Always use integration DOMAIN, never platform domain (e.g., `sensor`, `switch`)

**Implementation structure:**

- `async_setup_services(hass)` is a `@callback` (registration does no I/O), called without `await` from `async_setup()`
  in `__init__.py`
- An `async_setup()` makes hassfest require a `CONFIG_SCHEMA` in `__init__.py`. For a config-entry-only integration it
  is `CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)`, which also tells a user who adds the domain to
  `configuration.yaml` that it is not read
- Register the actions in `service_actions/__init__.py`; put the handler bodies in a module per logical group
- Resolve the target with `homeassistant.helpers.service`: `service.async_get_config_entry(hass, DOMAIN, entry_id)`
  for a `config_entry_id` field, `service.async_get_device_and_config_entry(hass, DOMAIN, device_id)` for a
  `device_id` field. Both raise a translated `ServiceValidationError` when the entry or device is unknown, belongs to
  another integration, or is not loaded — do not hand-write those checks or invent `entry_not_found`-style keys
- An action that acts on every entry iterates `hass.config_entries.async_loaded_entries(DOMAIN)`, never
  `async_entries()`, which also returns entries that are not loaded and have no `runtime_data`
- Reach state through `entry.runtime_data`. **NEVER** use `hass.data[DOMAIN]` — this integration stores runtime
  state on the config entry.

## Service Schema

Use `probatio` with `homeassistant.helpers.config_validation` for parameter validation. Home Assistant validates with
`probatio`, and service registration is typed against `probatio.Schema` — a `voluptuous` schema fails type checking.

```python
import probatio

from homeassistant.helpers import config_validation as cv

SERVICE_SCHEMA = probatio.Schema({
    probatio.Required("device_id"): cv.string,
    probatio.Optional("force", default=False): cv.boolean,
})
```

## Exception Handling

**Use appropriate exceptions:**

- `ServiceValidationError` - the caller provided invalid data
- `HomeAssistantError` - anything else failed, such as the device not responding

Neither is logged with a stack trace at the default log level; the difference is what the caller gets back (a
`service_validation_error` or `home_assistant_error` over WebSocket, status 400 or 500 over REST). Both take
translation keys.

**Authentication failures need `entry.async_start_reauth(hass)`.** `ConfigEntryAuthFailed` only triggers the reauth
flow when it is raised from `async_setup_entry` in `__init__.py` or from the coordinator. Raised in an action handler
it does nothing but log, so start the flow explicitly and raise a translated `HomeAssistantError` for the caller.

**Wrap every device and library failure in `HomeAssistantError`.** An automation step with `continue_on_error` skips
only a `HomeAssistantError` (`ServiceValidationError` included); any other exception stops the run, and so do
configuration errors — schema, template, unknown action or entity (`CONFIGURATION_ERRORS` in `helpers/script.py`).

**Calling an action twice is harmless.** Automations retrigger more often than anyone expects; a second identical
call must not double an effect.

## Target Field

Use modern `target` field in `services.yaml` instead of deprecated `entity_id`:

```yaml
reset_filter:
  target:
    entity:
      domain: sensor
```

## Response Data

Services can return JSON-serializable data (`homeassistant.util.json.JsonObjectType`) for use in automations:

**Critical requirements:**

- Response MUST be a `dict`
- **datetime objects MUST use `.isoformat()`** - Template engine cannot handle raw datetime
- Raise exceptions for errors, never return error codes in response data
- The shape is an interface automations are built against: changing a key or the structure is a breaking change
  ([`ha-breaking-changes`](../skills/ha-breaking-changes/SKILL.md))

**SupportsResponse modes:**

- `SupportsResponse.OPTIONAL` - Returns data only if `call.return_response` is True
- `SupportsResponse.ONLY` - Always returns data, performs no action

Example with datetime conversion:

```python
from homeassistant.core import SupportsResponse

async def search_items(call: ServiceCall) -> ServiceResponse:
    items = await client.search(call.data["start"], call.data["end"])
    return {
        "items": [
            {
                "summary": item["summary"],
                "timestamp": item["timestamp"].isoformat(),  # ✅ Convert datetime!
            }
            for item in items
        ],
    }

hass.services.async_register(
    DOMAIN, "search", search_items,
    supports_response=SupportsResponse.ONLY,
)
```

## Entity Service Actions

For services targeting entities, use `async_register_platform_entity_service`:

```python
from homeassistant.helpers import service

service.async_register_platform_entity_service(
    hass,
    DOMAIN,  # Integration domain, NOT platform domain!
    "set_timer",
    entity_domain="media_player",
    schema={probatio.Required("sleep_time"): cv.time_period},
    func="set_sleep_timer",  # Method name on entity class
)
```

`func` takes either the name of a method on the entity class, as above, or a callable `(entity, service_call)`.

## Service Icons

Define in `icons.json`:

```json
{
  "services": {
    "turn_on": { "service": "mdi:lightbulb-on" },
    "start_brewing": {
      "service": "mdi:flask",
      "sections": { "advanced_options": "mdi:test-tube" }
    }
  }
}
```

## Permissions

**A call without `call.context.user_id` comes from Home Assistant itself** — an automation, a script, a time trigger.
Never reject it for that reason; doing so breaks every automation that calls the action.

- An action that changes configuration or has other security implications is registered with
  `service.async_register_admin_service(hass, DOMAIN, name, handler, schema)` instead of
  `hass.services.async_register`. It rejects non-admin users before the handler runs and lets system calls through.
  Entity actions take `admin_only=True` on `async_register_platform_entity_service` instead.
- A handler that acts on an entity ID it received outside `target:` checks the user's right to control it:

```python
from homeassistant.auth.permissions.const import POLICY_CONTROL
from homeassistant.exceptions import Unauthorized, UnknownUser

if call.context.user_id:
    user = await hass.auth.async_get_user(call.context.user_id)
    if user is None:
        raise UnknownUser(context=call.context)
    if not user.permissions.check_entity(entity_id, POLICY_CONTROL):
        raise Unauthorized(context=call.context, entity_id=entity_id, permission=POLICY_CONTROL)
```

## Security

- A file path from the caller is checked with `hass.config.is_allowed_path(path)` before it is read or written. It
  does blocking I/O, so run it through `hass.async_add_executor_job`.
- A URL from the caller that Home Assistant will fetch is checked with `hass.config.is_allowed_external_url(url)`.
- Data reported by the device or the cloud is untrusted too: validate it before it becomes part of a URL, a file path
  or a command.
