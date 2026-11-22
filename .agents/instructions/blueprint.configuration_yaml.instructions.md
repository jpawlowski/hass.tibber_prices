---
name: "Home Assistant Configuration"
description: "Modern configuration.yaml syntax for the local test instance"
applyTo: "**/configuration.yaml"
paths:
  - "**/configuration.yaml"
---

# Home Assistant Configuration Instructions

**Applies to:** `configuration.yaml` files

## Schema

**Schema:** `/schemas/yaml/configuration_schema.yaml`

Consult this schema for available configuration options and structure.

## Minimal Structure

For development and testing, keep configuration minimal:

```yaml
# Load default configuration
default_config:

# Enable your integration
your_domain:

# Logging for development
logger:
  default: info
  logs:
    custom_components.your_domain: debug
```

## Modern Syntax Only

Three renames that older examples still get wrong, and Home Assistant accepts silently:

- `trigger: state` inside the trigger list, **not** `platform: state`
- `action:` for a service call, **not** the deprecated `service:`
- triggers and conditions are lists, even with one entry

## Logger Configuration

**Adjust log levels for debugging:**

```yaml
logger:
  default: warning
  logs:
    # Your integration - verbose
    custom_components.your_domain: debug

    # Reduce noise from other components
    homeassistant.components.http: warning
    homeassistant.components.websocket_api: error

    # Keep important helpers visible
    homeassistant.helpers.entity_registry: info
    homeassistant.helpers.device_registry: info
    homeassistant.config_entries: info
```

## Validation

Home Assistant validates this file at startup — `script/develop`, then read the terminal or
`config/home-assistant.log`. Deprecated syntax still loads, so a clean start is not proof it is current; check the
[automation documentation](https://www.home-assistant.io/docs/automation/) when in doubt.
