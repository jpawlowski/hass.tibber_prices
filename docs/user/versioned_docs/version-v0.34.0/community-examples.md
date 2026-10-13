---
comments: false
---

# Community Examples

This page collects **real-world examples** contributed by the community — templates, automations, dashboard cards, and creative solutions built with Tibber Prices.

> **Before you start:** All examples require adaptation to your setup. At minimum, replace entity IDs like `sensor.<home_name>_...` with your own. See **Settings → Devices & Services → Entities** to find the correct IDs.

---

## Country-Specific Price Calculations

The Tibber API provides the raw spot price (`energy_price` attribute) and tax/fee component (`tax` attribute) on every price sensor. Their unit follows your integration's **Currency Display Mode**:

- Subunit mode: `ct/kWh` (default for EUR, including NL)
- Base mode: `€/kWh`

Since the exact composition of `tax` varies by country, you can use these attributes to build **your own** country-specific calculations with Home Assistant templates.

:::tip Keep templates unit-safe
For long-term stable templates, normalize values to `€/kWh` inside your template (recommended below). If you use Subunit mode, you can alternatively use the dedicated **Current Electricity Price (Energy Dashboard)** sensor (`current_interval_price_base`), which provides base-currency values for Energy Dashboard use cases. In Base mode, this extra sensor is not exposed because `current_interval_price` already provides base-currency values.
:::

:::tip Why templates instead of built-in calculations?
Tax rates and energy fees change regularly (often annually). Using `input_number` helpers in Home Assistant keeps your calculations up-to-date with a simple UI adjustment — no integration update needed.
:::

:::caution Adapt values to your country
The tax rates and fees shown below are **examples only**. Verify them against your energy provider's invoices and update them when rates change (usually January 1st).
:::

---

## 🇳🇱 Netherlands: Solar Feed-In Compensation

