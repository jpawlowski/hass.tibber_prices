# Tibber Price Information & Ratings

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
[![Project Maintenance][maintenance-shield]][user_profile]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

A Home Assistant integration that provides advanced price information and ratings from Tibber. This integration fetches **quarter-hourly** electricity prices, enriches them with statistical analysis, and provides smart indicators to help you optimize your energy consumption and save money.

![Tibber Price Information & Ratings](images/logo.png)

## 📖 Documentation

-   **[User Guide](docs/user/)** - Installation, configuration, and usage guides
    -   **[Period Calculation](docs/user/period-calculation.md)** - How Best/Peak Price periods are calculated
-   **[Developer Guide](docs/development/)** - Contributing, architecture, and release process
-   **[Changelog](https://github.com/jpawlowski/hass.tibber_prices/releases)** - Release history and notes

## ✨ Features

-   **Quarter-Hourly Price Data**: Access detailed 15-minute interval pricing (384 data points across 4 days: day before yesterday/yesterday/today/tomorrow)
-   **Current and Next Interval Prices**: Get real-time price data in both major currency (€, kr) and minor units (ct, øre)
-   **Multi-Currency Support**: Automatic detection and formatting for EUR, NOK, SEK, DKK, USD, and GBP
-   **Price Level Indicators**: Know when you're in a VERY_CHEAP, CHEAP, NORMAL, EXPENSIVE, or VERY_EXPENSIVE period
-   **Statistical Sensors**: Track lowest, highest, and average prices for the day
-   **Price Ratings**: Quarter-hourly ratings comparing current prices to 24-hour trailing averages
-   **Smart Indicators**: Binary sensors to detect peak hours and best price hours for automations
-   **Intelligent Caching**: Minimizes API calls while ensuring data freshness across Home Assistant restarts
-   **Custom Actions** (backend services): API endpoints for advanced integrations (ApexCharts support included)
-   **Diagnostic Sensors**: Monitor data freshness and availability
-   **Reliable API Usage**: Uses only official Tibber [`priceInfo`](https://developer.tibber.com/docs/reference#priceinfo) and [`priceInfoRange`](https://developer.tibber.com/docs/reference#subscription) endpoints - no legacy APIs. Price ratings and statistics are calculated locally for maximum reliability and future-proofing.

## 🚀 Quick Start

### Step 1: Install the Integration

**Prerequisites:** This integration requires [HACS](https://hacs.xyz/) (Home Assistant Community Store) to be installed.

Click the button below to open the integration directly in HACS:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jpawlowski&repository=hass.tibber_prices&category=integration)

Then:

1. Click "Download" to install the integration
2. **Restart Home Assistant** (required after installation)

> **Note:** The My Home Assistant redirect will first take you to a landing page. Click the button there to open your Home Assistant instance. If the repository is not yet in the HACS default store, HACS will ask if you want to add it as a custom repository.

### Step 2: Add and Configure the Integration

**Important:** You must have installed the integration first (see Step 1) and restarted Home Assistant!

#### Option 1: One-Click Setup (Quick)

Click the button below to open the configuration dialog:

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=tibber_prices)

This will guide you through:

1. Enter your Tibber API token ([get one here](https://developer.tibber.com/settings/access-token))
2. Select your Tibber home
3. Configure price thresholds (optional)

#### Option 2: Manual Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **"+ Add Integration"**
3. Search for "Tibber Price Information & Ratings"
4. Follow the configuration steps (same as Option 1)

### Step 3: Start Using!

-   30+ sensors are now available (key sensors enabled by default)
-   Configure additional sensors in **Settings** → **Devices & Services** → **Tibber Price Information & Ratings** → **Entities**
-   Use sensors in automations, dashboards, and scripts

📖 **[Full Installation Guide →](docs/user/installation.md)**

## 📊 Available Entities

The integration provides **30+ sensors** across different categories. Key sensors are enabled by default, while advanced sensors can be enabled as needed.

> **Rich Sensor Attributes**: All sensors include extensive attributes with timestamps, context data, and detailed explanations. Enable **Extended Descriptions** in the integration options to add `long_description` and `usage_tips` attributes to every sensor, providing in-context documentation directly in Home Assistant's UI.

### Core Price Sensors (Enabled by Default)

| Entity                     | Description                                       |
| -------------------------- | ------------------------------------------------- |
| Current Electricity Price  | Current 15-minute interval price                  |
| Next Interval Price        | Price for the next 15-minute interval             |
| Current Hour Average Price | Average of current hour's 4 intervals             |
| Next Hour Average Price    | Average of next hour's 4 intervals                |
| Current Price Level        | API classification (VERY_CHEAP to VERY_EXPENSIVE) |
| Next Interval Price Level  | Price level for next interval                     |
| Current Hour Price Level   | Price level for current hour average              |
| Next Hour Price Level      | Price level for next hour average                 |

### Statistical Sensors (Enabled by Default)

| Entity                    | Description                                 |
| ------------------------- | ------------------------------------------- |
| Today's Lowest Price      | Minimum price for today                     |
| Today's Highest Price     | Maximum price for today                     |
| Today's Average Price     | Mean price across today's intervals         |
| Tomorrow's Lowest Price   | Minimum price for tomorrow (when available) |
| Tomorrow's Highest Price  | Maximum price for tomorrow (when available) |
| Tomorrow's Average Price  | Mean price for tomorrow (when available)    |
| Leading 24h Average Price | Average of next 24 hours from now           |
| Leading 24h Minimum Price | Lowest price in next 24 hours               |
| Leading 24h Maximum Price | Highest price in next 24 hours              |

### Price Rating Sensors (Enabled by Default)

| Entity                     | Description                                               |
| -------------------------- | --------------------------------------------------------- |
| Current Price Rating       | % difference from 24h trailing average (current interval) |
| Next Interval Price Rating | % difference from 24h trailing average (next interval)    |
| Current Hour Price Rating  | % difference for current hour average                     |
| Next Hour Price Rating     | % difference for next hour average                        |

> **How ratings work**: Compares each interval to the average of the previous 96 intervals (24 hours). Positive values mean prices are above average, negative means below average.

### Binary Sensors (Enabled by Default)

| Entity                    | Description                                                                               |
| ------------------------- | ----------------------------------------------------------------------------------------- |
| Peak Price Period         | ON when in a detected peak price period ([how it works](docs/user/period-calculation.md)) |
| Best Price Period         | ON when in a detected best price period ([how it works](docs/user/period-calculation.md)) |
| Tibber API Connection     | Connection status to Tibber API                                                           |
| Tomorrow's Data Available | Whether tomorrow's price data is available                                                |

### Diagnostic Sensors (Enabled by Default)

| Entity          | Description                                |
| --------------- | ------------------------------------------ |
| Data Expiration | Timestamp when current data expires        |
| Price Forecast  | Formatted list of upcoming price intervals |

### Additional Sensors (Disabled by Default)

The following sensors are available but disabled by default. Enable them in `Settings > Devices & Services > Tibber Price Information & Ratings > Entities`:

-   **Previous Interval Price** & **Previous Interval Price Level**: Historical data for the last 15-minute interval
-   **Previous Interval Price Rating**: Rating for the previous interval
-   **Trailing 24h Average Price**: Average of the past 24 hours from now
-   **Trailing 24h Minimum/Maximum Price**: Min/max in the past 24 hours

> **Note**: All monetary sensors use minor currency units (ct/kWh, øre/kWh, ¢/kWh, p/kWh) automatically based on your Tibber account's currency. Supported: EUR, NOK, SEK, DKK, USD, GBP.

## Automation Examples

> **Note:** See the [full automation examples guide](docs/user/automation-examples.md) for more advanced recipes.

### Run Appliances During Cheap Hours

Use the `binary_sensor.tibber_best_price_period` to automatically start appliances during detected best price periods:

```yaml
automation:
    - alias: "Run Dishwasher During Cheap Hours"
      trigger:
          - platform: state
            entity_id: binary_sensor.tibber_best_price_period
            to: "on"
      condition:
          - condition: time
            after: "21:00:00"
            before: "06:00:00"
      action:
          - service: switch.turn_on
            target:
                entity_id: switch.dishwasher
```

> **Learn more:** The [period calculation guide](docs/user/period-calculation.md) explains how Best/Peak Price periods are identified and how you can configure filters (flexibility, minimum distance from average, price level filters with gap tolerance).

### Notify on Extremely High Prices

Get notified when prices reach the VERY_EXPENSIVE level:

```yaml
automation:
    - alias: "Notify on Very Expensive Electricity"
      trigger:
          - platform: state
            entity_id: sensor.tibber_current_interval_price_level
            to: "VERY_EXPENSIVE"
      action:
          - service: notify.mobile_app
            data:
                title: "⚠️ High Electricity Prices"
                message: "Current electricity price is in the VERY EXPENSIVE range. Consider reducing consumption."
```

### Temperature Control Based on Price Ratings

Adjust heating/cooling when current prices are significantly above the 24h average:

```yaml
automation:
    - alias: "Reduce Heating During High Price Ratings"
      trigger:
          - platform: numeric_state
            entity_id: sensor.tibber_current_interval_price_rating
            above: 20 # More than 20% above 24h average
      action:
          - service: climate.set_temperature
            target:
                entity_id: climate.living_room
            data:
                temperature: 19 # Lower target temperature
```

### Smart EV Charging Based on Tomorrow's Prices

Start charging when tomorrow's prices drop below today's average:

```yaml
automation:
    - alias: "Smart EV Charging"
      trigger:
          - platform: state
            entity_id: binary_sensor.tibber_best_price_interval
            to: "on"
      condition:
          - condition: numeric_state
            entity_id: sensor.tibber_current_interval_price_rating
            below: -15 # At least 15% below average
          - condition: numeric_state
            entity_id: sensor.ev_battery_level
            below: 80
      action:
          - service: switch.turn_on
            target:
                entity_id: switch.ev_charger
```

## Troubleshooting

### No data appearing

1. Check your API token is valid at [developer.tibber.com](https://developer.tibber.com/settings/access-token)
2. Verify you have an active Tibber subscription
3. Check the Home Assistant logs for detailed error messages (`Settings > System > Logs`)
4. Restart the integration: `Settings > Devices & Services > Tibber Price Information & Ratings > ⋮ > Reload`

### Missing tomorrow's price data

-   Tomorrow's price data typically becomes available between **13:00 and 15:00** each day (Nordic time)
-   The integration automatically checks more frequently during this window
-   Check `binary_sensor.tibber_tomorrows_data_available` to see if data is available
-   If data is unavailable after 15:00, verify it's available in the Tibber app first

### Prices not updating at quarter-hour boundaries

-   Entities automatically refresh at 00/15/30/45-minute marks without waiting for API polls
-   Check `sensor.tibber_data_expiration` to verify data freshness
-   The integration caches data intelligently and survives Home Assistant restarts

### Currency or units showing incorrectly

-   Currency is automatically detected from your Tibber account
-   The integration supports EUR, NOK, SEK, DKK, USD, and GBP with appropriate minor units
-   Enable/disable major vs. minor unit sensors in `Settings > Devices & Services > Tibber Price Information & Ratings > Entities`

## Advanced Features

### Sensor Attributes

Every sensor includes rich attributes beyond just the state value. These attributes provide context, timestamps, and additional data useful for automations and templates.

**Standard attributes available on most sensors:**

-   `timestamp` - ISO 8601 timestamp for the data point
-   `description` - Brief explanation of what the sensor represents
-   `level_id` and `level_value` - For price level sensors (e.g., `VERY_CHEAP` = -2)

**Extended descriptions** (enable in integration options):

-   `long_description` - Detailed explanation of the sensor's purpose
-   `usage_tips` - Practical suggestions for using the sensor in automations

**Example - Current Price sensor attributes:**

```yaml
timestamp: "2025-11-03T14:15:00+01:00"
description: "The current electricity price per kWh"
long_description: "Shows the current price per kWh from your Tibber subscription"
usage_tips: "Use this to track prices or to create automations that run when electricity is cheap"
```

**Example template using attributes:**

```yaml
template:
    - sensor:
          - name: "Price Status"
            state: >
                {% set price = states('sensor.tibber_current_electricity_price') | float %}
                {% set timestamp = state_attr('sensor.tibber_current_electricity_price', 'timestamp') %}
                Price at {{ timestamp }}: {{ price }} ct/kWh
```

📖 **[View all sensors and attributes →](docs/user/sensors.md)**

### Custom Actions

The integration provides custom actions (they still appear as services under the hood) for advanced use cases. These actions show up in Home Assistant under **Developer Tools → Actions**.

-   `tibber_prices.get_chartdata` - Get price data in chart-friendly formats for any visualization card
-   `tibber_prices.get_apexcharts_yaml` - Generate complete ApexCharts configurations
-   `tibber_prices.refresh_user_data` - Manually refresh account information

📖 **[Action documentation and examples →](docs/user/actions.md)**

### ApexCharts Integration

The integration includes built-in support for creating beautiful price visualization cards. Use the `get_apexcharts_yaml` action to generate card configurations automatically.

📖 **[ApexCharts examples →](docs/user/automation-examples.md#apexcharts-cards)**

## 🤝 Contributing

Contributions are welcome! Please read the [Contributing Guidelines](CONTRIBUTING.md) and [Developer Guide](docs/development/) before submitting pull requests.

### For Contributors

-   **[Developer Setup](docs/development/setup.md)** - Get started with DevContainer
-   **[Architecture Guide](docs/development/architecture.md)** - Understand the codebase
-   **[Release Management](docs/development/release-management.md)** - Release process and versioning

## 🤖 Development Note

This integration is developed with extensive AI assistance (GitHub Copilot, Claude, and other AI tools). While AI enables rapid development and helps implement complex features, it's possible that some edge cases or subtle bugs may exist that haven't been discovered yet. If you encounter any issues, please [open an issue](https://github.com/jpawlowski/hass.tibber_prices/issues/new) - we'll work on fixing them (with AI help, of course! 😊).

The integration is actively maintained and benefits from AI's ability to quickly understand and implement Home Assistant patterns, maintain consistency across the codebase, and handle complex data transformations. Quality is ensured through automated linting (Ruff), Home Assistant's type checking, and real-world testing.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

[releases]: https://github.com/jpawlowski/hass.tibber_prices/releases
[releases-shield]: https://img.shields.io/github/release/jpawlowski/hass.tibber_prices.svg?style=for-the-badge
[commits-shield]: https://img.shields.io/github/commit-activity/y/jpawlowski/hass.tibber_prices.svg?style=for-the-badge
[commits]: https://github.com/jpawlowski/hass.tibber_prices/commits/main
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[exampleimg]: https://raw.githubusercontent.com/jpawlowski/hass.tibber_prices/main/images/example.png
[license-shield]: https://img.shields.io/github/license/jpawlowski/hass.tibber_prices.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40jpawlowski-blue.svg?style=for-the-badge
[user_profile]: https://github.com/jpawlowski
[buymecoffee]: https://www.buymeacoffee.com/jpawlowski
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
