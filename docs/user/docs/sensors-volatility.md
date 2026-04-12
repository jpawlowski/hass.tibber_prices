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

| Sensor                                                                                  | Description                               | Time Window            |
| --------------------------------------------------------------------------------------- | ----------------------------------------- | ---------------------- |
| <EntityRef id="today_volatility">Today's Price Volatility</EntityRef>                   | Volatility for the current calendar day   | 00:00 - 23:59 today    |
| <EntityRef id="tomorrow_volatility">Tomorrow's Price Volatility</EntityRef>             | Volatility for the next calendar day      | 00:00 - 23:59 tomorrow |
| **Next 24h Price Volatility** (`next_24h_volatility`)                                   | Volatility for the next 24 hours from now | Rolling 24h forward    |
| <EntityRef id="today_tomorrow_volatility">Today + Tomorrow Price Volatility</EntityRef> | Volatility across both today and tomorrow | Up to 48 hours         |

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

| Attribute                       | Description                                                      | Example      |
| ------------------------------- | ---------------------------------------------------------------- | ------------ |
| `price_volatility`              | Volatility level (language-independent, always English)          | `"moderate"` |
| `price_coefficient_variation_%` | The calculated Coefficient of Variation                          | `23.5`       |
| `price_spread`                  | The difference between the highest and lowest price              | `12.3`       |
| `price_min`                     | The lowest price in the period                                   | `10.2`       |
| `price_max`                     | The highest price in the period                                  | `22.5`       |
| `price_mean`                    | The arithmetic mean of all prices in the period                  | `15.1`       |
| `price_median`                  | Median price (50th percentile, robust to outliers)               | `14.8`       |
| `price_q25`                     | 25th percentile — lower quartile price                           | `11.0`       |
| `price_q75`                     | 75th percentile — upper quartile price                           | `19.5`       |
| `price_typical_spread`          | Typical price band width — IQR (Q75 − Q25, the middle 50% of prices)         | `8.5`        |
| `price_typical_spread_%`        | Typical price band as a percentage of the median (IQR%)                      | `57.4`       |
| `price_spike_count`             | Intervals outside the Tukey fence (Q25−1.5×IQR … Q75+1.5×IQR) — spikes/dips | `3`          |
| `interval_count`                | Number of price intervals included in the calculation            | `96`         |

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

## Typical Price Band Statistics (IQR)

In addition to the CV-based volatility level, every volatility sensor provides **typical price band statistics** as attributes. These are derived from the **IQR (Interquartile Range)** — the spread of the middle 50% of prices — making them more **robust to isolated price spikes** than the CV.

| Metric                | CV (state)                                | IQR attributes                     |
| --------------------- | ----------------------------------------- | ---------------------------------- |
| Sensitive to spikes?  | ✅ Yes — spikes inflate CV                | ❌ No — IQR ignores the outer 25%  |
| Use for optimization? | "Is today worth optimizing?"              | "How wide is the core price band?" |
| Best for              | Triggering battery/EV charging strategies | Understanding price structure      |

The `price_typical_spread_%` attribute (IQR as a percentage of the median) tells you how wide the **core** price band is relative to the median. Even on a high-CV day with isolated spikes, a low `price_typical_spread_%` means most of the day has stable prices — only a few intervals are outliers.

The `price_spike_count` attribute (Tukey fence method: Q25 − 1.5×IQR to Q75 + 1.5×IQR) tells you how many intervals fall outside the normal range. A high `price_spike_count` day with a high CV is a classic "spiky" day: mostly stable prices with a few expensive or cheap peaks.

---

## Price Rank Sensors (Percentile Rank)

The price rank sensors answer the simple question: **"Is this price cheap or expensive compared to the rest of the day?"**

Unlike the volatility sensors (which measure the _shape_ of the entire price distribution), price rank sensors place a _specific price_ within that distribution — technically its **percentile rank**. A value of **0% means cheapest interval of the reference set**, while a value near **99% means most expensive**.

Each sensor ranks a different **subject price** against a **reference window**:

- **Subject** — Which price is being ranked: current interval, next interval, previous interval, or the rolling hourly average
- **Reference window** — Which pool of slots to compare against: today only, tomorrow only, or today+tomorrow combined

### How It Works (Percentile Rank Formula)

```
Price rank (percentile rank) = (number of intervals strictly cheaper than subject) ÷ total intervals × 100
```

The cheapest interval always returns 0% — you can use `state == 0` to detect the absolute cheapest moment.

### Available Sensors

**Current interval** (price of the active quarter-hour):

| Sensor                                                                                                                        | Reference Set                          | Enabled by Default |
| ----------------------------------------------------------------------------------------------------------------------------- | -------------------------------------- | ------------------ |
| <EntityRef id="current_interval_price_rank_today">Current Price Rank (Today)</EntityRef>                                      | Today's 96 quarter-hour intervals      | ✅ Yes             |
| <EntityRef id="current_interval_price_rank_tomorrow">Current Price Rank (Tomorrow)</EntityRef>                                | Tomorrow's 96 intervals (once avail.)  | ❌ No              |
| <EntityRef id="current_interval_price_rank_today_tomorrow">Current Price Rank (Today+Tomorrow)</EntityRef>                    | Combined pool (up to 192 intervals)    | ❌ No              |

**Next interval** (price of the upcoming quarter-hour):

