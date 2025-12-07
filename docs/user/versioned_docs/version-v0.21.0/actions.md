# Actions (Services)

Home Assistant now surfaces these backend service endpoints as **Actions** in the UI (for example, Developer Tools → Actions or the Action editor inside dashboards). Behind the scenes they are still Home Assistant services that use the `service:` key, but this guide uses the word “action” whenever we refer to the user interface.

You can still call them from automations, scripts, and dashboards the same way as before (`service: tibber_prices.get_chartdata`, etc.), just remember that the frontend officially lists them as actions.

## Available Actions

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
-   **When tomorrow data available** (typically after ~13:00): Returns today + tomorrow
-   **When tomorrow data not available**: Returns yesterday + today

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

For detailed parameter descriptions, open **Developer Tools → Actions** (the UI label) and select `tibber_prices.get_chartdata`. The inline documentation is still stored in `services.yaml` because actions are backed by services.

---

### tibber_prices.get_apexcharts_yaml

> ⚠️ **IMPORTANT:** This action generates a **basic example configuration** as a starting point, NOT a complete solution for all ApexCharts features.
>
> This integration is primarily a **data provider**. The generated YAML demonstrates how to use the `get_chartdata` action to fetch price data. Due to the segmented nature of our data (different time periods per series) and the use of Home Assistant's service API instead of entity attributes, many advanced ApexCharts features (like `in_header`, certain transformations) are **not compatible** or require manual customization.
>
> **You are welcome to customize** the generated YAML for your specific needs, but comprehensive ApexCharts configuration support is beyond the scope of this integration. Community contributions with improved configurations are always appreciated!
>
> **For custom solutions:** Use the `get_chartdata` action directly to build your own charts with full control over the data format and visualization.

**Purpose:** Generates a basic ApexCharts card YAML configuration example for visualizing electricity prices with automatic color-coding by price level.

**Prerequisites:**
- [ApexCharts Card](https://github.com/RomRider/apexcharts-card) (required for all configurations)
- [Config Template Card](https://github.com/iantrich/config-template-card) (required only for rolling window modes - enables dynamic Y-axis scaling)

**✨ Key Features:**

- **Automatic Color-Coded Series**: Separate series for each price level (VERY_CHEAP, CHEAP, NORMAL, EXPENSIVE, VERY_EXPENSIVE) or rating (LOW, NORMAL, HIGH)
- **Dynamic Y-Axis Scaling**: Rolling window modes automatically use `chart_metadata` sensor for optimal Y-axis bounds
- **Best Price Period Highlights**: Optional vertical bands showing detected best price periods
- **Translated Labels**: Automatically uses your Home Assistant language setting
- **Clean Gap Visualization**: Proper NULL insertion for missing data segments

**Quick Example:**

```yaml
service: tibber_prices.get_apexcharts_yaml
data:
    entry_id: YOUR_ENTRY_ID
    day: today  # Optional: yesterday, today, tomorrow, rolling_window, rolling_window_autozoom
    level_type: rating_level  # or "level" for 5-level classification
    highlight_best_price: true  # Show best price period overlays
response_variable: apexcharts_config
```

**Day Parameter Options:**

- **Fixed days** (`yesterday`, `today`, `tomorrow`): Static 24-hour views, no additional dependencies
- **Rolling Window** (default when omitted or `rolling_window`): Dynamic 48-hour window that automatically shifts between yesterday+today and today+tomorrow based on data availability
  - **✨ Includes dynamic Y-axis scaling** via `chart_metadata` sensor
- **Rolling Window (Auto-Zoom)** (`rolling_window_autozoom`): Same as rolling window, but additionally zooms in progressively (2h lookback + remaining time until midnight, graph span decreases every 15 minutes)
  - **✨ Includes dynamic Y-axis scaling** via `chart_metadata` sensor

**Dynamic Y-Axis Scaling (Rolling Window Modes):**

Rolling window configurations automatically integrate with the `chart_metadata` sensor for optimal chart appearance:

- **Automatic bounds**: Y-axis min/max adjust to data range
- **No manual configuration**: Works out of the box if sensor is enabled
- **Fallback behavior**: If sensor is disabled, uses ApexCharts auto-scaling
- **Real-time updates**: Y-axis adapts when price data changes

**Example: Today's Prices (Static View)**

```yaml
service: tibber_prices.get_apexcharts_yaml
data:
    entry_id: YOUR_ENTRY_ID
    day: today
    level_type: rating_level
response_variable: config

# Use in dashboard:
type: custom:apexcharts-card
# ... paste generated config
```

**Example: Rolling 48h Window (Dynamic View)**

```yaml
service: tibber_prices.get_apexcharts_yaml
data:
    entry_id: YOUR_ENTRY_ID
    # Omit 'day' for rolling window (or use 'rolling_window')
    level_type: level  # 5-level classification
    highlight_best_price: true
response_variable: config

# Use in dashboard:
type: custom:config-template-card
entities:
    - sensor.tibber_home_tomorrow_data
    - sensor.tibber_home_chart_metadata  # For dynamic Y-axis
card:
    # ... paste generated config
```

**Screenshots:**

_Screenshots coming soon for all 4 modes: today, tomorrow, rolling_window, rolling_window_autozoom_

**Level Type Options:**

- **`rating_level`** (default): 3 series (LOW, NORMAL, HIGH) - based on your personal thresholds
- **`level`**: 5 series (VERY_CHEAP, CHEAP, NORMAL, EXPENSIVE, VERY_EXPENSIVE) - absolute price ranges

**Best Price Period Highlights:**

When `highlight_best_price: true`:
- Vertical bands overlay the chart showing detected best price periods
- Tooltip shows "Best Price Period" label when hovering over highlighted areas
- Only appears when best price periods are configured and detected

**Important Notes:**

- **Config Template Card** is only required for rolling window modes (enables dynamic Y-axis)
- Fixed day views (`today`, `tomorrow`, `yesterday`) work with ApexCharts Card alone
- Generated YAML is a starting point - customize colors, styling, features as needed
- All labels are automatically translated to your Home Assistant language

Use the response in Lovelace dashboards by copying the generated YAML.

**Documentation:** Refer to **Developer Tools → Actions** for descriptions of the fields exposed by this action.

---

### tibber_prices.refresh_user_data

**Purpose:** Forces an immediate refresh of user data (homes, subscriptions) from the Tibber API.

**Example:**

```yaml
service: tibber_prices.refresh_user_data
data:
    entry_id: YOUR_ENTRY_ID
```

**Note:** User data is cached for 24 hours. Trigger this action only when you need immediate updates (e.g., after changing Tibber subscriptions).

---

## Migration from Chart Data Export Sensor

If you're still using the `sensor.tibber_home_chart_data_export` sensor, consider migrating to the `tibber_prices.get_chartdata` action:

**Benefits:**

-   No HA restart required for configuration changes
-   More flexible filtering and formatting options
-   Better performance (on-demand instead of polling)
-   Future-proof (active development)

**Migration Steps:**

1. Note your current sensor configuration (Step 7 in Options Flow)
2. Create automation/script that calls `tibber_prices.get_chartdata` with the same parameters
3. Test the new approach
4. Disable the old sensor when satisfied
