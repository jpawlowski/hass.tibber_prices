# Automation Examples

> **Note:** This guide is under construction.

> **Tip:** For dashboard examples with dynamic icons and colors, see the **[Dynamic Icons Guide](dynamic-icons.md)** and **[Dynamic Icon Colors Guide](icon-colors.md)**.

## Table of Contents

-   [Price-Based Automations](#price-based-automations)
-   [Volatility-Aware Automations](#volatility-aware-automations)
-   [Best Hour Detection](#best-hour-detection)
-   [ApexCharts Cards](#apexcharts-cards)

---

> **Important Note:** The following examples are intended as templates to illustrate the logic. They are **not** suitable for direct copy & paste without adaptation.
>
> Please make sure you:
> 1.  Replace the **Entity IDs** (e.g., `sensor.<home_name>_...`, `switch.pool_pump`) with the IDs of your own devices and sensors.
> 2.  Adapt the logic to your specific devices (e.g., heat pump, EV, water boiler).
>
> These examples provide a good starting point but must be tailored to your individual Home Assistant setup.
>
> **Entity ID tip:** `<home_name>` is a placeholder for your Tibber home display name in Home Assistant. Entity IDs are derived from the displayed name (localized), so the exact slug may differ. Example suffixes below use the English display names (en.json) as a baseline. You can find the real ID in **Settings → Devices & Services → Entities** (or **Developer Tools → States**).

## Price-Based Automations

Coming soon...

---

## Volatility-Aware Automations

These examples show how to create robust automations that only act when price differences are meaningful, avoiding unnecessary actions on days with flat prices.

### Use Case: Only Act on Meaningful Price Variations

On days with low price variation, the difference between "cheap" and "expensive" periods can be just a fraction of a cent. This automation charges a home battery only when the volatility is high enough to result in actual savings.

**Best Practice:** Instead of checking a numeric percentage, this automation checks the sensor's classified state. This makes the automation simpler and respects the volatility thresholds you have configured centrally in the integration's options.

```yaml
automation:
    - alias: "Home Battery - Charge During Best Price (Moderate+ Volatility)"
      description: "Charge home battery during Best Price periods, but only on days with meaningful price differences"
      trigger:
          - platform: state
            entity_id: binary_sensor.<home_name>_best_price_period
            to: "on"
      condition:
          # Best Practice: Check the classified volatility level.
          # This ensures the automation respects the thresholds you set in the config options.
          # We use the 'price_volatility' attribute for a language-independent check.
          # 'low' means minimal savings, so we only run if it's NOT low.
          - condition: template
            value_template: >
                {{ state_attr('sensor.<home_name>_today_s_price_volatility', 'price_volatility') != 'low' }}
          # Only charge if battery has capacity
          - condition: numeric_state
            entity_id: sensor.home_battery_level
            below: 90
      action:
          - service: switch.turn_on
            target:
                entity_id: switch.home_battery_charge
          - service: notify.mobile_app
            data:
                message: >
                  Home battery charging started. Price: {{ states('sensor.<home_name>_current_electricity_price') }} {{ state_attr('sensor.<home_name>_current_electricity_price', 'unit_of_measurement') }}.
                  Today's volatility is {{ state_attr('sensor.<home_name>_today_s_price_volatility', 'price_volatility') }}.

```

**Why this works:**

-   The automation only runs if volatility is `moderate`, `high`, or `very_high`.
-   If you adjust your volatility thresholds in the future, this automation adapts automatically without any changes.
-   It uses the `price_volatility` attribute, ensuring it works correctly regardless of your Home Assistant's display language.

### Use Case: Combined Volatility and Absolute Price Check

This is the most robust approach. It trusts the "Best Price" classification on volatile days but adds a backup absolute price check for low-volatility days. This handles situations where prices are globally low, even if the daily variation is minimal.

```yaml
automation:
    - alias: "EV Charging - Smart Strategy"
      description: "Charge EV using volatility-aware logic"
      trigger:
          - platform: state
            entity_id: binary_sensor.<home_name>_best_price_period
            to: "on"
      condition:
          # Check battery level
          - condition: numeric_state
            entity_id: sensor.ev_battery_level
            below: 80
          # Strategy: Moderate+ volatility OR the price is genuinely cheap
          - condition: or
            conditions:
                # Path 1: Volatility is not 'low', so we trust the 'Best Price' period classification.
                - condition: template
                  value_template: >
                      {{ state_attr('sensor.<home_name>_today_s_price_volatility', 'price_volatility') != 'low' }}
                # Path 2: Volatility is low, but we charge anyway if the price is below an absolute cheapness threshold.
                - condition: numeric_state
                  entity_id: sensor.<home_name>_current_electricity_price
                  below: 0.18
      action:
          - service: switch.turn_on
            target:
                entity_id: switch.ev_charger
          - service: notify.mobile_app
            data:
                message: >
                    EV charging started. Price: {{ states('sensor.<home_name>_current_electricity_price') }} {{ state_attr('sensor.<home_name>_current_electricity_price', 'unit_of_measurement') }}.
                    Today's volatility is {{ state_attr('sensor.<home_name>_today_s_price_volatility', 'price_volatility') }}.
```

**Why this works:**

-   On days with meaningful price swings, it charges during any `Best Price` period.
-   On days with flat prices, it still charges if the price drops below your personal "cheap enough" threshold (e.g., 0.18 €/kWh or 18 ct/kWh).
-   This gracefully handles midnight period flips, as the absolute price check will likely remain true if prices stay low.

### Use Case: Using the Period's Own Volatility Attribute

For maximum simplicity, you can use the attributes of the `best_price_period` sensor itself. It contains the volatility classification for the day the period belongs to. This is especially useful for periods that span across midnight.

```yaml
automation:
    - alias: "Heat Pump - Smart Heating Using Period's Volatility"
      trigger:
          - platform: state
            entity_id: binary_sensor.<home_name>_best_price_period
            to: "on"
      condition:
          # Best Practice: Check if the period's own volatility attribute is not 'low'.
          # This correctly handles periods that start today but end tomorrow.
          - condition: template
            value_template: >
                {{ state_attr('binary_sensor.<home_name>_best_price_period', 'volatility') != 'low' }}
      action:
          - service: climate.set_temperature
            target:
                entity_id: climate.heat_pump
            data:
                temperature: 22 # Boost temperature during cheap period
```

**Why this works:**

-   Each detected period has its own `volatility` attribute (`low`, `moderate`, etc.).
-   This is the simplest way to check for meaningful savings for that specific period.
-   The attribute name on the binary sensor is `volatility` (lowercase) and its value is also lowercase.
-   It also contains other useful attributes like `price_mean`, `price_spread`, and the `price_coefficient_variation_%` for that period.

---

## Best Hour Detection

Coming soon...

---

## ApexCharts Cards

> ⚠️ **IMPORTANT:** The `tibber_prices.get_apexcharts_yaml` service generates a **basic example configuration** as a starting point. It is NOT a complete solution for all ApexCharts features.
>
> This integration is primarily a **data provider**. Due to technical limitations (segmented time periods, service API usage), many advanced ApexCharts features require manual customization or may not be compatible.
>
> **For advanced customization:** Use the `get_chartdata` service directly to build charts tailored to your specific needs. Community contributions with improved configurations are welcome!

The `tibber_prices.get_apexcharts_yaml` service generates basic ApexCharts card configuration examples for visualizing electricity prices.

### Prerequisites

**Required:**

-   [ApexCharts Card](https://github.com/RomRider/apexcharts-card) - Install via HACS

**Optional (for rolling window mode):**

-   [Config Template Card](https://github.com/iantrich/config-template-card) - Install via HACS

### Installation

1. Open HACS → Frontend
2. Search for "ApexCharts Card" and install
3. (Optional) Search for "Config Template Card" and install if you want rolling window mode

### Example: Fixed Day View

```yaml
# Generate configuration via automation/script
service: tibber_prices.get_apexcharts_yaml
data:
    entry_id: YOUR_ENTRY_ID
    day: today # or "yesterday", "tomorrow"
    level_type: rating_level # or "level" for 5-level view
response_variable: apexcharts_config
```

Then copy the generated YAML into your Lovelace dashboard.

### Example: Rolling 48h Window

For a dynamic chart that automatically adapts to data availability:

```yaml
service: tibber_prices.get_apexcharts_yaml
data:
    entry_id: YOUR_ENTRY_ID
    day: rolling_window # Or omit for same behavior (default)
    level_type: rating_level
response_variable: apexcharts_config
```

**Behavior:**

-   **When tomorrow data available** (typically after ~13:00): Shows today + tomorrow
-   **When tomorrow data not available**: Shows yesterday + today
-   **Fixed 48h span:** Always shows full 48 hours

**Auto-Zoom Variant:**

For progressive zoom-in throughout the day:

```yaml
service: tibber_prices.get_apexcharts_yaml
data:
    entry_id: YOUR_ENTRY_ID
    day: rolling_window_autozoom
    level_type: rating_level
response_variable: apexcharts_config
```

-   Same data loading as rolling window
-   **Progressive zoom:** Graph span starts at ~26h in the morning and decreases to ~14h by midnight
-   **Updates every 15 minutes:** Always shows 2h lookback + remaining time until midnight

**Note:** Rolling window modes require Config Template Card to dynamically adjust the time range.

### Features

-   Color-coded price levels/ratings (green = cheap, yellow = normal, red = expensive)
-   Best price period highlighting (semi-transparent green overlay)
-   Automatic NULL insertion for clean gaps
-   Translated labels based on your Home Assistant language
-   Interactive zoom and pan
-   Live marker showing current time
