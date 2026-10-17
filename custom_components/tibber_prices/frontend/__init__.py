"""
Dashboard cards shipped with the integration.

The JavaScript lives next to this file and is served by Home Assistant itself, then loaded
into every frontend: users get the cards with the integration (HACS update included), with
no separate repository and no dashboard resource to add. The file is cached for long, so its
URL carries the integration version and the file's modification time: browsers fetch the new
file after an update, and after an edit during development.
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
CARDS_FILE = "tibber-prices-cards.js"


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Serve the card file and load it into the frontend (once per Home Assistant start)."""
    path = Path(__file__).parent / CARDS_FILE
    version = async_get_loaded_integration(hass, DOMAIN).version
    modified = int((await hass.async_add_executor_job(path.stat)).st_mtime)
    await hass.http.async_register_static_paths(
        [StaticPathConfig(f"{URL_BASE}/{CARDS_FILE}", str(path), cache_headers=True)]
    )
    add_extra_js_url(hass, f"{URL_BASE}/{CARDS_FILE}?v={version}-{modified}")
