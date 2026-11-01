"""The integration serves its dashboard cards itself and loads them into the frontend."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.tibber_prices import frontend


@pytest.mark.unit
async def test_cards_are_served_and_loaded_with_version() -> None:
    """The card directory is served under a URL with version and modification time, so imports bust the cache too."""
    hass = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))
    with (
        patch.object(frontend, "async_get_loaded_integration", return_value=MagicMock(version="1.2.3")),
        patch.object(frontend, "_newest_modification", return_value=1700000000),
        patch.object(frontend, "add_extra_js_url") as add_js,
    ):
        await frontend.async_register_frontend(hass)

    (config,) = hass.http.async_register_static_paths.call_args.args[0]
    directory = Path(config.path)
    assert config.url_path == "/tibber_prices_frontend/1.2.3-1700000000"
    assert config.cache_headers is True
    assert (directory / "tibber-prices-cards.js").is_file()
    assert not (directory / "__init__.py").exists()
    add_js.assert_called_once_with(hass, "/tibber_prices_frontend/1.2.3-1700000000/tibber-prices-cards.js")


@pytest.mark.unit
def test_stamp_is_the_newest_module(tmp_path: Path) -> None:
    """Editing any module changes the URL; files that aren't modules don't."""
    for name, modified in (("a.js", 1000), ("b.js", 2000), ("notes.txt", 3000)):
        (tmp_path / name).write_text("")
        os.utime(tmp_path / name, (modified, modified))
    assert frontend._newest_modification(tmp_path) == 2000  # noqa: SLF001
