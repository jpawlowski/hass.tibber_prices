---
id: 20261123-time-travel-moved-clock
status: accepted
rule:
  - .agents/instructions/tibber.coordinator.instructions.md
  - .agents/instructions/tibber.entities.instructions.md
migrated-from: docs/developer/docs/time-travel-architecture.md
---

# A time-travel view is the live coordinator with a moved clock and its own interval pool

## Context

A time-travel view reports a home as it was on an earlier date. A separate historical code path would duplicate the
fetch window, enrichment, period calculation and every sensor, and would drift from the live path.

## Decision

A view is an ordinary coordinator whose `TibberPricesTimeService` is shifted. Every instance comes from
`_create_time_service()` in `coordinator/core.py`, resolved against real time once per update cycle, so the view's
clock advances and yearly mode is re-resolved each day.

- **Each view owns its interval pool**, stored under `subentry_storage_id()`. A pool shared with the live coordinator
  would have each garbage collector evict the other's protected window.
- **The API client and query routing stay on real time.** The client is shared and spaces its requests by its clock;
  a past clock would stall it. The boundary between the two query types belongs to Tibber's API, not to the view.
- **No valid target date fails the update.** A missing 29 February or a date before `QUARTER_HOURLY_SINCE` raises
  `UpdateFailed` in `_check_time_travel_coverage()`; a nearby date is never substituted, because a comparison against
  the wrong day is worse than none.
- **Repairs are disabled for views**, which share the parent's `entry_id`.

Considered and rejected: one pool per config entry shared by the live coordinator and its views.

## Consequences

- Code that needs the current time reads `coordinator.time`; `dt_util.now()` is reserved for the API client, query
  routing and the subscription phase, each with a comment.
- Day-offset helpers depend on `referenceTime` travelling in the coordinator data.
- Every view costs its own storage file and its own fetches of historical data.
