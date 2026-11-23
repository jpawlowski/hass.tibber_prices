"""The integration serves its dashboard cards itself and loads them into the frontend."""

import gzip
import os
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import web
import pytest

from custom_components.tibber_prices import frontend
from homeassistant.components.http.static import CachingStaticResource

if TYPE_CHECKING:
    from pytest_homeassistant.typing import ClientSessionGenerator


@pytest.fixture
async def registered() -> tuple[MagicMock, MagicMock, MagicMock]:
    """Run the registration for version 1.2.3 with modules last changed at 1700000000.

    Returns the hass mock, the add_extra_js_url mock and the websocket registration mock.
    """
    hass = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))
    with (
        patch.object(frontend, "async_get_loaded_integration", return_value=MagicMock(version="1.2.3")),
        patch.object(frontend, "_newest_modification", return_value=1700000000),
        patch.object(frontend, "add_extra_js_url") as add_js,
        patch.object(frontend.websocket_api, "async_register_command") as register,
    ):
        await frontend.async_register_frontend(hass)
    return hass, add_js, register


URL = "/tibber_prices_frontend/1.2.3-1700000000"


@pytest.mark.unit
def test_cards_are_served_and_loaded_with_version(registered: tuple[MagicMock, MagicMock, MagicMock]) -> None:
    """The card directory is served under a URL with version and modification time, so imports bust the cache too."""
    hass, add_js, _register = registered
    (config,) = hass.http.async_register_static_paths.call_args.args[0]
    directory = Path(config.path)
    assert config.url_path == URL
    assert config.cache_headers is True
    assert (directory / "tibber-prices-cards.js").is_file()
    assert not (directory / "__init__.py").exists()
    add_js.assert_called_once_with(hass, f"{URL}/tibber-prices-cards.js")


@pytest.mark.unit
def test_open_pages_can_ask_where_the_cards_are_now(registered: tuple[MagicMock, MagicMock, MagicMock]) -> None:
    """The websocket command names the URL of this start, the one cards/reload.js compares with its own."""
    hass, _add_js, register = registered
    ((registered_hass, handler),) = (call.args for call in register.call_args_list)
    assert registered_hass is hass
    connection = MagicMock()
    handler(hass, connection, {"id": 7, "type": "tibber_prices/frontend"})
    connection.send_result.assert_called_once_with(7, {"url": URL})


@pytest.mark.unit
def test_stamp_is_the_newest_module(tmp_path: Path) -> None:
    """Editing any module changes the URL; files that aren't modules (the gzip copies too) don't."""
    for name, modified in (("a.js", 1000), ("b.js", 2000), ("notes.txt", 3000), ("a.js.gz", 4000)):
        (tmp_path / name).write_text("")
        os.utime(tmp_path / name, (modified, modified))
    assert frontend._newest_modification(tmp_path) == 2000  # noqa: SLF001


@pytest.mark.unit
def test_stale_gzip_copies_are_dropped(tmp_path: Path) -> None:
    """A copy that no longer matches its module would send old code under the new URL: it goes."""
    (tmp_path / "same.js").write_bytes(b"new")
    (tmp_path / "same.js.gz").write_bytes(gzip.compress(b"new"))
    (tmp_path / "edited.js").write_bytes(b"new")
    (tmp_path / "edited.js.gz").write_bytes(gzip.compress(b"old"))
    (tmp_path / "gone.js.gz").write_bytes(gzip.compress(b"old"))
    (tmp_path / "broken.js").write_bytes(b"new")
    (tmp_path / "broken.js.gz").write_bytes(b"not gzip")

    frontend._drop_stale_copies(tmp_path)  # noqa: SLF001

    assert sorted(path.name for path in tmp_path.iterdir()) == ["broken.js", "edited.js", "same.js", "same.js.gz"]


@pytest.mark.unit
@pytest.mark.usefixtures("socket_enabled")  # a local test server, as Home Assistant's own hass_client_no_auth
@pytest.mark.parametrize(("accept", "encoding"), [("gzip, deflate, br", "gzip"), ("identity", None)])
async def test_gzip_copy_is_served_when_accepted(
    aiohttp_client: ClientSessionGenerator, tmp_path: Path, accept: str, encoding: str | None
) -> None:
    """The release ships `<module>.js.gz` beside each module; Home Assistant's static handler sends it.

    Guards the assumption build-asset relies on: if Home Assistant or aiohttp stopped picking up
    the copy, every user would download the cards uncompressed again.
    """
    source = b"export const answer = 42;\n"
    (tmp_path / "card.js").write_bytes(source)
    (tmp_path / "card.js.gz").write_bytes(gzip.compress(source))
    app = web.Application()
    app.router.register_resource(CachingStaticResource("/cards", str(tmp_path)))

    client = await aiohttp_client(app, auto_decompress=False)
    response = await client.get("/cards/card.js", headers={"Accept-Encoding": accept})
    body = await response.read()

    assert response.status == 200
    assert response.headers.get("Content-Encoding") == encoding
    assert response.content_type == "text/javascript"
    assert (gzip.decompress(body) if encoding else body) == source
    if encoding:
        assert response.headers["Vary"] == "Accept-Encoding"
