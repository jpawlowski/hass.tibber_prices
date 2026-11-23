---
id: 20261123-period-defaults-and-guards
status: accepted
migrated-from: docs/developer/docs/period-calculation-theory.md
---

# Different defaults for best and peak price; flat-day, low-price and duration guards are not options

## Context

Best price periods trigger actions — a dishwasher, a car charger — so a false positive costs money. Peak price periods
warn, and a brief spike is still worth knowing about. Separately, some days defeat the regular filters: on a flat day
two distinct periods do not exist, on a day averaging a few cents a percentage min_distance means a fraction of a cent
and the relative CV gate rejects homogeneous periods, and after relaxation some days still have no period.

## Decision

- Defaults differ: best price 60 min minimum length and 15 % flex, peak price 30 min and 20 % flex (`const.py`). All
  remain user options.
- The guards are hard-coded: the flat-day target of one period (`LOW_IQR_PCT_FLAT_DAY_THRESHOLD`, with
  `LOW_CV_FLAT_DAY_THRESHOLD` as fallback), min_distance scaling below `LOW_PRICE_AVG_THRESHOLD`, the CV gate bypass
  below `LOW_PRICE_QUALITY_BYPASS_THRESHOLD`. The 0.10 major-unit thresholds fit EUR, NOK and SEK alike.
- The min-duration fallback shortens the minimum period length to `MIN_DURATION_FALLBACK_MINIMUM` and nothing else to
  the maximum: flex stays at the last relaxation level, min_distance is halved, the level filter is `any`, and the
  periods are marked `duration_fallback_active`.

## Consequences

The guards correct defects rather than express preferences, so no setting can switch them off; disabling them would
bring back zero periods on V-shaped days. The earlier fallback, which also opened flex to 50 % and dropped
min_distance, accepted almost any interval on flat days and is not to return.

## Considered options

- **Symmetric defaults**: rejected; misses short expensive spikes.
- **The guards as user options**: rejected; no user benefits from a CV gate rejecting a 2 ct period.
