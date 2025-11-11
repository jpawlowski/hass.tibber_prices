# Period Calculation# Period Calculation



Learn how Best Price and Peak Price periods work, and how to configure them for your needs.Learn how Best Price and Peak Price periods work, and how to configure them for your needs.



## Table of Contents## Table of Contents



- [Quick Start](#quick-start)- [Quick Start](#quick-start)

- [How It Works](#how-it-works)- [How It Works](#how-it-works)

- [Configuration Guide](#configuration-guide)- [Configuration Guide](#configuration-guide)

- [Understanding Relaxation](#understanding-relaxation)- [Understanding Relaxation](#understanding-relaxation)

- [Common Scenarios](#common-scenarios)- [Common Scenarios](#common-scenarios)

- [Troubleshooting](#troubleshooting)- [Troubleshooting](#troubleshooting)

- [Advanced Topics](#advanced-topics)- [Advanced Topics](#advanced-topics)



------



## Quick Start## Quick Start



### What Are Price Periods?### What Are Price Periods?



The integration finds time windows when electricity is especially **cheap** (Best Price) or **expensive** (Peak Price):The integration finds time windows when electricity is especially **cheap** (Best Price) or **expensive** (Peak Price):



- **Best Price Periods** 🟢 - When to run your dishwasher, charge your EV, or heat water- **Best Price Periods** 🟢 - When to run your dishwasher, charge your EV, or heat water

- **Peak Price Periods** 🔴 - When to reduce consumption or defer non-essential loads- **Peak Price Periods** 🔴 - When to reduce consumption or defer non-essential loads



### Default Behavior### Default Behavior



Out of the box, the integration:Out of the box, the integration:

- ✅ Finds the cheapest time windows each day (Best Price)- ✅ Finds the cheapest time windows each day (Best Price)

- ✅ Finds the most expensive time windows each day (Peak Price)- ✅ Finds the most expensive time windows each day (Peak Price)

- ✅ Requires periods to be at least 1 hour long- ✅ Requires periods to be at least 1 hour long

- ✅ Automatically adjusts when no perfect matches exist (Relaxation)- ✅ Automatically adjusts when no perfect matches exist (Relaxation)



**Most users don't need to change anything!** The defaults work well for typical use cases.**Most users don't need to change anything!** The defaults work well for typical use cases.



------



## How It Works## How It Works



### The Basic Idea### The Basic Idea



Each day, the integration analyzes all 96 quarter-hourly price intervals and identifies **continuous time ranges** that meet specific criteria.Each day, the integration analyzes all 96 quarter-hourly price intervals and identifies **continuous time ranges** that meet specific criteria.



Think of it like this:Think of it like this:

1. **Find potential windows** - Times close to the daily MIN (Best Price) or MAX (Peak Price)1. **Find potential windows** - Times close to the daily MIN (Best Price) or MAX (Peak Price)

2. **Filter by quality** - Ensure they're meaningfully different from average2. **Filter by quality** - Ensure they're meaningfully different from average

3. **Check duration** - Must be long enough to be useful3. **Check duration** - Must be long enough to be useful

4. **Apply preferences** - Optional: only show stable prices, avoid mediocre times4. **Apply preferences** - Optional: only show stable prices, avoid mediocre times



### Step-by-Step Process### Step-by-Step Process



#### 1. Define the Search Range (Flexibility)#### 1. Define the Search Range (Flexibility)



**Best Price:** How much MORE than the daily minimum can a price be?**Best Price:** How much MORE than the daily minimum can a price be?

``````

Daily MIN: 20 ct/kWhDaily MIN: 20 ct/kWh

Flexibility: 15% (default)Flexibility: 15% (default)

→ Search for times ≤ 23 ct/kWh (20 + 15%)→ Search for times ≤ 23 ct/kWh (20 + 15%)

``````



**Peak Price:** How much LESS than the daily maximum can a price be?**Peak Price:** How much LESS than the daily maximum can a price be?

``````

Daily MAX: 40 ct/kWhDaily MAX: 40 ct/kWh

Flexibility: -15% (default)Flexibility: -15% (default)

→ Search for times ≥ 34 ct/kWh (40 - 15%)→ Search for times ≥ 34 ct/kWh (40 - 15%)

``````



**Why flexibility?** Prices rarely stay at exactly MIN/MAX. Flexibility lets you capture realistic time windows.**Why flexibility?** Prices rarely stay at exactly MIN/MAX. Flexibility lets you capture realistic time windows.



#### 2. Ensure Quality (Distance from Average)#### 2. Ensure Quality (Distance from Average)



Periods must be meaningfully different from the daily average:Periods must be meaningfully different from the daily average:



``````

Daily AVG: 30 ct/kWhDaily AVG: 30 ct/kWh

Minimum distance: 2% (default)Minimum distance: 2% (default)



Best Price: Must be ≤ 29.4 ct/kWh (30 - 2%)Best Price: Must be ≤ 29.4 ct/kWh (30 - 2%)

Peak Price: Must be ≥ 30.6 ct/kWh (30 + 2%)Peak Price: Must be ≥ 30.6 ct/kWh (30 + 2%)

``````



**Why?** This prevents marking mediocre times as "best" just because they're slightly below average.**Why?** This prevents marking mediocre times as "best" just because they're slightly below average.



#### 3. Check Duration#### 3. Check Duration



Periods must be long enough to be practical:Periods must be long enough to be practical:

``````

Default: 60 minutes minimumDefault: 60 minutes minimum



45-minute period → Discarded45-minute period → Discarded

90-minute period → Kept ✓90-minute period → Kept ✓

``````



#### 4. Apply Optional Filters#### 4. Apply Optional Filters



You can optionally require:You can optionally require:

- **Stable prices** (volatility filter) - "Only show if price doesn't fluctuate much"- **Stable prices** (volatility filter) - "Only show if price doesn't fluctuate much"

- **Absolute quality** (level filter) - "Only show if prices are CHEAP/EXPENSIVE (not just below/above average)"- **Absolute quality** (level filter) - "Only show if prices are CHEAP/EXPENSIVE (not just below/above average)"



### Visual Example### Visual Example



**Timeline for a typical day:****Timeline for a typical day:**

``````

Hour:  00  01  02  03  04  05  06  07  08  09  10  11  12  13  14  15  16  17  18  19  20  21  22  23Hour:  00  01  02  03  04  05  06  07  08  09  10  11  12  13  14  15  16  17  18  19  20  21  22  23

Price: 18  19  20  28  29  30  35  34  33  32  30  28  25  24  26  28  30  32  31  22  21  20  19  18Price: 18  19  20  28  29  30  35  34  33  32  30  28  25  24  26  28  30  32  31  22  21  20  19  18



Daily MIN: 18 ct | Daily MAX: 35 ct | Daily AVG: 26 ctDaily MIN: 18 ct | Daily MAX: 35 ct | Daily AVG: 26 ct



Best Price (15% flex = ≤20.7 ct):Best Price (15% flex = ≤20.7 ct):

       ████████                                                                        ████████████████       ████████                                                                        ████████████████

       00:00-03:00 (3h)                                                               19:00-24:00 (5h)       00:00-03:00 (3h)                                                               19:00-24:00 (5h)



Peak Price (-15% flex = ≥29.75 ct):Peak Price (-15% flex = ≥29.75 ct):

                              ████████████████████████                              ████████████████████████

                              06:00-11:00 (5h)                              06:00-11:00 (5h)

``````



------



## Configuration Guide## Configuration Guide



### Basic Settings### Basic Settings



#### Flexibility#### Flexibility



**What:** How far from MIN/MAX to search for periods  **What:** How far from MIN/MAX to search for periods

**Default:** 15% (Best Price), -15% (Peak Price)  **Default:** 15% (Best Price), -15% (Peak Price)

**Range:** 0-100%**Range:** 0-100%



```yaml```yaml

best_price_flex: 15    # Can be up to 15% more expensive than daily MINbest_price_flex: 15    # Can be up to 15% more expensive than daily MIN

peak_price_flex: -15   # Can be up to 15% less expensive than daily MAXpeak_price_flex: -15   # Can be up to 15% less expensive than daily MAX

``````



**When to adjust:****When to adjust:**

- **Increase (20-25%)** → Find more/longer periods- **Increase (20-25%)** → Find more/longer periods

- **Decrease (5-10%)** → Find only the very best/worst times- **Decrease (5-10%)** → Find only the very best/worst times



#### Minimum Period Length#### Minimum Period Length



**What:** How long a period must be to show it  **What:** How long a period must be to show it

**Default:** 60 minutes  **Default:** 60 minutes

**Range:** 15-240 minutes**Range:** 15-240 minutes



```yaml```yaml

best_price_min_period_length: 60best_price_min_period_length: 60

peak_price_min_period_length: 60peak_price_min_period_length: 60

``````



**When to adjust:****When to adjust:**

- **Increase (90-120 min)** → Only show longer periods (e.g., for heat pump cycles)- **Increase (90-120 min)** → Only show longer periods (e.g., for heat pump cycles)

- **Decrease (30-45 min)** → Show shorter windows (e.g., for quick tasks)- **Decrease (30-45 min)** → Show shorter windows (e.g., for quick tasks)



#### Distance from Average#### Distance from Average



**What:** How much better than average a period must be  **What:** How much better than average a period must be

**Default:** 2%  **Default:** 2%

**Range:** 0-20%**Range:** 0-20%



```yaml```yaml

best_price_min_distance_from_avg: 2best_price_min_distance_from_avg: 2

peak_price_min_distance_from_avg: 2peak_price_min_distance_from_avg: 2

``````



**When to adjust:****When to adjust:**

- **Increase (5-10%)** → Only show clearly better times- **Increase (5-10%)** → Only show clearly better times

- **Decrease (0-1%)** → Show any time below/above average- **Decrease (0-1%)** → Show any time below/above average



### Optional Filters### Optional Filters



#### Volatility Filter (Price Stability)#### Volatility Filter (Price Stability)



**What:** Only show periods with stable prices (low fluctuation)  **What:** Only show periods with stable prices (low fluctuation)

**Default:** `low` (disabled)  **Default:** `low` (disabled)

**Options:** `low` | `moderate` | `high` | `very_high`**Options:** `low` | `moderate` | `high` | `very_high`



```yaml```yaml

best_price_min_volatility: low        # Show all periodsbest_price_min_volatility: low        # Show all periods

best_price_min_volatility: moderate   # Only show if price doesn't swing >5 ctbest_price_min_volatility: moderate   # Only show if price doesn't swing >5 ct

``````



**Use case:** "I want predictable prices during the period"**Use case:** "I want predictable prices during the period"



#### Level Filter (Absolute Quality)#### Level Filter (Absolute Quality)



**What:** Only show periods with CHEAP/EXPENSIVE intervals (not just below/above average)  **What:** Only show periods with CHEAP/EXPENSIVE intervals (not just below/above average)

**Default:** `any` (disabled)  **Default:** `any` (disabled)

**Options:** `any` | `cheap` | `very_cheap` (Best Price) | `expensive` | `very_expensive` (Peak Price)**Options:** `any` | `cheap` | `very_cheap` (Best Price) | `expensive` | `very_expensive` (Peak Price)



```yaml```yaml

best_price_max_level: any      # Show any period below averagebest_price_max_level: any      # Show any period below average

best_price_max_level: cheap    # Only show if at least one interval is CHEAPbest_price_max_level: cheap    # Only show if at least one interval is CHEAP

``````



**Use case:** "Only notify me when prices are objectively cheap/expensive"**Use case:** "Only notify me when prices are objectively cheap/expensive"



#### Gap Tolerance (for Level Filter)#### Gap Tolerance (for Level Filter)



**What:** Allow some "mediocre" intervals within an otherwise good period  **What:** Allow some "mediocre" intervals within an otherwise good period

**Default:** 0 (strict)  **Default:** 0 (strict)

**Range:** 0-10**Range:** 0-10



```yaml```yaml

best_price_max_level: cheapbest_price_max_level: cheap

best_price_max_level_gap_count: 2   # Allow up to 2 NORMAL intervals per periodbest_price_max_level_gap_count: 2   # Allow up to 2 NORMAL intervals per period

``````



**Use case:** "Don't split periods just because one interval isn't perfectly CHEAP"**Use case:** "Don't split periods just because one interval isn't perfectly CHEAP"



------



## Understanding Relaxation## Understanding Relaxation



### What Is Relaxation?### What Is Relaxation?



Sometimes, strict filters find too few periods (or none). **Relaxation automatically loosens filters** until a minimum number of periods is found.Sometimes, strict filters find too few periods (or none). **Relaxation automatically loosens filters** until a minimum number of periods is found.



### How to Enable### How to Enable



```yaml```yaml

enable_min_periods_best: trueenable_min_periods_best: true

min_periods_best: 2              # Try to find at least 2 periods per daymin_periods_best: 2              # Try to find at least 2 periods per day

relaxation_step_best: 35         # Increase flex by 35% per step (e.g., 15% → 20.25% → 27.3%)relaxation_step_best: 35         # Increase flex by 35% per step (e.g., 15% → 20.25% → 27.3%)

``````



### How It Works (Smart 4×4 Matrix)### How It Works (New Smart Strategy)

```

Relaxation uses a **4×4 matrix approach** - trying 4 flexibility levels with 4 different filter combinations (16 attempts total per day):Found periods:

- 00:00-01:00 (60 min) ✓ Keep

#### Phase Matrix- 03:00-03:30 (30 min) ✗ Discard (too short)

- 14:00-15:15 (75 min) ✓ Keep

For each day, the system tries:```



**4 Flexibility Levels:**

1. Original (e.g., 15%)### How It Works (New Smart Strategy)

2. +35% step (e.g., 20.25%)

3. +35% step (e.g., 27.3%)Relaxation uses a **4×4 matrix approach** - trying 4 flexibility levels with 4 different filter combinations (16 attempts total per day):

4. +35% step (e.g., 36.9%)

#### Phase Matrix

**4 Filter Combinations (per flexibility level):**

1. Original filters (your configured volatility + level)For each day, the system tries:

2. Remove volatility filter (keep level filter)

3. Remove level filter (keep volatility filter)**4 Flexibility Levels:**

4. Remove both filters1. Original (e.g., 15%)

2. +35% step (e.g., 20.25%)

**Example progression:**3. +35% step (e.g., 27.3%)

```4. +35% step (e.g., 36.9%)

Flex 15% + Original filters → Not enough periods

Flex 15% + Volatility=any   → Not enough periods**4 Filter Combinations (per flexibility level):**

Flex 15% + Level=any        → Not enough periods1. Original filters (your configured volatility + level)

Flex 15% + All filters off  → Not enough periods2. Remove volatility filter (keep level filter)

Flex 20.25% + Original      → SUCCESS! Found 2 periods ✓3. Remove level filter (keep volatility filter)

(stops here - no need to try more)4. Remove both filters

```

**Example progression:**

#### Per-Day Independence```

Flex 15% + Original filters → Not enough periods

**Critical:** Each day relaxes **independently**:Flex 15% + Volatility=any   → Not enough periods

Flex 15% + Level=any        → Not enough periods

```Flex 15% + All filters off  → Not enough periods

Day 1: Finds 2 periods with flex 15% (original) → No relaxation neededFlex 20.25% + Original      → SUCCESS! Found 2 periods ✓

Day 2: Needs flex 27.3% + level=any → Uses relaxed settings(stops here - no need to try more)

Day 3: Finds 2 periods with flex 15% (original) → No relaxation needed```

```

#### Per-Day Independence

**Why?** Price patterns vary daily. Some days have clear cheap/expensive windows (strict filters work), others don't (relaxation needed).

**Critical:** Each day relaxes **independently**:

#### Period Replacement Logic

```

When relaxation finds new periods, they interact with baseline periods in two ways:Day 1: Finds 2 periods with flex 15% (original) → No relaxation needed

Day 2: Needs flex 27.3% + level=any → Uses relaxed settings

**1. Extension** (Enlargement)Day 3: Finds 2 periods with flex 15% (original) → No relaxation needed

A relaxed period that **overlaps** with a baseline period and extends it:```

```

Baseline:  [14:00-16:00] ████████**Why?** Price patterns vary daily. Some days have clear cheap/expensive windows (strict filters work), others don't (relaxation needed).

Relaxed:   [13:00-16:30]    ████████████

Result:    [13:00-16:30] ████████████████  (baseline expanded)#### Period Replacement Logic

           ↑ Keeps baseline metadata (original flex/filters)

```When relaxation finds new periods, they interact with baseline periods in two ways:



**2. Replacement** (Substitution)**1. Extension** (Enlargement)

A **larger** relaxed period completely contains a **smaller** relaxed period from earlier phases:A relaxed period that **overlaps** with a baseline period and extends it:

``````

Phase 1:   [14:00-15:00] ████        (found with flex 15%)Baseline:  [14:00-16:00] ████████

Phase 3:   [13:00-17:00]    ████████████  (found with flex 27.3%)Relaxed:   [13:00-16:30]    ████████████

Result:    [13:00-17:00] ████████████  (larger replaces smaller)Result:    [13:00-16:30] ████████████████  (baseline expanded)

           ↑ Uses Phase 3 metadata (flex 27.3%)           ↑ Keeps baseline metadata (original flex/filters)

``````



**Why two different behaviors?****2. Replacement** (Substitution)

- **Extensions preserve quality:** Baseline periods found with original strict filters are high-quality. When relaxation finds overlapping periods, we expand the baseline but keep its original metadata (indicating it was found with strict criteria).A **larger** relaxed period completely contains a **smaller** relaxed period from earlier phases:

- **Replacements reflect reality:** When a larger relaxed period is found, it completely replaces smaller relaxed periods because it better represents the actual price window. The metadata shows which relaxation phase actually found this period.```

Phase 1:   [14:00-15:00] ████        (found with flex 15%)

**Key principle:** Baseline periods are "gold standard" - they get extended but never replaced. Relaxed periods compete with each other based on size.Phase 3:   [13:00-17:00]    ████████████  (found with flex 27.3%)

Result:    [13:00-17:00] ████████████  (larger replaces smaller)

#### Counting Logic           ↑ Uses Phase 3 metadata (flex 27.3%)

```

The system counts **standalone periods** (periods that remain in the final result):

**Why two different behaviors?**

```- **Extensions preserve quality:** Baseline periods found with original strict filters are high-quality. When relaxation finds overlapping periods, we expand the baseline but keep its original metadata (indicating it was found with strict criteria).

After all relaxation phases:- **Replacements reflect reality:** When a larger relaxed period is found, it completely replaces smaller relaxed periods because it better represents the actual price window. The metadata shows which relaxation phase actually found this period.

- Period A: Extended baseline (counts ✓)

- Period B: Standalone relaxed (counts ✓)**Key principle:** Baseline periods are "gold standard" - they get extended but never replaced. Relaxed periods compete with each other based on size.

- Period C: Was replaced by larger period (doesn't count ✗)

#### Counting Logic

Total: 2 periods

Comparison: ≥ min_periods_best? → Yes → SUCCESSThe system counts **standalone periods** (periods that remain in the final result):

```

```

### Metadata TrackingAfter all relaxation phases:

- Period A: Extended baseline (counts ✓)

Each period shows **how it was found** via entity attributes:- Period B: Standalone relaxed (counts ✓)

- Period C: Was replaced by larger period (doesn't count ✗)

**Baseline Period (no relaxation needed):**

```yamlTotal: 2 periods

relaxation_active: falseComparison: ≥ min_periods_best? → Yes → SUCCESS

relaxation_level: "price_diff_15.0%"        # Original flexibility```

```

### Metadata Tracking

**Extended Baseline (relaxation extended it):**

```yamlEach period shows **how it was found** via entity attributes:

relaxation_active: true                      # Relaxation was needed globally

relaxation_level: "price_diff_15.0%"        # But THIS period was baseline**Baseline Period (no relaxation needed):**

``````yaml

relaxation_active: false

**Standalone Relaxed Period:**relaxation_level: "price_diff_15.0%"        # Original flexibility

```yaml```

relaxation_active: true

relaxation_level: "price_diff_27.3%+level_any"  # Found at flex 27.3%, level filter removed**Extended Baseline (relaxation extended it):**

``````yaml

relaxation_active: true                      # Relaxation was needed globally

**Replaced Period (doesn't appear in final result):**relaxation_level: "price_diff_15.0%"        # But THIS period was baseline

- Not exposed as entity (was replaced by larger period)```



### Configuration Example**Standalone Relaxed Period:**

```yaml

```yamlrelaxation_active: true

# Best Price with relaxationrelaxation_level: "price_diff_27.3%+level_any"  # Found at flex 27.3%, level filter removed

enable_min_periods_best: true```

min_periods_best: 2                    # Try to find at least 2 periods per day

relaxation_step_best: 35               # Increase flex by 35% per step**Replaced Period (doesn't appear in final result):**

best_price_flex: 15                    # Start with 15%- Not exposed as entity (was replaced by larger period)

best_price_min_volatility: moderate    # Start with volatility filter

best_price_max_level: cheap            # Start with level filter### Configuration Example



# Result: Tries up to 16 combinations per day:```yaml

# Flex 15%/20.25%/27.3%/36.9% × Filters original/vol-any/lvl-any/all-any# Best Price with relaxation

# Stops immediately when 2 periods foundenable_min_periods_best: true

```min_periods_best: 2                    # Try to find at least 2 periods per day

relaxation_step_best: 35               # Increase flex by 35% per step

---best_price_flex: 15                    # Start with 15%

best_price_min_volatility: moderate    # Start with volatility filter

## Common Scenariosbest_price_max_level: cheap            # Start with level filter



### Scenario 1: Simple Best Price (Default)# Result: Tries up to 16 combinations per day:

# Flex 15%/20.25%/27.3%/36.9% × Filters original/vol-any/lvl-any/all-any

**Goal:** Find the cheapest time each day to run dishwasher# Stops immediately when 2 periods found

```

**Configuration:**

```yaml---

# Use defaults - no configuration needed!

best_price_flex: 15                      # (default)## Common Scenarios

best_price_min_period_length: 60         # (default)

best_price_min_distance_from_avg: 2      # (default)### Scenario 1: Simple Best Price (Default)

```

**Goal:** Find the cheapest time each day to run dishwasher

**What you get:**

- 1-3 periods per day with prices ≤ MIN + 15%**Configuration:**

- Each period at least 1 hour long```yaml

- All periods at least 2% cheaper than daily average# Use defaults - no configuration needed!

best_price_flex: 15                      # (default)

**Automation example:**best_price_min_period_length: 60         # (default)

```yamlbest_price_min_distance_from_avg: 2      # (default)

automation:```

  - trigger:

      - platform: state**What you get:**

        entity_id: binary_sensor.tibber_home_best_price_period- 1-3 periods per day with prices ≤ MIN + 15%

        to: "on"- Each period at least 1 hour long

    action:- All periods at least 2% cheaper than daily average

      - service: switch.turn_on

        target:**Automation example:**

          entity_id: switch.dishwasher```yaml

```automation:

  - trigger:

### Scenario 2: Heat Pump (Long Periods + Relaxation)      - platform: state

        entity_id: binary_sensor.tibber_home_best_price_period

**Goal:** Run water heater during long cheap windows, accept longer periods even if not perfectly cheap        to: "on"

    action:

**Configuration:**      - service: switch.turn_on

```yaml        target:

best_price_min_period_length: 120        # Need at least 2 hours          entity_id: switch.dishwasher

enable_min_periods_best: true```

min_periods_best: 2                      # Want 2 opportunities per day

relaxation_step_best: 35### Scenario 2: Heat Pump (Long Periods + Relaxation)

best_price_max_level: cheap              # Prefer CHEAP intervals

best_price_max_level_gap_count: 3        # But allow some NORMAL intervals**Goal:** Run water heater during long cheap windows, accept longer periods even if not perfectly cheap

```

**Configuration:**

**What you get:**```yaml

- At least 2 periods per day (relaxation ensures this)best_price_min_period_length: 120        # Need at least 2 hours

- Each period at least 2 hours longenable_min_periods_best: true

- Primarily CHEAP intervals, but tolerates up to 3 NORMAL intervals per periodmin_periods_best: 2                      # Want 2 opportunities per day

- If not enough strict matches, relaxation finds longer/less-strict periodsrelaxation_step_best: 35

best_price_max_level: cheap              # Prefer CHEAP intervals

**Automation example:**best_price_max_level_gap_count: 3        # But allow some NORMAL intervals

```yaml```

automation:

  - trigger:**What you get:**

      - platform: state- At least 2 periods per day (relaxation ensures this)

        entity_id: binary_sensor.tibber_home_best_price_period- Each period at least 2 hours long

        to: "on"- Primarily CHEAP intervals, but tolerates up to 3 NORMAL intervals per period

    condition:- If not enough strict matches, relaxation finds longer/less-strict periods

      - condition: numeric_state

        entity_id: sensor.water_heater_temperature**Automation example:**

        below: 50```yaml

    action:automation:

      - service: climate.set_hvac_mode  - trigger:

        target:      - platform: state

          entity_id: climate.water_heater        entity_id: binary_sensor.tibber_home_best_price_period

        data:        to: "on"

          hvac_mode: heat    condition:

```      - condition: numeric_state

        entity_id: sensor.water_heater_temperature

### Scenario 3: EV Charging (Stable Prices Only)        below: 50

    action:

**Goal:** Charge electric vehicle only during stable, predictable cheap prices      - service: climate.set_hvac_mode

        target:

**Configuration:**          entity_id: climate.water_heater

```yaml        data:

best_price_flex: 10                      # Very strict (only very cheap times)          hvac_mode: heat

best_price_min_volatility: moderate      # Require stable prices```

best_price_max_level: cheap              # Require at least one CHEAP interval

enable_min_periods_best: false           # Don't relax - better to skip a day### Scenario 3: EV Charging (Stable Prices Only)

```

**Goal:** Charge electric vehicle only during stable, predictable cheap prices

**What you get:**

- Very strict matching - only clearly cheap, stable periods**Configuration:**

- Some days might have 0 periods (and that's OK)```yaml

- When periods appear, they're high confidencebest_price_flex: 10                      # Very strict (only very cheap times)

best_price_min_volatility: moderate      # Require stable prices

**Automation example:**best_price_max_level: cheap              # Require at least one CHEAP interval

```yamlenable_min_periods_best: false           # Don't relax - better to skip a day

automation:```

  - trigger:

      - platform: state**What you get:**

        entity_id: binary_sensor.tibber_home_best_price_period- Very strict matching - only clearly cheap, stable periods

        to: "on"- Some days might have 0 periods (and that's OK)

    condition:- When periods appear, they're high confidence

      - condition: numeric_state

        entity_id: sensor.ev_battery_level**Automation example:**

        below: 80```yaml

      - condition: stateautomation:

        entity_id: binary_sensor.ev_connected  - trigger:

        state: "on"      - platform: state

    action:        entity_id: binary_sensor.tibber_home_best_price_period

      - service: switch.turn_on        to: "on"

        target:    condition:

          entity_id: switch.ev_charger      - condition: numeric_state

```        entity_id: sensor.ev_battery_level

        below: 80

### Scenario 4: Peak Price Avoidance      - condition: state

        entity_id: binary_sensor.ev_connected

**Goal:** Reduce heating during the most expensive hours        state: "on"

    action:

**Configuration:**      - service: switch.turn_on

```yaml        target:

peak_price_flex: -10                     # Only the very expensive times          entity_id: switch.ev_charger

peak_price_min_period_length: 30         # Even short periods matter```

enable_min_periods_peak: true

min_periods_peak: 1                      # Ensure at least 1 peak warning per day### Scenario 4: Peak Price Avoidance

```

**Goal:** Reduce heating during the most expensive hours

**What you get:**

- At least 1 expensive period per day (relaxation ensures this)**Configuration:**

- Periods can be as short as 30 minutes```yaml

- Clear signal when to reduce consumptionpeak_price_flex: -10                     # Only the very expensive times

peak_price_min_period_length: 30         # Even short periods matter

**Automation example:**enable_min_periods_peak: true

```yamlmin_periods_peak: 1                      # Ensure at least 1 peak warning per day

automation:```

  - trigger:

      - platform: state**What you get:**

        entity_id: binary_sensor.tibber_home_peak_price_period- At least 1 expensive period per day (relaxation ensures this)

        to: "on"- Periods can be as short as 30 minutes

    action:- Clear signal when to reduce consumption

      - service: climate.set_temperature

        target:**Automation example:**

          entity_id: climate.living_room```yaml

        data:automation:

          temperature: 19  # Reduce by 2°C during peaks  - trigger:

```      - platform: state

        entity_id: binary_sensor.tibber_home_peak_price_period

---        to: "on"

    action:

## Troubleshooting      - service: climate.set_temperature

        target:

### No Periods Found          entity_id: climate.living_room

        data:

**Symptom:** `binary_sensor.tibber_home_best_price_period` never turns "on"          temperature: 19  # Reduce by 2°C during peaks

```

**Possible causes:**

---

1. **Filters too strict**

   ```yaml## Troubleshooting

   # Try:

   best_price_flex: 20              # Increase from default 15%### No Periods Found

   best_price_min_distance_from_avg: 1  # Reduce from default 2%

   ```**Symptom:** `binary_sensor.tibber_home_best_price_period` never turns "on"



2. **Period length too long****Possible causes:**

   ```yaml

   # Try:1. **Filters too strict**

   best_price_min_period_length: 45     # Reduce from default 60 minutes   ```yaml

   ```   # Try:

   best_price_flex: 20              # Increase from default 15%

3. **Flat price curve** (all prices very similar)   best_price_min_distance_from_avg: 1  # Reduce from default 2%

   - Enable relaxation to ensure at least some periods   ```

   ```yaml

   enable_min_periods_best: true2. **Period length too long**

   min_periods_best: 1   ```yaml

   ```   # Try:

   best_price_min_period_length: 45     # Reduce from default 60 minutes

### Too Many Periods   ```



**Symptom:** 5+ periods per day, hard to decide which one to use3. **Flat price curve** (all prices very similar)

   - Enable relaxation to ensure at least some periods

**Solution:**   ```yaml

```yaml   enable_min_periods_best: true

# Make filters stricter:   min_periods_best: 1

best_price_flex: 10                  # Reduce from default 15%   ```

best_price_min_period_length: 90     # Increase from default 60 minutes

best_price_min_volatility: moderate  # Require stable prices

best_price_max_level: cheap          # Require CHEAP intervals**Symptom:** 5+ periods per day, hard to decide which one to use

```

**Solution:**

### Periods Split Into Small Pieces```yaml

# Make filters stricter:

**Symptom:** Many short periods instead of one long periodbest_price_flex: 10                  # Reduce from default 15%

best_price_min_period_length: 90     # Increase from default 60 minutes

**Possible causes:**best_price_min_volatility: moderate  # Require stable prices

best_price_max_level: cheap          # Require CHEAP intervals

1. **Level filter too strict**```

   ```yaml

   # One "NORMAL" interval splits an otherwise good period### Periods Split Into Small Pieces

   # Solution: Use gap tolerance

   best_price_max_level: cheap**Symptom:** Many short periods instead of one long period

   best_price_max_level_gap_count: 2    # Allow 2 NORMAL intervals

   ```**Possible causes:**



2. **Flexibility too tight**1. **Level filter too strict**

   ```yaml   ```yaml

   # One interval just outside flex range splits the period   # One "NORMAL" interval splits an otherwise good period

   # Solution: Increase flexibility   # Solution: Use gap tolerance

   best_price_flex: 20                  # Increase from 15%   best_price_max_level: cheap

   ```   best_price_max_level_gap_count: 2    # Allow 2 NORMAL intervals

   ```

### Understanding Sensor Attributes

2. **Flexibility too tight**

**Check period details:**   ```yaml

```yaml   # One interval just outside flex range splits the period

# Entity: binary_sensor.tibber_home_best_price_period   # Solution: Increase flexibility

   best_price_flex: 20                  # Increase from 15%

# Attributes when "on":   ```

start: "2025-11-11T02:00:00+01:00"

end: "2025-11-11T05:00:00+01:00"### Understanding Sensor Attributes

duration_minutes: 180

rating_level: "LOW"                              # All intervals are LOW price**Check period details:**

price_avg: 18.5                                  # Average price in this period```yaml

relaxation_active: true                          # This day used relaxation# Entity: binary_sensor.tibber_home_best_price_period

relaxation_level: "price_diff_20.25%+level_any" # Found at flex 20.25%, level filter removed

# Attributes when "on":

# When "off" (outside any period):start: "2025-11-11T02:00:00+01:00"

next_start: "2025-11-11T14:00:00+01:00"         # Next period starts at 14:00end: "2025-11-11T05:00:00+01:00"

next_end: "2025-11-11T17:00:00+01:00"duration_minutes: 180

next_duration_minutes: 180rating_level: "LOW"                              # All intervals are LOW price

```price_avg: 18.5                                  # Average price in this period

relaxation_active: true                          # This day used relaxation

### Checking the Logsrelaxation_level: "price_diff_20.25%+level_any" # Found at flex 20.25%, level filter removed



Enable debug logging to see detailed calculation:# When "off" (outside any period):

next_start: "2025-11-11T14:00:00+01:00"         # Next period starts at 14:00

```yamlnext_end: "2025-11-11T17:00:00+01:00"

# configuration.yamlnext_duration_minutes: 180

logger:```

  default: warning

  logs:### Checking the Logs

    custom_components.tibber_prices.period_utils: debug

```Enable debug logging to see detailed calculation:



**What to look for:**```yaml

```# configuration.yaml

INFO: Calculating BEST PRICE periods: relaxation=ON, target=2/day, flex=15.0%logger:

DEBUG: Day 2025-11-11: Found 1 baseline period (need 2)  default: warning

DEBUG: Day 2025-11-11: Starting relaxation...  logs:

DEBUG: Phase 1: flex 20.25% + original filters    custom_components.tibber_prices.period_utils: debug

DEBUG:   Candidate: 02:00-05:00 (3h) - rating=LOW, avg=18.5 ct```

DEBUG:   Result: 2 standalone periods after merge ✓

INFO: Day 2025-11-11: Success after 1 relaxation phase (2 periods)**What to look for:**

``````

INFO: Calculating BEST PRICE periods: relaxation=ON, target=2/day, flex=15.0%

---DEBUG: Day 2025-11-11: Found 1 baseline period (need 2)

DEBUG: Day 2025-11-11: Starting relaxation...

## Advanced TopicsDEBUG: Phase 1: flex 20.25% + original filters

DEBUG:   Candidate: 02:00-05:00 (3h) - rating=LOW, avg=18.5 ct

For advanced configuration patterns and technical deep-dive, see:DEBUG:   Result: 2 standalone periods after merge ✓

- [Automation Examples](./automation-examples.md) - Real-world automation patternsINFO: Day 2025-11-11: Success after 1 relaxation phase (2 periods)

- [Services](./services.md) - Using the `tibber_prices.get_price` service for custom logic```



### Quick Reference---



**Configuration Parameters:**## Advanced Topics



| Parameter | Default | Range | Purpose |For advanced configuration patterns and technical deep-dive, see:

|-----------|---------|-------|---------|- [Automation Examples](./automation-examples.md) - Real-world automation patterns

| `best_price_flex` | 15% | 0-100% | Search range from daily MIN |- [Services](./services.md) - Using the `tibber_prices.get_price` service for custom logic

| `best_price_min_period_length` | 60 min | 15-240 | Minimum duration |

| `best_price_min_distance_from_avg` | 2% | 0-20% | Quality threshold |### Quick Reference

| `best_price_min_volatility` | low | low/mod/high/vhigh | Stability filter |

| `best_price_max_level` | any | any/cheap/vcheap | Absolute quality |**Configuration Parameters:**

| `best_price_max_level_gap_count` | 0 | 0-10 | Gap tolerance |

| `enable_min_periods_best` | false | true/false | Enable relaxation || Parameter | Default | Range | Purpose |

| `min_periods_best` | - | 1-10 | Target periods per day ||-----------|---------|-------|---------|

| `relaxation_step_best` | - | 5-100% | Relaxation increment || `best_price_flex` | 15% | 0-100% | Search range from daily MIN |

| `best_price_min_period_length` | 60 min | 15-240 | Minimum duration |

**Peak Price:** Same parameters with `peak_price_*` prefix (defaults: flex=-15%, same otherwise)| `best_price_min_distance_from_avg` | 2% | 0-20% | Quality threshold |

| `best_price_min_volatility` | low | low/mod/high/vhigh | Stability filter |

### Price Levels Reference| `best_price_max_level` | any | any/cheap/vcheap | Absolute quality |

| `best_price_max_level_gap_count` | 0 | 0-10 | Gap tolerance |

The Tibber API provides price levels for each 15-minute interval:| `enable_min_periods_best` | false | true/false | Enable relaxation |

| `min_periods_best` | - | 1-10 | Target periods per day |

**Levels (based on trailing 24h average):**| `relaxation_step_best` | - | 5-100% | Relaxation increment |

- `VERY_CHEAP` - Significantly below average

- `CHEAP` - Below average**Peak Price:** Same parameters with `peak_price_*` prefix (defaults: flex=-15%, same otherwise)

- `NORMAL` - Around average

- `EXPENSIVE` - Above average### Price Levels Reference

- `VERY_EXPENSIVE` - Significantly above average

The Tibber API provides price levels for each 15-minute interval:

**Note:** Your configured `best_price_max_level` or `peak_price_min_level` filter uses these API-provided levels.

**Levels (based on trailing 24h average):**

---- `VERY_CHEAP` - Significantly below average

- `CHEAP` - Below average

**Last updated:** November 11, 2025  - `NORMAL` - Around average

**Integration version:** 2.0+- `EXPENSIVE` - Above average

- `VERY_EXPENSIVE` - Significantly above average

**Note:** Your configured `best_price_max_level` or `peak_price_min_level` filter uses these API-provided levels.

---

**Last updated:** November 11, 2025
**Integration version:** 2.0+

### Best Price Period Settings

| Option | Default | Description | Acts in Step |
|--------|---------|-------------|--------------|
| `best_price_flex` | 15% | How much more expensive than the daily **MIN** can an interval be? | 2 (Identification) |
| `best_price_min_period_length` | 60 min | Minimum length of a period | 3 (Length filter) |
| `best_price_min_distance_from_avg` | 2% | Minimum distance below daily **average** (separate from flexibility) | 4 (Quality filter) |
| `best_price_min_volatility` | LOW | Minimum volatility within the period (optional) | 5 (Volatility filter) |
| `best_price_max_level` | ANY | Maximum price level (optional, e.g., only CHEAP or better) | 5 (Level filter) |
| `best_price_max_level_gap_count` | 0 | Tolerance for level deviations (see [Gap Tolerance](#gap-tolerance-for-level-filters)) | 5 (Level filter) |
| `enable_min_periods_best` | Off | Enables relaxation mechanism | - (Relaxation) |
| `min_periods_best` | 2 | Minimum number of periods **per day** to achieve | - (Relaxation) |
| `relaxation_step_best` | 25% | Step size for filter relaxation | - (Relaxation) |

### Peak Price Period Settings

| Option | Default | Description | Acts in Step |
|--------|---------|-------------|--------------|
| `peak_price_flex` | -15% | How much less expensive than the daily **MAX** can an interval be? | 2 (Identification) |
| `peak_price_min_period_length` | 60 min | Minimum length of a period | 3 (Length filter) |
| `peak_price_min_distance_from_avg` | 2% | Minimum distance above daily **average** (separate from flexibility) | 4 (Quality filter) |
| `peak_price_min_volatility` | LOW | Minimum volatility within the period (optional) | 5 (Volatility filter) |
| `peak_price_min_level` | ANY | Minimum price level (optional, e.g., only EXPENSIVE or higher) | 5 (Level filter) |
| `peak_price_max_level_gap_count` | 0 | Tolerance for level deviations (see [Gap Tolerance](#gap-tolerance-for-level-filters)) | 5 (Level filter) |
| `enable_min_periods_peak` | Off | Enables relaxation mechanism | - (Relaxation) |
| `min_periods_peak` | 2 | Minimum number of periods **per day** to achieve | - (Relaxation) |
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
2. Fewer than `min_periods_best/peak` periods found **for a specific day**

**Important:** The minimum period requirement is checked **separately for each day** (today and tomorrow). This ensures:
- Each day must have enough periods independently
- Today can meet the requirement while tomorrow doesn't (or vice versa)
- When tomorrow's prices arrive, both days are evaluated separately

**Example scenario:**
- Configuration: `min_periods_best = 3`
- 14:00: Tomorrow's prices arrive
- Today: 10 periods remaining → ✅ Meets requirement (≥3)
- Tomorrow: 2 periods found → ❌ Doesn't meet requirement (<3)
- **Result:** Relaxation only applies to tomorrow's periods

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

**Important:** This increases the flexibility percentage, which allows intervals **further from the daily MIN/MAX** to be included. For best price, this means accepting intervals more expensive than the original flexibility threshold.

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
MIN: 18.0 ct/kWh
MAX: 32.0 ct/kWh
AVG: 25.0 ct/kWh

00:00-02:00: 18-20 ct (cheap)
06:00-08:00: 28-30 ct (expensive)
12:00-14:00: 24-26 ct (normal)
18:00-20:00: 19-21 ct (cheap)
```

**Calculation:**
1. Flexibility threshold: 18.0 × 1.15 = 20.7 ct (vs MIN, not average!)
2. Minimum distance threshold: 25.0 × 0.98 = 24.5 ct (vs AVG)
3. Both conditions: Price ≤ 20.7 ct AND Price ≤ 24.5 ct

**Result:**
- ✓ 00:00-02:00 (18-20 ct, all ≤ 20.7 and all ≤ 24.5)
- ✗ 06:00-08:00 (too expensive)
- ✗ 12:00-14:00 (24-26 ct, exceeds flexibility threshold of 20.7 ct)
- ✓ 18:00-20:00 (19-21 ct, all ≤ 20.7 and all ≤ 24.5)

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

best_price_flex: 5  # Very strict!
best_price_min_volatility: "high"  # Very strict!
```

**Day with little price spread:**
```
MIN: 23.0 ct/kWh
MAX: 27.0 ct/kWh
AVG: 25.0 ct/kWh
All prices between 23-27 ct (low volatility)
```

**Relaxation process:**

1. **Attempt 1:** 5% flex + HIGH volatility
   ```
   Threshold: 23.0 × 1.05 = 24.15 ct (vs MIN)
   No period meets both conditions
   → 0 periods (< 2 required)
   ```

2. **Attempt 2:** 6.25% flex + HIGH volatility
   ```
   Threshold: 23.0 × 1.0625 = 24.44 ct
   Still 0 periods
   ```

3. **Attempt 3:** Disable volatility filter
   ```
   6.25% flex + ANY volatility
   → 1 period found (< 2)
   ```

4. **Attempt 4:** 7.81% flex + ANY volatility
   ```
   Threshold: 23.0 × 1.0781 = 24.80 ct
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
   best_price_flex: 5  # Only allows intervals ≤5% above daily MIN
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
   MIN: 23 ct, MAX: 27 ct (hardly any differences)
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
