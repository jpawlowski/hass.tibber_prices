# Tibber Price Information & Ratings

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
[![Project Maintenance][maintenance-shield]][user_profile]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

A Home Assistant integration that provides advanced price information and ratings from Tibber. This integration allows you to monitor electricity prices, price levels, and rating information to help you optimize your energy consumption and save money.

![Tibber Price Information & Ratings][exampleimg]

## Features

-   **Current and Next Hour Prices**: Get real-time price data in both EUR and cents/kWh
-   **Price Level Indicators**: Know when you're in a low, normal, or high price period
-   **Statistical Sensors**: Track lowest, highest, and average prices for the day
-   **Price Ratings**: Quarterly-hour, daily, and monthly ratings to understand how current prices compare to historical data
-   **Smart Indicators**: Binary sensors to detect peak hours and best price hours for automations
-   **Diagnostic Sensors**: Monitor data freshness and availability

## Installation

### HACS Installation (Recommended)

1. Ensure [HACS](https://hacs.xyz/) is installed in your Home Assistant instance
2. Go to HACS > Integrations > Click the three dots in the top right > Custom repositories
3. Add this repository URL: `https://github.com/jpawlowski/hass.tibber_prices`
4. Click "Add"
5. Search for "Tibber Price Information & Ratings" in the Integrations tab
6. Click "Install"
7. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/tibber_prices` directory from this repository into your Home Assistant's `custom_components` directory
2. Restart Home Assistant

## Configuration

### Requirements

-   A Tibber account with an active subscription
-   A Tibber API access token (obtain from [developer.tibber.com](https://developer.tibber.com/settings/access-token))

### Setup Process

1. Go to **Settings** > **Devices & Services** in your Home Assistant UI
2. Click the **+ ADD INTEGRATION** button in the bottom right
3. Search for "Tibber Price Information & Ratings"
4. Enter your Tibber API access token when prompted
5. Click "Submit"

## Available Entities

### Price Sensors

| Entity                            | Description                                                                                 | Unit   | Default Enabled |
| --------------------------------- | ------------------------------------------------------------------------------------------- | ------ | --------------- |
| Current Electricity Price         | The current hourly price                                                                    | ct/kWh | Yes             |
| Current Electricity Price (EUR)   | The current hourly price                                                                    | €      | No              |
| Next Hour Electricity Price       | The price for the upcoming hour                                                             | ct/kWh | Yes             |
| Next Hour Electricity Price (EUR) | The price for the upcoming hour                                                             | €      | No              |
| Current Price Level               | Tibber's classification of the price (VERY_CHEAP, CHEAP, NORMAL, EXPENSIVE, VERY_EXPENSIVE) | -      | Yes             |

### Statistical Sensors

| Entity                      | Description                           | Unit   | Default Enabled |
| --------------------------- | ------------------------------------- | ------ | --------------- |
| Today's Lowest Price        | The lowest price for the current day  | ct/kWh | Yes             |
| Today's Lowest Price (EUR)  | The lowest price for the current day  | €      | No              |
| Today's Highest Price       | The highest price for the current day | ct/kWh | Yes             |
| Today's Highest Price (EUR) | The highest price for the current day | €      | No              |
| Today's Average Price       | The average price for the current day | ct/kWh | Yes             |
| Today's Average Price (EUR) | The average price for the current day | €      | No              |

### Rating Sensors

| Entity               | Description                                              | Unit | Default Enabled |
| -------------------- | -------------------------------------------------------- | ---- | --------------- |
| Hourly Price Rating  | How the current hour's price compares to historical data | %    | Yes             |
| Daily Price Rating   | How today's prices compare to historical data            | %    | Yes             |
| Monthly Price Rating | How this month's prices compare to historical data       | %    | Yes             |

### Binary Sensors

| Entity                | Description                                                         | Default Enabled |
| --------------------- | ------------------------------------------------------------------- | --------------- |
| Peak Hour             | Whether the current hour is in the top 20% of prices for the day    | Yes             |
| Best Price Hour       | Whether the current hour is in the bottom 20% of prices for the day | Yes             |
| Tibber API Connection | Shows connection status to the Tibber API                           | Yes             |

### Diagnostic Sensors

| Entity                 | Description                                                      | Default Enabled |
| ---------------------- | ---------------------------------------------------------------- | --------------- |
| Last Data Update       | Timestamp of the most recent data update                         | Yes             |
| Tomorrow's Data Status | Indicates if tomorrow's price data is available (Yes/No/Partial) | Yes             |

## Automation Examples

### Run Appliances During Cheap Hours

```yaml
automation:
    - alias: "Run Dishwasher During Cheap Hours"
      trigger:
          - platform: state
            entity_id: binary_sensor.tibber_best_price_hour
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

### Notify on Extremely High Prices

```yaml
automation:
    - alias: "Notify on Very Expensive Electricity"
      trigger:
          - platform: state
            entity_id: sensor.tibber_current_price_level
            to: "VERY_EXPENSIVE"
      action:
          - service: notify.mobile_app
            data:
                title: "⚠️ High Electricity Prices"
                message: "Current electricity price is in the VERY EXPENSIVE range. Consider reducing consumption."
```

## Troubleshooting

### No data appearing

1. Check your API token is valid at [developer.tibber.com](https://developer.tibber.com/settings/access-token)
2. Verify you have an active Tibber subscription
3. Check the Home Assistant logs for detailed error messages
4. Restart the integration by going to Configuration > Integrations > Tibber Price Information & Ratings > Options

### Missing tomorrow's price data

-   Tomorrow's price data usually becomes available between 13:00 and 15:00 each day
-   If data is still unavailable after this time, check the Tibber app to see if data is available there

## Contributing

If you want to contribute to this project, please read the [Contributing Guidelines](CONTRIBUTING.md).

## License

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
