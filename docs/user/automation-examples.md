# Automation Examples

> **Note:** This guide is under construction.

> **Tip:** For dashboard examples with dynamic icons and colors, see the **[Dynamic Icons Guide](dynamic-icons.md)** and **[Dynamic Icon Colors Guide](icon-colors.md)**.

## Table of Contents

-   [Price-Based Automations](#price-based-automations)
-   [Volatility-Aware Automations](#volatility-aware-automations)
-   [Best Hour Detection](#best-hour-detection)
-   [ApexCharts Cards](#apexcharts-cards)

---

## Price-Based Automations

Coming soon...

---

## Volatility-Aware Automations

These examples show how to handle low-volatility days where period classifications may flip at midnight despite minimal absolute price changes.

### Use Case: Only Act on High-Volatility Days

On days with low price variation (< 15% volatility), the difference between "cheap" and "expensive" periods is minimal. This automation only runs appliances when the savings are meaningful:

```yaml
automation:
  - alias: "Dishwasher - Best Price (High Volatility Only)"
    description: "Start dishwasher during Best Price period, but only on days with meaningful price differences"
    trigger:
      - platform: state
        entity_id: binary_sensor.tibber_home_best_price_period
        to: "on"
    condition:
      # Only act if volatility > 15% (meaningful savings)
      - condition: numeric_state
        entity_id: sensor.tibber_home_volatility_today
        above: 15
      # Optional: Ensure dishwasher is idle and door closed
      - condition: state
        entity_id: binary_sensor.dishwasher_door
        state: "off"
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.dishwasher_smart_plug
      - service: notify.mobile_app
        data:
          message: "Dishwasher started during Best Price period ({{ states('sensor.tibber_home_current_interval_price_ct') }} ct/kWh, volatility {{ states('sensor.tibber_home_volatility_today') }}%)"
```

**Why this works:**
- On high-volatility days (e.g., 25% span), Best Price periods save 5-10 ct/kWh
- On low-volatility days (e.g., 8% span), savings are only 1-2 ct/kWh
- User can manually start dishwasher on low-volatility days without automation interference

### Use Case: Absolute Price Threshold

Instead of relying on relative classification, check if the absolute price is cheap enough:

```yaml
automation:
  - alias: "Water Heater - Cheap Enough"
    description: "Heat water when price is below absolute threshold, regardless of period classification"
    trigger:
      - platform: state
        entity_id: binary_sensor.tibber_home_best_price_period
        to: "on"
    condition:
      # Absolute threshold: Only run if < 20 ct/kWh
      - condition: numeric_state
        entity_id: sensor.tibber_home_current_interval_price_ct
        below: 20
      # Optional: Check water temperature
      - condition: numeric_state
        entity_id: sensor.water_heater_temperature
        below: 55  # Only heat if below 55°C
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.water_heater
      - delay:
          hours: 2  # Heat for 2 hours
      - service: switch.turn_off
        target:
          entity_id: switch.water_heater
```

**Why this works:**
- Period classification can flip at midnight on low-volatility days
- Absolute threshold (20 ct/kWh) is stable across midnight boundary
- User sets their own "cheap enough" price based on local rates

### Use Case: Combined Volatility and Price Check

Most robust approach: Check both volatility and absolute price:

```yaml
automation:
  - alias: "EV Charging - Smart Strategy"
    description: "Charge EV using volatility-aware logic"
    trigger:
      - platform: state
        entity_id: binary_sensor.tibber_home_best_price_period
        to: "on"
    condition:
      # Check battery level
      - condition: numeric_state
        entity_id: sensor.ev_battery_level
        below: 80
      # Strategy: High volatility OR cheap enough
      - condition: or
        conditions:
          # Path 1: High volatility day - trust period classification
          - condition: numeric_state
            entity_id: sensor.tibber_home_volatility_today
            above: 15
          # Path 2: Low volatility but price is genuinely cheap
          - condition: numeric_state
            entity_id: sensor.tibber_home_current_interval_price_ct
            below: 18
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.ev_charger
      - service: notify.mobile_app
        data:
          message: >
            EV charging started: {{ states('sensor.tibber_home_current_interval_price_ct') }} ct/kWh
            (Volatility: {{ states('sensor.tibber_home_volatility_today') }}%)
```

**Why this works:**
- On high-volatility days (> 15%): Trust the Best Price classification
- On low-volatility days (< 15%): Only charge if price is actually cheap (< 18 ct/kWh)
- Handles midnight flips gracefully: Continues charging if price stays cheap

### Use Case: Ignore Period Flips During Active Period

Prevent automations from stopping mid-cycle when a period flips at midnight:

```yaml
automation:
  - alias: "Washing Machine - Complete Cycle"
    description: "Start washing machine during Best Price, ignore midnight flips"
    trigger:
      - platform: state
        entity_id: binary_sensor.tibber_home_best_price_period
        to: "on"
    condition:
      # Only start if washing machine is idle
      - condition: state
        entity_id: sensor.washing_machine_state
        state: "idle"
      # And volatility is meaningful
      - condition: numeric_state
        entity_id: sensor.tibber_home_volatility_today
        above: 15
    action:
      - service: button.press
        target:
          entity_id: button.washing_machine_eco_program
      # Create input_boolean to track active cycle
      - service: input_boolean.turn_on
        target:
          entity_id: input_boolean.washing_machine_auto_started

  # Separate automation: Clear flag when cycle completes
  - alias: "Washing Machine - Cycle Complete"
    trigger:
      - platform: state
        entity_id: sensor.washing_machine_state
        to: "finished"
    condition:
      # Only clear flag if we auto-started it
      - condition: state
        entity_id: input_boolean.washing_machine_auto_started
        state: "on"
    action:
      - service: input_boolean.turn_off
        target:
          entity_id: input_boolean.washing_machine_auto_started
      - service: notify.mobile_app
        data:
          message: "Washing cycle complete"
```

**Why this works:**
- Uses `input_boolean` to track auto-started cycles
- Won't trigger multiple times if period flips during the 2-3 hour wash cycle
- Only triggers on "off" → "on" transitions, not during "on" → "on" continuity

### Use Case: Per-Period Day Volatility

The simplest approach: Use the period's day volatility attribute directly:

```yaml
automation:
  - alias: "Heat Pump - Smart Heating"
    trigger:
      - platform: state
        entity_id: binary_sensor.tibber_home_best_price_period
        to: "on"
    condition:
      # Check if the PERIOD'S DAY has meaningful volatility
      - condition: template
        value_template: >
          {{ state_attr('binary_sensor.tibber_home_best_price_period', 'day_volatility_%') | float(0) > 15 }}
    action:
      - service: climate.set_temperature
        target:
          entity_id: climate.heat_pump
        data:
          temperature: 22  # Boost temperature during cheap period
```

**Available per-period attributes:**
- `day_volatility_%`: Percentage volatility of the period's day (e.g., 8.2 for 8.2%)
- `day_price_min`: Minimum price of the day in minor currency (ct/øre)
- `day_price_max`: Maximum price of the day in minor currency (ct/øre)
- `day_price_span`: Absolute difference (max - min) in minor currency (ct/øre)

These attributes are available on both `binary_sensor.tibber_home_best_price_period` and `binary_sensor.tibber_home_peak_price_period`.

**Why this works:**
- Each period knows its day's volatility
- No need to query separate sensors
- Template checks if saving is meaningful (> 15% volatility)

---

## Best Hour Detection

Coming soon...

---

## ApexCharts Cards

Coming soon...
