---
comments: false
---

# Caching Strategy

This document explains all caching mechanisms in the Tibber Prices integration, their purpose, invalidation logic, and lifetime.

For timer coordination and scheduling details, see [Timer Architecture](./timer-architecture.md).

## Overview

The integration uses **4 distinct caching layers** with different purposes and lifetimes:

1. **Persistent API Data Cache** (HA Storage) - Hours to days
2. **Translation Cache** (Memory) - Forever (until HA restart)
3. **Config Dictionary Cache** (Memory) - Until config changes
4. **Period Calculation Cache** (Memory) - Until price data or config changes

## 1. Persistent API Data Cache

**Location:** `coordinator/cache.py` → HA Storage (`.storage/tibber_prices.<entry_id>`)

**Purpose:** Reduce API calls to Tibber by caching user data and price data between HA restarts.

**What is cached:**
- **Price data** (`price_data`): Day before yesterday/yesterday/today/tomorrow price intervals with enriched fields (384 intervals total)
- **User data** (`user_data`): Homes, subscriptions, features from Tibber GraphQL `viewer` query
- **Timestamps**: Last update times for validation

**Lifetime:**
- **Price data**: Until midnight turnover (cleared daily at 00:00 local time)
- **User data**: 24 hours (refreshed daily)
- **Survives**: HA restarts via persistent Storage

**Invalidation triggers:**

