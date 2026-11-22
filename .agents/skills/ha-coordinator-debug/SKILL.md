---
name: ha-coordinator-debug
description: >-
  Diagnose and fix runtime problems in this Home Assistant custom integration — entities showing "unavailable" or
  "unknown", stale data, the integration failing to set up, "Config entry not ready", repeated reauth prompts,
  coordinator update failures, timeouts, or blocking-call warnings. Use when asked to "debug", "why is my sensor
  unavailable", "the integration won't load", "data isn't updating", "check the logs", "restart Home Assistant",
  or when investigating anything in coordinator/, api/, or the setup path. Covers the run loop, `script/ha`, when
  to read `config/.storage/` instead, and the coordinator failure contract. SYMPTOMS — load this if you are about to: invent your own
  `hass`/`pytest` command instead of the project scripts; read or write `config/.storage/` while Home Assistant is
  running; ask the developer to read a state or download diagnostics from the UI for you; return None from
  `_async_update_data` to signal failure; or catch Exception broadly in the coordinator.
---

# Debug the running integration

Work from evidence, not from guesses. The order below is deliberate: reproduce, read the log, localise to a layer, then
fix.

| File                                                     | When to read                                                                          |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| [`references/async-rules.md`](references/async-rules.md) | A blocking-call warning, a thread-safety error, or a hang with no traceback behind it |

## 1. Reproduce with a clean instance

Always use the project scripts — hand-rolled `hass` or `pip` invocations miss the venv, `PYTHONPATH`, port cleanup, and
debugpy setup, and are the single most common cause of agents getting stuck.

```bash
./script/develop
```

If Home Assistant is unresponsive or the port is held:

```bash
pkill -f "hass --config" || true && pkill -f "debugpy.*5678" || true && ./script/develop
```

Restart after **any** change to Python files, `manifest.json`, `services.yaml`, translations, or the config flow.

Once it is up, [`script/ha`](../blueprint-tooling/references/ha-cli.md) reads the instance directly — entity states,
config entry status, diagnostics, the error log — so nothing below depends on asking the developer to look something
up in the UI. It authenticates itself; there is no token to set up.

```bash
script/ha status     # reachable, and which version
script/ha entries    # did the config entry actually load
```

### The instance is shared

The developer restarts Home Assistant, clicks through the UI, and tries things out while you work — often precisely
because you are busy. **Never carry the instance's run state from one step to the next. Observe it.**

```bash
script/ha status    # exit 0 up, exit 2 down; `started` and `uptime` reveal a restart you did not do
```

- **A changed run state is the expected case, not a fault.** Running when you left it stopped means the developer
  started it. Do not go through `ps`, the process tree, or the log looking for an explanation — start it, or re-run
  your command, and carry on.
- **Spend at most one re-check on it.** If it still does not add up, say what you observed and continue with the task.
  Reconciling who started what is never the task.
- **`./script/develop` takes the instance over — it is not "start it if it is not running".** It kills whatever is
  already bound to `config/` and starts its own, by design, because the log has to stream into the terminal that
  launched it. So the developer's terminal falls silent, and the live log they were watching is gone. Check
  `script/ha status` first and simply use the instance that is already there. Run `script/develop` only when it is
  genuinely down, or when a change to Python, `manifest.json`, `services.yaml`, translations or the config flow
  forces a restart — and say that you are doing it. Never restart to tidy up.
- **The same happens in reverse**, and is equally fine: when the developer runs `./script/develop`, the instance you
  started dies and whatever file you were writing its log to stops growing. Treat that as normal and re-orient.
- **Announce it before you take exclusive control**, so the developer knows to keep their hands off meanwhile. That
  covers `script/setup/reset`, `script/ha token --rotate` and `--revoke`, and any loop that restarts repeatedly — all
  of them need Home Assistant stopped or undisturbed.
- **The Home Assistant environment is the developer's choice, never yours.** `script/ha-env use`,
  `script/ha-env refresh` and `script/develop --env` move every terminal, `script/test` and the instance to another
  version at once. Switch only when asked; `script/ha-env list` and `script/ha status` show what is active and who
  started the running instance. Never pass `--force` to `script/ha-env use` or `script/develop` without asking, and name the
  environment that is active when you finish.
- **`ha call`, `ha flow`, `ha reload` and `ha loglevel` change what the developer sees.** Cheap and reversible, but a
  config entry created by a flow stays until someone removes it.
- **State the run state when you finish — after checking it**, never from memory.

### Ask the instance, or read the files?

There are two sources of truth for runtime state, and which one is correct depends only on whether Home Assistant is
running. Getting this backwards is the most common way to debug a ghost.

