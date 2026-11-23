# Best and peak price periods

How the integration finds the best price and peak price periods of a day, and how to read what it did. The
user-facing explanation is [`docs/user/docs/period-calculation.md`](../user/docs/period-calculation.md) and
[`period-relaxation.md`](../user/docs/period-relaxation.md); the rules agents follow while editing this code are in
[`tibber.periods`](../../.agents/instructions/tibber.periods.instructions.md), and the debugging procedure is the
[`tibber-periods`](../../.agents/skills/tibber-periods/SKILL.md) skill.

## Where the code is

| File (under `custom_components/tibber_prices/coordinator/`) | Does                                                                                 |
| ----------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| `periods.py`                                                | `TibberPricesPeriodCalculator`: reads the options, caches by hash, calls the package |
| `period_handlers/relaxation.py`                             | `calculate_periods_with_relaxation()`: per-day loops, flex steps, fallback           |
| `period_handlers/core.py`                                   | `calculate_periods()`: one pass with one configuration, `MAX_SAFE_FLEX`              |
| `period_handlers/level_filtering.py`                        | `check_interval_criteria()`: the flex and min_distance tests, low-price scaling      |
| `period_handlers/period_building.py`                        | `build_periods()`: walks the intervals, cross-day validation and bridging            |
| `period_handlers/outlier_filtering.py`                      | spike smoothing before the periods are built                                         |
| `period_handlers/period_overlap.py`                         | merging relaxed periods into the existing ones, with the quality gate                |
| `period_handlers/period_statistics.py`                      | the per-period attributes, including the day volatility values                       |
| `period_handlers/day_pattern.py`                            | classifies the day's shape and finds the knee points of a valley or peak             |
| `period_handlers/shape_extension.py`                        | optional extension of a period into adjacent very cheap / very expensive intervals   |
| `period_handlers/types.py`                                  | `TibberPricesPeriodConfig`, `TibberPricesIntervalCriteria`, shared constants         |

`periods.py` caches the result and recalculates only when `_compute_periods_hash()` changes: today's and tomorrow's
interval signatures, both period configurations and both level filters. A new setting that affects the result has to
reach that hash, or the old periods stay on screen.

## The three filters

An interval is a candidate only when all three pass. Shown for best price; peak price mirrors each one with the
daily maximum and `1 + min_distance/100`.

1. **Flex**: `price ≤ daily_min + |daily_avg − daily_min| × flex`. Flex is a share of the gap between the day's
   extreme and its mean, so the threshold never crosses the mean below 100 % and flex, not min_distance, sets the
   period edges. The geometric flex bonus (`*_geometric_flex`, only inside a valley or peak zone from
   `day_pattern.py`) is passed separately as `TibberPricesIntervalCriteria.geometric_flex` and stays a share of the
   former base `max(|avg − ref|, |ref|)`.
2. **Min_distance**: `price ≤ daily_avg × (1 − min_distance/100)`, so a period is notably cheaper than the day, not
   marginally.
3. **Level**: the interval's price level is within the configured maximum (best) or minimum (peak) level, with the
   gap tolerance in `level_filtering.py`.

Each interval is judged against **its own day's** reference prices (`ref_date = date_key` in `build_periods()`),
also inside a period that started the day before. Why: [day boundaries](decisions/20261123-period-day-boundaries.md).

## When flex and min_distance conflict

The flex threshold passes the min_distance threshold when

```text
flex > 1 − (daily_avg × min_distance/100) / (daily_avg − daily_min)
```

On a normal day (min 10, avg 15, min_distance 5 %) that needs flex above 85 %, beyond the 50 % cap. On a flat day
(min 30, avg 33) it is 45 %. There min_distance would block what flex allows, so `calculate_effective_min_distance()`
cuts it, but only when flex plus the geometric bonus is above `FLEX_SCALING_THRESHOLD` (20 %, reached during
relaxation or in a geometric zone), only where the flex threshold actually passes it, and only as far as both meet.
It never goes below `MIN_DISTANCE_SCALE_FLOOR` (25 % of the setting) and never raises a value the low-price scaling
already cut further.

