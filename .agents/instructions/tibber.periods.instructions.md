---
name: "Tibber Periods"
description: "Best and peak price period calculation: flex, min_distance, relaxation, outlier smoothing, day boundaries"
applyTo: "custom_components/tibber_prices/coordinator/period_handlers/**, custom_components/tibber_prices/coordinator/periods.py"
paths:
  - "custom_components/tibber_prices/coordinator/period_handlers/**"
  - "custom_components/tibber_prices/coordinator/periods.py"
---

# Period Calculation Instructions

**Procedure:** [`tibber-periods`](../skills/tibber-periods/SKILL.md) — load it to change or debug the best/peak
period calculation. The design and every filter in detail: [`PERIODS.md`](../../docs/development/PERIODS.md).

## Traps

- **Flex is a share of `|avg − ref|`; never bring back `max(|avg − ref|, |ref|)` as its base.** With positive prices
  the reference wins for peak price and on flat best-price days, the threshold crosses the daily mean, and
  min_distance alone cuts the period.
  Source: docs/development/decisions/20261123-period-flex-min-distance-relaxation.md
- **Keep the geometric flex bonus in `TibberPricesIntervalCriteria.geometric_flex`, never add it to `flex`.** It is a
  share of the former base on purpose, so configured bonus values keep their strength.
  Source: docs/development/decisions/20261123-period-flex-min-distance-relaxation.md
- **Cut min_distance only above `FLEX_SCALING_THRESHOLD` and only where the flex threshold passes it, never below
  `MIN_DISTANCE_SCALE_FLOOR`.** Cutting it by flex on every day loosens it where nothing conflicts, and without the
  floor very flat days produce phantom periods.
  Source: docs/development/decisions/20261123-period-flex-min-distance-relaxation.md
- **Relaxation steps a fixed `RELAXATION_FLEX_INCREMENT`, capped at 50 %; do not make it a percentage of the base or
  an option.** A percentage step escalates a high base flex to the cap within a few steps.
  Source: docs/development/decisions/20261123-period-flex-min-distance-relaxation.md
- **Outlier smoothing uses `CONTEXT_STABILITY_RATIO`, never flex.** Tied to flex, changing or relaxing flex silently
  changed which spikes were smoothed.
  Source: docs/development/decisions/20261123-period-outlier-smoothing.md
- **Statistics and attributes read `_original_price`, never the smoothed `total`.** Smoothing only decides which
  intervals form a period; the prices users see must stay the real ones.
  Source: docs/development/decisions/20261123-period-outlier-smoothing.md
- **Judge each interval against its own day's reference (`ref_date = date_key`), not the period's start day.** A
  period across midnight would otherwise lend one day's threshold to the other.
  Source: docs/development/decisions/20261123-period-day-boundaries.md
- **Read time from the `time` service passed in, never `dt_util.now()`.** A time-travel view runs this code on a
  shifted clock, and real time would pick the wrong day.
- **A setting that changes the result goes into `_compute_periods_hash()` in `periods.py`.** The calculator returns
  the cached periods while the hash matches, so a missing input keeps the old periods on screen.
- **Indent period log lines with the `INDENT_L0` … `INDENT_L5` constants, one level per nesting step.** The debug
  output of a run is read as a tree — run, day, flex step, overlap, period, segment — and an unindented line breaks it.
