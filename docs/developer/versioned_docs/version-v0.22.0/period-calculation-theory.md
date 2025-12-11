# Period Calculation Theory

## Overview

This document explains the mathematical foundations and design decisions behind the period calculation algorithm, particularly focusing on the interaction between **Flexibility (Flex)**, **Minimum Distance from Average**, and **Relaxation Strategy**.

**Target Audience:** Developers maintaining or extending the period calculation logic.

**Related Files:**
- `coordinator/period_handlers/core.py` - Main calculation entry point
- `coordinator/period_handlers/level_filtering.py` - Flex and distance filtering
- `coordinator/period_handlers/relaxation.py` - Multi-phase relaxation strategy
- `coordinator/periods.py` - Period calculator orchestration

---

## Core Filtering Criteria

Period detection uses **three independent filters** (all must pass):

### 1. Flex Filter (Price Distance from Reference)

**Purpose:** Limit how far prices can deviate from the daily min/max.

**Logic:**
```python
# Best Price: Price must be within flex% ABOVE daily minimum
in_flex = price <= (daily_min + daily_min × flex)

# Peak Price: Price must be within flex% BELOW daily maximum
in_flex = price >= (daily_max - daily_max × flex)
```

**Example (Best Price):**
- Daily Min: 10 ct/kWh
- Flex: 15%
- Acceptance Range: 0 - 11.5 ct/kWh (10 + 10×0.15)

### 2. Min Distance Filter (Distance from Daily Average)

**Purpose:** Ensure periods are **significantly** cheaper/more expensive than average, not just marginally better.

**Logic:**
```python
# Best Price: Price must be at least min_distance% BELOW daily average
meets_distance = price <= (daily_avg × (1 - min_distance/100))

# Peak Price: Price must be at least min_distance% ABOVE daily average
meets_distance = price >= (daily_avg × (1 + min_distance/100))
```

**Example (Best Price):**
- Daily Avg: 15 ct/kWh
- Min Distance: 5%
- Acceptance Range: 0 - 14.25 ct/kWh (15 × 0.95)

### 3. Level Filter (Price Level Classification)

**Purpose:** Restrict periods to specific price classifications (VERY_CHEAP, CHEAP, NORMAL, EXPENSIVE, VERY_EXPENSIVE).

**Logic:** See `level_filtering.py` for gap tolerance details.

**Volatility Thresholds - Important Separation:**

The integration maintains **two independent sets** of volatility thresholds:

1. **Sensor Thresholds** (user-configurable via `CONF_VOLATILITY_*_THRESHOLD`)
   - Purpose: Display classification in `sensor.tibber_home_volatility_*`
   - Default: LOW < 10%, MEDIUM < 20%, HIGH ≥ 20%
   - User can adjust in config flow options
   - Affects: Sensor state/attributes only

2. **Period Filter Thresholds** (internal, fixed)
   - Purpose: Level filter criteria when using `level="volatility_low"` etc.
   - Source: `PRICE_LEVEL_THRESHOLDS` in `const.py`
   - Values: Same as sensor defaults (LOW < 10%, MEDIUM < 20%, HIGH ≥ 20%)
   - User **cannot** adjust these
   - Affects: Period candidate selection

**Rationale for Separation:**

- **Sensor thresholds** = Display preference ("I want to see LOW at 15% instead of 10%")
- **Period thresholds** = Algorithm configuration (tested defaults, complex interactions)
- Changing sensor display should not affect automation behavior
- Prevents unexpected side effects when user adjusts sensor classification
- Period calculation has many interacting filters (Flex, Distance, Level) - exposing all internals would be error-prone

**Implementation:**
```python
# Sensor classification uses user config
user_low_threshold = config_entry.options.get(CONF_VOLATILITY_LOW_THRESHOLD, 10)

# Period filter uses fixed constants
period_low_threshold = PRICE_LEVEL_THRESHOLDS["volatility_low"]  # Always 10%
```

**Status:** Intentional design decision (Nov 2025). No plans to expose period thresholds to users.

---

## The Flex × Min_Distance Conflict

### Problem Statement

**These two filters can conflict when Flex is high!**

#### Scenario: Best Price with Flex=50%, Min_Distance=5%

**Given:**
- Daily Min: 10 ct/kWh
- Daily Avg: 15 ct/kWh
- Daily Max: 20 ct/kWh

**Flex Filter (50%):**
```
Max accepted = 10 + (10 × 0.50) = 15 ct/kWh
```

**Min Distance Filter (5%):**
```
Max accepted = 15 × (1 - 0.05) = 14.25 ct/kWh
```

**Conflict:**
- Interval at 14.8 ct/kWh:
  - ✅ Flex: 14.8 ≤ 15 (PASS)
  - ❌ Distance: 14.8 > 14.25 (FAIL)
  - **Result:** Rejected by Min_Distance even though Flex allows it!

**The Issue:** At high Flex values, Min_Distance becomes the dominant filter and blocks intervals that Flex would permit. This defeats the purpose of having high Flex.

