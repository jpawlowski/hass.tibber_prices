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

Coming soon...
