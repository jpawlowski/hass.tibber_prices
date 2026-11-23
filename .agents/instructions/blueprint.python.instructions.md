---
name: "Python Code"
description: "Module layout, type hints, async patterns, imports, logging, and validation"
applyTo: "**/*.py"
paths:
  - "**/*.py"
---

# Python Code Instructions

**Applies to:** All Python files in the integration

## File Structure

### Module Organization

**Integration modules:**

- `__init__.py` - Platform setup with `async_setup_entry()`
- Individual files - One class per file when practical
- `const.py` - Module constants only (no logic)

**File size guidelines:**

- **Target:** 200-400 lines per file
- **Maximum:** ~500 lines before refactoring
- **Reason:** AI models have context limits - keep files manageable

**When a file grows too large:**

1. Extract helper functions to separate files
2. Move entity classes to individual files
3. Create subpackages for related functionality
4. Split constants into logical groups

**Example structure:**

```text
sensor/
  __init__.py          # Setup and entity list (50 lines)
  air_quality.py       # Air quality sensor class (200 lines)
  temperature.py       # Temperature sensor class (150 lines)
  diagnostic.py        # Diagnostic sensors (180 lines)
  const.py             # Sensor-specific constants (30 lines)
```

**Naming:**

- Files: `snake_case.py`
- Classes: `PascalCase` prefixed with the integration's class prefix (defined in project identity)
- Functions/methods: `snake_case`
- Constants: `UPPER_SNAKE_CASE`

## Type Annotations

**Required for:**

- All function parameters and return values
- Class attributes (when not obvious)

**Import rules:**

- Never `from __future__ import annotations` — Home Assistant requires Python 3.14, where annotations are already
  lazily evaluated; Ruff's `banned-api` rejects it
- `collections.abc` for abstract base classes (prefer over `typing`)
- `typing` for complex types (Any, TYPE_CHECKING, etc.)

**Avoiding circular imports:**

Use `if TYPE_CHECKING:` block for type-only imports that would cause circular dependencies.

**Narrowing a type for Pyright:** an `assert x is not None` belongs **inside** a `TYPE_CHECKING` block, so it exists
for the type checker and changes nothing at runtime:

```python
if TYPE_CHECKING:
    assert self.config_entry is not None
```

**Docstrings** are Google style when they need more than a summary line — `Args:`, `Returns:`, `Raises:`. Leave the
types out; the annotations already carry them.

## Async Patterns

**All I/O operations must be async** - Network, file, database, blocking operations

**Core patterns:**

- `async def` for coroutines, `await` for async calls
- `asyncio.gather()` for concurrent operations
- `asyncio.timeout()` for timeouts (not `async_timeout`)
- Never: `time.sleep()`, synchronous HTTP libraries, blocking operations

**Running blocking code:**

- `await hass.async_add_executor_job(sync_function, arg1, arg2)` - Run blocking I/O in executor thread
- Avoid if sync function also uses executor internally (deadlock risk)

**Background tasks:** inside an integration, create tasks on the **config entry**, not on `hass` — the entry cancels
them on unload, which `hass.async_create_task` does not.

- `entry.async_create_task(hass, coroutine)` - Work that must finish before the entry unloads
- `entry.async_create_background_task(hass, coroutine, name)` - Long-lived loops (a listener, a reconnect loop)
- `hass.async_create_task(coroutine)` - Only in `async_setup()` scope, where there is no entry
- All three default to `eager_start=True`: the coroutine runs synchronously up to its first `await` before the call
  returns. Do not assume it starts on the next loop iteration — ordering-sensitive code and tests will surprise you.
- `asyncio.run_coroutine_threadsafe(coro, hass.loop).result()` - From sync thread (rare)

**Callback decorator:**

- `@callback` from `homeassistant.core` - For event loop functions without blocking
- Required for event listeners, state change callbacks
- Cannot do I/O, cannot call coroutines (only schedule them)
- Missing decorator causes execution in executor thread (wrong context)

