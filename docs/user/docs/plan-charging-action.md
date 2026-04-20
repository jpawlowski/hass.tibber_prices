# Plan Charging Action

The `plan_charging` action turns **battery parameters** into a complete **cost-minimized charging schedule**. Instead of manually computing energy, duration, and power, you describe the battery (capacity, current SoC, target SoC, max power) and the action returns a per-interval plan with SoC progression, cost totals, and segment grouping.

:::tip When to use this
If you already know the duration in minutes and just need the cheapest time window, use [`find_cheapest_hours`](scheduling-actions.md#find-cheapest-hours) or [`find_cheapest_block`](scheduling-actions.md#find-cheapest-block). Use `plan_charging` when you know your battery/EV parameters and want the integration to compute the duration, account for charging losses, and produce a SoC progression.
:::

## At a Glance

| Situation | Example |
|-----------|---------|
| Home battery: "Charge from 20% to 80%, efficiency 0.92" | `current_soc_percent: 20`, `target_soc_percent: 80`, `battery_capacity_kwh: 10` |
| EV with 3-phase charger: "Use 1/2/3 phases as needed" | `charge_power_steps_w: [1380, 4140, 11000]` |
| Battery with modulation: "30 W – 1200 W continuous" | `min_charge_power_w: 30`, `max_charge_power_w: 1200` |
| Deadline-aware: "At least 50% before next peak" | `must_reach_soc_percent: 50`, `must_reach_by_event: next_peak_period` |
| Arbitrage: "Only charge if later discharge is profitable" | `expected_discharge_price: 0.28`, `reserve_for_discharge: true` |

## Required Inputs

| Field | Description |
|-------|-------------|
| `max_charge_power_w` | Maximum charging power in watts (upper bound for every interval). |
| `current_soc_percent` **or** `current_soc_kwh` | Current battery state of charge. |
| `target_soc_percent` **or** `target_soc_kwh` | Desired battery state of charge. |
| `battery_capacity_kwh` | Required when you use percent values. |

All other inputs (deadline, power steps, grid limit, economics, search range) are optional.

## Choosing Between Fixed / Continuous / Stepped Power

| Mode | Trigger | Behavior |
|------|---------|----------|
| **Fixed** | Only `max_charge_power_w` set | Every selected interval charges at full power. Last interval may over-shoot the target slightly (rounding up). |
| **Continuous** | Add `min_charge_power_w` | Planner can reduce the final partial interval down to the minimum power — no over-shoot. |
| **Stepped** | Add `charge_power_steps_w: [a, b, c]` | Planner picks the smallest allowed step that covers the remaining energy. Mutually exclusive with `min_charge_power_w`. |

## Deadlines

Combine a **minimum SoC** with a **deadline**:

- `must_reach_soc_percent` / `must_reach_soc_kwh` — the minimum you need by the deadline.
- Then pick one of:
  - `must_reach_by` — absolute datetime.
  - `must_reach_by_event` — one of `midnight`, `next_peak_period`, `next_best_period_end`.

The planner runs a two-pass schedule: first guarantee the minimum SoC before the deadline using the cheapest pre-deadline intervals, then fill the remaining target with the cheapest intervals from the full search range.

## Economics (Arbitrage)

For "charge cheap now, discharge expensive later" use cases:

- `discharging_efficiency` — fraction still usable when discharged (default `1.0`).
- `expected_discharge_price` — expected price per kWh at discharge time (in your configured display unit).
- `reserve_for_discharge` — when `true`, discards intervals that are unprofitable given the round-trip efficiency.
- `max_cost_per_kwh` — a hard ceiling; any interval above this price is discarded before scheduling.

The response's `economics.break_even_price` tells you the maximum charging price at which the round-trip still breaks even.

## Examples

### Home battery — charge from 20% to 80% overnight

<details>
<summary>Show YAML</summary>

```yaml
service: tibber_prices.plan_charging
data:
  battery_capacity_kwh: 10
  current_soc_percent: 20
  target_soc_percent: 80
  charging_efficiency: 0.92
  max_charge_power_w: 2500
  search_scope: remaining_today
response_variable: plan
```

</details>

### EV — 3-phase, at least 50% before next peak period

<details>
<summary>Show YAML</summary>

```yaml
service: tibber_prices.plan_charging
data:
  battery_capacity_kwh: 60
  current_soc_percent: 30
  target_soc_percent: 80
  must_reach_soc_percent: 50
  must_reach_by_event: next_peak_period
  max_charge_power_w: 11000
  charge_power_steps_w: [1380, 4140, 11000]
  grid_import_limit_w: 16000
response_variable: plan
```

</details>

### Battery arbitrage — only if profitable

<details>
<summary>Show YAML</summary>

```yaml
service: tibber_prices.plan_charging
data:
  battery_capacity_kwh: 10
  current_soc_percent: 10
  target_soc_percent: 100
  charging_efficiency: 0.92
  discharging_efficiency: 0.92
  expected_discharge_price: 0.28   # ct/kWh value expected when discharging
  reserve_for_discharge: true
  max_charge_power_w: 3000
  search_scope: next_48h
response_variable: plan
```

</details>

## Response Structure

The response contains the following top-level keys:

| Key | Description |
|-----|-------------|
| `intervals_found` | `true` when a schedule was produced. |
| `battery` | Normalized SoC / capacity / efficiency / `achieved_soc_kwh` (what you actually reach with the returned schedule). |
| `charging` | Mode, total duration, total energy, total cost, and the `schedule` block. |
| `charging.schedule` | `segments[]`, `intervals[]`, `segment_count`, `seconds_until_start`, `seconds_until_end`, and price statistics. |
| `deadline` | Present when a deadline was set — includes `must_reach_by`, `must_reach_soc_kwh`, `achieved_soc_kwh`, `deadline_met`. |
| `economics` | Present when any economic parameter was set — includes `break_even_price`, `expected_net_savings`, `round_trip_efficiency`. |
| `price_comparison` | Difference between the selected schedule and the most expensive equivalent window. |
| `relaxation_applied` / `relaxation_steps` | Whether the schedule was relaxed to fit available data. |
| `reason` | Stable reason code when no schedule was found (see below). |

### Per-Interval Fields

Each entry in `charging.schedule.intervals[]` includes:

- `starts_at`, `ends_at`, `price`, `level`, `rating_level`
- `power_w` — power assigned to this interval (watts)
- `grid_energy_kwh` — energy drawn from the grid
- `stored_energy_kwh` — energy actually stored after losses
- `soc_after_kwh`, `soc_after_percent` — cumulative SoC after this interval

## Reason Codes

When no schedule is found, `reason` contains one of:

| Code | Meaning |
|------|---------|
| `already_at_target` | Current SoC is already at or above target — no charging needed. |
| `no_data_in_range` | The search range has no price data. |
| `no_intervals_matching_level_filter` | `min_price_level` / `max_price_level` filtered everything out. |
| `no_intervals_after_economic_filter` | `max_cost_per_kwh` or `reserve_for_discharge` filtered everything out. |
| `energy_unreachable` | The energy needed cannot be charged within the available intervals + power limits. |
| `energy_unreachable_by_deadline` | The minimum SoC cannot be reached before the deadline with the available intervals. |
| `selection_above_distance_threshold` | `min_distance_from_avg` is not satisfied by the cheapest selection. |

## Related

- [`find_cheapest_hours`](scheduling-actions.md#find-cheapest-hours) — when you already know the duration in minutes.
- [`find_cheapest_block`](scheduling-actions.md#find-cheapest-block) — for appliances that must run uninterrupted.
- [Scheduling Actions](scheduling-actions.md) — shared parameters (search range, price filters, relaxation).
