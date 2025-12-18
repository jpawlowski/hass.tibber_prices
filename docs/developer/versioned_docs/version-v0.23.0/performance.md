# Performance Optimization

Guidelines for maintaining and improving integration performance.

## Performance Goals

Target metrics:
- **Coordinator update**: &lt;500ms (typical: 200-300ms)
- **Sensor update**: &lt;10ms per sensor
- **Period calculation**: &lt;100ms (typical: 20-50ms)
- **Memory footprint**: &lt;10MB per home
- **API calls**: &lt;100 per day per home

## Profiling

### Timing Decorator

Use for performance-critical functions:

```python
import time
import functools

def timing(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        duration = time.perf_counter() - start
        _LOGGER.debug("%s took %.3fms", func.__name__, duration * 1000)
        return result
    return wrapper

@timing
def expensive_calculation():
    # Your code here
```

### Memory Profiling

```python
import tracemalloc

tracemalloc.start()
# Run your code
current, peak = tracemalloc.get_traced_memory()
_LOGGER.info("Memory: current=%.2fMB peak=%.2fMB",
             current / 1024**2, peak / 1024**2)
tracemalloc.stop()
```

### Async Profiling

```bash
# Install aioprof
uv pip install aioprof

# Run with profiling
python -m aioprof homeassistant -c config
```

## Optimization Patterns

### Caching

**1. Persistent Cache** (API data):
```python
# Already implemented in coordinator/cache.py
store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
data = await store.async_load()
```

**2. Translation Cache** (in-memory):
```python
# Already implemented in const.py
_TRANSLATION_CACHE: dict[str, dict] = {}

def get_translation(path: str, language: str) -> dict:
    cache_key = f"{path}_{language}"
    if cache_key not in _TRANSLATION_CACHE:
        _TRANSLATION_CACHE[cache_key] = load_translation(path, language)
    return _TRANSLATION_CACHE[cache_key]
```

**3. Config Cache** (invalidated on options change):
```python
class DataTransformer:
    def __init__(self):
        self._config_cache: dict | None = None

    def get_config(self) -> dict:
        if self._config_cache is None:
            self._config_cache = self._build_config()
        return self._config_cache

    def invalidate_config_cache(self):
        self._config_cache = None
```

### Lazy Loading

**Load data only when needed:**
```python
@property
def extra_state_attributes(self) -> dict | None:
    """Return attributes."""
    # Calculate only when accessed
    if self.entity_description.key == "complex_sensor":
        return self._calculate_complex_attributes()
    return None
```

### Bulk Operations

**Process multiple items at once:**
```python
# ❌ Slow - loop with individual operations
for interval in intervals:
    enriched = enrich_single_interval(interval)
    results.append(enriched)

# ✅ Fast - bulk processing
results = enrich_intervals_bulk(intervals)
```

### Async Best Practices

**1. Concurrent API calls:**
```python
# ❌ Sequential (slow)
user_data = await fetch_user_data()
price_data = await fetch_price_data()

# ✅ Concurrent (fast)
user_data, price_data = await asyncio.gather(
    fetch_user_data(),
    fetch_price_data()
)
```

**2. Don't block event loop:**
```python
# ❌ Blocking
result = heavy_computation()  # Blocks for seconds

# ✅ Non-blocking
result = await hass.async_add_executor_job(heavy_computation)
```

## Memory Management

### Avoid Memory Leaks

**1. Clear references:**
```python
class Coordinator:
    async def async_shutdown(self):
        """Clean up resources."""
        self._listeners.clear()
        self._data = None
        self._cache = None
```

**2. Use weak references for callbacks:**
```python
import weakref

class Manager:
    def __init__(self):
        self._callbacks: list[weakref.ref] = []

    def register(self, callback):
        self._callbacks.append(weakref.ref(callback))
```

### Efficient Data Structures

**Use appropriate types:**
```python
# ❌ List for lookups (O(n))
if timestamp in timestamp_list:
    ...

# ✅ Set for lookups (O(1))
if timestamp in timestamp_set:
    ...

# ❌ List comprehension with filter
results = [x for x in items if condition(x)]

# ✅ Generator for large datasets
results = (x for x in items if condition(x))
```

## Coordinator Optimization

### Minimize API Calls

**Already implemented:**
- Cache valid until midnight
- User data cached for 24h
- Only poll when tomorrow data expected

**Monitor API usage:**
```python
_LOGGER.debug("API call: %s (cache_age=%s)",
              endpoint, cache_age)
```

### Smart Updates

**Only update when needed:**
```python
async def _async_update_data(self) -> dict:
    """Fetch data from API."""
    if self._is_cache_valid():
        _LOGGER.debug("Using cached data")
        return self.data

    # Fetch new data
    return await self._fetch_data()
```

## Database Impact

### State Class Selection

**Affects long-term statistics storage:**
```python
# ❌ MEASUREMENT for prices (stores every change)
state_class=SensorStateClass.MEASUREMENT  # ~35K records/year

# ✅ None for prices (no long-term stats)
state_class=None  # Only current state

# ✅ TOTAL for counters only
state_class=SensorStateClass.TOTAL  # For cumulative values
```

### Attribute Size

**Keep attributes minimal:**
```python
# ❌ Large nested structures (KB per update)
attributes = {
    "all_intervals": [...],  # 384 intervals
    "full_history": [...],   # Days of data
}

# ✅ Essential data only (bytes per update)
attributes = {
    "timestamp": "...",
    "rating_level": "...",
    "next_interval": "...",
}
```

## Testing Performance

### Benchmark Tests

```python
import pytest
import time

@pytest.mark.benchmark
def test_period_calculation_performance(coordinator):
    """Period calculation should complete in &lt;100ms."""
    start = time.perf_counter()

    periods = calculate_periods(coordinator.data)

    duration = time.perf_counter() - start
    assert duration < 0.1, f"Too slow: {duration:.3f}s"
```

### Load Testing

```python
@pytest.mark.integration
async def test_multiple_homes_performance(hass):
    """Test with 10 homes."""
    coordinators = []
    for i in range(10):
        coordinator = create_coordinator(hass, home_id=f"home_{i}")
        await coordinator.async_refresh()
        coordinators.append(coordinator)

    # Verify memory usage
    # Verify update times
```

## Monitoring in Production

### Log Performance Metrics

```python
@timing
async def _async_update_data(self) -> dict:
    """Fetch data with timing."""
    result = await self._fetch_data()
    _LOGGER.info("Update completed in %.2fs", timing_duration)
    return result
```

### Memory Tracking

```python
import psutil
import os

process = psutil.Process(os.getpid())
memory_mb = process.memory_info().rss / 1024**2
_LOGGER.debug("Current memory usage: %.2f MB", memory_mb)
```

---

💡 **Related:**
- [Caching Strategy](caching-strategy.md) - Cache layers
- [Architecture](architecture.md) - System design
- [Debugging](debugging.md) - Profiling tools
