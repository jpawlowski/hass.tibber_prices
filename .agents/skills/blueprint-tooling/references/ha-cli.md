# `script/ha` — the development instance from the terminal

Reads and controls the Home Assistant instance started by `script/develop`. It exists so debugging does not depend on
reading a log file and asking a human to click through the UI: entity states, config entry status, diagnostics, the
error log, service actions, and config flows are all reachable directly.

The debugging procedure that uses these commands is
[`ha-coordinator-debug`](../../ha-coordinator-debug/SKILL.md). This file is the command reference.

## Authentication

`script/setup/seed-auth` mints a long-lived access token offline and stores it in
`config/.storage/dev_access_token` (mode `0600`, gitignored, excluded from template sync). `script/develop` runs it on
every start, so there is nothing to set up and nothing to paste.

`script/ha` reads that file itself. **The token never appears in a command line, in output, or in an agent's context** —
`script/ha token` prints metadata only.

| Situation                             | What happens                                                                    |
| ------------------------------------- | ------------------------------------------------------------------------------- |
| Instance not onboarded yet            | No token. Complete onboarding in the browser, then restart Home Assistant once. |
| Just after `script/setup/reset`       | Same — the token appears on the **second** `script/develop`.                    |
| Token expired or revoked              | `script/ha token --rotate` with Home Assistant **stopped**.                     |
| You do not want a token in this clone | `export HA_DEV_TOKEN=0` in `script/hooks/develop.pre.sh`.                       |

## Global options

| Option / variable  | Default                 | Effect                                                      |
| ------------------ | ----------------------- | ----------------------------------------------------------- |
| `--json`           | off                     | raw JSON instead of a table — pipe it into `jq`             |
| `--all`            | off                     | widen a listing from this integration to the whole instance |
| `--timeout N`      | `10`                    | request timeout in seconds                                  |
| `--url` / `HA_URL` | `http://127.0.0.1:8123` | target another instance                                     |
| `HA_TOKEN`         | the seeded token file   | authenticate as someone else                                |

**Listings are scoped to this repository's integration by default.** The domain comes from `manifest.json`, so nothing
has to be passed.

Output is redacted: `token`, `access_token`, `authorization`, `password`, `api_key`, `latitude`, and `longitude` are
replaced with `**REDACTED**` wherever they appear as keys.

### Exit codes

| Code | Meaning                                                              |
| ---- | -------------------------------------------------------------------- |
| `0`  | success                                                              |
| `1`  | the command failed — a bad argument, or Home Assistant refused it    |
| `2`  | Home Assistant is not reachable — start it with `./script/develop`   |
| `3`  | authentication failed — rotate the token with Home Assistant stopped |

## Inspecting

```bash
script/ha status                       # up? since when? which version, environment and config dir, who started it
script/ha entries                      # config entry state and failure reason
script/ha states                       # every entity of this integration
script/ha states sensor.<id>           # one entity in full, attributes included
script/ha entity sensor.<id>           # state + registry entry + platform source
script/ha entities                     # registry entries: unique_id, disabled_by, entity_category
script/ha devices                      # devices owned by this integration
script/ha setup-info                   # setup timing and the manifest
```

`script/ha status` also reports `started`, `uptime`, and `pid`, read from the `flock` Home Assistant holds on
`config/.ha_run.lock`. That matters because the instance is shared: an `uptime` of seconds when you left it running for
an hour means the developer restarted it. Use this instead of `ps` or `pgrep` — the lock file stays behind after a
shutdown with a stale PID, so its mere presence proves nothing, and only the lock is authoritative.
`environment` and `started_by` come from what `script/develop` recorded when it started the instance: which Home
Assistant environment (`script/ha-env`) it runs, and whether the developer or an agent started it.

When it is not reachable, `status` still distinguishes the two cases: nothing running at all, or a local instance
holding the lock but not answering yet because it is still starting.

`script/ha entries` is the first command to run on a setup failure: `state` and `reason` carry exactly what the UI
would show, without opening it.

`script/ha entities` is how to check unique IDs before and after a change — see
[`ha-breaking-changes`](../../ha-breaking-changes/SKILL.md).

## Diagnostics

```bash
script/ha diagnostics                  # config entry diagnostics as JSON
script/ha diagnostics --device <id>    # device diagnostics
script/ha diagnostics | jq .data       # the integration's own payload
```

This replaces _Settings → Devices & services → ⋮ → Download diagnostics_. If the integration has no
`async_get_config_entry_diagnostics`, the command says so rather than returning a bare 404.

## Logs

```bash
script/ha logs                                    # warnings and above, newest last
script/ha logs --level error -n 10                # only errors
script/ha logs --grep coordinator                 # filter by text
```

