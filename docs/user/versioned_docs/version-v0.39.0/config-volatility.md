---
sidebar_label: 💨 Price Volatility
---

# 💨 Price Volatility Thresholds

**Settings → Devices & Services → Tibber Prices → Configure → 💨 Price Volatility**

---

Volatility sensors measure how much prices vary throughout the day using the **Coefficient of Variation (CV)** — the ratio of the standard deviation to the mean. A higher CV means more extreme price swings and greater optimization potential.

See **[Volatility Sensors](sensors-volatility.md)** for a full explanation of all volatility sensors and how to use them in automations.

## Thresholds

These thresholds define the boundaries between volatility levels:

| Level | Default CV | Meaning |
|-------|-----------|---------|
| **Moderate** | ≥ 15% | Noticeable variation — some optimization potential |
| **High** | ≥ 30% | Significant swings — good for timing optimization |
| **Very High** | ≥ 50% | Extreme volatility — maximum optimization benefit |

Days below the Moderate threshold are classified as **Low** volatility.

## Adjusting for your market

The defaults work well for most European electricity markets. You may want to adjust if:

- **Your market rarely exceeds 20% CV**: Lower the Moderate threshold to 10% so you still get meaningful classifications
- **Your market routinely hits 50%+ CV**: Raise the Very High threshold to 70%+ to distinguish truly exceptional days

:::tip Volatility affects Trend thresholds too
The [Price Trend](config-price-trend.md) thresholds automatically widen on high-volatility days to prevent constant state changes. Changes here indirectly affect trend sensitivity.
:::
