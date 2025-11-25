"""Main config flow for tibber_prices integration."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

import voluptuous as vol

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
from custom_components.tibber_prices.const import DOMAIN, LOGGER, get_translation
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigSubentryFlow


class TibberPricesConfigFlowHandler(ConfigFlow, domain=DOMAIN):
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
        """Handle a flow initialized by the user. Choose account or enter new token."""
        # Get existing accounts
        existing_entries = self.hass.config_entries.async_entries(DOMAIN)

        # If there are existing accounts, offer choice
        if existing_entries and user_input is None:
            return await self.async_step_account_choice()

        # Otherwise, go directly to token input
        return await self.async_step_new_token(user_input)

    async def async_step_account_choice(
        self,
        user_input: dict | None = None,
    ) -> ConfigFlowResult:
        """Let user choose between existing account or new token."""
        if user_input is not None:
            choice = user_input["account_choice"]

            if choice == "new_token":
                return await self.async_step_new_token()

            # User selected an existing account - copy its token
            selected_entry_id = choice
            selected_entry = next(
                (
                    entry
                    for entry in self.hass.config_entries.async_entries(DOMAIN)
                    if entry.entry_id == selected_entry_id
                ),
                None,
            )

            if not selected_entry:
                return self.async_abort(reason="unknown")

            # Copy token from selected entry and proceed
            access_token = selected_entry.data.get(CONF_ACCESS_TOKEN)
            if not access_token:
                return self.async_abort(reason="unknown")

            return await self.async_step_new_token({CONF_ACCESS_TOKEN: access_token})

        # Build options: unique user accounts (grouped by user_id) + "New Token" option
        existing_entries = self.hass.config_entries.async_entries(DOMAIN)

        # Group entries by user_id to show unique accounts
        # Minimum parts in unique_id format: user_id_home_id
        min_unique_id_parts = 2

        seen_users = {}
        for entry in existing_entries:
            # Extract user_id from unique_id (format: user_id_home_id or user_id_home_id_sub/hist_...)
            unique_id = entry.unique_id
            if unique_id:
                # Split by underscore and take first part as user_id
                parts = unique_id.split("_")
                if len(parts) >= min_unique_id_parts:
                    user_id = parts[0]
                    if user_id not in seen_users:
                        seen_users[user_id] = entry

        # Build dropdown options from unique user accounts
        account_options = [
            SelectOptionDict(
                value=entry.entry_id,
                label=f"{entry.title} ({entry.data.get('user_login', 'N/A')})",
            )
            for entry in seen_users.values()
        ]
        # Add "new_token" option with translated label
        new_token_label = (
            get_translation(
                ["selector", "account_choice", "options", "new_token"],
                self.hass.config.language,
            )
            or "Add new Tibber account API token"
        )
        account_options.append(
            SelectOptionDict(
                value="new_token",
                label=new_token_label,
            )
        )

        return self.async_show_form(
            step_id="account_choice",
            data_schema=vol.Schema(
                {
                    vol.Required("account_choice"): SelectSelector(
                        SelectSelectorConfig(
                            options=account_options,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_new_token(
        self,
        user_input: dict | None = None,
    ) -> ConfigFlowResult:
        """Handle token input (new or copied from existing account)."""
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

                # Store viewer data in the flow for use in the next step
                self._viewer = viewer
                self._access_token = user_input[CONF_ACCESS_TOKEN]
                self._user_name = user_name
                self._user_login = user_login
                self._user_id = user_id

                # Move to home selection step
                return await self.async_step_select_home()

        return self.async_show_form(
            step_id="new_token",
            data_schema=get_user_schema((user_input or {}).get(CONF_ACCESS_TOKEN)),
            errors=_errors,
        )

    async def async_step_select_home(self, user_input: dict | None = None) -> ConfigFlowResult:  # noqa: PLR0911
        """Handle home selection during initial setup."""
        homes = self._viewer.get("homes", []) if self._viewer else []

        if not homes:
            return self.async_abort(reason="unknown")

        # Filter out already configured homes
        configured_home_ids = {
            entry.data.get("home_id")
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if entry.data.get("home_id")
        }
        available_homes = [home for home in homes if home["id"] not in configured_home_ids]

        # If no homes available, abort
        if not available_homes:
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            selected_home_id = user_input["home_id"]
            selected_home = next((home for home in available_homes if home["id"] == selected_home_id), None)

            if not selected_home:
                return self.async_abort(reason="unknown")

            # Validate that home has an active or future subscription
            subscription_status = self._get_subscription_status(selected_home)

            if subscription_status == "none":
                return self.async_show_form(
                    step_id="select_home",
                    data_schema=get_select_home_schema(
                        [
                            SelectOptionDict(
                                value=home["id"],
                                label=self._get_home_title_with_status(home),
                            )
                            for home in available_homes
                        ]
                    ),
                    errors={"home_id": "no_active_subscription"},
                )

            if subscription_status == "expired":
                return self.async_show_form(
                    step_id="select_home",
                    data_schema=get_select_home_schema(
                        [
                            SelectOptionDict(
                                value=home["id"],
                                label=self._get_home_title_with_status(home),
                            )
                            for home in available_homes
                        ]
                    ),
                    errors={"home_id": "subscription_expired"},
                )

            # Set unique_id to user_id + home_id combination
            # This allows multiple homes per user account (single-home architecture)
            unique_id = f"{self._user_id}_{selected_home_id}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            # Note: This check is now redundant since we filter available_homes upfront,
            # but kept as defensive programming in case of race conditions
            for entry in self.hass.config_entries.async_entries(DOMAIN):
                if entry.data.get("home_id") == selected_home_id:
                    return self.async_show_form(
                        step_id="select_home",
                        data_schema=get_select_home_schema(
                            [
                                SelectOptionDict(
                                    value=home["id"],
                                    label=self._get_home_title(home),
                                )
                                for home in available_homes
                            ]
                        ),
                        errors={"home_id": "home_already_configured"},
                    )

            data = {
                CONF_ACCESS_TOKEN: self._access_token or "",
                "home_id": selected_home_id,
                "home_data": selected_home,
                "homes": homes,
                "user_login": self._user_login or "N/A",
            }

            # Generate entry title from home address (not appNickname)
            entry_title = self._get_entry_title(selected_home)

            return self.async_create_entry(
                title=entry_title,
                data=data,
                description=f"{self._user_login} ({self._user_id})",
            )

        home_options = [
            SelectOptionDict(
                value=home["id"],
                label=self._get_home_title_with_status(home),
            )
            for home in available_homes
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
    def _get_subscription_status(home: dict) -> str:
        """
        Check subscription status of home.

        Returns:
            - "active": Subscription is currently active
            - "future": Subscription exists but starts in the future (validFrom > now)
            - "expired": Subscription exists but has ended (validTo < now)
            - "none": No subscription exists

        """
        subscription = home.get("currentSubscription")

        if subscription is None or subscription.get("status") is None:
            return "none"

        # Check validTo (contract end date)
        valid_to = subscription.get("validTo")
        if valid_to:
            try:
                valid_to_dt = datetime.fromisoformat(valid_to)
                if valid_to_dt < datetime.now(valid_to_dt.tzinfo):
                    return "expired"
            except (ValueError, AttributeError):
                pass  # If parsing fails, continue with other checks

        # Check validFrom (contract start date)
        valid_from = subscription.get("validFrom")
        if valid_from:
            try:
                valid_from_dt = datetime.fromisoformat(valid_from)
                if valid_from_dt > datetime.now(valid_from_dt.tzinfo):
                    return "future"
            except (ValueError, AttributeError):
                pass  # If parsing fails, assume active

        return "active"

    def _get_home_title_with_status(self, home: dict) -> str:
        """Generate a user-friendly title for a home with subscription status."""
        base_title = self._get_home_title(home)
        status = self._get_subscription_status(home)

        if status == "none":
            return f"{base_title} ⚠️ (No active contract)"
        if status == "expired":
            return f"{base_title} ⚠️ (Contract expired)"
        if status == "future":
            return f"{base_title} ⚠️ (Contract starts soon)"

        return base_title

    @staticmethod
    def _format_city_name(city: str) -> str:
        """
        Format city name to title case.

        Converts 'MÜNCHEN' to 'München', handles multi-word cities like
        'BAD TÖLZ' -> 'Bad Tölz', and hyphenated cities like
        'GARMISCH-PARTENKIRCHEN' -> 'Garmisch-Partenkirchen'.
        """
        if not city:
            return city

        # Split by space and hyphen while preserving delimiters
        words = []
        current_word = ""

        for char in city:
            if char in (" ", "-"):
                if current_word:
                    words.append(current_word)
                words.append(char)  # Preserve delimiter
                current_word = ""
            else:
                current_word += char

        if current_word:  # Add last word
            words.append(current_word)

        # Capitalize first letter of each word (not delimiters)
        formatted_words = []
        for word in words:
            if word in (" ", "-"):
                formatted_words.append(word)
            else:
                # Capitalize first letter, lowercase rest
                formatted_words.append(word.capitalize())

        return "".join(formatted_words)

    @staticmethod
    def _get_entry_title(home: dict) -> str:
        """
        Generate entry title from address (for config entry title).

        Uses 'address1, City' format, e.g. 'Pählstraße 6B, München'.
        Does NOT use appNickname (that's for _get_home_title).
        """
        address = home.get("address", {})

        if not address:
            # Fallback to home ID if no address
            return home.get("id", "Unknown Home")

        parts = []

        # Always prefer address1
        address1 = address.get("address1")
        if address1 and address1.strip():
            parts.append(address1.strip())

        # Format city name (convert MÜNCHEN -> München)
        city = address.get("city")
        if city and city.strip():
            formatted_city = TibberPricesConfigFlowHandler._format_city_name(city.strip())
            parts.append(formatted_city)

        if parts:
            return ", ".join(parts)

        # Final fallback
        return home.get("id", "Unknown Home")

    @staticmethod
    def _get_home_title(home: dict) -> str:
        """
        Generate a user-friendly title for a home (for dropdown display).

        Prefers appNickname, falls back to address.
        """
        title = home.get("appNickname")
        if title and title.strip():
            return title.strip()

        address = home.get("address", {})
        if address:
            parts = []
            if address.get("address1"):
                parts.append(address["address1"])
            if address.get("city"):
                # Format city for display too
                city = address["city"]
                formatted_city = TibberPricesConfigFlowHandler._format_city_name(city)
                parts.append(formatted_city)
            if parts:
                return ", ".join(parts)

        return home.get("id", "Unknown Home")
