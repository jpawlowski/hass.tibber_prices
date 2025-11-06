# Copilot Instructions

This is a **Home Assistant custom component** for Tibber electricity price data, distributed via **HACS**. It fetches, caches, and enriches **quarter-hourly** electricity prices with statistical analysis, price levels, and ratings.

## Architecture Overview

**Core Data Flow:**

1. `TibberPricesApiClient` (`api.py`) queries Tibber's GraphQL API with `resolution:QUARTER_HOURLY` for user data and prices (yesterday/today/tomorrow - 192 intervals total)
2. `TibberPricesDataUpdateCoordinator` (`coordinator.py`) orchestrates updates every 15 minutes, manages persistent storage via `Store`, and schedules quarter-hour entity refreshes
3. Price enrichment functions (`price_utils.py`, `average_utils.py`) calculate trailing/leading 24h averages, price differences, and rating levels for each 15-minute interval
4. Entity platforms (`sensor.py`, `binary_sensor.py`) expose enriched data as Home Assistant entities
5. Custom services (`services.py`) provide API endpoints for integrations like ApexCharts

**Key Patterns:**

-   **Dual translation system**: Standard HA translations in `/translations/` (config flow, UI strings per HA schema), supplemental in `/custom_translations/` (entity descriptions not supported by HA schema). Both must stay in sync. Use `async_load_translations()` and `async_load_standard_translations()` from `const.py`. When to use which: `/translations/` is bound to official HA schema requirements; anything else goes in `/custom_translations/` (requires manual translation loading).
-   **Price data enrichment**: All quarter-hourly price intervals get augmented with `trailing_avg_24h`, `difference`, and `rating_level` fields via `enrich_price_info_with_differences()` in `price_utils.py`. Enriched structure example:
    ```python
    {
      "startsAt": "2025-11-03T14:00:00+01:00",
      "total": 0.2534,              # Original from API
      "level": "NORMAL",            # Original from API
      "trailing_avg_24h": 0.2312,   # Added: 24h trailing average
      "difference": 9.6,            # Added: % diff from trailing avg
      "rating_level": "NORMAL"      # Added: LOW/NORMAL/HIGH based on thresholds
    }
    ```
-   **Quarter-hour precision**: Entities update on 00/15/30/45-minute boundaries via `_schedule_quarter_hour_refresh()` in coordinator, not just on data fetch intervals. This ensures current price sensors update without waiting for the next API poll.
-   **Currency handling**: Multi-currency support with major/minor units (e.g., EUR/ct, NOK/øre) via `get_currency_info()` and `format_price_unit_*()` in `const.py`.
-   **Intelligent caching strategy**: Minimizes API calls while ensuring data freshness:
    -   User data cached for 24h (rarely changes)
    -   Price data validated against calendar day - cleared on midnight turnover to force fresh fetch
    -   Cache survives HA restarts via `Store` persistence
    -   API polling intensifies only when tomorrow's data expected (afternoons)
    -   Stale cache detection via `_is_cache_valid()` prevents using yesterday's data as today's

**Component Structure:**

```
custom_components/tibber_prices/
├── __init__.py           # Entry setup, platform registration
├── coordinator.py        # DataUpdateCoordinator with caching/scheduling
├── api.py                # GraphQL client with retry/error handling
├── price_utils.py        # Price enrichment, level/rating calculations
├── average_utils.py      # Trailing/leading average utilities
├── services.py           # Custom services (get_price, ApexCharts, etc.)
├── sensor.py             # Price/stats/diagnostic sensors
├── binary_sensor.py      # Peak/best hour binary sensors
├── entity.py             # Base TibberPricesEntity class
├── data.py               # @dataclass TibberPricesData
├── const.py              # Constants, translation loaders, currency helpers
├── config_flow.py        # UI configuration flow
└── services.yaml         # Service definitions
```

## Development Workflow

**Start dev environment:**

