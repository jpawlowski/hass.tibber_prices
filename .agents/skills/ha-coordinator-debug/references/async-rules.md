# Async rules: threads, blocking calls, late imports

Lookup tables for the three async mistakes that produce a warning or a hang rather than a clean error. The everyday
rules — `async def` for I/O, `asyncio.timeout()`, `@callback` semantics, where to create tasks — are in
[`blueprint.python.instructions.md`](../../../instructions/blueprint.python.instructions.md) and load automatically.

Enable Home Assistant's debug mode **and** asyncio's during development: most of what follows is then reported the
moment it happens instead of surfacing later as a hang or a state that quietly went wrong.

## Calling Home Assistant from a non-event-loop thread

The `async_*` APIs are not thread-safe, and Home Assistant reports and blocks a call from the wrong thread. A library
callback running on its own thread is the usual reason to need one of these. The most common cause is a missing
`@callback` on a function handed to a helper: without it, the helper runs the function in the executor.

| From a worker thread, instead of                           | call                                           |
| ---------------------------------------------------------- | ---------------------------------------------- |
| `hass.async_create_task`                                   | `hass.create_task`                             |
| `hass.bus.async_fire`                                      | `hass.bus.fire`                                |
| `hass.services.async_register` / `async_remove`            | `hass.services.register` / `remove`            |
| `hass.states.async_set`                                    | `hass.states.set`                              |
| `entity.async_write_ha_state`                              | `entity.schedule_update_ha_state`              |
| `async_dispatcher_send`                                    | `dispatcher_send`                              |
| `issue_registry.async_create_issue` / `async_delete_issue` | `issue_registry.create_issue` / `delete_issue` |

**No thread-safe twin** — schedule a `@callback` that makes the call with `hass.add_job(func, *args)`:

- the area, category, device, entity, floor and label registries (`async_get_or_create`, `async_update_device`,
  `async_update_entity`, `async_remove`, …);
- `hass.config_entries.async_update_entry` and `async_update_subentry`;
- template rendering;
- `issue_registry.async_ignore_issue`, `async_refresh_issues`, `async_keep_issue`.

`hass.add_job` is the sync entry point and is not deprecated; `hass.async_add_job` is. When the thread needs the
result, `asyncio.run_coroutine_threadsafe(coro, hass.loop).result()` — never from inside the event loop, where it
deadlocks.

## Blocking calls in the event loop

Home Assistant reports these with the integration and line. Two of them are also **stopped** — the call raises
`RuntimeError` instead of running:

| Detected call                                                                                              | Behaviour |
| ---------------------------------------------------------------------------------------------------------- | --------- |
| `time.sleep`                                                                                               | raises    |
| `http.client` `putrequest` — so `urllib`, `requests` and anything built on them                            | raises    |
| `open()`, `Path.open` / `read_text` / `read_bytes` / `write_text` / `write_bytes`                          | reported  |
| `os.listdir`, `os.scandir`, `os.walk`, `glob.glob`, `glob.iglob`                                           | reported  |
| `importlib.import_module`                                                                                  | reported  |
| `SSLContext.load_default_certs` / `load_verify_locations` / `load_cert_chain` / `set_default_verify_paths` | reported  |

**Not detected, still blocking:** `os.stat`, `os.path.exists`, `os.path.isfile` and friends, `hass.config.is_allowed_path()`
(it resolves the path on disk), and any sync SDK. Most of the "reported" rows are also skipped while tests run, so a
green suite does not prove the loop is clean — check `config/home-assistant.log` for `Detected blocking call`.

All of them belong in the executor: `await hass.async_add_executor_job(blocking_func)`, and
`await hass.async_add_executor_job(partial(f, kwarg=True))` when there are keyword arguments. For HTTP, use `aiohttp`
via `async_get_clientsession(hass)` instead.

**The `open()` trap:** Home Assistant detects the `open` call and nothing after it. Moving `open` into the executor
while leaving `.read()` in the event loop silences the warning without fixing the block — move the whole file
operation.

**A blocking `sleep` from a serial library** is usually `pyserial-asyncio`. Replace it with `serialx`, which is
import-compatible with `serial`, `serial_asyncio` and `serial_asyncio_fast` and natively async.

**SSL is not an executor problem.** Stop building the context yourself: `async_get_clientsession(hass)`,
`homeassistant.helpers.httpx_client.get_async_client(hass)`, or `homeassistant.util.ssl.get_default_context()`.

**A URL pointing back at Home Assistant** comes from `homeassistant.helpers.network.get_url(hass, ...)`, never from
`hass.config.internal_url` / `external_url` directly.

## Late imports

CPython's import machinery is not thread-safe, so the right helper depends on how the module can be reached:

| The module is…                                | Import it with                                                                                                              |
| --------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| At module level                               | A plain import — safe, it is loaded on the import executor                                                                  |
| Imported in exactly one place, conditionally  | `await hass.async_add_executor_job(_do_the_late_import)`                                                                    |
| Already in `sys.modules`                      | A plain import — Python does not load it again                                                                              |
| Possibly imported from several places at once | `await homeassistant.helpers.importlib.async_import_module(hass, "module.path")` — caches and serialises concurrent imports |
| Needed only for type annotations              | `if TYPE_CHECKING:`                                                                                                         |

Prefer not importing rarely used code at all over importing it late and badly.
