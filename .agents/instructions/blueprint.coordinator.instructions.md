---
name: "Coordinator and API Client"
description: "Three-layer architecture, update intervals, pull versus push, caching, and the API exception hierarchy"
applyTo: "custom_components/**/coordinator/**/*.py, custom_components/**/api/**/*.py"
paths:
  - "custom_components/**/coordinator/**/*.py"
  - "custom_components/**/api/**/*.py"
---

# Coordinator and API Client Instructions

**Procedure:** [`ha-coordinator-debug`](../skills/ha-coordinator-debug/SKILL.md) — load it when data is stale, entities
are unavailable or setup fails. This file is the rule set; the skill is the local run loop, how to read the log, and
the four coordinator failures no exception-mapping table can express.

**Applies to:** the coordinator and the API client. An integration that fetches nothing has no `api/` package; the
layering below is unchanged either way.

## Three-Layer Architecture (CRITICAL)

**Entities → Coordinator → API Client** - Never skip layers

- **Entities:** Read `coordinator.data` only, never call API
- **Coordinator:** Calls API, transforms data, handles errors/timing
- **API Client:** HTTP communication, auth, exception translation

✅ **Correct:** `self.coordinator.data.temperature` (in entity properties)

❌ **Wrong:** `await self.api_client.get_data()` (never fetch directly in entities)

## API Client vs PyPI Library

The criteria are in `AGENTS.md` § Custom Integration Flexibility. The choice is expensive to reverse: record it in
a decision record in `docs/development/decisions/` (see [`blueprint-decisions`](../skills/blueprint-decisions/SKILL.md)). Adding the dependency itself —
`manifest.json` **and** `requirements.txt`, kept in sync — is covered by
[`blueprint-tooling`](../skills/blueprint-tooling/SKILL.md).

## API Client Rules

**Session management:**

- MUST accept `aiohttp.ClientSession` parameter in `__init__`
- NEVER create session (`aiohttp.ClientSession()`) in client
- Session comes from `async_get_clientsession(hass)` in `__init__.py`

**Timeout handling:**

- Use `asyncio.timeout()` not `async_timeout`
- Set reasonable timeout per request (10-30s typical)

**Return values:**

- Return raw API response data; let the coordinator transform it for entities
- **Mirror the API's own structure**, even where it is badly designed or contains a typo. A client that "improves"
  the shape hides what the service actually returns, and the next reader cannot match it against the API docs.
- **Never convert units** (Celsius/Fahrenheit and friends). That decides precision and rounding on the caller's
  behalf; set `native_unit_of_measurement` on the entity and let Home Assistant convert.
- Implement pagination here — fetch all pages and hand the coordinator a complete dataset.

**Building a URL that points back at Home Assistant** — a webhook target, a device callback, a proxied image — use
`homeassistant.helpers.network.get_url(hass, ...)`. It knows about internal versus external, SSL, and Nabu Casa, none
of which can be reconstructed from `hass.config.internal_url`. It raises `NoURLAvailableError` when no suitable URL
exists; catch it rather than falling back to a guess.

**Webhooks** — the ID is the only secret a webhook has: generate it with `webhook.async_generate_id()`, never derive
it from the entry or device. Register with `local_only=True` whenever the caller is on the local network.

**Authentication:**

- The auth layer authenticates; it does not **store**. Persisting tokens is the config entry's job.
- Return tokens as JSON-serializable values (`str`, `int`, `float`, and dicts of those) so they survive being written
  into `entry.data`.
- With the OAuth2 helper, let its token errors (`OAuth2TokenRequestError` and subclasses,
  `ImplementationUnavailableError`) propagate — they already are `ConfigEntryNotReady` / `ConfigEntryAuthFailed`.
  Never wrap them in `UpdateFailed`, which would turn a reauth into an endless retry.
