---
id: 20261123-fetch-timer-and-boundary-timers
status: accepted
rule: .agents/instructions/tibber.coordinator.instructions.md
migrated-from: docs/developer/docs/timer-architecture.md
---

# Fetch on the coordinator's own timer, refresh entities on exact boundaries

## Context

Prices change at every quarter hour, so entity states must change at :00, :15, :30 and :45. Home Assistant's
`DataUpdateCoordinator` runs every `UPDATE_INTERVAL` (`coordinator/constants.py`) from whenever the integration was
set up, not on the clock. Moving the fetch onto the boundaries would make the values exact, but would also make every
installation ask Tibber's API at the same second.

## Decision

Keep two kinds of timer apart:

- **Fetching** stays on the coordinator's unsynchronised timer. Each installation runs at its own offset, which spreads
  the load on Tibber's API, and the coordinator keeps Home Assistant's retry, backpressure and manual refresh. Most
  cycles find the interval pool complete and fetch nothing.
- **Entity refresh** runs on `async_track_utc_time_change` in `coordinator/listeners.py`: at the quarter-hour
  boundaries for the time-sensitive listeners, and every 30 seconds for the countdown and progress listeners. These
  only notify entities; they never fetch or transform.

Midnight turnover is an atomic date check (`coordinator/midnight_handler.py`), so whichever timer reaches the new day
first performs it and the other skips it.

The old documentation also described a random delay of up to 30 seconds before the tomorrow check. No such delay
exists in the code; the spreading comes from the installation-specific offset alone.

## Consequences

- A new value that depends on the time of day registers as a time-sensitive or timing listener; it does not shorten
  the fetch interval.
- The fetch timer's offset is not something to "fix" by aligning it to the clock.
- Two paths can perform the midnight turnover, so it must stay idempotent.
