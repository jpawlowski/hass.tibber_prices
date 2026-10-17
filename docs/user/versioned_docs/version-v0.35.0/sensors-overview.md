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

**Forecast-style outlook:** **Current Electricity Price** (`current_interval_price`) also carries the coming hours the way a weather forecast shows them:

- `outlook_hours`: 48 clock hours: up to the end of the known prices (at most the end of tomorrow), at least one hour back, and before that as much of the past as fills the 48 (yesterday's hours while tomorrow's prices aren't out).
- `outlook_day_parts`: parts of the day covering what `outlook_hours` does (back to yesterday until tomorrow's prices are out, whole: a night that led into yesterday from 22:00 the day before; a part whose beginning isn't known is left out), as far as prices are known: morning (06–09), day (09–17), evening (17–22) and night (22–06, across midnight). The part where the known prices end is included as far as it's known (at least an hour) with `complete: false`; its `end` is where the prices end and its numbers cover only that stretch.
- `outlook_days`: today and, once its prices are complete, tomorrow, with `date`, the day's `volatility` (same thresholds as the volatility sensors), `price_min_at` / `price_max_at` (when the day's lowest and highest price occur) and `price_reference` (the day's median or average, as set for the ⌀ sensors).
- `outlook_day_part_hours`: when each part of the day begins and ends, e.g. `night: [22, 6]`.
- `outlook_yesterday`: yesterday's `price_mean`, `price_median` and `price_reference`, for the dashed line over yesterday's last hour after midnight.
- `outlook_quarters`: every quarter-hour price from where `outlook_hours` and `outlook_day_parts` begin (at the latest 22:00 last night, where a night still running began) to the end of the known prices, compactly: `start`, `minutes` (15), then `prices` and `levels`, one entry per quarter hour (`null` where a price is missing). The forecast card zooms into an hour, a part of the day or a day with it.
- `outlook_past_periods`: the best and peak price periods (`best_price`, `peak_price`, each a list of `start` and `end`) that ended before today, as far back as `outlook_hours` and `outlook_day_parts` reach. The period sensors list only today's and tomorrow's, so this lets cards mark yesterday's periods too.

Each entry has `start`, `end`, `price_mean`, `price_median`, `price_min` and `price_max` (in your display unit) and the aggregated `level`; day parts also have `part`. The spread between lowest and highest price tells whether timing within a block matters: a night from 0.30 to 0.35 needs no planning, a day from 0.30 to 1.80 does. The [dashboard from `get_dashboard_yaml`](dashboard-examples.md#complete-dashboard-as-a-starting-point) shows them under **Course of the day**. These lists aren't stored in the recorder history.

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

> **⚠️ Legacy Feature**: For chart data, use the **`tibber_prices.get_chartdata`** action instead of this sensor. A configurable price list is a poor fit for an attribute: it can grow large, is rewritten every 15 minutes and is pushed to every open dashboard, even where nobody looks at it. The action returns data on demand, in exactly the range, resolution and unit you ask for. Small summaries with a fixed shape are a different case: the outlook attributes on the current price sensor, which the bundled cards read, stay small and are not recorded. This sensor stays available for consumers that can only read sensor attributes, for example [tibber-graph](chart-third-party.md). If you use such a project, consider asking its author to support the action.

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
          return entity.attributes.data.map((i) => [new Date(i.start_time).getTime(), i.price_per_kwh]);
```

</details>

<span id="use-with-tibber-graph"></span>

#### Use with third-party cards and integrations

Projects like [tibber-graph](https://github.com/stefanes/tibber-graph) can read this sensor directly, with no template sensor and no extra API calls. See **[Third-Party Cards & Integrations](chart-third-party.md)** for setup, format options and a list of known projects.

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
