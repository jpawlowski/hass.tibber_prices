---
comments: false
---

# Troubleshooting

## Common Issues

### Sensors Show "Unavailable"

**After initial setup or HA restart:**

This is normal. The integration needs up to one update cycle (15 minutes) to fetch data from the Tibber API. If sensors remain unavailable after 30 minutes:

1. Check your internet connection
2. Verify your Tibber API token is still valid at [developer.tibber.com](https://developer.tibber.com)
3. Check the logs for error messages (see [Debug Logging](#debug-logging) below)

**After working fine previously:**

- **API communication error**: Tibber's API may be temporarily down. The integration retries automatically — wait 15–30 minutes.
- **Authentication expired**: If you see a "Reauth required" notification in HA, your API token needs to be re-entered. Go to **Settings → Devices & Services → Tibber Prices** and follow the reauth flow.
- **Rate limiting**: If you have multiple integrations using the same Tibber token, you may hit API rate limits. Check logs for "429" or "rate limit" messages.

### Contract Has Not Started Yet (or Has Ended)

You can set up the integration before your Tibber contract starts, for example right after signing up. Tibber sends no prices before the start date, so until then:

- Only the diagnostic entities exist (connection, **Data Lifecycle Status** (`data_lifecycle_status`), subscription status and the home details). The **Data Lifecycle Status** shows `awaiting_subscription`, and the **Connection** sensor has a `subscription_phase` attribute (`pending`).
- Nothing is fetched from the Tibber API, so there are no error messages in the log.
- At the exact start date the integration reloads itself, creates the price entities and starts fetching prices. You don't need to do anything.

When a contract ends, the entities keep showing the last day of the contract and no longer change: "today" stays that last day, "yesterday" is the day before it and there is no "tomorrow". The **Data Lifecycle Status** shows `subscription_ended`. If you start a new contract, the integration picks it up within a day, or immediately after a restart.

### Tomorrow's Prices Not Available

Tomorrow's electricity prices are typically published by Tibber between **13:00 and 15:00 CET** (Central European Time). Before that time, all "tomorrow" sensors will show unavailable or their last known state.

The integration automatically polls more frequently in the afternoon to detect when tomorrow's data becomes available. No manual action is needed.

### Timing Sensors Show "Unknown" During an Active Period

If **Best Price Start** / **Best Price Starts In** (`best_price_next_start_time`, `best_price_next_in_minutes`) or the Peak Price equivalents show "Unknown" while a period is running, this is expected.

While a period is active, these sensors point to the *next* period after the current one. If none exists yet, there is no value to show. This is common when tomorrow's prices are not published yet (see above), because the active period may be the last one found for today. Once tomorrow's prices arrive and a further period is found, the sensors update on their own.

The same applies to Peak Price: if no further peak period is left today, its timing sensors stay "Unknown" until one appears.

If the sensors stay "Unknown" even though tomorrow's prices are available and a later period is expected, see [What to Include in Bug Reports](#what-to-include-in-bug-reports).

### Wrong Currency or Price Units

If prices show in the wrong currency or wrong unit (EUR vs ct):

1. Go to **Settings → Devices & Services → Tibber Prices → Configure**
2. Check the **Currency Display** step
3. Choose between base units (EUR, NOK, SEK) and sub-units (ct, øre)

Note: The currency is determined by your Tibber account's home country and cannot be changed — only the display unit (base vs. sub-unit) is configurable.

### No Best/Peak Price Periods Found

If the Best Price Period or Peak Price Period binary sensors never turn on:

1. **Check your flex settings**: A flex value that's too low may filter out all intervals. Try increasing it (e.g., from 10% to 20%).
2. **Enable relaxation**: In the options flow, enable relaxation for the affected period type. This automatically increases flex until periods are found.
3. **Check daily price variation**: On days with very flat prices (low volatility), periods may not meet the threshold criteria. This is expected behavior — the integration correctly identifies that no intervals stand out.

See the [Period Calculation Guide](period-calculation.md) for detailed configuration advice.

### Entities Duplicated After Reconfiguration

If you see duplicate entities after changing settings:

1. Go to **Settings → Devices & Services → Entities**
2. Filter by "Tibber Prices"
3. Remove any disabled or orphaned entities
4. Restart Home Assistant

### Integration Not Showing After Installation

If the integration doesn't appear in **Settings → Devices & Services → Add Integration**:

1. Confirm you restarted Home Assistant after installing via HACS
2. Clear your browser cache (Ctrl+Shift+R)
3. Check the HA logs for import errors related to `tibber_prices`

## Debug Logging

When reporting issues, debug logs help identify the problem quickly.

### Enable Debug Logging

Add this to your `configuration.yaml`:

<details>
<summary>Show YAML: configuration.yaml Logging</summary>

```yaml
logger:
    default: warning
    logs:
        custom_components.tibber_prices: debug
```

</details>

Restart Home Assistant for the change to take effect.

### Targeted Logging

For specific subsystems, you can enable logging selectively:

<details>
<summary>Show YAML: Targeted Subsystem Logging</summary>

```yaml
logger:
    default: warning
    logs:
        # API communication (requests, responses, errors)
        custom_components.tibber_prices.api: debug

        # Coordinator (data updates, caching, scheduling)
        custom_components.tibber_prices.coordinator: debug

        # Period calculation (best/peak price detection)
        custom_components.tibber_prices.coordinator.period_handlers: debug

        # Sensor value calculation
        custom_components.tibber_prices.sensor: debug
```

    </details>

### Temporary Debug Logging (No Restart)

You can also enable debug logging temporarily from the HA UI:

1. Go to **Developer Tools → Services**
2. Call service: `logger.set_level`
3. Data:
   <details>
   <summary>Show YAML example (temporary logger.set_level payload)</summary>

    ```yaml
    custom_components.tibber_prices: debug
    ```

   </details>

This resets when HA restarts.

### Downloading Diagnostics

For bug reports, include the integration's diagnostic dump:

1. Go to **Settings → Devices & Services → Tibber Prices**
2. Click the three-dot menu (⋮) on the integration card
3. Select **Download diagnostics**

The downloaded file includes configuration, cache status, period information, and recent errors — with sensitive data redacted.

### What to Include in Bug Reports

When opening a [GitHub issue](https://github.com/jpawlowski/hass.tibber_prices/issues/new):

1. **Integration version** (from Settings → Devices & Services → Tibber Prices)
2. **Home Assistant version** (from Settings → About)
3. **Description** of the problem and expected behavior
4. **Debug logs** (relevant excerpts from the HA log)
5. **Diagnostics file** (downloaded as described above)
6. **Steps to reproduce** (if applicable)

## Getting Help

- Check [existing issues](https://github.com/jpawlowski/hass.tibber_prices/issues)
- Open a [new issue](https://github.com/jpawlowski/hass.tibber_prices/issues/new) with detailed information
- Include logs, configuration, and steps to reproduce
