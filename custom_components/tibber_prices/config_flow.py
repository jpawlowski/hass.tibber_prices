"""Adds config flow for tibber_prices."""

from __future__ import annotations

import voluptuous as vol

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


class TibberPricesFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for tibber_prices."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._reauth_entry: config_entries.ConfigEntry | None = None
        self._pending_user_input: dict | None = None

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
                # Store viewer for use in finish step
                self._pending_user_input = {
                    "access_token": user_input[CONF_ACCESS_TOKEN],
                    "viewer": viewer,
                }
                return await self.async_step_finish()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ACCESS_TOKEN,
                        default=(user_input or {}).get(CONF_ACCESS_TOKEN, vol.UNDEFINED),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                },
            ),
            errors=_errors,
        )

    async def async_step_finish(self, user_input: dict | None = None) -> config_entries.ConfigFlowResult:
        """Show a finish screen after successful setup, then create entry on submit."""
        if self._pending_user_input is not None and user_input is None:
            # First visit: show home selection
            viewer = self._pending_user_input["viewer"]
            homes = viewer.get("homes", [])
            # Build choices: label = address or nickname, value = id
            home_choices = {}
            for home in homes:
                label = home.get("appNickname") or home.get("address", {}).get("address1") or home["id"]
                if home.get("address", {}).get("city"):
                    label += f", {home['address']['city']}"
                home_choices[home["id"]] = label
            schema = vol.Schema({vol.Required("home_id"): vol.In(home_choices)})
            return self.async_show_form(
                step_id="finish",
                data_schema=schema,
                description_placeholders={},
                errors={},
                last_step=True,
            )
        if self._pending_user_input is not None and user_input is not None:
            # User selected home, create entry
            home_id = user_input["home_id"]
            viewer = self._pending_user_input["viewer"]
            # Use the same label as shown to the user for the config entry title
            home_label = None
            for home in viewer.get("homes", []):
                if home["id"] == home_id:
                    home_label = home.get("appNickname") or home.get("address", {}).get("address1") or home_id
                    if home.get("address", {}).get("city"):
                        home_label += f", {home['address']['city']}"
                    break
            if not home_label:
                home_label = viewer.get("name", "Tibber")
            data = {
                CONF_ACCESS_TOKEN: self._pending_user_input["access_token"],
                CONF_EXTENDED_DESCRIPTIONS: DEFAULT_EXTENDED_DESCRIPTIONS,
                CONF_BEST_PRICE_FLEX: DEFAULT_BEST_PRICE_FLEX,
                CONF_PEAK_PRICE_FLEX: DEFAULT_PEAK_PRICE_FLEX,
            }
            self._pending_user_input = None
            # Set unique_id to home_id
            await self.async_set_unique_id(unique_id=home_id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=home_label,
                data=data,
            )
        return self.async_abort(reason="setup_complete")

    async def _get_viewer_details(self, access_token: str) -> dict:
        """Validate credentials and return information about the account (viewer object)."""
        client = TibberPricesApiClient(
            access_token=access_token,
            session=async_create_clientsession(self.hass),
        )
        result = await client.async_get_viewer_details()
        return result["viewer"]


class TibberPricesOptionsFlowHandler(config_entries.OptionsFlow):
    """Tibber Prices config flow options handler."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:  # noqa: ARG002
        """Initialize options flow."""
        super().__init__()

    async def async_step_init(self, user_input: dict | None = None) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        # Build options schema
        options = {
            vol.Required(
                CONF_ACCESS_TOKEN,
                default=self.config_entry.data.get(CONF_ACCESS_TOKEN, ""),
            ): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.TEXT,
                ),
            ),
            vol.Optional(
                CONF_EXTENDED_DESCRIPTIONS,
                default=self.config_entry.options.get(
                    CONF_EXTENDED_DESCRIPTIONS,
                    self.config_entry.data.get(CONF_EXTENDED_DESCRIPTIONS, DEFAULT_EXTENDED_DESCRIPTIONS),
                ),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_BEST_PRICE_FLEX,
                default=int(
                    self.config_entry.options.get(
                        CONF_BEST_PRICE_FLEX,
                        self.config_entry.data.get(CONF_BEST_PRICE_FLEX, DEFAULT_BEST_PRICE_FLEX),
                    )
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=100,
                    step=1,
                    mode=selector.NumberSelectorMode.SLIDER,
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
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=100,
                    step=1,
                    mode=selector.NumberSelectorMode.SLIDER,
                ),
            ),
        }

        if user_input is not None:
            # Validate new access token if changed
            new_token = user_input.get(CONF_ACCESS_TOKEN, self.config_entry.data.get(CONF_ACCESS_TOKEN, "")) or ""
            current_home_id = self.config_entry.data.get("home_id", "")
            errors = {}
            if new_token != self.config_entry.data.get(CONF_ACCESS_TOKEN, ""):
                try:
                    client = TibberPricesApiClient(
                        access_token=new_token,
                        session=async_create_clientsession(self.hass),
                    )
                    result = await client.async_get_viewer_details()
                    homes = result["viewer"].get("homes", [])
                    if not any(home["id"] == current_home_id for home in homes):
                        errors[CONF_ACCESS_TOKEN] = "different_home"
                except TibberPricesApiClientAuthenticationError as exception:
                    LOGGER.warning(exception)
                    errors[CONF_ACCESS_TOKEN] = "auth"
                except TibberPricesApiClientCommunicationError as exception:
                    LOGGER.error(exception)
                    errors[CONF_ACCESS_TOKEN] = "connection"
                except TibberPricesApiClientError as exception:
                    LOGGER.exception(exception)
                    errors[CONF_ACCESS_TOKEN] = "unknown"
            if errors:
                # Show form again with errors
                description_placeholders = {
                    "access_token": new_token,
                    "home_id": current_home_id,
                }
                return self.async_show_form(
                    step_id="init",
                    data_schema=vol.Schema(options),
                    errors=errors,
                    description_placeholders=description_placeholders,
                )
            # Only update options and access token if valid
            return self.async_create_entry(title="", data=user_input)

        # Prepare read-only info for description placeholders
        description_placeholders = {
            "access_token": self.config_entry.data.get(CONF_ACCESS_TOKEN, ""),
            "unique_id": self.config_entry.unique_id or "",
        }

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(options),
            errors=errors,
            description_placeholders=description_placeholders,
        )
