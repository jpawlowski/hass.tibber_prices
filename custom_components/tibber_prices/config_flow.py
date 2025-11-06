"""Adds config flow for tibber_prices."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
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
    SelectOptionDict,
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
    CONF_BEST_PRICE_MIN_DISTANCE_FROM_AVG,
    CONF_EXTENDED_DESCRIPTIONS,
    CONF_PEAK_PRICE_FLEX,
    CONF_PEAK_PRICE_MIN_DISTANCE_FROM_AVG,
    CONF_PRICE_RATING_THRESHOLD_HIGH,
    CONF_PRICE_RATING_THRESHOLD_LOW,
    DEFAULT_BEST_PRICE_FLEX,
    DEFAULT_BEST_PRICE_MIN_DISTANCE_FROM_AVG,
    DEFAULT_EXTENDED_DESCRIPTIONS,
    DEFAULT_PEAK_PRICE_FLEX,
    DEFAULT_PEAK_PRICE_MIN_DISTANCE_FROM_AVG,
    DEFAULT_PRICE_RATING_THRESHOLD_HIGH,
    DEFAULT_PRICE_RATING_THRESHOLD_LOW,
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
        self._reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Confirm reauth dialog - prompt for new access token."""
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
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACCESS_TOKEN): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.TEXT),
                    ),
                }
            ),
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
            data_schema=vol.Schema(
                {
                    vol.Required("home_id"): SelectSelector(
                        SelectSelectorConfig(
                            options=home_options,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
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

    async def _get_viewer_details(self, access_token: str) -> dict:
        """Validate credentials and return information about the account (viewer object)."""
        client = TibberPricesApiClient(
            access_token=access_token,
            session=async_create_clientsession(self.hass),
        )
        result = await client.async_get_viewer_details()
        return result["viewer"]


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

        options = {
            vol.Optional(
                CONF_EXTENDED_DESCRIPTIONS,
                default=subentry.data.get(CONF_EXTENDED_DESCRIPTIONS, DEFAULT_EXTENDED_DESCRIPTIONS),
            ): BooleanSelector(),
        }

        if user_input is not None:
            return self.async_update_and_abort(
                self._get_entry(),
                subentry,
                data_updates=user_input,
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(options),
            errors=errors,
        )


class TibberPricesOptionsFlowHandler(OptionsFlow):
    """Handle options for tibber_prices entries."""

    def __init__(self) -> None:
        """Initialize options flow."""
        self._options: dict[str, Any] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the options - General Settings."""
        # Initialize options from config_entry on first call
        if not self._options:
            self._options = dict(self.config_entry.options)

        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_price_rating()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_EXTENDED_DESCRIPTIONS,
                        default=self.config_entry.options.get(
                            CONF_EXTENDED_DESCRIPTIONS, DEFAULT_EXTENDED_DESCRIPTIONS
                        ),
                    ): BooleanSelector(),
                }
            ),
            description_placeholders={
                "user_login": self.config_entry.data.get("user_login", "N/A"),
            },
        )

    async def async_step_price_rating(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Configure price rating thresholds."""
        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_best_price()

        return self.async_show_form(
            step_id="price_rating",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_PRICE_RATING_THRESHOLD_LOW,
                        default=int(
                            self.config_entry.options.get(
                                CONF_PRICE_RATING_THRESHOLD_LOW,
                                DEFAULT_PRICE_RATING_THRESHOLD_LOW,
                            )
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=-100,
                            max=0,
                            step=1,
                            mode=NumberSelectorMode.SLIDER,
                        ),
                    ),
                    vol.Optional(
                        CONF_PRICE_RATING_THRESHOLD_HIGH,
                        default=int(
                            self.config_entry.options.get(
                                CONF_PRICE_RATING_THRESHOLD_HIGH,
                                DEFAULT_PRICE_RATING_THRESHOLD_HIGH,
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
            ),
        )

    async def async_step_best_price(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Configure best price period settings."""
        if user_input is not None:
            self._options.update(user_input)
            return await self.async_step_peak_price()

        return self.async_show_form(
            step_id="best_price",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_BEST_PRICE_FLEX,
                        default=int(
                            self.config_entry.options.get(
                                CONF_BEST_PRICE_FLEX,
                                DEFAULT_BEST_PRICE_FLEX,
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
                        CONF_BEST_PRICE_MIN_DISTANCE_FROM_AVG,
                        default=int(
                            self.config_entry.options.get(
                                CONF_BEST_PRICE_MIN_DISTANCE_FROM_AVG,
                                DEFAULT_BEST_PRICE_MIN_DISTANCE_FROM_AVG,
                            )
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=50,
                            step=1,
                            mode=NumberSelectorMode.SLIDER,
                        ),
                    ),
                }
            ),
        )

    async def async_step_peak_price(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Configure peak price period settings."""
        if user_input is not None:
            self._options.update(user_input)
            return self.async_create_entry(title="", data=self._options)

        return self.async_show_form(
            step_id="peak_price",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_PEAK_PRICE_FLEX,
                        default=int(
                            self.config_entry.options.get(
                                CONF_PEAK_PRICE_FLEX,
                                DEFAULT_PEAK_PRICE_FLEX,
                            )
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=-100,
                            max=0,
                            step=1,
                            mode=NumberSelectorMode.SLIDER,
                        ),
                    ),
                    vol.Optional(
                        CONF_PEAK_PRICE_MIN_DISTANCE_FROM_AVG,
                        default=int(
                            self.config_entry.options.get(
                                CONF_PEAK_PRICE_MIN_DISTANCE_FROM_AVG,
                                DEFAULT_PEAK_PRICE_MIN_DISTANCE_FROM_AVG,
                            )
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=50,
                            step=1,
                            mode=NumberSelectorMode.SLIDER,
                        ),
                    ),
                }
            ),
        )
