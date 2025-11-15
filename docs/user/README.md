# User Documentation

Welcome to Tibber Prices! This integration provides enhanced electricity price data from Tibber with quarter-hourly precision, statistical analysis, and intelligent ratings.

## 📚 Documentation

-   **[Installation](installation.md)** - How to install via HACS and configure the integration
-   **[Configuration](configuration.md)** - Setting up your Tibber API token and price thresholds
-   **[Period Calculation](period-calculation.md)** - How Best/Peak Price periods are calculated and configured
-   **[Sensors](sensors.md)** - Available sensors, their states, and attributes
-   **[Dynamic Icons](dynamic-icons.md)** - State-based automatic icon changes
-   **[Dynamic Icon Colors](icon-colors.md)** - Using icon_color attribute for color-coded dashboards
-   **[Services](services.md)** - Custom services and how to use them
-   **[Automation Examples](automation-examples.md)** - Ready-to-use automation recipes
-   **[Troubleshooting](troubleshooting.md)** - Common issues and solutions

## 🚀 Quick Start

1. **Install via HACS** (add as custom repository)
2. **Add Integration** in Home Assistant → Settings → Devices & Services
3. **Enter Tibber API Token** (get yours at [developer.tibber.com](https://developer.tibber.com/))
4. **Configure Price Thresholds** (optional, defaults work for most users)
5. **Start Using Sensors** in automations, dashboards, and scripts!

## ✨ Key Features

-   **Quarter-hourly precision** - 15-minute intervals for accurate price tracking
-   **Statistical analysis** - Trailing/leading 24h averages for context
-   **Price ratings** - LOW/NORMAL/HIGH classification based on your thresholds
-   **Best/Peak hour detection** - Automatic detection of cheapest/peak periods with configurable filters ([learn how](period-calculation.md))
-   **ApexCharts integration** - Custom services for beautiful price charts
-   **Multi-currency support** - EUR, NOK, SEK with proper minor units (ct, øre, öre)

## 🔗 Useful Links

-   [GitHub Repository](https://github.com/jpawlowski/hass.tibber_prices)
-   [Issue Tracker](https://github.com/jpawlowski/hass.tibber_prices/issues)
-   [Release Notes](https://github.com/jpawlowski/hass.tibber_prices/releases)
-   [Home Assistant Community](https://community.home-assistant.io/)

## 🤝 Need Help?

-   Check the [Troubleshooting Guide](troubleshooting.md)
-   Search [existing issues](https://github.com/jpawlowski/hass.tibber_prices/issues)
-   Open a [new issue](https://github.com/jpawlowski/hass.tibber_prices/issues/new) if needed

---

**Note:** These guides are for end users. If you want to contribute to development, see the [Developer Documentation](../development/).
