---
name: "Config Flow"
description: "Setup, options, reauth, reconfigure, discovery, unique IDs, and entry migration"
applyTo: "custom_components/**/config_flow_handler/**/*.py, custom_components/**/config_flow.py"
paths:
  - "custom_components/**/config_flow_handler/**/*.py"
  - "custom_components/**/config_flow.py"
---

# Config Flow Instructions

**Procedure:** [`ha-config-flow`](../skills/ha-config-flow/SKILL.md) — load it before touching setup, options, reauth,
reconfigure, discovery or subentries. This file is the rule set; the skill is which flow a request actually needs and
what has to happen alongside it, including the entry migration a shape change forces.

**Official Documentation:**

- [Data Entry Flow Index](https://contributors.home-assistant.io/core/integrations/flow-steps/) - Fundamental flow concepts and result types
- [Config Entries Index](https://contributors.home-assistant.io/core/integrations/config-entries/) - Overview and lifecycle
- [Config Flow Handler](https://contributors.home-assistant.io/core/integrations/config-flow/)
- [Options Flow Handler](https://contributors.home-assistant.io/core/integrations/options-flow/)

## Architecture Overview

**Data Entry Flow** is the framework — `FlowHandler`, the result types, form schemas — and config flows, options
flows, subentry flows and repair flows are all built on it. The same `async_show_form()` / `async_create_entry()`
mechanics therefore work identically in all of them.

- **Config flow** creates the entry: immutable `data` (credentials, host) plus mutable `options`.
- **Options flow** only ever changes `options`. Changing `data` is a reconfigure, not an option.
- **Repair flows** live in `repairs.py` and follow a different architecture — see
  [`blueprint.repairs`](blueprint.repairs.instructions.md).

**Data Entry Flow has nothing to do with `data.py`.** The names collide and mean opposite things: one collects input
from users, the other types `entry.runtime_data`.

## Data Entry Flow Fundamentals

Every step method must return one of these result types (see [Data Entry Flow docs](https://contributors.home-assistant.io/core/integrations/flow-steps/)):

**Result Types:**

- `FORM` - Show form: `async_show_form(step_id, data_schema, errors={}, description_placeholders={})`
- `CREATE_ENTRY` - Create entry: `async_create_entry(title, data={}, options={})`
- `ABORT` - Stop flow: `async_abort(reason="...")`
- `SHOW_MENU` - Navigation menu: `async_show_menu(step_id, menu_options=[...])`
- `EXTERNAL_STEP` - OAuth2 redirect: `async_external_step(step_id, url)` then `async_external_step_done(next_step_id)`
- `SHOW_PROGRESS` - Long tasks: `async_show_progress(step_id, progress_action, progress_task)` then `async_show_progress_done(next_step_id)`
  - Report a fraction with `self.async_update_progress(0.5)` (0–1)
  - While the task is still running, call `async_show_progress` again — never start a second task

**Always pass `step_id`** to `async_show_form`, `async_show_menu`, `async_show_progress` and `async_external_step`:
the name of the step method you are in, without `async_step_`. Leaving it out is deprecated, and the
inferred ID is wrong whenever one step method calls another.

### Form Schemas

Schemas are written with Probatio (`import probatio`), the validation library Home Assistant uses — not voluptuous.

**Simple fields** - `probatio.Required("field"): str`, `probatio.Optional("field", default=value): int`

**Rich UI** - Use [selectors](https://contributors.home-assistant.io/glossary/selector/): `TextSelector`,
`NumberSelector`, `EntitySelector`, `DeviceClassSelector`, `StateClassSelector`, etc.

**Sections** - Group with `section()`:
`probatio.Required("advanced"): section(probatio.Schema({...}), {"collapsed": True})`

- Only **one level** — a section inside a section is not allowed.
- A section **nests the submitted data**: `{"host": …, "advanced": {"port": …}}`. Read it accordingly. (Sections in
  `services.yaml` do the opposite and leave the data flat — see `blueprint.services_yaml`.)
- Icons for a section go under `config.step.<step>.sections.<name>`.
- Options most users never need go in a collapsed section. **Never read `self.show_advanced_options`** — it is
  deprecated and always returns `True`.

**Fields that depend on another field** — `visible=` and the device-class-driven unit selector:
[`flow-types.md`](../skills/ha-config-flow/references/flow-types.md#fields-that-depend-on-another-field).

**Schema hygiene:**

- Required keys first, optional second.
- An optional key's default must be a **valid value** — `probatio.Optional(CONF_X, default=None): cv.string` is wrong;
  use `default=""`.
- Reach for the specific validator before `cv.string`: `probatio.Port()`, `cv.url`, `cv.positive_int`,
  `cv.small_float`, `cv.entity_id`, `cv.time_zone`, `cv.slug`, `cv.icon`, `cv.temperature_unit`.
- Wrap the key of a password, token or PIN in `probatio.Secret(...)` —
  `probatio.Required(probatio.Secret(CONF_PASSWORD))` — so a validation error never echoes the value.
- A `probatio.In(...)` field with no `default` pre-selects the first option in the frontend.

**Menus** - `async_show_menu(..., sort=True)` sorts entries by their translated label; per-entry help text comes from
`menu_option_descriptions` in the translations.

**Do not use `SchemaConfigFlowHandler`.** It writes every value into `options`, which contradicts the data/options
split below, so it cannot hold connection data or credentials.

**Pre-filling:**

- Default values: `probatio.Optional("field", default="value")`
- Suggested values: `probatio.Optional("field", description={"suggested_value": "value"})`
- Merge from existing: `self.add_suggested_values_to_schema(schema, entry.options)`

**Read-only fields** - Set `read_only=True` in selector config (e.g., `EntitySelectorConfig(read_only=True)`)

### Validation and Error Handling

**Return errors dict for validation failures** - Use translation keys. Attach an error to the field that caused it —
`errors={CONF_HOST: "invalid_host"}` — and use `"base"` only for what concerns the whole form:
`errors={"base": "cannot_connect"}`.

**Common error keys:** `cannot_connect`, `invalid_auth`, `unknown`. `already_configured` is an **abort** reason, not
an error — `_abort_if_unique_id_configured()` ends the flow with it.

**Pattern:** Try validation → catch exceptions → set errors → re-show form

**MUST log unexpected exceptions:** `_LOGGER.exception("Unexpected exception")`

### Multi-Step Flows

**Store data between steps** - Save to instance: `self.step_data = user_input`

**Forward to next step** - Return: `return await self.async_step_next_step()`

**Access previous data** - Read from instance: `self.step_data`

### Browser Autofill

**Option 1:** Use recognized field names (`username`, `password` → auto-mapped)

**Option 2:** Explicit autocomplete in selectors: `TextSelectorConfig(autocomplete="username")`

**Common values:** `username`, `current-password`, `email`, `tel`, `postal-code`

## File Organization

- Place config flow in `config_flow_handler/config_flow.py`
- Place options flow in `config_flow_handler/options_flow.py`
- Place subentry flow in `config_flow_handler/subentry_flow.py` (if needed)
- Place shared logic in `config_flow_handler/handler.py`
- Place schemas in `config_flow_handler/schemas/*.py`
- Place validators in `config_flow_handler/validators/*.py`
- **MUST** maintain `config_flow.py` at integration root (hassfest requirement) that imports from package

## Data vs Options

Where a value lives is decided once and changing it later requires a migration.

| `entry.data`                                             | `entry.options`                                           |
| -------------------------------------------------------- | --------------------------------------------------------- |
| Identity and connection: host, port, API key, account ID | Behaviour the user may tune later: thresholds, filters    |
| Anything needed to establish the connection at all       | Anything safe to change without re-validating credentials |

**MUST:**

- Keep credentials in `entry.data` only — never in `entry.options`, never in the entry title.
- Reuse `CONF_*` names from `homeassistant.const` where one exists; otherwise define them in `const.py`.
- Give every schema field a `selector.*` and a default. A bare `probatio.Coerce(int)` renders as an untyped box and is
  a review blocker.
- Give every field both a `data` and a `data_description` translation key.
- Pre-fill with `self.add_suggested_values_to_schema(schema, entry.data)` on reconfigure and options.
- Tolerate entries created before the field existed — supply a default at read time or migrate.

```python
probatio.Optional(CONF_THRESHOLD, default=DEFAULT_THRESHOLD): selector.NumberSelector(
    selector.NumberSelectorConfig(min=1, max=60, unit_of_measurement="%", mode=selector.NumberSelectorMode.BOX),
),
```

**NEVER** offer the polling interval as a field, in setup or options (Quality Scale `appropriate-polling`; Core's
pylint check `home-assistant-config-flow-polling-field`). The integration picks an interval that suits most users;
anyone who needs another one disables polling for the entry and drives `homeassistant.update_entity` from an
automation.

**Consumers:** the coordinator reads `entry.options`, the API client reads `entry.data`.

## Step Names

**Reserved discovery steps** (require manifest entry):

- `bluetooth`, `dhcp`, `homekit`, `mqtt`, `ssdp`, `usb`, `zeroconf`

**Reserved system steps:**

- `user` - User-initiated setup
- `reauth` - Re-authentication flow
- `reconfigure` - Configuration changes
- `import` - YAML migration
- `hassio` - A Supervisor app announced itself (`HassioServiceInfo`)
- `integration_discovery` - Another integration found a device for this one and started the flow with
  `discovery_flow.async_create_flow(hass, DOMAIN, context={"source": SOURCE_INTEGRATION_DISCOVERY}, data=…)`. Always
  start flows from code with that helper — it de-duplicates and waits for Home Assistant to start.

**Rules:**

- If discovery step exists → called on discovery
- If discovery step omitted → `user` step called on discovery, and only while the integration has no config entry yet
- A user step that sets the same unique ID as discovery passes `raise_on_progress=False` to `async_set_unique_id`, so a
  user setting up by hand is not aborted by an open discovery flow for the same device.
- **NEVER** auto-create entries from discovery - always confirm with user first
- **`discovery` is a deprecated step name** — never implement `async_step_discovery`. Use the specific step for the
  protocol.
- A reauth flow starts with `source`, `entry_id` and `unique_id` in `self.context`, and sets `title_placeholders` to
  `{"name": <entry title>}` for you. A reconfigure flow gets no `title_placeholders`; pass the name through
  `description_placeholders` yourself.

## Unique IDs

**MUST:**

- Set unique ID for all discovery flows: `await self.async_set_unique_id(device_id)`
- Call `self._abort_if_unique_id_configured()` to prevent duplicates
- Use stable identifiers: serial number, MAC address, device ID, latitude/longitude, an identifier printed on the
  device, or — for a cloud service — an account ID that is guaranteed collision-free
- Take the MAC **from the device API or the discovery handler** and normalise it with `format_mac()`. Reading the ARP
  cache (`getmac` and similar) does not work in every supported network setup and is not acceptable.
- **Never** use an email address or a username. Core's docs accept them for cloud services; this project does not,
  because the user can change both at the provider. Use the account ID the API returns.
- Use `updates` parameter to refresh config data: `self._abort_if_unique_id_configured(updates={CONF_HOST: host})`

**NEVER:**

- Use IP addresses (can change via DHCP)
- Use device names (user-changeable)
- Use URLs (can change)
- Use a hostname the user can change. Only the stable substring of a hostname that encodes a serial or MAC is
  acceptable — the hostname itself is not.

**Discovery without unique ID:**

- Use `await self._async_handle_discovery_without_unique_id()` if ID unavailable
- Implement `is_matching(other_flow)` if unique ID is ambiguous

## The individual flows

Each flow type has its own MUST/NEVER list — user, discovery, reauth, reconfigure, options, subentry — in
[`ha-config-flow/references/flow-types.md`](../skills/ha-config-flow/references/flow-types.md). Read the section for
the flow you are implementing.

Setup failures in `async_setup_entry()` are not this file's scope: see
[`blueprint.python`](blueprint.python.instructions.md).

## Version and Migration

**Define versions in ConfigFlow:**

- `VERSION` - Major (breaking changes), `MINOR_VERSION` - Minor (compatible)

**Implement `async_migrate_entry()` in `__init__.py`:**

- Handle only the versions you know — `if entry.version == 1 and entry.minor_version < 2:`. Home Assistant never
  calls it for a **newer major** version (it refuses that entry itself), and a **newer minor** version from a later
  release must be left alone. A `if entry.version > N: return False` branch is dead code.
- Return nothing: success is the absence of an exception. A custom integration's `True` still works, but is
  deprecated.
- Update via `hass.config_entries.async_update_entry(entry, version=X, minor_version=Y)`
- On failure, **raise** rather than return `False`: `ConfigEntryNotReady` when retrying later can succeed,
  `ConfigEntryError` when it cannot — the repair that retries the latter:
  [`migration.md`](../skills/ha-config-flow/references/migration.md).
- Log migration events

Both default to `1`; set them only when implementing a migration.

**Minor:** Compatible changes. A newer minor version still loads even without `async_migrate_entry`.
**Major:** Breaking changes, requires migration — and a major bump means the entry **fails to load** if the user
downgrades Home Assistant. That asymmetry is the reason to prefer a minor bump whenever the change is additive.

## Titles and Translations

**Title priority:** `title_placeholders` + `flow_title` → `title_placeholders["name"]` → `title` → manifest `name` → domain

**Set placeholders:** `self.context["title_placeholders"] = {"name": device_name}`

Two ways a `flow_title` is silently ignored: `title_placeholders` is missing or empty (even when `flow_title` has no
placeholders at all), or it is non-empty but has no `name` key and there is no localized `flow_title`.

**Translation keys:** `config.step.<step>.title`, `config.error.<key>`, `config.abort.<key>`

## Config Entry Lifecycle

**States:** `not loaded`, `setup in progress`, `loaded`, `setup error`, `setup retry`, `migration error`, `unload in progress`, `failed unload`

**Setup (in `__init__.py`):**

**`async_setup_entry(hass, entry)`** - Forward platforms, return `True`, raise `ConfigEntryNotReady`/`ConfigEntryAuthFailed`

**`async_unload_entry(hass, entry)`** - Always implement it. `entry.async_on_unload()` callbacks are not a substitute,
and they also run when `async_setup_entry` raises.

**`async_remove_entry(hass, entry)`** - Optional, cleanup cloud resources after deletion

**CRITICAL:**

- **NEVER mutate ConfigEntry directly** - Use `hass.config_entries.async_update_entry()`
- Use `entry.async_on_unload()` for cleanup callbacks
- To react to another entry changing state: `entry.async_on_unload(entry.async_on_state_change(callback))`
- `ConfigEntryNotReady` only works from `async_setup_entry` in `__init__.py`. Raised from a platform it is inert.
- Entity cleanup: `async_will_remove_from_hass()` in entities
