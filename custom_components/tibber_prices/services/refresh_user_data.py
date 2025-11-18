"""
User data refresh service handler.

This module implements the `refresh_user_data` service, which forces a refresh
of user profile and home information from the Tibber API.

Features:
- Force refresh of cached user data
- Bypass 24h cache TTL
- Return updated user profile and homes
- Error handling for API failures

Service: tibber_prices.refresh_user_data
Response: JSON with refresh status and updated data

"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

import voluptuous as vol

from custom_components.tibber_prices.api import (
    TibberPricesApiClientAuthenticationError,
    TibberPricesApiClientCommunicationError,
    TibberPricesApiClientError,
)
from homeassistant.exceptions import ServiceValidationError

from .helpers import get_entry_and_data

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall

# Service constants
REFRESH_USER_DATA_SERVICE_NAME: Final = "refresh_user_data"
ATTR_ENTRY_ID: Final = "entry_id"

# Service schema
REFRESH_USER_DATA_SERVICE_SCHEMA: Final = vol.Schema(
    {
        vol.Required(ATTR_ENTRY_ID): str,
    }
)


async def handle_refresh_user_data(call: ServiceCall) -> dict[str, Any]:
    """
    Refresh user data for a specific config entry.

    Forces a refresh of user profile and home information from Tibber API,
    bypassing the 24-hour cache TTL. Returns updated information or error details.

    See services.yaml for detailed parameter documentation.

    Args:
        call: Service call with parameters

    Returns:
        Dictionary with refresh status and updated data

    Raises:
        ServiceValidationError: If entry_id is missing or invalid

    """
    entry_id = call.data.get(ATTR_ENTRY_ID)
    hass = call.hass

    if not entry_id:
        return {
            "success": False,
            "message": "Entry ID is required",
        }

    # Get the entry and coordinator
    try:
        _, coordinator, _ = get_entry_and_data(hass, entry_id)
    except ServiceValidationError as ex:
        return {
            "success": False,
            "message": f"Invalid entry ID: {ex}",
        }

    # Force refresh user data using the public method
    try:
        updated = await coordinator.refresh_user_data()
    except (
        TibberPricesApiClientAuthenticationError,
        TibberPricesApiClientCommunicationError,
        TibberPricesApiClientError,
    ) as ex:
        return {
            "success": False,
            "message": f"API error refreshing user data: {ex!s}",
        }
    else:
        if updated:
            user_profile = coordinator.get_user_profile()
            homes = coordinator.get_user_homes()

            return {
                "success": True,
                "message": "User data refreshed successfully",
                "user_profile": user_profile,
                "homes_count": len(homes),
                "homes": homes,
                "last_updated": user_profile.get("last_updated"),
            }
        return {
            "success": False,
            "message": "User data was already up to date",
        }
