"""Adds config flow for tibber_prices."""

from __future__ import annotations

import voluptuous as vol
from slugify import slugify

from homeassistant import config_entries
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import (
    TibberPricesApiClient,
    TibberPricesApiClientAuthenticationError,
    TibberPricesApiClientCommunicationError,
    TibberPricesApiClientError,
)
from .const import DOMAIN, LOGGER


class TibberPricesFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for tibber_prices."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._reauth_entry: config_entries.ConfigEntry | None = None

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return TibberPricesOptionsFlowHandler(config_entry)

    def is_matching(self, other_flow: dict) -> bool:
        """Return True if match_dict matches this flow."""
        return bool(other_flow.get("domain") == DOMAIN)

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        _errors = {}
        if user_input is not None:
            try:
                name = await self._test_credentials(
                    access_token=user_input[CONF_ACCESS_TOKEN]
                )
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
                await self.async_set_unique_id(unique_id=slugify(name))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=name,
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ACCESS_TOKEN,
                        default=(user_input or {}).get(
                            CONF_ACCESS_TOKEN, vol.UNDEFINED
                        ),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                },
            ),
            errors=_errors,
        )

    async def _test_credentials(self, access_token: str) -> str:
        """Validate credentials and return the user's name."""
        client = TibberPricesApiClient(
            access_token=access_token,
            session=async_create_clientsession(self.hass),
        )
        result = await client.async_test_connection()
        return result["viewer"]["name"]


class TibberPricesOptionsFlowHandler(config_entries.OptionsFlow):
    """Tibber Prices config flow options handler."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        super().__init__()
        # Store the entry_id instead of the whole config_entry
        self._entry_id = config_entry.entry_id

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Test the new access token and get account name
                client = TibberPricesApiClient(
                    access_token=user_input[CONF_ACCESS_TOKEN],
                    session=async_create_clientsession(self.hass),
                )
                result = await client.async_test_connection()
                new_account_name = result["viewer"]["name"]

                # Get the config entry using the entry_id
                config_entry = self.hass.config_entries.async_get_entry(self._entry_id)
                if not config_entry:
                    return self.async_abort(reason="entry_not_found")

                # Check if this token is for the same account
                current_unique_id = config_entry.unique_id
                new_unique_id = slugify(new_account_name)

                if current_unique_id != new_unique_id:
                    # Token is for a different account
                    errors["base"] = "different_account"
                else:
                    # Update the config entry with the new access token
                    return self.async_create_entry(title="", data=user_input)

            except TibberPricesApiClientAuthenticationError as exception:
                LOGGER.warning(exception)
                errors["base"] = "auth"
            except TibberPricesApiClientCommunicationError as exception:
                LOGGER.error(exception)
                errors["base"] = "connection"
            except TibberPricesApiClientError as exception:
                LOGGER.exception(exception)
                errors["base"] = "unknown"

        # Get current config entry to get the current access token
        config_entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if not config_entry:
            return self.async_abort(reason="entry_not_found")

        # If there's no user input or if there were errors, show the form
        schema = {
            vol.Required(
                CONF_ACCESS_TOKEN,
                default=config_entry.data.get(CONF_ACCESS_TOKEN, ""),
            ): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.TEXT,
                ),
            ),
        }

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
            errors=errors,
        )
