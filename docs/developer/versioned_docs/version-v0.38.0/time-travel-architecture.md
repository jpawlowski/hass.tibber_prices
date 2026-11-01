---
sidebar_label: 🕰️ Time-Travel Architecture
---

# Time-Travel Architecture

A time-travel view is a `ConfigSubentry` of a home's config entry that reports that home as it was at a point in the past. This page covers how it is wired; the user-facing behaviour is in the [user guide](https://jpawlowski.github.io/hass.tibber_prices/user/time-travel).

## The core idea

There is no separate "historical" code path. A view is an ordinary coordinator whose clock has been moved: everything downstream — the fetch window, "today", "tomorrow", period calculation, enrichment — derives from `TimeService.now()` and therefore follows automatically.

The one rule that makes this hold: **the coordinator never constructs a `TibberPricesTimeService` directly.** Every instance comes from `_create_time_service()`, which resolves the shift against real time:

```python
# coordinator/core.py - conceptual
def _create_time_service(self):
    real_now = dt_util.now()
    return TibberPricesTimeService(reference_time=self._time_shift.resolve(real_now) or real_now)
```

A fresh instance per update cycle is what keeps the view's clock *advancing* rather than frozen at a fixed instant. Within a cycle `now()` is constant, as it is for the live coordinator.

## TimeShift

`time_travel.py` holds the shift as a frozen dataclass rather than a `timedelta`, because in yearly mode the distance to the target is not a constant — leap years and DST both move it. It is therefore resolved per cycle, not precomputed.

| Mode | `target_date()` | Notes |
|---|---|---|
| `days` | `today + timedelta(days=n)` | Constant offset |
| `yearly` | `today.replace(year=today.year + n)` | Same month/day; `None` on 29 February in a non-leap target year |

`resolve()` returning `None` means the view has no valid date today. `_check_time_travel_coverage()` turns that — and any date before `QUARTER_HOURLY_SINCE` — into an `UpdateFailed`, so entities go unavailable instead of quietly showing something else. Never substitute a nearby date: a comparison against the wrong day is worse than no comparison.

## Why each view owns its interval pool

Tempting alternative: one pool per config entry, shared by the live coordinator and all views. It does not work.

The pool's garbage collector protects the window around *its* notion of today (`interval_pool/cache.py`, `get_protected_range()`). With a shared pool the live coordinator would protect the live window and evict the historical one, and a view would do the reverse. So each coordinator gets its own pool with its own storage key (`subentry_storage_id()`), and `_propagate_time_service()` pushes the view's clock into it every cycle.

## What must not follow the shifted clock

Two things stay on real time, deliberately:

**The API client.** It is shared between the live coordinator and every view, and it uses its `TimeService` only to space out requests. A clock days in the past would make "time since last request" come out negative and stall the client for exactly that long. `_propagate_time_service()` therefore skips `self.api` for views; the live coordinator keeps it supplied.

**Query routing.** `interval_pool/routing.py` picks `PRICE_INFO` vs. `PRICE_INFO_RANGE` from real time, because the boundary is a property of Tibber's API, not of what the view is looking at.

## Day-offset filtering

`get_intervals_for_day_offsets()` is called from roughly twenty places (sensors, icons, average utilities). Threading a `TimeService` through all of them would have been invasive, so the data carries its own reference instead: the transformer writes `referenceTime` into the coordinator data, and the helper resolves offsets against it, falling back to real time when absent.

```python
reference = reference_time or coordinator_data.get("referenceTime") or dt_util.now()
```

Callers that build a minimal `{"priceInfo": ...}` dict internally (`coordinator/periods.py`) add `referenceTime` from their own `self.time`.

## Cache lifecycle

| Event | Cache | Why |
|---|---|---|
| Reload / HA restart | Kept | The whole point of the persistent store |
| Offset reconfigured | Dropped | The view points at a different stretch of history |
| Headless / realism toggled | Kept | Presentation changed, not which data is needed |
| View deleted | Dropped | Would otherwise linger until the entry is removed |
| Entry disabled | Dropped | May stay off for weeks; would be stale on return |

`_async_handle_subentry_change()` compares `_offset_signature()` to tell a reconfigure apart from a presentation change. Disable is distinguished from reload by `entry.disabled_by`, which Home Assistant sets *before* unloading.

## Tomorrow realism

Historical data is complete, so the API hands a view its "tomorrow" at any hour — which defeats rehearsing automations that wait for tomorrow's prices. `_apply_tomorrow_realism()` filters those intervals out of the raw data before transformation, until the view's own clock passes the configured arrival hour. It runs on the raw input, so enrichment and period calculation never see the withheld day.

## Scoping rules

| Thing | Live entry | View |
|---|---|---|
| Device identifier | `{entry_identifier}` | `{entry_identifier}_{subentry_id}` |
| Entity unique ID | `{entry_id}_{key}` | `{entry_id}_{subentry_id}_{key}` |
| Pool storage | `{entry_id}` | `{entry_id}_{subentry_id}` |
| Coordinator store | `{DOMAIN}.{entry_id}` | `{DOMAIN}.{entry_id}.{subentry_id}` |

Live IDs are unchanged from before views existed, so no migration was needed. Entities are registered with `async_add_entities(..., config_subentry_id=...)`, which is what files their device under the subentry — the Home Assistant 2026.8 device registry gives a device exactly one config entry and at most one subentry.

Repairs are disabled for views (`TibberPricesRepairManager(enabled=False)`): they share the parent's `entry_id` and would otherwise create and clear the same issue IDs as the live coordinator.

## Adding to a view

When adding anything that asks "what time is it?", use `coordinator.time`, never `dt_util.now()`. The exceptions are listed above and each carries a comment explaining why. When adding a sensor that reads day offsets, pass full coordinator data so `referenceTime` travels with it.

## Related Documentation

- **[Architecture](./architecture.md)** - Overall data flow and components
- **[Timer Architecture](./timer-architecture.md)** - The three timers a coordinator runs
- **[Caching Strategy](./caching-strategy.md)** - Interval pool and cache invalidation