```bash
./scripts/develop  # Starts HA in debug mode with config/ dir, sets PYTHONPATH
```

**Linting (auto-fix):**

```bash
./scripts/lint     # Runs ruff format + ruff check --fix
```

**Linting (check-only):**

```bash
./scripts/lint-check  # CI mode, no modifications
```

**Testing:**

```bash
pytest tests/      # Unit tests exist (test_*.py) but no framework enforced
```

**Key commands:**

-   Dev container includes `hass` CLI for manual HA operations
-   Use `uv run --active` prefix for running Python tools in the venv
-   `.ruff.toml` enforces max line length 120, complexity ≤25, Python 3.13 target

## Critical Project-Specific Patterns

**1. Translation Loading (Async-First)**
Always load translations at integration setup or before first use:

```python
# In __init__.py async_setup_entry:
await async_load_translations(hass, "en")
await async_load_standard_translations(hass, "en")
```

Access cached translations synchronously later via `get_translation(path, language)`.

**2. Price Data Enrichment**
Never use raw API price data directly. Always enrich first:

```python
from .price_utils import enrich_price_info_with_differences

enriched = enrich_price_info_with_differences(
    price_info_data,  # Raw API response
    thresholds,       # User-configured rating thresholds
)
```

This adds `trailing_avg_24h`, `difference`, `rating_level` to each interval.

**3. Time Handling**
Always prefer Home Assistant utilities over standard library equivalents. Use `dt_util` from `homeassistant.util` instead of Python's `datetime` module.

**Critical:** Always use `dt_util.as_local()` when comparing API timestamps to local time:

```python
from homeassistant.util import dt as dt_util

# ✅ Use dt_util for timezone-aware operations
price_time = dt_util.parse_datetime(price_data["startsAt"])
price_time = dt_util.as_local(price_time)  # IMPORTANT: Convert to HA's local timezone
now = dt_util.now()  # Current time in HA's timezone

# ❌ Avoid standard library datetime for timezone operations
# from datetime import datetime
# now = datetime.now()  # Don't use this
```

When you need Python's standard datetime types (e.g., for type annotations), import only specific types:

```python
from datetime import date, datetime, timedelta  # For type hints
from homeassistant.util import dt as dt_util    # For operations

def _needs_tomorrow_data(self, tomorrow_date: date) -> bool:
    """Use date type hint but dt_util for operations."""
    price_time = dt_util.parse_datetime(starts_at)
    price_date = dt_util.as_local(price_time).date()  # Convert to local before extracting date
```

**4. Coordinator Data Structure**
Access coordinator data like:

```python
coordinator.data = {
    "user_data": {...},      # Cached user info from viewer query
    "priceInfo": {
        "yesterday": [...],  # List of enriched price dicts
        "today": [...],
        "tomorrow": [...],
        "currency": "EUR",
    },
}
```

**5. Service Response Pattern**
Services use `SupportsResponse.ONLY` and must return dicts:

```python
@callback
def async_setup_services(hass: HomeAssistant) -> None:
    hass.services.async_register(
        DOMAIN, "get_price", _get_price,
        schema=PRICE_SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
```

## Code Quality Rules

**Ruff config (`.ruff.toml`):**

-   Max line length: **120** chars (not 88 from default Black)
-   Max complexity: **25** (McCabe)
-   Target: Python 3.13
-   No unused imports/variables (`F401`, `F841`)
-   No mutable default args (`B008`)
-   Use `_LOGGER` not `print()` (`T201`)

**Import order (enforced by isort):**

1. Python stdlib (only specific types needed, e.g., `from datetime import date, datetime, timedelta`)
2. Third-party (`homeassistant.*`, `aiohttp`, etc.)
3. Local (`.api`, `.const`, etc.)

**Import best practices:**