### Mathematical Analysis

**Conflict condition for Best Price:**
```
daily_min × (1 + flex) > daily_avg × (1 - min_distance/100)
```

**Typical values:**
- Min = 10, Avg = 15, Min_Distance = 5%
- Conflict occurs when: `10 × (1 + flex) > 14.25`
- Simplify: `flex > 0.425` (42.5%)

**Below 42.5% Flex:** Both filters contribute meaningfully.
**Above 42.5% Flex:** Min_Distance dominates and blocks intervals.

### Solution: Dynamic Min_Distance Scaling

**Approach:** Reduce Min_Distance proportionally as Flex increases.

**Formula:**
```python
if flex > 0.20:  # 20% threshold
    flex_excess = flex - 0.20
    scale_factor = max(0.25, 1.0 - (flex_excess × 2.5))
    adjusted_min_distance = original_min_distance × scale_factor
```

**Scaling Table (Original Min_Distance = 5%):**

| Flex  | Scale Factor | Adjusted Min_Distance | Rationale |
|-------|--------------|----------------------|-----------|
| ≤20%  | 1.00         | 5.0%                | Standard - both filters relevant |
| 25%   | 0.88         | 4.4%                | Slight reduction |
| 30%   | 0.75         | 3.75%               | Moderate reduction |
| 40%   | 0.50         | 2.5%                | Strong reduction - Flex dominates |
| 50%   | 0.25         | 1.25%               | Minimal distance - Flex decides |

**Why stop at 25% of original?**
- Min_Distance ensures periods are **significantly** different from average
- Even at 1.25%, prevents "flat days" (little price variation) from accepting every interval
- Maintains semantic meaning: "this is a meaningful best/peak price period"

**Implementation:** See `level_filtering.py` → `check_interval_criteria()`

**Code Extract:**
```python
# coordinator/period_handlers/level_filtering.py

FLEX_SCALING_THRESHOLD = 0.20  # 20% - start adjusting min_distance
SCALE_FACTOR_WARNING_THRESHOLD = 0.8  # Log when reduction > 20%

def check_interval_criteria(price, criteria):
    # ... flex check ...

    # Dynamic min_distance scaling
    adjusted_min_distance = criteria.min_distance_from_avg
    flex_abs = abs(criteria.flex)

    if flex_abs > FLEX_SCALING_THRESHOLD:
        flex_excess = flex_abs - 0.20  # How much above 20%
        scale_factor = max(0.25, 1.0 - (flex_excess × 2.5))
        adjusted_min_distance = criteria.min_distance_from_avg × scale_factor

        if scale_factor < SCALE_FACTOR_WARNING_THRESHOLD:
            _LOGGER.debug(
                "High flex %.1f%% detected: Reducing min_distance %.1f%% → %.1f%%",
                flex_abs × 100,
                criteria.min_distance_from_avg,
                adjusted_min_distance,
            )

    # Apply adjusted min_distance in distance check
    meets_min_distance = (
        price <= avg_price × (1 - adjusted_min_distance/100)  # Best Price
        # OR
        price >= avg_price × (1 + adjusted_min_distance/100)  # Peak Price
    )
```

**Why Linear Scaling?**
- Simple and predictable
- No abrupt behavior changes
- Easy to reason about for users and developers
- Alternative considered: Exponential scaling (rejected as too aggressive)

**Why 25% Minimum?**
- Below this, min_distance loses semantic meaning
- Even on flat days, some quality filter needed
- Prevents "every interval is a period" scenario
- Maintains user expectation: "best/peak price means notably different"

---

## Flex Limits and Safety Caps

### Implementation Constants

**Defined in `coordinator/period_handlers/core.py`:**
```python
MAX_SAFE_FLEX = 0.50  # 50% - hard cap: above this, period detection becomes unreliable
MAX_OUTLIER_FLEX = 0.25  # 25% - cap for outlier filtering: above this, spike detection too permissive
```

**Defined in `const.py`:**
```python
DEFAULT_BEST_PRICE_FLEX = 15  # 15% base - optimal for relaxation mode (default enabled)
DEFAULT_PEAK_PRICE_FLEX = -20  # 20% base (negative for peak detection)
DEFAULT_RELAXATION_ATTEMPTS_BEST = 11  # 11 steps: 15% → 48% (3% increment per step)
DEFAULT_RELAXATION_ATTEMPTS_PEAK = 11  # 11 steps: 20% → 50% (3% increment per step)
DEFAULT_BEST_PRICE_MIN_PERIOD_LENGTH = 60  # 60 minutes
DEFAULT_PEAK_PRICE_MIN_PERIOD_LENGTH = 30  # 30 minutes
DEFAULT_BEST_PRICE_MIN_DISTANCE_FROM_AVG = 5  # 5% minimum distance
DEFAULT_PEAK_PRICE_MIN_DISTANCE_FROM_AVG = 5  # 5% minimum distance
```

### Rationale for Asymmetric Defaults

