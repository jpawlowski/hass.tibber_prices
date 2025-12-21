---
comments: false
---

# Coding Guidelines

> **Note:** For complete coding standards, see [`AGENTS.md`](https://github.com/jpawlowski/hass.tibber_prices/blob/v0.23.1/AGENTS.md).

## Code Style

-   **Formatter/Linter**: Ruff (replaces Black, Flake8, isort)
-   **Max line length**: 120 characters
-   **Max complexity**: 25 (McCabe)
-   **Target**: Python 3.13

Run before committing:

```bash
./scripts/lint        # Auto-fix issues
./scripts/release/hassfest    # Validate integration structure
```

## Naming Conventions

### Class Names

**All public classes MUST use the integration name as prefix.**

This is a Home Assistant standard to avoid naming conflicts between integrations.

```python
# ✅ CORRECT
class TibberPricesApiClient:
class TibberPricesDataUpdateCoordinator:
class TibberPricesSensor:

# ❌ WRONG - Missing prefix
class ApiClient:
class DataFetcher:
class TimeService:
```

**When prefix is required:**
- Public classes used across multiple modules
- All exception classes
- All coordinator and entity classes
- Data classes (dataclasses, NamedTuples) used as public APIs

**When prefix can be omitted:**
- Private helper classes within a single module (prefix with `_` underscore)
- Type aliases and callbacks (e.g., `TimeServiceCallback`)
- Small internal NamedTuples for function returns

**Private Classes:**

If a helper class is ONLY used within a single module file, prefix it with underscore:

```python
# ✅ Private class - used only in this file
class _InternalHelper:
    """Helper used only within this module."""
    pass

# ❌ Wrong - no prefix but used across modules
class DataFetcher:  # Should be TibberPricesDataFetcher
    pass
```

**Note:** Currently (Nov 2025), this project has **NO private classes** - all classes are used across module boundaries.

**Current Technical Debt:**

Many existing classes lack the `TibberPrices` prefix. Before refactoring:
1. Document the plan in `/planning/class-naming-refactoring.md`
2. Use `multi_replace_string_in_file` for bulk renames
3. Test thoroughly after each module

See [`AGENTS.md`](https://github.com/jpawlowski/hass.tibber_prices/blob/v0.23.1/AGENTS.md) for complete list of classes needing rename.

## Import Order

1. Python stdlib (specific types only)
2. Third-party (`homeassistant.*`, `aiohttp`)
3. Local (`.api`, `.const`)

## Critical Patterns

### Time Handling

Always use `dt_util` from `homeassistant.util`:

```python
from homeassistant.util import dt as dt_util

price_time = dt_util.parse_datetime(starts_at)
price_time = dt_util.as_local(price_time)  # Convert to HA timezone
now = dt_util.now()
```

### Translation Loading

```python
# In __init__.py async_setup_entry:
await async_load_translations(hass, "en")
await async_load_standard_translations(hass, "en")
```

### Price Data Enrichment

Always enrich raw API data:

```python
from .price_utils import enrich_price_info_with_differences

enriched = enrich_price_info_with_differences(
    price_info_data,
    thresholds,
)
```

See [`AGENTS.md`](https://github.com/jpawlowski/hass.tibber_prices/blob/v0.23.1/AGENTS.md) for complete guidelines.
