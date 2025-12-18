---
comments: false
---

# Dynamic Icon Colors

Many sensors in the Tibber Prices integration provide an `icon_color` attribute that allows you to dynamically color elements in your dashboard based on the sensor's state. This is particularly useful for visual dashboards where you want instant recognition of price levels or states.

**What makes icon_color special:** Instead of writing complex if/else logic to interpret the sensor state, you can simply use the `icon_color` value directly - it already contains the appropriate CSS color variable for the current state.

> **Related:** Many sensors also automatically change their **icon** based on state. See the **[Dynamic Icons Guide](dynamic-icons.md)** for details.

## What is icon_color?

The `icon_color` attribute contains a **CSS variable name** (not a direct color value) that changes based on the sensor's state. For example:

-   **Price level sensors**: `var(--success-color)` for cheap, `var(--error-color)` for expensive
-   **Binary sensors**: `var(--success-color)` when in best price period, `var(--error-color)` during peak price
-   **Volatility**: `var(--success-color)` for low volatility, `var(--error-color)` for very high

### Why CSS Variables?

Using CSS variables like `var(--success-color)` instead of hardcoded colors (like `#00ff00`) has important advantages:

-   ✅ **Automatic theme adaptation** - Colors change with light/dark mode
-   ✅ **Consistent with your theme** - Uses your theme's color scheme
-   ✅ **Future-proof** - Works with custom themes and future HA updates

You can use the `icon_color` attribute directly in your card templates, or interpret the sensor state yourself if you prefer custom colors (see examples below).

## Which Sensors Support icon_color?

Many sensors provide the `icon_color` attribute for dynamic styling. To see if a sensor has this attribute:

1. Go to **Developer Tools** → **States** in Home Assistant
2. Search for your sensor (e.g., `sensor.tibber_home_current_interval_price_level`)
3. Look for `icon_color` in the attributes section

**Common sensor types with icon_color:**

-   Price level sensors (e.g., `current_interval_price_level`)
-   Price rating sensors (e.g., `current_interval_price_rating`)
-   Volatility sensors (e.g., `volatility_today`)
-   Price trend sensors (e.g., `price_trend_next_3h`)
-   Binary sensors (e.g., `best_price_period`, `peak_price_period`)
-   Timing sensors (e.g., `best_price_time_until_start`, `best_price_progress`)

The colors adapt to the sensor's state - cheaper prices typically show green, expensive prices red, and neutral states gray.

## When to Use icon_color vs. State Value

**Use `icon_color` when:**

-   ✅ You can apply the CSS variable directly (icons, text colors, borders)
-   ✅ Your card supports CSS variable substitution
-   ✅ You want simple, clean code without if/else logic

**Use the state value directly when:**

-   ⚠️ You need to convert the color (e.g., CSS variable → RGBA with transparency)
-   ⚠️ You need different colors than what `icon_color` provides
-   ⚠️ You're building complex conditional logic anyway

**Example of when NOT to use icon_color:**

```yaml
# ❌ DON'T: Converting icon_color requires if/else anyway
card:
  - background: |
      [[[
        const color = entity.attributes.icon_color;
        if (color === 'var(--success-color)') return 'rgba(76, 175, 80, 0.1)';
        if (color === 'var(--error-color)') return 'rgba(244, 67, 54, 0.1)';
        // ... more if statements
      ]]]

# ✅ DO: Interpret state directly if you need custom logic
card:
  - background: |
      [[[
        const level = entity.state;
        if (level === 'very_cheap' || level === 'cheap') return 'rgba(76, 175, 80, 0.1)';
        if (level === 'very_expensive' || level === 'expensive') return 'rgba(244, 67, 54, 0.1)';
        return 'transparent';
      ]]]
```

The advantage of `icon_color` is simplicity - if you need complex logic, you lose that advantage.

## How to Use icon_color in Your Dashboard

### Method 1: Custom Button Card (Recommended)