**Why Best Price ≠ Peak Price?**

The different defaults reflect fundamentally different use cases:

#### Best Price: Optimization Focus

**Goal:** Find practical time windows for running appliances

**Constraints:**
- Appliances need time to complete cycles (dishwasher: 2-3h, EV charging: 4-8h)
- Short periods are impractical (not worth automation overhead)
- User wants genuinely cheap times, not just "slightly below average"

**Defaults:**
- **60 min minimum** - Ensures period is long enough for meaningful use
- **15% flex** - Stricter selection, focuses on truly cheap times
- **Reasoning:** Better to find fewer, higher-quality periods than many mediocre ones

**User behavior:**
- Automations trigger actions (turn on devices)
- Wrong automation = wasted energy/money
- Preference: Conservative (miss some savings) over aggressive (false positives)

#### Peak Price: Warning Focus

**Goal:** Alert users to expensive periods for consumption reduction

**Constraints:**
- Brief price spikes still matter (even 15-30 min is worth avoiding)
- Early warning more valuable than perfect accuracy
- User can manually decide whether to react

**Defaults:**
- **30 min minimum** - Catches shorter expensive spikes
- **20% flex** - More permissive, earlier detection
- **Reasoning:** Better to warn early (even if not peak) than miss expensive periods

**User behavior:**
- Notifications/alerts (informational)
- Wrong alert = minor inconvenience, not cost
- Preference: Sensitive (catch more) over specific (catch only extremes)

#### Mathematical Justification

**Peak Price Volatility:**

Price curves tend to have:
- **Sharp spikes** during peak hours (morning/evening)
- **Shorter duration** at maximum (1-2 hours typical)
- **Higher variance** in peak times than cheap times

**Example day:**
```
Cheap period:     02:00-07:00 (5 hours at 10-12 ct)  ← Gradual, stable
Expensive period: 17:00-18:30 (1.5 hours at 35-40 ct) ← Sharp, brief
```

**Implication:**
- Stricter flex on peak (15%) might miss real expensive periods (too brief)
- Longer min_length (60 min) might exclude legitimate spikes
- Solution: More flexible thresholds for peak detection

#### Design Alternatives Considered

**Option 1: Symmetric defaults (rejected)**
- Both 60 min, both 15% flex
- Problem: Misses short but expensive spikes
- User feedback: "Why didn't I get warned about the 30-min price spike?"

**Option 2: Same defaults, let users figure it out (rejected)**
- No guidance on best practices
- Users would need to experiment to find good values
- Most users stick with defaults, so defaults matter

**Option 3: Current approach (adopted)**
- **All values user-configurable** via config flow options
- **Different installation defaults** for Best Price vs. Peak Price
- Defaults reflect recommended practices for each use case
- Users who need different behavior can adjust
- Most users benefit from sensible defaults without configuration

---

## Flex Limits and Safety Caps

#### 1. Absolute Maximum: 50% (MAX_SAFE_FLEX)

**Enforcement:** `core.py` caps `abs(flex)` at 0.50 (50%)

**Rationale:**
- Above 50%, period detection becomes unreliable
- Best Price: Almost entire day qualifies (Min + 50% typically covers 60-80% of intervals)
- Peak Price: Similar issue with Max - 50%
- **Result:** Either massive periods (entire day) or no periods (min_length not met)

**Warning Message:**
```
Flex XX% exceeds maximum safe value! Capping at 50%.
Recommendation: Use 15-20% with relaxation enabled, or 25-35% without relaxation.
```

#### 2. Outlier Filtering Maximum: 25%

**Enforcement:** `core.py` caps outlier filtering flex at 0.25 (25%)

**Rationale:**
- Outlier filtering uses Flex to determine "stable context" threshold
- At > 25% Flex, almost any price swing is considered "stable"
- **Result:** Legitimate price shifts aren't smoothed, breaking period formation

**Note:** User's Flex still applies to period criteria (`in_flex` check), only outlier filtering is capped.

### Recommended Ranges (User Guidance)

#### With Relaxation Enabled (Recommended)

**Optimal:** 10-20%
- Relaxation increases Flex incrementally: 15% → 18% → 21% → ...
- Low baseline ensures relaxation has room to work

**Warning Threshold:** > 25%
- INFO log: "Base flex is on the high side"

**High Warning:** > 30%
- WARNING log: "Base flex is very high for relaxation mode!"
- Recommendation: Lower to 15-20%

#### Without Relaxation

**Optimal:** 20-35%
- No automatic adjustment, must be sufficient from start
- Higher baseline acceptable since no relaxation fallback

**Maximum Useful:** ~50%
- Above this, period detection degrades (see Hard Limits)

---

## Relaxation Strategy

### Purpose

Ensure **minimum periods per day** are found even when baseline filters are too strict.

**Use Case:** User configures strict filters (low Flex, restrictive Level) but wants guarantee of N periods/day for automation reliability.

### Multi-Phase Approach

