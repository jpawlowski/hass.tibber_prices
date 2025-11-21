# Period Calculation

Learn how Best Price and Peak Price periods work, and how to configure them for your needs.

## Table of Contents

-   [Quick Start](#quick-start)
-   [How It Works](#how-it-works)
-   [Configuration Guide](#configuration-guide)
-   [Understanding Relaxation](#understanding-relaxation)
-   [Common Scenarios](#common-scenarios)
-   [Troubleshooting](#troubleshooting)
    -   [No Periods Found](#no-periods-found)
    -   [Periods Split Into Small Pieces](#periods-split-into-small-pieces)
    -   [Midnight Price Classification Changes](#midnight-price-classification-changes)
-   [Advanced Topics](#advanced-topics)

---

## Quick Start

### What Are Price Periods?

The integration finds time windows when electricity is especially **cheap** (Best Price) or **expensive** (Peak Price):

-   **Best Price Periods** 🟢 - When to run your dishwasher, charge your EV, or heat water
-   **Peak Price Periods** 🔴 - When to reduce consumption or defer non-essential loads

### Default Behavior

Out of the box, the integration:

1. **Best Price**: Finds cheapest 1-hour+ windows that are at least 5% below the daily average
2. **Peak Price**: Finds most expensive 30-minute+ windows that are at least 5% above the daily average
3. **Relaxation**: Automatically loosens filters if not enough periods are found

**Most users don't need to change anything!** The defaults work well for typical use cases.

<details>
<summary>ℹ️ Why do Best Price and Peak Price have different defaults?</summary>

The integration sets different **initial defaults** because the features serve different purposes:

**Best Price (60 min, 15% flex):**
- Longer duration ensures appliances can complete their cycles
- Stricter flex (15%) focuses on genuinely cheap times
- Use case: Running dishwasher, EV charging, water heating

**Peak Price (30 min, 20% flex):**
- Shorter duration acceptable for early warnings
- More flexible (20%) catches price spikes earlier
- Use case: Alerting to expensive periods, even brief ones

**You can adjust all these values** in the configuration if the defaults don't fit your use case. The asymmetric defaults simply provide good starting points for typical scenarios.
</details>

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
Minimum distance: 5% (default)

Best Price: Must be ≤ 28.5 ct/kWh (30 - 5%)
Peak Price: Must be ≥ 31.5 ct/kWh (30 + 5%)
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

#### 5. Automatic Price Spike Smoothing

Isolated price spikes are automatically detected and smoothed to prevent unnecessary period fragmentation:

```
Original prices: 18, 19, 35, 20, 19 ct   ← 35 ct is an isolated outlier
Smoothed:        18, 19, 19, 20, 19 ct   ← Spike replaced with trend prediction

Result: Continuous period 00:00-01:15 instead of split periods
```

**Important:**
-   Original prices are always preserved (min/max/avg show real values)
-   Smoothing only affects which intervals are combined into periods
-   The attribute `period_interval_smoothed_count` shows if smoothing was active

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

**💡 Tip:** Very high flexibility (>30%) is rarely useful. **Recommendation:** Start with 15-20% and enable relaxation – it adapts automatically to each day's price pattern.

#### Minimum Period Length

**What:** How long a period must be to show it
**Default:** 60 minutes (Best Price), 30 minutes (Peak Price)
**Range:** 15-240 minutes

```yaml
best_price_min_period_length: 60
peak_price_min_period_length: 30
```

**When to adjust:**

-   **Increase (90-120 min)** → Only show longer periods (e.g., for heat pump cycles)
-   **Decrease (30-45 min)** → Show shorter windows (e.g., for quick tasks)

#### Distance from Average

**What:** How much better than average a period must be
**Default:** 5%
**Range:** 0-20%

```yaml
best_price_min_distance_from_avg: 5
peak_price_min_distance_from_avg: 5
```

**When to adjust:**

-   **Increase (5-10%)** → Only show clearly better times
-   **Decrease (0-1%)** → Show any time below/above average

**ℹ️ Note:** Both flexibility and distance filters must be satisfied. When using high flexibility values (>30%), the distance filter may become the limiting factor. For best results, use moderate flexibility (15-20%) with relaxation enabled.

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

**ℹ️ Volatility Thresholds:** The level filter also supports volatility-based levels (`volatility_low`, `volatility_medium`, `volatility_high`). These use **fixed internal thresholds** (LOW < 10%, MEDIUM < 20%, HIGH ≥ 20%) that are separate from the sensor volatility thresholds you configure in the UI. This separation ensures that changing sensor display preferences doesn't affect period calculation behavior.

#### Gap Tolerance (for Level Filter)

**What:** Allow some "mediocre" intervals within an otherwise good period
**Default:** 0 (strict)
**Range:** 0-10

```yaml
best_price_max_level: cheap
best_price_max_level_gap_count: 2 # Allow up to 2 NORMAL intervals per period
```

**Use case:** "Don't split periods just because one interval isn't perfectly CHEAP"

### Tweaking Strategy: What to Adjust First?

When you're not happy with the default behavior, adjust settings in this order:

#### 1. **Start with Relaxation (Easiest)**

If you're not finding enough periods:

```yaml
enable_min_periods_best: true   # Already default!
min_periods_best: 2             # Already default!
relaxation_attempts_best: 11    # Already default!
```

**Why start here?** Relaxation automatically finds the right balance for each day. Much easier than manual tuning.

#### 2. **Adjust Period Length (Simple)**

If periods are too short/long for your use case:

```yaml
best_price_min_period_length: 90  # Increase from 60 for longer periods
# OR
best_price_min_period_length: 45  # Decrease from 60 for shorter periods
```

**Safe to change:** This only affects duration, not price selection logic.

#### 3. **Fine-tune Flexibility (Moderate)**

If you consistently want more/fewer periods:

```yaml
best_price_flex: 20  # Increase from 15% for more periods
# OR
best_price_flex: 10  # Decrease from 15% for stricter selection
```

**⚠️ Watch out:** Values >25% may conflict with distance filter. Use relaxation instead.

#### 4. **Adjust Distance from Average (Advanced)**

Only if periods seem "mediocre" (not really cheap/expensive):

```yaml
best_price_min_distance_from_avg: 10  # Increase from 5% for stricter quality
```

**⚠️ Careful:** High values (>10%) can make it impossible to find periods on flat price days.

#### 5. **Enable Level Filter (Expert)**

Only if you want absolute quality requirements:

```yaml
best_price_max_level: cheap  # Only show objectively CHEAP periods
```

**⚠️ Very strict:** Many days may have zero qualifying periods. **Always enable relaxation when using this!**

### Common Mistakes to Avoid

❌ **Don't increase flexibility to >30% manually** → Use relaxation instead
❌ **Don't combine high distance (>10%) with strict level filter** → Too restrictive
❌ **Don't disable relaxation with strict filters** → You'll get zero periods on some days
❌ **Don't change all settings at once** → Adjust one at a time and observe results

✅ **Do use defaults + relaxation** → Works for 90% of cases
✅ **Do adjust one setting at a time** → Easier to understand impact
✅ **Do check sensor attributes** → Shows why periods were/weren't found

---

## Understanding Relaxation

### What Is Relaxation?

Sometimes, strict filters find too few periods (or none). **Relaxation automatically loosens filters** until a minimum number of periods is found.

### How to Enable

```yaml
enable_min_periods_best: true
min_periods_best: 2 # Try to find at least 2 periods per day
relaxation_attempts_best: 11 # Flex levels to test (default: 11 steps = 22 filter combinations)
```

**ℹ️ Good news:** Relaxation is **enabled by default** with sensible settings. Most users don't need to change anything here!

Set the matching `relaxation_attempts_peak` value when tuning Peak Price periods. Both sliders accept 1-12 attempts, and the default of 11 flex levels translates to 22 filter-combination tries (11 flex levels × 2 filter combos) for each of Best and Peak calculations. Lower it for quick feedback, or raise it when either sensor struggles to hit the minimum-period target on volatile days.

### Why Relaxation Is Better Than Manual Tweaking

**Problem with manual settings:**
- You set flex to 25% → Works great on Monday (volatile prices)
- Same 25% flex on Tuesday (flat prices) → Finds "best price" periods that aren't really cheap
- You're stuck with one setting for all days

**Solution with relaxation:**
- Monday (volatile): Uses flex 15% (original) → Finds 2 perfect periods ✓
- Tuesday (flat): Escalates to flex 21% → Finds 2 decent periods ✓
- Wednesday (mixed): Uses flex 18% → Finds 2 good periods ✓

**Each day gets exactly the flexibility it needs!**

### How It Works (Adaptive Matrix)

Relaxation uses a **matrix approach** - trying _N_ flexibility levels (your configured **relaxation attempts**) with 2 filter combinations per level. With the default of 11 attempts, that means 11 flex levels × 2 filter combinations = **22 total filter-combination tries per day**; fewer attempts mean fewer flex increases, while more attempts extend the search further before giving up.

**Important:** The flexibility increment is **fixed at 3% per step** (hard-coded for reliability). This means:
- Base flex 15% → 18% → 21% → 24% → ... → 48% (with 11 attempts)
- Base flex 20% → 23% → 26% → 29% → ... → 50% (with 11 attempts)

#### Phase Matrix

For each day, the system tries:

**Flexibility Levels (Attempts):**

1. Attempt 1 = Original flex (e.g., 15%)
2. Attempt 2 = +3% step (18%)
3. Attempt 3 = +3% step (21%)
4. Attempt 4 = +3% step (24%)
5. … Attempts 5-11 (default) continue adding +3% each time
6. … Additional attempts keep extending the same pattern up to the 12-attempt maximum (up to 51%)

**2 Filter Combinations (per flexibility level):**

1. Original filters (your configured level filter)
2. Remove level filter (level=any)

**Example progression:**

```
Flex 15% + Original filters → Not enough periods
Flex 15% + Level=any        → Not enough periods
Flex 18% + Original filters → Not enough periods
Flex 18% + Level=any        → SUCCESS! Found 2 periods ✓
(stops here - no need to try more)
```

### Choosing the Number of Attempts

-   **Default (11 attempts)** balances speed and completeness for most grids (22 combinations per day for both Best and Peak)
-   **Lower (4-8 attempts)** if you only want mild relaxation and keep processing time minimal (reaches ~27-39% flex)
-   **Higher (12 attempts)** for extremely volatile days when you must reach near the 50% maximum (24 combinations)
-   Remember: each additional attempt adds two more filter combinations because every new flex level still runs both filter overrides (original + level=any)

#### Per-Day Independence

**Critical:** Each day relaxes **independently**:

```
Day 1: Finds 2 periods with flex 15% (original) → No relaxation needed
Day 2: Needs flex 21% + level=any → Uses relaxed settings
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
best_price_min_distance_from_avg: 5 # (default)
```

**What you get:**

-   1-3 periods per day with prices ≤ MIN + 15%
-   Each period at least 1 hour long
-   All periods at least 5% cheaper than daily average

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

**Common Solutions:**

1. **Check if relaxation is enabled**
   ```yaml
   enable_min_periods_best: true  # Should be true (default)
   min_periods_best: 2  # Try to find at least 2 periods
   ```

2. **If still no periods, check filters**
   - Look at sensor attributes: `relaxation_active` and `relaxation_level`
   - If relaxation exhausted all attempts: Filters too strict or flat price day

3. **Try increasing flexibility slightly**
   ```yaml
   best_price_flex: 20  # Increase from default 15%
   ```

4. **Or reduce period length requirement**
   ```yaml
   best_price_min_period_length: 45  # Reduce from default 60 minutes
   ```

### Periods Split Into Small Pieces

**Symptom:** Many short periods instead of one long period

**Common Solutions:**

1. **If using level filter, add gap tolerance**
   ```yaml
   best_price_max_level: cheap
   best_price_max_level_gap_count: 2  # Allow 2 NORMAL intervals
   ```

2. **Slightly increase flexibility**
   ```yaml
   best_price_flex: 20  # From 15% → captures wider price range
   ```

3. **Check for price spikes**
   - Automatic smoothing should handle this
   - Check attribute: `period_interval_smoothed_count`
   - If 0: Not isolated spikes, but real price levels

### Understanding Sensor Attributes

**Key attributes to check:**

```yaml
# Entity: binary_sensor.tibber_home_best_price_period

# When "on" (period active):
start: "2025-11-11T02:00:00+01:00"  # Period start time
end: "2025-11-11T05:00:00+01:00"    # Period end time
duration_minutes: 180                # Duration in minutes
price_avg: 18.5                      # Average price in the period
rating_level: "LOW"                  # All intervals have LOW rating

# Relaxation info (shows if filter loosening was needed):
relaxation_active: true              # This day needed relaxation
relaxation_level: "price_diff_18.0%+level_any"  # Found at 18% flex, level filter removed

# Optional (only shown when relevant):
period_interval_smoothed_count: 2    # Number of price spikes smoothed
period_interval_level_gap_count: 1   # Number of "mediocre" intervals tolerated
```

### Midnight Price Classification Changes

**Symptom:** A Best Price period at 23:45 suddenly changes to Peak Price at 00:00 (or vice versa), even though the absolute price barely changed.

**Why This Happens:**

This is **mathematically correct behavior** caused by how electricity prices are set in the day-ahead market:

**Market Timing:**
- The EPEX SPOT Day-Ahead auction closes at **12:00 CET** each day
- **All prices** for the next day (00:00-23:45) are set at this moment
- Late-day intervals (23:45) are priced **~36 hours before delivery**
- Early-day intervals (00:00) are priced **~12 hours before delivery**

**Why Prices Jump at Midnight:**
1. **Forecast Uncertainty:** Weather, demand, and renewable generation forecasts are more uncertain 36 hours ahead than 12 hours ahead
2. **Risk Buffer:** Late-day prices include a risk premium for this uncertainty
3. **Independent Days:** Each day has its own min/max/avg calculated from its 96 intervals
4. **Relative Classification:** Periods are classified based on their **position within the day's price range**, not absolute prices

**Example:**

```yaml
# Day 1 (low volatility, narrow range)
Price range: 18-22 ct/kWh (4 ct span)
Daily average: 20 ct/kWh
23:45: 18.5 ct/kWh → 7.5% below average → BEST PRICE ✅

# Day 2 (low volatility, narrow range)
Price range: 17-21 ct/kWh (4 ct span)
Daily average: 19 ct/kWh
00:00: 18.6 ct/kWh → 2.1% below average → PEAK PRICE ❌

# Observation: Absolute price barely changed (18.5 → 18.6 ct)
# But relative position changed dramatically:
# - Day 1: Near the bottom of the range
# - Day 2: Near the middle/top of the range
```

**When This Occurs:**
- **Low-volatility days:** When price span is narrow (< 5 ct/kWh)
- **Stable weather:** Similar conditions across multiple days
- **Market transitions:** Switching between high/low demand seasons

**How to Detect:**

Check the volatility sensors to understand if a period flip is meaningful:

```yaml
# Check daily volatility (available in integration)
sensor.tibber_home_volatility_today: 8.2%     # Low volatility
sensor.tibber_home_volatility_tomorrow: 7.9%  # Also low

# Low volatility (< 15%) means:
# - Small absolute price differences between periods
# - Classification changes may not be economically significant
# - Consider ignoring period classification on such days
```

**Handling in Automations:**

You can make your automations volatility-aware:

```yaml
# Option 1: Only act on high-volatility days
automation:
  - alias: "Dishwasher - Best Price (High Volatility Only)"
    trigger:
      - platform: state
        entity_id: binary_sensor.tibber_home_best_price_period
        to: "on"
    condition:
      - condition: numeric_state
        entity_id: sensor.tibber_home_volatility_today
        above: 15  # Only act if volatility > 15%
    action:
      - service: switch.turn_on
        entity_id: switch.dishwasher

# Option 2: Check absolute price, not just classification
automation:
  - alias: "Heat Water - Cheap Enough"
    trigger:
      - platform: state
        entity_id: binary_sensor.tibber_home_best_price_period
        to: "on"
    condition:
      - condition: numeric_state
        entity_id: sensor.tibber_home_current_interval_price_ct
        below: 20  # Absolute threshold: < 20 ct/kWh
    action:
      - service: switch.turn_on
        entity_id: switch.water_heater

# Option 3: Use per-period day volatility (available on period sensors)
automation:
  - alias: "EV Charging - Volatility-Aware"
    trigger:
      - platform: state
        entity_id: binary_sensor.tibber_home_best_price_period
        to: "on"
    condition:
      # Check if the period's day has meaningful volatility
      - condition: template
        value_template: >
          {{ state_attr('binary_sensor.tibber_home_best_price_period', 'day_volatility_%') | float(0) > 15 }}
    action:
      - service: switch.turn_on
        entity_id: switch.ev_charger
```

**Available Per-Period Attributes:**

Each period sensor exposes day volatility and price statistics:

```yaml
binary_sensor.tibber_home_best_price_period:
  day_volatility_%: 8.2         # Volatility % of the period's day
  day_price_min: 1800.0          # Minimum price of the day (ct/kWh)
  day_price_max: 2200.0          # Maximum price of the day (ct/kWh)
  day_price_span: 400.0          # Difference (max - min) in ct
```

These attributes allow automations to check: "Is the classification meaningful on this particular day?"

**Summary:**
- ✅ **Expected behavior:** Periods are evaluated per-day, midnight is a natural boundary
- ✅ **Market reality:** Late-day prices have more uncertainty than early-day prices
- ✅ **Solution:** Use volatility sensors, absolute price thresholds, or per-period day volatility attributes

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
| `best_price_min_distance_from_avg` | 5%      | 0-20%            | Quality threshold              |
| `best_price_max_level`             | any     | any/cheap/vcheap | Absolute quality               |
| `best_price_max_level_gap_count`   | 0       | 0-10             | Gap tolerance                  |
| `enable_min_periods_best`          | true    | true/false       | Enable relaxation              |
| `min_periods_best`                 | 2       | 1-10             | Target periods per day         |
| `relaxation_attempts_best`         | 11      | 1-12             | Flex levels (attempts) per day |

**Peak Price:** Same parameters with `peak_price_*` prefix (defaults: flex=-15%, same otherwise)

### Price Levels Reference

The Tibber API provides price levels for each 15-minute interval:

**Levels (based on trailing 24h average):**

-   `VERY_CHEAP` - Significantly below average
-   `CHEAP` - Below average
-   `NORMAL` - Around average
-   `EXPENSIVE` - Above average
-   `VERY_EXPENSIVE` - Significantly above average

---

**Last updated:** November 20, 2025
**Integration version:** 2.0+
