---
name: "Tibber Coordinator"
description: "Time service and time travel, subscription phases, price enrichment, timers, migrations and repair issues"
applyTo: "custom_components/tibber_prices/coordinator/**, custom_components/tibber_prices/api/**, custom_components/tibber_prices/utils/subscription.py, custom_components/tibber_prices/time_travel.py, custom_components/tibber_prices/migrations.py, custom_components/tibber_prices/repairs.py"
paths:
  - "custom_components/tibber_prices/coordinator/**"
  - "custom_components/tibber_prices/api/**"
  - "custom_components/tibber_prices/utils/subscription.py"
  - "custom_components/tibber_prices/time_travel.py"
  - "custom_components/tibber_prices/migrations.py"
  - "custom_components/tibber_prices/repairs.py"
---

# Coordinator Instructions

**Procedure:** [`ha-coordinator-debug`](../skills/ha-coordinator-debug/SKILL.md) — load it when data is stale or the
setup fails. This file adds this integration's own rules to `blueprint.coordinator` and `blueprint.repairs`. The
components and the data flow: [`ARCHITECTURE.md`](../../docs/development/ARCHITECTURE.md); caches:
[`CACHING.md`](../../docs/development/CACHING.md); views: [`TIME_TRAVEL.md`](../../docs/development/TIME_TRAVEL.md).

## Traps

- **Read the time from `coordinator.time`, never `dt_util.now()` — except in the API client (`api/client.py`), query
  routing (`coordinator/interval_pool/routing.py`) and the subscription phase, each with a comment.** A time-travel
  view runs the same code on a moved clock; the three exceptions talk to Tibber, whose API lives in real time.
  Source: docs/development/decisions/20261123-time-travel-moved-clock.md
- **A time-travel date that does not exist raises `UpdateFailed` (`_check_time_travel_coverage()`); never substitute
  a nearby date.** A comparison against the wrong day is worse than none.
  Source: docs/development/decisions/20261123-time-travel-moved-clock.md
- **Hand the full coordinator data to anything that reads day offsets.** `referenceTime` travels in it; a minimal
  dict without it makes the helpers fall back to real time.
  Source: docs/development/decisions/20261123-time-travel-moved-clock.md
- **Never pass raw API prices on; every interval goes through `enrich_price_info_with_differences()`
  (`utils/price.py`).** Entities, periods and service actions all expect the enriched fields.
- **Fetch on the coordinator's own unsynchronised timer; the quarter-hour and 30-second timers only notify
  listeners.** Aligning the fetch to the clock would make every installation hit Tibber's API in the same second.
  Source: docs/development/decisions/20261123-fetch-timer-and-boundary-timers.md
- **Decide a subscription's phase from its status, never from a missing `current` price.** A contract that has not
  started has no current price, but neither has a running one during Tibber maintenance; and a contract `running`
  before its `validFrom` is already active, because Tibber sends its prices weeks ahead.
- **Compute the subscription phase against real time (`dt_util.now()`), never `coordinator.time`.** After the end
  the time service is held back at the last interval, so the shifted clock would never see the contract end.
- **Clamp an ended subscription's clock to the start of its last quarter hour
  (`get_subscription_last_interval_start()`), never to a second before midnight.** Quarter-hour rounding turns
  23:59:59 into the next day, which has no prices.
- **Bump `MINOR_VERSION` in `config_flow_handler/user_flow.py` for a config entry change, and keep each migration in
  its module.** One-time upgrades and entry versions in `migrations.py`, option format changes in
  `_migrate_config_options()`, runtime issues in `coordinator/repairs.py`, fix flows in `repairs.py`; only existing
  entries see the upgrade notice.
- **A notice that only informs is created with `is_fixable=True`, listed in `migrations.NOTICES` and answered with
  `ConfirmRepairFlow` in `repairs.py`.** An ignorable issue stays in the registry for good. Its translation has
  `title` and `fix_flow.step.confirm`, and no issue-level `description` — Home Assistant allows one of the two.
- **A new runtime issue type goes into `RUNTIME_ISSUES` in `coordinator/repairs.py`.** `TibberPricesRepairManager`
  clears those on start, so an issue ignored before a restart does not hide the same problem later.
