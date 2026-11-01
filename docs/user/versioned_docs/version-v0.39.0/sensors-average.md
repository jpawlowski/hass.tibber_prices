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

## Rolling Hour, Not Clock Hour

The Tibber app shows hourly prices for **clock hours** (13:00–13:59). The hourly sensors of this integration don't. Since prices come in 15-minute intervals, a fixed clock hour would mix intervals you've already lived through with ones still ahead, and its value would jump at every full hour. Instead, the hourly averages **move along with the 15-minute intervals**.

Three sensors cover "the hour", each with a different window. Example at **13:20** (current interval 13:15–13:30):

```
                        12:45  13:00  13:15  13:30  13:45  14:00  14:15  14:30  14:45  15:00
                                        ▲ now (13:20)
⌀ Hourly Price Current    ├──────────────────────────────────┤                                  12:45–14:00
⌀ Price Next 1h                                ├───────────────────────────┤                    13:30–14:30
⌀ Hourly Price Next                                   ├──────────────────────────────────┤      13:45–15:00
```

| Sensor | Window | Looks back? | Best for |
|--------|--------|-------------|----------|
| <EntityRef id="current_hour_average_price">⌀ Hourly Price Current</EntityRef> | 2 intervals before + current + 2 after (75 min), centered on now | ✅ 30 min | A smoothed "price right now" that ignores single-interval spikes |
| <EntityRef id="next_avg_1h">⌀ Price Next 1h</EntityRef> | The 4 intervals after the current one (60 min) | ❌ | "What will the next hour cost?" for decisions starting now |
| <EntityRef id="next_hour_average_price">⌀ Hourly Price Next</EntityRef> | Same as ⌀ Hourly Price Current, one hour later (75 min) | ❌ | "What will the price be around one hour from now?" |

The level and rating sensors for the current and next hour (**Current Hour Price Level**, **Next Hour Price Rating**, …) use the same windows as the matching average sensors.

**Prefer clock hours?** ⌀ Hourly Price Current and ⌀ Hourly Price Next also carry the average of the clock hour, like the Tibber app shows it: `clock_hour_price_mean`, `clock_hour_price_median`, `clock_hour_start` and `clock_hour_end`. At 13:20, ⌀ Hourly Price Current reports 13:00–14:00 there, ⌀ Hourly Price Next 14:00–15:00. The sensor state stays the rolling hour: it moves smoothly instead of jumping at every full hour.

Charts are different: with `resolution: hourly`, the chart actions always use clock hours, because a chart draws each hour as a step from :00 to :59.

**See the exact window:** ⌀ Hourly Price Current, ⌀ Hourly Price Next and the matching level and rating sensors have the attributes `window_start` and `window_end`. Use them to show the span on your dashboard:

<details>
<summary>Show YAML: Display the rolling hour window</summary>

```yaml
type: markdown
content: >
    Average {{ as_timestamp(state_attr('sensor.<home_name>_hourly_price_current', 'window_start')) | timestamp_custom('%H:%M') }}–{{ as_timestamp(state_attr('sensor.<home_name>_hourly_price_current', 'window_end')) | timestamp_custom('%H:%M') }}:
    {{ states('sensor.<home_name>_hourly_price_current') }} {{ state_attr('sensor.<home_name>_hourly_price_current', 'unit_of_measurement') }}
```

</details>

## Configurable Display: Median vs Mean

All average sensors support **two different calculation methods** for the state value:

- **Median** (default): The "middle value" when all prices are sorted. Resistant to extreme price spikes, shows the **typical** price level you experienced.
- **Arithmetic Mean**: The mathematical average including all prices. Better for **cost calculations** but affected by extreme spikes.

**Why two values matter:**

<details>
<summary>Show YAML: Why two values matter</summary>

```yaml
# Example price data for one day:
# Prices: 10, 12, 13, 15, 80 ct/kWh (one extreme spike)
#
# Median = 13 ct/kWh    ← "Typical" price level (middle value)
# Mean = 26 ct/kWh      ← Mathematical average (affected by spike)
```

</details>

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

<details>
<summary>Show YAML: Mean and Median in Automations</summary>

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

</details>

## Practical Examples

**Example 1: Smart dishwasher control**

Run dishwasher only when price is significantly below the daily typical level:

<details>
<summary>Show YAML: Practical Examples</summary>

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
<summary>Show YAML: Mean for Cost Calculations</summary>

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
<summary>Show YAML: Practical Examples</summary>

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
