# Installation

## HACS Installation (Recommended)

[HACS](https://hacs.xyz/) (Home Assistant Community Store) is the easiest way to install and keep the integration up to date.

### Prerequisites

- Home Assistant 2025.10.0 or newer
- [HACS](https://hacs.xyz/docs/use/) installed and configured
- A [Tibber API token](https://developer.tibber.com/settings/access-token)

### Steps

1. Open HACS in your Home Assistant sidebar
2. Go to **Integrations**
3. Click the **⋮** menu (top right) → **Custom repositories**
4. Add the repository URL:
   ```
   https://github.com/jpawlowski/hass.tibber_prices
   ```
   Category: **Integration**
5. Click **Add**
6. Find **Tibber Price Information & Ratings** in the integration list
7. Click **Download**
8. **Restart Home Assistant**
9. Continue with [Configuration](configuration.md)

### Updating

HACS will show a notification when updates are available:

1. Open HACS → **Integrations**
2. Find **Tibber Price Information & Ratings**
3. Click **Update**
4. **Restart Home Assistant**

## Manual Installation

If you prefer not to use HACS:

1. Download the [latest release](https://github.com/jpawlowski/hass.tibber_prices/releases/latest) from GitHub
2. Extract the `custom_components/tibber_prices/` folder
3. Copy it to your Home Assistant `config/custom_components/` directory:
   ```
   config/
   └── custom_components/
       └── tibber_prices/
           ├── __init__.py
           ├── manifest.json
           ├── sensor/
           ├── binary_sensor/
           └── ...
   ```
4. **Restart Home Assistant**
5. Continue with [Configuration](configuration.md)

## After Installation

Once installed and restarted, add the integration:

1. Go to **Settings → Devices & Services**
2. Click **+ Add Integration**
3. Search for **Tibber Price Information & Ratings**
4. Enter your [Tibber API token](https://developer.tibber.com/settings/access-token)
5. Select your Tibber home
6. The integration will start fetching price data

See the [Configuration Guide](configuration.md) for detailed setup options.