| Sensor                                                                                                                        | Reference Set                          | Enabled by Default |
| ----------------------------------------------------------------------------------------------------------------------------- | -------------------------------------- | ------------------ |
| <EntityRef id="next_interval_price_rank_today">Next Price Rank (Today)</EntityRef>                                            | Today's 96 quarter-hour intervals      | ❌ No              |
| <EntityRef id="next_interval_price_rank_today_tomorrow">Next Price Rank (Today+Tomorrow)</EntityRef>                          | Combined pool (up to 192 intervals)    | ❌ No              |

**Previous interval** (price of the just-ended quarter-hour):

| Sensor                                                                                                                        | Reference Set                          | Enabled by Default |
| ----------------------------------------------------------------------------------------------------------------------------- | -------------------------------------- | ------------------ |
| <EntityRef id="previous_interval_price_rank_today">Last Price Rank (Today)</EntityRef>                                        | Today's 96 quarter-hour intervals      | ❌ No              |
| <EntityRef id="previous_interval_price_rank_today_tomorrow">Last Price Rank (Today+Tomorrow)</EntityRef>                      | Combined pool (up to 192 intervals)    | ❌ No              |

**Rolling hourly average** (5-interval window, ~1 hour):

| Sensor                                                                                                                        | Reference Set                          | Enabled by Default |
| ----------------------------------------------------------------------------------------------------------------------------- | -------------------------------------- | ------------------ |
| <EntityRef id="current_hour_price_rank_today">⌀ Hourly Price Current Rank (Today)</EntityRef>                                 | Today's 96 quarter-hour intervals      | ❌ No              |
| <EntityRef id="current_hour_price_rank_today_tomorrow">⌀ Hourly Price Current Rank (Today+Tomorrow)</EntityRef>               | Combined pool (up to 192 intervals)    | ❌ No              |
| <EntityRef id="next_hour_price_rank_today">⌀ Hourly Price Next Rank (Today)</EntityRef>                                       | Today's 96 quarter-hour intervals      | ❌ No              |
| <EntityRef id="next_hour_price_rank_today_tomorrow">⌀ Hourly Price Next Rank (Today+Tomorrow)</EntityRef>                     | Combined pool (up to 192 intervals)    | ❌ No              |

### Key Attributes

All price rank sensors share most of these attributes. The price attribute key reflects the subject:

| Attribute                | Description                                              | Subject            |
| ------------------------ | -------------------------------------------------------- | ------------------ |
| `current_price`          | The price being ranked (current interval)                | Current interval   |
| `next_price`             | The price being ranked (next interval)                   | Next interval      |
| `previous_price`         | The price being ranked (previous interval)               | Previous interval  |
| `current_hour_avg_price` | The rolling average being ranked (current hour)          | Current hour avg   |
| `next_hour_avg_price`    | The rolling average being ranked (next hour)             | Next hour avg      |
| `prices_below_count`     | How many reference intervals are strictly cheaper        | All sensors        |
| `interval_count`         | Total intervals in the reference set                     | All sensors        |
| `reference_min`          | The cheapest price in the reference set                  | All sensors        |
| `reference_max`          | The most expensive price in the reference set            | All sensors        |
| `reference_mean`         | Average price of the reference set                       | All sensors        |

### When to Use Which Sensor

- **Current (Today)** — Same-day scheduling. "Is the active quarter-hour within the cheapest 25% of today?"
- **Next (Today)** — Prepare for the next interval. "Should I pre-heat now so the device runs in the coming cheap slot?"
- **Current (Today+Tomorrow)** — Broadest view for flexible tasks. "Is this among the cheapest moments of a 48-hour window?"
- **Current (Tomorrow)** — Decide whether to wait until tomorrow. "Is today's price worse than what tomorrow offers?"
- **⌀ Hourly Current (Today)** — For tasks that take about an hour. "Is this hour cheap enough to start a 60-minute cycle?"
- **⌀ Hourly Next (Today)** — One-hour look-ahead. "Will the upcoming hour be cheap enough to start now?"

### Usage in Automations

<details>
<summary>Show YAML: Start dishwasher in bottom quartile</summary>

```yaml
automation:
    - alias: "Start dishwasher at cheapest time of day"
      trigger:
          - platform: numeric_state
            entity_id: sensor.<home_name>_current_price_rank_today
            below: 25
      condition:
          - condition: state
            entity_id: binary_sensor.<home_name>_best_price_period
            state: "on"
      action:
          - service: switch.turn_on
            entity_id: switch.dishwasher
```

</details>

<details>
<summary>Show YAML: Postpone task if tomorrow is cheaper</summary>

```yaml
automation:
    - alias: "Skip charging tonight if tomorrow is cheaper"
      trigger:
          - platform: time
            at: "21:00:00"
      condition:
          # Only postpone if tomorrow's cheapest quartile is better than the current price
          - condition: template
            value_template: >
                {{ states('sensor.<home_name>_current_price_rank_tomorrow') | float(100) < 25 }}
      action:
          - service: input_boolean.turn_off
            entity_id: input_boolean.ev_charge_tonight
```

</details>

<details>
<summary>Show YAML: Pre-heat when the next interval is cheap</summary>

```yaml
automation:
    - alias: "Pre-heat if next interval is top quartile cheapest"
      trigger:
          - platform: time_pattern
            minutes: "/15"
      condition:
          - condition: numeric_state
            entity_id: sensor.<home_name>_next_price_rank_today
            below: 25
      action:
          - service: climate.set_hvac_mode
            entity_id: climate.living_room
            data:
                hvac_mode: heat
```

</details>