| Day (min_distance 5 %, flex 50 %) | Min / avg | Flex threshold | Distance threshold | Effective min_distance   |
| --------------------------------- | --------- | -------------- | ------------------ | ------------------------ |
| Normal                            | 10 / 20   | 15 ct          | 19 ct              | 5 % (no conflict)        |
| Flat                              | 30 / 33   | 31.5 ct        | 31.35 ct           | 4.55 % (meet at 31.5 ct) |
| Very flat                         | 30 / 30.2 | 30.1 ct        | 28.69 ct           | 1.25 % (floor)           |

Why this shape and not a cut by flex on every day: [flex, min_distance and relaxation](decisions/20261123-period-flex-min-distance-relaxation.md).

## Limits and warnings

- `MAX_SAFE_FLEX` (`core.py`) caps `abs(flex)` at 50 %: halfway between the extreme and the mean. Beyond that the
  result is either the whole day or nothing.
- With relaxation on, `relaxation.py` logs INFO from `FLEX_WARNING_THRESHOLD_RELAXATION` (25 %) and WARNING from
  `FLEX_HIGH_THRESHOLD_RELAXATION` (30 %) base flex, independent of the day's shape: a high base leaves few steps to
  the cap.

## Relaxation

When a day has fewer periods than the configured minimum, `calculate_periods_with_relaxation()` escalates **that day
only**:

1. Baseline with the user's configuration.
2. Per step, flex rises by `RELAXATION_FLEX_INCREMENT` (3 percentage points), capped at `MAX_FLEX_HARD_LIMIT` (50 %).
   With the defaults that is 15 % → 18 % → … → 48 % for best price over `DEFAULT_RELAXATION_ATTEMPTS_BEST` steps.
3. At each flex level the original level filter is tried first, then `level_filter="any"`.
4. The day stops as soon as it reaches its target.

New periods are merged into the existing ones by `resolve_period_overlaps()` (`period_overlap.py`), which refuses a
merge whose combined coefficient of variation would exceed `PERIOD_MAX_CV` (25 %).

### Flat-day target

`_compute_day_effective_min()` lowers a day's target to one period when its prices are flat: IQR % at most
`LOW_IQR_PCT_FLAT_DAY_THRESHOLD` (15 %), or, where IQR % is undefined (median near zero or negative), CV at most
`LOW_CV_FLAT_DAY_THRESHOLD` (10 %). It applies to best and peak price, and only with relaxation on and a minimum above
one. The count is exposed as `flat_days_detected`.

### Min-duration fallback

If relaxation ends with a day that has **no** period at all, `_try_min_duration_fallback()` shortens the minimum
period length in `MIN_DURATION_FALLBACK_STEP` steps down to `MIN_DURATION_FALLBACK_MINIMUM` (30 min). Everything else
stays strict: flex at the final relaxation level, min_distance halved (not zeroed), level `any`. Its periods carry
`duration_fallback_active`, `duration_fallback_min_length` and a `relaxation_level` of `duration_fallback=<n>min`.

## Low-price days

Two guards for days that are cheap in absolute terms, such as a solar surplus day at a few cents. Both thresholds are
in the currency's major unit (0.10 = 10 ct / øre / öre). Why they are not options:
[defaults and guards](decisions/20261123-period-defaults-and-guards.md).

- **Min_distance scaling** (`level_filtering.py`): below `LOW_PRICE_AVG_THRESHOLD` the min_distance shrinks linearly
  with the daily average, to zero at an average of zero. Otherwise 5 % of 2 ct would require a tenth of a cent.
- **Quality gate bypass** (`_check_period_quality()` in `relaxation.py`, `_check_merge_quality_gate()` in
  `period_overlap.py`): a period whose mean is below `LOW_PRICE_QUALITY_BYPASS_THRESHOLD` skips the CV check. Prices of
  0.5–4 ct show a large relative spread but differ by fractions of a cent.

## Day boundaries

- **Overnight validation**: an interval before `CROSS_DAY_OVERNIGHT_VALIDATION_HOUR` (06:00) must also pass the
  previous day's flex test. Otherwise it could qualify only because the neighbouring day has a more extreme reference.
  Applies to best and peak.
- **Bridging**: `extend_periods_across_midnight()` merges two periods split by midnight when both sides have a
  qualifying period, the gap is at most `CROSS_DAY_MAX_BRIDGE_GAP_INTERVALS` (one hour) and the merged CV stays within
  `PERIOD_MAX_CV`. A period that ended at 21:30 is never bridged; it ended because the price changed.
