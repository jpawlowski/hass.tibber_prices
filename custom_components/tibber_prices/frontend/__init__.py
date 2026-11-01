"""
Dashboard cards shipped with the integration.

The JavaScript lives in `cards/` next to this file and is served by Home Assistant itself, then
loaded into every frontend: users get the cards with the integration (HACS update included), with
no separate repository and no dashboard resource to add. The cards are ES modules that import each
other by relative path, and they are cached for long. So the version is part of the directory's
URL, not a query on the entry file: a query would not reach the modules it imports, and after an
update the browser would mix new modules with old ones from its cache. The integration version
changes the URL on every release, the newest modification time of the files on every edit during
development.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from custom_components.tibber_prices.const import DOMAIN
from homeassistant.components.frontend import add_extra_js_url

# Public import path, as HA core integrations use it; the http package re-exports it without __all__
from homeassistant.components.http import StaticPathConfig  # pyright: ignore[reportPrivateImportUsage]
from homeassistant.loader import async_get_loaded_integration

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

URL_BASE = f"/{DOMAIN}_frontend"
CARDS_DIR = Path(__file__).parent / "cards"
CARDS_FILE = "tibber-prices-cards.js"


def _newest_modification(directory: Path) -> int:
    """Return the newest modification time of the modules in the directory, in whole seconds."""
    return max(int(module.stat().st_mtime) for module in directory.glob("*.js"))


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Serve the card modules and load the entry into the frontend (once per Home Assistant start)."""
    version = async_get_loaded_integration(hass, DOMAIN).version
    modified = await hass.async_add_executor_job(_newest_modification, CARDS_DIR)
    url = f"{URL_BASE}/{version}-{modified}"
    await hass.http.async_register_static_paths([StaticPathConfig(url, str(CARDS_DIR), cache_headers=True)])
    add_extra_js_url(hass, f"{url}/{CARDS_FILE}")
