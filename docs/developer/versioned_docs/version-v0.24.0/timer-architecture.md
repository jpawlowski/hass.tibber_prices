---
comments: false
---

# Timer Architecture

This document explains the timer/scheduler system in the Tibber Prices integration - what runs when, why, and how they coordinate.

## Overview

The integration uses **three independent timer mechanisms** for different purposes:

| Timer | Type | Interval | Purpose | Trigger Method |
|-------|------|----------|---------|----------------|
| **Timer #1** | HA built-in | 15 minutes | API data updates | `DataUpdateCoordinator` |
| **Timer #2** | Custom | :00, :15, :30, :45 | Entity state refresh | `async_track_utc_time_change()` |
| **Timer #3** | Custom | Every minute | Countdown/progress | `async_track_utc_time_change()` |

**Key principle:** Timer #1 (HA) controls **data fetching**, Timer #2 controls **entity updates**, Timer #3 controls **timing displays**.

---

## Timer #1: DataUpdateCoordinator (HA Built-in)

**File:** `coordinator/core.py` → `TibberPricesDataUpdateCoordinator`

**Type:** Home Assistant's built-in `DataUpdateCoordinator` with `UPDATE_INTERVAL = 15 minutes`

**What it is:**
- HA provides this timer system automatically when you inherit from `DataUpdateCoordinator`
- Triggers `_async_update_data()` method every 15 minutes
- **Not** synchronized to clock boundaries (each installation has different start time)

**Purpose:** Check if fresh API data is needed, fetch if necessary

**What it does:**

```python
async def _async_update_data(self) -> TibberPricesData:
    # Step 1: Check midnight turnover FIRST (prevents race with Timer #2)
    if self._check_midnight_turnover_needed(dt_util.now()):
        await self._perform_midnight_data_rotation(dt_util.now())
        # Notify ALL entities after midnight turnover
        return self.data  # Early return

    # Step 2: Check if we need tomorrow data (after 13:00)
    if self._should_update_price_data() == "tomorrow_check":
        await self._fetch_and_update_data()  # Fetch from API
        return self.data

    # Step 3: Use cached data (fast path - most common)
    return self.data
```

**Load Distribution:**
- Each HA installation starts Timer #1 at different times → natural distribution
- Tomorrow data check adds 0-30s random delay → prevents "thundering herd" on Tibber API
- Result: API load spread over ~30 minutes instead of all at once

**Midnight Coordination:**
- Atomic check: `_check_midnight_turnover_needed(now)` compares dates only (no side effects)
- If midnight turnover needed → performs it and returns early
- Timer #2 will see turnover already done and skip gracefully

