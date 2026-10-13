---
sidebar_label: 💱 Currency Display
---

# 💱 Currency Display

**Settings → Devices & Services → Tibber Prices → Configure → 💱 Currency Display**

---

## Display Mode

Choose whether price sensor states show values in **base currency** or **subunit**:

| Mode | Example | Smart default |
|------|---------|---------------|
| **Base currency** | 0.2534 €/kWh, 2.53 kr/kWh | NOK, SEK, DKK |
| **Subunit** (default for EUR) | 25.34 ct/kWh, 25.3 øre/kWh | EUR |

The smart default is automatically applied when you first set up the integration based on your Tibber account currency.

:::caution Decide before building automations
Switching the display mode later changes **all** price sensor state values (e.g., 25.34 → 0.2534). This will break:
- Numeric thresholds in automations and conditions
- Template sensors and conditional cards with hardcoded values

**If you do switch later:**

1. A **repair notification** from this integration appears immediately in your sidebar — it reminds you to update automations and dashboards.
2. HA's Recorder detects the unit mismatch and shows a **"The unit has changed"** dialog (may take a few minutes or until the next statistics run). Choose **"Delete all old statistic data"** to start fresh. Do _not_ choose "Update the unit without converting" — that re-labels old numbers with the new unit, making historical values factually wrong.
3. Update every **automation trigger and condition** with a numeric price value.
4. Update **dashboard cards** with hardcoded thresholds or unit labels.
:::

## Price Precision and Rounding

All prices are received from the Tibber API in base currency and processed without loss of precision. The sensor **state value** is rounded and stored as follows:

| Display Mode | Stored precision | Example |
|---|---|---|
| **Subunit** (ct, øre) | 2 decimal places | 25.34 ct/kWh |
| **Base currency** (€, kr) | 4 decimal places | 0.2534 €/kWh |

This applies to both sensor states and attributes (e.g., `energy_price`, `price_mean`, `price_min`).

### Default display precision

Home Assistant shows fewer decimals than the stored value by default — enough for a quick glance. The integration sets these defaults per sensor type:

| Sensor type | Subunit default | Base currency default |
|---|---|---|
| **Current / Next / Previous interval price** | 2 decimals (25.34 ct) | 4 decimals (0.2534 €) |
| **All other price sensors** (averages, min/max, …) | 1 decimal (25.3 ct) | 2 decimals (0.25 €) |
| **Energy Dashboard sensor** | — | 4 decimals (always) |

You can override the displayed precision per entity in the HA UI:

1. Go to **Settings → Devices & Services → Entities**
2. Select a price sensor → click the gear icon
3. Change **Display precision** to your preference

**Practical ceiling:** Subunit values have exactly 2 decimal places stored — setting more than 2 shows trailing zeros. Base currency values have 4 decimal places stored — 3–4 decimals are meaningful.
