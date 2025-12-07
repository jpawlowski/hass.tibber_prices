---
comments: false
---

# Sensors

> **Note:** This guide is under construction. For now, please refer to the [main README](https://github.com/jpawlowski/hass.tibber_prices/blob/v0.20.0/README.md) for available sensors.

> **Tip:** Many sensors have dynamic icons and colors! See the **[Dynamic Icons Guide](dynamic-icons.md)** and **[Dynamic Icon Colors Guide](icon-colors.md)** to enhance your dashboards.

## Binary Sensors

### Best Price Period & Peak Price Period

These binary sensors indicate when you're in a detected best or peak price period. See the **[Period Calculation Guide](period-calculation.md)** for a detailed explanation of how these periods are calculated and configured.

**Quick overview:**

-   **Best Price Period**: Turns ON during periods with significantly lower prices than the daily average
-   **Peak Price Period**: Turns ON during periods with significantly higher prices than the daily average

Both sensors include rich attributes with period details, intervals, relaxation status, and more.

## Core Price Sensors

Coming soon...

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
