---
sidebar_label: ⚙️ General Settings
---

# ⚙️ General Settings

**Settings → Devices & Services → Tibber Prices → Configure → ⚙️ General Settings**

---

## Extended Entity Descriptions

Controls whether sensor attributes include detailed explanations and usage tips.

| State | Attributes included |
|-------|---------------------|
| **Disabled** (default) | `description` only — brief one-liner |
| **Enabled** | `description` + `long_description` + `usage_tips` |

Enable this while getting familiar with the integration. Once you know what each sensor does, disabling it reduces attribute clutter in your Developer Tools / history views.

## Average Sensor Display

Controls which statistical measure the sensor **state value** shows for all average price sensors. The other value is always available as an attribute regardless of this setting.

| Mode | Shows | Best for |
|------|-------|----------|
| **Median** (default) | Middle value when prices are sorted | Dashboards, typical price level |
| **Arithmetic Mean** | Mathematical average of all prices | Cost calculations, budgeting |

### Why the difference matters

Consider a day with these prices: `10, 12, 13, 15, 80 ct/kWh`

- **Median = 13 ct/kWh** — "typical" price (ignores the expensive spike)
- **Mean = 26 ct/kWh** — average cost if consuming evenly (spike included)

The median gives a better feel for what the day was like. The mean is more accurate for calculating what you actually paid on average.

### Both values always available

You can always access both values as attributes from any average sensor, regardless of this display setting:

```yaml
{{ state_attr('sensor.<home_name>_price_today', 'price_median') }}
{{ state_attr('sensor.<home_name>_price_today', 'price_mean') }}
```

This means you can change the display setting at any time without breaking automations that use attributes.

### Affected sensors

This setting applies to:
- Daily average sensors (today, tomorrow)
- 24-hour rolling averages (trailing, leading)
- Hourly smoothed prices (current hour, next hour)
- Future forecast sensors (next 1h, 2h, 3h, … 12h)

See **[Average Sensors](sensors-average.md)** for detailed examples.

### Choosing your mode

**Choose Median if:**
- 👥 You show prices to users ("What's today like?")
- 📊 You want dashboard values representing typical conditions
- 🎯 You compare price levels across days

**Choose Mean if:**
- 💰 You calculate costs and budgets
- 🧮 You need mathematical accuracy for financial planning
- 📊 You track actual average costs over time

**Pro tip:** Most users prefer **Median** for displays, but use the `price_mean` attribute in cost calculation automations.
