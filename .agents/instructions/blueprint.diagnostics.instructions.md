---
name: "Diagnostics"
description: "Redacting credentials and personal data from diagnostics output"
applyTo: "custom_components/**/diagnostics.py"
paths:
  - "custom_components/**/diagnostics.py"
---

# Diagnostics Instructions

**Applies to:** Diagnostics implementation files

## Critical: Always Redact Sensitive Data

**Use `async_redact_data()` for all user data:**

```python
from homeassistant.helpers.redact import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

# Define what to redact
TO_REDACT = {
    CONF_PASSWORD,
    CONF_USERNAME,
    "api_key",
    "token",
    "refresh_token",
}

async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data.coordinator

    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "entry_options": async_redact_data(entry.options, TO_REDACT),
        "coordinator_data": async_redact_data(coordinator.data, TO_REDACT),
    }
```

**The coordinator data is redacted too.** An API payload usually holds more than the entities show — serials,
coordinates, account names — and users post this file in public issues. Read the real output once, not just the code.

A device or entity registry entry goes in through `device_entry_as_dict()` / `entity_entry_as_dict()` from
`homeassistant.components.diagnostics`, which leave out the registry's internal fields. Where an identifier has to
stay recognisable, `homeassistant.helpers.redact.partial_redact()` masks all but its first and last characters.

## Device-Level Diagnostics

A second, optional entry point. Implement it when a single device's data is worth downloading on its own; without it,
the device page offers the config entry diagnostics instead.

```python
async def async_get_device_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
    device: DeviceEntry,
) -> dict[str, Any]:
    """Return diagnostics for a device."""
```

Either function may exist on its own, or both together. Redaction rules are identical.

## Never Expose

The following must ALWAYS be redacted:

- Passwords
- API keys / tokens (access_token, refresh_token, api_key, etc.)
- OAuth credentials
- Location data (latitude/longitude)
- Personal information (email, phone, name)
- Device serial numbers (if considered sensitive)
- MAC addresses (use `format_mac` if needed for identification)

## Testing

Cover the output with a snapshot test, so every change to it shows up in review:
`get_diagnostics_for_config_entry` / `get_diagnostics_for_device` from
`pytest_homeassistant.components.diagnostics` return exactly what a user downloads. Read the snapshot
for anything that should have been redacted before committing it — procedure in
[`ha-testing`](../skills/ha-testing/SKILL.md).

## When in Doubt

If you're unsure whether data is sensitive, **redact it**. Better to redact too much than expose credentials.
