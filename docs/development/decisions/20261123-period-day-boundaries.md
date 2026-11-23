---
id: 20261123-period-day-boundaries
status: accepted
rule: .agents/instructions/tibber.periods.instructions.md
migrated-from: docs/developer/docs/period-calculation-theory.md
---

# Each interval is judged against its own day; midnight splits are bridged only with evidence on both sides

## Context

Every day has its own minimum, maximum and mean. A period can run across midnight, and the two days can differ a lot:
day-ahead prices for the whole next day are set at noon, so late intervals carry more forecast uncertainty than early
ones and prices jump at midnight without a change in demand. Judging every interval against one reference either
lends a cheap day's threshold to an expensive one or the other way round.

## Decision

- `build_periods()` judges each interval against the reference prices of the day it belongs to (`ref_date = date_key`),
  not the day the period started.
- Intervals before `CROSS_DAY_OVERNIGHT_VALIDATION_HOUR` (06:00) must also pass the previous day's flex test, for best
  and peak price, so an interval cannot qualify only because the neighbouring day has a more extreme reference.
- `extend_periods_across_midnight()` merges two periods split by midnight only when both sides have a qualifying
  period, the gap is at most `CROSS_DAY_MAX_BRIDGE_GAP_INTERVALS` (one hour) and the merged CV stays within
  `PERIOD_MAX_CV`.
- The per-period attributes `day_volatility_percent`, `day_price_min`, `day_price_max` and `day_price_span` let users
  judge how much a classification change at midnight matters.

## Consequences

A period may break at midnight when the days differ, and that is the correct result. The overnight check costs one
extra criteria evaluation for the early-morning intervals.

## Considered options

- **The period start day's reference for the whole period**: rejected; it breaks the relative evaluation.
- **Adjusting flex or min_distance at midnight**: rejected; unpredictable and hides the market's real jump.
- **Always splitting at midnight**: rejected; fragments natural overnight periods.
- **The next day's reference after midnight**: rejected; criteria change within one period.