Reads `system_log/list` over the WebSocket API, not the log file: records are deduplicated with a repeat count, and the
traceback stays attached to the record it belongs to. For the raw stream, `config/home-assistant.log` is still there.

```bash
script/ha loglevel custom_components.<domain>=debug
script/ha loglevel homeassistant.helpers.update_coordinator=debug
```

**Takes effect immediately, with no restart and no edit to `configuration.yaml`.** It does not survive a restart — use
the `logger:` block in `config/configuration.yaml` for a level that should.

## Watching state change

```bash
script/ha watch                                   # 30s of state_changed for this integration
script/ha watch --seconds 120                     # a full poll cycle of a slow coordinator
script/ha watch --entity sensor.<id>              # one entity (repeatable)
script/ha watch --event call_service --all        # any event type
```

This is the way to answer "does this value ever actually update". Home Assistant only fires `state_changed` when the
state or an attribute really changes, so silence here is itself the finding: the coordinator is returning identical
data, not merely failing to notify.

## Acting

```bash
script/ha reload                                  # reload the config entry
script/ha services                                # this integration's actions and their fields
script/ha call <domain>.<action> entity_id=sensor.<id>
script/ha call <domain>.<action> --data '{"nested": {"key": 1}}'
script/ha call <domain>.<action> --response       # actions with SupportsResponse
script/ha template '{{ integration_entities("<domain>") | count }}'
```

`key=value` values are parsed as JSON when they can be, so `brightness=255` is a number and `name=Kitchen` is a string.

**`script/ha reload` reloads the config entry, which is enough for changed options or a stuck coordinator. It does not
re-import Python.** After editing any `.py` file, restart:

```bash
pkill -f "hass --config" && ./script/develop
```

There is deliberately no `script/ha restart`: `script/develop` runs Home Assistant in the foreground with no
supervisor, so a restart request would simply stop it.

## Config, options, and reconfigure flows

```bash
script/ha flow handlers                           # does this integration offer a config flow at all
script/ha flow start                              # begin setup
script/ha flow start --reconfigure                # reconfigure the existing entry
script/ha flow options                            # open the options flow
script/ha flow show <flow_id>                     # current step of a running flow
script/ha flow step <flow_id> key=value ...       # submit
script/ha flow abort <flow_id>
```

Each step prints its `step_id`, any `errors`, the description placeholders, and a flattened schema — field name,
whether it is required, its selector type, and its default — so the next `step` can be filled in without opening a
browser.

Two behaviours worth knowing:

- **Fields you do not pass fall back to the step's own defaults**, because Home Assistant validates a step against its
  whole schema and would otherwise reject every field you left out. Pass `--exact` to submit only what you typed.
  A required field with no default must still be given.
- **A flow id is enough** — config flows and options flows live at different endpoints, and the right one is detected.

Reauth and reconfigure finish by aborting with a reason ending in `_successful`; that counts as success and exits `0`.

Flows are held in memory, so anything left half-finished disappears on the next restart.

## Token management

```bash
script/ha token                                   # metadata only: never the token itself
script/ha token --rotate                          # mint a fresh one   (Home Assistant stopped)
script/ha token --revoke                          # remove it entirely (Home Assistant stopped)
```

Both `--rotate` and `--revoke` delegate to `script/setup/seed-auth`, which refuses to touch the auth store while Home
Assistant is running — a token written into a running instance is discarded when it next saves.

## When `script/ha` is the wrong tool

It talks to a **running** instance. With Home Assistant stopped, every command exits `2` — and that is the point at
which the files under `config/` become the right thing to read.

| Home Assistant is… | Authoritative                                                                    |
| ------------------ | -------------------------------------------------------------------------------- |
| running            | `script/ha`. `config/.storage/*` lags by 1–180 s and holds no live state at all. |
| stopped            | the files. `config/.storage/*` is then accurate and is the only source.          |

Two things `script/ha` deliberately does not cover, because the log file already does them better: the startup
sequence, and the full surrounding context of a traceback. Use `config/home-assistant.log`, or
`config/home-assistant.log.1` for the previous run.

**Never edit `config/.storage/` while Home Assistant is running** — it rewrites each store wholesale from memory on its
next save, so the edit disappears without a message. The decision table and the per-store save delays are in
[`ha-coordinator-debug`](../../ha-coordinator-debug/SKILL.md).

## Targeting another instance

```bash
HA_URL=http://192.168.1.10:8123 HA_TOKEN=<token> script/ha entries --all
```

Useful for reproducing against a real installation. Everything is scoped by `--domain` rather than by the local
checkout, so `--domain <other>` inspects another integration entirely.
