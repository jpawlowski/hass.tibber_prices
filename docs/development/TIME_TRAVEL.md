# Time travel

A time-travel view is a config subentry of a home's config entry that reports that home as it was at a point in the
past. This page covers how it is wired; what users see is in the user guide. Why it is built this way:
[the decision record](decisions/20261123-time-travel-moved-clock.md).

## One code path, a moved clock

There is no historical code path. A view is an ordinary coordinator whose clock has been moved: the fetch window,
"today", "tomorrow", enrichment and the period calculation all derive from the coordinator's
`TibberPricesTimeService` (`coordinator/time_service.py`) and follow it.

The coordinator never constructs a time service directly. Every instance comes from `_create_time_service()` in
`coordinator/core.py`, which resolves the shift against real time. A fresh instance per update cycle keeps the view's
clock advancing instead of frozen; within a cycle `now()` is constant, as it is for the live coordinator.
`_propagate_time_service()` then hands it to the price data manager, the data transformer and the period calculator.

## The shift

`TimeShift` in `time_travel.py` is a frozen dataclass, not a `timedelta`, because in yearly mode the
distance to the target is not constant — leap years and DST both move it. It is resolved per cycle.

| Mode     | Target date                       | Note                                                           |
| -------- | --------------------------------- | -------------------------------------------------------------- |
| `days`   | today plus a fixed number of days | constant offset                                                |
| `yearly` | same month and day, another year  | no date on 29 February when the target year is not a leap year |

`_check_time_travel_coverage()` turns a missing date, and any date before `QUARTER_HOURLY_SINCE`, into an
`UpdateFailed`, so the view's entities go unavailable instead of showing something else.

## Each view owns its interval pool

The pool's garbage collector protects the window around its own notion of today (`get_protected_range()` in
`coordinator/interval_pool/cache.py`). A pool shared by the live coordinator and its views would have each evict the
other's window. So every coordinator has its own pool under its own storage key (`subentry_storage_id()` in
`time_travel.py`), and for a view `_propagate_time_service()` also pushes the shifted clock into that pool.

## What stays on real time

- **The API client** (`api/client.py`) is shared by the live coordinator and every view and uses its time service only
  to space out requests. A clock in the past would make the time since the last request negative and stall the client
  for that long, so `_propagate_time_service()` hands the client the live clock only.
- **Query routing** (`coordinator/interval_pool/routing.py`) picks `PRICE_INFO` or `PRICE_INFO_RANGE` from real time,
  because the boundary between them is a property of Tibber's API, not of the date a view looks at.
- **The subscription phase** (`coordinator/price_data_manager.py`) is a fact about the contract today.

Each of these call sites says so in a comment.

## Day offsets travel with the data

`get_intervals_for_day_offsets()` (`coordinator/helpers.py`) is called from the sensors, binary sensors, icons,
service actions and the price and average utilities. Instead of threading a time service through all of them, the
transformer writes `referenceTime` into the coordinator data, and the helper resolves offsets against it, falling back
to real time when it is absent. A caller that builds a minimal `{"priceInfo": ...}` dict itself, as
`coordinator/periods.py` does, adds `referenceTime` from its own clock.

## Cache lifecycle

| Event                          | View's cache | Why                                              |
| ------------------------------ | ------------ | ------------------------------------------------ |
| Reload, Home Assistant restart | kept         | what the persistent store is for                 |
| Offset reconfigured            | dropped      | the view now points at different history         |
| Headless or realism toggled    | kept         | presentation changed, not which data is needed   |
| View deleted                   | dropped      | it would otherwise linger until the entry goes   |
| Entry disabled                 | dropped      | it may stay off for weeks and be stale on return |

`_async_handle_subentry_change()` in `__init__.py` compares `_offset_signature()` to tell a reconfiguration from a
presentation change. Disabling is told apart from a reload by `entry.disabled_by`, which Home Assistant sets before it
unloads.

## Tomorrow realism

Historical data is complete, so the API would hand a view its "tomorrow" at any hour, which defeats rehearsing
automations that wait for tomorrow's prices. `_apply_tomorrow_realism()` in `coordinator/core.py` removes those
intervals from the raw data until the view's clock passes the configured arrival hour. It runs before transformation,
so enrichment and the period calculation never see the withheld day.

## Scoping

| Thing             | Live entry                 | View                                     |
| ----------------- | -------------------------- | ---------------------------------------- |
| Device identifier | `{entry_identifier}`       | `{entry_identifier}_{subentry_id}`       |
| Entity unique ID  | `{entry_id}_{key}`         | `{entry_id}_{subentry_id}_{key}`         |
| Number and switch | `{entry.unique_id}_{key}`  | `{entry.unique_id}_{subentry_id}_{key}`  |
| Pool storage      | `{entry_id}`               | `{entry_id}_{subentry_id}`               |
| Coordinator store | `tibber_prices.{entry_id}` | `tibber_prices.{entry_id}.{subentry_id}` |

Live IDs are the ones from before views existed. Entities are added with `async_add_entities(...,
config_subentry_id=...)`, which files their device under the subentry.

Repairs are off for views (`TibberPricesRepairManager(..., enabled=not self.is_time_travel)`): a view shares its
parent's `entry_id` and would otherwise raise and clear the live coordinator's issues.

## Adding to a view

Anything that asks "what time is it?" reads `coordinator.time`, never `dt_util.now()`, apart from the three real-time
cases above. A new consumer of day offsets gets the full coordinator data, so `referenceTime` comes with it.
