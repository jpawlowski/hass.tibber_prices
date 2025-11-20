"""Main config flow for tibber_prices integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from custom_components.tibber_prices.config_flow_handlers.options_flow import (
    TibberPricesOptionsFlowHandler,
)
from custom_components.tibber_prices.config_flow_handlers.schemas import (
    get_reauth_confirm_schema,
    get_select_home_schema,
    get_user_schema,
)
from custom_components.tibber_prices.config_flow_handlers.subentry_flow import (
    TibberPricesSubentryFlowHandler,
)
from custom_components.tibber_prices.config_flow_handlers.validators import (
    TibberPricesCannotConnectError,
    TibberPricesInvalidAuthError,
    validate_api_token,
)
from custom_components.tibber_prices.const import DOMAIN, LOGGER
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import callback
from homeassistant.helpers.selector import SelectOptionDict

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigSubentryFlow


class TibberPricesFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for tibber_prices."""

    VERSION = 1
    MINOR_VERSION = 0

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._reauth_entry: ConfigEntry | None = None
        self._viewer: dict | None = None
        self._access_token: str | None = None
        self._user_name: str | None = None
        self._user_login: str | None = None
        self._user_id: str | None = None

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls,
        config_entry: ConfigEntry,  # noqa: ARG003
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentries supported by this integration."""
        return {"home": TibberPricesSubentryFlowHandler}

    @staticmethod
    @callback
    def async_get_options_flow(_config_entry: ConfigEntry) -> OptionsFlow:
        """Create an options flow for this configentry."""
        return TibberPricesOptionsFlowHandler()

    def is_matching(self, other_flow: dict) -> bool:
        """Return True if match_dict matches this flow."""
        return bool(other_flow.get("domain") == DOMAIN)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:  # noqa: ARG002
        """Handle reauth flow when access token becomes invalid."""
        entry_id = self.context.get("entry_id")
        if entry_id:
            self._reauth_entry = self.hass.config_entries.async_get_entry(entry_id)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Confirm reauth dialog - prompt for new access token."""
        _errors = {}

        if user_input is not None:
            try:
                viewer = await validate_api_token(self.hass, user_input[CONF_ACCESS_TOKEN])
            except TibberPricesInvalidAuthError as exception:
                LOGGER.warning(exception)
                _errors["base"] = "auth"
            except TibberPricesCannotConnectError as exception:
                LOGGER.error(exception)
                _errors["base"] = "connection"
            else:
                # Validate that the new token has access to all configured homes
                if self._reauth_entry:
                    # Get all configured home IDs (main entry + subentries)
                    configured_home_ids = self._get_all_configured_home_ids(self._reauth_entry)

                    # Get accessible home IDs from the new token
                    accessible_homes = viewer.get("homes", [])
                    accessible_home_ids = {home["id"] for home in accessible_homes}

                    # Check if all configured homes are accessible with the new token
                    missing_home_ids = configured_home_ids - accessible_home_ids

                    if missing_home_ids:
                        # New token doesn't have access to all configured homes
                        LOGGER.error(
                            "New access token missing access to configured homes: %s",
                            ", ".join(missing_home_ids),
                        )
                        _errors["base"] = "missing_homes"
                    else:
                        # Update the config entry with the new access token
                        self.hass.config_entries.async_update_entry(
                            self._reauth_entry,
                            data={
                                **self._reauth_entry.data,
                                CONF_ACCESS_TOKEN: user_input[CONF_ACCESS_TOKEN],
                            },
                        )
                        await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                        return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=get_reauth_confirm_schema(),
            errors=_errors,
        )

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user. Only ask for access token."""
        _errors = {}
        if user_input is not None:
            try:
                viewer = await validate_api_token(self.hass, user_input[CONF_ACCESS_TOKEN])
            except TibberPricesInvalidAuthError as exception:
                LOGGER.warning(exception)
                _errors["base"] = "auth"
            except TibberPricesCannotConnectError as exception:
                LOGGER.error(exception)
                _errors["base"] = "connection"
            else:
                user_id = viewer.get("userId", None)
                user_name = viewer.get("name") or user_id or "Unknown User"
                user_login = viewer.get("login", "N/A")
                homes = viewer.get("homes", [])

                if not user_id:
                    LOGGER.error("No user ID found: %s", viewer)
                    return self.async_abort(reason="unknown")

                if not homes:
                    LOGGER.error("No homes found: %s", viewer)
                    return self.async_abort(reason="unknown")

                LOGGER.debug("Viewer data received: %s", viewer)

                await self.async_set_unique_id(unique_id=str(user_id))
                self._abort_if_unique_id_configured()

                # Store viewer data in the flow for use in the next step
                self._viewer = viewer
                self._access_token = user_input[CONF_ACCESS_TOKEN]
                self._user_name = user_name
                self._user_login = user_login
                self._user_id = user_id

                # Move to home selection step
                return await self.async_step_select_home()

        return self.async_show_form(
            step_id="user",
            data_schema=get_user_schema((user_input or {}).get(CONF_ACCESS_TOKEN)),
            errors=_errors,
        )

    async def async_step_select_home(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Handle home selection during initial setup."""
        homes = self._viewer.get("homes", []) if self._viewer else []

        if not homes:
            return self.async_abort(reason="unknown")

        if user_input is not None:
            selected_home_id = user_input["home_id"]
            selected_home = next((home for home in homes if home["id"] == selected_home_id), None)

            if not selected_home:
                return self.async_abort(reason="unknown")

            data = {
                CONF_ACCESS_TOKEN: self._access_token or "",
                "home_id": selected_home_id,
                "home_data": selected_home,
                "homes": homes,
                "user_login": self._user_login or "N/A",
            }

            return self.async_create_entry(
                title=self._user_name or "Unknown User",
                data=data,
                description=f"{self._user_login} ({self._user_id})",
            )

        home_options = [
            SelectOptionDict(
                value=home["id"],
                label=self._get_home_title(home),
            )
            for home in homes
        ]

        return self.async_show_form(
            step_id="select_home",
            data_schema=get_select_home_schema(home_options),
        )

    def _get_all_configured_home_ids(self, main_entry: ConfigEntry) -> set[str]:
        """Get all configured home IDs from main entry and all subentries."""
        home_ids = set()

        # Add home_id from main entry if it exists
        if main_entry.data.get("home_id"):
            home_ids.add(main_entry.data["home_id"])

        # Add home_ids from all subentries
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.data.get("home_id") and entry != main_entry:
                home_ids.add(entry.data["home_id"])

        return home_ids

    @staticmethod
    def _get_home_title(home: dict) -> str:
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
