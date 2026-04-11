# Average & Statistics Sensors

:::tip Entity ID tip
`<home_name>` is a placeholder for your Tibber home display name in Home Assistant. Entity IDs are derived from the displayed name (localized), so the exact slug may differ. **Can't find a sensor?** Use the **[Entity Reference (All Languages)](sensor-reference.md)** to search by name in your language.
:::

The integration provides several sensors that calculate average electricity prices over different time windows. These sensors show a **typical** price value that represents the overall price level, helping you make informed decisions about when to use electricity.

## Available Average Sensors

| Sensor | Description | Time Window |
|--------|-------------|-------------|
| <EntityRef id="average_price_today">Average Price Today</EntityRef> | Typical price for current calendar day | 00:00 - 23:59 today |
| <EntityRef id="average_price_tomorrow">Average Price Tomorrow</EntityRef> | Typical price for next calendar day | 00:00 - 23:59 tomorrow |
| <EntityRef id="trailing_price_average">Trailing Price Average</EntityRef> | Typical price for last 24 hours | Rolling 24h backward |
| <EntityRef id="leading_price_average">Leading Price Average</EntityRef> | Typical price for next 24 hours | Rolling 24h forward |
| <EntityRef id="current_hour_average_price">Current Hour Average</EntityRef> | Smoothed price around current time | 5 intervals (~75 min) |
| <EntityRef id="next_hour_average_price">Next Hour Average</EntityRef> | Smoothed price around next hour | 5 intervals (~75 min) |
| **Next N Hours Average** (`next_avg_1h`–`next_avg_12h`) | Future price forecast | 1h, 2h, 3h, 4h, 5h, 6h, 8h, 12h |

## Configurable Display: Median vs Mean

All average sensors support **two different calculation methods** for the state value:

- **Median** (default): The "middle value" when all prices are sorted. Resistant to extreme price spikes, shows the **typical** price level you experienced.
- **Arithmetic Mean**: The mathematical average including all prices. Better for **cost calculations** but affected by extreme spikes.

**Why two values matter:**

```yaml
# Example price data for one day:
# Prices: 10, 12, 13, 15, 80 ct/kWh (one extreme spike)
#
# Median = 13 ct/kWh    ← "Typical" price level (middle value)
# Mean = 26 ct/kWh      ← Mathematical average (affected by spike)
```

The median shows you what price level was **typical** during that period, while the mean shows the actual **average cost** if you consumed evenly throughout the period.

## Configuring the Display

You can choose which value is displayed in the sensor state:

1. Go to **Settings → Devices & Services → Tibber Prices**
2. Click **Configure** on your home
3. Navigate to **Step 6: Average Sensor Display Settings**
4. Choose between:
   - **Median** (default) - Shows typical price level, resistant to spikes
   - **Arithmetic Mean** - Shows actual mathematical average

**Important:** Both values are **always available** as sensor attributes, regardless of your choice! This ensures your automations continue to work if you change the display setting.

## Using Both Values in Automations

Both `price_mean` and `price_median` are always available as attributes:

```yaml
# Example: Get both values regardless of display setting
sensor:
  - platform: template
    sensors:
      daily_price_analysis:
        friendly_name: "Daily Price Analysis"
        value_template: >
          {% set median = state_attr('sensor.<home_name>_price_today', 'price_median') %}
          {% set mean = state_attr('sensor.<home_name>_price_today', 'price_mean') %}
          {% set current = states('sensor.<home_name>_current_electricity_price') | float %}

          {% if current < median %}
            Below typical ({{ ((1 - current/median) * 100) | round(1) }}% cheaper)
          {% elif current < mean %}
            Typical price range
          {% else %}
            Above average ({{ ((current/mean - 1) * 100) | round(1) }}% more expensive)
          {% endif %}
```

## Practical Examples

**Example 1: Smart dishwasher control**

Run dishwasher only when price is significantly below the daily typical level:

<details>
<summary>Show YAML: Automation — start dishwasher when cheap</summary>

```yaml
automation:
  - alias: "Start Dishwasher When Cheap"
    trigger:
      - platform: state
        entity_id: binary_sensor.<home_name>_best_price_period
        to: "on"
    condition:
      # Only if current price is at least 20% below typical (median)
      - condition: template
        value_template: >
          {% set current = states('sensor.<home_name>_current_electricity_price') | float %}
          {% set median = state_attr('sensor.<home_name>_price_today', 'price_median') | float %}
          {{ current < (median * 0.8) }}
    action:
      - service: switch.turn_on
        entity_id: switch.dishwasher
```

</details>

**Example 2: Cost-aware heating control**

Use mean for actual cost calculations:

<details>
<summary>Show YAML: Automation — cost-aware heating control</summary>

```yaml
automation:
  - alias: "Heating Budget Control"
    trigger:
      - platform: time
        at: "06:00:00"
    action:
      # Calculate expected daily heating cost
      - variables:
          mean_price: "{{ state_attr('sensor.<home_name>_price_today', 'price_mean') | float }}"
          heating_kwh_per_day: 15  # Estimated consumption
          daily_cost: "{{ (mean_price * heating_kwh_per_day / 100) | round(2) }}"
      - service: notify.mobile_app
        data:
          title: "Heating Cost Estimate"
          message: "Expected cost today: €{{ daily_cost }} (avg price: {{ mean_price }} ct/kWh)"
```

</details>

**Example 3: Smart charging based on rolling average**

Use trailing average to understand recent price trends:

<details>
<summary>Show YAML: Automation — EV charging based on rolling average</summary>

```yaml
automation:
  - alias: "EV Charging - Price Trend Based"
    trigger:
      - platform: state
        entity_id: sensor.ev_battery_level
    condition:
      # Start charging if current price < 90% of recent 24h average
      - condition: template
        value_template: >
          {% set current = states('sensor.<home_name>_current_electricity_price') | float %}
          {% set trailing_avg = state_attr('sensor.<home_name>_price_trailing_24h', 'price_median') | float %}
          {{ current < (trailing_avg * 0.9) }}
      # And battery < 80%
      - condition: numeric_state
        entity_id: sensor.ev_battery_level
        below: 80
    action:
      - service: switch.turn_on
        entity_id: switch.ev_charger
```

</details>

## Key Attributes

All average sensors provide these attributes:

| Attribute | Description | Example |
|-----------|-------------|---------|
| `price_mean` | Arithmetic mean (always available) | 25.3 ct/kWh |
| `price_median` | Median value (always available) | 22.1 ct/kWh |
| `interval_count` | Number of intervals included | 96 |
| `timestamp` | Reference time for calculation | 2025-12-18T00:00:00+01:00 |

**Note:** The `price_mean` and `price_median` attributes are **always present** regardless of which value you configured for display. This ensures automation compatibility when changing the display setting.

## When to Use Which Value

**Use Median for:**
- ✅ Comparing "typical" price levels across days
- ✅ Determining if current price is unusually high/low
- ✅ User-facing displays ("What was today like?")
- ✅ Volatility analysis (comparing typical vs extremes)

**Use Mean for:**
- ✅ Cost calculations and budgeting
- ✅ Energy cost estimations
- ✅ Comparing actual average costs between periods
- ✅ Financial planning and forecasting

**Both values tell different stories:**
- High median + much higher mean = Expensive spikes occurred
- Low median + higher mean = Generally cheap with occasional spikes
- Similar median and mean = Stable prices (low volatility)
