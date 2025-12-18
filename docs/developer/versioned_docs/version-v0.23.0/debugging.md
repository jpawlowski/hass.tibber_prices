# Debugging Guide

Tips and techniques for debugging the Tibber Prices integration during development.

## Logging

### Enable Debug Logging

Add to `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.tibber_prices: debug
```

Restart Home Assistant to apply.

### Key Log Messages

**Coordinator Updates:**
```
[custom_components.tibber_prices.coordinator] Successfully fetched price data
[custom_components.tibber_prices.coordinator] Cache valid, using cached data
[custom_components.tibber_prices.coordinator] Midnight turnover detected, clearing cache
```

**Period Calculation:**
```
[custom_components.tibber_prices.coordinator.periods] Calculating BEST PRICE periods: flex=15.0%
[custom_components.tibber_prices.coordinator.periods] Day 2024-12-06: Found 2 periods
[custom_components.tibber_prices.coordinator.periods] Period 1: 02:00-05:00 (12 intervals)
```

**API Errors:**
```
[custom_components.tibber_prices.api] API request failed: Unauthorized
[custom_components.tibber_prices.api] Retrying (attempt 2/3) after 2.0s
```

## VS Code Debugging

### Launch Configuration

`.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Home Assistant",
      "type": "debugpy",
      "request": "launch",
      "module": "homeassistant",
      "args": ["-c", "config", "--debug"],
      "justMyCode": false,
      "env": {
        "PYTHONPATH": "${workspaceFolder}/.venv/lib/python3.13/site-packages"
      }
    }
  ]
}
```

### Set Breakpoints

**Coordinator update:**
```python
# coordinator/core.py
async def _async_update_data(self) -> dict:
    """Fetch data from API."""
    breakpoint()  # Or set VS Code breakpoint
```

**Period calculation:**
```python
# coordinator/period_handlers/core.py
def calculate_periods(...) -> list[dict]:
    """Calculate best/peak price periods."""
    breakpoint()
```

## pytest Debugging

### Run Single Test with Output

```bash
.venv/bin/python -m pytest tests/test_period_calculation.py::test_midnight_crossing -v -s
```

**Flags:**
- `-v` - Verbose output
- `-s` - Show print statements
- `-k pattern` - Run tests matching pattern

### Debug Test in VS Code

Set breakpoint in test file, use "Debug Test" CodeLens.

### Useful Test Patterns

**Print coordinator data:**
```python
def test_something(coordinator):
    print(f"Coordinator data: {coordinator.data}")
    print(f"Price info count: {len(coordinator.data['priceInfo'])}")
```

**Inspect period attributes:**
```python
def test_periods(hass, coordinator):
    periods = coordinator.data.get('best_price_periods', [])
    for period in periods:
        print(f"Period: {period['start']} to {period['end']}")
        print(f"  Intervals: {len(period['intervals'])}")
```

## Common Issues

### Integration Not Loading

**Check:**
```bash
grep "tibber_prices" config/home-assistant.log
```

**Common causes:**
- Syntax error in Python code → Check logs for traceback
- Missing dependency → Run `uv sync`
- Wrong file permissions → `chmod +x scripts/*`

### Sensors Not Updating

**Check coordinator state:**
```python
# In Developer Tools > Template
{{ states.sensor.tibber_home_current_interval_price.last_updated }}
```

**Debug in code:**
```python
# Add logging in sensor/core.py
_LOGGER.debug("Updating sensor %s: old=%s new=%s",
              self.entity_id, self._attr_native_value, new_value)
```

### Period Calculation Wrong

**Enable detailed period logs:**
```python
# coordinator/period_handlers/period_building.py
_LOGGER.debug("Candidate intervals: %s",
              [(i['startsAt'], i['total']) for i in candidates])
```

**Check filter statistics:**
```
[period_building] Flex filter blocked: 45 intervals
[period_building] Min distance blocked: 12 intervals
[period_building] Level filter blocked: 8 intervals
```

## Performance Profiling

### Time Execution

```python
import time

start = time.perf_counter()
result = expensive_function()
duration = time.perf_counter() - start
_LOGGER.debug("Function took %.3fs", duration)
```

### Memory Usage

```python
import tracemalloc

tracemalloc.start()
# ... your code ...
current, peak = tracemalloc.get_traced_memory()
_LOGGER.debug("Memory: current=%d peak=%d", current, peak)
tracemalloc.stop()
```

### Profile with cProfile

```bash
python -m cProfile -o profile.stats -m homeassistant -c config
python -m pstats profile.stats
# Then: sort cumtime, stats 20
```

## Live Debugging in Running HA

### Remote Debugging with debugpy

Add to coordinator code:
```python
import debugpy
debugpy.listen(5678)
_LOGGER.info("Waiting for debugger attach on port 5678")
debugpy.wait_for_client()
```

Connect from VS Code with remote attach configuration.

### IPython REPL

Install in container:
```bash
uv pip install ipython
```

Add breakpoint:
```python
from IPython import embed
embed()  # Drops into interactive shell
```

---

💡 **Related:**
- [Testing Guide](testing.md) - Writing and running tests
- [Setup Guide](setup.md) - Development environment
- [Architecture](architecture.md) - Code structure
