---
sidebar_label: 🕰️ Time-Travel Views
---

# Time-Travel Views

A **time-travel view** shows one of your homes exactly as it looked at a point in the past. It is not a history graph: the view has its own complete set of sensors, its own device, and its own clock — a clock that runs at normal speed but trails real time by a fixed offset.

Set up a view with a `-7 days` offset and, at 14:30 today, it reports the prices, levels, ratings and best/peak price periods of 14:30 last week. Fifteen minutes later it reports 14:45 last week. Tomorrow it reports the day after last week.

## What it is good for

**Rehearsing automations.** Your washing-machine automation is supposed to start in the cheapest period. Point it at a view instead of the live device and you can watch it decide against a day whose prices you already know — including the part where tomorrow's prices only show up in the afternoon.

**Comparing days.** Put the live device and a view side by side in an ApexCharts card to see today against the same weekday last week, or against the same date last year.

**Reproducing problems.** "The best price period was wrong on the 12th" is much easier to investigate on a view pinned to the 12th than from recorder history.

## Adding a view

**Settings → Devices & Services → Tibber Prices → Add time-travel view**

Views belong to a home, so you add them on the entry of the home you want to travel through. Add as many as you like — each one is independent.

### Offset mode

| Mode | Behaviour | Use it for |
|---|---|---|
| **A number of days ago** | Shifts by a fixed number of days | Recent days, weekday comparisons, rehearsing automations |
| **The same date in an earlier year** | Same month and day, earlier year | Christmas last year, seasonal comparisons |