*Contributed by community member OdynBrouwer ([Discussion #105](https://github.com/jpawlowski/hass.tibber_prices/discussions/105))*

### Background

In the Netherlands, the electricity price paid to consumers includes:

| Component | Dutch Name | Typical Value (2025) |
|-----------|-----------|---------------------|
| Spot price | Inkoopprijs | Variable (`energy_price` attribute; unit depends on display mode) |
| Energy tax | Energiebelasting | ~0.0916 €/kWh (excl. VAT) |
| Purchase fee | Inkoopvergoeding | ~0.0205 €/kWh |
| Sales fee | Verkoopvergoeding | ~-0.0205 €/kWh |
| VAT | BTW | 21% |

:::warning Rates change annually
The values above are examples. Check [Rijksoverheid.nl](https://www.rijksoverheid.nl/onderwerpen/belastingplan/energiebelasting) for current energy tax rates and your energy contract for purchase/sales fees.
:::

### Saldering (Net Metering) — Until 2027

The Netherlands currently uses **saldering** (net metering): solar feed-in is offset against consumption at the full consumer price. This effectively means you earn the `total` price for each kWh exported. [The Dutch government has confirmed this ends in 2027.](https://www.rijksoverheid.nl/onderwerpen/duurzame-energie/zonne-energie)

### Step 1: Create Input Number Helpers

Create `input_number` helpers in Home Assistant for each fee component. This way, when rates change (usually January 1st), you only need to update the values in the UI.

**Settings → Devices & Services → Helpers → Create Helper → Number**

| Helper | Entity ID | Min | Max | Step | Unit | Example Value |
|--------|-----------|-----|-----|------|------|---------------|
| Energiebelasting | `input_number.energiebelasting` | 0 | 1 | 0.0001 | €/kWh | 0.0916 |
| Inkoopvergoeding | `input_number.inkoopvergoeding` | 0 | 1 | 0.0001 | €/kWh | 0.0205 |
| Verkoopvergoeding | `input_number.verkoopvergoeding` | -1 | 1 | 0.0001 | €/kWh | -0.0205 |
| BTW percentage | `input_number.btw_percentage` | 0 | 100 | 0.01 | % | 21 |

:::note Signed fee input
`input_number.verkoopvergoeding` is a signed value in this example, so negative values are allowed. Enter all fee components excluding VAT.
:::

<details>
<summary>Show YAML: Input Number Helpers</summary>

If you prefer YAML configuration over the UI, add these to your `configuration.yaml`:

```yaml
input_number:
    energiebelasting:
        name: Energiebelasting
        min: 0
        max: 1
        step: 0.0001
        unit_of_measurement: "€/kWh"
        icon: mdi:lightning-bolt
    inkoopvergoeding:
        name: Inkoopvergoeding
        min: 0
        max: 1
        step: 0.0001
        unit_of_measurement: "€/kWh"
        icon: mdi:cash-minus
    verkoopvergoeding:
        name: Verkoopvergoeding
        min: -1
        max: 1
        step: 0.0001
        unit_of_measurement: "€/kWh"
        icon: mdi:cash-plus
    btw_percentage:
        name: BTW Percentage
        min: 0
        max: 100
        step: 0.01
        unit_of_measurement: "%"
        icon: mdi:percent
```

</details>

### Step 2: Template Sensors for Feed-In Compensation

These template sensors calculate what you **earn** per kWh when feeding solar power back to the grid.

<details>
<summary>Show YAML: Feed-In Compensation Sensors</summary>

```yaml
template:
    - sensor:
          # Feed-in compensation WITH saldering (current rules, until 2027)
          # With saldering, you effectively earn the full consumer price
          # plus purchase and sales fee components (use negative verkoopvergoeding
          # to offset inkoopvergoeding when your contract defines it that way).
          - name: "Solar Feed-In Price (with Saldering)"
            unique_id: solar_feed_in_saldering
            unit_of_measurement: "€/kWh"
            device_class: monetary
            state: >
                {# Option A: current display-mode sensor (default) #}
                {# Option B: in Subunit mode, switch to current_interval_price_base for base-currency workflows #}
                {% set price_entity = 'sensor.<home_name>_current_electricity_price' %}
                {% set energy_raw = state_attr(price_entity, 'energy_price') %}
                {% set price_unit = state_attr(price_entity, 'unit_of_measurement') %}
                {% set unit_factor = 100 if price_unit == 'ct/kWh' else 1 %}
                {% set eb = states('input_number.energiebelasting') | float %}
                {% set inkoop = states('input_number.inkoopvergoeding') | float %}
                {% set verkoop = states('input_number.verkoopvergoeding') | float %}
                {% set btw = states('input_number.btw_percentage') | float / 100 %}
                {% if energy_raw is not none %}
                  {% set energy = (energy_raw | float) / unit_factor %}
                  {{ ((energy + eb + inkoop + verkoop) * (1 + btw)) | round(4) }}
                {% else %}
                  unavailable
                {% endif %}
            icon: mdi:solar-power-variant

          # Feed-in compensation WITHOUT saldering (after 2027)
          # Without saldering, you only earn the raw spot price
          # plus purchase and sales fee components.
          - name: "Solar Feed-In Price (without Saldering)"
            unique_id: solar_feed_in_no_saldering
            unit_of_measurement: "€/kWh"
            device_class: monetary
            state: >
                {# Option A: current display-mode sensor (default) #}
                {# Option B: in Subunit mode, switch to current_interval_price_base for base-currency workflows #}
                {% set price_entity = 'sensor.<home_name>_current_electricity_price' %}
                {% set energy_raw = state_attr(price_entity, 'energy_price') %}
                {% set price_unit = state_attr(price_entity, 'unit_of_measurement') %}
                {% set unit_factor = 100 if price_unit == 'ct/kWh' else 1 %}
                {% set inkoop = states('input_number.inkoopvergoeding') | float %}
                {% set verkoop = states('input_number.verkoopvergoeding') | float %}
                {% set btw = states('input_number.btw_percentage') | float / 100 %}
                {% if energy_raw is not none %}
                  {% set energy = (energy_raw | float) / unit_factor %}
                  {{ ((energy + inkoop + verkoop) * (1 + btw)) | round(4) }}
                {% else %}
                  unavailable
                {% endif %}
            icon: mdi:solar-power-variant-outline
```

</details>

### Step 3: Use in Automations

Now you can use these sensors to make smarter decisions about when to export solar power vs. charge a battery:

<details>
<summary>Show YAML: Feed-In Automation</summary>

```yaml
automation:
    - alias: "Solar: Smart Export Decision"
      description: >
          When solar production exceeds consumption, decide whether to
          export power or charge the home battery based on current
          feed-in compensation vs. upcoming price forecasts.
      trigger:
          - platform: numeric_state
            entity_id: sensor.solar_production_power
            above: 2000
      condition:
          - condition: template
            value_template: >
                {# Export if feed-in price is above the next 3 hours average #}
                {% set feed_in = states('sensor.solar_feed_in_price_with_saldering') | float(0) %}
                {% set upcoming = states('sensor.<home_name>_next_3h_average_price') | float(0) %}
                {{ feed_in > upcoming }}
      action:
          - service: switch.turn_off
            entity_id: switch.battery_charging
```

</details>

### Preparing for the End of Saldering

To understand the financial impact of the saldering phase-out, you can create a dashboard comparing both scenarios side by side:

:::note Unit label reminder
The label `ct/kWh` below is a manual display label. If your integration uses Base currency mode, update this label to `€/kWh` so it matches your active display mode.
:::

<details>
<summary>Show YAML: Preparing for the End of Saldering</summary>

```yaml
type: entities
title: "Solar Feed-In Compensation Comparison"
entities:
    - entity: sensor.<home_name>_current_electricity_price
      name: "Consumer Price (total)"
    - type: attribute
      entity: sensor.<home_name>_current_electricity_price
      attribute: energy_price
      name: "Spot Price (energy, ct/kWh)"
      icon: mdi:transmission-tower
    - entity: sensor.solar_feed_in_price_with_saldering
      name: "Feed-In with Saldering"
      icon: mdi:solar-power-variant
    - entity: sensor.solar_feed_in_price_no_saldering
      name: "Feed-In without Saldering (2027+)"
      icon: mdi:solar-power-variant-outline
```

</details>

---

## 🇩🇪 Germany: Feed-In Compensation

### Background

In Germany, private households usually get a **fixed feed-in compensation** (Einspeisevergütung) for exported PV energy, while consumption uses the dynamic end-user price from your tariff.

That means the practical question is often:

- consume/store energy locally now, or
- export now at your fixed feed-in rate

### Step 1: Create Input Number Helper for Feed-In Compensation

Create one helper for your current contractual feed-in rate in `€/kWh`.

**Settings → Devices & Services → Helpers → Create Helper → Number**

| Helper | Entity ID | Min | Max | Step | Unit | Example Value |
|--------|-----------|-----|-----|------|------|---------------|
| Einspeisevergütung | `input_number.einspeiseverguetung` | 0 | 1 | 0.0001 | €/kWh | 0.0778 |

:::note Keep this value up to date
Use the exact value from your contract or network operator statement. Typical values differ by commissioning date and plant setup (partial vs full feed-in).
:::

<details>
<summary>Show YAML: Input Number Helper</summary>

```yaml
input_number:
    einspeiseverguetung:
        name: Einspeisevergütung
        min: 0
        max: 1
        step: 0.0001
        unit_of_measurement: "€/kWh"
        icon: mdi:transmission-tower-export
```

</details>

### Step 2: Template Sensors for Feed-In Decision Support

These sensors normalize your current price to `€/kWh`, compare it with your fixed feed-in compensation, and expose a clean binary signal for automations.

:::note Display-mode safe
`current_electricity_price` can be in `ct/kWh` or `€/kWh` depending on display mode. The template below normalizes automatically to `€/kWh`.
:::

<details>
<summary>Show YAML: Feed-In Decision Sensors</summary>

```yaml
template:
    - sensor:
          - name: "Current Electricity Price (EUR normalized)"
            unique_id: current_electricity_price_eur_normalized
            unit_of_measurement: "€/kWh"
            device_class: monetary
            state: >
                {% set price_entity = 'sensor.<home_name>_current_electricity_price' %}
                {% set total_raw = states(price_entity) | float(none) %}
                {% set price_unit = state_attr(price_entity, 'unit_of_measurement') %}
                {% set unit_factor = 100 if price_unit == 'ct/kWh' else 1 %}
                {% if total_raw is not none %}
                  {{ (total_raw / unit_factor) | round(4) }}
                {% else %}
                  unavailable
                {% endif %}
            icon: mdi:currency-eur

          - name: "Self-Consumption Advantage"
            unique_id: self_consumption_advantage
            unit_of_measurement: "€/kWh"
            device_class: monetary
            state: >
                {% set import_price = states('sensor.current_electricity_price_eur_normalized') | float(none) %}
                {% set feed_in = states('input_number.einspeiseverguetung') | float(none) %}
                {% if import_price is not none and feed_in is not none %}
                  {{ (import_price - feed_in) | round(4) }}
                {% else %}
                  unavailable
                {% endif %}
            icon: mdi:scale-balance

    - binary_sensor:
          - name: "Prefer Self-Consumption"
            unique_id: prefer_self_consumption
            state: >
                {% set advantage = states('sensor.self_consumption_advantage') | float(none) %}
                {{ advantage is not none and advantage > 0 }}
            icon: mdi:home-lightning-bolt
```

</details>

### Step 3: Use in Automations

Use the binary sensor to switch behavior between export-oriented and self-consumption-oriented operation.

<details>
<summary>Show YAML: Example Automation (Battery Charging Strategy)</summary>

```yaml
automation:
    - alias: "Battery: Prefer self-consumption when import price is higher than feed-in"
      trigger:
          - platform: state
            entity_id: binary_sensor.prefer_self_consumption
      action:
          - choose:
                - conditions:
                      - condition: state
                        entity_id: binary_sensor.prefer_self_consumption
                        state: "on"
                  sequence:
                      # Example: keep energy locally (charge battery / reduce export)
                      - service: switch.turn_on
                        target:
                            entity_id: switch.battery_charging
                - conditions:
                      - condition: state
                        entity_id: binary_sensor.prefer_self_consumption
                        state: "off"
                  sequence:
                      # Example: allow more export to grid
                      - service: switch.turn_off
                        target:
                            entity_id: switch.battery_charging
```

</details>

---

## 🇳🇴 Norway / 🇸🇪 Sweden: Grid & Tax Components

Norway and Sweden have their own fee structures, but the same pattern applies — use `input_number` helpers for the fixed/semi-fixed components and `energy_price` for the spot price (unit depends on your display mode).

**Contributions welcome!** If you have working template examples for Norway or Sweden, please share them in a [GitHub Discussion](https://github.com/jpawlowski/hass.tibber_prices/discussions).

---

## Contributing Your Own Examples

Have a useful template, automation, or dashboard card built with Tibber Prices? We'd love to feature it here!

1. Share it in a [GitHub Discussion](https://github.com/jpawlowski/hass.tibber_prices/discussions)
2. Describe your use case and include the YAML code
3. Tested examples that work with the current version are preferred

Community examples are attributed to their original authors.
