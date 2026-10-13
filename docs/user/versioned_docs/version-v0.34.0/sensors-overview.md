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

> **⚠️ Legacy Feature**: Other integrations and cards should no longer read price data from entity attributes. Use the **`tibber_prices.get_chartdata`** action instead: it returns data on demand, offers more flexibility and avoids keeping a large list in the state machine that is rewritten every 15 minutes. This sensor stays available for consumers that can only read sensor attributes, for example [tibber-graph](#use-with-tibber-graph). If you use such a project, consider asking its author to support the action.

This diagnostic sensor provides cached chart-friendly price data that can be consumed by chart cards (ApexCharts, custom cards, etc.).

**Key Features:**

-   **Configurable via `configuration.yaml`**: Action parameters are set in the optional `chart_export` block (see below). Without it, sensible defaults apply
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
-   **`currency`**: Currency code of your home (for example `EUR`)
-   **`data`** (or custom name): Array of price data points in configured format

**Configuration:**

The sensor works without any configuration: it exports today and tomorrow (or yesterday and today while tomorrow's prices are not published yet) as `data`, with `start_time` and `price_per_kwh` per quarter-hour interval. To change the output, add a `chart_export` block to your `configuration.yaml` and restart Home Assistant:

```yaml
tibber_prices:
    chart_export:
        day: [today, tomorrow]
        resolution: hourly
        data_key: prices
```

See the `tibber_prices.get_chartdata` action documentation for the available parameters.

**Example Usage:**

<details>
<summary>Show YAML: Example Usage</summary>

```yaml
# ApexCharts card consuming the sensor
type: custom:apexcharts-card
series:
    - entity: sensor.<home_name>_chart_data_export
      data_generator: |
          return entity.attributes.data;
```

</details>

#### Use with tibber-graph

[tibber-graph](https://github.com/stefanes/tibber-graph) can render prices from any sensor that exposes a list of `start_time` and `price_per_kwh` in its attributes. This sensor already uses exactly that format, so no template sensor is needed and no extra API calls are made:

1. Enable `sensor.<home_name>_chart_data_export` (**Settings → Devices & Services → Tibber Prices → your home → Entities**, then show disabled entities).
2. In tibber-graph, use that entity as the price sensor, for example `price_entity_id: sensor.<home_name>_chart_data_export` in the `create_graph` or `set_data_source` action.

Leave `subunit_currency` at its default (`false`) so prices stay in the base currency per kWh (for example EUR/kWh), which is what tibber-graph expects.

**Migration Path:**

If you're currently using this sensor and the consumer can call actions, consider migrating to the action:

<details>
<summary>Show YAML: Chart Data Export</summary>

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

</details>
