---
sidebar_label: 📈 Price Trend
---

# 📈 Price Trend Thresholds

**Settings → Devices & Services → Tibber Prices → Configure → 📈 Price Trend**

---

Price trend sensors compare the upcoming price average to the current price and report whether prices are rising, falling, or stable. These thresholds define how much of a change is required before the trend sensor changes state.

See **[Trend Sensors](sensors-trends.md)** for a full explanation of all trend sensors, how volatility-adaption works, and automation examples.

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| **Rising** | +3% | Future average this much above current → `rising` |
| **Strongly rising** | +9% | Future average far above current → `strongly_rising` |
| **Falling** | -3% | Future average this much below current → `falling` |
| **Strongly falling** | -9% | Future average far below current → `strongly_falling` |

Prices within the rising/falling range are reported as `stable`.

## Volatility-adaptive thresholds

On high-volatility days, the thresholds automatically widen to prevent the trend sensor from flickering constantly due to natural price variation. The effective threshold is scaled based on the day's [volatility level](config-volatility.md):

- **Low volatility**: Thresholds used as-is
- **Moderate volatility**: Thresholds slightly widened
- **High / Very High volatility**: Thresholds significantly widened

This means the same `rising` threshold (3%) may correspond to a 5% effective threshold on a volatile day. The scaling is automatic — you only need to configure the baseline values here.

## Adjusting for your market

- If trend sensors flicker too often on typical days → increase all thresholds slightly (e.g., 4% / 12%)
- If trend sensors rarely change even on obviously moving price days → decrease thresholds (e.g., 2% / 6%)
- For markets with structural day/night patterns, consider using the `strongly_*` states in automations to ensure only major movements trigger actions
