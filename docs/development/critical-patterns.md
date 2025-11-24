# Critical Behavior Patterns - Testing Guide

**Purpose:** This documentation lists essential behavior patterns that must be tested to ensure production-quality code and prevent resource leaks.

**Last Updated:** 2025-11-22
**Test Coverage:** 41 tests implemented (100% of critical patterns)

## 🎯 Why Are These Tests Critical?

Home Assistant integrations run **continuously** in the background. Resource leaks lead to:
- **Memory Leaks**: RAM usage grows over days/weeks until HA becomes unstable
- **Callback Leaks**: Listeners remain registered after entity removal → CPU load increases
- **Timer Leaks**: Timers continue running after unload → unnecessary background tasks
- **File Handle Leaks**: Storage files remain open → system resources exhausted

## ✅ Test Categories

### 1. Resource Cleanup (Memory Leak Prevention)

**File:** `tests/test_resource_cleanup.py`

#### 1.1 Listener Cleanup ✅

**What is tested:**
- Time-sensitive listeners are correctly removed (`async_add_time_sensitive_listener()`)
- Minute-update listeners are correctly removed (`async_add_minute_update_listener()`)
- Lifecycle callbacks are correctly unregistered (`register_lifecycle_callback()`)
- Sensor cleanup removes ALL registered listeners
- Binary sensor cleanup removes ALL registered listeners

**Why critical:**
- Each registered listener holds references to Entity + Coordinator
- Without cleanup: Entities are not freed by GC → Memory Leak
- With 80+ sensors × 3 listener types = 240+ callbacks that must be cleanly removed

**Code Locations:**
- `coordinator/listeners.py` → `async_add_time_sensitive_listener()`, `async_add_minute_update_listener()`
- `coordinator/core.py` → `register_lifecycle_callback()`
- `sensor/core.py` → `async_will_remove_from_hass()`
- `binary_sensor/core.py` → `async_will_remove_from_hass()`

#### 1.2 Timer Cleanup ✅

**What is tested:**
- Quarter-hour timer is cancelled and reference cleared
- Minute timer is cancelled and reference cleared
- Both timers are cancelled together
- Cleanup works even when timers are `None`

**Why critical:**
- Uncancelled timers continue running after integration unload
- HA's `async_track_utc_time_change()` creates persistent callbacks
- Without cleanup: Timers keep firing → CPU load + unnecessary coordinator updates

**Code Locations:**
- `coordinator/listeners.py` → `cancel_timers()`
- `coordinator/core.py` → `async_shutdown()`

#### 1.3 Config Entry Cleanup ✅

**What is tested:**
- Options update listener is registered via `async_on_unload()`
- Cleanup function is correctly passed to `async_on_unload()`

**Why critical:**
- `entry.add_update_listener()` registers permanent callback
- Without `async_on_unload()`: Listener remains active after reload → duplicate updates
- Pattern: `entry.async_on_unload(entry.add_update_listener(handler))`

**Code Locations:**
- `coordinator/core.py` → `__init__()` (listener registration)
- `__init__.py` → `async_unload_entry()`

### 2. Cache Invalidation ✅

**File:** `tests/test_resource_cleanup.py`

#### 2.1 Config Cache Invalidation

**What is tested:**
- DataTransformer config cache is invalidated on options change
- PeriodCalculator config + period cache is invalidated
- Trend calculator cache is cleared on coordinator update

**Why critical:**
- Stale config → Sensors use old user settings
- Stale period cache → Incorrect best/peak price periods
- Stale trend cache → Outdated trend analysis

**Code Locations:**
- `coordinator/data_transformation.py` → `invalidate_config_cache()`
- `coordinator/periods.py` → `invalidate_config_cache()`
- `sensor/calculators/trend.py` → `clear_trend_cache()`

### 3. Storage Cleanup ✅

**File:** `tests/test_resource_cleanup.py` + `tests/test_coordinator_shutdown.py`

#### 3.1 Persistent Storage Removal

**What is tested:**
- Storage file is deleted on config entry removal
- Cache is saved on shutdown (no data loss)

**Why critical:**
- Without storage removal: Old files remain after uninstallation
- Without cache save on shutdown: Data loss on HA restart
- Storage path: `.storage/tibber_prices.{entry_id}`

**Code Locations:**
- `__init__.py` → `async_remove_entry()`
- `coordinator/core.py` → `async_shutdown()`

### 4. Timer Scheduling ✅

**File:** `tests/test_timer_scheduling.py`

**What is tested:**
- Quarter-hour timer is registered with correct parameters
- Minute timer is registered with correct parameters
- Timers can be re-scheduled (override old timer)
- Midnight turnover detection works correctly

**Why critical:**
- Wrong timer parameters → Entities update at wrong times
- Without timer override on re-schedule → Multiple parallel timers → Performance problem

### 5. Sensor-to-Timer Assignment ✅

**File:** `tests/test_sensor_timer_assignment.py`

**What is tested:**
- All `TIME_SENSITIVE_ENTITY_KEYS` are valid entity keys
- All `MINUTE_UPDATE_ENTITY_KEYS` are valid entity keys
- Both lists are disjoint (no overlap)
- Sensor and binary sensor platforms are checked

**Why critical:**
- Wrong timer assignment → Sensors update at wrong times
- Overlap → Duplicate updates → Performance problem

## 🚨 Additional Analysis (Nice-to-Have Patterns)

These patterns were analyzed and classified as **not critical**:

### 6. Async Task Management

