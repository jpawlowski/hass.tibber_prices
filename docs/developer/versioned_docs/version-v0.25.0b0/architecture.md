---
comments: false
---

# Architecture

This document provides a visual overview of the integration's architecture, focusing on end-to-end data flow and caching layers.

For detailed implementation patterns, see [`AGENTS.md`](https://github.com/jpawlowski/hass.tibber_prices/blob/v0.25.0b0/AGENTS.md).

---

## End-to-End Data Flow

```mermaid
flowchart TB
    %% External Systems
    TIBBER[("🌐 Tibber GraphQL API<br/>api.tibber.com")]
    HA[("🏠 Home Assistant<br/>Core")]

    %% Entry Point
    SETUP["__init__.py<br/>async_setup_entry()"]

    %% Core Components
    API["api.py<br/>TibberPricesApiClient<br/><br/>GraphQL queries"]
    COORD["coordinator.py<br/>TibberPricesDataUpdateCoordinator<br/><br/>Orchestrates updates every 15min"]

    %% Caching Layers
    CACHE_API["💾 API Cache<br/>coordinator/cache.py<br/><br/>HA Storage (persistent)<br/>User: 24h | Prices: until midnight"]
    CACHE_TRANS["💾 Transformation Cache<br/>coordinator/data_transformation.py<br/><br/>Memory (enriched prices)<br/>Until config change or midnight"]
    CACHE_PERIOD["💾 Period Cache<br/>coordinator/periods.py<br/><br/>Memory (calculated periods)<br/>Hash-based invalidation"]
    CACHE_CONFIG["💾 Config Cache<br/>coordinator/*<br/><br/>Memory (parsed options)<br/>Until config change"]
    CACHE_TRANS_TEXT["💾 Translation Cache<br/>const.py<br/><br/>Memory (UI strings)<br/>Until HA restart"]

    %% Processing Components
    TRANSFORM["coordinator/data_transformation.py<br/>DataTransformer<br/><br/>Enrich prices with statistics"]
    PERIODS["coordinator/periods.py<br/>PeriodCalculator<br/><br/>Calculate best/peak periods"]
    ENRICH["price_utils.py + average_utils.py<br/><br/>Calculate trailing/leading averages<br/>rating_level, differences"]

    %% Output Components
    SENSORS["sensor/<br/>TibberPricesSensor<br/><br/>120+ price/level/rating sensors"]
    BINARY["binary_sensor/<br/>TibberPricesBinarySensor<br/><br/>Period indicators"]
    SERVICES["services/<br/><br/>Custom service endpoints<br/>(get_chartdata, ApexCharts)"]

    %% Flow Connections
    TIBBER -->|"Query user data<br/>Query prices<br/>(yesterday/today/tomorrow)"| API

    API -->|"Raw GraphQL response"| COORD

    COORD -->|"Check cache first"| CACHE_API
    CACHE_API -.->|"Cache hit:<br/>Return cached"| COORD
    CACHE_API -.->|"Cache miss:<br/>Fetch from API"| API

    COORD -->|"Raw price data"| TRANSFORM
    TRANSFORM -->|"Check cache"| CACHE_TRANS
    CACHE_TRANS -.->|"Cache hit"| TRANSFORM
    CACHE_TRANS -.->|"Cache miss"| ENRICH
    ENRICH -->|"Enriched data"| TRANSFORM

    TRANSFORM -->|"Enriched price data"| COORD

    COORD -->|"Enriched data"| PERIODS
    PERIODS -->|"Check cache"| CACHE_PERIOD
    CACHE_PERIOD -.->|"Hash match:<br/>Return cached"| PERIODS
    CACHE_PERIOD -.->|"Hash mismatch:<br/>Recalculate"| PERIODS

    PERIODS -->|"Calculated periods"| COORD

    COORD -->|"Complete data<br/>(prices + periods)"| SENSORS
    COORD -->|"Complete data"| BINARY
    COORD -->|"Data access"| SERVICES

    SENSORS -->|"Entity states"| HA
    BINARY -->|"Entity states"| HA
    SERVICES -->|"Service responses"| HA

    %% Config access
    CACHE_CONFIG -.->|"Parsed options"| TRANSFORM
    CACHE_CONFIG -.->|"Parsed options"| PERIODS
    CACHE_TRANS_TEXT -.->|"UI strings"| SENSORS
    CACHE_TRANS_TEXT -.->|"UI strings"| BINARY

    SETUP -->|"Initialize"| COORD
    SETUP -->|"Register"| SENSORS
    SETUP -->|"Register"| BINARY
    SETUP -->|"Register"| SERVICES

    %% Styling
    classDef external fill:#e1f5ff,stroke:#0288d1,stroke-width:3px
    classDef cache fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    classDef processing fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef output fill:#e8f5e9,stroke:#388e3c,stroke-width:2px

    class TIBBER,HA external
    class CACHE_API,CACHE_TRANS,CACHE_PERIOD,CACHE_CONFIG,CACHE_TRANS_TEXT cache
    class TRANSFORM,PERIODS,ENRICH processing
    class SENSORS,BINARY,SERVICES output
```

### Flow Description

1. **Setup** (`__init__.py`)
   - Integration loads, creates coordinator instance
   - Registers entity platforms (sensor, binary_sensor)
   - Sets up custom services

2. **Data Fetch** (every 15 minutes)
   - Coordinator triggers update via `api.py`
   - API client checks **persistent cache** first (`coordinator/cache.py`)
   - If cache valid → return cached data
   - If cache stale → query Tibber GraphQL API
   - Store fresh data in persistent cache (survives HA restart)

3. **Price Enrichment**
   - Coordinator passes raw prices to `DataTransformer`
   - Transformer checks **transformation cache** (memory)
   - If cache valid → return enriched data
   - If cache invalid → enrich via `price_utils.py` + `average_utils.py`
     - Calculate 24h trailing/leading averages
     - Calculate price differences (% from average)
     - Assign rating levels (LOW/NORMAL/HIGH)
   - Store enriched data in transformation cache

4. **Period Calculation**
   - Coordinator passes enriched data to `PeriodCalculator`
   - Calculator computes **hash** from prices + config
   - If hash matches cache → return cached periods
   - If hash differs → recalculate best/peak price periods
   - Store periods with new hash

5. **Entity Updates**
   - Coordinator provides complete data (prices + periods)
   - Sensors read values via unified handlers
   - Binary sensors evaluate period states
   - Entities update on quarter-hour boundaries (00/15/30/45)

6. **Service Calls**
   - Custom services access coordinator data directly
   - Return formatted responses (JSON, ApexCharts format)

---

## Caching Architecture

### Overview

The integration uses **5 independent caching layers** for optimal performance:

| Layer | Location | Lifetime | Invalidation | Memory |
|-------|----------|----------|--------------|--------|
| **API Cache** | `coordinator/cache.py` | 24h (user)<br/>Until midnight (prices) | Automatic | 50KB |
| **Translation Cache** | `const.py` | Until HA restart | Never | 5KB |
| **Config Cache** | `coordinator/*` | Until config change | Explicit | 1KB |
| **Period Cache** | `coordinator/periods.py` | Until data/config change | Hash-based | 10KB |
| **Transformation Cache** | `coordinator/data_transformation.py` | Until midnight/config | Automatic | 60KB |

**Total cache overhead:** ~126KB per coordinator instance (main entry + subentries)

### Cache Coordination

```mermaid
flowchart LR
    USER[("User changes options")]
    MIDNIGHT[("Midnight turnover")]
    NEWDATA[("Tomorrow data arrives")]

    USER -->|"Explicit invalidation"| CONFIG["Config Cache<br/>❌ Clear"]
    USER -->|"Explicit invalidation"| PERIOD["Period Cache<br/>❌ Clear"]
    USER -->|"Explicit invalidation"| TRANS["Transformation Cache<br/>❌ Clear"]

    MIDNIGHT -->|"Date validation"| API["API Cache<br/>❌ Clear prices"]
    MIDNIGHT -->|"Date check"| TRANS

    NEWDATA -->|"Hash mismatch"| PERIOD

    CONFIG -.->|"Next access"| CONFIG_NEW["Reparse options"]
    PERIOD -.->|"Next access"| PERIOD_NEW["Recalculate"]
    TRANS -.->|"Next access"| TRANS_NEW["Re-enrich"]
    API -.->|"Next access"| API_NEW["Fetch from API"]

    classDef invalid fill:#ffebee,stroke:#c62828,stroke-width:2px
    classDef rebuild fill:#e8f5e9,stroke:#388e3c,stroke-width:2px

    class CONFIG,PERIOD,TRANS,API invalid
    class CONFIG_NEW,PERIOD_NEW,TRANS_NEW,API_NEW rebuild
```

**Key insight:** No cascading invalidations - each cache is independent and rebuilds on-demand.

For detailed cache behavior, see [Caching Strategy](./caching-strategy.md).

---

## Component Responsibilities

### Core Components

| Component | File | Responsibility |
|-----------|------|----------------|
| **API Client** | `api.py` | GraphQL queries to Tibber, retry logic, error handling |
| **Coordinator** | `coordinator.py` | Update orchestration, cache management, absolute-time scheduling with boundary tolerance |
| **Data Transformer** | `coordinator/data_transformation.py` | Price enrichment (averages, ratings, differences) |
| **Period Calculator** | `coordinator/periods.py` | Best/peak price period calculation with relaxation |
| **Sensors** | `sensor/` | 80+ entities for prices, levels, ratings, statistics |
| **Binary Sensors** | `binary_sensor/` | Period indicators (best/peak price active) |
| **Services** | `services/` | Custom service endpoints (get_chartdata, get_apexcharts_yaml, refresh_user_data) |

### Sensor Architecture (Calculator Pattern)

The sensor platform uses **Calculator Pattern** for clean separation of concerns (refactored Nov 2025):

| Component | Files | Lines | Responsibility |
|-----------|-------|-------|----------------|
| **Entity Class** | `sensor/core.py` | 909 | Entity lifecycle, coordinator, delegates to calculators |
| **Calculators** | `sensor/calculators/` | 1,838 | Business logic (8 specialized calculators) |
| **Attributes** | `sensor/attributes/` | 1,209 | State presentation (8 specialized modules) |
| **Routing** | `sensor/value_getters.py` | 276 | Centralized sensor → calculator mapping |
| **Chart Export** | `sensor/chart_data.py` | 144 | Service call handling, YAML parsing |
| **Helpers** | `sensor/helpers.py` | 188 | Aggregation functions, utilities |

**Calculator Package** (`sensor/calculators/`):
- `base.py` - Abstract BaseCalculator with coordinator access
- `interval.py` - Single interval calculations (current/next/previous)
- `rolling_hour.py` - 5-interval rolling windows
- `daily_stat.py` - Calendar day min/max/avg statistics
- `window_24h.py` - Trailing/leading 24h windows
- `volatility.py` - Price volatility analysis
- `trend.py` - Complex trend analysis with caching
- `timing.py` - Best/peak price period timing
- `metadata.py` - Home/metering metadata

**Benefits:**
- 58% reduction in core.py (2,170 → 909 lines)
- Clear separation: Calculators (logic) vs Attributes (presentation)
- Independent testability for each calculator
- Easy to add sensors: Choose calculation pattern, add to routing

### Helper Utilities

| Utility | File | Purpose |
|---------|------|---------|
| **Price Utils** | `utils/price.py` | Rating calculation, enrichment, level aggregation |
| **Average Utils** | `utils/average.py` | Trailing/leading 24h average calculations |
| **Entity Utils** | `entity_utils/` | Shared icon/color/attribute logic |
| **Translations** | `const.py` | Translation loading and caching |

---

## Key Patterns

### 1. Dual Translation System

- **Standard translations** (`/translations/*.json`): HA-compliant schema for entity names
- **Custom translations** (`/custom_translations/*.json`): Extended descriptions, usage tips
- Both loaded at integration setup, cached in memory
- Access via `get_translation()` helper function

### 2. Price Data Enrichment

All quarter-hourly price intervals get augmented via `utils/price.py`:

```python
# Original from Tibber API
{
  "startsAt": "2025-11-03T14:00:00+01:00",
  "total": 0.2534,
  "level": "NORMAL"
}

# After enrichment (utils/price.py)
{
  "startsAt": "2025-11-03T14:00:00+01:00",
  "total": 0.2534,
  "level": "NORMAL",
  "trailing_avg_24h": 0.2312,    # ← Added: 24h trailing average
  "difference": 9.6,              # ← Added: % diff from trailing avg
  "rating_level": "NORMAL"        # ← Added: LOW/NORMAL/HIGH based on thresholds
}
```

### 3. Quarter-Hour Precision

- **API polling**: Every 15 minutes (coordinator fetch cycle)
- **Entity updates**: On 00/15/30/45-minute boundaries via `coordinator/listeners.py`
- **Timer scheduling**: Uses `async_track_utc_time_change(minute=[0, 15, 30, 45], second=0)`
  - HA may trigger ±few milliseconds before/after exact boundary
  - Smart boundary tolerance (±2 seconds) handles scheduling jitter in `sensor/helpers.py`
  - If HA schedules at 14:59:58 → rounds to 15:00:00 (shows new interval data)
  - If HA restarts at 14:59:30 → stays at 14:45:00 (shows current interval data)
- **Absolute time tracking**: Timer plans for **all future boundaries** (not relative delays)
  - Prevents double-updates (if triggered at 14:59:58, next trigger is 15:15:00, not 15:00:00)
- **Result**: Current price sensors update without waiting for next API poll

### 4. Calculator Pattern (Sensor Platform)

Sensors organized by **calculation method** (refactored Nov 2025):

**Unified Handler Methods** (`sensor/core.py`):
- `_get_interval_value(offset, type)` - current/next/previous intervals
- `_get_rolling_hour_value(offset, type)` - 5-interval rolling windows
- `_get_daily_stat_value(day, stat_func)` - calendar day min/max/avg
- `_get_24h_window_value(stat_func)` - trailing/leading statistics

**Routing** (`sensor/value_getters.py`):
- Single source of truth mapping 80+ entity keys to calculator methods
- Organized by calculation type (Interval, Rolling Hour, Daily Stats, etc.)

**Calculators** (`sensor/calculators/`):
- Each calculator inherits from `BaseCalculator` with coordinator access
- Focused responsibility: `IntervalCalculator`, `TrendCalculator`, etc.
- Complex logic isolated (e.g., `TrendCalculator` has internal caching)

**Attributes** (`sensor/attributes/`):
- Separate from business logic, handles state presentation
- Builds extra_state_attributes dicts for entity classes
- Unified builders: `build_sensor_attributes()`, `build_extra_state_attributes()`

**Benefits:**
- Minimal code duplication across 80+ sensors
- Clear separation of concerns (calculation vs presentation)
- Easy to extend: Add sensor → choose pattern → add to routing
- Independent testability for each component

---

## Performance Characteristics

### API Call Reduction

- **Without caching:** 96 API calls/day (every 15 min)
- **With caching:** ~1-2 API calls/day (only when cache expires)
- **Reduction:** ~98%

### CPU Optimization

| Optimization | Location | Savings |
|--------------|----------|---------|
| Config caching | `coordinator/*` | ~50% on config checks |
| Period caching | `coordinator/periods.py` | ~70% on period recalculation |
| Lazy logging | Throughout | ~15% on log-heavy operations |
| Import optimization | Module structure | ~20% faster loading |

### Memory Usage

- **Per coordinator instance:** ~126KB cache overhead
- **Typical setup:** 1 main + 2 subentries = ~378KB total
- **Redundancy eliminated:** 14% reduction (10KB saved per coordinator)

---

## Related Documentation

- **[Timer Architecture](./timer-architecture.md)** - Timer system, scheduling, coordination (3 independent timers)
- **[Caching Strategy](./caching-strategy.md)** - Detailed cache behavior, invalidation, debugging
- **[Setup Guide](./setup.md)** - Development environment setup
- **[Testing Guide](./testing.md)** - How to test changes
- **[Release Management](./release-management.md)** - Release workflow and versioning
- **[AGENTS.md](https://github.com/jpawlowski/hass.tibber_prices/blob/v0.25.0b0/AGENTS.md)** - Complete reference for AI development
