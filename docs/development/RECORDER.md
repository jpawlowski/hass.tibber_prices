# Recorder

What this integration's entities leave in the recorder database, and why. Two independent mechanisms decide it:
which attributes are stored with each state row, and which sensors write long-term statistics.

| Mechanism                 | Table                                 | Purged by the recorder                        |
| ------------------------- | ------------------------------------- | --------------------------------------------- |
| unrecorded attributes     | `state_attributes`                    | yes, with the states after `purge_keep_days`  |
| `state_class` on a sensor | `statistics_short_term`, `statistics` | short-term yes; the hourly `statistics` never |

## Attributes: excluded unless declared for history

Every sensor and binary sensor description lists its attributes with `attribute()` from `utils/attribute_specs.py`;
the declarations live in `sensor/attribute_sets.py` and `binary_sensor/definitions.py`. An attribute is left out of
the recorder unless it is declared `history=True`, so a new attribute cannot fill the database by accident.

The set is applied per entity, not per class: `TibberPricesEntity._apply_recorder_exclusions()` in `entity.py` adds
`excluded_keys(description)` to Home Assistant's `_state_info["unrecorded_attributes"]`, called from the entities'
`async_added_to_hass` in `sensor/core.py` and `binary_sensor/core.py`. That lets one key mean different things on
different entities of the same class — the price phase binary sensors leave out `start` and `end`, the best and peak
price period sensors keep them. A sensor whose state is its own mean or median (`state_is_average=True`) also leaves
out the attribute of that average. Why the private attribute and not the documented class-level
`_unrecorded_attributes`: [the decision record](decisions/20261123-recorder-exclusions-per-entity.md).

An attribute an entity exposes without declaring it is reported by `report_undeclared()` and excluded from then on
(`_screen_attributes()` in `entity.py`); in tests it raises. The chart export's service result (`open_attributes`)
is excluded the same way, without a report.

Numbers and switches expose only `description` and Home Assistant's own capability attributes, and keep a class-level
`_unrecorded_attributes` (`number/core.py`, `switch/core.py`).

Guarded by `tests/test_recorder_exclusions.py` (what the declarations exclude) and `tests/test_entity_attributes.py`
(that the exclusions reach `_state_info`, so a change in Home Assistant fails there).

## What is left out, by kind

- **Help text** — `description`, `usage_tips`: static, and available from the translations.
- **Large nested structures** — the `periods` list, the chart export's `data`, `segments`, `all_segments`.
- **Values that change every update without the state changing** — `icon_color`, `trend_value`,
  `minutes_until_change`, `price_direction_duration_minutes`, `price_at_change`, `price_avg_after_change`, the
  half-window interval counts.
- **Configuration and identifiers** — `level_value`, `rating_value`, `level_id`, `rating_id`, `currency`,
  `resolution`, the chart axis bounds.
- **Moments that are stale by the next update** — `timestamp`, `next_api_poll`, `last_successful_update`,
  `last_turnover`, `last_error`, `error`. The state row carries its own time, so dropping `timestamp` leaves no gap
  in the series.
- **Relaxation detail** — `relaxation_level` and the original and applied threshold percentages; the boolean
  `relaxation_active` stays.
- **What repeats the state or another sensor's state** — the timing sensors' minute counts, `price_volatility`, the
  rank sensors' `current_price`, `next_price`, `previous_price`, and `today_volatility`, `tomorrow_volatility`.
- **Statistics of the same prices, or derivable from them** — `price_spread`, the quartiles, typical spread, spike
  and interval counts, the rank references, the clock-hour mean and median, the day-pattern details, the price
  phases' segment fields, `hours`, the period differences from the daily extremes, `day_volatility_percent`.
- **Trend hour variants** — `trend_<h>h_percent`, `trajectory_<h>h_percent`, `next_<h>h_avg`, `first_half_<h>h_avg`,
  `second_half_<h>h_avg` and their differences from the current price. They are averages over the next hours and can
  be recalculated from the recorded price series; the trend decision itself is the recorded state. They are declared
  per hour count by `outlook_attributes()` and `trajectory_attributes()` in `sensor/attribute_sets.py`, so a new hour
  count cannot be missed.

## What is kept on purpose

- The period timing and price statistics: `start`, `end`, `duration_minutes`, `price_mean`, `price_median`,
  `price_min`, `price_max`, `period_position`, `period_count_today`, `period_count_tomorrow`.
- `price_coefficient_variation_percent`, the number behind the volatility level.
- `relaxation_active`, to see when periods needed relaxation.
- Data status: `intervals_available`, `tomorrow_available`, `updates_today`, `using_cached_data`,
  `subscription_phase`.
- Levels and directions: `level`, `rating_level`, `direction`, `previous_direction`, `from_direction`,
  `period_interval_count`.

Before declaring `history=True`, ask whether the value is useful in a history query a week later, whether it can be
recalculated from what is recorded, and whether it only serves the current UI.

## Long-term statistics

For a `MONETARY` sensor only `TOTAL` and no state class are valid. Three sensors keep `state_class=TOTAL` in
`sensor/definitions.py`: `current_interval_price`, `current_interval_price_base` (the Energy Dashboard needs it) and
`average_price_today`. Every other monetary sensor — forecasts, next and previous intervals, daily extremes, rolling
windows — has none, because the hourly statistics table is never purged. Their state history still works; only the
statistics chart on the entity page is gone. Why: [the decision record](decisions/20261123-long-term-statistics-three-sensors.md).

## Checking a state row

Changes apply to new state writes only; existing rows stay. After a restart, the newest rows show what is stored:

```sql
SELECT s.last_updated_ts, a.shared_attrs
FROM states s
JOIN states_meta m ON s.metadata_id = m.metadata_id
LEFT JOIN state_attributes a ON s.attributes_id = a.attributes_id
WHERE m.entity_id = '<entity_id>'
ORDER BY s.last_updated_ts DESC
LIMIT 5;
```
