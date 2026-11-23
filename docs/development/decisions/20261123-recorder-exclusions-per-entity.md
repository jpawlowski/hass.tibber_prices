---
id: 20261123-recorder-exclusions-per-entity
status: accepted
rule: .agents/instructions/tibber.entities.instructions.md
migrated-from:
  - docs/developer/docs/recorder-optimization.md
  - AGENTS.md@0f00a56
---

# Recorder exclusions are derived per entity from the attribute declarations

## Context

The sensors and binary sensors expose many attributes, most of them derivable, large, or stale by the next update.
Home Assistant's documented way to keep them out of the recorder is a class-level `_unrecorded_attributes`, which
applies to every entity of the class alike. Here one class serves many entities, and the same key is worth keeping on
one and not on another: `start` and `end` matter on the best and peak price period sensors and repeat the price data
on the price phase binary sensors.

## Decision

Every attribute is declared on its entity description with `attribute()` (`utils/attribute_specs.py`) and is left out
of the recorder unless declared `history=True`. `TibberPricesEntity._apply_recorder_exclusions()` in `entity.py` adds
the description's `excluded_keys()` to Home Assistant's private `_state_info["unrecorded_attributes"]` when the entity
is added. An attribute an entity exposes without a declaration is logged once and excluded from then on; in tests it
raises.

Numbers and switches, whose attributes do not vary per entity, keep the documented class-level form.

## Consequences

- A new attribute stays out of the database unless someone decides to keep it.
- This relies on a private Home Assistant attribute. `tests/test_entity_attributes.py` checks that the exclusions
  reach `_state_info`, so a change in Home Assistant fails there rather than silently recording everything.
- Moving to the class-level form would change what users' recorders store, which counts as a breaking change.
