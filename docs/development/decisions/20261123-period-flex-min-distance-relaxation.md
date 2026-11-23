---
id: 20261123-period-flex-min-distance-relaxation
status: accepted
rule: .agents/instructions/tibber.periods.instructions.md
migrated-from:
  - docs/developer/docs/period-calculation-theory.md
  - AGENTS.md@0f00a56
---

# Flex is a share of the gap to the mean, min_distance yields only where flex passes it, relaxation steps 3 %

## Context

Flex was a share of `max(|avg − ref|, |ref|)`. With positive prices the reference itself won for peak price on
practically every day and for best price on flat days, so the threshold crossed the daily mean at default settings
and min_distance alone cut the period. To make high flex usable, min_distance was then cut linearly from 20 % flex on
every day, which loosened it where nothing conflicted. Relaxation stepped flex by a percentage of the base, so a high
base flex escalated 40 → 50 → 60 % within a few steps.

## Decision

- Flex is a share of `|avg − ref|` for best and peak price; the threshold never crosses the mean below 100 %.
- The geometric flex bonus stays a share of the former base `max(|avg − ref|, |ref|)`, passed separately as
  `TibberPricesIntervalCriteria.geometric_flex`, so configured bonus values keep their strength.
- `calculate_effective_min_distance()` cuts min_distance only above `FLEX_SCALING_THRESHOLD` (20 %) and only where the
  flex threshold passes the min_distance threshold, just far enough for both to meet, never below
  `MIN_DISTANCE_SCALE_FLOOR` (25 % of the setting). Normal days keep the full min_distance at any flex.
- Relaxation raises flex by a fixed `RELAXATION_FLEX_INCREMENT` (3 points) per step up to the 50 % cap
  (`MAX_SAFE_FLEX`, `MAX_FLEX_HARD_LIMIT`); the step is not an option. High base flex gets an INFO at 25 % and a
  WARNING at 30 %.

## Consequences

Flex sets the period edges and min_distance stays a quality floor; very flat days still produce no phantom periods.
The escalation path is predictable and the same from every base. Accepted: a 3-point step is large relative to a
very low base flex (5 % → 8 %).

## Considered options

- **The old base `max(|avg − ref|, |ref|)` for flex**: rejected for the threshold crossing the mean described above.
- **Cutting min_distance by flex on every day**: rejected; with the new base the conflict exists only on flat days.
- **Percentage or configurable relaxation step, or `max(base × 0.2, 0.03)`**: rejected; unpredictable escalation or
  another knob for an edge case.
- **Adaptive flex per day from the day's variation**: rejected; harder to predict than explicit relaxation.
