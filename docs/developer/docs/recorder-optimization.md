# Recorder History Optimization

**Status**: ✅ IMPLEMENTED
**Last Updated**: 2025-12-07

## Overview

This document describes the implementation of `_unrecorded_attributes` for Tibber Prices entities to prevent Home Assistant Recorder database bloat by excluding non-essential attributes from historical data storage.

**Reference**: [HA Developer Docs - Excluding State Attributes](https://developers.home-assistant.io/docs/core/entity/#excluding-state-attributes-from-recorder-history)

## Implementation

Sensors and binary sensors decide **per entity** what the recorder leaves out, derived from the attribute declarations of their descriptions. Numbers and switches only expose `description` and Home Assistant's own capability attributes and keep a small class-level `_unrecorded_attributes`.

### Pattern

```python
# sensor/attribute_sets.py: what an entity exposes, and what the recorder keeps
PRICE_AVERAGES = (attribute("price_mean", history=True), attribute("price_median", history=True))
PRICE_SPLIT = (attribute("energy_price"), attribute("tax"))  # no history=True: left out of the database


# entity.py: called from the entities' async_added_to_hass
def _apply_recorder_exclusions(self, *extra: str) -> None:
    info = self._state_info  # set by Home Assistant just before, read on every state write
    self._state_info = {
        **info,
        "unrecorded_attributes": info["unrecorded_attributes"] | excluded_keys(self.entity_description) | set(extra),
    }
```

An attribute is excluded unless it is declared `history=True`, so a new attribute can't fill the database by accident. Because the set belongs to the entity, one key can mean different things on different entities: the price phase binary sensors leave out `start` and `end` (the price data already tells), the best and peak price period sensors keep them. A sensor whose state is its mean or median (`state_is_average=True`) also leaves out the attribute of that average.

The documented route is a class-level `_unrecorded_attributes`, which applies to every entity of a class alike. `_state_info` is a private attribute of Home Assistant's `Entity`; `tests/test_entity_attributes.py` checks that the exclusions reach it, so a change in Home Assistant fails there.

**Key Points:**

- Applied when the entity is added (before its first state write)
- Applied automatically by Home Assistant's Recorder component

## Categories of Excluded Attributes

### 1. Descriptions/Help Text

**Attributes:** `description`, `usage_tips`

**Reason:** Static, large text strings (100-500 chars each) that:

- Never change or change very rarely
- Don't provide analytical value in history
- Consume significant database space when recorded every state change
- Can be retrieved from translation files when needed

**Impact:** ~500-1000 bytes saved per state change

### 2. Large Nested Structures

**Attributes:**

- `periods` (binary_sensor) - Array of all period summaries
- `data` (chart_data_export) - Complete price data arrays
- `trend_attributes` - Detailed trend analysis
- `current_trend_attributes` - Current trend details
- `trend_change_attributes` - Trend change analysis
- `volatility_attributes` - Detailed volatility breakdown

**Reason:** Complex nested data structures that are:

- Serialized to JSON for storage (expensive)
- Create large database rows (2-20 KB each)
- Slow down history queries
- Provide limited value in historical analysis (current state usually sufficient)

**Impact:** ~10-30 KB saved per state change for affected sensors

**Example - periods array:**

```json
{
    "periods": [
        {
            "start": "2025-12-07T06:00:00+01:00",
            "end": "2025-12-07T08:00:00+01:00",
            "duration_minutes": 120,
            "price_mean": 18.5,
            "price_median": 18.3,
            "price_min": 17.2,
            "price_max": 19.8
            // ... 10+ more attributes × 10-20 periods
        }
    ]
}
```

### 3. Frequently Changing Diagnostics

**Attributes:** `icon_color`, `cache_age`, `cache_validity`, `data_completeness`, `data_status`

**Reason:**

- Change every update cycle (every 15 minutes or more frequently)
- Don't provide long-term analytical value
- Create state changes even when core values haven't changed
- Clutter history with cosmetic changes
- Can be reconstructed from other attributes if needed

**Impact:** Prevents unnecessary state writes when only cosmetic attributes change

**Example:** `icon_color` changes from `#00ff00` to `#ffff00` but price hasn't changed → No state write needed

### 4. Static/Rarely Changing Configuration

**Attributes:** `tomorrow_expected_after`, `level_value`, `rating_value`, `level_id`, `rating_id`, `currency`, `resolution`, `yaxis_min`, `yaxis_max`

**Reason:**

- Configuration values that rarely change
- Wastes space when recorded repeatedly
- Can be derived from other attributes or from entity state

**Impact:** ~100-200 bytes saved per state change

### 5. Temporary/Time-Bound Data

**Attributes:** `timestamp`, `next_api_poll`, `next_midnight_turnover`, `last_api_fetch`, `last_cache_update`, `last_turnover`, `last_error`, `error`

**Reason:**

- `timestamp` is the rounded-quarter reference time used at the moment of the state write — it's stale as soon as the next update fires and has no analytical value in history
- `next_api_poll`, `next_midnight_turnover` etc. are only relevant at the moment of reading; they're superseded by the next update
- Similar to `entity_picture` in HA core image entities

**Note:** The entity's `native_value` (the actual price/state) is always recorded by HA as the entity state itself — independently of `_unrecorded_attributes`. So excluding `timestamp` does not create a gap in the time-series; the state row already carries the recording timestamp.

**Impact:** ~200-400 bytes saved per state change

**Example:** `next_api_poll: "2025-12-07T14:30:00"` stored at 14:15 is useless when viewing history at 15:00

### 6. Relaxation Details

**Attributes:** `relaxation_level`, `relaxation_threshold_original_percent`, `relaxation_threshold_applied_percent`

**Reason:**

- Detailed technical information not needed for historical analysis
- Only useful for debugging during active development
- Boolean `relaxation_active` is kept for high-level analysis

**Impact:** ~50-100 bytes saved per state change

### 7. Redundant/Derived Data

**Attributes:** `price_spread`, `volatility`, `diff_percent`, `rating_difference_percent`, `period_price_diff_from_daily_min`, `period_price_diff_from_daily_min_percent`, `period_count_total`, `period_count_remaining`

**Reason:**

- Can be calculated from other attributes
- Redundant information
- Doesn't add analytical value to history

**Impact:** ~100-200 bytes saved per state change

**Example:** `price_spread = price_max - price_min` (both are recorded, so spread can be calculated). `period_count_remaining = period_count_total - period_position` (both components are recorded).

**Decided when the attributes were declared and translated (#267):**

- **Repeats the state:** timing sensors' `remaining_minutes`, `next_in_minutes`, `period_duration_minutes`, `phase_duration_minutes` (the state is the same number in minutes); `price_volatility` (the level in lower case); the rank sensors' `current_price`, `next_price`, `previous_price`, `current_hour_avg_price`, `next_hour_avg_price` (the states of the price sensors); `today_volatility`, `tomorrow_volatility` (states of other sensors)
- **Statistics of the same prices or derivable from them:** volatility `price_spread`, `price_q25`, `price_q75`, `price_typical_spread(_percent)`, `price_spike_count`, `interval_count_today/_tomorrow`; rank `prices_below_count`, `reference_min/_max/_mean`; `clock_hour_price_mean/_median`; day pattern `confidence`, `day_cv_percent`, `extreme_time`, `valley_*`, `peak_*`; price phases `start`, `end`, `segment_index`, `segment_count`, `is_tomorrow`; `hours`; binary period `period_price_diff_from_daily_max(_percent)`, `day_volatility_percent`
- **Large:** `segments`, `all_segments`
- **Changing every update:** `trend_value`, `minutes_until_change`, `price_direction_duration_minutes`, `price_at_change`, `price_avg_after_change`, `first_half_interval_count`, `second_half_interval_count`
- **Trend hour variants** (`trend_<h>h_percent`, `trajectory_<h>h_percent`, `next_<h>h_avg`, `first_half_<h>h_avg`, `second_half_<h>h_avg` and their `_diff_from_current_percent`): the averages are the mean price of a window of the next hours and the percentages their difference from the current price, so they can be recalculated from the price series that the price sensors record (not exactly in the evening before tomorrow's prices are known, when the window was shorter than the full hour count). What history cannot rebuild is the trend decision itself (thresholds, volatility factor), but the categorical trend state is recorded, so the decision stays visible. Declared per hour count by `outlook_attributes()` and `trajectory_attributes()` (`sensor/attribute_sets.py`), so a new hour count can't be missed
- Chart axis bounds per source: `yaxis_min/max_energy`, `yaxis_min/max_tax`

Kept on purpose: `price_coefficient_variation_percent` (the number behind the volatility level), `price_min/max/mean/median` (values the price sensors' states don't carry), and `start`/`end` of the three `in_*_price_phase` binary sensors (`_unrecorded_attributes` is per class, and the best/peak price periods need `start`/`end`; they change only when a phase changes).

## Attributes That ARE Recorded

These attributes **remain in history** because they provide essential analytical value:

### Time-Series Core

- All price values - Core sensor states (the entity's `native_value` is always recorded separately)

### Diagnostics & Tracking

- `cache_age_minutes` - Numeric value for diagnostics tracking over time
- `updates_today` - Tracking API usage patterns

### Data Completeness

- `interval_count`, `intervals_available` - Data completeness metrics
- `yesterday_available`, `today_available`, `tomorrow_available` - Boolean status

### Period Data

- `start`, `end`, `duration_minutes` - Core period timing
- `price_mean`, `price_median`, `price_min`, `price_max` - Core price statistics
- `period_position` - Position of current period in the day's sequence
- `period_count_today`, `period_count_tomorrow` - How many periods per day (useful in automations)

### High-Level Status

- `relaxation_active` - Whether relaxation was used (boolean, useful for analyzing when periods needed relaxation)

## Expected Database Impact

### Space Savings

**Per state change:**

- Before: ~3-8 KB average
- After: ~0.5-1.5 KB average
- **Reduction: 60-85%**

**Daily per sensor:**
| Sensor Type | Updates/Day | Before | After | Savings |
|------------|-------------|--------|-------|---------|
| High-frequency (15min) | 96 | ~290 KB | ~140 KB | 50% |
| Low-frequency (6h) | 4 | ~32 KB | ~6 KB | 80% |

### Most Impactful Exclusions

1. **`periods` array** (binary_sensor) - Saves 2-5 KB per state
2. **`data`** (chart_data_export) - Saves 5-20 KB per state
3. **`trend_attributes`** - Saves 1-2 KB per state
4. **`description`/`usage_tips`** - Saves 500-1000 bytes per state
5. **`icon_color`** - Prevents unnecessary state changes

### Real-World Impact

For a typical installation with:

- 80+ sensors
- Updates every 15 minutes
- ~10 sensors updating every minute

**Before:** ~1.5 GB per month
**After:** ~400-500 MB per month
**Savings:** ~1 GB per month (~66% reduction)

## Implementation Files

- **Sensor Platform**: `custom_components/tibber_prices/sensor/core.py`
    - Class: `TibberPricesSensor`
    - 46 attributes excluded

- **Binary Sensor Platform**: `custom_components/tibber_prices/binary_sensor/core.py`
    - Class: `TibberPricesBinarySensor`
    - 29 attributes excluded

## When to Declare an Attribute with `history=True`

An attribute is excluded by default. Declare `history=True` only for what must stay in history. Leave it out of history when:

### Exclusion list (default) when:

✅ Adding new **description/help text** attributes
✅ Adding **large nested structures** (arrays, complex objects)
✅ Adding **frequently changing diagnostic info** (colors, formatted strings)
✅ Adding **temporary/time-bound data** (timestamps that become stale)
✅ Adding **redundant/derived calculations**

### Keep in History (`history=True`) When:

✅ **Core price/timing data** needed for analysis
✅ **Boolean status flags** that show state transitions
✅ **Numeric counters** useful for tracking patterns
✅ **Data that helps understand system behavior** over time

## Decision Framework

When adding a new attribute, ask:

1. **Will this be useful in history queries 1 week from now?**
    - No → Exclude
    - Yes → Keep

2. **Can this be calculated from other recorded attributes?**
    - Yes → Exclude
    - No → Keep

3. **Is this primarily for current UI display?**
    - Yes → Exclude
    - No → Keep

4. **Does this change frequently without indicating state change?**
    - Yes → Exclude
    - No → Keep

5. **Is this larger than 100 bytes and not essential for analysis?**
    - Yes → Exclude
    - No → Keep

## Testing

After changing the `history` flags:

1. **Restart Home Assistant** to apply changes
2. **Check Recorder database size** before/after
3. **Verify essential attributes** still appear in history
4. **Confirm excluded attributes** don't appear in new state writes

**SQL Query to check attribute presence:**

```sql
SELECT
    state_id,
    attributes
FROM states
WHERE entity_id = 'sensor.tibber_home_current_interval_price'
ORDER BY last_updated DESC
LIMIT 5;
```

## Maintenance Notes

- ✅ Must be a **class attribute** (instance attributes are ignored)
- ✅ Use `frozenset` for immutability
- ✅ Only affects **new** state writes (doesn't purge existing history)
- ✅ Attributes still available via `entity.attributes` in templates/automations
- ✅ Only prevents **storage** in Recorder, not runtime availability

## Long-Term Statistics Optimization (`state_class`)

**This is a second, independent mechanism** that controls writes to the HA `statistics` and `statistics_short_term` tables — distinct from `_unrecorded_attributes`, which only affects the `state_attributes` table.

### Why This Matters

- The `state_attributes` table (controlled by `_unrecorded_attributes`) is **auto-purged** after ~10 days
- The `statistics`/`statistics_short_term` tables (controlled by `state_class`) are **never auto-purged** — they grow unbounded

This makes `state_class=TOTAL` on many sensors the primary cause of long-term database bloat for users with long-running installations.

### HA Constraint: MONETARY Device Class

For sensors with `device_class=SensorDeviceClass.MONETARY`, only two `state_class` values are valid:

| `state_class` | Statistics written        | Frontend effect                                   |
| ------------- | ------------------------- | ------------------------------------------------- |
| `TOTAL`       | ✅ Yes — unbounded growth | Statistics line-chart on entity detail page       |
| `None`        | ❌ No                     | States timeline only (History panel, "Show More") |
| `MEASUREMENT` | ❌ Blocked by hassfest    | —                                                 |

`MEASUREMENT` causes a hassfest validation error for MONETARY sensors, leaving only `TOTAL` or `None`.

### Implementation Decision

Only 3 of 26 MONETARY sensors keep `state_class=TOTAL` — those where long-term history is genuinely useful:

| Sensor                        | Reason                               |
| ----------------------------- | ------------------------------------ |
| `current_interval_price`      | Long-term price trend (weeks/months) |
| `current_interval_price_base` | Required for Energy Dashboard        |
| `average_price_today`         | Seasonal daily average tracking      |

All other 23 MONETARY sensors use `state_class=None`:

- Forecast/future sensors (`next_avg_*h`)
- Daily snapshots (`lowest/highest_price_today/tomorrow`)
- Rolling windows (`trailing/leading_24h_*`)
- Next/previous interval sensors

**Effect of `state_class=None`:**

- ✅ Short-term state history (States timeline, ~10 days) still works normally
- ✅ Templates, automations, and attributes are unaffected
- ❌ Statistics line-chart removed from entity detail page for these sensors
- ❌ No writes to `statistics`/`statistics_short_term` tables

### Expected Impact

Going from 26 → 3 sensors writing to the statistics tables:

- **~88% reduction** in statistics table writes
- Prevents the primary cause of long-term database bloat
- Existing statistics data is retained (only new writes stop)

### Relationship to `_unrecorded_attributes`

These are two independent mechanisms targeting different tables:

| Mechanism                | Table affected                        | Purged?     | Controls                                        |
| ------------------------ | ------------------------------------- | ----------- | ----------------------------------------------- |
| `_unrecorded_attributes` | `state_attributes`                    | ✅ ~10 days | Which attributes are stored per state write     |
| `state_class=None`       | `statistics`, `statistics_short_term` | ❌ Never    | Whether long-term statistics are written at all |

Both optimizations work together. `_unrecorded_attributes` reduces the size of each state write; `state_class=None` eliminates an entire category of unbounded writes.

### Implementation File

- **`custom_components/tibber_prices/sensor/definitions.py`** — `state_class` set per-sensor in `SensorEntityDescription`

## References

- [HA Developer Docs - Excluding State Attributes](https://developers.home-assistant.io/docs/core/entity/#excluding-state-attributes-from-recorder-history)
- Implementation PR: [Link when merged]
- Related Issue: [Link if applicable]
