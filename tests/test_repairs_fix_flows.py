"""Tests for the fixes of the repair issues: removing a home that's gone, confirming notices."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.tibber_prices import repairs
from custom_components.tibber_prices.coordinator import repairs as runtime
from homeassistant.components.repairs import ConfirmRepairFlow


@pytest.mark.unit
async def test_home_not_found_is_fixed_by_removing_its_entry() -> None:
    """Confirming "home not found" removes the home's config entry."""
    flow = await repairs.async_create_fix_flow(MagicMock(), "home_not_found_abc", {"entry_id": "abc"})
    assert isinstance(flow, repairs.TibberPricesRemoveHomeFlow)

    flow.hass = MagicMock()
    flow.hass.config_entries.async_remove = AsyncMock()
    flow.handler = "tibber_prices"
    flow.issue_id = "home_not_found_abc"
    result = await flow.async_step_confirm({})

    flow.hass.config_entries.async_remove.assert_awaited_once_with("abc")
    assert result["type"] == "create_entry"


@pytest.mark.unit
async def test_notices_are_confirmed_without_side_effects() -> None:
    """A notice only needs confirming; HA deletes it then."""
    flow = await repairs.async_create_fix_flow(MagicMock(), "period_day_price_unit_abc", None)

    assert type(flow) is ConfirmRepairFlow


@pytest.mark.unit
def test_runtime_issues_of_an_earlier_run_are_cleared_on_start() -> None:
    """An issue reported (and maybe ignored) before a restart goes; what's still wrong comes again."""
    with patch.object(runtime.ir, "async_delete_issue") as delete_issue:
        runtime.TibberPricesRepairManager(MagicMock(), "abc", "Home")

    assert sorted(call.args[2] for call in delete_issue.call_args_list) == sorted(
        f"{key}_abc" for key in runtime.RUNTIME_ISSUES
    )


@pytest.mark.unit
def test_time_travel_views_leave_the_live_entrys_issues_alone() -> None:
    """A time-travel view shares its parent's entry ID: it must not clear the live entry's issues."""
    with patch.object(runtime.ir, "async_delete_issue") as delete_issue:
        runtime.TibberPricesRepairManager(MagicMock(), "abc", "Home", enabled=False)

    delete_issue.assert_not_called()
