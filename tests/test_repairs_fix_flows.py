"""Tests for the fixes of the repair issues: removing a home that's gone, confirming notices."""

from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.tibber_prices.const import DOMAIN
from custom_components.tibber_prices.coordinator import repairs as runtime
from homeassistant.components.repairs import RepairsFlowManager, repairs_flow_manager
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

ISSUE_ID = "home_not_found_abc"


@pytest.fixture
async def flow_manager(hass: HomeAssistant) -> RepairsFlowManager:
    """Set up repairs and this integration, without an entry, and return the repairs flow manager."""
    assert await async_setup_component(hass, "repairs", {})
    assert await async_setup_component(hass, DOMAIN, {})
    manager = repairs_flow_manager(hass)
    assert manager is not None
    return manager


def _create_home_not_found_issue(hass: HomeAssistant) -> None:
    """Report the home of entry "abc" as gone, as the coordinator does."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_ID,
        data={"entry_id": "abc"},
        is_fixable=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key="home_not_found",
        translation_placeholders={"home_name": "Home"},
    )


@pytest.mark.integration
async def test_home_not_found_is_fixed_by_removing_its_entry(
    hass: HomeAssistant, flow_manager: RepairsFlowManager, issue_registry: ir.IssueRegistry
) -> None:
    """Confirming "home not found" shows the home's name, then removes its entry and the issue."""
    entry = MockConfigEntry(domain=DOMAIN, entry_id="abc")
    entry.add_to_hass(hass)
    _create_home_not_found_issue(hass)

    result = await flow_manager.async_init(DOMAIN, context={"issue_id": ISSUE_ID})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {"home_name": "Home"}

    result = await flow_manager.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert hass.config_entries.async_get_entry("abc") is None
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID) is None


@pytest.mark.integration
async def test_home_not_found_tolerates_an_entry_already_removed(
    hass: HomeAssistant, flow_manager: RepairsFlowManager, issue_registry: ir.IssueRegistry
) -> None:
    """The fix still finishes, and clears the issue, when the entry went in the meantime."""
    _create_home_not_found_issue(hass)

    result = await flow_manager.async_init(DOMAIN, context={"issue_id": ISSUE_ID})
    result = await flow_manager.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID) is None


@pytest.mark.integration
async def test_notices_are_confirmed_without_side_effects(
    hass: HomeAssistant, flow_manager: RepairsFlowManager, issue_registry: ir.IssueRegistry
) -> None:
    """A notice only needs confirming; HA deletes it then and leaves the entry alone."""
    entry = MockConfigEntry(domain=DOMAIN, entry_id="abc")
    entry.add_to_hass(hass)
    issue_id = "period_day_price_unit_abc"
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        data={"entry_id": "abc"},
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="period_day_price_unit",
    )

    result = await flow_manager.async_init(DOMAIN, context={"issue_id": issue_id})
    assert result["type"] is FlowResultType.FORM
    result = await flow_manager.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert hass.config_entries.async_get_entry("abc") is entry
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


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
