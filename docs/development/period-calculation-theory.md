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

---

## Flex Limits and Safety Caps

### Hard Limits (Enforced in Code)

#### 1. Absolute Maximum: 50%

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

**Problem (Before Fix):**
```python
# OLD: Increment scales with base Flex
increment = base_flex × (step_pct / 100)

# Example: base_flex=40%, step_pct=25%
increment = 0.40 × 0.25 = 0.10 (10% per step!)
# After 6 steps: 40% → 50% → 60% → 70% → 80% → 90% → 100% (explosion!)
```

**Solution (Current):**
```python
# NEW: Cap increment at 3% per step
raw_increment = base_flex × (step_pct / 100)
capped_increment = min(raw_increment, 0.03)  # 3% maximum

# Example: base_flex=40%, step_pct=25%
increment = min(0.10, 0.03) = 0.03 (3% per step)
# After 8 steps: 40% → 43% → 46% → 49% → 52% → 55% → 58% → 61% (controlled!)
```

**Rationale:**
- High base Flex (30%+) already very permissive
- Large increments push toward 100% too quickly
- 100% Flex = accept ALL prices (meaningless periods)

**Warning Threshold:**
- If base Flex > 30% with relaxation enabled: Warn user to lower base Flex

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

### Debugging Tips

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
best_price_min_distance_from_avg: 5  # Keep at least 5%
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

### Scenario 2: Flat Day (Poor Variation)

**Price Range:** 14 - 16 ct/kWh (14% variation)
**Average:** 15 ct/kWh

**Expected Behavior:**
- Flex 15%: May find 1-2 small periods (or zero if no clear winners)
- Min_Distance 5%: Critical here - ensures only truly cheaper intervals qualify
- Without Min_Distance: Would accept almost entire day as "best price"

### Scenario 3: Extreme Day (High Volatility)

**Price Range:** 5 - 40 ct/kWh (700% variation)
**Average:** 18 ct/kWh

**Expected Behavior:**
- Flex 15%: Finds multiple very cheap periods (5-6 ct)
- Outlier filtering: May smooth isolated spikes (30-40 ct)
- Distance filter: Less impactful (clear separation between cheap/expensive)

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

## References

- [User Documentation: Period Calculation](../user/period-calculation.md)
- [Architecture Overview](./architecture.md)
- [Caching Strategy](./caching-strategy.md)
- [AGENTS.md](../../AGENTS.md) - AI assistant memory (implementation patterns)

## Changelog

- **2025-11-19**: Initial documentation of Flex/Distance interaction and Relaxation strategy fixes