**Never block the event loop.** File and directory operations, `urllib`, `time.sleep` and SSL context loading all
block; so does calling an `async_*` API from a worker thread, which raises outright. The lookup tables — which sync
twin to call from a thread, the full blocking-call list with the `open()` trap, and the four late-import cases — are
in [`ha-coordinator-debug/references/async-rules.md`](../skills/ha-coordinator-debug/references/async-rules.md).

**Late imports:** module-level imports are safe. Anything conditional needs one of the import helpers in that
reference, because CPython's import machinery is not thread-safe. Type-only imports go in `if TYPE_CHECKING:`.

## Code Style

**Conventions not enforced by Ruff:**

- Alphabetical sorting of constants/lists when order doesn't matter
- Comments: see `blueprint.comments.instructions.md` for when one is warranted at all — the default is none, and
  those that survive are complete sentences with capitalization and an ending period

**Note:** Ruff enforces `__all__`/`__slots__` sorting, import ordering, f-string usage in logs.

## Home Assistant Requirements

**Setup Failure Handling:**

See [Integration Setup Failures](https://contributors.home-assistant.io/core/integrations/setup-failures/) for details.

- `ConfigEntryNotReady` - Device offline/unavailable, retry later (raise in `async_setup_entry()`)
- `ConfigEntryAuthFailed` - Expired credentials (triggers reauth flow)
- `ConfigEntryError` - Will not resolve on its own (closed account, unsupported device); stops the retry loop
- Pass error message to exception (HA logs at debug level automatically)
- **Do NOT log setup failures manually** - Avoid log spam
- **Do NOT write your own retry loop** - Home Assistant already retries `ConfigEntryNotReady` with exponential backoff
- Outside setup and the coordinator, `ConfigEntryAuthFailed` does nothing — call `entry.async_start_reauth(hass)`
- Raising any of the three still runs the `entry.async_on_unload` callbacks, but does **not** replace
  `async_unload_entry` — that always has to exist
- Raising `ConfigEntryNotReady` in a **platform's** `async_setup_entry` does nothing; by then the config entry setup
  has already completed and cannot catch it

**Constants:**

- Prefer `homeassistant.const` over defining new ones (e.g., `CONF_USERNAME`, `CONF_PASSWORD`)
- Only add to integration's `const.py` if widely used internally

**Units of Measurement:**

- Always use constants from `homeassistant.const` - Never hardcode strings
- Examples: `UnitOfDensity.MICROGRAMS_PER_CUBIC_METER`, `UnitOfRatio.PERCENTAGE`, `UnitOfTime.HOURS` — not the bare
  `PERCENTAGE` or the `CONCENTRATION_*` constants
  ([`deprecations.md`](../skills/ha-modern-apis/references/deprecations.md#entities))
- Construct compound units if no combined constant exists: `f"{UnitOfLength.METERS}/{UnitOfTime.SECONDS}"`
- **Do not convert units Home Assistant can convert.** Set `native_unit_of_measurement` and let Home Assistant convert
  according to `hass.config.units`. Where the device class has no converter — money, currency subunits, prices per
  unit — converting is the integration's job
  ([`ha-user-experience`](../skills/ha-user-experience/SKILL.md#units-users-think-in)). `hass.config.language`,
  `.country` and `.currency` are there too, when an API needs a locale.

**Time and Timestamps:**

- Always use UTC timestamps (ISO 8601 or Unix)
- Use `dt_util.utcnow().isoformat()` from `homeassistant.util`
- Never use relative time ("2 hours ago") in state/attributes

**Service Actions:**

- Format: `<integration_domain>.<action_name>`
- Register under integration domain (not platform domain)
- Example: `hass.services.async_register(DOMAIN, "reset_filter", handler)`

**Event Names:**

- Prefix with integration domain: `<domain>_<event_name>`
- Example: `hass.bus.async_fire(f"{DOMAIN}_device_paired", data)`
- Event data — like state attributes — must be **JSON-serializable**. A `datetime` or a dataclass breaks the
  recorder and the WebSocket API; convert before firing. Fired events land in the recorder database, so keep the
  payload small.

**PARALLEL_UPDATES:**

- Required in **every** platform `__init__.py`, not optional — a missing one fails the `parallel-updates` rule
- A module-level literal, never imported from `const.py`; `0` or `1` is decided per platform in
  [`blueprint.entities`](blueprint.entities.instructions.md)
- Left undefined, Home Assistant derives it: `1` only when the entity has a sync `update()`, otherwise unlimited

## Imports

Ruff orders them. **Standard HA aliases:** `cv`, `dr`, `er`, `dt_util`. Schemas use a plain `import probatio`
(`probatio.Schema`, `probatio.Required`, …), not `import voluptuous as vol` — see
[`ha-modern-apis`](../skills/ha-modern-apis/references/deprecations.md#schema-validation--voluptuous-replaced-by-probatio).

**A relative import may not reach into a parent package.** Ruff's `TID252` runs with the default
`ban-relative-imports = "parents"`, the same setting Home Assistant Core uses, so `from ..const import DOMAIN` is
rejected wherever it appears — including inside an `if TYPE_CHECKING:` block. Siblings within the same package are
fine.

- ✅ `from .base import {ClassPrefix}Entity` — same package
- ✅ `from custom_components.<domain>.const import DOMAIN` — anything above it
- ❌ `from ..const import DOMAIN`, `from ...api import ApiClient`

The absolute form is long, and reaching for `..` to shorten it is the reflex this rule exists to stop: `script/lint`
reports it, but only after the file is written.

## Error Handling

**Use specific exceptions from integration's exception module**

- Keep `try` blocks small — only the call that can raise, with the code that uses its result in `else:`.
- `except Exception` only as the **last** handler of a config-flow step, to turn the unexpected into an `unknown`
  error (and log it with `_LOGGER.exception`). Nowhere else — not in the coordinator, not in an API client.
- Log **or** raise, never both: a raised exception is logged where it is handled.
- Read keys a schema has already validated as `data["key"]`, not `data.get("key")`; `.get()` is for keys that may be
  missing, such as one added in a later entry version.

**Errors that reach the user** — from a service action handler _and_ from an entity method
(`async_set_native_value`, `async_set_hvac_mode`, …) — are a translated `ServiceValidationError` or
`HomeAssistantError`, **never `ValueError`**, which reaches the user as an unhandled crash. Which of the two:
[`blueprint.service_actions`](blueprint.service_actions.instructions.md#exception-handling).

**Logging:** `_LOGGER.exception()` inside an exception handler, `_LOGGER.info()` sparingly and only for something the
user needs. No period at the end (syslog style), never a credential, token or API key in any line at any level, and
`%` formatting rather than an f-string (Ruff G004). When a line must identify a key or an account ID, mask it with
`partial_redact(value)` from `homeassistant.helpers.redact` — users attach debug logs to public issues.

## Validation

`script/python` then `script/type-check`, until both exit 0 — the full loop and the fix/check matrix are in
[`blueprint-tooling`](../skills/blueprint-tooling/SKILL.md).

**Suppressing a check:** always with the specific code and a reason — `# noqa: F401 - Reason`,
`# type: ignore[attr-defined] - Reason`. Never bare `# noqa`, `# type: ignore` or `# ruff: noqa`.

## Verify Current Patterns

Home Assistant APIs evolve fast enough that a remembered pattern is unreliable. **The installed source in the
devcontainer is the authority** — grep it before trusting recall, a blog post, or an older integration:

```bash
rg -n "deprecated|breaks_in_ha_version" .venv/lib/python*/site-packages/homeassistant/helpers/<module>.py
```

The procedure and the full deprecation table: [`ha-modern-apis`](../skills/ha-modern-apis/SKILL.md).
