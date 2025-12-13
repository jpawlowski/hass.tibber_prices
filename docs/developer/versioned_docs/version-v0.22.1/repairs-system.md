# Repairs System

The Tibber Prices integration includes a proactive repair notification system that alerts users to important issues requiring attention. This system leverages Home Assistant's built-in `issue_registry` to create user-facing notifications in the UI.

## Overview

The repairs system is implemented in `coordinator/repairs.py` via the `TibberPricesRepairManager` class, which is instantiated in the coordinator and integrated into the update cycle.

**Design Principles:**
- **Proactive**: Detect issues before they become critical
- **User-friendly**: Clear explanations with actionable guidance
- **Auto-clearing**: Repairs automatically disappear when conditions resolve
- **Non-blocking**: Integration continues to work even with active repairs

## Implemented Repair Types

### 1. Tomorrow Data Missing

**Issue ID:** `tomorrow_data_missing_{entry_id}`

**When triggered:**
- Current time is after 18:00 (configurable via `TOMORROW_DATA_WARNING_HOUR`)
- Tomorrow's electricity price data is still not available

**When cleared:**
- Tomorrow's data becomes available
- Automatically checks on every successful API update

**User impact:**
Users cannot plan ahead for tomorrow's electricity usage optimization. Automations relying on tomorrow's prices will not work.

**Implementation:**
```python
# In coordinator update cycle
has_tomorrow_data = self._data_fetcher.has_tomorrow_data(result["priceInfo"])
await self._repair_manager.check_tomorrow_data_availability(
    has_tomorrow_data=has_tomorrow_data,
    current_time=current_time,
)
```

**Translation placeholders:**
- `home_name`: Name of the affected home
- `warning_hour`: Hour after which warning appears (default: 18)

### 2. Rate Limit Exceeded

**Issue ID:** `rate_limit_exceeded_{entry_id}`

**When triggered:**
- Integration encounters 3 or more consecutive rate limit errors (HTTP 429)
- Threshold configurable via `RATE_LIMIT_WARNING_THRESHOLD`

**When cleared:**
- Successful API call completes (no rate limit error)
- Error counter resets to 0

**User impact:**
API requests are being throttled, causing stale data. Updates may be delayed until rate limit expires.

**Implementation:**
```python
# In error handler
is_rate_limit = (
    "429" in error_str
    or "rate limit" in error_str
    or "too many requests" in error_str
)
if is_rate_limit:
    await self._repair_manager.track_rate_limit_error()

# On successful update
await self._repair_manager.clear_rate_limit_tracking()
```

**Translation placeholders:**
- `home_name`: Name of the affected home
- `error_count`: Number of consecutive rate limit errors

### 3. Home Not Found

**Issue ID:** `home_not_found_{entry_id}`

**When triggered:**
- Home configured in this integration is no longer present in Tibber account
- Detected during user data refresh (daily check)

**When cleared:**
- Home reappears in Tibber account (unlikely - manual cleanup expected)
- Integration entry is removed (shutdown cleanup)

**User impact:**
Integration cannot fetch data for a non-existent home. User must remove the config entry and re-add if needed.

**Implementation:**
```python
# After user data update
home_exists = self._data_fetcher._check_home_exists(home_id)
if not home_exists:
    await self._repair_manager.create_home_not_found_repair()
else:
    await self._repair_manager.clear_home_not_found_repair()
```

**Translation placeholders:**
- `home_name`: Name of the missing home
- `entry_id`: Config entry ID for reference

## Configuration Constants

Defined in `coordinator/constants.py`:

```python
TOMORROW_DATA_WARNING_HOUR = 18  # Hour after which to warn about missing tomorrow data
RATE_LIMIT_WARNING_THRESHOLD = 3  # Number of consecutive errors before creating repair
```

## Architecture

### Class Structure

```python
class TibberPricesRepairManager:
    """Manages repair issues for a single Tibber home."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        home_name: str,
    ) -> None:
        """Initialize repair manager."""
        self._hass = hass
        self._entry_id = entry_id
        self._home_name = home_name

        # State tracking
        self._tomorrow_data_repair_active = False
        self._rate_limit_error_count = 0
        self._rate_limit_repair_active = False
        self._home_not_found_repair_active = False
```

### State Tracking

Each repair type maintains internal state to avoid redundant operations:

- **`_tomorrow_data_repair_active`**: Boolean flag, prevents creating duplicate repairs
- **`_rate_limit_error_count`**: Integer counter, tracks consecutive errors
- **`_rate_limit_repair_active`**: Boolean flag, tracks repair status
- **`_home_not_found_repair_active`**: Boolean flag, one-time repair (manual cleanup)

### Lifecycle Integration

**Coordinator Initialization:**
```python
self._repair_manager = TibberPricesRepairManager(
    hass=hass,
    entry_id=self.config_entry.entry_id,
    home_name=self._home_name,
)
```

