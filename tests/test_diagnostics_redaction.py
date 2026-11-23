"""Diagnostics files get attached to public issues: nothing identifying may be in them."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.tibber_prices.diagnostics import async_get_config_entry_diagnostics

ADDRESS = "Musterstrasse 1, 12345 Musterstadt"
HOME_ID = "96a14971-525a-4420-aae9-e5aedaa129ff"


@pytest.mark.unit
async def test_diagnostics_redact_address_title_and_home_id() -> None:
    """Entry and view titles (built from the address), the home id and personal fields are redacted."""
    coordinator = MagicMock()
    coordinator.data = {
        "home_id": HOME_ID,
        "priceInfo": [],
        "user": {
            "address": {"address1": "Musterstrasse 1", "latitude": 52.5},
            "owner": {"email": "a@b.de"},
            "login": "login@b.de",
        },
    }
    coordinator.time_shift.describe.return_value = "none"
    coordinator.time_shift.resolve.return_value = None
    coordinator.time_shift.has_data_coverage.return_value = True
    coordinator.last_exception = RuntimeError(f"Home {HOME_ID} at {ADDRESS} has no subscription")
    coordinator._last_price_update = None  # noqa: SLF001
    coordinator._last_user_update = None  # noqa: SLF001
    coordinator._last_coordinator_update = None  # noqa: SLF001
    coordinator._last_api_call_date = None  # noqa: SLF001

    view = SimpleNamespace(coordinator=coordinator, subentry=SimpleNamespace(title=f"{ADDRESS} (+1 day)", data={}))
    entry = SimpleNamespace(
        entry_id="entry1",
        version=1,
        minor_version=1,
        domain="tibber_prices",
        title=ADDRESS,
        state="loaded",
        data={"home_id": HOME_ID, "access_token": "secret-token"},
        options={},
        runtime_data=SimpleNamespace(coordinator=coordinator, subentries={"sub1": view}),
    )

    result = await async_get_config_entry_diagnostics(MagicMock(), entry)  # type: ignore[arg-type]

    dumped = json.dumps(result, default=str)
    for secret in (ADDRESS, "Musterstrasse", HOME_ID, "a@b.de", "login@b.de", "52.5", "secret-token"):
        assert secret not in dumped, f"{secret!r} leaked into diagnostics"
