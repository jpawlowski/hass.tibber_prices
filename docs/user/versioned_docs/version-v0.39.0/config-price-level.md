---
sidebar_label: 🏷️ Price Level
---

# 🏷️ Price Level Gap Tolerance

**Settings → Devices & Services → Tibber Prices → Configure → 🏷️ Price Level**

---

Tibber's API assigns each interval a price level: VERY_CHEAP, CHEAP, NORMAL, EXPENSIVE, or VERY_EXPENSIVE. In practice, a single interval can jump to a different level briefly before jumping back — creating isolated "noise" intervals that make sensors flicker.

Gap tolerance smooths this out.

## Setting

| Setting | Default | Description |
|---------|---------|-------------|
| **Gap tolerance** | 1 | Number of consecutive "mismatched" intervals to fill in automatically |

### Example

With gap tolerance = 1, a lone NORMAL interval surrounded by CHEAP on both sides is automatically corrected to CHEAP:

```
Before:  CHEAP  CHEAP  NORMAL  CHEAP  CHEAP
After:   CHEAP  CHEAP  CHEAP   CHEAP  CHEAP
                        ↑ filled in
```

With gap tolerance = 0, no smoothing is applied and every interval uses the raw API level.

## Notes

- This applies to Tibber's own level classification (separate from the [Price Rating](config-price-rating.md) which is calculated by this integration)
- Increasing gap tolerance beyond 2 is rarely useful — larger gaps usually represent genuine price differences
- The gap tolerance here only affects level sensors; the separate gap tolerance in [Best Price](config-best-price.md) and [Peak Price](config-peak-price.md) settings controls period merging behavior
