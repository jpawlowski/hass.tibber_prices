# Services

This integration provides several services for advanced price data access and manipulation.

## Available Services

### tibber_prices.get_chartdata

**Purpose:** Returns electricity price data in chart-friendly formats for visualization and analysis.

**Key Features:**

-   **Flexible Output Formats**: Array of objects or array of arrays
-   **Time Range Selection**: Filter by day (yesterday, today, tomorrow)
-   **Price Filtering**: Filter by price level or rating
-   **Period Support**: Return best/peak price period summaries instead of intervals
-   **Resolution Control**: Interval (15-minute) or hourly aggregation
-   **Customizable Field Names**: Rename output fields to match your chart library
-   **Currency Control**: Major (EUR/NOK) or minor (ct/øre) units

**Basic Example:**

```yaml
service: tibber_prices.get_chartdata
data:
    entry_id: YOUR_ENTRY_ID
    day: ["today", "tomorrow"]
    output_format: array_of_objects
response_variable: chart_data
```

**Response Format:**

```json
{
    "data": [
        {
            "start_time": "2025-11-17T00:00:00+01:00",
            "price_per_kwh": 0.2534
        },
        {
            "start_time": "2025-11-17T00:15:00+01:00",
            "price_per_kwh": 0.2498
        }
    ]
}
```

**Common Parameters:**

| Parameter        | Description                                 | Default                 |
| ---------------- | ------------------------------------------- | ----------------------- |
| `entry_id`       | Integration entry ID (required)             | -                       |
| `day`            | Days to include: yesterday, today, tomorrow | `["today", "tomorrow"]` |
| `output_format`  | `array_of_objects` or `array_of_arrays`     | `array_of_objects`      |
| `resolution`     | `interval` (15-min) or `hourly`             | `interval`              |
| `minor_currency` | Return prices in ct/øre instead of EUR/NOK  | `false`                 |
| `round_decimals` | Decimal places (0-10)                       | 4 (major) or 2 (minor)  |

**Rolling Window Mode:**

Omit the `day` parameter to get a dynamic 48-hour rolling window that automatically adapts to data availability:

```yaml
service: tibber_prices.get_chartdata
data:
    entry_id: YOUR_ENTRY_ID
    # Omit 'day' for rolling window
    output_format: array_of_objects
response_variable: chart_data
```

**Behavior:**
- **When tomorrow data available** (typically after ~13:00): Returns today + tomorrow
- **When tomorrow data not available**: Returns yesterday + today

This is useful for charts that should always show a 48-hour window without manual day selection.

**Period Filter Example:**

Get best price periods as summaries instead of intervals:

```yaml
service: tibber_prices.get_chartdata
data:
    entry_id: YOUR_ENTRY_ID
    period_filter: best_price # or peak_price
    day: ["today", "tomorrow"]
    include_level: true
    include_rating_level: true
response_variable: periods
```

**Advanced Filtering:**

```yaml
service: tibber_prices.get_chartdata
data:
    entry_id: YOUR_ENTRY_ID
    level_filter: ["VERY_CHEAP", "CHEAP"] # Only cheap periods
    rating_level_filter: ["LOW"] # Only low-rated prices
    insert_nulls: segments # Add nulls at segment boundaries
```

**Complete Documentation:**

For detailed parameter descriptions, see the service definition in **Developer Tools → Services → tibber_prices.get_chartdata** or check the inline documentation in the integration's `services.yaml` file.

---

### tibber_prices.get_apexcharts_yaml

**Purpose:** Generates complete ApexCharts card YAML configuration for visualizing electricity prices.

**Prerequisites:**
- [ApexCharts Card](https://github.com/RomRider/apexcharts-card) (required for all configurations)
- [Config Template Card](https://github.com/iantrich/config-template-card) (required only for rolling window mode without `day` parameter)

**Quick Example:**

```yaml
service: tibber_prices.get_apexcharts_yaml
data:
    entry_id: YOUR_ENTRY_ID
    day: today  # Optional: omit for rolling 48h window (requires config-template-card)
response_variable: apexcharts_config
```

**Rolling Window Mode:** When omitting the `day` parameter, the service generates a dynamic 48-hour rolling window that automatically shows:
- Today + Tomorrow (when tomorrow data is available)
- Yesterday + Today (when tomorrow data is not yet available)

This mode requires the Config Template Card to dynamically adjust the time window based on data availability.

Use the response in Lovelace dashboards by copying the generated YAML.

**Documentation:** See Developer Tools → Services for parameter details.

---

### tibber_prices.refresh_user_data

**Purpose:** Forces an immediate refresh of user data (homes, subscriptions) from the Tibber API.

**Example:**

```yaml
service: tibber_prices.refresh_user_data
data:
    entry_id: YOUR_ENTRY_ID
```

**Note:** User data is cached for 24 hours. Use this service only when you need immediate updates (e.g., after changing Tibber subscriptions).

---

## Migration from Chart Data Export Sensor

If you're currently using the `sensor.tibber_home_chart_data_export` sensor, consider migrating to `tibber_prices.get_chartdata`:

**Benefits:**

-   No HA restart required for configuration changes
-   More flexible filtering and formatting options
-   Better performance (on-demand instead of polling)
-   Future-proof (active development)

**Migration Steps:**

1. Note your current sensor configuration (Step 7 in Options Flow)
2. Create automation/script using `tibber_prices.get_chartdata` with same parameters
3. Test the new approach
4. Disable the old sensor when satisfied
