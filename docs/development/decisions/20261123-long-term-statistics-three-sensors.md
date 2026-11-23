---
id: 20261123-long-term-statistics-three-sensors
status: accepted
rule: .agents/instructions/tibber.entities.instructions.md
migrated-from: docs/developer/docs/recorder-optimization.md
---

# Only three monetary sensors write long-term statistics

## Context

A sensor with a `state_class` writes long-term statistics. The short-term table is purged with the states, but the
hourly `statistics` table is never purged and grows for as long as the installation runs. For a `MONETARY` sensor
the only valid choices are `TOTAL` or no state class. Most of this integration's monetary sensors are forecasts,
next or previous intervals, daily extremes or rolling windows, whose history is derivable from the current price or
is not a measurement of the present at all.

## Decision

Only three sensors keep `state_class=SensorStateClass.TOTAL` in `sensor/definitions.py`:

- `current_interval_price`, the long-term price trend
- `current_interval_price_base`, which the Energy Dashboard needs
- `average_price_today`, the seasonal daily average

Every other monetary sensor has no state class. This includes the rolling present-time values (`trailing_24h_*`,
`current_hour_*`), which the shipped rule would otherwise give one.

## Consequences

- Users keep ordinary state history for all sensors; the statistics chart on the entity page exists only for the
  three.
- A new monetary sensor gets no state class unless it earns a place next to these three; adding one is a decision,
  not a default.
- Giving an existing sensor a state class later starts its statistics from that day; removing one stops new rows but
  keeps the old ones.