**While Home Assistant runs, the API is authoritative and the files under `config/.storage/` are stale by design** —
they are `Store.async_delay_save` files, written some time after the change they describe. Everything here about
`config/` applies to `.local/ha-config/<name>/` while another environment is active; `script/ha status` names the
directory as `config_dir`.

| What                              | Written                                            |
| --------------------------------- | -------------------------------------------------- |
| entity / device / area registry   | 10 s after a change — but **180 s during startup** |
| config entries                    | 1 s after a change                                 |
| `core.restore_state`              | every 15 minutes, and on shutdown                  |
| `home-assistant_v2.db` (recorder) | every `commit_interval` seconds — 30 s here        |

So a registry entry you just created can be missing from `core.entity_registry` for three minutes, and **live state is
in none of these files at all** — `core.restore_state` is a periodic snapshot, and the recorder holds history, not the
present.

| Question                                           | Use                                         |
| -------------------------------------------------- | ------------------------------------------- |
| What is this entity's state right now              | `script/ha states` / `entity`               |
| Did the entry load, and why not                    | `script/ha entries`                         |
| What unique IDs / registry flags does it have      | `script/ha entities`                        |
| What does the coordinator actually hand out        | `script/ha diagnostics`                     |
| Did an error happen                                | `script/ha logs`, then the log file         |
| Startup order, full traceback, surrounding context | `config/home-assistant.log`                 |
| The previous run                                   | `config/home-assistant.log.1`               |
| What a migration persisted                         | `config/.storage/*` — **with HA stopped**   |
| Whether a value changed over the last hours        | `script/ha watch`, or the recorder database |

Reading the raw files is right when Home Assistant is **stopped**: post-mortem analysis, checking what a config entry
migration actually wrote, or diffing `.storage` before and after a change. Then they are the only source, and they are
accurate.

**Never write into `config/.storage/` while Home Assistant is running.** It holds every store in memory and rewrites
the whole file on its next save, so your edit is discarded — silently, minutes later. `script/setup/seed-auth` takes
Home Assistant's own `.ha_run.lock` for exactly this reason. `config/.storage/auth` and `dev_access_token` are
additionally read-denied: they are credentials, not debugging material.

## 2. Read the log

Start with the structured log — it is deduplicated, counts repeats, and keeps each traceback attached to its record:

```bash
script/ha logs --level error        # then widen to --level warning
script/ha logs --grep coordinator
```

The raw stream is still there when you need surrounding context: live in the terminal running `./script/develop`, and
in `config/home-assistant.log` (previous run in `config/home-assistant.log.1`).

```bash
rg -n "<domain>|Traceback|ERROR|WARNING" config/home-assistant.log | tail -50
```

Raise verbosity without restarting — this takes effect immediately:

```bash
script/ha loglevel custom_components.<domain>=debug homeassistant.helpers.update_coordinator=debug
```

It does not survive a restart. For a level that should, put it in `config/configuration.yaml` and restart:

```yaml
logger:
  default: warning
  logs:
    custom_components.<domain>: debug
```

Read the **first** error in a cascade, not the last. A wall of "Error doing job" usually has one root cause above it.

Two debug modes catch what no log level shows: Home Assistant's own, and asyncio's. With both on, calling an `async_*`
API from the wrong thread and blocking the event loop are reported the moment they happen, instead of surfacing later
as an unexplained hang or a state that quietly went wrong.

A `debug_console:` line in `config/configuration.yaml` adds a Python console under **Settings** >
**Tools**, with `hass` in scope — quicker than a log line and a restart for inspecting live objects. It runs in the event
loop, so never call anything blocking there.

**A config flow missing after a restart is usually the frontend cache, not the code.** Hard-refresh the browser before
debugging the flow.

## 3. Localise the failure

Each symptom has one command that produces the evidence, so you are reading state rather than guessing at it.

