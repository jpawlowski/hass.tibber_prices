"""Adds config flow for tibber_prices."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentry,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    TibberPricesApiClient,
    TibberPricesApiClientAuthenticationError,
    TibberPricesApiClientCommunicationError,
    TibberPricesApiClientError,
)
from .const import (
    CONF_BEST_PRICE_FLEX,
    CONF_EXTENDED_DESCRIPTIONS,
    CONF_PEAK_PRICE_FLEX,
    DEFAULT_BEST_PRICE_FLEX,
    DEFAULT_EXTENDED_DESCRIPTIONS,
    DEFAULT_PEAK_PRICE_FLEX,
    DOMAIN,
    LOGGER,
)


class TibberPricesFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for tibber_prices."""

    VERSION = 1
    MINOR_VERSION = 0

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._reauth_entry: ConfigEntry | None = None

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry: ConfigEntry) -> dict[str, type[ConfigSubentryFlow]]:  # noqa: ARG003
        """Return subentries supported by this integration."""
        return {"home": TibberPricesSubentryFlowHandler}

    @staticmethod
    def async_get_reauth_flow(entry: ConfigEntry) -> ConfigFlow:
        """Return the reauth flow handler for this integration."""
        return TibberPricesReauthFlowHandler(entry)

    def is_matching(self, other_flow: dict) -> bool:
        """Return True if match_dict matches this flow."""
        return bool(other_flow.get("domain") == DOMAIN)

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user. Only ask for access token."""
        _errors = {}
        if user_input is not None:
            try:
                viewer = await self._get_viewer_details(access_token=user_input[CONF_ACCESS_TOKEN])
            except TibberPricesApiClientAuthenticationError as exception:
                LOGGER.warning(exception)
                _errors["base"] = "auth"
            except TibberPricesApiClientCommunicationError as exception:
                LOGGER.error(exception)
                _errors["base"] = "connection"
            except TibberPricesApiClientError as exception:
                LOGGER.exception(exception)
                _errors["base"] = "unknown"
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

                data = {CONF_ACCESS_TOKEN: user_input[CONF_ACCESS_TOKEN], "homes": homes}

                await self.async_set_unique_id(unique_id=str(user_id))
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_name,
                    data=data,
                    description=f"{user_login} ({user_id})",
                    description_placeholders={
                        "user_id": user_id,
                        "user_name": user_name,
                        "user_login": user_login,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ACCESS_TOKEN,
                        default=(user_input or {}).get(CONF_ACCESS_TOKEN, vol.UNDEFINED),
                    ): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.TEXT,
                        ),
                    ),
                },
            ),
            errors=_errors,
        )

    async def _get_viewer_details(self, access_token: str) -> dict:
        """Validate credentials and return information about the account (viewer object)."""
        client = TibberPricesApiClient(
            access_token=access_token,
            session=async_create_clientsession(self.hass),
        )
        result = await client.async_get_viewer_details()
        return result["viewer"]


class TibberPricesReauthFlowHandler(ConfigFlow):
    """Handle a reauthentication flow for tibber_prices."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the reauth flow handler."""
        self._entry = entry
        self._errors: dict[str, str] = {}

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Prompt for a new access token."""
        if user_input is not None:
            try:
                await TibberPricesApiClient(
                    access_token=user_input[CONF_ACCESS_TOKEN],
                    session=async_create_clientsession(self.hass),
                ).async_get_viewer_details()
            except TibberPricesApiClientAuthenticationError as exception:
                LOGGER.warning(exception)
                self._errors["base"] = "auth"
            except TibberPricesApiClientCommunicationError as exception:
                LOGGER.error(exception)
                self._errors["base"] = "connection"
            except TibberPricesApiClientError as exception:
                LOGGER.exception(exception)
                self._errors["base"] = "unknown"
            else:
                self.hass.config_entries.async_update_entry(
                    self._entry,
                    data={
                        **self._entry.data,
                        CONF_ACCESS_TOKEN: user_input[CONF_ACCESS_TOKEN],
                    },
                )
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACCESS_TOKEN): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
                }
            ),
            errors=self._errors,
        )


class TibberPricesSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flows for tibber_prices."""

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """User flow to add a new home."""
        parent_entry = self._get_entry()
        if not parent_entry:
            return self.async_abort(reason="no_parent_entry")

        homes = parent_entry.data.get("homes", [])
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
        existing_home_ids = set()
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            # Check if this entry has home_id data (indicating it's a subentry)
            if entry.data.get("home_id") and entry != parent_entry:
                existing_home_ids.add(entry.data["home_id"])

        available_homes = [home for home in homes if home["id"] not in existing_home_ids]

        if not available_homes:
            return self.async_abort(reason="no_available_homes")

        from homeassistant.helpers.selector import SelectOptionDict

        home_options = [
            SelectOptionDict(
                value=home["id"],
                label=self._get_home_title(home),
            )
            for home in available_homes
        ]

        schema = vol.Schema(
            {
                vol.Required("home_id"): SelectSelector(
                    SelectSelectorConfig(
                        options=home_options,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            description_placeholders={},
            errors={},
        )

    def _get_home_title(self, home: dict) -> str:
        """Generate a user-friendly title for a home."""
        title = home.get("appNickname")
        if title:
            return title

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


class TibberPricesOptionsSubentryFlowHandler(OptionsFlow):
    """Tibber Prices config flow options handler."""

    def __init__(self, config_entry: ConfigSubentry) -> None:  # noqa: ARG002
        """Initialize options flow."""
        super().__init__()

    async def async_step_init(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        options = {
            vol.Optional(
                CONF_EXTENDED_DESCRIPTIONS,
                default=self.config_entry.options.get(
                    CONF_EXTENDED_DESCRIPTIONS,
                    self.config_entry.data.get(CONF_EXTENDED_DESCRIPTIONS, DEFAULT_EXTENDED_DESCRIPTIONS),
                ),
            ): BooleanSelector(),
            vol.Optional(
                CONF_BEST_PRICE_FLEX,
                default=int(
                    self.config_entry.options.get(
                        CONF_BEST_PRICE_FLEX,
                        self.config_entry.data.get(CONF_BEST_PRICE_FLEX, DEFAULT_BEST_PRICE_FLEX),
                    )
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    max=100,
                    step=1,
                    mode=NumberSelectorMode.SLIDER,
                ),
            ),
            vol.Optional(
                CONF_PEAK_PRICE_FLEX,
                default=int(
                    self.config_entry.options.get(
                        CONF_PEAK_PRICE_FLEX,
                        self.config_entry.data.get(CONF_PEAK_PRICE_FLEX, DEFAULT_PEAK_PRICE_FLEX),
                    )
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    max=100,
                    step=1,
                    mode=NumberSelectorMode.SLIDER,
                ),
            ),
        }

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        description_placeholders = {
            "unique_id": self.config_entry.unique_id or "",
        }

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(options),
            errors=errors,
            description_placeholders=description_placeholders,
        )