**Why we use HA's timer:**
- Automatic restart after HA restart
- Built-in retry logic for temporary failures
- Standard HA integration pattern
- Handles backpressure (won't queue up if previous update still running)

---

## Timer #2: Quarter-Hour Refresh (Custom)

**File:** `coordinator/listeners.py` → `ListenerManager.schedule_quarter_hour_refresh()`

**Type:** Custom timer using `async_track_utc_time_change(minute=[0, 15, 30, 45], second=0)`

**Purpose:** Update time-sensitive entity states at interval boundaries **without waiting for API poll**

**Problem it solves:**
- Timer #1 runs every 15 minutes but NOT synchronized to clock (:03, :18, :33, :48)
- Current price changes at :00, :15, :30, :45 → entities would show stale data for up to 15 minutes
- Example: 14:00 new price, but Timer #1 ran at 13:58 → next update at 14:13 → users see old price until 14:13

**What it does:**

```python
async def _handle_quarter_hour_refresh(self, now: datetime) -> None:
    # Step 1: Check midnight turnover (coordinates with Timer #1)
    if self._check_midnight_turnover_needed(now):
        # Timer #1 might have already done this → atomic check handles it
        await self._perform_midnight_data_rotation(now)
        # Notify ALL entities after midnight turnover
        return

    # Step 2: Normal quarter-hour refresh (most common path)
    # Only notify time-sensitive entities (current_interval_price, etc.)
    self._listener_manager.async_update_time_sensitive_listeners()
```

**Smart Boundary Tolerance:**
- Uses `round_to_nearest_quarter_hour()` with ±2 second tolerance
- HA may schedule timer at 14:59:58 → rounds to 15:00:00 (shows new interval)
- HA restart at 14:59:30 → stays at 14:45:00 (shows current interval)
- See [Architecture](./architecture.md#3-quarter-hour-precision) for details

**Absolute Time Scheduling:**
- `async_track_utc_time_change()` plans for **all future boundaries** (15:00, 15:15, 15:30, ...)
- NOT relative delays ("in 15 minutes")
- If triggered at 14:59:58 → next trigger is 15:15:00, NOT 15:00:00 (prevents double updates)

**Which entities listen:**
- All sensors that depend on "current interval" (e.g., `current_interval_price`, `next_interval_price`)
- Binary sensors that check "is now in period?" (e.g., `best_price_period_active`)
- ~50-60 entities out of 120+ total

**Why custom timer:**
- HA's built-in coordinator doesn't support exact boundary timing
- We need **absolute time** triggers, not periodic intervals
- Allows fast entity updates without expensive data transformation

---

## Timer #3: Minute Refresh (Custom)

**File:** `coordinator/listeners.py` → `ListenerManager.schedule_minute_refresh()`

**Type:** Custom timer using `async_track_utc_time_change(second=0)` (every minute)

**Purpose:** Update countdown and progress sensors for smooth UX

**What it does:**

```python
async def _handle_minute_refresh(self, now: datetime) -> None:
    # Only notify minute-update entities
    # No data fetching, no transformation, no midnight handling
    self._listener_manager.async_update_minute_listeners()
```

**Which entities listen:**
- `best_price_remaining_minutes` - Countdown timer
- `peak_price_remaining_minutes` - Countdown timer
- `best_price_progress` - Progress bar (0-100%)
- `peak_price_progress` - Progress bar (0-100%)
- ~10 entities total

**Why custom timer:**
- Users want smooth countdowns (not jumping 15 minutes at a time)
- Progress bars need minute-by-minute updates
- Very lightweight (no data processing, just state recalculation)

**Why NOT every second:**
- Minute precision sufficient for countdown UX
- Reduces CPU load (60× fewer updates than seconds)
- Home Assistant best practice (avoid sub-minute updates)

---

## Listener Pattern (Python/HA Terminology)

**Your question:** "Sind Timer für dich eigentlich 'Listener'?"

**Answer:** In Home Assistant terminology:

- **Timer** = The mechanism that triggers at specific times (`async_track_utc_time_change`)
- **Listener** = A callback function that gets called when timer triggers
- **Observer Pattern** = Entities register callbacks, coordinator notifies them

**How it works:**

```python
# Entity registers a listener callback
class TibberPricesSensor(CoordinatorEntity):
    async def async_added_to_hass(self):
        # Register this entity's update callback
        self._remove_listener = self.coordinator.async_add_time_sensitive_listener(
            self._handle_coordinator_update
        )

# Coordinator maintains list of listeners
class ListenerManager:
    def __init__(self):
        self._time_sensitive_listeners = []  # List of callbacks

    def async_add_time_sensitive_listener(self, callback):
        self._time_sensitive_listeners.append(callback)

    def async_update_time_sensitive_listeners(self):
        # Timer triggered → notify all listeners
        for callback in self._time_sensitive_listeners:
            callback()  # Entity updates itself
```

**Why this pattern:**
- Decouples timer logic from entity logic
- One timer can notify many entities efficiently
- Entities can unregister when removed (cleanup)
- Standard HA pattern for coordinator-based integrations

---

## Timer Coordination Scenarios

### Scenario 1: Normal Operation (No Midnight)

```
14:00:00 → Timer #2 triggers
         → Update time-sensitive entities (current price changed)
         → 60 entities updated (~5ms)

14:03:12 → Timer #1 triggers (HA's 15-min cycle)
         → Check if tomorrow data needed (no, still cached)
         → Return cached data (fast path, ~2ms)

14:15:00 → Timer #2 triggers
         → Update time-sensitive entities
         → 60 entities updated (~5ms)

14:16:00 → Timer #3 triggers
         → Update countdown/progress entities
         → 10 entities updated (~1ms)
```

**Key observation:** Timer #1 and Timer #2 run **independently**, no conflicts.

### Scenario 2: Midnight Turnover

```
23:45:12 → Timer #1 triggers
         → Check midnight: current_date=2025-11-17, last_check=2025-11-17
         → No turnover needed
         → Return cached data

00:00:00 → Timer #2 triggers FIRST (synchronized to midnight)
         → Check midnight: current_date=2025-11-18, last_check=2025-11-17
         → Turnover needed! Perform rotation, save cache
         → _last_midnight_check = 2025-11-18
         → Notify ALL entities

00:03:12 → Timer #1 triggers (its regular cycle)
         → Check midnight: current_date=2025-11-18, last_check=2025-11-18
         → Turnover already done → skip
         → Return existing data (fast path)
```

**Key observation:** Atomic date comparison prevents double-turnover, whoever runs first wins.

### Scenario 3: Tomorrow Data Check (After 13:00)

```
13:00:00 → Timer #2 triggers
         → Normal quarter-hour refresh
         → Update time-sensitive entities

13:03:12 → Timer #1 triggers
         → Check tomorrow data: missing or invalid
         → Fetch from Tibber API (~300ms)
         → Transform data (~200ms)
         → Calculate periods (~100ms)
         → Notify ALL entities (new data available)

13:15:00 → Timer #2 triggers
         → Normal quarter-hour refresh (uses newly fetched data)
         → Update time-sensitive entities
```

**Key observation:** Timer #1 does expensive work (API + transform), Timer #2 does cheap work (entity notify).

---

## Why We Keep HA's Timer (Timer #1)

**Your question:** "warum wir den HA timer trotzdem weiter benutzen, da er ja für uns unkontrollierte aktualisierte änderungen triggert"

**Answer:** You're correct that it's not synchronized, but that's actually **intentional**:

### Reason 1: Load Distribution on Tibber API

If all installations used synchronized timers:
- ❌ Everyone fetches at 13:00:00 → Tibber API overload
- ❌ Everyone fetches at 14:00:00 → Tibber API overload
- ❌ "Thundering herd" problem

With HA's unsynchronized timer:
- ✅ Installation A: 13:03:12, 13:18:12, 13:33:12, ...
- ✅ Installation B: 13:07:45, 13:22:45, 13:37:45, ...
- ✅ Installation C: 13:11:28, 13:26:28, 13:41:28, ...
- ✅ Natural distribution over ~30 minutes
- ✅ Plus: Random 0-30s delay on tomorrow checks

**Result:** API load spread evenly, no spikes.

### Reason 2: What Timer #1 Actually Checks

Timer #1 does NOT blindly update. It checks:

```python
def _should_update_price_data(self) -> str:
    # Check 1: Do we have tomorrow data? (only relevant after ~13:00)
    if tomorrow_missing or tomorrow_invalid:
        return "tomorrow_check"  # Fetch needed

    # Check 2: Is cache still valid?
    if cache_valid:
        return "cached"  # No fetch needed (most common!)

    # Check 3: Has enough time passed?
    if time_since_last_update < threshold:
        return "cached"  # Too soon, skip fetch

    return "update_needed"  # Rare case
```

**Most Timer #1 cycles:** Fast path (~2ms), no API call, just returns cached data.

**API fetch only when:**
- Tomorrow data missing/invalid (after 13:00)
- Cache expired (midnight turnover)
- Explicit user refresh

### Reason 3: HA Integration Best Practices

- ✅ Standard HA pattern: `DataUpdateCoordinator` is recommended by HA docs
- ✅ Automatic retry logic for temporary API failures
- ✅ Backpressure handling (won't queue updates if previous still running)
- ✅ Developer tools integration (users can manually trigger refresh)
- ✅ Diagnostics integration (shows last update time, success/failure)

### What We DO Synchronize

- ✅ **Timer #2:** Entity state updates at exact boundaries (user-visible)
- ✅ **Timer #3:** Countdown/progress at exact minutes (user-visible)
- ❌ **Timer #1:** API fetch timing (invisible to user, distribution wanted)

---

## Performance Characteristics

### Timer #1 (DataUpdateCoordinator)
- **Triggers:** Every 15 minutes (unsynchronized)
- **Fast path:** ~2ms (cache check, return existing data)
- **Slow path:** ~600ms (API fetch + transform + calculate)
- **Frequency:** ~96 times/day
- **API calls:** ~1-2 times/day (cached otherwise)

### Timer #2 (Quarter-Hour Refresh)
- **Triggers:** 96 times/day (exact boundaries)
- **Processing:** ~5ms (notify 60 entities)
- **No API calls:** Uses cached/transformed data
- **No transformation:** Just entity state updates

### Timer #3 (Minute Refresh)
- **Triggers:** 1440 times/day (every minute)
- **Processing:** ~1ms (notify 10 entities)
- **No API calls:** No data processing at all
- **Lightweight:** Just countdown math

**Total CPU budget:** ~15 seconds/day for all timers combined.

---

## Debugging Timer Issues

### Check Timer #1 (HA Coordinator)

```python
# Enable debug logging
_LOGGER.setLevel(logging.DEBUG)

# Watch for these log messages:
"Fetching data from API (reason: tomorrow_check)"  # API call
"Using cached data (no update needed)"             # Fast path
"Midnight turnover detected (Timer #1)"            # Turnover
```

### Check Timer #2 (Quarter-Hour)

```python
# Watch coordinator logs:
"Updated 60 time-sensitive entities at quarter-hour boundary"  # Normal
"Midnight turnover detected (Timer #2)"                        # Turnover
```

### Check Timer #3 (Minute)

```python
# Watch coordinator logs:
"Updated 10 minute-update entities"  # Every minute
```

### Common Issues

1. **Timer #2 not triggering:**
   - Check: `schedule_quarter_hour_refresh()` called in `__init__`?
   - Check: `_quarter_hour_timer_cancel` properly stored?

2. **Double updates at midnight:**
   - Should NOT happen (atomic coordination)
   - Check: Both timers use same date comparison logic?

3. **API overload:**
   - Check: Random delay working? (0-30s jitter on tomorrow check)
   - Check: Cache validation logic correct?

---

## Related Documentation

- **[Architecture](./architecture.md)** - Overall system design, data flow
- **[Caching Strategy](./caching-strategy.md)** - Cache lifetimes, invalidation, midnight turnover
- **[AGENTS.md](https://github.com/jpawlowski/hass.tibber_prices/blob/v0.24.0/AGENTS.md)** - Complete reference for AI development

---

## Summary

**Three independent timers:**
1. **Timer #1** (HA built-in, 15 min, unsynchronized) → Data fetching (when needed)
2. **Timer #2** (Custom, :00/:15/:30/:45) → Entity state updates (always)
3. **Timer #3** (Custom, every minute) → Countdown/progress (always)

**Key insights:**
- Timer #1 unsynchronized = good (load distribution on API)
- Timer #2 synchronized = good (user sees correct data immediately)
- Timer #3 synchronized = good (smooth countdown UX)
- All three coordinate gracefully (atomic midnight checks, no conflicts)

**"Listener" terminology:**
- Timer = mechanism that triggers
- Listener = callback that gets called
- Observer pattern = entities register, coordinator notifies
