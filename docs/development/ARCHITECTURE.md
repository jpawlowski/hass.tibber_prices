# Architecture Overview

How the Tibber Prices & Planning custom integration is built: what each package does, how a price travels from
Tibber's API to an entity, and where the deeper topics are documented.

| Topic                                         | Document                            |
| --------------------------------------------- | ----------------------------------- |
| Best and peak price periods                   | [`PERIODS.md`](PERIODS.md)          |
| Storage files, in-memory caches, invalidation | [`CACHING.md`](CACHING.md)          |
| Time-travel views                             | [`TIME_TRAVEL.md`](TIME_TRAVEL.md)  |
| What the recorder keeps, long-term statistics | [`RECORDER.md`](RECORDER.md)        |
| Why a choice was made                         | [`decisions/`](decisions/README.md) |

## Directory structure

```text
custom_components/tibber_prices/
├── __init__.py              # async_setup (service actions), setup and unload of an entry, PLATFORMS
├── config_flow.py           # Discovery shim; the flow lives in config_flow_handler/
├── const.py                 # Constants, option keys, currency helpers, translation loading and cache
├── data.py                  # Runtime data types
├── device.py                # build_device_info(), the one DeviceInfo every entity of an entry uses
├── diagnostics.py           # Redacted diagnostics
├── entity.py                # TibberPricesEntity, base of every entity
├── migrations.py            # One-time upgrades: entity key renames, entry versions, confirmable notices
├── repairs.py               # Fix flows of the repair issues
├── time_travel.py           # Helpers for time-travel subentries
├── services.yaml            # Service action definitions (legacy filename)
├── api/                     # Tibber GraphQL client: client.py, queries.py, exceptions.py, helpers.py
├── coordinator/             # Data update coordinator
│   ├── core.py              # TibberPricesDataUpdateCoordinator
│   ├── price_data_manager.py# User data and the subscription phase; prices through the interval pool
│   ├── interval_pool/       # Persistent store of every fetched price interval
│   ├── data_transformation.py # Enrichment, day patterns, periods -> coordinator.data
│   ├── periods.py           # TibberPricesPeriodCalculator, hash-cached
│   ├── period_handlers/     # The period algorithm (see PERIODS.md)
│   ├── time_service.py      # TibberPricesTimeService, the one clock
│   ├── listeners.py         # Quarter-hour and 30-second refresh timers
│   ├── midnight_handler.py  # Midnight turnover, exactly once per day
│   ├── cache.py             # Persistent user data and timestamps
│   ├── repairs.py           # Runtime repair issues
│   ├── helpers.py, constants.py
├── config_flow_handler/     # user_flow.py, options_flow.py, subentry_flow.py, schemas.py, validators.py
├── sensor/                  # core.py, definitions.py, value_getters.py, calculators/, attributes/
├── binary_sensor/           # core.py, definitions.py, attributes.py
├── number/, switch/         # Runtime overrides of period settings
├── entity_utils/            # Shared attribute, icon, colour and window helpers
├── utils/                   # Pure functions: price.py, average.py, trend.py, day_outlook.py, subscription.py, …
├── service_actions/         # One module per action; charging/ holds the plan_charging solver
├── frontend/                # The bundled dashboard cards (frontend/cards/)
├── blueprints/              # Automation and script blueprints shipped with the integration
├── translations/            # Home Assistant translations (de, en, nb, nl, sv)
├── custom_translations/     # Strings outside Home Assistant's schema
└── brand/                   # Brand images
```

## Data flow

```text
Tibber GraphQL API
      │  api/client.py (TibberPricesApiClient)
      ▼
coordinator/core.py ──► price_data_manager.py ──► interval_pool/ (fetch only what is missing)
      │
      ▼
data_transformation.py: enrich every interval, detect day patterns, calculate periods
      │
      ▼
coordinator.data ──► sensor/, binary_sensor/, number/, switch/, service_actions/, cards
```

1. **Setup.** `async_setup()` registers the service actions; `async_setup_entry()` creates the API client, the
   interval pool and the coordinator, and forwards the four platforms.
2. **Fetch.** The coordinator updates every `UPDATE_INTERVAL`. User data (homes, subscription, currency) is
   refreshed daily and kept in `coordinator/cache.py`. Prices come from the interval pool, which asks the API only
   for intervals it does not hold yet.
