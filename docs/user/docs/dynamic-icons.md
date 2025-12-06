# Dynamic Icons

Many sensors in the Tibber Prices integration automatically change their icon based on their current state. This provides instant visual feedback about price levels, trends, and periods without needing to read the actual values.

## What are Dynamic Icons?

Instead of having a fixed icon, some sensors update their icon to reflect their current state:

-   **Price level sensors** show different cash/money icons depending on whether prices are cheap or expensive
-   **Price rating sensors** show thumbs up/down based on how the current price compares to average
-   **Volatility sensors** show different chart types based on price stability
-   **Binary sensors** show different icons when ON vs OFF (e.g., piggy bank when in best price period)

The icons change automatically - no configuration needed!

## How to Check if a Sensor Has Dynamic Icons

To see which icon a sensor currently uses:

1. Go to **Developer Tools** → **States** in Home Assistant
2. Search for your sensor (e.g., `sensor.tibber_home_current_interval_price_level`)
3. Look at the icon displayed in the entity row
4. Change conditions (wait for price changes) and check if the icon updates

**Common sensor types with dynamic icons:**

-   Price level sensors (e.g., `current_interval_price_level`)
-   Price rating sensors (e.g., `current_interval_price_rating`)
-   Volatility sensors (e.g., `volatility_today`)
-   Binary sensors (e.g., `best_price_period`, `peak_price_period`)

## Using Dynamic Icons in Your Dashboard

### Standard Entity Cards

Dynamic icons work automatically in standard Home Assistant cards:

```yaml
type: entities
entities:
    - entity: sensor.tibber_home_current_interval_price_level
    - entity: sensor.tibber_home_current_interval_price_rating
    - entity: sensor.tibber_home_volatility_today
    - entity: binary_sensor.tibber_home_best_price_period
```

The icons will update automatically as the sensor states change.

### Glance Card

```yaml
type: glance
entities:
    - entity: sensor.tibber_home_current_interval_price_level
      name: Price Level
    - entity: sensor.tibber_home_current_interval_price_rating
      name: Rating
    - entity: binary_sensor.tibber_home_best_price_period
      name: Best Price
```

### Custom Button Card

```yaml
type: custom:button-card
entity: sensor.tibber_home_current_interval_price_level
name: Current Price Level
show_state: true
# Icon updates automatically - no need to specify it!
```

### Mushroom Entity Card

```yaml
type: custom:mushroom-entity-card
entity: sensor.tibber_home_volatility_today
name: Price Volatility
# Icon changes automatically based on volatility level
```

## Overriding Dynamic Icons

If you want to use a fixed icon instead of the dynamic one:

### In Entity Cards

```yaml
type: entities
entities:
    - entity: sensor.tibber_home_current_interval_price_level
      icon: mdi:lightning-bolt # Fixed icon, won't change
```

### In Custom Button Card

```yaml
type: custom:button-card
entity: sensor.tibber_home_current_interval_price_rating
name: Price Rating
icon: mdi:chart-line # Fixed icon overrides dynamic behavior
show_state: true
```

## Combining with Dynamic Colors

Dynamic icons work great together with dynamic colors! See the **[Dynamic Icon Colors Guide](icon-colors.md)** for examples.

**Example: Dynamic icon AND color**

```yaml
type: custom:button-card
entity: sensor.tibber_home_current_interval_price_level
name: Current Price
show_state: true
# Icon changes automatically (cheap/expensive cash icons)
styles:
    icon:
        - color: |
              [[[
                return entity.attributes.icon_color || 'var(--state-icon-color)';
              ]]]
```

This gives you both:

-   ✅ Different icon based on state (e.g., cash-plus when cheap, cash-remove when expensive)
-   ✅ Different color based on state (e.g., green when cheap, red when expensive)

## Icon Behavior Details

### Binary Sensors

Binary sensors may have different icons for different states:

-   **ON state**: Typically shows an active/alert icon
-   **OFF state**: May show different icons depending on whether future periods exist
    -   Has upcoming periods: Timer/waiting icon
    -   No upcoming periods: Sleep/inactive icon

**Example:** `binary_sensor.tibber_home_best_price_period`

-   When ON: Shows a piggy bank (good time to save money)
-   When OFF with future periods: Shows a timer (waiting for next period)
-   When OFF without future periods: Shows a sleep icon (no periods expected soon)

### State-Based Icons

Sensors with text states (like `cheap`, `normal`, `expensive`) typically show icons that match the meaning:

-   Lower/better values → More positive icons
-   Higher/worse values → More cautionary icons
-   Normal/average values → Neutral icons

The exact icons are chosen to be intuitive and meaningful in the Home Assistant ecosystem.

## Troubleshooting

**Icon not changing:**

-   Wait for the sensor state to actually change (prices update every 15 minutes)
-   Check in Developer Tools → States that the sensor state is changing
-   If you've set a custom icon in your card, it will override the dynamic icon

**Want to see the icon code:**

-   Look at the entity in Developer Tools → States
-   The `icon` attribute shows the current Material Design icon code (e.g., `mdi:cash-plus`)

**Want different icons:**

-   You can override icons in your card configuration (see examples above)
-   Or create a template sensor with your own icon logic

## See Also

-   [Dynamic Icon Colors](icon-colors.md) - Color your icons based on state
-   [Sensors Reference](sensors.md) - Complete list of available sensors
-   [Automation Examples](automation-examples.md) - Use dynamic icons in automations