**Each day processed independently:**
1. Calculate baseline periods with user's config
2. If insufficient periods found, enter relaxation loop
3. Try progressively relaxed filter combinations
4. Stop when target reached or all attempts exhausted

### Relaxation Increments

**Current Implementation (November 2025):**

**File:** `coordinator/period_handlers/relaxation.py`

```python
# Hard-coded 3% increment per step (reliability over configurability)
flex_increment = 0.03  # 3% per step
base_flex = abs(config.flex)

# Generate flex levels
for attempt in range(max_relaxation_attempts):
    flex_level = base_flex + (attempt × flex_increment)
    # Try flex_level with both filter combinations
```

**Constants:**
```python
FLEX_WARNING_THRESHOLD_RELAXATION = 0.25  # 25% - INFO: suggest lowering to 15-20%
FLEX_HIGH_THRESHOLD_RELAXATION = 0.30  # 30% - WARNING: very high for relaxation mode
MAX_FLEX_HARD_LIMIT = 0.50  # 50% - absolute maximum (enforced in core.py)
```

**Design Decisions:**

1. **Why 3% fixed increment?**
   - Predictable escalation path (15% → 18% → 21% → ...)
   - Independent of base flex (works consistently)
   - 11 attempts covers full useful range (15% → 48%)
   - Balance: Not too slow (2%), not too fast (5%)

2. **Why hard-coded, not configurable?**
   - Prevents user misconfiguration
   - Simplifies mental model (fewer knobs to turn)
   - Reliable behavior across all configurations
   - If needed, user adjusts `max_relaxation_attempts` (fewer/more steps)

3. **Why warn at 25% base flex?**
   - At 25% base, first relaxation step reaches 28%
   - Above 30%, entering diminishing returns territory
   - User likely doesn't need relaxation with such high base flex
   - Should either: (a) lower base flex, or (b) disable relaxation

**Historical Context (Pre-November 2025):**

The algorithm previously used percentage-based increments that scaled with base flex:
```python
increment = base_flex × (step_pct / 100)  # REMOVED
```

This caused exponential escalation with high base flex values (e.g., 40% → 50% → 60% → 70% in just 6 steps), making behavior unpredictable. The fixed 3% increment solves this by providing consistent, controlled escalation regardless of starting point.

**Warning Messages:**
```python
if base_flex >= FLEX_HIGH_THRESHOLD_RELAXATION:  # 30%
    _LOGGER.warning(
        "Base flex %.1f%% is very high for relaxation mode! "
        "Consider lowering to 15-20%% or disabling relaxation.",
        base_flex × 100,
    )
elif base_flex >= FLEX_WARNING_THRESHOLD_RELAXATION:  # 25%
    _LOGGER.info(
        "Base flex %.1f%% is on the high side. "
        "Consider 15-20%% for optimal relaxation effectiveness.",
        base_flex × 100,
    )
```

### Filter Combination Strategy

**Per Flex level, try in order:**
1. Original Level filter
2. Level filter = "any" (disabled)