3. **Enrich.** `TibberPricesDataTransformer` passes every quarter-hour interval through
   `enrich_price_info_with_differences()` (`utils/price.py`). It compares each price with the trailing 24-hour
   average and adds the `difference` in percent and the `rating_level`, with hysteresis and gap tolerance against
   flicker; it also smooths isolated changes of Tibber's own `level`:

   ```python
   {"startsAt": "…T14:00:00+01:00", "total": 0.2534, "level": "NORMAL"}  # from Tibber
   {"startsAt": "…T14:00:00+01:00", "total": 0.2534, "level": "NORMAL",
    "difference": 9.6, "rating_level": "NORMAL"}                         # after enrichment
   ```

   An interval without 24 hours of earlier prices gets no rating.

4. **Periods.** Day patterns are detected first, then `TibberPricesPeriodCalculator` finds the best and peak price
   periods, cached by a hash of prices and settings ([`PERIODS.md`](PERIODS.md)).
5. **Publish.** `coordinator.data` holds `priceInfo` (one flat list of enriched intervals, from the day before yesterday to tomorrow),
   `pricePeriods`, `dayPatterns`, `currency`, `home_id` and `referenceTime`, the coordinator's own "now". Entities
   read only from there.

Prices are never used raw: entities, periods and actions all rely on the enriched fields.

## Core components

### API client

`api/client.py` talks to Tibber's GraphQL API with Home Assistant's shared aiohttp session, retries transient errors
and maps failures to the exceptions in `api/exceptions.py`. `api/queries.py` defines the query types:
`PRICE_INFO` for recent prices, `PRICE_INFO_RANGE` for anything older than the window that query covers, and `USER`.
Which one a request needs is decided in `coordinator/interval_pool/routing.py` against real time, because the
boundary belongs to Tibber's API, not to the clock of a view.

### Coordinator

`TibberPricesDataUpdateCoordinator` (`coordinator/core.py`) owns the update cycle and composes the helpers beside it:
`TibberPricesPriceDataManager` (user data, subscription phase, price fetching), `TibberPricesDataTransformer`,
`TibberPricesPeriodCalculator`, `TibberPricesListenerManager`, `TibberPricesMidnightHandler` and
`TibberPricesRepairManager`. Failures follow the shared contract in [`AGENTS.md`](../../AGENTS.md).

### Interval pool

`coordinator/interval_pool/` keeps every fetched interval in its own store file per entry: `fetcher.py` checks
coverage and fetches the gaps, `index.py` looks intervals up by timestamp, `garbage_collector.py` evicts what lies
outside the protected window, `storage.py` persists the pool, and `manager.py` ties it together. Prices live only
here; [`CACHING.md`](CACHING.md) has the storage layout.

### Time service

`TibberPricesTimeService` (`coordinator/time_service.py`) is the one clock: the current interval, day boundaries,
rounding to the nearest quarter hour with a small tolerance for scheduling jitter. A time-travel view gets a shifted
instance from `_create_time_service()`, so everything that reads `coordinator.time` follows the view
([`TIME_TRAVEL.md`](TIME_TRAVEL.md)).

### Subscription phases

`utils/subscription.py` sorts a contract into pending, active or ended. A pending contract has no prices yet, so only
diagnostic entities exist; once it starts, the coordinator schedules one reload of the entry. An ended contract
fetches nothing new: the clock is clamped to its last quarter hour and intervals from `validTo` on are dropped, so
its last day stays "today".

## Timers and listeners

Three timers drive the integration:

| Timer                 | Where                      | Does                                                           |
| --------------------- | -------------------------- | -------------------------------------------------------------- |
| The coordinator's own | `DataUpdateCoordinator`    | Fetches; runs at an installation-specific offset               |
| Quarter hour          | `coordinator/listeners.py` | At :00, :15, :30 and :45, notifies the time-sensitive entities |
| Every 30 seconds      | `coordinator/listeners.py` | Notifies the timing entities (remaining minutes, progress)     |

Only the first fetches; the other two refresh entities from data already held, so a price changes at the boundary
without an API call ([decision](decisions/20261123-fetch-timer-and-boundary-timers.md)). Midnight turnover is an
atomic date check in `coordinator/midnight_handler.py`: whichever timer reaches the new day first performs it.

Leaked listeners and timers are guarded by `tests/test_resource_cleanup.py`, `tests/test_coordinator_shutdown.py`,
`tests/test_timer_scheduling.py` and `tests/test_sensor_timer_assignment.py`.

## Sensor platform

The sensor platform splits calculation from presentation:

- `sensor/definitions.py` holds the entity descriptions, grouped by how their value is calculated, with their
  declared attributes (`attributes=`, shared sets in `sensor/attribute_sets.py`).
- `sensor/value_getters.py` maps every key to the calculator method that produces its value.
- `sensor/calculators/` holds one calculator per kind — interval, rolling hour, daily statistics, 24-hour window,
  trend, volatility, timing, lifecycle, metadata, time travel — all based on `TibberPricesBaseCalculator`.
