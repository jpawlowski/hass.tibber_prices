# Actions Overview

Tibber Prices provides **actions** (formerly called "services") that you can use in automations, scripts, and dashboards. Home Assistant surfaces them in **Developer Tools → Actions** and in the automation/script editor.

Behind the scenes, YAML still uses the `service:` key — but the UI calls them "actions".

## Finding Your Config Entry ID

Most actions accept an optional `entry_id` parameter that identifies the **config entry** (= integration instance) of the Tibber home you want to query. **If you only have one home configured, you can omit `entry_id` entirely** — the integration auto-selects your only config entry. If you have multiple homes, you need to specify which one.

### In the Action UI — no lookup needed

When you use the action through the Home Assistant interface (Developer Tools → Actions, or the Action picker inside the automation / script editor), the `entry_id` field renders as a **dropdown list** showing all your configured Tibber Prices instances. Just select your home from the drop-down and Home Assistant fills in the correct ID automatically. You never have to deal with the raw ID string.

### In YAML — copy from the integration menu

When you write YAML directly (automations, scripts, Lovelace dashboard cards), you need the actual ID string. The quickest way to get it:

1. Go to **Settings → Devices & Services**
2. Find the **Tibber Prices** integration card
3. Click the **⋮** (three-dot) menu on the card
4. Choose **"Copy Config Entry ID"**
5. Paste the value wherever you see `YOUR_CONFIG_ENTRY_ID` in the YAML examples

The ID looks like a long alphanumeric string, for example `01JKPC7AB3EF4GH5IJ6KL7MN8P`.

:::tip Multiple homes?
If you have configured more than one Tibber home, each home has its own config entry ID. Repeat the steps above for each integration card to get the individual IDs.
:::

## All Actions at a Glance

### Scheduling Actions

Find the cheapest (or most expensive) time windows for your appliances. Ideal for automating when to run devices based on real price data.

| Action | Description | Best For |
|--------|-------------|----------|
| [`find_cheapest_block`](scheduling-actions.md#find-cheapest-block) | Cheapest contiguous window | Dishwasher, washing machine, dryer |
| [`find_cheapest_hours`](scheduling-actions.md#find-cheapest-hours) | Cheapest N hours (non-contiguous OK) | EV charging, battery storage, pool pump |
| [`find_cheapest_schedule`](scheduling-actions.md#find-cheapest-schedule) | Multiple appliances, no overlap | Dishwasher + washing machine overnight |
| [`find_most_expensive_block`](scheduling-actions.md#find-most-expensive-block) | Most expensive contiguous window | Peak avoidance, battery discharge |
| [`find_most_expensive_hours`](scheduling-actions.md#find-most-expensive-hours) | Most expensive N hours | Demand response, consumption shifting |
| [`plan_charging`](plan-charging-action.md) | Battery/EV schedule from SoC + power | Home battery, EV, deadline-aware charging |

**→ [Scheduling Actions — Full Guide](scheduling-actions.md)** with parameters, response formats, decision flowchart, and automation examples.
**→ [Plan Charging Action — Guide](plan-charging-action.md)** for battery/EV charging scheduled from SoC and power (not duration).

### Chart & Visualization Actions

Generate chart-ready data and ApexCharts configurations for your dashboards.

| Action | Description |
|--------|-------------|
| [`get_chartdata`](chart-actions.md#tibber_pricesget_chartdata) | Price data in chart-friendly formats (arrays, filtering, rolling windows) |
| [`get_apexcharts_yaml`](chart-actions.md#tibber_pricesget_apexcharts_yaml) | Auto-generated ApexCharts card configuration with color-coded price levels |

**→ [Chart & Visualization Actions — Full Guide](chart-actions.md)** with parameters, examples, rolling window modes, and migration guide.

### Data & Utility Actions

Fetch raw price data or refresh cached information.

| Action | Description |
|--------|-------------|
| [`get_price`](data-actions.md#tibber_pricesget_price) | Fetch raw price intervals for any time range (with intelligent caching) |
| [`refresh_user_data`](data-actions.md#tibber_pricesrefresh_user_data) | Force-refresh user data (homes, subscriptions) from Tibber API |

**→ [Data & Utility Actions — Full Guide](data-actions.md)** with parameters and response formats.
