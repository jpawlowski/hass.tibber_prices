"""
Fixes for the integration's repair issues.

- home_not_found: the home is gone from the Tibber account. Its fix removes the home's entry, as
  the notice suggests (should the home come back, the notice goes by itself before that).
- Notices (migrations.NOTICES): only to read; confirming them deletes them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.helpers import issue_registry as ir

if TYPE_CHECKING:
    from homeassistant.components.repairs import RepairsFlowResult
    from homeassistant.core import HomeAssistant


class TibberPricesRemoveHomeFlow(RepairsFlow):
    """Confirm, then remove the config entry of a home that's gone from the Tibber account."""

    def __init__(self, entry_id: str) -> None:
        """Remember which entry to remove."""
        self._entry_id = entry_id

    async def async_step_init(self, user_input: dict[str, str] | None = None) -> RepairsFlowResult:
        """Start with the confirmation."""
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict[str, str] | None = None) -> RepairsFlowResult:
        """Remove the entry once confirmed (HA then deletes the issue)."""
        if user_input is not None:
            if self.hass.config_entries.async_get_entry(self._entry_id) is not None:
                await self.hass.config_entries.async_remove(self._entry_id)
            return self.async_create_entry(data={})
        issue = ir.async_get(self.hass).async_get_issue(self.handler, self.issue_id)
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders=issue.translation_placeholders if issue else None,
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Return the fix for an issue: removing a home that's gone, or confirming a notice."""
    entry_id = data.get("entry_id") if data else None
    if issue_id.startswith("home_not_found_") and isinstance(entry_id, str):
        return TibberPricesRemoveHomeFlow(entry_id)
    return ConfirmRepairFlow()
