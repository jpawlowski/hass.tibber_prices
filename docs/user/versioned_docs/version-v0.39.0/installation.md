# Installation

## Marketplace Installation (Recommended)

Install the integration from the Marketplace, built into Home Assistant from 2026.11. On older versions, use [HACS](https://hacs.xyz/), which shares its catalog. When you upgrade to 2026.11, your HACS install carries over on its own.

:::caution Not affiliated with Home Assistant
The Marketplace warns you that the Home Assistant project doesn't make or support community-made integrations. That applies here too: report problems in [our issue tracker](https://github.com/jpawlowski/hass.tibber_prices/issues), not to Home Assistant.
:::

### Prerequisites

- Home Assistant 2026.4.4 or newer
- A [Tibber API token](https://developer.tibber.com/settings/access-token)

### Steps (Home Assistant 2026.11 or newer)

[![Open your Home Assistant instance and open a repository inside the Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=jpawlowski&repository=hass.tibber_prices&category=integration)

1. Go to **Settings → Marketplace**
2. Search for **Tibber Prices & Planning**
3. Click **Download**
4. Continue with [Configuration](configuration.md): a first install loads right away, no restart needed

### Steps (HACS, Home Assistant before 2026.11)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jpawlowski&repository=hass.tibber_prices&category=integration)

1. Open HACS in your Home Assistant sidebar
2. Search for **Tibber Prices & Planning**
3. Click **Download**
4. **Restart Home Assistant**
5. Continue with [Configuration](configuration.md)

### Updating

New versions appear as an update under **Settings → Updates**, with their release notes. Read them first.

1. Open the update for **Tibber Prices & Planning**
2. Click **Install**
3. **Restart Home Assistant** (the Marketplace shows a repair with a restart button)

A new release can take a few hours to appear. Want to try a pre-release? Turn on the pre-release switch for the integration in the Marketplace.

## Manual Installation

If you prefer not to use the Marketplace or HACS:

1. Download the [latest release](https://github.com/jpawlowski/hass.tibber_prices/releases/latest) from GitHub
2. Extract the `custom_components/tibber_prices/` folder
3. Copy it to your Home Assistant `config/custom_components/` directory:
<details>
<summary>Show example: Folder Structure</summary>

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

</details>
4. **Restart Home Assistant**
5. Continue with [Configuration](configuration.md)

## After Installation

Once installed and restarted, add the integration:

1. Go to **Settings → Devices & Services**
2. Click **+ Add Integration**
3. Search for **Tibber Prices & Planning**
4. Enter your [Tibber API token](https://developer.tibber.com/settings/access-token)
5. Select your Tibber home
6. The integration will start fetching price data

See the [Configuration Guide](configuration.md) for detailed setup options.