The [custom:button-card](https://github.com/custom-cards/button-card) from HACS supports dynamic icon colors.

**Example: Icon color only**

```yaml
type: custom:button-card
entity: sensor.tibber_home_current_interval_price_level
name: Current Price Level
show_state: true
icon: mdi:cash
styles:
    icon:
        - color: |
              [[[
                return entity.attributes.icon_color || 'var(--state-icon-color)';
              ]]]
```

**Example: Icon AND state value with same color**

```yaml
type: custom:button-card
entity: sensor.tibber_home_current_interval_price_level
name: Current Price Level
show_state: true
icon: mdi:cash
styles:
    icon:
        - color: |
              [[[
                return entity.attributes.icon_color || 'var(--state-icon-color)';
              ]]]
    state:
        - color: |
              [[[
                return entity.attributes.icon_color || 'var(--primary-text-color)';
              ]]]
        - font-weight: bold
```

### Method 2: Entities Card with card_mod

Use Home Assistant's built-in entities card with card_mod for icon and state colors:

```yaml
type: entities
entities:
    - entity: sensor.tibber_home_current_interval_price_level
card_mod:
    style:
        hui-generic-entity-row:
            $: |
                state-badge {
                  color: {{ state_attr('sensor.tibber_home_current_interval_price_level', 'icon_color') }} !important;
                }
                .info {
                  color: {{ state_attr('sensor.tibber_home_current_interval_price_level', 'icon_color') }} !important;
                }
```

### Method 3: Mushroom Cards

The [Mushroom cards](https://github.com/piitaya/lovelace-mushroom) support card_mod for icon and text colors:

**Icon color only:**

```yaml
type: custom:mushroom-entity-card
entity: binary_sensor.tibber_home_best_price_period
name: Best Price Period
icon: mdi:piggy-bank
card_mod:
    style: |
        ha-card {
          --card-mod-icon-color: {{ state_attr('binary_sensor.tibber_home_best_price_period', 'icon_color') }};
        }
```

**Icon and state value:**

```yaml
type: custom:mushroom-entity-card
entity: sensor.tibber_home_current_interval_price_level
name: Price Level
card_mod:
    style: |
        ha-card {
          --card-mod-icon-color: {{ state_attr('sensor.tibber_home_current_interval_price_level', 'icon_color') }};
          --primary-text-color: {{ state_attr('sensor.tibber_home_current_interval_price_level', 'icon_color') }};
        }
```

### Method 4: Glance Card with card_mod

Combine multiple sensors with dynamic colors:

```yaml
type: glance
entities:
    - entity: sensor.tibber_home_current_interval_price_level
    - entity: sensor.tibber_home_volatility_today
    - entity: binary_sensor.tibber_home_best_price_period
card_mod:
    style: |
        ha-card div.entity:nth-child(1) state-badge {
          color: {{ state_attr('sensor.tibber_home_current_interval_price_level', 'icon_color') }} !important;
        }
        ha-card div.entity:nth-child(2) state-badge {
          color: {{ state_attr('sensor.tibber_home_volatility_today', 'icon_color') }} !important;
        }
        ha-card div.entity:nth-child(3) state-badge {
          color: {{ state_attr('binary_sensor.tibber_home_best_price_period', 'icon_color') }} !important;
        }
```

## Complete Dashboard Example

Here's a complete example combining multiple sensors with dynamic colors:

```yaml
type: vertical-stack
cards:
    # Current price status
    - type: horizontal-stack
      cards:
          - type: custom:button-card
            entity: sensor.tibber_home_current_interval_price_level
            name: Price Level
            show_state: true
            styles:
                icon:
                    - color: |
                          [[[
                            return entity.attributes.icon_color || 'var(--state-icon-color)';
                          ]]]

          - type: custom:button-card
            entity: sensor.tibber_home_current_interval_price_rating
            name: Price Rating
            show_state: true
            styles:
                icon:
                    - color: |
                          [[[
                            return entity.attributes.icon_color || 'var(--state-icon-color)';
                          ]]]

    # Binary sensors for periods
    - type: horizontal-stack
      cards:
          - type: custom:button-card
            entity: binary_sensor.tibber_home_best_price_period
            name: Best Price Period
            show_state: true
            icon: mdi:piggy-bank
            styles:
                icon:
                    - color: |
                          [[[
                            return entity.attributes.icon_color || 'var(--state-icon-color)';
                          ]]]

          - type: custom:button-card
            entity: binary_sensor.tibber_home_peak_price_period
            name: Peak Price Period
            show_state: true
            icon: mdi:alert-circle
            styles:
                icon:
                    - color: |
                          [[[
                            return entity.attributes.icon_color || 'var(--state-icon-color)';
                          ]]]

    # Volatility and trends
    - type: horizontal-stack
      cards:
          - type: custom:button-card
            entity: sensor.tibber_home_volatility_today
            name: Volatility
            show_state: true
            styles:
                icon:
                    - color: |
                          [[[
                            return entity.attributes.icon_color || 'var(--state-icon-color)';
                          ]]]

          - type: custom:button-card
            entity: sensor.tibber_home_price_trend_next_3h
            name: Next 3h Trend
            show_state: true
            styles:
                icon:
                    - color: |
                          [[[
                            return entity.attributes.icon_color || 'var(--state-icon-color)';
                          ]]]
```

## CSS Color Variables

The integration uses Home Assistant's standard CSS variables for theme compatibility:

-   `var(--success-color)` - Green (good/cheap/low)
-   `var(--info-color)` - Blue (informational)
-   `var(--warning-color)` - Orange (caution/expensive)
-   `var(--error-color)` - Red (alert/very expensive/high)
-   `var(--state-icon-color)` - Gray (neutral/normal)
-   `var(--disabled-color)` - Light gray (no data/inactive)

These automatically adapt to your theme's light/dark mode and custom color schemes.

### Using Custom Colors

If you want to override the theme colors with your own, you have two options:

#### Option 1: Use icon_color but Override in Your Theme

Define custom colors in your theme configuration (`themes.yaml`):

```yaml
my_custom_theme:
    # Override standard variables
    success-color: "#00C853" # Custom green
    error-color: "#D32F2F" # Custom red
    warning-color: "#F57C00" # Custom orange
    info-color: "#0288D1" # Custom blue
```

The `icon_color` attribute will automatically use your custom theme colors.

#### Option 2: Interpret State Value Directly

Instead of using `icon_color`, read the sensor state and apply your own colors:

**Example: Custom colors for price level**

```yaml
type: custom:button-card
entity: sensor.tibber_home_current_interval_price_level
name: Current Price Level
show_state: true
icon: mdi:cash
styles:
    icon:
        - color: |
              [[[
                const level = entity.state;
                if (level === 'very_cheap') return '#00E676';    // Bright green
                if (level === 'cheap') return '#66BB6A';         // Light green
                if (level === 'normal') return '#9E9E9E';        // Gray
                if (level === 'expensive') return '#FF9800';     // Orange
                if (level === 'very_expensive') return '#F44336'; // Red
                return 'var(--state-icon-color)';  // Fallback
              ]]]
```

**Example: Custom colors for binary sensor**

```yaml
type: custom:button-card
entity: binary_sensor.tibber_home_best_price_period
name: Best Price Period
show_state: true
icon: mdi:piggy-bank
styles:
    icon:
        - color: |
              [[[
                // Use state directly, not icon_color
                return entity.state === 'on' ? '#4CAF50' : '#9E9E9E';
              ]]]
    card:
        - background: |
              [[[
                return entity.state === 'on' ? 'rgba(76, 175, 80, 0.1)' : 'transparent';
              ]]]
```

**Example: Custom colors for volatility**

```yaml
type: custom:button-card
entity: sensor.tibber_home_volatility_today
name: Volatility Today
show_state: true
styles:
    icon:
        - color: |
              [[[
                const volatility = entity.state;
                if (volatility === 'low') return '#4CAF50';       // Green
                if (volatility === 'moderate') return '#2196F3';  // Blue
                if (volatility === 'high') return '#FF9800';      // Orange
                if (volatility === 'very_high') return '#F44336'; // Red
                return 'var(--state-icon-color)';
              ]]]
```

**Example: Custom colors for price rating**

```yaml
type: custom:button-card
entity: sensor.tibber_home_current_interval_price_rating
name: Price Rating
show_state: true
styles:
    icon:
        - color: |
              [[[
                const rating = entity.state;
                if (rating === 'low') return '#00C853';      // Dark green
                if (rating === 'normal') return '#78909C';   // Blue-gray
                if (rating === 'high') return '#D32F2F';     // Dark red
                return 'var(--state-icon-color)';
              ]]]
```

### Which Approach Should You Use?

| Use Case                              | Recommended Approach               |
| ------------------------------------- | ---------------------------------- |
| Want theme-consistent colors          | ✅ Use `icon_color` directly       |
| Want light/dark mode support          | ✅ Use `icon_color` directly       |
| Want custom theme colors              | ✅ Override CSS variables in theme |
| Want specific hardcoded colors        | ⚠️ Interpret state value directly  |
| Multiple themes with different colors | ✅ Use `icon_color` directly       |

**Recommendation:** Use `icon_color` whenever possible for better theme integration. Only interpret the state directly if you need very specific color values that shouldn't change with themes.

## Troubleshooting

**Icons not changing color:**

-   Make sure you're using a card that supports custom styling (like custom:button-card or card_mod)
-   Check that the entity actually has the `icon_color` attribute (inspect in Developer Tools → States)
-   Verify your Home Assistant theme supports the CSS variables

**Colors look wrong:**

-   The colors are theme-dependent. Try switching themes to see if they appear correctly
-   Some custom themes may override the standard CSS variables with unexpected colors

**Want different colors?**

-   You can override the colors in your theme configuration
-   Or use conditional logic in your card templates based on the state value instead of `icon_color`

## See Also

-   [Sensors Reference](sensors.md) - Complete list of available sensors
-   [Automation Examples](automation-examples.md) - Use color-coded sensors in automations
-   [Configuration Guide](configuration.md) - Adjust thresholds for price levels and ratings
