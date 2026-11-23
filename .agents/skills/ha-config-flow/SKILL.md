---
name: ha-config-flow
description: >-
  Work on the Home Assistant config flow of this custom integration — the setup UI, options flow,
  reauthentication, reconfigure, discovery (zeroconf, dhcp, ssdp, bluetooth, usb, mqtt, homekit), subentries,
  unique IDs, and config entry version migration. Use when asked to "add a config option", "add a setting", "ask
  the user for X during setup", "add an options flow", "support reauth", "add discovery", "make the host
  configurable", "migrate the config entry", or when editing config_flow_handler/, its schemas/ and validators/,
  or manifest discovery matchers. Covers reserved step names, acceptable unique IDs, abort reasons, validation,
  and the migration contract. SYMPTOMS — load this if you are about to: use a host or IP as the unique ID; create
  a config entry without validating the connection; store a credential in `entry.options`; read `entry.data[key]`
  for a key old entries will not have; or change entry data without bumping VERSION/MINOR_VERSION.
---

# Work on the config flow

The config flow is the only supported way to configure a device or service integration ([ADR-0010](https://github.com/home-assistant/architecture/blob/master/adr/0010-integration-configuration.md)). Everything the user
can change lives here, and mistakes here are expensive: `unique_id` and the shape of `entry.data` are effectively
permanent.

**Read [`blueprint.config_flow.instructions.md`](../../instructions/blueprint.config_flow.instructions.md)
first.** It is the authoritative rule set: data-vs-options, reserved step names, acceptable unique IDs and their
normalisation, schema hygiene, title placeholders, and the migration contract. Copilot injects it automatically when
you edit a config flow file; other agents must open it. This skill is the order of operations and the decisions; the
MUST/NEVER list for each individual flow is in the first reference below.

| File                                                                   | When to read                                                                    |
| ---------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| [`references/flow-types.md`](references/flow-types.md)                 | Implementing one flow — user, discovery, reauth, reconfigure, options, subentry |
| [`references/discovery-matchers.md`](references/discovery-matchers.md) | Writing a `manifest.json` discovery matcher, or using a discovery helper API    |
| [`references/oauth2.md`](references/oauth2.md)                         | The service authenticates with OAuth2 rather than an API key or a password      |
| [`references/migration.md`](references/migration.md)                   | A config entry migration can fail, and the user needs a way to retry it         |

## Package layout

Where each piece goes. The example ships `__init__.py`, `config_flow.py`, `schemas/config.py` and
`validators/credentials.py`; create the rest when something needs them, rather than leaving empty scaffolding behind.

```text
config_flow_handler/
├── __init__.py          # exports
├── config_flow.py       # user, reauth, reauth_confirm, reconfigure, discovery steps
├── options_flow.py      # post-setup options, only when there is something to tune
├── handler.py           # logic shared between the flows above
├── subentry_flow.py     # multi-device / multi-account subentries
├── schemas/
│   ├── config.py        # probatio schemas for setup steps
│   └── options.py       # probatio schemas for the options flow
└── validators/
    ├── credentials.py   # "can we actually talk to it" checks
    └── sanitizers.py    # input normalisation (strip, lowercase host, …)
```

The top-level `config_flow.py` is a thin shim Home Assistant discovers — leave it alone.

## Adding a config option

1. **Decide data or options** using the table in the instructions file. This is the one irreversible choice here.
   A polling interval is neither — it is not a field at all. In an integration without options yet, the first real
   option is when `options_flow.py` and `schemas/options.py` get created.
2. Add the `CONF_*` key to `const.py`.
3. Add the field to `schemas/config.py` or `schemas/options.py` with a selector and a default.
4. Consume it: coordinator reads `entry.options`, client reads `entry.data`.
5. Add the `data` and `data_description` translation keys ([`ha-translations`](../ha-translations/SKILL.md)). The
   description says what the option changes. Once the options no longer fit one screen, or an automation should
   change one, see [`ha-user-experience`](../ha-user-experience/SKILL.md#6-options-that-stay-navigable).
6. **Handle existing entries** that predate the key — a default at read time, or a `MINOR_VERSION` bump plus migration.
   This is the step that gets forgotten and breaks upgrades.

## Adding discovery

1. Add the matcher to `manifest.json` — read
   [`references/discovery-matchers.md`](references/discovery-matchers.md) first, because each protocol has a rule
   that fails silently when you guess (lowercase-only zeroconf properties, DHCP MACs arriving without separators,
   VID/PID pairs shared by hundreds of devices):

   ```json
   "zeroconf": [{ "type": "_myservice._tcp.local.", "name": "blueprint*" }]
   ```

2. Implement the matching `async_step_<method>()` following the discovery MUST/NEVER list in
   [`references/flow-types.md`](references/flow-types.md).
3. Decide what the discovery payload gives you as a stable unique ID. If it offers nothing stable, stop and discuss it
   — do not fall back to the IP address.
4. Confirm the flow end-to-end in the UI: the card shows a useful name, a second discovery of the same device aborts,
   and a device that changed IP updates the existing entry rather than creating a second one.

## Config entry migration

Bump `MINOR_VERSION` for additive changes, `VERSION` for restructuring. Read
[`ha-breaking-changes`](../ha-breaking-changes/SKILL.md) first — changing entry data affects every existing install.

Implement `async_migrate_entry()` in `custom_components/<domain>/__init__.py`:

```python
async def async_migrate_entry(hass: HomeAssistant, entry: {ClassPrefix}ConfigEntry) -> None:
    """Migrate an old config entry."""
    if entry.version == 1 and entry.minor_version < 2:
        data = {**entry.data, CONF_PORT: DEFAULT_PORT}
        hass.config_entries.async_update_entry(entry, data=data, minor_version=2)
```

No downgrade branch and no `return False` — the contract is under
[Version and Migration](../../instructions/blueprint.config_flow.instructions.md#version-and-migration); a migration
that can fail needs [`references/migration.md`](references/migration.md).

Migrations must be idempotent and must never delete a key they do not understand. Cover every migration with a test
([`ha-testing`](../ha-testing/SKILL.md)).

## Validate

```bash
script/lint && script/type-check
script/hassfest          # cross-checks every step/error/abort key against translations
script/test
```

Then restart Home Assistant and **walk every flow you touched** — add, reconfigure, options, and, by invalidating the
credential, reauth. hassfest proves the translation keys exist; only walking the flow proves it is usable. A flow that
passes CI and dead-ends on the second step is the normal failure here.

Walk it from the terminal first — it is faster, it is repeatable, and it shows the serialised schema Home Assistant
actually built, which is where defaults and selectors go wrong:

```bash
script/ha flow start                              # or --reconfigure
script/ha flow step <flow_id> host=192.0.2.10 username=admin password=secret
script/ha flow options                            # then step through it the same way
script/ha entries                                 # the entry exists and loaded
```

Each step prints its `step_id`, any `errors`, and every field with its type and default. Full reference:
[`references/ha-cli.md`](../blueprint-tooling/references/ha-cli.md).

Two things only the browser can confirm, so finish there: that the translated labels and `data_description` hints read
correctly, and that the form renders the way the selectors promise.

## Do not

- Do not do blocking I/O or long retries inside a flow step; validate with a short timeout.
- Do not call the flow done before walking it end to end.
- Do not give an optional free-text field `default=None` — probatio injects that default when the field is left
  empty and the selector then rejects it, making the form unsubmittable. Carry the current value in
  `description={"suggested_value": ...}` instead.
