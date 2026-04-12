# Tibber Prices - Custom Home Assistant Integration

<p align="center">
  <img src="https://raw.githubusercontent.com/jpawlowski/hass.tibber_prices/main/images/header.svg" alt="Tibber Prices Custom Integration for Tibber" width="600">
</p>

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
[![Project Maintenance][maintenance-shield]][user_profile]

<a href="https://www.buymeacoffee.com/jpawlowski" target="_blank"><img src="https://raw.githubusercontent.com/jpawlowski/hass.tibber_prices/main/images/bmc-button.svg" alt="Buy Me A Coffee" height="41" width="174"></a>

> **⚠️ Not affiliated with Tibber**
> This is an independent, community-maintained custom integration for Home Assistant. It is **not** an official Tibber product and is **not** affiliated with or endorsed by Tibber AS.

**The most comprehensive Tibber price integration for Home Assistant.** Get 100+ sensors with quarter-hourly precision, intelligent best/peak price period detection, price forecasts, trend analysis, volatility tracking, and beautiful chart visualizations - all from a single integration. Automate your energy consumption like a pro.

## 📖 Documentation

**[📚 Complete Documentation](https://jpawlowski.github.io/hass.tibber_prices/)** — Installation, guides, examples, and full sensor reference:

- **[👤 User Documentation](https://jpawlowski.github.io/hass.tibber_prices/user/)** — Setup, sensors, automations, dashboards
- **[🔧 Developer Documentation](https://jpawlowski.github.io/hass.tibber_prices/developer/)** — Architecture, contributing, development

**Quick Links:**
[Installation](https://jpawlowski.github.io/hass.tibber_prices/user/installation) · [Sensor Reference](https://jpawlowski.github.io/hass.tibber_prices/user/sensor-reference) · [Charts](https://jpawlowski.github.io/hass.tibber_prices/user/chart-examples) · [Automations](https://jpawlowski.github.io/hass.tibber_prices/user/automation-examples) · [FAQ](https://jpawlowski.github.io/hass.tibber_prices/user/faq) · [Changelog](https://github.com/jpawlowski/hass.tibber_prices/releases)

## ✨ Why This Integration?

Most Tibber integrations give you a single price sensor. This one gives you a **complete energy optimization toolkit**:

### 🔮 Know What's Coming

- **Quarter-hourly precision** — 15-minute interval prices, not just hourly averages
- **Price forecasts** — See average prices for the next 1h, 2h, 3h, ... up to 12h ahead
- **Trend analysis** — Know if prices are rising, falling, or stable — and when the next trend change happens
- **Price trajectory** — Detect turning points before they happen (first-half vs second-half window comparison)
- **Price outlook** — Instantly see if the next hours will be cheaper or more expensive than now

### ⚡ Automate Smartly

- **Best Price & Peak Price Periods** — Intelligent binary sensors that detect the cheapest and most expensive periods of the day, with configurable flexibility, relaxation strategies, and gap tolerance ([how it works](https://jpawlowski.github.io/hass.tibber_prices/user/period-calculation))
- **Period timing sensors** — Duration, end time, remaining minutes, progress percentage, and countdown to next period — everything you need for advanced automations
- **Runtime configuration** — Adjust period detection parameters on the fly via switches and number entities, without restarting — perfect for automations that adapt to your schedule
- **5-level price classification** — VERY_CHEAP, CHEAP, NORMAL, EXPENSIVE, VERY_EXPENSIVE from Tibber's API
- **3-level price ratings** — LOW, NORMAL, HIGH based on 24h trailing average comparison

### 📊 Visualize Beautifully

- **Auto-generated ApexCharts** — One action call generates a complete chart configuration with dynamic Y-axis scaling and color-coded price levels ([see examples](https://jpawlowski.github.io/hass.tibber_prices/user/chart-examples))
- **Dynamic icons & colors** — Every sensor adapts its icon and color to the current price state — cheap prices glow green, expensive ones turn red ([icon guide](https://jpawlowski.github.io/hass.tibber_prices/user/dynamic-icons))
- **Chart data export** — Flexible data API with filtering, resolution control, and multiple output formats for any visualization card

### 📈 Understand Your Market

- **Volatility analysis** — Know if today's prices are stable or wild (low/moderate/high/very_high)
- **Daily & rolling statistics** — Min, max, average, median for today, tomorrow, trailing 24h, and leading 24h
- **Energy & tax breakdown** — See spot price vs. tax components as sensor attributes
- **Multi-currency support** — EUR, NOK, SEK, DKK, USD, GBP with configurable base/subunit display (€ vs ct, kr vs øre)

### 🛡️ Built for Reliability

- **Intelligent caching** — Multi-layer caching minimizes API calls, survives HA restarts, auto-invalidates at midnight
- **High-performance interval pool** — O(1) timestamp lookups, gap detection, auto-fetching of missing data
- **Quarter-hour precision updates** — Sensors refresh at :00/:15/:30/:45 boundaries, independent of API polling
- **Official API only** — Uses Tibber's [`priceInfo`](https://developer.tibber.com/docs/reference#priceinfo) and [`priceInfoRange`](https://developer.tibber.com/docs/reference#subscription) endpoints. All ratings and statistics are calculated locally.

## 🚀 Quick Start

### Step 1: Install via HACS

**Prerequisites:** [HACS](https://hacs.xyz/) (Home Assistant Community Store) must be installed.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jpawlowski&repository=hass.tibber_prices&category=integration)

1. Click "Download" to install
2. **Restart Home Assistant**

### Step 2: Configure

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=tibber_prices)

1. Enter your Tibber API token ([get one here](https://developer.tibber.com/settings/access-token))
2. Select your Tibber home
3. Configure price thresholds (optional — sensible defaults are provided)

Or manually: **Settings** → **Devices & Services** → **+ Add Integration** → search "Tibber Price Information & Ratings"

### Step 3: Done!

- **100+ sensors** are now available (key sensors enabled by default, advanced ones ready to enable)
- Explore entities in **Settings** → **Devices & Services** → **Tibber Price Information & Ratings**
- Start building automations, dashboards, and energy-saving workflows

📖 **[Full Installation Guide →](https://jpawlowski.github.io/hass.tibber_prices/user/installation)**

## 📊 What You Get

The integration provides **100+ entities** across sensors, binary sensors, switches, and number entities. Here are the highlights — all key sensors are **enabled by default**:

<img src="https://raw.githubusercontent.com/jpawlowski/hass.tibber_prices/main/docs/user/static/img/entities-overview.jpg" width="400" alt="Entity list showing dynamic icons for different price states">

| Category                | Highlights                                                                    | Count |
| ----------------------- | ----------------------------------------------------------------------------- | ----- |
| **💰 Prices**           | Current, next & previous interval price + rolling hour averages               | 6+    |
| **📊 Statistics**       | Daily min/max/avg for today & tomorrow, 24h trailing & leading windows        | 12+   |
| **🔮 Forecasts**        | Next 1h–12h average prices, price outlook & trajectory sensors                | 20+   |
| **📈 Trends**           | Current trend direction, next trend change time & countdown                   | 3     |
| **📉 Volatility**       | Today, tomorrow, next 24h & combined volatility levels                        | 4     |
| **🏷️ Levels & Ratings** | 5-level (API) and 3-level (computed) classification per interval, hour & day  | 12+   |
| **⏰ Period Timing**    | Best/peak: end time, duration, remaining, progress, next start                | 10+   |
| **🔌 Binary Sensors**   | Best price period, peak price period, tomorrow data available, API connection | 4+    |
| **🎛️ Runtime Config**   | Switches & numbers to adjust period detection live — no restart needed        | 14    |
| **🔧 Diagnostics**      | Data lifecycle status, home metadata, grid info, subscription status          | 15+   |

> **Every sensor includes rich attributes** — timestamps, detailed descriptions, and context data. Enable **Extended Descriptions** in the integration options to get `long_description` and `usage_tips` on every entity.

📖 **[Complete Sensor Reference →](https://jpawlowski.github.io/hass.tibber_prices/user/sensor-reference)** — All entities with descriptions, attributes, and multi-language lookup

## 🤖 Automation Sneak Peek

> See the **[full automation examples guide](https://jpawlowski.github.io/hass.tibber_prices/user/automation-examples)** for more recipes.

**Run appliances when electricity is cheapest:**

```yaml
automation:
    - alias: "Start Dishwasher During Best Price Period"
      trigger:
          - platform: state
            entity_id: binary_sensor.tibber_best_price_period
            to: "on"
      action:
          - action: switch.turn_on
            target:
                entity_id: switch.dishwasher
```

**Reduce heating when prices spike above average:**

```yaml
automation:
    - alias: "Reduce Heating During High Prices"
      trigger:
          - platform: numeric_state
            entity_id: sensor.tibber_current_interval_price_rating
            above: 20 # More than 20% above 24h average
      action:
          - action: climate.set_temperature
            target:
                entity_id: climate.living_room
            data:
                temperature: 19
```

📖 **[More automations →](https://jpawlowski.github.io/hass.tibber_prices/user/automation-examples)** — EV charging, heat pump control, price notifications, and more

## 📈 Chart Visualizations

Generate beautiful price charts with a single action call — dynamic Y-axis, color-coded price levels, and multiple chart modes included.

<img src="https://raw.githubusercontent.com/jpawlowski/hass.tibber_prices/main/docs/user/static/img/charts/rolling-window.jpg" width="600" alt="Dynamic 48h rolling window chart with color-coded price levels">

📖 **[Chart examples & setup →](https://jpawlowski.github.io/hass.tibber_prices/user/chart-examples)** | **[Actions reference →](https://jpawlowski.github.io/hass.tibber_prices/user/actions)**

## ❓ Help & Support

- 📖 **[FAQ](https://jpawlowski.github.io/hass.tibber_prices/user/faq)** — Common questions answered
- 🔧 **[Troubleshooting](https://jpawlowski.github.io/hass.tibber_prices/user/troubleshooting)** — Solving common issues
- 🐛 **[Report an Issue](https://github.com/jpawlowski/hass.tibber_prices/issues/new)** — Found a bug? Let us know

## 🤝 Contributing

Contributions are welcome! See the [Contributing Guidelines](CONTRIBUTING.md) and [Developer Documentation](https://jpawlowski.github.io/hass.tibber_prices/developer/) to get started.

- **[Developer Setup](https://jpawlowski.github.io/hass.tibber_prices/developer/setup)** — DevContainer-based development environment
- **[Architecture Guide](https://jpawlowski.github.io/hass.tibber_prices/developer/architecture)** — Understand the codebase
- **[Release Management](https://jpawlowski.github.io/hass.tibber_prices/developer/release-management)** — Release process and versioning

## 🤖 Development Note

This integration is developed with extensive AI assistance (GitHub Copilot, Claude, and other AI tools). While AI enables rapid development, it's possible that some edge cases haven't been discovered yet. If you encounter any issues, please [open an issue](https://github.com/jpawlowski/hass.tibber_prices/issues/new) — we'll fix them (with AI help, of course! 😊).

Quality is ensured through automated linting (Ruff), static type checking (Pyright), and real-world testing.

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

[releases]: https://github.com/jpawlowski/hass.tibber_prices/releases
[releases-shield]: https://img.shields.io/github/release/jpawlowski/hass.tibber_prices.svg?style=for-the-badge
[commits-shield]: https://img.shields.io/github/commit-activity/y/jpawlowski/hass.tibber_prices.svg?style=for-the-badge
[commits]: https://github.com/jpawlowski/hass.tibber_prices/commits/main
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[license-shield]: https://img.shields.io/github/license/jpawlowski/hass.tibber_prices.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40jpawlowski-blue.svg?style=for-the-badge
[user_profile]: https://github.com/jpawlowski
[buymecoffee]: https://www.buymeacoffee.com/jpawlowski
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
