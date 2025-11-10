# Period Calculation

A detailed explanation of how Best Price and Peak Price periods are calculated and how you can influence the calculation with configuration options.

## Table of Contents

- [Overview](#overview)
- [Calculation Flow](#calculation-flow)
- [Configuration Options in Detail](#configuration-options-in-detail)
- [Filter Pipeline](#filter-pipeline)
- [Gap Tolerance for Level Filters](#gap-tolerance-for-level-filters)
- [Relaxation Mechanism](#relaxation-mechanism)
- [Practical Examples](#practical-examples)
- [Troubleshooting](#troubleshooting)

---

## Overview

### What are Price Periods?

The integration automatically calculates **Best Price Periods** (cheap time windows) and **Peak Price Periods** (expensive time windows) for each day. These periods help you:

- **Best Price**: Shift electricity consumption to cheap times (e.g., charge electric car, run dishwasher, washing machine, heat pump water heater)
- **Peak Price**: Avoid high consumption during expensive times (e.g., reduce heating temporarily, defer non-essential loads)

### Basic Principle

The calculation happens in **two main steps**:

1. **Period Identification**: Find contiguous time ranges that differ significantly from the daily average
2. **Filter Application**: Apply various filters to keep only relevant periods

Both steps can be influenced by configuration options.

---

## Calculation Flow

### Step 1: Data Preparation

**What happens:**
- Fetch all price intervals for today (96 x 15-minute intervals = 24 hours)
- Calculate daily average price
- Calculate trailing 24h average for each interval

**Example:**
```
Today: 96 intervals from 00:00 to 23:59
Average price today: 25.5 ct/kWh
```

### Step 2: Period Identification (Flexibility)

**What happens:**
- Search for contiguous intervals that are **significantly cheaper** (Best Price) or **more expensive** (Peak Price) than the average
- "Significant" is defined by the **flexibility** setting

**Configuration:**
- `best_price_flex` (default: 15%) - How much cheaper than average?
- `peak_price_flex` (default: -15%) - How much more expensive than average?

**Example (Best Price with 15% flexibility):**
```
Average price: 25.0 ct/kWh
Flexibility: -15%
Threshold: 25.0 - (25.0 × 0.15) = 21.25 ct/kWh

Intervals that cost ≤ 21.25 ct/kWh are grouped into periods:
00:00-00:15: 20.5 ct ✓ │
00:15-00:30: 19.8 ct ✓ ├─ Period 1 (1h)
00:30-00:45: 21.0 ct ✓ │
00:45-01:00: 20.2 ct ✓ │
01:00-01:15: 26.5 ct ✗   (too expensive, period ends)
```

### Step 3: Minimum Period Length

**What happens:**
- Periods that are too short are discarded (not practical to use)

**Configuration:**
- `best_price_min_period_length` (default: 60 minutes)
- `peak_price_min_period_length` (default: 60 minutes)

**Example:**
```
Found periods:
- 00:00-01:00 (60 min) ✓ Keep
- 03:00-03:30 (30 min) ✗ Discard (too short)
- 14:00-15:15 (75 min) ✓ Keep
```

### Step 4: Minimum Distance from Average

**What happens:**
- Periods must have **additional** distance from the daily average beyond flexibility
- Prevents marking "almost normal" prices as "Best/Peak" on days with small price spread

**Configuration:**
- `best_price_min_distance_from_avg` (default: 2%) - Additional distance below average
- `peak_price_min_distance_from_avg` (default: 2%) - Additional distance above average

**Example (Best Price):**
```
Daily average: 25.0 ct/kWh
Flexibility threshold: 21.25 ct/kWh (from Step 2)
Minimum distance: 2%

Final check for each interval:
1. Price ≤ flexibility threshold? (21.25 ct)
2. AND price ≤ average × (1 - 0.02)? (24.5 ct)

Interval with 23.0 ct:
  ✗ Meets flexibility (23.0 > 21.25)
  ✓ Meets minimum distance (23.0 < 24.5)
  → REJECTED (both conditions must be met)
```

### Step 5: Filter Application

**What happens:**
- Apply optional filters (volatility, price level)
- See [Filter Pipeline](#filter-pipeline) for details

---

## Configuration Options in Detail

### Best Price Period Settings

| Option | Default | Description | Acts in Step |
|--------|---------|-------------|--------------|
| `best_price_flex` | 15% | How much cheaper than average must a period be? | 2 (Identification) |
| `best_price_min_period_length` | 60 min | Minimum length of a period | 3 (Length filter) |
| `best_price_min_distance_from_avg` | 2% | Additional minimum distance below daily average | 4 (Quality filter) |
| `best_price_min_volatility` | LOW | Minimum volatility within the period (optional) | 5 (Volatility filter) |
| `best_price_max_level` | ANY | Maximum price level (optional, e.g., only CHEAP or better) | 5 (Level filter) |
| `best_price_max_level_gap_count` | 0 | Tolerance for level deviations (see [Gap Tolerance](#gap-tolerance-for-level-filters)) | 5 (Level filter) |
| `enable_min_periods_best` | Off | Enables relaxation mechanism | - (Relaxation) |
| `min_periods_best` | 2 | Minimum number of periods to achieve | - (Relaxation) |
| `relaxation_step_best` | 25% | Step size for filter relaxation | - (Relaxation) |

### Peak Price Period Settings

| Option | Default | Description | Acts in Step |
|--------|---------|-------------|--------------|
| `peak_price_flex` | -15% | How much more expensive than average must a period be? | 2 (Identification) |
| `peak_price_min_period_length` | 60 min | Minimum length of a period | 3 (Length filter) |
| `peak_price_min_distance_from_avg` | 2% | Additional minimum distance above daily average | 4 (Quality filter) |
| `peak_price_min_volatility` | LOW | Minimum volatility within the period (optional) | 5 (Volatility filter) |
| `peak_price_min_level` | ANY | Minimum price level (optional, e.g., only EXPENSIVE or higher) | 5 (Level filter) |
| `peak_price_max_level_gap_count` | 0 | Tolerance for level deviations (see [Gap Tolerance](#gap-tolerance-for-level-filters)) | 5 (Level filter) |
| `enable_min_periods_peak` | Off | Enables relaxation mechanism | - (Relaxation) |
| `min_periods_peak` | 2 | Minimum number of periods to achieve | - (Relaxation) |
| `relaxation_step_peak` | 25% | Step size for filter relaxation | - (Relaxation) |

---

## Filter Pipeline

After basic period identification (Steps 1-4), two optional **additional filters** can be applied:

### Volatility Filter

**Purpose:** Only show periods when the price spread within the period is large enough.

**Use case:**
- **Best Price**: "I only want to optimize when it's really worth it" (high volatility)
- **Peak Price**: "Only warn me about large price swings" (high volatility)

**How it works:**
```
Period: 00:00-01:00
Intervals: 20.5 | 19.8 | 21.0 | 20.2 ct/kWh
Min: 19.8 ct, Max: 21.0 ct
Volatility (spread): 21.0 - 19.8 = 1.2 ct/kWh

Volatility thresholds:
- LOW: < 5.0 ct   → This period: LOW
- MODERATE: 5-15 ct
- HIGH: 15-30 ct
- VERY_HIGH: ≥ 30 ct

best_price_min_volatility = "MODERATE" (5 ct)
→ Period is REJECTED (1.2 ct < 5.0 ct)
```

**Configuration:**
- `best_price_min_volatility`: `low` | `moderate` | `high` | `very_high`
- `peak_price_min_volatility`: `low` | `moderate` | `high` | `very_high`

**Default:** `low` (filter disabled, all periods shown)

### Level Filter (Price Level)

**Purpose:** Only show periods that are actually cheap/expensive in absolute terms, not just relative to the daily average.

**Use case:**
- **Best Price**: "Only show best price when there's at least one CHEAP interval" (not just "less expensive than usual today")
- **Peak Price**: "Only show peak price when there's at least one EXPENSIVE interval" (not just "more expensive than average")

**Price levels (from Tibber API):**
- `VERY_CHEAP` (-2)
- `CHEAP` (-1)
- `NORMAL` (0)
- `EXPENSIVE` (+1)
- `VERY_EXPENSIVE` (+2)

**How it works (Best Price example):**
```
best_price_max_level = "CHEAP"

Period: 00:00-01:00
Intervals with levels:
  00:00: 20.5 ct → CHEAP ✓
  00:15: 19.8 ct → VERY_CHEAP ✓
  00:30: 21.0 ct → NORMAL ✗
  00:45: 20.2 ct → CHEAP ✓

Filter logic (without gap tolerance):
  → Does the period have at least ONE interval with level ≤ CHEAP?
  → YES (three intervals are CHEAP or better)
  → Period is KEPT

But: One NORMAL interval in the middle!
  → Without gap tolerance: Period is split into two parts
  → With gap tolerance: Period stays together (see next section)
```

**Configuration:**
- `best_price_max_level`: `any` | `very_cheap` | `cheap` | `normal` | `expensive`
- `peak_price_min_level`: `any` | `expensive` | `normal` | `cheap` | `very_cheap`

**Default:** `any` (filter disabled)

---

## Gap Tolerance for Level Filters

### Problem Without Gap Tolerance

When you activate a level filter (e.g., `best_price_max_level = "CHEAP"`), periods are **strictly filtered**:

```
Period: 00:00-02:00 (2 hours)
Intervals:
  00:00-01:30: CHEAP, CHEAP, CHEAP, CHEAP, CHEAP, CHEAP
  01:30-01:45: NORMAL  ← A single deviating interval!
  01:45-02:00: CHEAP

Without gap tolerance:
  → Period is split into TWO periods:
    1. 00:00-01:30 (1.5h)
    2. 01:45-02:00 (0.25h) ✗ too short, discarded!
  → Result: Only 1.5h best price instead of 2h
```

### Solution: Gap Tolerance

**Gap tolerance** allows a configurable number of intervals that deviate by **exactly one level step** from the required level.

**How it works:**

1. **"Gap" definition:** An interval that deviates by exactly 1 level step
   ```
   Best Price filter: CHEAP (-1)
   NORMAL (0) is +1 step → GAP ✓
   EXPENSIVE (+1) is +2 steps → NOT A GAP, too far away
   ```

2. **Gap counting:** Max X gaps allowed per period (configurable: 0-8)

3. **Minimum distance between gaps:** Gaps must not be too close together
   ```
   Dynamic formula: max(2, (interval_count / max_gaps) / 2)

   Example: 16 intervals, max 2 gaps allowed
   → Minimum distance: max(2, (16/2)/2) = max(2, 4) = 4 intervals

   CHEAP, CHEAP, CHEAP, CHEAP, NORMAL, CHEAP, CHEAP, CHEAP, NORMAL, CHEAP
            ↑                    GAP1           ↑            GAP2
            └─────── 4 intervals ──────────────┘
   → OK, minimum distance maintained
   ```

4. **25% cap:** Maximum 25% of a period's intervals can be gaps
   ```
   Period: 12 intervals, user configured 5 gaps
   → Effective: min(5, 12/4) = min(5, 3) = 3 gaps allowed
   ```

5. **Minimum period length:** Gap tolerance only applies to periods ≥ 1.5h (6 intervals)
   ```
   Period < 1.5h: Strict filtering (0 tolerance)
   Period ≥ 1.5h: Gap tolerance as configured
   ```

### Gap Cluster Splitting

If a period would still be rejected **despite gap tolerance** (too many gaps or too dense), the integration tries to **intelligently split** it:

```
Period: 00:00-04:00 (16 intervals)
CHEAP, CHEAP, CHEAP, NORMAL, NORMAL, NORMAL, CHEAP, CHEAP, ..., CHEAP
                      └─ Gap cluster (3×) ─┘

Gap cluster = 2+ consecutive deviating intervals

→ Splitting at gap cluster:
  1. 00:00-00:45 (3 intervals) ✗ too short
  2. 01:30-04:00 (10 intervals) ✓ kept

→ Result: 2.5h best price instead of complete rejection
```

### Configuration

**Best Price:**
```yaml
best_price_max_level: "cheap"           # Enable level filter
best_price_max_level_gap_count: 2       # Allow 2 NORMAL intervals per period
```

**Peak Price:**
```yaml
peak_price_min_level: "expensive"       # Enable level filter
peak_price_max_level_gap_count: 1       # Allow 1 NORMAL interval per period
```

**Default:** `0` (no tolerance, strict filtering)

### Example Scenarios

#### Scenario 1: Conservative (0 gaps)
```yaml
best_price_max_level: "cheap"
best_price_max_level_gap_count: 0  # Default
```

**Behavior:**
- Every interval MUST be CHEAP or better
- A single NORMAL interval → period is split

**Good for:** Users who want absolute price guarantees

#### Scenario 2: Moderate (2-3 gaps)
```yaml
best_price_max_level: "cheap"
best_price_max_level_gap_count: 2
```

**Behavior:**
- Up to 2 NORMAL intervals per period tolerated
- Minimum distance between gaps dynamically calculated
- 25% cap protects against too many gaps

**Good for:** Most users - balance between quality and period length

#### Scenario 3: Aggressive (5-8 gaps)
```yaml
best_price_max_level: "cheap"
best_price_max_level_gap_count: 5
```

**Behavior:**
- Up to 5 NORMAL intervals (but max 25% of period)
- Longer periods possible
- Quality may suffer (more "not-quite-so-cheap" intervals)

**Good for:** Users with flexible devices that need long run times

---

## Relaxation Mechanism

If **too few periods** are found despite all filters, the integration can automatically **gradually relax** filters.

### When is Relaxation Applied?

Only when **both conditions** are met:
1. `enable_min_periods_best/peak` is enabled
2. Fewer than `min_periods_best/peak` periods found

### Relaxation Levels

The integration tries to relax filters in this order:

#### Level 1: Relax Flexibility
```
Original: best_price_flex = 15%
Step 1: 15% + (15% × 0.25) = 18.75%
Step 2: 18.75% + (18.75% × 0.25) = 23.44%
Step 3: ...
```

**Calculation:** `new_flexibility = old_flexibility × (1 + relaxation_step / 100)`

#### Level 2: Disable Volatility Filter
```
If flexibility relaxation isn't enough:
  → best_price_min_volatility = "any" (filter off)
```

#### Level 3: Disable All Filters
```
If still too few periods:
  → Volatility = "any"
  → Level filter = "any"
  → Only flexibility and minimum length active
```

### Relaxation Status

The sensors show the **relaxation status** as an attribute:

```yaml
Best Price Period:  # sensor.tibber_home_best_price_period
  state: "on"
  attributes:
    relaxation_level: "volatility_any"  # Volatility filter was disabled
```

**Possible values:**
- `none` - No relaxation, normal filters
- `volatility_any` - Volatility filter disabled
- `all_filters_off` - All optional filters disabled

### Example Configuration

```yaml
# Best Price: Try to find at least 2 periods
enable_min_periods_best: true
min_periods_best: 2
relaxation_step_best: 25  # 25% per step

best_price_flex: 15
best_price_min_volatility: "moderate"
```

**Process on a day with little price spread:**
1. Try with 15% flex + MODERATE volatility → 0 periods
2. Relax to 18.75% flex → 1 period
3. Relax to 23.44% flex → 1 period (still < 2)
4. Disable volatility filter → 2 periods ✓

**Result:** User sees 2 periods with `relaxation_level: "volatility_any"`

---

## Practical Examples

### Example 1: Standard Configuration (Best Price)

**Configuration:**
```yaml
best_price_flex: 15
best_price_min_period_length: 60
best_price_min_distance_from_avg: 2
best_price_min_volatility: "low"  # Filter disabled
best_price_max_level: "any"  # Filter disabled
```

**Daily prices:**
```
Average: 25.0 ct/kWh
00:00-02:00: 19-21 ct (cheap)
06:00-08:00: 28-30 ct (expensive)
12:00-14:00: 24-26 ct (normal)
18:00-20:00: 20-22 ct (cheap)
```

**Calculation:**
1. Flexibility threshold: 25.0 - (25.0 × 0.15) = 21.25 ct
2. Minimum distance threshold: 25.0 × (1 - 0.02) = 24.5 ct
3. Both conditions: Price ≤ 21.25 ct

**Result:**
- ✓ 00:00-02:00 (19-21 ct, all ≤ 21.25)
- ✗ 06:00-08:00 (too expensive)
- ✗ 12:00-14:00 (24-26 ct, not cheap enough)
- ✓ 18:00-20:00 (20-22 ct, all ≤ 21.25)

**2 Best Price periods found!**

### Example 2: Strict Level Filter Without Gap Tolerance

**Configuration:**
```yaml
best_price_flex: 15
best_price_max_level: "cheap"
best_price_max_level_gap_count: 0  # No tolerance
```

**Period candidate:**
```
00:00-02:00:
  00:00-01:30: CHEAP, CHEAP, CHEAP, CHEAP, CHEAP, CHEAP
  01:30-01:45: NORMAL  ← Deviation!
  01:45-02:00: CHEAP
```

**Result:**
- ✗ Period is split into 00:00-01:30 and 01:45-02:00
- ✗ 01:45-02:00 too short (15 min < 60 min) → discarded
- ✓ Only 00:00-01:30 (1.5h) remains

### Example 3: Level Filter With Gap Tolerance

**Configuration:**
```yaml
best_price_flex: 15
best_price_max_level: "cheap"
best_price_max_level_gap_count: 2  # 2 gaps allowed
```

**Period candidate (same as above):**
```
00:00-02:00:
  00:00-01:30: CHEAP, CHEAP, CHEAP, CHEAP, CHEAP, CHEAP
  01:30-01:45: NORMAL  ← Gap (1 of 2 allowed)
  01:45-02:00: CHEAP
```

**Gap tolerance check:**
- Gaps found: 1 (NORMAL)
- Max allowed: 2
- 25% cap: min(2, 8/4) = 2 (8 intervals)
- Minimum distance: N/A (only 1 gap)

**Result:**
- ✓ Period stays as a whole: 00:00-02:00 (2h)
- 1 NORMAL interval is tolerated

### Example 4: Gap Cluster Gets Split

**Configuration:**
```yaml
best_price_flex: 15
best_price_max_level: "cheap"
best_price_max_level_gap_count: 2
```

**Period candidate:**
```
00:00-04:00 (16 intervals):
  00:00-01:00: CHEAP, CHEAP, CHEAP, CHEAP (4)
  01:00-02:00: NORMAL, NORMAL, NORMAL, NORMAL (4) ← Gap cluster!
  02:00-04:00: CHEAP, CHEAP, CHEAP, ..., CHEAP (8)
```

**Gap tolerance check:**
- Gaps found: 4 (too many)
- Max allowed: 2
- → Normal check fails

**Gap cluster splitting:**
- Detect cluster: 4× consecutive NORMAL intervals
- Split period at cluster boundaries:
  1. 00:00-01:00 (4 intervals = 60 min) ✓
  2. 02:00-04:00 (8 intervals = 120 min) ✓

**Result:**
- ✓ Two separate periods: 00:00-01:00 and 02:00-04:00
- Total 3h best price (instead of complete rejection)

### Example 5: Relaxation in Action

**Configuration:**
```yaml
enable_min_periods_best: true
min_periods_best: 2
relaxation_step_best: 25

best_price_flex: 10  # Very strict!
best_price_min_volatility: "high"  # Very strict!
```

**Day with little price spread:**
```
Average: 25.0 ct/kWh
All prices between 23-27 ct (low volatility)
```

**Relaxation process:**

1. **Attempt 1:** 10% flex + HIGH volatility
   ```
   Threshold: 22.5 ct
   No period meets both conditions
   → 0 periods (< 2 required)
   ```

2. **Attempt 2:** 12.5% flex + HIGH volatility
   ```
   Threshold: 21.875 ct
   Still 0 periods
   ```

3. **Attempt 3:** Disable volatility filter
   ```
   12.5% flex + ANY volatility
   → 1 period found (< 2)
   ```

4. **Attempt 4:** 15.625% flex + ANY volatility
   ```
   Threshold: 21.09 ct
   → 2 periods found ✓
   ```

**Result:**
- Sensor shows 2 periods with `relaxation_level: "volatility_any"`
- User knows: "Filters were relaxed to reach minimum count"

---

## Troubleshooting

### Problem: No Periods Found

**Possible causes:**

1. **Too strict flexibility**
   ```
   best_price_flex: 5  # Only 5% cheaper than average
   ```
   **Solution:** Increase to 10-15%

2. **Too strict level filter without gap tolerance**
   ```
   best_price_max_level: "very_cheap"
   best_price_max_level_gap_count: 0
   ```
   **Solution:** Relax level to "cheap" or enable gap tolerance (1-2)

3. **Too high volatility requirement**
   ```
   best_price_min_volatility: "very_high"
   ```
   **Solution:** Reduce to "moderate" or "low"

4. **Too long minimum period length**
   ```
   best_price_min_period_length: 180  # 3 hours
   ```
   **Solution:** Reduce to 60-90 minutes

5. **Day with very small price spread**
   ```
   All prices between 24-26 ct (hardly any differences)
   ```
   **Solution:** Enable relaxation mechanism:
   ```yaml
   enable_min_periods_best: true
   min_periods_best: 1
   ```

### Problem: Too Many Periods

**Solution:** Make filters stricter:

```yaml
best_price_flex: 20  # Reduce to 10-15
best_price_min_volatility: "moderate"  # Require higher volatility
best_price_max_level: "cheap"  # Only truly cheap times
```

### Problem: Periods Are Too Short

**Solution:** Increase minimum length and use gap tolerance:

```yaml
best_price_min_period_length: 90  # 1.5 hours
best_price_max_level_gap_count: 2  # Tolerate deviations
```

### Problem: Periods With "Mediocre" Prices

**Solution:** Increase minimum distance:

```yaml
best_price_min_distance_from_avg: 5  # Must be 5% below average
```

### Problem: Relaxation Applied Too Aggressively

**Solution:** Reduce step size:

```yaml
relaxation_step_best: 10  # Smaller steps (instead of 25)
```

Or disable relaxation completely:

```yaml
enable_min_periods_best: false
```

### Problem: Gap Tolerance Not Working As Expected

**Possible causes:**

1. **Period too short (< 1.5h)**
   ```
   Gap tolerance only applies to periods ≥ 1.5h
   ```
   **Solution:** Reduce `best_price_min_period_length` or adjust flexibility

2. **25% cap limiting effective gaps**
   ```
   Period: 8 intervals, configured 4 gaps
   → Effective: min(4, 8/4) = 2 gaps
   ```
   **Solution:** Accept limitation or relax level filter

3. **Gaps too close together**
   ```
   Minimum distance between gaps not maintained
   ```
   **Solution:** Increase gap count or accept splitting

---

## Further Documentation

- **[Configuration Guide](configuration.md)** - UI screenshots and step-by-step guide
- **[Sensors](sensors.md)** - All available sensors and attributes
- **[Automation Examples](automation-examples.md)** - Practical automation recipes with periods
- **[Developer Documentation](../development/)** - Code architecture and algorithm details

---

**Questions or feedback?** Open an [issue on GitHub](https://github.com/jpawlowski/hass.tibber_prices/issues)!
