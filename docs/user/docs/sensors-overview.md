# Sensors Overview

> **Tip:** Many sensors have dynamic icons and colors! See the **[Dynamic Icons Guide](dynamic-icons.md)** and **[Dynamic Icon Colors Guide](icon-colors.md)** to enhance your dashboards.

:::tip Entity ID tip
`<home_name>` is a placeholder for your Tibber home display name in Home Assistant. Entity IDs are derived from the displayed name (localized), so the exact slug may differ. **Can't find a sensor?** Use the **[Entity Reference (All Languages)](sensor-reference.md)** to search by name in your language.
:::

The integration provides **100+ sensors** organized by purpose. This page gives a quick overview and links to detailed guides for each sensor family.

| Sensor Family | Purpose | Guide |
|---|---|---|
| **Binary Sensors** | Period on/off indicators | [below](#binary-sensors) |
| **Core Price** | Current, next, previous interval prices | [below](#core-price-sensors) |
| **Average & Statistics** | Daily averages, rolling averages, median/mean | [Average Sensors](sensors-average.md) |
| **Ratings & Levels** | Price classification (3-level ratings, 5-level API levels) | [Ratings & Levels](sensors-ratings-levels.md) |
| **Min/Max** | Daily and rolling 24h extremes | [below](#minmax-sensors) |
| **Volatility** | Price fluctuation analysis | [Volatility Sensors](sensors-volatility.md) |
| **Trends** | Price outlook, trajectory, direction | [Trend Sensors](sensors-trends.md) |
| **Timing** | Period countdown, progress, duration | [Timing Sensors](sensors-timing.md) |
| **Energy & Tax** | Spot price and tax breakdown | [Energy & Tax](sensors-energy-tax.md) |
| **Diagnostic** | Chart metadata, data export | [below](#diagnostic-sensors) |

---

## Binary Sensors

### Best Price Period & Peak Price Period

These binary sensors indicate when you're in a detected best or peak price period. See the **[Period Calculation Guide](period-calculation.md)** for a detailed explanation of how these periods are calculated and configured.

**Quick overview:**

-   <EntityRef id="best_price_period">Best Price Period</EntityRef>: Turns ON during periods with significantly lower prices than the daily average
-   <EntityRef id="peak_price_period">Peak Price Period</EntityRef>: Turns ON during periods with significantly higher prices than the daily average

Both sensors include rich attributes with period details, intervals, relaxation status, and more.

## Core Price Sensors

The integration provides price sensors for the **current**, **next**, and **previous** 15-minute interval. Each exposes the total price as sensor state, with `energy_price` and `tax` available as attributes (see [Energy & Tax Breakdown](sensors-energy-tax.md)).

**Next N Hours Average** sensors (`next_avg_1h`–`next_avg_12h`) provide future price forecasts for 1h, 2h, 3h, 4h, 5h, 6h, 8h, and 12h windows.

For detailed average sensor behavior (median vs mean, configuration, automation examples), see **[Average & Statistics Sensors](sensors-average.md)**.

## Min/Max Sensors

These sensors show the lowest and highest prices for calendar days and rolling windows:

### Daily Min/Max

| Sensor | Description |
|--------|-------------|
| <EntityRef id="lowest_price_today">Today's Lowest Price</EntityRef> | Minimum price today (00:00–23:59) |
| <EntityRef id="highest_price_today">Today's Highest Price</EntityRef> | Maximum price today (00:00–23:59) |
| <EntityRef id="lowest_price_tomorrow">Tomorrow's Lowest Price</EntityRef> | Minimum price tomorrow |
| <EntityRef id="highest_price_tomorrow">Tomorrow's Highest Price</EntityRef> | Maximum price tomorrow |

### 24-Hour Rolling Min/Max

| Sensor | Description |
|--------|-------------|
| <EntityRef id="trailing_price_min">Trailing Price Min</EntityRef> | Lowest price in the last 24 hours |
| <EntityRef id="trailing_price_max">Trailing Price Max</EntityRef> | Highest price in the last 24 hours |
| <EntityRef id="leading_price_min">Leading Price Min</EntityRef> | Lowest price in the next 24 hours |
| <EntityRef id="leading_price_max">Leading Price Max</EntityRef> | Highest price in the next 24 hours |

### Key Attributes

All min/max sensors include:

| Attribute | Description |
|-----------|-------------|
| `timestamp` | When the extreme price occurs/occurred |
| `price_diff_from_daily_min` | Difference from daily minimum |
| `price_diff_from_daily_min_%` | Percentage difference |

## Diagnostic Sensors

### Chart Metadata

**Entity ID:** `sensor.<home_name>_chart_metadata`

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

**Entity ID:** `sensor.<home_name>_chart_data_export`
**Default State:** Disabled (must be manually enabled)

> **⚠️ Legacy Feature**: This sensor is maintained for backward compatibility. For new integrations, use the **`tibber_prices.get_chartdata`** action instead, which offers more flexibility and better performance.

This diagnostic sensor provides cached chart-friendly price data that can be consumed by chart cards (ApexCharts, custom cards, etc.).

**Key Features:**

-   **Configurable via Options Flow**: Service parameters can be configured through the integration's options menu (Step 7 of 7)
-   **Automatic Updates**: Data refreshes on coordinator updates (every 15 minutes)
-   **Attribute-Based Output**: Chart data is stored in sensor attributes for easy access
-   **State Indicator**: Shows `pending` (before first call), `ready` (data available), or `error` (service call failed)

**Important Notes:**

-   ⚠️ Disabled by default - must be manually enabled in entity settings
-   ⚠️ Consider using the action instead for better control and flexibility
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

See the `tibber_prices.get_chartdata` action documentation for a complete list of available parameters. All action parameters can be configured through the options flow.

**Example Usage:**

```yaml
# ApexCharts card consuming the sensor
type: custom:apexcharts-card
series:
    - entity: sensor.<home_name>_chart_data_export
      data_generator: |
          return entity.attributes.data;
```

**Migration Path:**

If you're currently using this sensor, consider migrating to the action:

```yaml
# Old approach (sensor)
- service: apexcharts_card.update
  data:
      entity: sensor.<home_name>_chart_data_export

# New approach (action)
- service: tibber_prices.get_chartdata
  data:
      entry_id: YOUR_CONFIG_ENTRY_ID
      day: ["today", "tomorrow"]
      output_format: array_of_objects
  response_variable: chart_data
```