**Update Cycle Integration:**
```python
# Success path - check conditions
if result and "priceInfo" in result:
    has_tomorrow_data = self._data_fetcher.has_tomorrow_data(result["priceInfo"])
    await self._repair_manager.check_tomorrow_data_availability(
        has_tomorrow_data=has_tomorrow_data,
        current_time=current_time,
    )
await self._repair_manager.clear_rate_limit_tracking()

# Error path - track rate limits
if is_rate_limit:
    await self._repair_manager.track_rate_limit_error()
```

**Shutdown Cleanup:**
```python
async def async_shutdown(self) -> None:
    """Shut down coordinator and clean up."""
    await self._repair_manager.clear_all_repairs()
    # ... other cleanup ...
```

## Translation System

Repairs use Home Assistant's standard translation system. Translations are defined in:

- `/translations/en.json`
- `/translations/de.json`
- `/translations/nb.json`
- `/translations/nl.json`
- `/translations/sv.json`

**Structure:**
```json
{
  "issues": {
    "tomorrow_data_missing": {
      "title": "Tomorrow's price data missing for {home_name}",
      "description": "Detailed explanation with multiple paragraphs...\n\nPossible causes:\n- Cause 1\n- Cause 2"
    }
  }
}
```

## Home Assistant Integration

Repairs appear in:
- **Settings → System → Repairs** (main repairs panel)
- **Notifications** (bell icon in UI shows repair count)

Repair properties:
- **`is_fixable=False`**: No automated fix available (user action required)
- **`severity=IssueSeverity.WARNING`**: Yellow warning level (not critical)
- **`translation_key`**: References `issues.{key}` in translation files

## Testing Repairs

### Tomorrow Data Missing

1. Wait until after 18:00 local time
2. Ensure integration has no tomorrow price data
3. Repair should appear in UI
4. When tomorrow data arrives (next API fetch), repair clears

**Manual trigger:**
```python
# Temporarily set warning hour to current hour for testing
TOMORROW_DATA_WARNING_HOUR = datetime.now().hour
```

### Rate Limit Exceeded

1. Simulate 3+ consecutive rate limit errors
2. Repair should appear after 3rd error
3. Successful API call clears the repair

**Manual test:**
- Reduce API polling interval to trigger rate limiting
- Or temporarily return HTTP 429 in API client

### Home Not Found

1. Remove home from Tibber account via app/web
2. Wait for user data refresh (daily check)
3. Repair appears indicating home is missing
4. Remove integration entry to clear repair

## Adding New Repair Types

To add a new repair type:

1. **Add constants** (if needed) in `coordinator/constants.py`
2. **Add state tracking** in `TibberPricesRepairManager.__init__`
3. **Implement check method** with create/clear logic
4. **Add translations** to all 5 language files
5. **Integrate into coordinator** update cycle or error handlers
6. **Add cleanup** to `clear_all_repairs()` method
7. **Document** in this file

**Example template:**
```python
async def check_new_condition(self, *, param: bool) -> None:
    """Check new condition and create/clear repair."""
    should_warn = param  # Your condition logic

    if should_warn and not self._new_repair_active:
        await self._create_new_repair()
    elif not should_warn and self._new_repair_active:
        await self._clear_new_repair()

async def _create_new_repair(self) -> None:
    """Create new repair issue."""
    _LOGGER.warning("New issue detected - creating repair")

    ir.async_create_issue(
        self._hass,
        DOMAIN,
        f"new_issue_{self._entry_id}",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="new_issue",
        translation_placeholders={
            "home_name": self._home_name,
        },
    )
    self._new_repair_active = True

async def _clear_new_repair(self) -> None:
    """Clear new repair issue."""
    _LOGGER.debug("New issue resolved - clearing repair")

    ir.async_delete_issue(
        self._hass,
        DOMAIN,
        f"new_issue_{self._entry_id}",
    )
    self._new_repair_active = False
```

## Best Practices

1. **Always use state tracking** - Prevents duplicate repair creation
2. **Auto-clear when resolved** - Improves user experience
3. **Clear on shutdown** - Prevents orphaned repairs
4. **Use descriptive issue IDs** - Include entry_id for multi-home setups
5. **Provide actionable guidance** - Tell users what they can do
6. **Use appropriate severity** - WARNING for most cases, ERROR only for critical
7. **Test all language translations** - Ensure placeholders work correctly
8. **Document expected behavior** - What triggers, what clears, what user should do

## Future Enhancements

Potential additions to the repairs system:

- **Stale data warning**: Alert when cache is >24 hours old with no API updates
- **Missing permissions**: Detect insufficient API token scopes
- **Config migration needed**: Notify users of breaking changes requiring reconfiguration
- **Extreme price alert**: Warn when prices exceed historical thresholds (optional, user-configurable)

## References

- Home Assistant Repairs Documentation: https://developers.home-assistant.io/docs/core/platform/repairs
- Issue Registry API: `homeassistant.helpers.issue_registry`
- Integration Constants: `custom_components/tibber_prices/const.py`
- Repair Manager Implementation: `custom_components/tibber_prices/coordinator/repairs.py`
