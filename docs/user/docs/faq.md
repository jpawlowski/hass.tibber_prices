# FAQ - Frequently Asked Questions

Common questions about the Tibber Prices integration.

## General Questions

### Why don't I see tomorrow's prices yet?

Tomorrow's prices are published by Tibber around **13:00 CET** (12:00 UTC in winter, 11:00 UTC in summer).

- **Before publication**: Sensors show `unavailable` or use today's data
- **After publication**: Integration automatically fetches new data within 15 minutes
- **No manual refresh needed** - polling happens automatically

### How often does the integration update data?

- **API Polling**: Every 15 minutes
- **Sensor Updates**: On quarter-hour boundaries (00, 15, 30, 45 minutes)
- **Cache**: Price data cached until midnight (reduces API load)

### Can I use multiple Tibber homes?

Yes! Use the **"Add another home"** option:

1. Settings → Devices & Services → Tibber Prices
2. Click "Configure" → "Add another home"
3. Select additional home from dropdown
4. Each home gets separate sensors with unique entity IDs

### Does this work without a Tibber subscription?

No, you need:
- Active Tibber electricity contract
- API token from [developer.tibber.com](https://developer.tibber.com/)

The integration is free, but requires Tibber as your electricity provider.

## Configuration Questions

### What are good values for price thresholds?

**Default values work for most users:**
- High Price Threshold: 30% above average
- Low Price Threshold: 15% below average

**Adjust if:**
- You're in a market with high volatility → increase thresholds
- You want more sensitive ratings → decrease thresholds
- Seasonal changes → review every few months

### How do I optimize Best Price Period detection?

**Key parameters:**
- **Flex**: 15-20% is optimal (default 15%)
- **Min Distance**: 5-10% recommended (default 5%)
- **Rating Levels**: Start with "CHEAP + VERY_CHEAP" (default)
- **Relaxation**: Keep enabled (helps find periods on expensive days)

See [Period Calculation](period-calculation.md) for detailed tuning guide.

### Why do I sometimes only get 1 period instead of 2?

This happens on **high-price days** when:
- Few intervals meet your criteria
- Relaxation is disabled
- Flex is too low
- Min Distance is too strict

**Solutions:**
1. Enable relaxation (recommended)
2. Increase flex to 20-25%
3. Reduce min_distance to 3-5%
4. Add more rating levels (include "NORMAL")

## Troubleshooting

### Sensors show "unavailable"

**Common causes:**
1. **API Token invalid** → Check token at developer.tibber.com
2. **No internet connection** → Check HA network
3. **Tibber API down** → Check [status.tibber.com](https://status.tibber.com)
4. **Integration not loaded** → Restart Home Assistant

### Best Price Period is ON all day

This means **all intervals meet your criteria** (very cheap day!):
- Not an error - enjoy the low prices!
- Consider tightening filters (lower flex, higher min_distance)
- Or add automation to only run during first detected period

### Prices are in wrong currency or wrong units

**Currency** is determined by your Tibber subscription (cannot be changed).

**Display mode** (base vs. subunit) is configurable:
- Configure in: `Settings > Devices & Services > Tibber Prices > Configure`
- Options:
  - **Base currency**: €/kWh, kr/kWh (decimal values like 0.25)
  - **Subunit**: ct/kWh, øre/kWh (larger values like 25.00)
- Smart defaults: EUR → subunit, NOK/SEK/DKK → base currency

If you see unexpected units, check your configuration in the integration options.

### Tomorrow data not appearing at all

**Check:**
1. Your Tibber home has hourly price contract (not fixed price)
2. API token has correct permissions
3. Integration logs for API errors (`/config/home-assistant.log`)
4. Tibber actually published data (check Tibber app)

## Automation Questions

> **Entity ID tip:** `<home_name>` is a placeholder for your Tibber home display name in Home Assistant. Entity IDs are derived from the displayed name (localized), so the exact slug may differ. Example suffixes below use the English display names (en.json) as a baseline. You can find the real ID in **Settings → Devices & Services → Entities** (or **Developer Tools → States**).

### How do I run dishwasher during cheap period?

```yaml
automation:
  - alias: "Dishwasher during Best Price"
    trigger:
      - platform: state
        entity_id: binary_sensor.<home_name>_best_price_period
        to: "on"
    condition:
      - condition: time
        after: "20:00:00"  # Only start after 8 PM
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.dishwasher
```

See [Automation Examples](automation-examples.md) for more recipes.

### Can I avoid peak prices automatically?

Yes! Use Peak Price Period binary sensor:

```yaml
automation:
  - alias: "Disable charging during peak prices"
    trigger:
      - platform: state
        entity_id: binary_sensor.<home_name>_peak_price_period
        to: "on"
    action:
      - service: switch.turn_off
        target:
          entity_id: switch.ev_charger
```

---

💡 **Still need help?**
- [Troubleshooting Guide](troubleshooting.md)
- [GitHub Issues](https://github.com/jpawlowski/hass.tibber_prices/issues)