-   Prefer Home Assistant utilities over stdlib equivalents: `from homeassistant.util import dt as dt_util` instead of `import datetime`
-   Import only specific stdlib types when needed for type hints: `from datetime import date, datetime, timedelta`
-   Use `dt_util` for all datetime operations (parsing, timezone conversion, current time)
-   Avoid aliasing stdlib modules with same names as HA utilities (e.g., `import datetime as dt` conflicts with `dt_util`)

**Error handling best practices:**

-   Keep try blocks minimal - only wrap code that can throw exceptions
-   Process data **after** the try/except block, not inside
-   Catch specific exceptions, avoid bare `except Exception:` (allowed only in config flows and background tasks)
-   Use `ConfigEntryNotReady` for temporary failures (device offline)
-   Use `ConfigEntryAuthFailed` for auth issues
-   Use `ServiceValidationError` for user input errors in services

**Logging guidelines:**

-   Use lazy logging: `_LOGGER.debug("Message with %s", variable)`
-   No periods at end of log messages
-   No integration name in messages (added automatically)
-   Debug level for non-user-facing messages

**Function organization:**
Public entry points → direct helpers (call order) → pure utilities. Prefix private helpers with `_`.

**No backwards compatibility code** unless explicitly requested. Target latest HA stable only.

**Translation sync:** When updating `/translations/en.json`, update ALL language files (`de.json`, etc.) with same keys (placeholder values OK).

## Common Tasks

**Add a new sensor:**

1. Define entity description in `sensor.py` (add to `SENSOR_TYPES`)
2. Add translation keys to `/translations/en.json` and `/custom_translations/en.json`
3. Sync all language files
4. Implement `@property` methods in `TibberPricesSensor` class

**Modify price calculations:**
Edit `price_utils.py` or `average_utils.py`. These are stateless pure functions operating on price lists.

**Add a new service:**

1. Define schema in `services.py` (top-level constants)
2. Add service definition to `services.yaml`
3. Implement handler function in `services.py`
4. Register in `async_setup_services()`

**Change update intervals:**
Edit `UPDATE_INTERVAL` in `coordinator.py` (default: 15 min) or `QUARTER_HOUR_BOUNDARIES` for entity refresh timing.

**Debug GraphQL queries:**
Check `api.py` → `QueryType` enum and `_build_query()` method. Queries are dynamically constructed based on operation type.

## Anti-Patterns to Avoid

**Never do these:**

```python
# ❌ Blocking operations in event loop
data = requests.get(url)  # Use aiohttp with async_get_clientsession(hass)
time.sleep(5)             # Use await asyncio.sleep(5)

# ❌ Processing data inside try block
try:
    data = await api.get_data()
    processed = data["value"] * 100  # Move outside try
    self._attr_native_value = processed
except ApiError:
    pass

# ❌ Hardcoded strings (not translatable)
self._attr_name = "Temperature Sensor"  # Use translation_key instead

# ❌ Accessing hass.data directly in tests
coord = hass.data[DOMAIN][entry.entry_id]  # Use proper fixtures

# ❌ User-configurable polling intervals
vol.Optional("scan_interval"): cv.positive_int  # Not allowed, integration determines this

# ❌ Using standard library datetime for timezone operations
from datetime import datetime
now = datetime.now()  # Use dt_util.now() instead
```

**Do these instead:**

```python
# ✅ Async operations
data = await session.get(url)
await asyncio.sleep(5)

# ✅ Process after exception handling
try:
    data = await api.get_data()
except ApiError:
    return
processed = data["value"] * 100  # Safe processing after try/except

# ✅ Translatable entities
_attr_has_entity_name = True
_attr_translation_key = "temperature_sensor"

# ✅ Proper test setup with fixtures
@pytest.fixture
async def init_integration(hass, mock_config_entry):
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    return mock_config_entry

# ✅ Use Home Assistant datetime utilities
from homeassistant.util import dt as dt_util
now = dt_util.now()  # Timezone-aware current time
```
