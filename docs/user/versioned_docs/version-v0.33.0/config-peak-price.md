---
sidebar_label: 🔴 Peak Price Period
---

# 🔴 Peak Price Period

**Settings → Devices & Services → Tibber Prices → Configure → 🔴 Peak Price Period**

---

Peak Price Period sensors detect windows of time when electricity is expensive enough that you should avoid or postpone consumption. The binary sensor `is_peak_price_period` is `on` during these windows.

The detection algorithm mirrors [Best Price Period](config-best-price.md), but in reverse — looking for expensive intervals rather than cheap ones.

See **[Period Calculation](period-calculation.md)** for an in-depth explanation of the detection algorithm and [Period Relaxation](period-relaxation.md) for how relaxation works.

## Settings

### Period Settings

| Setting | Default | Description |
|---------|---------|-------------|
| **Minimum period length** | 60 min | Shortest window to report as a period |
| **Minimum price level** | EXPENSIVE | Only intervals at this Tibber level or more expensive qualify |
| **Gap tolerance** | 1 | Consecutive below-threshold intervals allowed inside a period — bridges small price dips between two expensive windows |

### Flexibility Settings

| Setting | Default | Description |
|---------|---------|-------------|
| **Flex percentage** | -20% | How far below the daily maximum a price can be and still qualify (negative value = below maximum) |
| **Minimum distance from average** | 5% | Qualifying intervals must be at least this far above the daily average |

### Relaxation & Target

| Setting | Default | Description |
|---------|---------|-------------|
| **Enable minimum period target** | On | Automatically loosens criteria until the target count is reached |
| **Target periods per day** | 2 | How many distinct peak periods the algorithm aims to find per day |
| **Relaxation attempts** | 11 | How many times to loosen the criteria before giving up |

## Runtime Override Entities

Same concept as [Best Price overrides](config-best-price.md#runtime-override-entities) — disabled by default, enable individually in Entities.

| Entity | Type | Range | Overrides |
|--------|------|-------|-----------|
| `number.<home_name>_peak_price_flexibility` | Number | -50–0% | Flex percentage |
| `number.<home_name>_peak_price_minimum_distance` | Number | 0–50% | Minimum distance from average |
| `number.<home_name>_peak_price_minimum_period_length` | Number | 15–180 min | Minimum period length |
| `number.<home_name>_peak_price_minimum_periods` | Number | 1–10 | Target periods per day |
| `number.<home_name>_peak_price_relaxation_attempts` | Number | 1–12 | Relaxation attempts |
| `number.<home_name>_peak_price_gap_tolerance` | Number | 0–8 | Gap tolerance |
| `switch.<home_name>_peak_price_enable_relaxation` | Switch | On/Off | Enable relaxation |

See **[Runtime Override Entities](config-runtime-overrides.md)** for full details on how overrides work, viewing entity descriptions, and recorder optimization.
