---
id: 20261123-period-outlier-smoothing
status: accepted
rule: .agents/instructions/tibber.periods.instructions.md
migrated-from:
  - docs/developer/docs/period-calculation-theory.md
  - AGENTS.md@0f00a56
---

# Outlier smoothing by local regression with a symmetry check and a fixed stable-context ratio

## Context

A single-interval spike cuts a period in two. Smoothing it must not flatten a real price shift such as the morning
ramp, must not touch the prices users see, and must not change when the user changes flex. Until the flex base
changed, the stable-context test used the user's flex (capped at 25 %), so changing flex or relaxing it silently
changed spike detection.

## Decision

`outlier_filtering.py` predicts each interval from a local linear regression over its neighbours, flags it outside an
adaptive confidence band (`CONFIDENCE_LEVEL_MIN` … `CONFIDENCE_LEVEL_MAX`, from the day's CV), keeps asymmetric moves
(`SYMMETRY_THRESHOLD`), rejects zigzag clusters (`RELATIVE_VOLATILITY_THRESHOLD`) and smooths only when the context is
stable within the fixed `CONTEXT_STABILITY_RATIO` (15 % of the price before). The original price stays in
`_original_price`, and every statistic uses it.

## Consequences

Trends survive, detection does not depend on flex, and the smoothing affects only which intervals form a period.

## Considered options

- **Median filter**: rejected; removes legitimate peaks.
- **Moving average**: rejected; cannot follow a trend.
- **IQR**: rejected; assumes a distribution the prices do not have.
- **RANSAC**: rejected; more than one-dimensional data needs.
- **Flex-based stable context**: rejected, see Context.
