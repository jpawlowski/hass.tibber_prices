---
sidebar_label: 📊 Price Rating
---

# 📊 Price Rating Thresholds

**Settings → Devices & Services → Tibber Prices → Configure → 📊 Price Rating**

---

Price ratings classify each 15-minute interval as **LOW**, **NORMAL**, or **HIGH** relative to the 24-hour trailing average. Sensors and automations can use these ratings to decide when to run appliances.

See **[Ratings & Levels](sensors-ratings-levels.md)** for a full explanation of how ratings work and which sensors expose them.

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| **Low threshold** | -10% | Prices this far below the trailing average → rated **LOW** |
| **High threshold** | +10% | Prices this far above the trailing average → rated **HIGH** |
| **Hysteresis** | 2% | Buffer zone around thresholds — prevents rapid flickering when a price hovers right at the boundary |
| **Gap tolerance** | 1 | Smooths isolated rating blocks: a lone NORMAL interval surrounded by LOW on both sides gets corrected to LOW |

## How thresholds are applied

```
Trailing 24h average: 20 ct/kWh
Low threshold: -10%  → prices ≤ 18 ct → LOW
High threshold: +10% → prices ≥ 22 ct → HIGH
Everything else      → NORMAL
```

Hysteresis adds an inner dead-band: once a rating is set to LOW, it stays LOW until the price rises above `18 ct + 2% = 18.36 ct`. This prevents sensors from flickering between LOW and NORMAL when prices are right at the boundary.

## Adjusting for your market

**Markets with low daily price variation** (e.g., day typically stays within ±5%):
- Lower the thresholds: try -5% / +5%
- This keeps meaningful LOW/HIGH periods even on calm days

**Markets with high daily variation** (e.g., ±30% swings):
- Raise the thresholds: try -15% / +15%
- This reserves LOW/HIGH for genuinely exceptional periods only
- Consider using [Volatility](config-volatility.md) sensors alongside ratings on such days
