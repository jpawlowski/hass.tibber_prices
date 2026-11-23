---
id: 20261123-trend-volatility-calculators-build-attributes
status: accepted
rule: .agents/instructions/tibber.entities.instructions.md
migrated-from: AGENTS.md@0f00a56
---

# Trend and volatility calculators build their own attributes

## Context

The sensor platform separates value calculation (`sensor/calculators/`) from attribute building
(`sensor/attributes/`), and the attributes package never imports from the calculators. For trend and volatility the
attributes depend on intermediate results of the calculation itself — the window, the prices used, the classification
steps — that the attribute builder would otherwise have to compute a second time.

## Decision

The trend and volatility calculators compute the value and build its attribute dict in the same pass. The sensor
keeps the dict, and the attributes package only reads it back (`_add_cached_trend_attributes()`,
`_add_timing_or_volatility_attributes()` in `sensor/attributes/__init__.py`). The volatility calculator imports its
helpers from `sensor/attributes/`, a deliberate dependency from calculator to attributes.

All other calculators keep the strict split.

## Consequences

- The complex logic lives in one place, with the full context of the calculation.
- The calculator → attributes dependency is one-way only; anything in `sensor/attributes/` importing from
  `sensor/calculators/` creates a cycle.
- Trend and volatility attributes cannot be tested without running their calculator.
