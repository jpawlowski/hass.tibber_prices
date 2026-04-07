---
comments: false
---

# Glossary

Quick reference for terms used throughout the documentation.

## A

**API Token**
: Your personal access key from Tibber. Get it at [developer.tibber.com](https://developer.tibber.com/settings/access-token).

**Attributes**
: Additional data attached to each sensor (timestamps, statistics, metadata). Access via `state_attr()` in templates.

## B

**Best Price Period**
: Automatically detected time window with favorable electricity prices. Ideal for scheduling dishwashers, heat pumps, EV charging.

**Binary Sensor**
: Sensor with ON/OFF state (e.g., "Best Price Period Active"). Used in automations as triggers.

## C

**Currency Display Mode**
: Configurable setting for how prices are shown. Choose base currency (€, kr) or subunit (ct, øre). Smart defaults apply: EUR → subunit, NOK/SEK/DKK → base.

**Coordinator**
: Home Assistant component managing data fetching and updates. Polls Tibber API every 15 minutes.

## D

**Dynamic Icons**
: Icons that change based on sensor state (e.g., battery icons showing price level). See [Dynamic Icons](dynamic-icons.md).

## F

**Flex (Flexibility)**
: Configuration parameter controlling how strict period detection is. Higher flex = more periods found, but potentially at higher prices.

## I

**Interval**
: 15-minute time slot with fixed electricity price (00:00-00:15, 00:15-00:30, etc.).

## L

**Level**
: Price classification within a day (LOWEST, LOW, NORMAL, HIGH, HIGHEST). Based on daily min/max prices.

## M

**Min Distance**
: Threshold requiring periods to be at least X% below daily average. Prevents detecting "cheap" periods during expensive days.

## P

**Peak Price Period**
: Time window with highest electricity prices. Use to avoid heavy consumption.

**Price Info**
: Complete dataset with all intervals (yesterday, today, tomorrow) including enriched statistics.

## Q

**Quarter-Hourly**
: 15-minute precision (4 intervals per hour, 96 per day).

## R

**Rating**
: Statistical price classification (VERY_CHEAP, CHEAP, NORMAL, EXPENSIVE, VERY_EXPENSIVE). Based on 24h averages and thresholds.

**Relaxation**
: Automatic loosening of period detection filters when target period count isn't met. Ensures you always get usable periods.

## S

**State**
: Current value of a sensor (e.g., price in ct/kWh, "ON"/"OFF" for binary sensors).

**State Class**
: Home Assistant classification for long-term statistics (MEASUREMENT, TOTAL, or none).

## T

**Trailing Average**
: Average price over the past 24 hours from current interval.

**Leading Average**
: Average price over the next 24 hours from current interval.

**Trend**
: Directional price movement indicator. Simple trends compare current price to future averages (1h–12h). Current trend represents the ongoing price direction using a 3-hour outlook. Uses a 5-level scale: strongly_falling, falling, stable, rising, strongly_rising.

**Trend Hysteresis**
: Stability mechanism for trend change prediction. Requires 2 consecutive intervals confirming a different trend before reporting a change. Prevents false alarms from single-interval price spikes.

## V

**V-Shaped Day**
: Day with a V- or U-shaped price curve where prices drop to very cheap levels for an extended period. The Best Price Period covers only the absolute minimum, but favorable conditions may last much longer. See [V-Shaped Days](concepts.md#v-shaped-and-u-shaped-price-days).

**Volatility**
: Measure of price stability (LOW, MEDIUM, HIGH). High volatility = large price swings = good for timing optimization.

---

💡 **See Also:**
- [Core Concepts](concepts.md) - In-depth explanations
- [Sensors](sensors.md) - How sensors use these concepts
- [Period Calculation](period-calculation.md) - Deep dive into period detection
