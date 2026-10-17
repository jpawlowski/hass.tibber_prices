"""The integration serves its dashboard cards itself and loads them into the frontend."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.tibber_prices import frontend


@pytest.mark.unit
async def test_cards_are_served_and_loaded_with_version() -> None:
    """Served from the integration folder; version and modification time in the URL bust the cache."""
    hass = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))
    with (
        patch.object(frontend, "async_get_loaded_integration", return_value=MagicMock(version="1.2.3")),
        patch.object(frontend, "add_extra_js_url") as add_js,
    ):
        await frontend.async_register_frontend(hass)

    (config,) = hass.http.async_register_static_paths.call_args.args[0]
    assert config.url_path == "/tibber_prices_frontend/tibber-prices-cards.js"
    assert Path(config.path).is_file()
    modified = int(Path(config.path).stat().st_mtime)
    add_js.assert_called_once_with(hass, f"/tibber_prices_frontend/tibber-prices-cards.js?v=1.2.3-{modified}")
