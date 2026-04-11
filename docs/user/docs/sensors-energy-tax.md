# Energy & Tax Attributes

> **Entity ID tip:** `<home_name>` is a placeholder for your Tibber home display name in Home Assistant. Entity IDs are derived from the displayed name (localized), so the exact slug may differ. **Can't find a sensor?** Use the **[Entity Reference (All Languages)](sensor-reference.md)** to search by name in your language.

Most price sensors include **energy price** and **tax** attributes that break down the total price into its components:

```
total = energy_price + tax
```

These attributes appear on **all price sensors that display a raw price** (not on percentage, level, or trend sensors). The `energy_price` is the raw spot/market price, while `tax` includes all fees, surcharges, and taxes added by your electricity provider.

:::note Transition After Update
After updating the integration, the `energy_price` and `tax` attributes will appear gradually as new price data is fetched from the Tibber API. Existing cached intervals (up to ~2 days old) won't have these fields yet — the attributes will simply be absent until fresh data replaces them. No action needed.
:::

## Where These Attributes Appear

| Sensor Type | `energy_price` | `tax` | Notes |
|-------------|:-:|:-:|-------|
| Current/Next/Previous Interval Price | ✅ | ✅ | Single interval values |
| Rolling Hour Average | ✅ | ✅ | Averaged across 5 intervals |
| Daily Min/Max/Average | ✅ | ✅ | Aggregated for the day |
| Trailing/Leading 24h | ✅ | ✅ | Aggregated across window |
| Future Average (N-hour) | ✅ | ✅ | Averaged across future window |
| Levels, Ratings, Trends | ❌ | ❌ | Not price sensors |
| Volatility | ❌ | ❌ | Statistical, not price |

## Use Cases

### Solar Feed-In & Net Metering (Saldering)

In countries like the Netherlands, solar feed-in compensation is based on the **raw energy/spot price**, not the total consumer price. The `energy_price` attribute gives you exactly this value — no more reverse-engineering from the total price with fragile template calculations.

<details>
<summary>Show YAML: Automation — solar export or consume decision</summary>

```yaml
# Example: Decide whether to export solar power or consume it
# Compare energy price (what you'd earn by exporting) vs. total price (what you'd pay)
automation:
    - alias: "Solar: Export or Consume"
      trigger:
          - platform: numeric_state
            entity_id: sensor.solar_production_power
            above: 2000  # Producing more than 2 kW
      condition:
          - condition: template
            value_template: >
                {% set energy = state_attr('sensor.<home_name>_current_electricity_price', 'energy_price') %}
                {% set total = states('sensor.<home_name>_current_electricity_price') | float %}
                {# Export when energy price is high relative to total — you earn more #}
                {{ energy is not none and energy > (total * 0.4) }}
      action:
          - service: switch.turn_off
            entity_id: switch.battery_charging  # Don't charge battery, export instead
```

</details>

### Price Composition Analysis

Understand how your electricity price is structured — useful for comparing across days or spotting trends in market prices vs. fees:

<details>
<summary>Show YAML: Template sensor — electricity tax share percentage</summary>

```yaml
# Template sensor showing tax share
template:
    - sensor:
          - name: "Electricity Tax Share"
            unit_of_measurement: "%"
            state: >
                {% set tax = state_attr('sensor.<home_name>_current_electricity_price', 'tax') %}
                {% set total = states('sensor.<home_name>_current_electricity_price') | float %}
                {% if tax is not none and total > 0 %}
                  {{ ((tax / total) * 100) | round(1) }}
                {% else %}
                  unavailable
                {% endif %}
```

</details>

### Dashboard: Daily Cost Breakdown

Show users how today's average price splits into energy vs. tax:

```yaml
# Mushroom chips card showing the split
type: custom:mushroom-chips-card
chips:
    - type: template
      icon: mdi:flash
      content: >
          ⚡ {{ state_attr('sensor.<home_name>_price_today', 'energy_price_mean') | round(1) }} ct
    - type: template
      icon: mdi:receipt-text
      content: >
          🏛️ {{ state_attr('sensor.<home_name>_price_today', 'tax_mean') | round(1) }} ct
```

## Country-Specific Calculations

The composition of the `tax` field varies by country (Norway, Sweden, Germany, Netherlands each have different fee structures). For detailed examples of how to build country-specific calculations using `input_number` helpers and template sensors — including **Dutch solar feed-in compensation (saldering)** — see the **[Community Examples](community-examples.md#country-specific-price-calculations)** page.

## In Chart Data Actions

The `energy_price` and `tax` fields are also available in the `get_chartdata` action. See [Actions — Energy & Tax Fields](./actions.md#energy--tax-fields-in-get_chartdata) for details.