**Current Status:** Fire-and-forget pattern for short tasks
- `sensor/core.py` → Chart data refresh (short-lived, max 1-2 seconds)
- `coordinator/core.py` → Cache storage (short-lived, max 100ms)

**Why no tests needed:**
- No long-running tasks (all < 2 seconds)
- HA's event loop handles short tasks automatically
- Task exceptions are already logged

**If needed:** `_chart_refresh_task` tracking + cancel in `async_will_remove_from_hass()`

### 7. API Session Cleanup

**Current Status:** ✅ Correctly implemented
- `async_get_clientsession(hass)` is used (shared session)
- No new sessions are created
- HA manages session lifecycle automatically

**Code:** `api/client.py` + `__init__.py`

### 8. Translation Cache Memory

**Current Status:** ✅ Bounded cache
- Max ~5-10 languages × 5KB = 50KB total
- Module-level cache without re-loading
- Practically no memory issue

**Code:** `const.py` → `_TRANSLATIONS_CACHE`, `_STANDARD_TRANSLATIONS_CACHE`

### 9. Coordinator Data Structure Integrity

**Current Status:** Manually tested via `./scripts/develop`
- Midnight turnover works correctly (observed over several days)
- Missing keys are handled via `.get()` with defaults
- 80+ sensors access `coordinator.data` without errors

**Structure:**
```python
coordinator.data = {
    "user_data": {...},
    "priceInfo": [...],  # Flat list of all enriched intervals
    "currency": "EUR"  # Top-level for easy access
}
```

### 10. Service Response Memory

**Current Status:** HA's response lifecycle
- HA automatically frees service responses after return
- ApexCharts ~20KB response is one-time per call
- No response accumulation in integration code

**Code:** `services/apexcharts.py`

## 📊 Test Coverage Status

### ✅ Implemented Tests (41 total)

| Category | Status | Tests | File | Coverage |
|----------|--------|-------|------|----------|
| Listener Cleanup | ✅ | 5 | `test_resource_cleanup.py` | 100% |
| Timer Cleanup | ✅ | 4 | `test_resource_cleanup.py` | 100% |
| Config Entry Cleanup | ✅ | 1 | `test_resource_cleanup.py` | 100% |
| Cache Invalidation | ✅ | 3 | `test_resource_cleanup.py` | 100% |
| Storage Cleanup | ✅ | 1 | `test_resource_cleanup.py` | 100% |
| Storage Persistence | ✅ | 2 | `test_coordinator_shutdown.py` | 100% |
| Timer Scheduling | ✅ | 8 | `test_timer_scheduling.py` | 100% |
| Sensor-Timer Assignment | ✅ | 17 | `test_sensor_timer_assignment.py` | 100% |
| **TOTAL** | **✅** | **41** | | **100% (critical)** |

### 📋 Analyzed but Not Implemented (Nice-to-Have)

| Category | Status | Rationale |
|----------|--------|-----------|
| Async Task Management | 📋 | Fire-and-forget pattern used (no long-running tasks) |
| API Session Cleanup | ✅ | Pattern correct (`async_get_clientsession` used) |
| Translation Cache | ✅ | Cache size bounded (~50KB max for 10 languages) |
| Data Structure Integrity | 📋 | Would add test time without finding real issues |
| Service Response Memory | 📋 | HA automatically frees service responses |

**Legend:**
- ✅ = Fully tested or pattern verified correct
- 📋 = Analyzed, low priority for testing (no known issues)

## 🎯 Development Status

### ✅ All Critical Patterns Tested

All essential memory leak prevention patterns are covered by 41 tests:
- ✅ Listeners are correctly removed (no callback leaks)
- ✅ Timers are cancelled (no background task leaks)
- ✅ Config entry cleanup works (no dangling listeners)
- ✅ Caches are invalidated (no stale data issues)
- ✅ Storage is saved and cleaned up (no data loss)
- ✅ Timer scheduling works correctly (no update issues)
- ✅ Sensor-timer assignment is correct (no wrong updates)

### 📋 Nice-to-Have Tests (Optional)

If problems arise in the future, these tests can be added:

1. **Async Task Management** - Pattern analyzed (fire-and-forget for short tasks)
2. **Data Structure Integrity** - Midnight rotation manually tested
3. **Service Response Memory** - HA's response lifecycle automatic

**Conclusion:** The integration has production-quality test coverage for all critical resource leak patterns.

## 🔍 How to Run Tests

```bash
# Run all resource cleanup tests (14 tests)
./scripts/test tests/test_resource_cleanup.py -v

# Run all critical pattern tests (41 tests)
./scripts/test tests/test_resource_cleanup.py tests/test_coordinator_shutdown.py \
              tests/test_timer_scheduling.py tests/test_sensor_timer_assignment.py -v

# Run all tests with coverage
./scripts/test --cov=custom_components.tibber_prices --cov-report=html

# Type checking and linting
./scripts/check

# Manual memory leak test
# 1. Start HA: ./scripts/develop
# 2. Monitor RAM: watch -n 1 'ps aux | grep home-assistant'
# 3. Reload integration multiple times (HA UI: Settings → Devices → Tibber Prices → Reload)
# 4. RAM should stabilize (not grow continuously)
```

## 📚 References

- **Home Assistant Cleanup Patterns**: https://developers.home-assistant.io/docs/integration_setup_failures/#cleanup
- **Async Best Practices**: https://developers.home-assistant.io/docs/asyncio_101/
- **Memory Profiling**: https://docs.python.org/3/library/tracemalloc.html