- `sensor/attributes/` builds the attribute dicts. The trend and volatility calculators are the exception: they build
  their attributes in the same pass as the value
  ([decision](decisions/20261123-trend-volatility-calculators-build-attributes.md)).
- `sensor/core.py` (`TibberPricesSensor`) is the entity: lifecycle, state restore, delegation to the calculators.

Binary sensors follow the same idea in one package: `binary_sensor/definitions.py`, `attributes.py` and `core.py`.
Attribute names, recorder exclusions and a runtime check all derive from the declarations
(`utils/attribute_specs.py`, [`RECORDER.md`](RECORDER.md)).

"Hour" means two windows: rolling-hour sensors use a centred window of five intervals that moves every quarter hour,
charts group by clock hour (`aggregate_to_hourly()` in `service_actions/formatters.py`).

## Service actions

`service_actions/` has one module per action — price lookup, cheapest and most expensive blocks and hours,
scheduling, chart data, ApexCharts and dashboard YAML, user data refresh — registered by `async_setup_services()`
from `async_setup()`. `service_actions/charging/` holds the solver behind `plan_charging`.

## Dashboard cards

`frontend/` serves the cards in `frontend/cards/` as a static directory whose URL carries the version, and loads them
into every frontend with `add_extra_js_url`. They are plain web components as native ES modules, without a build step
([decision](decisions/20261123-cards-plain-es-modules.md)); the release zip adds a gzip copy of each.

- The modules form layers, listed in the header of the entry `tibber-prices-cards.js`; the editors in `editors.js`
  load on demand.
- Every card extends `TibberPricesCardBase` (`base.js`): entities, appearance, actions, gestures. A card can show
  another card in a window (`tibber-prices-card-window`), declared by its `windowCards`; its editor then nests the
  other card's real editor one level down (`nestedCards`).
- The energy card extends the chart card through hooks and adds the Energy dashboard's solar forecast, production,
  battery and grid. Its data comes from `energy/get_prefs`, `energy/solar_forecast` and
  `recorder/statistics_during_period`, cached once per page (`solarData()`).
- All cards read the price sensor through `priceState()` (`data.js`), which applies the `price_source` option.
- `reload.js` tells a page that stayed open across an update that its cards are outdated, using the websocket command
  `tibber_prices/frontend`.

## Repairs

`coordinator/repairs.py` raises and clears the runtime issues listed in `RUNTIME_ISSUES`: tomorrow's prices missing
in the evening, persistent rate limits, an API outage after `OUTAGE_REPAIR_DELAY`, and a home gone from the account.
All are cleared when the entry starts and reported again if still true. `home_not_found` is fixable in `repairs.py`,
which also confirms the notices `migrations.py` creates after an upgrade. Time-travel views raise none, as they share
their parent's entry.

## Key design decisions

Records live in [`decisions/`](decisions/README.md); its index says which are in force.

## AI agent context

Agent-facing content is layered so each piece loads only when relevant:

| Layer                             | Loaded                      | Contains                                          |
| --------------------------------- | --------------------------- | ------------------------------------------------- |
| `AGENTS.md`                       | always                      | project identity, workflow rules, validation loop |
| `.agents/instructions/*.md`       | per touched file            | passive style rules for one file type or area     |
| `.agents/skills/*/SKILL.md`       | when a task matches         | active procedures for a specific kind of work     |
| `docs/development/`, `docs/user/` | when a human or agent reads | explanations, decisions, guides — this document   |

This integration's own rules are the `tibber.*` instruction files and the `tibber-periods` skill; the routing table
in [`AGENTS.md`](../../AGENTS.md) names each. One copy of each instruction file serves GitHub Copilot and VS Code
(`applyTo`) and Claude Code (`paths`, through the `.claude/rules/instructions` symlink); Codex and OpenCode rely on
the routing table. The skill catalogue is [`.agents/skills/README.md`](../../.agents/skills/README.md); working with
agents here: [`AI_AGENTS.md`](AI_AGENTS.md).

## Testing

Tests live in `tests/` and run with `script/test`. Many exercise a whole coordinator on sample prices; entity tests
assert on `hass.states`, and `tests/test_entity_attributes.py` runs every entity to check its declared attributes.
The procedure: [`ha-testing`](../../.agents/skills/ha-testing/SKILL.md).

## Dependencies

The runtime requirements are in `manifest.json`, the minimum Home Assistant version in `hacs.json`; development
dependencies are pinned in `requirements*.txt` and the toolchain in `mise.toml`.
