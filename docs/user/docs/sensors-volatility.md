# Volatility Sensors

:::tip Entity ID tip
`<home_name>` is a placeholder for your Tibber home display name in Home Assistant. Entity IDs are derived from the displayed name (localized), so the exact slug may differ. **Can't find a sensor?** Use the **[Entity Reference (All Languages)](sensor-reference.md)** to search by name in your language.
:::

Volatility sensors help you understand how much electricity prices fluctuate over a given period. Instead of just looking at the absolute price, they measure the **relative price variation**, which is a great indicator of whether it's a good day for price-based energy optimization.

The calculation is based on the **Coefficient of Variation (CV)**, a standardized statistical measure defined as:

`CV = (Standard Deviation / Arithmetic Mean) * 100%`

This results in a percentage that shows how much prices deviate from the average. A low CV means stable prices, while a high CV indicates significant price swings and thus, a high potential for saving money by shifting consumption.

The sensor's state can be `low`, `moderate`, `high`, or `very_high`, based on configurable thresholds.

## Available Volatility Sensors

| Sensor | Description | Time Window |
|---|---|---|
| <EntityRef id="today_volatility">Today's Price Volatility</EntityRef> | Volatility for the current calendar day | 00:00 - 23:59 today |
| <EntityRef id="tomorrow_volatility">Tomorrow's Price Volatility</EntityRef> | Volatility for the next calendar day | 00:00 - 23:59 tomorrow |
| **Next 24h Price Volatility** (`next_24h_volatility`) | Volatility for the next 24 hours from now | Rolling 24h forward |
| <EntityRef id="today_tomorrow_volatility">Today + Tomorrow Price Volatility</EntityRef> | Volatility across both today and tomorrow | Up to 48 hours |

## Configuration

You can adjust the CV thresholds that determine the volatility level:
1. Go to **Settings → Devices & Services → Tibber Prices**.
2. Click **Configure**.
3. Go to the **Price Volatility Thresholds** step.

Default thresholds are:
- **Moderate:** 15%
- **High:** 30%
- **Very High:** 50%

## Key Attributes

All volatility sensors provide these attributes:

| Attribute | Description | Example |
|---|---|---|
| `price_volatility` | Volatility level (language-independent, always English) | `"moderate"` |
| `price_coefficient_variation_%` | The calculated Coefficient of Variation | `23.5` |
| `price_spread` | The difference between the highest and lowest price | `12.3` |
| `price_min` | The lowest price in the period | `10.2` |
| `price_max` | The highest price in the period | `22.5` |
| `price_mean` | The arithmetic mean of all prices in the period | `15.1` |
| `interval_count` | Number of price intervals included in the calculation | `96` |

## Usage in Automations & Best Practices

You can use the volatility sensor to decide if a price-based optimization is worth it. For example, if your solar battery has conversion losses, you might only want to charge and discharge it on days with high volatility.

### Best Practice: Use the `price_volatility` Attribute

For automations, it is strongly recommended to use the `price_volatility` attribute instead of the sensor's main state.

- **Why?** The main `state` of the sensor is translated into your Home Assistant language (e.g., "Hoch" in German). If you change your system language, automations based on this state will break. The `price_volatility` attribute is **always in lowercase English** (`"low"`, `"moderate"`, `"high"`, `"very_high"`) and therefore provides a stable, language-independent value.

**Good Example (Robust Automation):**
This automation triggers only if the volatility is classified as `high` or `very_high`, respecting your central settings and working independently of the system language.
<details>
<summary>Show YAML: Good Example (Robust Automation)</summary>

```yaml
automation:
  - alias: "Enable battery optimization only on volatile days"
    trigger:
      - platform: template
        value_template: >
          {{ state_attr('sensor.<home_name>_today_s_price_volatility', 'price_volatility') in ['high', 'very_high'] }}
    action:
      - service: input_boolean.turn_on
        entity_id: input_boolean.battery_optimization_enabled
```

</details>

---

### Avoid Hard-Coding Numeric Thresholds

You might be tempted to use the numeric `price_coefficient_variation_%` attribute directly in your automations. This is not recommended.

- **Why?** The integration provides central configuration options for the volatility thresholds. By using the classified `price_volatility` attribute, your automations automatically adapt if you decide to change what you consider "high" volatility (e.g., changing the threshold from 30% to 35%). Hard-coding values means you would have to find and update them in every single automation.

**Bad Example (Brittle Automation):**
This automation uses a hard-coded value. If you later change the "High" threshold in the integration's options to 35%, this automation will not respect that change and might trigger at the wrong time.
<details>
<summary>Show YAML: Bad Example (Brittle Automation)</summary>

```yaml
automation:
  - alias: "Brittle - Enable battery optimization"
    trigger:
      #
      # BAD: Avoid hard-coding numeric values
      #
      - platform: numeric_state
        entity_id: sensor.<home_name>_today_s_price_volatility
        attribute: price_coefficient_variation_%
        above: 30
    action:
      - service: input_boolean.turn_on
        entity_id: input_boolean.battery_optimization_enabled
```

</details>

By following the "Good Example", your automations become simpler, more readable, and much easier to maintain.
