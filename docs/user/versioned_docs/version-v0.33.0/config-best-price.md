---
sidebar_label: 💚 Best Price Period
---

# 💚 Best Price Period

**Settings → Devices & Services → Tibber Prices → Configure → 💚 Best Price Period**

---

Best Price Period sensors detect windows of time when electricity is cheap enough to be worth scheduling loads (dishwasher, washing machine, EV charging, water heater). The binary sensor `is_best_price_period` is `on` during these windows.

See **[Period Calculation](period-calculation.md)** for an in-depth explanation of the detection algorithm and [Period Relaxation](period-relaxation.md) for how the relaxation strategy works.

## Settings

### Period Settings

| Setting | Default | Description |
|---------|---------|-------------|
| **Minimum period length** | 60 min | Shortest window to report as a period — filters out tiny sub-hour dips |
| **Maximum price level** | CHEAP | Only intervals at this Tibber level or cheaper qualify |
| **Gap tolerance** | 1 | Consecutive above-threshold intervals allowed inside a period — bridges small price bumps between two cheap windows |

### Flexibility Settings

| Setting | Default | Description |
|---------|---------|-------------|
| **Flex percentage** | 15% | How far above the daily minimum a price can be and still qualify. Higher = more intervals qualify |
| **Minimum distance from average** | 5% | Qualifying intervals must be at least this far below the daily average — ensures periods are meaningfully cheap, not just "not expensive" |

### Relaxation & Target

| Setting | Default | Description |
|---------|---------|-------------|
| **Enable minimum period target** | On | Automatically loosens criteria (relaxation) until the target count is reached |
| **Target periods per day** | 2 | How many distinct periods the algorithm aims to find per day |
| **Relaxation attempts** | 11 | How many times to loosen the criteria before giving up. 11 steps × 3% increment = up to ~48% flex |

:::tip Start with defaults
The defaults are tuned for typical European electricity markets. If you're unsure, leave them as-is and observe the binary sensor over a few days.
:::

## Runtime Override Entities

You can override these settings at runtime through automations — useful for seasonal adjustments or dynamic schedules — without opening the configuration menu.

These entities are **disabled by default**. Enable them in **Settings → Devices & Services → Tibber Prices → Entities**.

| Entity | Type | Range | Overrides |
|--------|------|-------|-----------|
| `number.<home_name>_best_price_flexibility` | Number | 0–50% | Flex percentage |
| `number.<home_name>_best_price_minimum_distance` | Number | -50–0% | Minimum distance from average |
| `number.<home_name>_best_price_minimum_period_length` | Number | 15–180 min | Minimum period length |
| `number.<home_name>_best_price_minimum_periods` | Number | 1–10 | Target periods per day |
| `number.<home_name>_best_price_relaxation_attempts` | Number | 1–12 | Relaxation attempts |
| `number.<home_name>_best_price_gap_tolerance` | Number | 0–8 | Gap tolerance |
| `switch.<home_name>_best_price_enable_relaxation` | Switch | On/Off | Enable relaxation |

When an override entity is **enabled**, its value takes precedence over the menu setting. When **disabled** (default), the menu setting is used.

Changing a value triggers immediate period recalculation. Entity values are restored automatically after HA restarts.

### Example: Stricter detection in winter

<details>
<summary>Show YAML: Seasonal override automation</summary>

```yaml
automation:
  - alias: "Winter: Stricter Best Price Detection"
    trigger:
      - platform: time
        at: "00:00:00"
    condition:
      - condition: template
        value_template: "{{ now().month in [11, 12, 1, 2] }}"
    action:
      - service: number.set_value
        target:
          entity_id: number.<home_name>_best_price_flexibility
        data:
          value: 10  # Stricter than default 15%
```

</details>

See **[Runtime Override Entities](config-runtime-overrides.md)** for more details, including how overrides work, how to view entity descriptions, and recorder optimization.
