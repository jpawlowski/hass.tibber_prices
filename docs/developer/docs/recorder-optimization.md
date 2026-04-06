# Recorder History Optimization

**Status**: ✅ IMPLEMENTED
**Last Updated**: 2025-12-07

## Overview

This document describes the implementation of `_unrecorded_attributes` for Tibber Prices entities to prevent Home Assistant Recorder database bloat by excluding non-essential attributes from historical data storage.

**Reference**: [HA Developer Docs - Excluding State Attributes](https://developers.home-assistant.io/docs/core/entity/#excluding-state-attributes-from-recorder-history)

## Implementation

Both `TibberPricesSensor` and `TibberPricesBinarySensor` implement `_unrecorded_attributes` as a class-level `frozenset` to exclude attributes that don't provide value in historical data analysis.

### Pattern

```python
class TibberPricesSensor(TibberPricesEntity, SensorEntity):
    """tibber_prices Sensor class."""

    _unrecorded_attributes = frozenset(
        {
            "description",
            "usage_tips",
            # ... more attributes
        }
    )
```

**Key Points:**
- Must be a **class attribute** (not instance attribute)
- Use `frozenset` for immutability and performance
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
      "price_max": 19.8,
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

**Attributes:** `relaxation_level`, `relaxation_threshold_original_%`, `relaxation_threshold_applied_%`

**Reason:**
- Detailed technical information not needed for historical analysis
- Only useful for debugging during active development
- Boolean `relaxation_active` is kept for high-level analysis

**Impact:** ~50-100 bytes saved per state change

### 7. Redundant/Derived Data

**Attributes:** `price_spread`, `volatility`, `diff_%`, `rating_difference_%`, `period_price_diff_from_daily_min`, `period_price_diff_from_daily_min_%`, `periods_total`, `periods_remaining`

**Reason:**
- Can be calculated from other attributes
- Redundant information
- Doesn't add analytical value to history

**Impact:** ~100-200 bytes saved per state change

**Example:** `price_spread = price_max - price_min` (both are recorded, so spread can be calculated)

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

## When to Update _unrecorded_attributes

### Add to Exclusion List When:

✅ Adding new **description/help text** attributes
✅ Adding **large nested structures** (arrays, complex objects)
✅ Adding **frequently changing diagnostic info** (colors, formatted strings)
✅ Adding **temporary/time-bound data** (timestamps that become stale)
✅ Adding **redundant/derived calculations**

### Keep in History When:

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

After modifying `_unrecorded_attributes`:

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

| `state_class` | Statistics written | Frontend effect |
|---|---|---|
| `TOTAL` | ✅ Yes — unbounded growth | Statistics line-chart on entity detail page |
| `None` | ❌ No | States timeline only (History panel, "Show More") |
| `MEASUREMENT` | ❌ Blocked by hassfest | — |

`MEASUREMENT` causes a hassfest validation error for MONETARY sensors, leaving only `TOTAL` or `None`.

### Implementation Decision

Only 3 of 26 MONETARY sensors keep `state_class=TOTAL` — those where long-term history is genuinely useful:

| Sensor | Reason |
|---|---|
| `current_interval_price` | Long-term price trend (weeks/months) |
| `current_interval_price_base` | Required for Energy Dashboard |
| `average_price_today` | Seasonal daily average tracking |

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

| Mechanism | Table affected | Purged? | Controls |
|---|---|---|---|
| `_unrecorded_attributes` | `state_attributes` | ✅ ~10 days | Which attributes are stored per state write |
| `state_class=None` | `statistics`, `statistics_short_term` | ❌ Never | Whether long-term statistics are written at all |

Both optimizations work together. `_unrecorded_attributes` reduces the size of each state write; `state_class=None` eliminates an entire category of unbounded writes.

### Implementation File

- **`custom_components/tibber_prices/sensor/definitions.py`** — `state_class` set per-sensor in `SensorEntityDescription`

## References

- [HA Developer Docs - Excluding State Attributes](https://developers.home-assistant.io/docs/core/entity/#excluding-state-attributes-from-recorder-history)
- Implementation PR: [Link when merged]
- Related Issue: [Link if applicable]
