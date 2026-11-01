# Third-Party Cards & Integrations

Besides the built-in [ApexCharts YAML generator](chart-examples.md), you can feed your Tibber price data into other cards and integrations. This page explains the two ways to do that, which one to prefer, and which projects are known to work.

:::tip Entity ID tip
`<home_name>` is a placeholder for your Tibber home display name in Home Assistant. Entity IDs are derived from the displayed name (localized), so the exact slug may differ. **Can't find a sensor?** Use the **[Entity Reference (All Languages)](sensor-reference.md)** to search by name in your language.
:::

## Two Ways to Get Price Data Out

| | **Action** (recommended) | **Sensor attributes** (compatibility) |
|---|---|---|
| How | `tibber_prices.get_chartdata` returns the data when called | **Chart Data Export** (`chart_data_export`) keeps the list in its attributes |
| Data is produced | On demand, only when something asks | Every 15 minutes, for everyone |
| Configuration | Parameters per call, no restart | `chart_export` block in `configuration.yaml`, restart needed |
| Works with | Anything that can call an action and use the response | Anything that can read a list from a sensor attribute |

### Why the action is the better way

Home Assistant keeps entity attributes in its state machine, and every state change is passed on to connected dashboards and listeners. A full list of price intervals in an attribute is rewritten on every refresh, even when nobody looks at it. The action returns the same data only when a card, script or automation asks for it, and you can shape the result per call (days, resolution, filters, field names, currency).

Most third-party projects were built around attributes, because that is what price integrations like Nord Pool offered for years. They only need to read a sensor, so that is what they support. This integration offers the sensor for exactly that reason, so you can use these projects today.

:::info Help move things forward
If you use a card or integration that can only read attributes, consider asking its author to support calling an action as a data source. Actions like `tibber_prices.get_chartdata` return the data in the shape the project asks for, so a single option on their side is enough to avoid keeping a long list in an attribute.
:::

## Using the Sensor Attributes

The sensor is disabled by default.

1. Go to **Settings → Devices & Services → Tibber Prices → your home** and show disabled entities.
2. Enable **Chart Data Export** (`chart_data_export`, entity ID `sensor.<home_name>_chart_data_export`).
3. In the third-party project, select this sensor as the price source.

The sensor works without configuration. It exposes these attributes:

| Attribute | Content |
|---|---|
| `timestamp` | When the data was last refreshed |
| `currency` | Currency code of your home (for example `EUR`) |
| `data` | List of price intervals, each with `start_time` and `price_per_kwh` |

By default it contains today and tomorrow (or yesterday and today while tomorrow's prices are not published yet), in quarter-hourly resolution and in the **base currency** per kWh (for example EUR/kWh).

### Adapting the Format

Projects differ in the attribute and field names they expect. You can rename them in `configuration.yaml` (restart required). The same parameters exist for the [`get_chartdata` action](chart-actions.md):

```yaml
tibber_prices:
    chart_export:
        data_key: prices          # name of the attribute holding the list
        start_time_field: start   # name of the start time in each entry
        price_field: price        # name of the price in each entry
        subunit_currency: false   # false = EUR/kWh, true = ct/kWh
        resolution: interval      # interval (15 min) or hourly
```

The configuration applies to all homes. If a project cannot be adapted by names alone, a [template sensor](https://www.home-assistant.io/integrations/template/) that calls `tibber_prices.get_chartdata` and reshapes the response works as well.

## Known Projects

The table lists projects whose documented data format matches what the sensor provides. Third-party projects change over time, so check their README for current options.

| Project | What it does | How to connect |
|---|---|---|
| [ApexCharts Card](https://github.com/RomRider/apexcharts-card) | Flexible chart card (HACS) | Easiest with the built-in [YAML generator](chart-examples.md). To build your own series from the sensor, use `data_generator` and map `entity.attributes.data` to `[timestamp, price]` pairs. |
| [tibber-graph](https://github.com/stefanes/tibber-graph) | Renders price graphs as camera images, for example for e-ink or wall displays | Use the sensor as price source (`price_entity_id` in `create_graph` or `set_data_source`). It reads `data` with `start_time` and `price_per_kwh` and the optional `currency`, which match the defaults. |
| [Energy Flow & Price Card](https://github.com/dennisbest85/energy-flow-price-card) | Live energy flow plus price chart | Set `price_entity` to the sensor. It looks for a list attribute such as `data` with `start_time` and `price_per_kwh`, in EUR/kWh. Leave `price_use_tibber_service` off, that option is for the official Tibber integration. |

:::note
We list these projects based on their documentation and have not tested every combination. If a project does not show data, check **Developer Tools → States** for the attribute names of the sensor and compare them with the project's documentation.
:::

Use another project that works well? Share it in the [community examples](community-examples.md).