Yearly mode only appears once a full year of quarter-hourly price data exists (see [Limits](#limits)); before that the flow goes straight to the day offset.

### Settings

**Days / years back** — how far the view travels. The slider only offers offsets Tibber actually has data for, so it grows over time.

**Additional time offset** — optional fine-tuning in hours and minutes, subtracted on top. `-2 days` plus `02:30` lands 2 days and 2½ hours back. Handy for lining a view up with a specific moment.

**Withhold tomorrow's prices until they were published** (on by default) — see [Tomorrow realism](#tomorrow-realism).

**Arrival hour** (13 by default) — the hour at which tomorrow's prices appear. Tibber publishes them around 13:00 local time.

**Headless** (off by default) — see [Headless views](#headless-views).

The view's name is derived from the home and the offset, e.g. `My House (7 days ago)`. You can rename the device afterwards; the integration will not overwrite a name you set yourself.

## Tomorrow realism

Historical data is complete — the API will happily hand a view the day after its today, at any hour. That quietly breaks the most useful thing about a view: rehearsing an automation that waits for tomorrow's prices.

With realism enabled (the default), a view hides tomorrow's intervals until its own clock passes the arrival hour, exactly as the day originally played out:

- **Before 13:00 view time:** `tomorrow_data_available` is off, tomorrow's sensors are empty
- **At 13:00 view time:** tomorrow's prices appear, periods recalculate

Turn it off if you want the full historical range at all times — for a comparison chart, for instance, where the pretence just gets in the way.

## Headless views

A view normally creates the full set of entities — the same 100+ sensors the live device has. Three comparison views therefore add several hundred entities.

A **headless** view creates only its diagnostic sensors. It still fetches and caches its data, and that data stays reachable through the [actions](actions.md) — point any of them at the view with the `view_id` parameter (see [Using a view from an action](#using-a-view-from-an-action)). `get_chartdata` returns the view's series directly, so a headless view works fine as a chart source while keeping the entity list manageable. Their name carries a `[headless]` marker.

`get_apexcharts_yaml` is the one exception: the card it generates references its data by entity ID, and a headless view has none. Use `get_chartdata` for those, or make the view non-headless if you want a generated card.

## Using a view from an action

Every price-reading action takes a **`view_id`** parameter. Pass a view's device and the action answers as that view: its clock decides what "now" means, and its own cached prices are used.

```yaml
action: tibber_prices.find_cheapest_block
data:
  view_id: 0a1b2c3d4e5f...     # the view's device
  search_scope: next_24h
  duration:
    hours: 1
    minutes: 30
```

With a `-7 days` view this searches *last week's* next 24 hours. That is the whole point: the same automation logic you run live can be replayed against a day whose outcome you already know.

Relative ranges (`next_24h`, `remaining_today`, `search_start_offset_minutes`, and the default range) all follow the view's clock. Absolute ranges (`search_start`, `search_start_time`) are taken literally, so you can also point a view at a specific historical window.

The picker lists only your time-travel views — the home itself is already what the `entry_id` field selects. Leave `view_id` empty for live data.

**You do not need `entry_id` as well.** A view belongs to exactly one home, so picking the view already says which home. Setting both is fine as long as they agree — handy when you had already selected a home before adding the view.

:::caution With several homes, the view picker lists them all
Home Assistant can only filter a device picker by integration, not by whatever you chose in another field. So if you have more than one home, the `view_id` dropdown shows the views of *every* home — including ones that do not match the `entry_id` above it.

Picking a mismatched pair is rejected with an error naming both homes, rather than resolved in favour of one of them; either choice would silently answer for a home you did not ask about. The fix is either to pick a view of the home in `entry_id`, or simply to clear `entry_id` — the view already identifies its home.
:::

The parameter is available on `get_price`, `get_chartdata`, `get_apexcharts_yaml`, `find_cheapest_block`, `find_most_expensive_block`, `find_cheapest_hours`, `find_most_expensive_hours`, `find_cheapest_schedule` and `plan_charging`. Account-level actions (`refresh_user_data`) have no use for it.

## Knowing what you are looking at

Every device — live or a view — carries diagnostic sensors describing what it is showing. They are disabled by default; enable them under **Settings → Devices & Services → Tibber Prices → Entities**.

| Sensor | Shows |
|---|---|
| **Data Mode** | `Live`, `Time-travel (days)` or `Time-travel (yearly)` |
| **Shown Time** | The moment this device is currently reporting |
| **Time-travel Days Offset** | Day offset, empty outside days mode |
| **Time-travel Years Offset** | Year offset, empty outside yearly mode |
| **Time-travel Time Offset** | The additional fine-tuning, e.g. `-02:30` |
| **Headless Mode** | Whether the device only carries diagnostics |

On the live device these read `Live` with no offsets — which is the answer you want when comparing two entities in a chart and you are not sure which is which.

## Limits

**Nothing before 1 October 2025.** Tibber switched from hourly to quarter-hourly prices on that date. This integration's calculations are built for 15-minute intervals and cannot interpret the older hourly data, so views never reach further back. The offset slider enforces this, and a view that would cross the line reports its entities as unavailable rather than showing something misleading.

Because a view also needs the two days before its own date for trailing averages, the practical floor is 3 October 2025. Yearly mode therefore becomes usable in October 2026.

**29 February.** In yearly mode there is no 29 February in a non-leap target year. On that one day the view reports unavailable and resumes on 1 March. It deliberately does *not* slide to a neighbouring date — a comparison against the wrong day is worse than no comparison.

**Tibber's retention.** How far back Tibber serves historical prices is up to Tibber, and may be shorter than the slider allows. A view whose data is missing shows unavailable entities; nothing is ever synthesised to fill a gap.

**API usage.** Each view polls independently. After its first fetch the data is cached, so in steady state a view costs roughly one extra request per day, when its own midnight rolls over. Still, views are not free — configure the ones you will actually look at.

## Changing or removing a view

**Settings → Devices & Services → Tibber Prices → (view) → Configure** changes the offset and behaviour. The offset mode stays fixed; add a second view if you want to compare modes.

Changing a view reloads the integration entry, so its entities briefly become unavailable. Deleting a view removes its entities, its device and its cached data.

## Notes

- Views inherit all price settings (rating thresholds, flexibility, currency display, …) from the home's configuration. Changing an option applies to the live device and every view of that home at once.
- A view's repair notices are not shown separately. Data problems belong to the home and are reported on the live device.
- Views are diagnostic tools, not history storage. For long-term analysis, use Home Assistant's recorder and statistics on the live sensors.