1. **Midnight turnover** (Timer #2 in coordinator):
   ```python
   # coordinator/day_transitions.py
   def _handle_midnight_turnover() -> None:
       self._cached_price_data = None  # Force fresh fetch for new day
       self._last_price_update = None
       await self.store_cache()
   ```

2. **Cache validation on load**:
   ```python
   # coordinator/cache.py
   def is_cache_valid(cache_data: CacheData) -> bool:
       # Checks if price data is from a previous day
       if today_date < local_now.date():  # Yesterday's data
           return False
   ```

3. **Tomorrow data check** (after 13:00):
   ```python
   # coordinator/data_fetching.py
   if tomorrow_missing or tomorrow_invalid:
       return "tomorrow_check"  # Update needed
   ```

**Why this cache matters:** Reduces API load on Tibber (~192 intervals per fetch), speeds up HA restarts, enables offline operation until cache expires.

---

## 2. Translation Cache

**Location:** `const.py` → `_TRANSLATIONS_CACHE` and `_STANDARD_TRANSLATIONS_CACHE` (in-memory dicts)

**Purpose:** Avoid repeated file I/O when accessing entity descriptions, UI strings, etc.

**What is cached:**
- **Standard translations** (`/translations/*.json`): Config flow, selector options, entity names
- **Custom translations** (`/custom_translations/*.json`): Entity descriptions, usage tips, long descriptions

**Lifetime:**
- **Forever** (until HA restart)
- No invalidation during runtime

**When populated:**
- At integration setup: `async_load_translations(hass, "en")` in `__init__.py`
- Lazy loading: If translation missing, attempts file load once

**Access pattern:**
```python
# Non-blocking synchronous access from cached data
description = get_translation("binary_sensor.best_price_period.description", "en")
```

**Why this cache matters:** Entity attributes are accessed on every state update (~15 times per hour per entity). File I/O would block the event loop. Cache enables synchronous, non-blocking attribute generation.

---

## 3. Config Dictionary Cache

**Location:** `coordinator/data_transformation.py` and `coordinator/periods.py` (per-instance fields)

**Purpose:** Avoid ~30-40 `options.get()` calls on every coordinator update (every 15 minutes).

**What is cached:**

### DataTransformer Config Cache
```python
{
    "thresholds": {"low": 15, "high": 35},
    "volatility_thresholds": {"moderate": 15.0, "high": 25.0, "very_high": 40.0},
    # ... 20+ more config fields
}
```

### PeriodCalculator Config Cache
```python
{
    "best": {"flex": 0.15, "min_distance_from_avg": 5.0, "min_period_length": 60},
    "peak": {"flex": 0.15, "min_distance_from_avg": 5.0, "min_period_length": 60}
}
```

**Lifetime:**
- Until `invalidate_config_cache()` is called
- Built once on first use per coordinator update cycle

**Invalidation trigger:**
- **Options change** (user reconfigures integration):
  ```python
  # coordinator/core.py
  async def _handle_options_update(...) -> None:
      self._data_transformer.invalidate_config_cache()
      self._period_calculator.invalidate_config_cache()
      await self.async_request_refresh()
  ```

**Performance impact:**
- **Before:** ~30 dict lookups + type conversions per update = ~50μs
- **After:** 1 cache check = ~1μs
- **Savings:** ~98% (50μs → 1μs per update)

**Why this cache matters:** Config is read multiple times per update (transformation + period calculation + validation). Caching eliminates redundant lookups without changing behavior.

---

## 4. Period Calculation Cache

**Location:** `coordinator/periods.py` → `PeriodCalculator._cached_periods`

**Purpose:** Avoid expensive period calculations (~100-500ms) when price data and config haven't changed.

**What is cached:**
```python
{
    "best_price": {
        "periods": [...],      # Calculated period objects
        "intervals": [...],    # All intervals in periods
        "metadata": {...}      # Config snapshot
    },
    "best_price_relaxation": {"relaxation_active": bool, ...},
    "peak_price": {...},
    "peak_price_relaxation": {...}
}
```

**Cache key:** Hash of relevant inputs
```python
hash_data = (
    today_signature,           # (startsAt, rating_level) for each interval
    tuple(best_config.items()),  # Best price config
    tuple(peak_config.items()),  # Peak price config
    best_level_filter,         # Level filter overrides
    peak_level_filter
)
```

**Lifetime:**
- Until price data changes (today's intervals modified)
- Until config changes (flex, thresholds, filters)
- Recalculated at midnight (new today data)

**Invalidation triggers:**

1. **Config change** (explicit):
   ```python
   def invalidate_config_cache() -> None:
       self._cached_periods = None
       self._last_periods_hash = None
   ```

2. **Price data change** (automatic via hash mismatch):
   ```python
   current_hash = self._compute_periods_hash(price_info)
   if self._last_periods_hash != current_hash:
       # Cache miss - recalculate
   ```

**Cache hit rate:**
- **High:** During normal operation (coordinator updates every 15min, price data unchanged)
- **Low:** After midnight (new today data) or when tomorrow data arrives (~13:00-14:00)

**Performance impact:**
- **Period calculation:** ~100-500ms (depends on interval count, relaxation attempts)
- **Cache hit:** `<`1ms (hash comparison + dict lookup)
- **Savings:** ~70% of calculation time (most updates hit cache)

**Why this cache matters:** Period calculation is CPU-intensive (filtering, gap tolerance, relaxation). Caching avoids recalculating unchanged periods 3-4 times per hour.

---

## 5. Transformation Cache (Price Enrichment Only)

**Location:** `coordinator/data_transformation.py` → `_cached_transformed_data`

**Status:** ✅ **Clean separation** - enrichment only, no redundancy

**What is cached:**
```python
{
    "timestamp": ...,
    "homes": {...},
    "priceInfo": {...},  # Enriched price data (trailing_avg_24h, difference, rating_level)
    # NO periods - periods are exclusively managed by PeriodCalculator
}
```

**Purpose:** Avoid re-enriching price data when config unchanged between midnight checks.

**Current behavior:**
- Caches **only enriched price data** (price + statistics)
- **Does NOT cache periods** (handled by Period Calculation Cache)
- Invalidated when:
  - Config changes (thresholds affect enrichment)
  - Midnight turnover detected
  - New update cycle begins

**Architecture:**
- DataTransformer: Handles price enrichment only
- PeriodCalculator: Handles period calculation only (with hash-based cache)
- Coordinator: Assembles final data on-demand from both caches

**Memory savings:** Eliminating redundant period storage saves ~10KB per coordinator (14% reduction).

---

## Cache Invalidation Flow

### User Changes Options (Config Flow)
```
User saves options
  ↓
config_entry.add_update_listener() triggers
  ↓
coordinator._handle_options_update()
  ↓
├─> DataTransformer.invalidate_config_cache()
│   └─> _config_cache = None
│       _config_cache_valid = False
│       _cached_transformed_data = None
│
└─> PeriodCalculator.invalidate_config_cache()
    └─> _config_cache = None
        _config_cache_valid = False
        _cached_periods = None
        _last_periods_hash = None
  ↓
coordinator.async_request_refresh()
  ↓
Fresh data fetch with new config
```

### Midnight Turnover (Day Transition)
```
Timer #2 fires at 00:00
  ↓
coordinator._handle_midnight_turnover()
  ↓
├─> Clear persistent cache
│   └─> _cached_price_data = None
│       _last_price_update = None
│
└─> Clear transformation cache
    └─> _cached_transformed_data = None
        _last_transformation_config = None
  ↓
Period cache auto-invalidates (hash mismatch on new "today")
  ↓
Fresh API fetch for new day
```

### Tomorrow Data Arrives (~13:00)
```
Coordinator update cycle
  ↓
should_update_price_data() checks tomorrow
  ↓
Tomorrow data missing/invalid
  ↓
API fetch with new tomorrow data
  ↓
Price data hash changes (new intervals)
  ↓
Period cache auto-invalidates (hash mismatch)
  ↓
Periods recalculated with tomorrow included
```

---

## Cache Coordination

**All caches work together:**

```
Persistent Storage (HA restart)
       ↓
API Data Cache (price_data, user_data)
       ↓
       ├─> Enrichment (add rating_level, difference, etc.)
       │         ↓
       │   Transformation Cache (_cached_transformed_data)
       │
       └─> Period Calculation
                 ↓
           Period Cache (_cached_periods)
                 ↓
           Config Cache (avoid re-reading options)
                 ↓
           Translation Cache (entity descriptions)
```

**No cache invalidation cascades:**
- Config cache invalidation is **explicit** (on options update)
- Period cache invalidation is **automatic** (via hash mismatch)
- Transformation cache invalidation is **automatic** (on midnight/config change)
- Translation cache is **never invalidated** (read-only after load)

**Thread safety:**
- All caches are accessed from `MainThread` only (Home Assistant event loop)
- No locking needed (single-threaded execution model)

---

## Performance Characteristics

### Typical Operation (No Changes)
```
Coordinator Update (every 15 min)
├─> API fetch: SKIP (cache valid)
├─> Config dict build: ~1μs (cached)
├─> Period calculation: ~1ms (cached, hash match)
├─> Transformation: ~10ms (enrichment only, periods cached)
└─> Entity updates: ~5ms (translation cache hit)

Total: ~16ms (down from ~600ms without caching)
```

### After Midnight Turnover
```
Coordinator Update (00:00)
├─> API fetch: ~500ms (cache cleared, fetch new day)
├─> Config dict build: ~50μs (rebuild, no cache)
├─> Period calculation: ~200ms (cache miss, recalculate)
├─> Transformation: ~50ms (re-enrich, rebuild)
└─> Entity updates: ~5ms (translation cache still valid)

Total: ~755ms (expected once per day)
```

### After Config Change
```
Options Update
├─> Cache invalidation: `<`1ms
├─> Coordinator refresh: ~600ms
│   ├─> API fetch: SKIP (data unchanged)
│   ├─> Config rebuild: ~50μs
│   ├─> Period recalculation: ~200ms (new thresholds)
│   ├─> Re-enrichment: ~50ms
│   └─> Entity updates: ~5ms
└─> Total: ~600ms (expected on manual reconfiguration)
```

---

## Summary Table

| Cache Type | Lifetime | Size | Invalidation | Purpose |
|------------|----------|------|--------------|---------|
| **API Data** | Hours to 1 day | ~50KB | Midnight, validation | Reduce API calls |
| **Translations** | Forever (until HA restart) | ~5KB | Never | Avoid file I/O |
| **Config Dicts** | Until options change | `<`1KB | Explicit (options update) | Avoid dict lookups |
| **Period Calculation** | Until data/config change | ~10KB | Auto (hash mismatch) | Avoid CPU-intensive calculation |
| **Transformation** | Until midnight/config change | ~50KB | Auto (midnight/config) | Avoid re-enrichment |

**Total memory overhead:** ~116KB per coordinator instance (main + subentries)

**Benefits:**
- 97% reduction in API calls (from every 15min to once per day)
- 70% reduction in period calculation time (cache hits during normal operation)
- 98% reduction in config access time (30+ lookups → 1 cache check)
- Zero file I/O during runtime (translations cached at startup)

**Trade-offs:**
- Memory usage: ~116KB per home (negligible for modern systems)
- Code complexity: 5 cache invalidation points (well-tested, documented)
- Debugging: Must understand cache lifetime when investigating stale data issues

---

## Debugging Cache Issues

### Symptom: Stale data after config change
**Check:**
1. Is `_handle_options_update()` called? (should see "Options updated" log)
2. Are `invalidate_config_cache()` methods executed?
3. Does `async_request_refresh()` trigger?

**Fix:** Ensure `config_entry.add_update_listener()` is registered in coordinator init.

### Symptom: Period calculation not updating
**Check:**
1. Verify hash changes when data changes: `_compute_periods_hash()`
2. Check `_last_periods_hash` vs `current_hash`
3. Look for "Using cached period calculation" vs "Calculating periods" logs

**Fix:** Hash function may not include all relevant data. Review `_compute_periods_hash()` inputs.

### Symptom: Yesterday's prices shown as today
**Check:**
1. `is_cache_valid()` logic in `coordinator/cache.py`
2. Midnight turnover execution (Timer #2)
3. Cache clear confirmation in logs

**Fix:** Timer may not be firing. Check `_schedule_midnight_turnover()` registration.

### Symptom: Missing translations
**Check:**
1. `async_load_translations()` called at startup?
2. Translation files exist in `/translations/` and `/custom_translations/`?
3. Cache population: `_TRANSLATIONS_CACHE` keys

**Fix:** Re-install integration or restart HA to reload translation files.

---

## Related Documentation

- **[Timer Architecture](./timer-architecture.md)** - Timer system, scheduling, midnight coordination
- **[Architecture](./architecture.md)** - Overall system design, data flow
- **[AGENTS.md](https://github.com/jpawlowski/hass.tibber_prices/blob/v0.23.0/AGENTS.md)** - Complete reference for AI development
