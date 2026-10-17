---
sidebar_label: 🔁 Runtime Override Entities
---

# Runtime Override Entities

The integration provides optional **number** and **switch** entities that let you change Best Price and Peak Price detection settings at runtime — through automations or the HA UI — without going into the configuration menu.

These entities are **disabled by default**. Enable them individually in:

**Settings → Devices & Services → Tibber Prices → Entities**

---

## How overrides work

1. **Entity disabled** (default): The configuration menu setting is used
2. **Entity enabled**: The entity value overrides the menu setting
3. **Value changes**: Trigger immediate period recalculation
4. **HA restart**: Entity values are restored automatically

This lets you write automations that adjust detection criteria seasonally, based on weather forecasts, or based on other conditions — without manual configuration changes.

## Available entities

### Best Price Period

| Entity | Type | Range | Overrides |
|--------|------|-------|-----------|
| `number.<home_name>_best_price_flexibility` | Number | 0–50% | [Flex percentage](config-best-price.md) |
| `number.<home_name>_best_price_minimum_distance` | Number | -50–0% | [Minimum distance from average](config-best-price.md) |
| `number.<home_name>_best_price_minimum_period_length` | Number | 15–180 min | [Minimum period length](config-best-price.md) |
| `number.<home_name>_best_price_minimum_periods` | Number | 1–10 | [Target periods per day](config-best-price.md) |
| `number.<home_name>_best_price_relaxation_attempts` | Number | 1–12 | [Relaxation attempts](config-best-price.md) |
| `number.<home_name>_best_price_gap_tolerance` | Number | 0–8 | [Gap tolerance](config-best-price.md) |
| `switch.<home_name>_best_price_enable_relaxation` | Switch | On/Off | [Enable relaxation](config-best-price.md) |

### Peak Price Period

| Entity | Type | Range | Overrides |
|--------|------|-------|-----------|
| `number.<home_name>_peak_price_flexibility` | Number | -50–0% | [Flex percentage](config-peak-price.md) |
| `number.<home_name>_peak_price_minimum_distance` | Number | 0–50% | [Minimum distance from average](config-peak-price.md) |
| `number.<home_name>_peak_price_minimum_period_length` | Number | 15–180 min | [Minimum period length](config-peak-price.md) |
| `number.<home_name>_peak_price_minimum_periods` | Number | 1–10 | [Target periods per day](config-peak-price.md) |
| `number.<home_name>_peak_price_relaxation_attempts` | Number | 1–12 | [Relaxation attempts](config-peak-price.md) |
| `number.<home_name>_peak_price_gap_tolerance` | Number | 0–8 | [Gap tolerance](config-peak-price.md) |
| `switch.<home_name>_peak_price_enable_relaxation` | Switch | On/Off | [Enable relaxation](config-peak-price.md) |

## Viewing entity descriptions

Each override entity has a `description` attribute explaining what the setting does — the same text shown in the configuration menu.

**Note for Number entities:** Home Assistant shows a history graph by default in the entity detail view, which hides the attributes panel. To see the description:

1. Go to **Developer Tools → States**
2. Search for the entity (e.g., `number.<home_name>_best_price_flexibility`)
3. Expand the attributes section

Switch entities show their attributes normally in the entity details view.

## Example: Seasonal adjustment

<details>
<summary>Show YAML: Stricter detection in winter months</summary>

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

## Recorder optimization (optional)

These entities are already designed to minimize database impact:
- **EntityCategory.CONFIG** — excluded from Long-Term Statistics
- All attributes excluded from history recording
- Only state value (the number/switch state) is recorded

If you want to **completely exclude** these entities from the recorder (no history graph, no database entries at all):

<details>
<summary>Show YAML: Exclude from recorder</summary>

```yaml
recorder:
  exclude:
    entity_globs:
      - number.*_best_price_*
      - number.*_peak_price_*
      - switch.*_best_price_*
      - switch.*_peak_price_*
```

</details>

This is useful if you rarely change these settings and want the smallest possible database footprint.
