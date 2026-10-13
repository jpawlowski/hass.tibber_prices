---
sidebar_label: 📊 Chart Data Export
---

# 📊 Chart Data Export Sensor (Legacy)

**Settings → Devices & Services → Tibber Prices → Configure → 📊 Chart Data Export**

---

:::caution Legacy feature
Reading price data from entity attributes is the older way for other integrations and cards to get chart data. For new setups, use the **[get_chartdata action](chart-actions.md)** instead — it is more flexible, does not require a dedicated sensor, and returns data on demand. The sensor remains for consumers that can only read sensor attributes, such as [tibber-graph](sensors-overview.md#use-with-tibber-graph).
:::

## What this page does

This configuration page controls whether the legacy chart data export sensor is active. If you already use this sensor in existing dashboards or automations and don't want to migrate yet, leave it enabled.

## Migration to actions

The [Chart Actions](chart-actions.md) page covers the recommended approach for fetching chart data via HA actions (formerly services), including ready-to-use examples for ApexCharts and other chart cards.

If you have existing automations or cards using the legacy sensor, the [Chart Data Export legacy reference](chart-actions.md) includes migration guidance.
