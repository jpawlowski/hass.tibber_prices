# Coding Guidelines

> **Note:** For complete coding standards, see [`AGENTS.md`](../../AGENTS.md).

## Code Style

- **Formatter/Linter**: Ruff (replaces Black, Flake8, isort)
- **Max line length**: 120 characters
- **Max complexity**: 25 (McCabe)
- **Target**: Python 3.13

Run before committing:
```bash
./scripts/lint
```

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

See [`AGENTS.md`](../../AGENTS.md) for complete guidelines.
