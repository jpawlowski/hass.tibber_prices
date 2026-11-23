---
name: "Integration Manifest"
description: "Required manifest.json fields, integration types, and IoT classes"
applyTo: "**/manifest.json"
paths:
  - "**/manifest.json"
---

# Manifest Instructions

**Applies to:** `custom_components/<your_domain>/manifest.json`

## Schema Validation

**Schema:** `/schemas/json/manifest_schema.json`

This schema combines Home Assistant's official manifest requirements with the fields the Marketplace requires. Always validate against this schema.

## Required Fields

```json
{
  "domain": "your_domain",
  "name": "Your Integration Title",
  "codeowners": ["@your_github_username"],
  "config_flow": true,
  "documentation": "https://github.com/your_org/your_repo",
  "integration_type": "device",
  "iot_class": "cloud_polling",
  "issue_tracker": "https://github.com/your_org/your_repo/issues",
  "requirements": [],
  "version": "0.0.0"
}
```

## Field Reference

**Core fields:**

- `domain` - Integration identifier (matches directory name)
- `name` - Display name in Home Assistant
- `version` - Required: the Marketplace refuses to install without it, and it must equal the release tag. Any version
  AwesomeVersion recognises works (SemVer, CalVer); this project uses SemVer, and `script/version` owns the field.
- `documentation` - Link to documentation
- `issue_tracker` - Link to GitHub issues (required for the catalog)
- `codeowners` - GitHub usernames for notifications

**Integration behavior:**

- `config_flow` - Boolean, true if integration has UI config
- `integration_type` - One of: `device`, `hub`, `service`, `helper`. `virtual` can only be provided by Home Assistant
  Core, and `entity`, `hardware` and `system` are not for integrations like this one. Unset defaults to `hub` — set it
  explicitly.
- `iot_class` - Connectivity type (see below)
- `requirements` - Python package dependencies

**Optional fields:**

- `dependencies` - Integrations loaded before setup. This guarantees the integration is **loaded**, not that its
  config entries are set up. A custom integration may list both built-in and other custom integrations here.
- `after_dependencies` - Load after these integrations, without requiring them
- `loggers` - The logger names the integration's requirements use in their `getLogger` calls, so the user's log-level
  setting reaches the library too
- `single_config_entry` - `true` prevents the user adding a second entry. This is the only thing that makes "the one
  entry" a safe assumption in a service action handler.
- `categories` - One to three values from the
  [category list](https://contributors.home-assistant.io/core/integrations/categories/), `category` or
  `category.subcategory`, the primary one first; `schemas/json/manifest_schema.json` carries the same list. Optional
  for a custom integration, but the catalog publishes them and the HACS action warns when the key is missing.
- `quality_scale` - The tier the integration claims: `bronze` to `platinum`, or `custom`. Optional for custom
  integrations and not shown in the UI. Hassfest rejects `silver` and above without a non-empty `codeowners`.
- `disabled` - A reason string that stops Home Assistant from loading the integration at all; it only logs the reason.
  An emergency brake for a release that must not run, never a feature switch.
- `import_executor` - Custom integrations only. Defaults to `true`, importing the integration off the event loop; set
  `false` only when the import itself must run in the event loop.
- `dhcp`, `zeroconf`, `ssdp`, `usb`, `bluetooth` - Discovery configs. Each protocol has a matcher rule that fails
  silently when guessed — see
  [`ha-config-flow/references/discovery-matchers.md`](../skills/ha-config-flow/references/discovery-matchers.md).
- `homekit`, `mqtt` - Protocol configs
- `preview_features` - Home Assistant Labs features the user switches on themselves, keyed by slug, each with optional
  `feedback_url`, `learn_more_url` and `report_issue_url`. Works for a custom integration too; point the URLs at this
  repository, and read the switch with `async_is_preview_feature_enabled()` /
  `async_subscribe_preview_feature()` from `homeassistant.components.labs`.

There is **no minimum Home Assistant version key** in `manifest.json`. That lives in `hacs.json` → `homeassistant`
([`ha-marketplace`](../skills/ha-marketplace/SKILL.md)), and raising it is a breaking change
([`ha-breaking-changes`](../skills/ha-breaking-changes/SKILL.md)).

**Naming:** if the product exists as both a local and a cloud integration, the cloud one appends "Cloud". The local
one uses the plain product name — never append "Local".

## IoT Class Values

Choose the most accurate:

- `cloud_polling` - Cloud API with polling
- `cloud_push` - Cloud API with push updates
- `local_polling` - Local device with polling
- `local_push` - Local device with push updates
- `calculated` - Derived from other entities
- `assumed_state` - Cannot verify state

## Requirements Format

Use package name with version constraint:

```json
"requirements": [
  "some-package==1.2.3"
]
```

**Only list what Home Assistant does not already ship.** A custom integration must not repeat a package from Core's
own `requirements.txt` — `aiohttp`, `probatio`, `httpx`, `awesomeversion` and friends are already there, and
pinning them from here can only conflict with Core.

## Validation

`script/hassfest` is the gate. Home Assistant and the Marketplace also validate on install and load, and errors appear
in the log.

## References

- [Manifest Documentation](https://contributors.home-assistant.io/core/integrations/manifest/)
- [IoT Class](https://contributors.home-assistant.io/core/integrations/manifest/#iot_class)
- [Marketplace: custom integrations](https://contributors.home-assistant.io/marketplace/guides/integrations/)
