---
name: "Tibber Entities"
description: "Attribute declarations, recorder exclusions, timestamp, sensor calculators, rolling hour, key renames"
applyTo: "custom_components/tibber_prices/sensor/**, custom_components/tibber_prices/binary_sensor/**, custom_components/tibber_prices/number/**, custom_components/tibber_prices/switch/**, custom_components/tibber_prices/entity.py, custom_components/tibber_prices/entity_utils/**, custom_components/tibber_prices/utils/attribute_specs.py"
paths:
  - "custom_components/tibber_prices/sensor/**"
  - "custom_components/tibber_prices/binary_sensor/**"
  - "custom_components/tibber_prices/number/**"
  - "custom_components/tibber_prices/switch/**"
  - "custom_components/tibber_prices/entity.py"
  - "custom_components/tibber_prices/entity_utils/**"
  - "custom_components/tibber_prices/utils/attribute_specs.py"
---

# Entity Instructions

**Procedure:** [`ha-entity-platform`](../skills/ha-entity-platform/SKILL.md) — load it before adding or changing an
entity. This file adds this integration's own rules to `blueprint.entities`; where they differ, this file wins. How
the sensor platform is built: [`ARCHITECTURE.md`](../../docs/development/ARCHITECTURE.md#sensor-platform).

## Traps

- **Declare every attribute on its entity description (`attributes=`, built with `attribute()` from
  `utils/attribute_specs.py`).** The translated names, the recorder exclusions and the runtime check all derive from
  the declaration; an undeclared attribute is logged once in production and raises in tests
  (`tests/test_entity_attributes.py`). Shared sets live in `sensor/attribute_sets.py` and
  `binary_sensor/definitions.py`.
- **Deviation: sensors and binary sensors leave an attribute out of the recorder unless it is declared
  `history=True`, per entity, not with a class-level `_unrecorded_attributes`.** One class serves many entities whose
  same key is worth keeping on one and not another; `TibberPricesEntity._apply_recorder_exclusions()` writes into Home
  Assistant's private `_state_info`, so keep `tests/test_entity_attributes.py` green. Numbers and switches keep the
  class-level form. Details: [`RECORDER.md`](../../docs/development/RECORDER.md).
  Source: docs/development/decisions/20261123-recorder-exclusions-per-entity.md
- **Deviation: only `current_interval_price`, `current_interval_price_base` and `average_price_today` carry
  `state_class=TOTAL`; every other monetary sensor gets none, rolling present-time ones included.** The hourly
  statistics table is never purged, and the other values are derivable or forecasts.
  Source: docs/development/decisions/20261123-long-term-statistics-three-sensors.md
- **Deviation: every sensor and binary sensor keeps its `timestamp` attribute, first in the dict.** Removing or
  renaming it breaks users' automations; a new time attribute follows `blueprint.entities` and is named for what it
  means.
- **Deviation: some attributes appear only when they apply** — `flat_days_detected` when above zero,
  `relaxation_incomplete` when true, and the relaxation attributes of a period only when it was relaxed. They mark
  exceptions that most days do not have; keep a new diagnostic attribute present with `None` unless it is the same
  kind of exception marker.
- **`description` is always set; the long description and `usage_tips` only with `CONF_EXTENDED_DESCRIPTIONS`.** The
  texts come from `custom_translations/` through `add_description_attributes()` in `entity_utils/attributes.py`.
- **Nothing in `sensor/attributes/` or `sensor/helpers.py` imports from `sensor/calculators/`.** The trend and
  volatility calculators build their own attribute dicts and may import from `sensor/attributes/`; the reverse
  direction makes a cycle.
  Source: docs/development/decisions/20261123-trend-volatility-calculators-build-attributes.md
- **"Hour" means two windows on purpose: rolling-hour sensors use the centred five-interval window, charts the clock
  hour. Do not unify them.** A centred window moves smoothly every quarter hour, while a chart draws each hour as a
  step from :00; the rolling sensors expose the clock hour as attributes for those who want it.
- **A new rolling-hour key goes into `ROLLING_HOUR_SENSOR_WINDOWS` in `sensor/definitions.py`.** Both the value
  (`sensor/value_getters.py`) and the window attributes (`sensor/attributes/interval.py`) read it, so a key missing
  there has one without the other.
- **Name windows with this integration's vocabulary: `trailing_*` looks back, `leading_*` ahead, `next_*` starts at
  the next interval, always with the span (`trailing_24h_max`).** Users' templates and the attribute name generator
  rely on the scheme.
- **The `connection` binary sensor stays available and sets `force_update`.** It reports the connection itself, so it
  must not go unavailable with the data, and every repeated state belongs in its history.
- **Rename an entity key through `ENTITY_KEY_RENAMES` in `migrations.py`.** `check_entity_migrations()` moves the
  unique ID and keeps the entity ID, history and customisations; a bare rename orphans the old entity.
- **Read the time from `coordinator.time` (or the `time` service passed in), never `dt_util.now()`.** A time-travel
  view runs the same entities on a moved clock.
  Source: docs/development/decisions/20261123-time-travel-moved-clock.md