- A period may still break at midnight when the two days differ a lot. That is correct: day-ahead prices are set at
  noon for the whole next day, so a jump at midnight is real. The period attributes `day_volatility_percent`,
  `day_price_min`, `day_price_max` and `day_price_span` let an automation judge how much a classification change
  matters.

## Outlier smoothing

Before the periods are built, `outlier_filtering.py` smooths isolated single-interval spikes so they do not cut a
period in two:

- a local linear regression over at least `MIN_CONTEXT_SIZE` intervals on each side predicts the expected price;
- the confidence band is adaptive between `CONFIDENCE_LEVEL_MIN` and `CONFIDENCE_LEVEL_MAX` standard deviations,
  driven by the day's CV (`DAILY_CV_LOW`, `DAILY_CV_HIGH`): wider on flat days, narrower on volatile ones;
- `SYMMETRY_THRESHOLD` keeps asymmetric moves (a real shift, a morning ramp) unsmoothed;
- `RELATIVE_VOLATILITY_THRESHOLD` rejects zigzag clusters;
- a spike is only smoothed when the averages before and after differ by at most `CONTEXT_STABILITY_RATIO` (15 %) of
  the price before, independent of flex;
- prices within `EXTREMES_PROTECTION_TOLERANCE` of the daily minimum or maximum are never smoothed.

The original price stays in `_original_price`; every statistic and attribute uses it. The smoothed count per period is
`period_interval_smoothed_count`. Why regression and a fixed ratio:
[outlier smoothing](decisions/20261123-period-outlier-smoothing.md).

## Debugging

Loggers, each with a `.details` child for the per-interval and per-day lines:

```yaml
logger:
  logs:
    custom_components.tibber_prices.coordinator.period_handlers: debug
```

| Log line (logger)                                                                                          | Means                                                                                          |
| ---------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `Calculating … periods: relaxation=…, target=…/day, flex=…` (relaxation)                                   | the configuration a run starts from                                                            |
| `Base flex …% is high / too high for relaxation mode` (relaxation)                                         | base flex at or above 25 % / 30 %                                                              |
| `Smoothing price outliers: … stable context ≤15%, daily CV: …` (outlier_filtering)                         | the CV per day that sets the confidence band                                                   |
| `Filter statistics: N intervals checked` and `Filtered by FLEX / MIN_DISTANCE …` (period_building.details) | which filter removed how many candidates                                                       |
| `Day D: min_distance Y% → Z% (…)` (period_building.details)                                                | min_distance cut for that day; expected only on flat days above 20 % flex or on low-price days |
| `After build_periods: N raw periods found` (core)                                                          | candidates before the minimum length is applied                                                |
| `Baseline insufficient (…) - starting relaxation` (relaxation)                                             | at least one day missed its target                                                             |
| `Day D: flat price profile (…) → min_periods relaxed to 1` (relaxation.details)                            | the flat-day target applied                                                                    |
| `Min duration fallback: …` (relaxation)                                                                    | relaxation left a day with no period                                                           |

Log lines in this package are indented with the `INDENT_L0` … `INDENT_L5` constants from `types.py` (each module may
define its own subset), so one run reads as a tree: run, day, flex step, overlap resolution, period, segment.

Attributes on the period binary sensors that explain a result:

| Attribute                                      | Present                 | Meaning                                        |
| ---------------------------------------------- | ----------------------- | ---------------------------------------------- |
| `min_periods_configured`                       | always                  | the configured target per day                  |
| `flat_days_detected`                           | only when above zero    | days whose target was lowered to one           |
| `relaxation_incomplete`                        | only when true          | relaxation ran out before a day met its target |
| `relaxation_active`, `relaxation_level`        | only on relaxed periods | which flex and filter combination found it     |
| `day_volatility_percent` and the `day_price_*` | always on a period      | the day's spread, for midnight changes         |

### Two day shapes worth recognising

| Day                      | Prices                     | What happens                                                                                               |
| ------------------------ | -------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Flat, target two periods | 28–32 ct                   | flat-day target lowers it to one; `flat_days_detected: 1`, no `relaxation_incomplete`                      |
| Solar surplus, V-shape   | 0.5–4.2 ct, average 2.1 ct | min_distance scaled to about a fifth; the CV gate is bypassed, so a 0.5–2 ct period with a high CV is kept |