**Early Exit:** Stop immediately when target reached (don't try unnecessary combinations)

**Example Flow (target=2 periods/day):**
```
Day 2025-11-19:
1. Baseline flex=15%: Found 1 period (need 2)
2. Flex=18% + level=cheap: Found 1 period
3. Flex=18% + level=any: Found 2 periods → SUCCESS (stop)
```

---

## Implementation Notes

### Key Files and Functions

**Period Calculation Entry Point:**
```python
# coordinator/period_handlers/core.py
def calculate_periods(
    all_prices: list[dict],
    config: PeriodConfig,
    time: TimeService,
) -> dict[str, Any]
```

**Flex + Distance Filtering:**
```python
# coordinator/period_handlers/level_filtering.py
def check_interval_criteria(
    price: float,
    criteria: IntervalCriteria,
) -> tuple[bool, bool]  # (in_flex, meets_min_distance)
```

**Relaxation Orchestration:**
```python
# coordinator/period_handlers/relaxation.py
def calculate_periods_with_relaxation(...) -> tuple[dict, dict]
def relax_single_day(...) -> tuple[dict, dict]
```

#### Outlier Filtering Implementation

**File:** `coordinator/period_handlers/outlier_filtering.py`

**Purpose:** Detect and smooth isolated price spikes before period identification to prevent artificial fragmentation.

**Algorithm Details:**

1. **Linear Regression Prediction:**
   - Uses surrounding intervals to predict expected price
   - Window size: 3+ intervals (MIN_CONTEXT_SIZE)
   - Calculates trend slope and standard deviation
   - Formula: `predicted = mean + slope × (position - center)`

2. **Confidence Intervals:**
   - 95% confidence level (2 standard deviations)
   - Tolerance = 2.0 × std_dev (CONFIDENCE_LEVEL constant)
   - Outlier if: `|actual - predicted| > tolerance`
   - Accounts for natural price volatility in context window

3. **Symmetry Check:**
   - Rejects asymmetric outliers (threshold: 1.5 std dev)
   - Preserves legitimate price shifts (morning/evening peaks)
   - Algorithm:
     ```python
     residual = abs(actual - predicted)
     symmetry_threshold = 1.5 × std_dev

     if residual > tolerance:
         # Check if spike is symmetric in context
         context_residuals = [abs(p - pred) for p, pred in context]
         avg_context_residual = mean(context_residuals)

         if residual > symmetry_threshold × avg_context_residual:
             # Asymmetric spike → smooth it
         else:
             # Symmetric (part of trend) → keep it
     ```

4. **Enhanced Zigzag Detection:**
   - Detects spike clusters via relative volatility
   - Threshold: 2.0× local volatility (RELATIVE_VOLATILITY_THRESHOLD)
   - Single-pass algorithm (no iteration needed)
   - Catches patterns like: 18, 35, 19, 34, 18 (alternating spikes)

**Constants:**
```python
# coordinator/period_handlers/outlier_filtering.py

CONFIDENCE_LEVEL = 2.0  # 95% confidence (2 std deviations)
SYMMETRY_THRESHOLD = 1.5  # Asymmetry detection threshold
RELATIVE_VOLATILITY_THRESHOLD = 2.0  # Zigzag spike detection
MIN_CONTEXT_SIZE = 3  # Minimum intervals for regression
```

**Data Integrity:**
- Original prices stored in `_original_price` field
- All statistics (daily min/max/avg) use original prices
- Smoothing only affects period formation logic
- Smart counting: Only counts smoothing that changed period outcome

**Performance:**
- Single pass through price data
- O(n) complexity with small context window
- No iterative refinement needed
- Typical processing time: `<`1ms for 96 intervals

**Example Debug Output:**
```
DEBUG: [2025-11-11T14:30:00+01:00] Outlier detected: 35.2 ct
DEBUG:   Context: 18.5, 19.1, 19.3, 19.8, 20.2 ct
DEBUG:   Residual: 14.5 ct > tolerance: 4.8 ct (2×2.4 std dev)
DEBUG:   Trend slope: 0.3 ct/interval (gradual increase)
DEBUG:   Predicted: 20.7 ct (linear regression)
DEBUG:   Smoothed to: 20.7 ct
DEBUG:   Asymmetry ratio: 3.2 (>1.5 threshold) → confirmed outlier
```

**Why This Approach?**

1. **Linear regression over moving average:**
   - Accounts for price trends (morning ramp-up, evening decline)
   - Moving average can't predict direction, only level
   - Better accuracy on non-stationary price curves

2. **Symmetry check over fixed threshold:**
   - Prevents false positives on legitimate price shifts
   - Adapts to local volatility patterns
   - Preserves user expectation: "expensive during peak hours"

3. **Single-pass over iterative:**
   - Predictable behavior (no convergence issues)
   - Fast and deterministic
   - Easier to debug and reason about

**Alternative Approaches Considered:**

1. **Median filtering** - Rejected: Too aggressive, removes legitimate peaks
2. **Moving average** - Rejected: Can't handle trends
3. **IQR (Interquartile Range)** - Rejected: Assumes normal distribution
4. **RANSAC** - Rejected: Overkill for 1D data, slow

---

## Debugging Tips

**Enable DEBUG logging:**
```yaml
# configuration.yaml
logger:
  default: info
  logs:
    custom_components.tibber_prices.coordinator.period_handlers: debug
```

**Key log messages to watch:**
1. `"Filter statistics: X intervals checked"` - Shows how many intervals filtered by each criterion
2. `"After build_periods: X raw periods found"` - Periods before min_length filtering
3. `"Day X: Success with flex=Y%"` - Relaxation succeeded
4. `"High flex X% detected: Reducing min_distance Y% → Z%"` - Distance scaling active

---

## Common Configuration Pitfalls

### ❌ Anti-Pattern 1: High Flex with Relaxation

**Configuration:**
```yaml
best_price_flex: 40
enable_relaxation_best: true
```

**Problem:**
- Base Flex 40% already very permissive
- Relaxation increments further (43%, 46%, 49%, ...)
- Quickly approaches 50% cap with diminishing returns

**Solution:**
```yaml
best_price_flex: 15  # Let relaxation increase it
enable_relaxation_best: true
```

### ❌ Anti-Pattern 2: Zero Min_Distance

**Configuration:**
```yaml
best_price_min_distance_from_avg: 0
```

**Problem:**
- "Flat days" (little price variation) accept all intervals
- Periods lose semantic meaning ("significantly cheap")
- May create periods during barely-below-average times

**Solution:**
```yaml
best_price_min_distance_from_avg: 5  # Use default 5%
```

### ❌ Anti-Pattern 3: Conflicting Flex + Distance

**Configuration:**
```yaml
best_price_flex: 45
best_price_min_distance_from_avg: 10
```

**Problem:**
- Distance filter dominates, making Flex irrelevant
- Dynamic scaling helps but still suboptimal

**Solution:**
```yaml
best_price_flex: 20
best_price_min_distance_from_avg: 5
```

---

## Testing Scenarios

### Scenario 1: Normal Day (Good Variation)

**Price Range:** 10 - 20 ct/kWh (100% variation)
**Average:** 15 ct/kWh

**Expected Behavior:**
- Flex 15%: Should find 2-4 clear best price periods
- Flex 30%: Should find 4-8 periods (more lenient)
- Min_Distance 5%: Effective throughout range

**Debug Checks:**
```
DEBUG: Filter statistics: 96 intervals checked
DEBUG:   Filtered by FLEX: 12/96 (12.5%)  ← Low percentage = good variation
DEBUG:   Filtered by MIN_DISTANCE: 8/96 (8.3%)  ← Both filters active
DEBUG: After build_periods: 3 raw periods found
```

### Scenario 2: Flat Day (Poor Variation)

**Price Range:** 14 - 16 ct/kWh (14% variation)
**Average:** 15 ct/kWh

**Expected Behavior:**
- Flex 15%: May find 1-2 small periods (or zero if no clear winners)
- Min_Distance 5%: Critical here - ensures only truly cheaper intervals qualify
- Without Min_Distance: Would accept almost entire day as "best price"

**Debug Checks:**
```
DEBUG: Filter statistics: 96 intervals checked
DEBUG:   Filtered by FLEX: 45/96 (46.9%)  ← High percentage = poor variation
DEBUG:   Filtered by MIN_DISTANCE: 52/96 (54.2%)  ← Distance filter dominant
DEBUG: After build_periods: 1 raw period found
DEBUG: Day 2025-11-11: Baseline insufficient (1 < 2), starting relaxation
```

### Scenario 3: Extreme Day (High Volatility)

**Price Range:** 5 - 40 ct/kWh (700% variation)
**Average:** 18 ct/kWh

**Expected Behavior:**
- Flex 15%: Finds multiple very cheap periods (5-6 ct)
- Outlier filtering: May smooth isolated spikes (30-40 ct)
- Distance filter: Less impactful (clear separation between cheap/expensive)

**Debug Checks:**
```
DEBUG: Outlier detected: 38.5 ct (threshold: 4.2 ct)
DEBUG:   Smoothed to: 20.1 ct (trend prediction)
DEBUG: Filter statistics: 96 intervals checked
DEBUG:   Filtered by FLEX: 8/96 (8.3%)  ← Very selective
DEBUG:   Filtered by MIN_DISTANCE: 4/96 (4.2%)  ← Flex dominates
DEBUG: After build_periods: 4 raw periods found
```

### Scenario 4: Relaxation Success

**Initial State:** Baseline finds 1 period, target is 2

**Expected Flow:**
```
INFO: Calculating BEST PRICE periods: relaxation=ON, target=2/day, flex=15.0%
DEBUG: Day 2025-11-11: Baseline found 1 period (need 2)
DEBUG:   Phase 1: flex 18.0% + original filters
DEBUG:     Found 1 period (insufficient)
DEBUG:   Phase 2: flex 18.0% + level=any
DEBUG:     Found 2 periods → SUCCESS
INFO: Day 2025-11-11: Success after 1 relaxation phase (2 periods)
```

### Scenario 5: Relaxation Exhausted

**Initial State:** Strict filters, very flat day

**Expected Flow:**
```
INFO: Calculating BEST PRICE periods: relaxation=ON, target=2/day, flex=15.0%
DEBUG: Day 2025-11-11: Baseline found 0 periods (need 2)
DEBUG:   Phase 1-11: flex 15%→48%, all filter combinations tried
WARNING: Day 2025-11-11: All relaxation phases exhausted, still only 1 period found
INFO: Period calculation completed: 1/2 days reached target
```

### Debugging Checklist

When debugging period calculation issues:

1. **Check Filter Statistics**
   - Which filter blocks most intervals? (flex, distance, or level)
   - High flex filtering (>30%) = Need more flexibility or relaxation
   - High distance filtering (>50%) = Min_distance too strict or flat day
   - High level filtering = Level filter too restrictive

2. **Check Relaxation Behavior**
   - Did relaxation activate? Check for "Baseline insufficient" message
   - Which phase succeeded? Early success (phase 1-3) = good config
   - Late success (phase 8-11) = Consider adjusting base config
   - Exhausted all phases = Unrealistic target for this day's price curve

3. **Check Flex Warnings**
   - INFO at 25% base flex = On the high side
   - WARNING at 30% base flex = Too high for relaxation
   - If seeing these: Lower base flex to 15-20%

4. **Check Min_Distance Scaling**
   - Debug messages show "High flex X% detected: Reducing min_distance Y% → Z%"
   - If scale factor `<`0.8 (20% reduction): High flex is active
   - If periods still not found: Filters conflict even with scaling

5. **Check Outlier Filtering**
   - Look for "Outlier detected" messages
   - Check `period_interval_smoothed_count` attribute
   - If no smoothing but periods fragmented: Not isolated spikes, but legitimate price levels

---

## Future Enhancements

### Potential Improvements

1. **Adaptive Flex Calculation:**
   - Auto-adjust Flex based on daily price variation
   - High variation days: Lower Flex needed
   - Low variation days: Higher Flex needed

2. **Machine Learning Approach:**
   - Learn optimal Flex/Distance from user feedback
   - Classify days by pattern (normal/flat/volatile/bimodal)
   - Apply pattern-specific defaults

3. **Multi-Objective Optimization:**
   - Balance period count vs. quality
   - Consider period duration vs. price level
   - Optimize for user's stated use case (EV charging vs. heat pump)

### Known Limitations

1. **Fixed increment step:** 3% cap may be too aggressive for very low base Flex
2. **Linear distance scaling:** Could benefit from non-linear curve
3. **No consideration of temporal distribution:** May find all periods in one part of day

---

## Future Enhancements

### Potential Improvements

#### 1. Adaptive Flex Calculation (Not Yet Implemented)

**Concept:** Auto-adjust Flex based on daily price variation

**Algorithm:**
```python
# Pseudo-code for adaptive flex
variation = (daily_max - daily_min) / daily_avg

if variation < 0.15:  # Flat day (< 15% variation)
    adaptive_flex = 0.30  # Need higher flex
elif variation > 0.50:  # High volatility (> 50% variation)
    adaptive_flex = 0.10  # Lower flex sufficient
else:  # Normal day
    adaptive_flex = 0.15  # Standard flex
```

**Benefits:**
- Eliminates need for relaxation on most days
- Self-adjusting to market conditions
- Better user experience (less configuration needed)

**Challenges:**
- Harder to predict behavior (less transparent)
- May conflict with user's mental model
- Needs extensive testing across different markets

**Status:** Considered but not implemented (prefer explicit relaxation)

#### 2. Machine Learning Approach (Future Work)

**Concept:** Learn optimal Flex/Distance from user feedback

**Approach:**
- Track which periods user actually uses (automation triggers)
- Classify days by pattern (normal/flat/volatile/bimodal)
- Apply pattern-specific defaults
- Learn per-user preferences over time

**Benefits:**
- Personalized to user's actual behavior
- Adapts to local market patterns
- Could discover non-obvious patterns

**Challenges:**
- Requires user feedback mechanism (not implemented)
- Privacy concerns (storing usage patterns)
- Complexity for users to understand "why this period?"
- Cold start problem (new users have no history)

**Status:** Theoretical only (no implementation planned)

#### 3. Multi-Objective Optimization (Research Idea)

**Concept:** Balance multiple goals simultaneously

**Goals:**
- Period count vs. quality (cheap vs. very cheap)
- Period duration vs. price level (long mediocre vs. short excellent)
- Temporal distribution (spread throughout day vs. clustered)
- User's stated use case (EV charging vs. heat pump vs. dishwasher)

**Algorithm:**
- Pareto optimization (find trade-off frontier)
- User chooses point on frontier via preferences
- Genetic algorithm or simulated annealing

**Benefits:**
- More sophisticated period selection
- Better match to user's actual needs
- Could handle complex appliance requirements

**Challenges:**
- Much more complex to implement
- Harder to explain to users
- Computational cost (may need caching)
- Configuration explosion (too many knobs)

**Status:** Research idea only (not planned)

### Known Limitations

#### 1. Fixed Increment Step

**Current:** 3% cap may be too aggressive for very low base Flex

**Example:**
- Base flex 5% + 3% increment = 8% (60% increase!)
- Base flex 15% + 3% increment = 18% (20% increase)

**Possible Solution:**
- Percentage-based increment: `increment = max(base_flex × 0.20, 0.03)`
- This gives: 5% → 6% (20%), 15% → 18% (20%), 40% → 43% (7.5%)

**Why Not Implemented:**
- Very low base flex (`<`10%) unusual
- Users with strict requirements likely disable relaxation
- Simplicity preferred over edge case optimization

#### 2. Linear Distance Scaling

**Current:** Linear scaling may be too aggressive/conservative

**Alternative:** Non-linear curve
```python
# Example: Exponential scaling
scale_factor = 0.25 + 0.75 × exp(-5 × (flex - 0.20))

# Or: Sigmoid scaling
scale_factor = 0.25 + 0.75 / (1 + exp(10 × (flex - 0.35)))
```

**Why Not Implemented:**
- Linear is easier to reason about
- No evidence that non-linear is better
- Would need extensive testing

#### 3. No Temporal Distribution Consideration

**Issue:** May find all periods in one part of day

**Example:**
- All 3 "best price" periods between 02:00-08:00
- No periods in evening (when user might want to run appliances)

**Possible Solution:**
- Add "spread" parameter (prefer distributed periods)
- Weight periods by time-of-day preferences
- Consider user's typical usage patterns

**Why Not Implemented:**
- Adds complexity
- Users can work around with multiple automations
- Different users have different needs (no one-size-fits-all)

#### 4. Period Boundary Handling

**Current Behavior:** Periods can cross midnight naturally

**Design Principle:** Each interval is evaluated using its **own day's** reference prices (daily min/max/avg).

**Implementation:**
```python
# In period_building.py build_periods():
for price_data in all_prices:
    starts_at = time.get_interval_time(price_data)
    date_key = starts_at.date()

    # CRITICAL: Use interval's own day, not period_start_date
    ref_date = date_key

    criteria = TibberPricesIntervalCriteria(
        ref_price=ref_prices[ref_date],      # Interval's day
        avg_price=avg_prices[ref_date],      # Interval's day
        flex=flex,
        min_distance_from_avg=min_distance_from_avg,
        reverse_sort=reverse_sort,
    )
```

**Why Per-Day Evaluation?**

Periods can cross midnight (e.g., 23:45 → 01:00). Each day has independent reference prices calculated from its 96 intervals.

**Example showing the problem with period-start-day approach:**

```
Day 1 (2025-11-21): Cheap day
  daily_min = 10 ct, daily_avg = 20 ct, flex = 15%
  Criteria: price ≤ 11.5 ct (10 + 10×0.15)

Day 2 (2025-11-22): Expensive day
  daily_min = 20 ct, daily_avg = 30 ct, flex = 15%
  Criteria: price ≤ 23 ct (20 + 20×0.15)

Period crossing midnight: 23:45 Day 1 → 00:15 Day 2
  23:45 (Day 1): 11 ct → ✅ Passes (11 ≤ 11.5)
  00:00 (Day 2): 21 ct → Should this pass?

❌ WRONG (using period start day):
  00:00 evaluated against Day 1's 11.5 ct threshold
  21 ct > 11.5 ct → Fails
  But 21ct IS cheap on Day 2 (min=20ct)!

✅ CORRECT (using interval's own day):
  00:00 evaluated against Day 2's 23 ct threshold
  21 ct ≤ 23 ct → Passes
  Correctly identified as cheap relative to Day 2
```

**Trade-off: Periods May Break at Midnight**

When days differ significantly, period can split:
```
Day 1: Min=10ct, Avg=20ct, 23:45=11ct → ✅ Cheap (relative to Day 1)
Day 2: Min=25ct, Avg=35ct, 00:00=21ct → ❌ Expensive (relative to Day 2)
Result: Period stops at 23:45, new period starts later
```

This is **mathematically correct** - 21ct is genuinely expensive on a day where minimum is 25ct.

**Market Reality Explains Price Jumps:**

Day-ahead electricity markets (EPEX SPOT) set prices at 12:00 CET for all next-day hours:
- Late intervals (23:45): Priced ~36h before delivery → high forecast uncertainty → risk premium
- Early intervals (00:00): Priced ~12h before delivery → better forecasts → lower risk buffer

This explains why absolute prices jump at midnight despite minimal demand changes.

**User-Facing Solution (Nov 2025):**

Added per-period day volatility attributes to detect when classification changes are meaningful:
- `day_volatility_%`: Percentage spread (span/avg × 100)
- `day_price_min`, `day_price_max`, `day_price_span`: Daily price range (ct/øre)

Automations can check volatility before acting:
```yaml
condition:
  - condition: template
    value_template: >
      {{ state_attr('binary_sensor.tibber_home_best_price_period', 'day_volatility_%') | float(0) > 15 }}
```

Low volatility (< 15%) means classification changes are less economically significant.

**Alternative Approaches Rejected:**

1. **Use period start day for all intervals**
   - Problem: Mathematically incorrect - lends cheap day's criteria to expensive day
   - Rejected: Violates relative evaluation principle

2. **Adjust flex/distance at midnight**
   - Problem: Complex, unpredictable, hides market reality
   - Rejected: Users should understand price context, not have it hidden

3. **Split at midnight always**
   - Problem: Artificially fragments natural periods
   - Rejected: Worse user experience

4. **Use next day's reference after midnight**
   - Problem: Period criteria inconsistent across duration
   - Rejected: Confusing and unpredictable

**Status:** Per-day evaluation is intentional design prioritizing mathematical correctness.

**See Also:**
- User documentation: `docs/user/docs/period-calculation.md` → "Midnight Price Classification Changes"
- Implementation: `coordinator/period_handlers/period_building.py` (line ~126: `ref_date = date_key`)
- Attributes: `coordinator/period_handlers/period_statistics.py` (day volatility calculation)

---

## References

- [User Documentation: Period Calculation](https://jpawlowski.github.io/hass.tibber_prices/user/period-calculation)
- [Architecture Overview](./architecture.md)
- [Caching Strategy](./caching-strategy.md)
- [AGENTS.md](https://github.com/jpawlowski/hass.tibber_prices/blob/v0.22.0/AGENTS.md) - AI assistant memory (implementation patterns)

## Changelog

- **2025-11-19**: Initial documentation of Flex/Distance interaction and Relaxation strategy fixes
