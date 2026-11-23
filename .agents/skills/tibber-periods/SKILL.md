---
name: tibber-periods
description: >-
  Change or debug the best price and peak price period calculation of this integration — flex, min_distance, level
  filter, relaxation, outlier smoothing, flat-day and low-price guards, midnight handling. Use when asked "why is
  there no best price period", "why is the period so short / so long", "the peak period is missing", "too many
  periods", "relaxation does not work", "change how periods are found", or when editing coordinator/period_handlers/
  or coordinator/periods.py. SYMPTOMS — load this if you are about to: change a period threshold without reading the
  filter statistics of a real day first; tune flex or min_distance to fix one day's result; add a period setting
  without adding it to the period hash; or judge a period result from the user's screenshot instead of the debug log.
---

# Change or debug the period calculation

The design, every filter and every constant: [`docs/development/PERIODS.md`](../../../docs/development/PERIODS.md).
The rules for editing the code: `.agents/instructions/tibber.periods.instructions.md`, loaded with the files. The
decisions behind the filters are the `20261123-period-*` records in `docs/development/decisions/`; read the one whose
mechanism you are about to change.

## 1. Get the real day

A period result depends on one day's prices, so reproduce with that day, not with invented numbers.

- From a running instance: `script/ha diagnostics` holds the configuration and the price data; `script/ha states`
  holds the period binary sensors and their attributes.
- Note the attributes that explain the result: `min_periods_configured`, `flat_days_detected`,
  `relaxation_incomplete`, `relaxation_active`, `relaxation_level`, `duration_fallback_active`,
  `day_volatility_percent`.

## 2. Read the debug log

Turn on `custom_components.tibber_prices.coordinator.period_handlers: debug` in `config/configuration.yaml` (the
`.details` children carry the per-day and per-interval lines), restart per `ha-coordinator-debug`, then
`script/ha logs`. Walk the run top-down; the indentation follows run → day → flex step → overlap → period.

1. **Configuration line** (`Calculating … periods: relaxation=…, target=…, flex=…`) and any base-flex warning. A
   base flex of 25 % or more with relaxation on is the usual cause of erratic results.
2. **`Filter statistics`** with `Filtered by FLEX` / `Filtered by MIN_DISTANCE`: the filter that removes most
   candidates is the one to look at. A high min_distance share on a flat day is expected.
3. **`Day D: min_distance Y% → Z%`**: expected only on flat days above 20 % flex or on low-price days. On a normal
   day it means the conflict scaling misfires.
4. **`Baseline insufficient`**, the flex steps, and `Min duration fallback`: how far relaxation had to go.
5. **`flat price profile … → min_periods relaxed to 1`**: the day counted as flat; one period is the intended result.
6. **`Smoothing price outliers`** and its summary: whether a spike was smoothed or protected.

Name the cause in terms of one filter or guard before changing anything. "Flex is too low" is not a cause when the
log shows min_distance removing the candidates.

## 3. Change it

- A one-day result is fixed by a configuration change for that user unless the log shows a mechanism doing what
  `PERIODS.md` says it must not. Changing a constant or a filter changes every user's periods.
- A change to a mechanism that a decision record describes is a new decision: supersede the record per
  `ha-planning` instead of editing the code around it.
- A new setting that affects periods: add it to `_compute_periods_hash()` and to the period configuration in
  `periods.py`.

## 4. Verify

Turn the real day into a regression test next to the existing ones, then run them:

```bash
script/test tests/test_period_calculation.py tests/test_relaxation.py tests/test_level_filtering.py
script/test -k "period or midnight or relaxation"
```

Other suites that cover this area: `tests/test_period_overlap.py`, `tests/test_period_statistics.py`,
`tests/test_periods_hash.py`, `tests/test_midnight_periods.py`, `tests/test_negative_best_price_periods.py`,
`tests/test_day_pattern_segments.py`, `tests/test_binary_sensor_period_attributes.py`. Then `script/lint` and
`script/type-check`.

If the behaviour visible to users changed, update [`docs/user/docs/period-calculation.md`](../../../docs/user/docs/period-calculation.md)
in the same change.
