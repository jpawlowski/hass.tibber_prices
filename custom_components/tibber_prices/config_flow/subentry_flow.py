"""Subentry config flow for adding additional Tibber homes."""

from __future__ import annotations

from typing import Any

from custom_components.tibber_prices.config_flow.schemas import (
    get_select_home_schema,
    get_subentry_init_schema,
)
from custom_components.tibber_prices.const import (
    CONF_EXTENDED_DESCRIPTIONS,
    DEFAULT_EXTENDED_DESCRIPTIONS,
    DOMAIN,
)
from homeassistant.config_entries import ConfigSubentryFlow, SubentryFlowResult
from homeassistant.helpers.selector import SelectOptionDict


class TibberPricesSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flows for tibber_prices."""

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """User flow to add a new home."""
        parent_entry = self._get_entry()
        if not parent_entry or not hasattr(parent_entry, "runtime_data") or not parent_entry.runtime_data:
            return self.async_abort(reason="no_parent_entry")

        coordinator = parent_entry.runtime_data.coordinator

        # Force refresh user data to get latest homes from Tibber API
        await coordinator.refresh_user_data()

        homes = coordinator.get_user_homes()
        if not homes:
            return self.async_abort(reason="no_available_homes")

        if user_input is not None:
            selected_home_id = user_input["home_id"]
            selected_home = next((home for home in homes if home["id"] == selected_home_id), None)

            if not selected_home:
                return self.async_abort(reason="home_not_found")

            home_title = self._get_home_title(selected_home)
            home_id = selected_home["id"]

            return self.async_create_entry(
                title=home_title,
                data={
                    "home_id": home_id,
                    "home_data": selected_home,
                },
                description=f"Subentry for {home_title}",
                description_placeholders={"home_id": home_id},
                unique_id=home_id,
            )

        # Get existing home IDs by checking all subentries for this parent
        existing_home_ids = {
            entry.data["home_id"]
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if entry.data.get("home_id") and entry != parent_entry
        }

        available_homes = [home for home in homes if home["id"] not in existing_home_ids]

        if not available_homes:
            return self.async_abort(reason="no_available_homes")

        home_options = [
            SelectOptionDict(
                value=home["id"],
                label=self._get_home_title(home),
            )
            for home in available_homes
        ]

        return self.async_show_form(
            step_id="user",
            data_schema=get_select_home_schema(home_options),
            description_placeholders={},
            errors={},
        )

    def _get_home_title(self, home: dict) -> str:
        """Generate a user-friendly title for a home."""
        title = home.get("appNickname")
        if title and title.strip():
            return title.strip()

        address = home.get("address", {})
        if address:
            parts = []
            if address.get("address1"):
                parts.append(address["address1"])
            if address.get("city"):
                parts.append(address["city"])
            if parts:
                return ", ".join(parts)

        return home.get("id", "Unknown Home")

    async def async_step_init(self, user_input: dict | None = None) -> SubentryFlowResult:
        """Manage the options for a subentry."""
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}

        if user_input is not None:
            return self.async_update_and_abort(
                self._get_entry(),
                subentry,
                data_updates=user_input,
            )

        extended_descriptions = subentry.data.get(CONF_EXTENDED_DESCRIPTIONS, DEFAULT_EXTENDED_DESCRIPTIONS)

        return self.async_show_form(
            step_id="init",
            data_schema=get_subentry_init_schema(extended_descriptions=extended_descriptions),
            errors=errors,
        )
