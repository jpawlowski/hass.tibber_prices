# Configuration

> **Note:** This guide is under construction. For detailed setup instructions, please refer to the [main README](https://github.com/jpawlowski/hass.tibber_prices/blob/main/README.md).

> **Entity ID tip:** `<home_name>` is a placeholder for your Tibber home display name in Home Assistant. Entity IDs are derived from the displayed name (localized), so the exact slug may differ. Example suffixes below use the English display names (en.json) as a baseline. You can find the real ID in **Settings → Devices & Services → Entities** (or **Developer Tools → States**).

## Initial Setup

Coming soon...

## Configuration Options

### Average Sensor Display Settings

**Location:** Settings → Devices & Services → Tibber Prices → Configure → Step 6

The integration allows you to choose how average price sensors display their values. This setting affects all average sensors (daily, 24h rolling, hourly smoothed, and future forecasts).

#### Display Modes

**Median (Default):**
- Shows the "middle value" when all prices are sorted
- **Resistant to extreme spikes** - one expensive hour doesn't skew the result
- Best for understanding **typical price levels**
- Example: "What was the typical price today?"

**Arithmetic Mean:**
- Shows the mathematical average of all prices
- **Includes effect of spikes** - reflects actual cost if consuming evenly
- Best for **cost calculations and budgeting**
- Example: "What was my average cost per kWh today?"

#### Why This Matters

Consider a day with these hourly prices:
```
10, 12, 13, 15, 80 ct/kWh
```

- **Median = 13 ct/kWh** ← "Typical" price (middle value, ignores spike)
- **Mean = 26 ct/kWh** ← Average cost (spike pulls it up)

The median tells you the price was **typically** around 13 ct/kWh (4 out of 5 hours). The mean tells you if you consumed evenly, your **average cost** was 26 ct/kWh.

#### Automation-Friendly Design

**Both values are always available as attributes**, regardless of your display choice:

```yaml
# These attributes work regardless of display setting:
{{ state_attr('sensor.<home_name>_price_today', 'price_median') }}
{{ state_attr('sensor.<home_name>_price_today', 'price_mean') }}
```

This means:
- ✅ You can change the display anytime without breaking automations
- ✅ Automations can use both values for different purposes
- ✅ No need to create template sensors for the "other" value

#### Affected Sensors

This setting applies to:
- Daily average sensors (today, tomorrow)
- 24-hour rolling averages (trailing, leading)
- Hourly smoothed prices (current hour, next hour)
- Future forecast sensors (next 1h, 2h, 3h, ... 12h)

See the **[Sensors Guide](sensors.md#average-price-sensors)** for detailed examples.

#### Choosing Your Display

**Choose Median if:**
- 👥 You show prices to users ("What's today like?")
- 📊 You want dashboard values that represent typical conditions
- 🎯 You compare price levels across days
- 🔍 You analyze volatility (comparing typical vs extremes)

**Choose Mean if:**
- 💰 You calculate costs and budgets
- 📈 You forecast energy expenses
- 🧮 You need mathematical accuracy for financial planning
- 📊 You track actual average costs over time

**Pro Tip:** Most users prefer **Median** for displays (more intuitive), but use `price_mean` attribute in cost calculation automations.

## Runtime Configuration Entities

The integration provides optional configuration entities that allow you to override period calculation settings at runtime through automations. These entities are **disabled by default** and can be enabled individually as needed.

### Available Configuration Entities

When enabled, these entities override the corresponding Options Flow settings:

#### Best Price Period Settings

| Entity | Type | Range | Description |
|--------|------|-------|-------------|
| **Best Price: Flexibility** | Number | 0-50% | Maximum above daily minimum for "best price" intervals |
| **Best Price: Minimum Distance** | Number | -50-0% | Required distance below daily average |
| **Best Price: Minimum Period Length** | Number | 15-180 min | Shortest period duration to consider |
| **Best Price: Minimum Periods** | Number | 1-10 | Target number of periods per day |
| **Best Price: Relaxation Attempts** | Number | 1-12 | Steps to try when relaxing criteria |
| **Best Price: Gap Tolerance** | Number | 0-8 | Consecutive intervals allowed above threshold |
| **Best Price: Achieve Minimum Count** | Switch | On/Off | Enable relaxation algorithm |

#### Peak Price Period Settings

| Entity | Type | Range | Description |
|--------|------|-------|-------------|
| **Peak Price: Flexibility** | Number | -50-0% | Maximum below daily maximum for "peak price" intervals |
| **Peak Price: Minimum Distance** | Number | 0-50% | Required distance above daily average |
| **Peak Price: Minimum Period Length** | Number | 15-180 min | Shortest period duration to consider |
| **Peak Price: Minimum Periods** | Number | 1-10 | Target number of periods per day |
| **Peak Price: Relaxation Attempts** | Number | 1-12 | Steps to try when relaxing criteria |
| **Peak Price: Gap Tolerance** | Number | 0-8 | Consecutive intervals allowed below threshold |
| **Peak Price: Achieve Minimum Count** | Switch | On/Off | Enable relaxation algorithm |

### How Runtime Overrides Work

1. **Disabled (default):** The Options Flow setting is used
2. **Enabled:** The entity value overrides the Options Flow setting
3. **Value changes:** Trigger immediate period recalculation
4. **HA restart:** Entity values are restored automatically

### Viewing Entity Descriptions

Each configuration entity includes a detailed description attribute explaining what the setting does - the same information shown in the Options Flow.

**Note:** For **Number entities**, Home Assistant displays a history graph by default, which hides the attributes panel. To view the `description` attribute:

1. Go to **Developer Tools → States**
2. Search for the entity (e.g., `number.<home_name>_best_price_flexibility_override`)
3. Expand the attributes section to see the full description

**Switch entities** display their attributes normally in the entity details view.

### Example: Seasonal Automation

```yaml
automation:
  - alias: "Winter: Stricter Best Price Detection"
    trigger:
      - platform: time
        at: "00:00:00"
    condition:
      - condition: template
        value_template: "{{ now().month in [11, 12, 1, 2] }}"
    action:
      - service: number.set_value
        target:
          entity_id: number.<home_name>_best_price_flexibility_override
        data:
          value: 10  # Stricter than default 15%
```

### Recorder Optimization (Optional)

These configuration entities are designed to minimize database impact:
- **EntityCategory.CONFIG** - Excluded from Long-Term Statistics
- All attributes excluded from history recording
- Only state value changes are recorded

If you frequently adjust these settings via automations or want to track configuration changes over time, the default behavior is fine.

However, if you prefer to **completely exclude** these entities from the recorder (no history graph, no database entries), add this to your `configuration.yaml`:

```yaml
recorder:
  exclude:
    entity_globs:
      # Exclude all Tibber Prices configuration entities
      - number.*_best_price_*_override
      - number.*_peak_price_*_override
      - switch.*_best_price_*_override
      - switch.*_peak_price_*_override
```

This is especially useful if:
- You rarely change these settings
- You want the smallest possible database footprint
- You don't need to see the history graph for these entities