| Symptom                                           | Command                          | Layer to inspect                                                                   |
| ------------------------------------------------- | -------------------------------- | ---------------------------------------------------------------------------------- |
| Integration missing from the add-integration list | `script/ha setup-info`           | `manifest.json`, import error at module load — check the log at startup            |
| "Config entry not ready, retrying"                | `script/ha entries`              | `_async_update_data` / `_async_setup` raising `ConfigEntryNotReady`                |
| Entry loads, all entities `unavailable`           | `script/ha states`               | coordinator's first refresh failed, or `last_update_success` false                 |
| Entities available but values `unknown`/`None`    | `script/ha entity sensor.<id>`   | key mismatch between `coordinator.data` and the entity's read path                 |
| Values never change                               | `script/ha watch --seconds 120`  | `update_interval`, caching in the API client, or a swallowed error                 |
| Endless reauth prompts                            | `script/ha entries`              | `ConfigEntryAuthFailed` raised for a non-auth failure                              |
| Config flow rejects valid input                   | `script/ha flow start`           | see [`ha-config-flow`](../ha-config-flow/SKILL.md)                                 |
| "Detected blocking call inside the event loop"    | `script/ha logs --level warning` | sync I/O in async code — see [`ha-modern-apis`](../ha-modern-apis/SKILL.md)        |
| Entity duplicated after an update                 | `script/ha entities`             | `unique_id` changed — see [`ha-breaking-changes`](../ha-breaking-changes/SKILL.md) |

`script/ha entries` prints the entry `state` and its `reason` — the same text the UI shows, which is usually the whole
diagnosis for a setup failure.

`script/ha watch` deserves care: Home Assistant fires `state_changed` only when the state or an attribute genuinely
changes, so an empty watch is a finding, not a failed measurement. It means the coordinator is handing back identical
data, not that notification is broken.

Cross-check the actual payload rather than assuming its shape:

```python
LOGGER.debug("Coordinator data: %s", self.data)
```

`script/ha diagnostics | jq .data` shows the same payload without an edit and a restart, whenever the integration
implements diagnostics.

## 4. Check the failure contract

`_async_update_data` communicates through exception type, and getting it wrong is the root of most availability bugs.
The exception mapping table is in
[`blueprint.coordinator.instructions.md`](../../instructions/blueprint.coordinator.instructions.md). Read the
coordinator against it and check for the four failures that table cannot express:

- **Signalling failure by returning** `None` or an empty dict instead of raising. Entities then show `unknown` forever
  instead of going unavailable, and nothing retries.
- **A broad `except Exception`** that swallows the auth error, so reauth never triggers and the entry just looks broken.
  The OAuth2 helper's token errors are the same trap — see the instructions file's Authentication rules.
- **Logging on every failed poll.** The coordinator logs the first failure and then stays quiet by design
  (`log-when-unavailable`, Silver). Manual logging buries the real error in repetition.
- **`ConfigEntryNotReady` raised outside setup**, or `async_config_entry_first_refresh()` called outside setup.

## 5. Common fixes

**Update interval too aggressive** — the Bronze `appropriate-polling` rule. Local devices ~30 s, cloud services
~5–15 min, fixed in code — never a user option
([`blueprint.config_flow`](../../instructions/blueprint.config_flow.instructions.md#data-vs-options)).

**Timeouts** — every request needs one, with `asyncio.timeout`, never a bare `await`:

```python
async with asyncio.timeout(10):
    response = await self._session.get(url)
```

**Partial data** — when only part of the payload is missing, keep the previous value instead of dropping the whole
update; only raise when the update is genuinely useless.

**Entity reads the wrong key** — compare the `EntityDescription.key` / `value_fn` against the logged payload.

**Setup ordering** — expensive one-off work (fetching device metadata, capabilities) belongs in `_async_setup()`, which
runs once before the first refresh, not in `_async_update_data`.

**A listener or reconnect loop that outlives an unload** — start it with
`entry.async_create_background_task(hass, coro, name)`, which is cancelled when the entry unloads and does not hold up
startup. `hass.async_create_task` survives the unload and keeps running against a dead entry.

## 6. Confirm the fix

```bash
script/lint && script/type-check
script/test
```

Restart, reproduce the original scenario, and confirm the log is clean:

```bash
pkill -f "hass --config" && ./script/develop     # any change to a .py file needs this
script/ha entries                                 # state: loaded, reason: -
script/ha states                                  # the values you expected
script/ha logs --level warning                    # nothing new
```

If the failure was data-shaped, check the payload directly — `script/ha diagnostics | jq .data` should now show the
corrected structure. Diagnostics must run everything through `async_redact_data()`; if you added a field, make sure it
is redacted when sensitive.

`script/ha reload` is the shortcut when the change is confined to entry data or options — it reloads the config entry
without restarting the instance. It does **not** re-import Python, so it is never a substitute for a restart after a
code edit.

## 7. Add a regression test

A runtime bug that reached a user is exactly the case where a test pays for itself. Add one that reproduces the
original failure before the fix. See [`ha-testing`](../ha-testing/SKILL.md).

## Stop conditions

After three failed attempts at the same error, stop and report what you tried and what you observed. Do not keep
looping — a wrong mental model does not improve with repetition.
