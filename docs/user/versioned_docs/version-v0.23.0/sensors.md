---
comments: false
---

# Sensors

> **Note:** This guide is under construction. For now, please refer to the [main README](https://github.com/jpawlowski/hass.tibber_prices/blob/v0.23.0/README.md) for available sensors.

> **Tip:** Many sensors have dynamic icons and colors! See the **[Dynamic Icons Guide](dynamic-icons.md)** and **[Dynamic Icon Colors Guide](icon-colors.md)** to enhance your dashboards.

## Binary Sensors

### Best Price Period & Peak Price Period

These binary sensors indicate when you're in a detected best or peak price period. See the **[Period Calculation Guide](period-calculation.md)** for a detailed explanation of how these periods are calculated and configured.

**Quick overview:**

-   **Best Price Period**: Turns ON during periods with significantly lower prices than the daily average
-   **Peak Price Period**: Turns ON during periods with significantly higher prices than the daily average

Both sensors include rich attributes with period details, intervals, relaxation status, and more.

## Core Price Sensors

### Average Price Sensors

The integration provides several sensors that calculate average electricity prices over different time windows. These sensors show a **typical** price value that represents the overall price level, helping you make informed decisions about when to use electricity.

#### Available Average Sensors

| Sensor | Description | Time Window |
|--------|-------------|-------------|
| **Average Price Today** | Typical price for current calendar day | 00:00 - 23:59 today |
| **Average Price Tomorrow** | Typical price for next calendar day | 00:00 - 23:59 tomorrow |
| **Trailing Price Average** | Typical price for last 24 hours | Rolling 24h backward |
| **Leading Price Average** | Typical price for next 24 hours | Rolling 24h forward |
| **Current Hour Average** | Smoothed price around current time | 5 intervals (~75 min) |
| **Next Hour Average** | Smoothed price around next hour | 5 intervals (~75 min) |
| **Next N Hours Average** | Future price forecast | 1h, 2h, 3h, 4h, 5h, 6h, 8h, 12h |

#### Configurable Display: Median vs Mean

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

#### Configuring the Display

You can choose which value is displayed in the sensor state:

1. Go to **Settings → Devices & Services → Tibber Prices**
2. Click **Configure** on your home
3. Navigate to **Step 6: Average Sensor Display Settings**
4. Choose between:
   - **Median** (default) - Shows typical price level, resistant to spikes
   - **Arithmetic Mean** - Shows actual mathematical average

**Important:** Both values are **always available** as sensor attributes, regardless of your choice! This ensures your automations continue to work if you change the display setting.

#### Using Both Values in Automations

Both `price_mean` and `price_median` are always available as attributes:

```yaml
# Example: Get both values regardless of display setting
sensor:
  - platform: template
    sensors:
      daily_price_analysis:
        friendly_name: "Daily Price Analysis"
        value_template: >
          {% set median = state_attr('sensor.tibber_home_average_price_today', 'price_median') %}
          {% set mean = state_attr('sensor.tibber_home_average_price_today', 'price_mean') %}
          {% set current = states('sensor.tibber_home_current_interval_price') | float %}

          {% if current < median %}
            Below typical ({{ ((1 - current/median) * 100) | round(1) }}% cheaper)
          {% elif current < mean %}
            Typical price range
          {% else %}
            Above average ({{ ((current/mean - 1) * 100) | round(1) }}% more expensive)
          {% endif %}
```

#### Practical Examples

**Example 1: Smart dishwasher control**

Run dishwasher only when price is significantly below the daily typical level:

```yaml
automation:
  - alias: "Start Dishwasher When Cheap"
    trigger:
      - platform: state
        entity_id: binary_sensor.tibber_home_best_price_period
        to: "on"
    condition:
      # Only if current price is at least 20% below typical (median)
      - condition: template
        value_template: >
          {% set current = states('sensor.tibber_home_current_interval_price') | float %}
          {% set median = state_attr('sensor.tibber_home_average_price_today', 'price_median') | float %}
          {{ current < (median * 0.8) }}
    action:
      - service: switch.turn_on
        entity_id: switch.dishwasher
```

**Example 2: Cost-aware heating control**

Use mean for actual cost calculations:

```yaml
automation:
  - alias: "Heating Budget Control"
    trigger:
      - platform: time
        at: "06:00:00"
    action:
      # Calculate expected daily heating cost
      - variables:
          mean_price: "{{ state_attr('sensor.tibber_home_average_price_today', 'price_mean') | float }}"
          heating_kwh_per_day: 15  # Estimated consumption
          daily_cost: "{{ (mean_price * heating_kwh_per_day / 100) | round(2) }}"
      - service: notify.mobile_app
        data:
          title: "Heating Cost Estimate"
          message: "Expected cost today: €{{ daily_cost }} (avg price: {{ mean_price }} ct/kWh)"
```

**Example 3: Smart charging based on rolling average**

Use trailing average to understand recent price trends:

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
          {% set current = states('sensor.tibber_home_current_interval_price') | float %}
          {% set trailing_avg = state_attr('sensor.tibber_home_trailing_price_average', 'price_median') | float %}
          {{ current < (trailing_avg * 0.9) }}
      # And battery < 80%
      - condition: numeric_state
        entity_id: sensor.ev_battery_level
        below: 80
    action:
      - service: switch.turn_on
        entity_id: switch.ev_charger
```

#### Key Attributes

All average sensors provide these attributes:

| Attribute | Description | Example |
|-----------|-------------|---------|
| `price_mean` | Arithmetic mean (always available) | 25.3 ct/kWh |
| `price_median` | Median value (always available) | 22.1 ct/kWh |
| `interval_count` | Number of intervals included | 96 |
| `timestamp` | Reference time for calculation | 2025-12-18T00:00:00+01:00 |

**Note:** The `price_mean` and `price_median` attributes are **always present** regardless of which value you configured for display. This ensures automation compatibility when changing the display setting.

#### When to Use Which Value

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



## Statistical Sensors

Coming soon...

## Rating Sensors

Coming soon...

## Diagnostic Sensors

### Chart Metadata

**Entity ID:** `sensor.tibber_home_NAME_chart_metadata`

> **✨ New Feature**: This sensor provides dynamic chart configuration metadata for optimal visualization. Perfect for use with the `get_apexcharts_yaml` action!

This diagnostic sensor provides essential chart configuration values as sensor attributes, enabling dynamic Y-axis scaling and optimal chart appearance in rolling window modes.

**Key Features:**

-   **Dynamic Y-Axis Bounds**: Automatically calculates optimal `yaxis_min` and `yaxis_max` for your price data
-   **Automatic Updates**: Refreshes when price data changes (coordinator updates)
-   **Lightweight**: Metadata-only mode (no data processing) for fast response
-   **State Indicator**: Shows `pending` (initialization), `ready` (data available), or `error` (service call failed)

**Attributes:**

-   **`timestamp`**: When the metadata was last fetched
-   **`yaxis_min`**: Suggested minimum value for Y-axis (optimal scaling)
-   **`yaxis_max`**: Suggested maximum value for Y-axis (optimal scaling)
-   **`currency`**: Currency code (e.g., "EUR", "NOK")
-   **`resolution`**: Interval duration in minutes (usually 15)
-   **`error`**: Error message if service call failed

**Usage:**

The `tibber_prices.get_apexcharts_yaml` action **automatically uses this sensor** for dynamic Y-axis scaling in `rolling_window` and `rolling_window_autozoom` modes! No manual configuration needed - just enable the action's result with `config-template-card` and the sensor provides optimal Y-axis bounds automatically.

See the **[Chart Examples Guide](chart-examples.md)** for practical examples!

---

### Chart Data Export

**Entity ID:** `sensor.tibber_home_NAME_chart_data_export`
**Default State:** Disabled (must be manually enabled)

> **⚠️ Legacy Feature**: This sensor is maintained for backward compatibility. For new integrations, use the **`tibber_prices.get_chartdata`** service instead, which offers more flexibility and better performance.

This diagnostic sensor provides cached chart-friendly price data that can be consumed by chart cards (ApexCharts, custom cards, etc.).

**Key Features:**

-   **Configurable via Options Flow**: Service parameters can be configured through the integration's options menu (Step 7 of 7)
-   **Automatic Updates**: Data refreshes on coordinator updates (every 15 minutes)
-   **Attribute-Based Output**: Chart data is stored in sensor attributes for easy access
-   **State Indicator**: Shows `pending` (before first call), `ready` (data available), or `error` (service call failed)

**Important Notes:**

-   ⚠️ Disabled by default - must be manually enabled in entity settings
-   ⚠️ Consider using the service instead for better control and flexibility
-   ⚠️ Configuration updates require HA restart

**Attributes:**

The sensor exposes chart data with metadata in attributes:

-   **`timestamp`**: When the data was last fetched
-   **`error`**: Error message if service call failed
-   **`data`** (or custom name): Array of price data points in configured format

**Configuration:**

To configure the sensor's output format:

1. Go to **Settings → Devices & Services → Tibber Prices**
2. Click **Configure** on your Tibber home
3. Navigate through the options wizard to **Step 7: Chart Data Export Settings**
4. Configure output format, filters, field names, and other options
5. Save and restart Home Assistant

**Available Settings:**

See the `tibber_prices.get_chartdata` service documentation below for a complete list of available parameters. All service parameters can be configured through the options flow.

**Example Usage:**

```yaml
# ApexCharts card consuming the sensor
type: custom:apexcharts-card
series:
    - entity: sensor.tibber_home_chart_data_export
      data_generator: |
          return entity.attributes.data;
```

**Migration Path:**

If you're currently using this sensor, consider migrating to the service:

```yaml
# Old approach (sensor)
- service: apexcharts_card.update
  data:
      entity: sensor.tibber_home_chart_data_export

# New approach (service)
- service: tibber_prices.get_chartdata
  data:
      entry_id: YOUR_ENTRY_ID
      day: ["today", "tomorrow"]
      output_format: array_of_objects
  response_variable: chart_data
```
