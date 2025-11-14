# Period Calculation

Learn how Best Price and Peak Price periods work, and how to configure them for your needs.

## Table of Contents

-   [Quick Start](#quick-start)
-   [How It Works](#how-it-works)
-   [Configuration Guide](#configuration-guide)
-   [Understanding Relaxation](#understanding-relaxation)
-   [Common Scenarios](#common-scenarios)
-   [Troubleshooting](#troubleshooting)
-   [Advanced Topics](#advanced-topics)

---

## Quick Start

### What Are Price Periods?

The integration finds time windows when electricity is especially **cheap** (Best Price) or **expensive** (Peak Price):

-   **Best Price Periods** 🟢 - When to run your dishwasher, charge your EV, or heat water
-   **Peak Price Periods** 🔴 - When to reduce consumption or defer non-essential loads

### Default Behavior

Out of the box, the integration:

1. **Best Price**: Finds cheapest 1-hour+ windows that are at least 2% below the daily average
2. **Peak Price**: Finds most expensive 1-hour+ windows that are at least 2% above the daily average
3. **Relaxation**: Automatically loosens filters if not enough periods are found

**Most users don't need to change anything!** The defaults work well for typical use cases.

### Example Timeline

```
00:00 ████████████████ Best Price Period (cheap prices)
04:00 ░░░░░░░░░░░░░░░░ Normal
08:00 ████████████████ Peak Price Period (expensive prices)
12:00 ░░░░░░░░░░░░░░░░ Normal
16:00 ████████████████ Peak Price Period (expensive prices)
20:00 ████████████████ Best Price Period (cheap prices)
```

---

## How It Works

### The Basic Idea

Each day, the integration analyzes all 96 quarter-hourly price intervals and identifies **continuous time ranges** that meet specific criteria.

Think of it like this:

1. **Find potential windows** - Times close to the daily MIN (Best Price) or MAX (Peak Price)
2. **Filter by quality** - Ensure they're meaningfully different from average
3. **Check duration** - Must be long enough to be useful
4. **Apply preferences** - Optional: only show stable prices, avoid mediocre times

### Step-by-Step Process

#### 1. Define the Search Range (Flexibility)

**Best Price:** How much MORE than the daily minimum can a price be?

```
Daily MIN: 20 ct/kWh
Flexibility: 15% (default)
→ Search for times ≤ 23 ct/kWh (20 + 15%)
```

**Peak Price:** How much LESS than the daily maximum can a price be?

```
Daily MAX: 40 ct/kWh
Flexibility: -15% (default)
→ Search for times ≥ 34 ct/kWh (40 - 15%)
```

**Why flexibility?** Prices rarely stay at exactly MIN/MAX. Flexibility lets you capture realistic time windows.

#### 2. Ensure Quality (Distance from Average)

Periods must be meaningfully different from the daily average:

```
Daily AVG: 30 ct/kWh
Minimum distance: 2% (default)

Best Price: Must be ≤ 29.4 ct/kWh (30 - 2%)
Peak Price: Must be ≥ 30.6 ct/kWh (30 + 2%)
```

**Why?** This prevents marking mediocre times as "best" just because they're slightly below average.

#### 3. Check Duration

Periods must be long enough to be practical:

```
Default: 60 minutes minimum

45-minute period → Discarded
90-minute period → Kept ✓
```

#### 4. Apply Optional Filters

You can optionally require:

-   **Absolute quality** (level filter) - "Only show if prices are CHEAP/EXPENSIVE (not just below/above average)"

#### 5. Statistical Outlier Filtering

**Before** period identification, price spikes are automatically detected and smoothed:

```
Raw prices:    18, 19, 35, 20, 19 ct   ← 35 ct is an isolated spike
Smoothed:      18, 19, 19, 20, 19 ct   ← Spike replaced with trend prediction

Result: Continuous period 00:00-01:15 instead of split periods
```

**How it works:**

-   **Linear regression** predicts expected price based on surrounding trend
-   **95% confidence intervals** (2 standard deviations) define spike tolerance
-   **Symmetry checking** preserves legitimate price shifts (morning/evening peaks)
-   **Enhanced zigzag detection** catches spike clusters without multiple passes

**Data integrity:**

-   Original prices **always preserved** for statistics (min/max/avg show real values)
-   Smoothing **only affects period formation** (which intervals qualify for periods)
-   Attributes show when smoothing was impactful: `period_interval_smoothed_count`

**Example log output:**

```
DEBUG: [2025-11-11T14:30:00+01:00] Outlier detected: 35.2 ct
DEBUG:   Residual: 14.5 ct > tolerance: 4.8 ct (2×2.4 std dev)
DEBUG:   Trend slope: 0.3 ct/interval (gradual increase)
DEBUG:   Smoothed to: 20.7 ct (trend prediction)
```

### Visual Example

**Timeline for a typical day:**

```
Hour:  00  01  02  03  04  05  06  07  08  09  10  11  12  13  14  15  16  17  18  19  20  21  22  23
Price: 18  19  20  28  29  30  35  34  33  32  30  28  25  24  26  28  30  32  31  22  21  20  19  18

Daily MIN: 18 ct | Daily MAX: 35 ct | Daily AVG: 26 ct

Best Price (15% flex = ≤20.7 ct):
       ████████                                                                        ████████████████
       00:00-03:00 (3h)                                                               19:00-24:00 (5h)

Peak Price (-15% flex = ≥29.75 ct):
                              ████████████████████████
                              06:00-11:00 (5h)
```

---

## Configuration Guide

### Basic Settings

#### Flexibility

**What:** How far from MIN/MAX to search for periods
**Default:** 15% (Best Price), -15% (Peak Price)
**Range:** 0-100%

```yaml
best_price_flex: 15 # Can be up to 15% more expensive than daily MIN
peak_price_flex: -15 # Can be up to 15% less expensive than daily MAX
```

**When to adjust:**

-   **Increase (20-25%)** → Find more/longer periods
-   **Decrease (5-10%)** → Find only the very best/worst times

#### Minimum Period Length

**What:** How long a period must be to show it
**Default:** 60 minutes
**Range:** 15-240 minutes

```yaml
best_price_min_period_length: 60
peak_price_min_period_length: 60
```

**When to adjust:**

-   **Increase (90-120 min)** → Only show longer periods (e.g., for heat pump cycles)
-   **Decrease (30-45 min)** → Show shorter windows (e.g., for quick tasks)

#### Distance from Average

**What:** How much better than average a period must be
**Default:** 2%
**Range:** 0-20%

```yaml
best_price_min_distance_from_avg: 2
peak_price_min_distance_from_avg: 2
```

**When to adjust:**

-   **Increase (5-10%)** → Only show clearly better times
-   **Decrease (0-1%)** → Show any time below/above average

### Optional Filters

#### Level Filter (Absolute Quality)

**What:** Only show periods with CHEAP/EXPENSIVE intervals (not just below/above average)
**Default:** `any` (disabled)
**Options:** `any` | `cheap` | `very_cheap` (Best Price) | `expensive` | `very_expensive` (Peak Price)

```yaml
best_price_max_level: any      # Show any period below average
best_price_max_level: cheap    # Only show if at least one interval is CHEAP
```

**Use case:** "Only notify me when prices are objectively cheap/expensive"

#### Gap Tolerance (for Level Filter)

**What:** Allow some "mediocre" intervals within an otherwise good period
**Default:** 0 (strict)
**Range:** 0-10

```yaml
best_price_max_level: cheap
best_price_max_level_gap_count: 2 # Allow up to 2 NORMAL intervals per period
```

**Use case:** "Don't split periods just because one interval isn't perfectly CHEAP"

---

## Understanding Relaxation

### What Is Relaxation?

Sometimes, strict filters find too few periods (or none). **Relaxation automatically loosens filters** until a minimum number of periods is found.

### How to Enable

```yaml
enable_min_periods_best: true
min_periods_best: 2 # Try to find at least 2 periods per day
relaxation_step_best: 35 # Increase flex by 35% per step (e.g., 15% → 20.25% → 27.3%)
relaxation_attempts_best: 8 # Flex levels to test (default 8 flex levels = 32 filter combinations)
```

Set the matching `relaxation_attempts_peak` value when tuning Peak Price periods. Both sliders accept 1-12 attempts, and the default of 8 flex levels translates to 32 filter-combination tries (8 flex levels × 4 filter combos) for each of Best and Peak calculations. Lower it for quick feedback, or raise it when either sensor struggles to hit the minimum-period target on volatile days.

### How It Works (Adaptive Matrix)

Relaxation uses a **matrix approach** - trying _N_ flexibility levels (your configured **relaxation attempts**) with the same 4 filter combinations. With the default of 8 attempts, that means 8 flex levels × 4 filter combinations = **32 total filter-combination tries per day**; fewer attempts mean fewer flex increases, while more attempts extend the search further before giving up.

#### Phase Matrix

For each day, the system tries:

**Flexibility Levels (Attempts):**

1. Attempt 1 = Original flex (e.g., 15%)
2. Attempt 2 = +35% step (e.g., 20.25%)
3. Attempt 3 = +35% step (e.g., 27.3%)
4. Attempt 4 = +35% step (e.g., 36.9%)
5. … Attempts 5-8 (default) continue adding +35% each time
6. … Additional attempts keep extending the same pattern up to the 12-attempt maximum

**4 Filter Combinations (per flexibility level):**

1. Original filters (your configured level filter)
2. Remove level filter

**Example progression:**

```
Flex 15% + Original filters → Not enough periods
Flex 15% + Volatility=any   → Not enough periods
Flex 15% + Level=any        → Not enough periods
Flex 15% + All filters off  → Not enough periods
Flex 20.25% + Original      → SUCCESS! Found 2 periods ✓
(stops here - no need to try more)
```

### Choosing the Number of Attempts

-   **Default (8 attempts)** balances speed and completeness for most grids (32 combinations per day for both Best and Peak)
-   **Lower (1-4 attempts)** if you only want mild relaxation and keep processing time minimal
-   **Higher (9-12 attempts)** for extremely volatile days or when you must hit a strict minimum (up to 48 combinations)
-   Remember: each additional attempt adds four more filter combinations because every new flex level still runs all four filter overrides

#### Per-Day Independence

**Critical:** Each day relaxes **independently**:

```
Day 1: Finds 2 periods with flex 15% (original) → No relaxation needed
Day 2: Needs flex 27.3% + level=any → Uses relaxed settings
Day 3: Finds 2 periods with flex 15% (original) → No relaxation needed
```

**Why?** Price patterns vary daily. Some days have clear cheap/expensive windows (strict filters work), others don't (relaxation needed).

---

## Common Scenarios

### Scenario 1: Simple Best Price (Default)

**Goal:** Find the cheapest time each day to run dishwasher

**Configuration:**

```yaml
# Use defaults - no configuration needed!
best_price_flex: 15 # (default)
best_price_min_period_length: 60 # (default)
best_price_min_distance_from_avg: 2 # (default)
```

**What you get:**

-   1-3 periods per day with prices ≤ MIN + 15%
-   Each period at least 1 hour long
-   All periods at least 2% cheaper than daily average

**Automation example:**

```yaml
automation:
    - trigger:
          - platform: state
            entity_id: binary_sensor.tibber_home_best_price_period
            to: "on"
      action:
          - service: switch.turn_on
            target:
                entity_id: switch.dishwasher
```

---

## Troubleshooting

### No Periods Found

**Symptom:** `binary_sensor.tibber_home_best_price_period` never turns "on"

**Possible causes:**

1. **Filters too strict**

    ```yaml
    # Try:
    best_price_flex: 20 # Increase from default 15%
    best_price_min_distance_from_avg: 1 # Reduce from default 2%
    ```

2. **Period length too long**

    ```yaml
    # Try:
    best_price_min_period_length: 45 # Reduce from default 60 minutes
    ```

3. **Flat price curve** (all prices very similar)

    - Enable relaxation to ensure at least some periods

    ```yaml
    enable_min_periods_best: true
    min_periods_best: 1
    ```

### Periods Split Into Small Pieces

**Symptom:** Many short periods instead of one long period

**Possible causes:**

1. **Level filter too strict**

    ```yaml
    # One "NORMAL" interval splits an otherwise good period
    # Solution: Use gap tolerance
    best_price_max_level: cheap
    best_price_max_level_gap_count: 2 # Allow 2 NORMAL intervals
    ```

2. **Flexibility too tight**

    ```yaml
    # One interval just outside flex range splits the period
    # Solution: Increase flexibility
    best_price_flex: 20 # Increase from 15%
    ```

3. **Price spikes breaking periods**

    - Statistical outlier filtering should handle this automatically
    - Check logs for smoothing activity:

    ```
    DEBUG: [2025-11-11T14:30:00+01:00] Outlier detected: 35.2 ct
    DEBUG:   Smoothed to: 20.7 ct (trend prediction)
    ```

    - If smoothing isn't working as expected, check:
        - Is spike truly isolated? (3+ similar prices in a row won't be smoothed)
        - Is it a legitimate price shift? (symmetry check preserves morning/evening peaks)

### Understanding Sensor Attributes

**Check period details:**

```yaml
# Entity: binary_sensor.tibber_home_best_price_period

# Attributes when "on":
start: "2025-11-11T02:00:00+01:00"
end: "2025-11-11T05:00:00+01:00"
duration_minutes: 180
rating_level: "LOW" # All intervals are LOW price
price_avg: 18.5 # Average price in this period
relaxation_active: true # This day used relaxation
relaxation_level: "price_diff_20.25%+level_any" # Found at flex 20.25%, level filter removed
period_interval_smoothed_count: 2 # 2 outliers were smoothed (only if >0)
period_interval_level_gap_count: 1 # 1 interval kept via gap tolerance (only if >0)
```

---

## Advanced Topics

For advanced configuration patterns and technical deep-dive, see:

-   [Automation Examples](./automation-examples.md) - Real-world automation patterns
-   [Services](./services.md) - Using the `tibber_prices.get_price` service for custom logic

### Quick Reference

**Configuration Parameters:**

| Parameter                          | Default | Range            | Purpose                        |
| ---------------------------------- | ------- | ---------------- | ------------------------------ |
| `best_price_flex`                  | 15%     | 0-100%           | Search range from daily MIN    |
| `best_price_min_period_length`     | 60 min  | 15-240           | Minimum duration               |
| `best_price_min_distance_from_avg` | 2%      | 0-20%            | Quality threshold              |
| `best_price_max_level`             | any     | any/cheap/vcheap | Absolute quality               |
| `best_price_max_level_gap_count`   | 0       | 0-10             | Gap tolerance                  |
| `enable_min_periods_best`          | false   | true/false       | Enable relaxation              |
| `min_periods_best`                 | -       | 1-10             | Target periods per day         |
| `relaxation_step_best`             | -       | 5-100%           | Relaxation increment           |
| `relaxation_attempts_best`         | 8       | 1-12             | Flex levels (attempts) per day |

**Peak Price:** Same parameters with `peak_price_*` prefix (defaults: flex=-15%, same otherwise)

### Price Levels Reference

The Tibber API provides price levels for each 15-minute interval:

**Levels (based on trailing 24h average):**

-   `VERY_CHEAP` - Significantly below average
-   `CHEAP` - Below average
-   `NORMAL` - Around average
-   `EXPENSIVE` - Above average
-   `VERY_EXPENSIVE` - Significantly above average

### Outlier Filtering Technical Details

**Algorithm:**

1. **Linear regression**: Predicts expected price based on surrounding trend
2. **Confidence intervals**: 2 standard deviations (95% confidence)
3. **Symmetry check**: Rejects asymmetric outliers (1.5 std dev threshold)
4. **Enhanced zigzag detection**: Catches spike clusters with relative volatility (2.0× threshold)

**Constants:**

-   `CONFIDENCE_LEVEL`: 2.0 (95% confidence)
-   `SYMMETRY_THRESHOLD`: 1.5 std dev
-   `RELATIVE_VOLATILITY_THRESHOLD`: 2.0
-   `MIN_CONTEXT_SIZE`: 3 intervals minimum

**Data integrity:**

-   Smoothed intervals stored with `_original_price` field
-   All statistics (min/max/avg) use original prices
-   Period attributes show impact: `period_interval_smoothed_count`
-   Smart counting: Only counts smoothing that actually changed period formation

---

**Last updated:** November 15, 2025
**Integration version:** 2.0+