- A debug line that has to identify a key, token or account ID masks it — see `partial_redact` in
  [`blueprint.python`](blueprint.python.instructions.md#error-handling).

**Do not** implement retry logic here, and do not catch `TimeoutError` / `aiohttp.ClientError` in the coordinator —
the coordinator base class already handles both.

## Exception Hierarchy (REQUIRED)

Define in `api/__init__.py`:

- `{ClassPrefix}ApiClientError` (Base)
- `{ClassPrefix}ApiClientCommunicationError` (Network, timeout, HTTP errors)
- `{ClassPrefix}ApiClientAuthenticationError` (401, 403, invalid credentials)
- `{ClassPrefix}ApiClientRateLimitError(retry_after)` (429), a subclass of the communication error, so code that
  only knows the base still catches it

**Mapping:** HTTP 401/403 → Auth, HTTP 429 → RateLimit with the `Retry-After` seconds (a client default when the
header is missing or a date), Timeout/ClientError → Communication

## Error Handling in `_async_update_data()`

Translate API exceptions into Home Assistant ones here, and only here:

| API Exception         | Raise                                       | Home Assistant Behavior     |
| --------------------- | ------------------------------------------- | --------------------------- |
| `AuthenticationError` | `ConfigEntryAuthFailed`                     | Triggers reauth flow        |
| `RateLimitError`      | `UpdateFailed(retry_after=err.retry_after)` | Next poll waits that long   |
| `CommunicationError`  | `UpdateFailed("message")`                   | Retry at the usual interval |

Catch `RateLimitError` before the communication error it subclasses; Home Assistant honours `retry_after` during
`async_config_entry_first_refresh()` too. A rate limit outside the coordinator during setup raises
`ConfigEntryNotReady(retry_after=seconds)` instead. Bound the wait before passing it on — at least a few seconds, at
most the update interval — so `Retry-After: 0` does not poll in a loop and a huge value does not stop polling.

**Import from:** `homeassistant.exceptions.ConfigEntryAuthFailed`,
`homeassistant.helpers.update_coordinator.UpdateFailed`

Use `raise ... from err`. Pass the error message to the exception constructor and **do not log** setup or update
failures manually — Home Assistant does it, and manual logging buries the real error in repetition. Normal operation
logging (debug/info) is still appropriate.

See [Integration Setup Failures](https://contributors.home-assistant.io/core/integrations/setup-failures/).

## Data Transformation (Coordinator Responsibility)

`_async_update_data()` fetches the raw API data and transforms it into a shape entities read by key: entities read
`coordinator.data["temperature"]`, not `coordinator.data["sensors"]["temp"]["value"]`.

## Update Interval

**Set in coordinator:**
`super().__init__(hass, LOGGER, config_entry=entry, name="...", update_interval=timedelta(seconds=30))`

**Always pass `config_entry=`.** Omitting it makes the coordinator fall back to a ContextVar, which for a custom
integration is set to ignore the problem — so it fails silently rather than loudly.

**Guidelines:** Environmental sensors (30-60s), Energy (10-30s), Status (60-300s), Slow data (5-15min). The floor
Home Assistant accepts is 5 seconds.

## Pull vs. Push Architecture

**Prefer push whenever the device or service offers it** — WebSocket, webhook, MQTT — and fall back to polling when
the protocol is proprietary, undocumented, or not worth the implementation effort.

- **Pull:** the coordinator handles everything via `update_interval`.
- **Push:** set up the coordinator-level listener in `async_setup_entry()` and call
  `coordinator.async_set_updated_data(new_data)` on events. Set `update_interval=None`, or keep a long one as a
  fallback for offline detection. A subscription held by an **entity** goes in `async_added_to_hass()` instead and is
  released via `self.async_on_remove(...)` — a disabled entity is never added, so subscribing at setup leaks.
- `async_set_updated_data()` on a polling coordinator also resets the timer until the next poll.

See [HA Data Update Patterns](https://contributors.home-assistant.io/core/integrations/fetching-data/)

## First Refresh

**In `async_setup_entry()` in `__init__.py`:** Call `await coordinator.async_config_entry_first_refresh()`

**Automatic handling:** If `_async_update_data()` raises `UpdateFailed`, coordinator raises `ConfigEntryNotReady`
automatically.

**When setup should not be retried at all**, use `await coordinator.async_refresh()` instead — it does not raise, so
the entry loads with entities in an unavailable state rather than going into the retry loop.

See [Integration Setup Failures](https://contributors.home-assistant.io/core/integrations/setup-failures/#during-setup)

## Always Update Parameter

`always_update=True` (default) - Always notify entities of new data

`always_update=False` - Only notify if data changed (requires `__eq__` implementation in data class)

## Caching API Data

### In memory, to fetch less often than entities update

**When:** API rate limits stricter than update needs (e.g. API allows 1 req/5min, entities need 30s updates). Hold the
payload and its timestamp on the coordinator, and return the cached copy from `_async_update_data()` while the TTL
holds. Entities then update at `update_interval` while the API is called far less often.

### Persisted, so the integration works without a connection at startup

Home Assistant restarts without internet more often than one would think — after a power cut it is regularly up before
the router is. The reflex, `async_config_entry_first_refresh()`, raises `ConfigEntryNotReady` when that first fetch
fails, and then **no entity exists at all**: exactly when the user most wants to see the last known values, the
integration shows nothing.

**First decide whether the cached payload is still true**, because this is what separates honest caching from lying
about the device:

| The payload…                                                                           | On a cold start with no network            |
| -------------------------------------------------------------------------------------- | ------------------------------------------ |
| Covers a defined period — today's electricity prices, a published forecast, a schedule | Restore it. It is complete and still valid |
| Is a point-in-time reading — a temperature, a power draw, an online/offline flag       | Do **not** restore it. It is stale         |

For the first kind:

- Persist the payload with `homeassistant.helpers.storage.Store` when a fetch succeeds, and load it in
  `async_setup_entry` before the coordinator's first refresh. **Never write files into the integration's own folder**:
  every update replaces that folder, so anything persisted there is lost. `Store` (in `.storage/`) is the only place.
- **Return the cached payload from `_async_update_data()` instead of raising `UpdateFailed`**, as long as it is still
  inside its validity window. This is the part that actually works: `CoordinatorEntity.available` is exactly
  `coordinator.last_update_success`, so raising `UpdateFailed` and merely leaving `coordinator.data` populated makes
  every entity unavailable and shows the user nothing.
- Once the window has passed, raise `UpdateFailed` as normal. Serving yesterday's prices as today's is worse than
  going unavailable.
- Log the fallback once at `info` level, so "still on cached data" is visible without spamming every poll.

The Bronze `test-before-setup` rule is satisfied either way: setup still fails loudly when there is nothing valid to
fall back on. What changes is that a valid cache counts as "we can work".

**Values that change with the clock need a scheduler, not a shorter interval.** A "current price" sensor derived from
a daily payload changes on the hour; the answer is one fetch per validity window plus
`async_track_point_in_utc_time` / `async_track_time_change` to recompute locally — not polling every minute so the
value happens to flip in time. Polling for something the integration can compute is also what makes
`appropriate-polling` look violated.

Entity-level state restoration is a different mechanism for a different problem — see `RestoreSensor` in
[`sensors.md`](../skills/ha-entity-platform/references/sensors.md). Use it for a value the entity
accumulates itself; use `Store` for the payload the coordinator hands out.

## Package Organization

**Split large modules (~200-400 lines per file):**

- `coordinator/base.py` - Core coordinator
- `coordinator/data_processing.py` - Transform helpers
- `api/client.py` - Main client
- `api/auth.py` - Auth helpers (OAuth, token refresh)
- `api/endpoints/` - Grouped endpoints (if many)

## Reference

[Home Assistant: Fetching Data](https://contributors.home-assistant.io/core/integrations/fetching-data/)
