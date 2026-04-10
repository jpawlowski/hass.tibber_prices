---
comments: false
---

# Community Examples

This page collects **real-world examples** contributed by the community — templates, automations, dashboard cards, and creative solutions built with Tibber Prices.

> **Before you start:** All examples require adaptation to your setup. At minimum, replace entity IDs like `sensor.<home_name>_...` with your own. See **Settings → Devices & Services → Entities** to find the correct IDs.

---

## Country-Specific Price Calculations

The Tibber API provides the raw spot price (`energy_price` attribute) and tax/fee component (`tax` attribute) on every price sensor. Since the exact composition of `tax` varies by country, you can use these attributes to build **your own** country-specific calculations with Home Assistant templates.

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
| Spot price | Inkoopprijs | Variable (= `energy_price` attribute) |
| Energy tax | Energiebelasting | ~0.0916 €/kWh (excl. VAT) |
| VAT | BTW | 21% |
| Purchase fee | Inkoopvergoeding | ~0.0205 €/kWh |
| Sales fee | Verkoopvergoeding | ~0.0205 €/kWh |

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
| BTW percentage | `input_number.btw_percentage` | 0 | 100 | 0.01 | % | 21 |
| Inkoopvergoeding | `input_number.inkoopvergoeding` | 0 | 1 | 0.0001 | €/kWh | 0.0205 |
| Verkoopvergoeding | `input_number.verkoopvergoeding` | 0 | 1 | 0.0001 | €/kWh | 0.0205 |

<details>
<summary>Alternative: YAML configuration for input_number helpers</summary>

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
    btw_percentage:
        name: BTW Percentage
        min: 0
        max: 100
        step: 0.01
        unit_of_measurement: "%"
        icon: mdi:percent
    inkoopvergoeding:
        name: Inkoopvergoeding
        min: 0
        max: 1
        step: 0.0001
        unit_of_measurement: "€/kWh"
        icon: mdi:cash-minus
    verkoopvergoeding:
        name: Verkoopvergoeding
        min: 0
        max: 1
        step: 0.0001
        unit_of_measurement: "€/kWh"
        icon: mdi:cash-plus
```

</details>

### Step 2: Template Sensors for Feed-In Compensation

These template sensors calculate what you **earn** per kWh when feeding solar power back to the grid.

<details>
<summary>Show YAML: Template sensors for feed-in with and without saldering</summary>

```yaml
template:
    - sensor:
          # Feed-in compensation WITH saldering (current rules, until 2027)
          # With saldering, you effectively earn the full consumer price
          # minus the purchase fee, plus the sales fee.
          - name: "Solar Feed-In Price (with Saldering)"
            unique_id: solar_feed_in_saldering
            unit_of_measurement: "€/kWh"
            device_class: monetary
            state: >
                {% set energy = state_attr('sensor.<home_name>_current_electricity_price', 'energy_price') %}
                {% set eb = states('input_number.energiebelasting') | float %}
                {% set btw = states('input_number.btw_percentage') | float / 100 %}
                {% set inkoop = states('input_number.inkoopvergoeding') | float %}
                {% set verkoop = states('input_number.verkoopvergoeding') | float %}
                {% if energy is not none %}
                  {{ ((energy + eb) * (1 + btw) - inkoop + verkoop) | round(4) }}
                {% else %}
                  unavailable
                {% endif %}
            icon: mdi:solar-power-variant

          # Feed-in compensation WITHOUT saldering (after 2027)
          # Without saldering, you only earn the raw spot price
          # minus the purchase fee, plus the sales fee.
          - name: "Solar Feed-In Price (without Saldering)"
            unique_id: solar_feed_in_no_saldering
            unit_of_measurement: "€/kWh"
            device_class: monetary
            state: >
                {% set energy = state_attr('sensor.<home_name>_current_electricity_price', 'energy_price') %}
                {% set inkoop = states('input_number.inkoopvergoeding') | float %}
                {% set verkoop = states('input_number.verkoopvergoeding') | float %}
                {% if energy is not none %}
                  {{ (energy - inkoop + verkoop) | round(4) }}
                {% else %}
                  unavailable
                {% endif %}
            icon: mdi:solar-power-variant-outline
```

</details>

### Step 3: Use in Automations

Now you can use these sensors to make smarter decisions about when to export solar power vs. charge a battery:

<details>
<summary>Show YAML: Smart export automation</summary>

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

<details>
<summary>Show YAML: Dashboard comparison card</summary>

```yaml
type: entities
title: "Solar Feed-In Compensation Comparison"
entities:
    - entity: sensor.<home_name>_current_electricity_price
      name: "Consumer Price (total)"
    - type: attribute
      entity: sensor.<home_name>_current_electricity_price
      attribute: energy_price
      name: "Spot Price (energy)"
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

## 🇩🇪 Germany: Price Composition

### Background

In Germany, the electricity price includes numerous components bundled into `tax`:

| Component | German Name | Description |
|-----------|-----------|-------------|
| Spot price | Börsenstrompreis | Variable (= `energy_price` attribute) |
| Grid fees | Netzentgelte | Varies by grid operator |
| Electricity tax | Stromsteuer | Fixed per kWh |
| Concession fee | Konzessionsabgabe | Varies by municipality |
| Surcharges | Umlagen (§19, Offshore, KWKG) | Various regulatory surcharges |
| VAT | Mehrwertsteuer | 19% |

### Template: Spot Price Share

A simple template sensor showing what percentage of your total price is the actual energy cost:

<details>
<summary>Show YAML: Spot price share template sensor</summary>

```yaml
template:
    - sensor:
          - name: "Spot Price Share"
            unique_id: spot_price_share
            unit_of_measurement: "%"
            state: >
                {% set energy = state_attr('sensor.<home_name>_current_electricity_price', 'energy_price') %}
                {% set total = states('sensor.<home_name>_current_electricity_price') | float %}
                {% if energy is not none and total > 0 %}
                  {{ ((energy / total) * 100) | round(1) }}
                {% else %}
                  unavailable
                {% endif %}
            icon: mdi:chart-pie
```

</details>

---

## 🇳🇴 Norway / 🇸🇪 Sweden: Grid & Tax Components

Norway and Sweden have their own fee structures, but the same pattern applies — use `input_number` helpers for the fixed/semi-fixed components and `energy_price` for the spot price.

**Contributions welcome!** If you have working template examples for Norway or Sweden, please share them in a [GitHub Discussion](https://github.com/jpawlowski/hass.tibber_prices/discussions).

---

## Contributing Your Own Examples

Have a useful template, automation, or dashboard card built with Tibber Prices? We'd love to feature it here!

1. Share it in a [GitHub Discussion](https://github.com/jpawlowski/hass.tibber_prices/discussions)
2. Describe your use case and include the YAML code
3. Tested examples that work with the current version are preferred

Community examples are attributed to their original authors.
