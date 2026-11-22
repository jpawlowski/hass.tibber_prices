"""
Dashboard cards shipped with the integration.

The JavaScript lives in `cards/` next to this file and is served by Home Assistant itself, then
loaded into every frontend: users get the cards with the integration (updates included), with
no separate repository and no dashboard resource to add. The cards are ES modules that import each
other by relative path, and they are cached for long. So the version is part of the directory's
URL, not a query on the entry file: a query would not reach the modules it imports, and after an
update the browser would mix new modules with old ones from its cache. The integration version
changes the URL on every release, the newest modification time of the files on every edit during
development.

Home Assistant compresses none of this, but aiohttp's file response sends `<module>.js.gz`
instead of the module when it exists and the browser accepts gzip (with `Content-Encoding` and
`Vary`, the type still that of the module). The release zip carries such a copy of every module
(`scripts/release/build-asset`), the repository doesn't: during development the modules go out as
they are, so an edit is never hidden behind a stale copy. A copy that no longer matches its module
(a manual install copied over a store install, a module patched by hand) is deleted on start, else
aiohttp would keep sending the old code under the new URL. Bundling or minifying the cards was
weighed against that (#271) and left out: gzip alone takes them from about 700 KB to 200 KB, the
rest would cost a build tool from npm in the release and source maps for reading a user's error.

A page that stays open keeps the modules it loaded, also after an update moved them to a new URL.
The websocket command `tibber_prices/frontend` names the URL they are served under now; the cards
ask for it whenever their connection comes back and offer a reload when it isn't theirs
(`cards/reload.js`).
"""

from __future__ import annotations

import gzip
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import probatio as vol

from custom_components.tibber_prices.const import DOMAIN
from homeassistant.components import websocket_api
from homeassistant.components.frontend import add_extra_js_url

# Public import path, as HA core integrations use it; the http package re-exports it without __all__
from homeassistant.components.http import StaticPathConfig  # pyright: ignore[reportPrivateImportUsage]
from homeassistant.core import callback
from homeassistant.loader import async_get_loaded_integration
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

URL_BASE = f"/{DOMAIN}_frontend"
CARDS_DIR = Path(__file__).parent / "cards"
CARDS_FILE = "tibber-prices-cards.js"

# The URL the cards are served under since this start (without the trailing slash)
CARDS_URL: HassKey[str] = HassKey(f"{DOMAIN}_cards_url")


def _newest_modification(directory: Path) -> int:
    """Return the newest modification time of the modules in the directory, in whole seconds."""
    return max(int(module.stat().st_mtime) for module in directory.glob("*.js"))


def _drop_stale_copies(directory: Path) -> None:
    """Delete gzip copies whose module is gone or differs, so aiohttp never sends outdated code."""
    for copy in directory.glob("*.js.gz"):
        module = copy.with_suffix("")
        try:
            if module.is_file() and gzip.decompress(copy.read_bytes()) == module.read_bytes():
                continue
        except OSError, EOFError, gzip.BadGzipFile:
            pass  # unreadable or broken: as stale as an outdated one
        try:
            copy.unlink()
        except OSError as err:
            _LOGGER.warning("Could not delete the outdated card copy %s: %s", copy, err)
        else:
            _LOGGER.debug("Deleted the outdated card copy %s", copy.name)


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Serve the card modules and load the entry into the frontend (once per Home Assistant start)."""
    version = async_get_loaded_integration(hass, DOMAIN).version
    await hass.async_add_executor_job(_drop_stale_copies, CARDS_DIR)
    modified = await hass.async_add_executor_job(_newest_modification, CARDS_DIR)
    url = f"{URL_BASE}/{version}-{modified}"
    await hass.http.async_register_static_paths([StaticPathConfig(url, str(CARDS_DIR), cache_headers=True)])
    add_extra_js_url(hass, f"{url}/{CARDS_FILE}")
    hass.data[CARDS_URL] = url
    websocket_api.async_register_command(hass, websocket_cards_url)


@callback
@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/frontend"})
def websocket_cards_url(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Name the URL the cards are served under now, so an open page can tell its own are outdated."""
    connection.send_result(msg["id"], {"url": hass.data[CARDS_URL]})
