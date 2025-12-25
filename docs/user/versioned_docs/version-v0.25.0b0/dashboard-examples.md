# Dashboard Examples

Beautiful dashboard layouts using Tibber Prices sensors.

> **Entity ID tip:** `<home_name>` is a placeholder for your Tibber home display name in Home Assistant. Entity IDs are derived from the displayed name (localized), so the exact slug may differ. Example suffixes below use the English display names (en.json) as a baseline. You can find the real ID in **Settings → Devices & Services → Entities** (or **Developer Tools → States**).

## Basic Price Display Card

Simple card showing current price with dynamic color:

```yaml
type: entities
title: Current Electricity Price
entities:
  - entity: sensor.<home_name>_current_electricity_price
    name: Current Price
    icon: mdi:flash
  - entity: sensor.<home_name>_current_price_rating
    name: Price Rating
  - entity: sensor.<home_name>_next_electricity_price
    name: Next Price
```

## Period Status Cards

Show when best/peak price periods are active:

```yaml
type: horizontal-stack
cards:
  - type: entity
    entity: binary_sensor.<home_name>_best_price_period
    name: Best Price Active
    icon: mdi:currency-eur-off
  - type: entity
    entity: binary_sensor.<home_name>_peak_price_period
    name: Peak Price Active
    icon: mdi:alert
```

## Custom Button Card Examples

### Price Level Card

```yaml
type: custom:button-card
entity: sensor.<home_name>_current_price_level
name: Price Level
show_state: true
styles:
  card:
    - background: |
        [[[
          if (entity.state === 'LOWEST') return 'linear-gradient(135deg, #00ffa3 0%, #00d4ff 100%)';
          if (entity.state === 'LOW') return 'linear-gradient(135deg, #4dddff 0%, #00ffa3 100%)';
          if (entity.state === 'NORMAL') return 'linear-gradient(135deg, #ffd700 0%, #ffb800 100%)';
          if (entity.state === 'HIGH') return 'linear-gradient(135deg, #ff8c00 0%, #ff6b00 100%)';
          if (entity.state === 'HIGHEST') return 'linear-gradient(135deg, #ff4500 0%, #dc143c 100%)';
          return 'var(--card-background-color)';
        ]]]
```

## Lovelace Layouts

### Compact Mobile View

Optimized for mobile devices:

```yaml
type: vertical-stack
cards:
  - type: custom:mini-graph-card
    entities:
      - entity: sensor.<home_name>_current_electricity_price
    name: Today's Prices
    hours_to_show: 24
    points_per_hour: 4

  - type: glance
    entities:
      - entity: sensor.<home_name>_best_price_start
        name: Best Period Starts
      - entity: binary_sensor.<home_name>_best_price_period
        name: Active Now
```

### Desktop Dashboard

Full-width layout for desktop:

```yaml
type: grid
columns: 3
square: false
cards:
  - type: custom:apexcharts-card
    # See chart-examples.md for ApexCharts config

  - type: vertical-stack
    cards:
      - type: entities
        title: Current Status
        entities:
          - sensor.<home_name>_current_electricity_price
          - sensor.<home_name>_current_price_rating

  - type: vertical-stack
    cards:
      - type: entities
        title: Statistics
        entities:
          - sensor.<home_name>_price_today
          - sensor.<home_name>_today_s_lowest_price
          - sensor.<home_name>_today_s_highest_price
```

## Icon Color Integration

Using the `icon_color` attribute for dynamic colors:

```yaml
type: custom:mushroom-chips-card
chips:
  - type: entity
    entity: sensor.<home_name>_current_electricity_price
    icon_color: "{{ state_attr('sensor.<home_name>_current_electricity_price', 'icon_color') }}"

  - type: entity
    entity: binary_sensor.<home_name>_best_price_period
    icon_color: green

  - type: entity
    entity: binary_sensor.<home_name>_peak_price_period
    icon_color: red
```

See [Icon Colors](icon-colors.md) for detailed color mapping.

## Picture Elements Dashboard

Advanced interactive dashboard:

```yaml
type: picture-elements
image: /local/electricity_dashboard_bg.png
elements:
  - type: state-label
    entity: sensor.<home_name>_current_electricity_price
    style:
      top: 20%
      left: 50%
      font-size: 32px
      font-weight: bold

  - type: state-badge
    entity: binary_sensor.<home_name>_best_price_period
    style:
      top: 40%
      left: 30%

  # Add more elements...
```

## Auto-Entities Dynamic Lists

Automatically list all price sensors:

```yaml
type: custom:auto-entities
card:
  type: entities
  title: All Price Sensors
filter:
  include:
    - entity_id: "sensor.<home_name>_*_price"
  exclude:
    - state: unavailable
sort:
  method: state
  numeric: true
```

---

💡 **Related:**
- [Chart Examples](chart-examples.md) - ApexCharts configurations
- [Dynamic Icons](dynamic-icons.md) - Icon behavior
- [Icon Colors](icon-colors.md) - Color attributes
