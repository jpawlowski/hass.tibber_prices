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

### Tomorrow's Prices Not Available

Tomorrow's electricity prices are typically published by Tibber between **13:00 and 15:00 CET** (Central European Time). Before that time, all "tomorrow" sensors will show unavailable or their last known state.

The integration automatically polls more frequently in the afternoon to detect when tomorrow's data becomes available. No manual action is needed.

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

```yaml
logger:
    default: warning
    logs:
        custom_components.tibber_prices: debug
```

Restart Home Assistant for the change to take effect.

### Targeted Logging

For specific subsystems, you can enable logging selectively:

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

### Temporary Debug Logging (No Restart)

You can also enable debug logging temporarily from the HA UI:

1. Go to **Developer Tools → Services**
2. Call service: `logger.set_level`
3. Data:
    ```yaml
    custom_components.tibber_prices: debug
    ```

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
