"""Validation functions for Tibber Prices config flow."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.tibber_prices.api import (
    TibberPricesApiClient,
    TibberPricesApiClientAuthenticationError,
    TibberPricesApiClientCommunicationError,
    TibberPricesApiClientError,
)
from custom_components.tibber_prices.const import DOMAIN
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.loader import async_get_integration

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# Constants for validation
MAX_FLEX_PERCENTAGE = 100.0
MAX_MIN_PERIODS = 10  # Arbitrary upper limit for sanity


class TibberPricesInvalidAuthError(HomeAssistantError):
    """Error to indicate invalid authentication."""


class TibberPricesCannotConnectError(HomeAssistantError):
    """Error to indicate we cannot connect."""


async def validate_api_token(hass: HomeAssistant, token: str) -> dict:
    """
    Validate Tibber API token.

    Args:
        hass: Home Assistant instance
        token: Tibber API access token

    Returns:
        dict with viewer data on success

    Raises:
        TibberPricesInvalidAuthError: Invalid token
        TibberPricesCannotConnectError: API connection failed

    """
    try:
        integration = await async_get_integration(hass, DOMAIN)
        client = TibberPricesApiClient(
            access_token=token,
            session=async_create_clientsession(hass),
            version=str(integration.version) if integration.version else "unknown",
        )
        result = await client.async_get_viewer_details()
        return result["viewer"]
    except TibberPricesApiClientAuthenticationError as exception:
        raise TibberPricesInvalidAuthError from exception
    except TibberPricesApiClientCommunicationError as exception:
        raise TibberPricesCannotConnectError from exception
    except TibberPricesApiClientError as exception:
        raise TibberPricesCannotConnectError from exception


def validate_threshold_range(value: float, min_val: float, max_val: float) -> bool:
    """
    Validate threshold is within allowed range.

    Args:
        value: Value to validate
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        True if value is within range

    """
    return min_val <= value <= max_val


def validate_period_length(minutes: int) -> bool:
    """
    Validate period length is multiple of 15 minutes.

    Args:
        minutes: Period length in minutes

    Returns:
        True if length is valid

    """
    return minutes > 0 and minutes % 15 == 0


def validate_flex_percentage(flex: float) -> bool:
    """
    Validate flexibility percentage is within bounds.

    Args:
        flex: Flexibility percentage

    Returns:
        True if percentage is valid

    """
    return 0.0 <= flex <= MAX_FLEX_PERCENTAGE


def validate_min_periods(count: int) -> bool:
    """
    Validate minimum periods count is reasonable.

    Args:
        count: Number of minimum periods

    Returns:
        True if count is valid

    """
    return count > 0 and count <= MAX_MIN_PERIODS
