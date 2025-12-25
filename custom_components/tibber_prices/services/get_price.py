"""
Service handler for get_price service.

This service provides direct access to the interval pool for testing and development
purposes. It uses intelligent caching to minimize API calls by fetching only missing
intervals from the API.

Functions:
    handle_get_price: Service handler for fetching price data

Used for:
    - Testing interval pool caching logic
    - Development and debugging of historical data queries
    - Verifying gap detection and cache hit/miss behavior

"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import voluptuous as vol

from custom_components.tibber_prices.const import DOMAIN
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_utils

from .helpers import get_entry_and_data

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse

_LOGGER = logging.getLogger(__name__)

GET_PRICE_SERVICE_NAME = "get_price"

GET_PRICE_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("entry_id"): cv.string,
        vol.Required("start_time"): cv.datetime,
        vol.Required("end_time"): cv.datetime,
    }
)


def _raise_user_data_error() -> None:
    """Raise user data not available error."""
    msg = "User data not available"
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="user_data_not_available",
    ) from ValueError(msg)


async def handle_get_price(call: ServiceCall) -> ServiceResponse:
    """
    Handle get_price service call.

    Fetches price data for a specified time range using the interval pool.
    The pool intelligently caches intervals and only fetches missing data from the API.

    Args:
        call: Service call with entry_id, start_time, and end_time

    Returns:
        Dict with price data and metadata

    Raises:
        ServiceValidationError: If arguments invalid or request fails

    """
    hass: HomeAssistant = call.hass
    entry_id: str = call.data["entry_id"]
    start_time: datetime = call.data["start_time"]
    end_time: datetime = call.data["end_time"]

    # Validate and get entry data
    entry, coordinator, _data = get_entry_and_data(hass, entry_id)

    # Get home_id from entry
    home_id = entry.data.get("home_id")
    if not home_id:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="missing_home_id",
        )

    # Get API client from coordinator
    api_client = coordinator.api

    # Get user data (needed for timezone) - coordinator doesn't expose this publicly yet
    user_data = coordinator._cached_user_data  # noqa: SLF001

    if not user_data:
        _raise_user_data_error()

    # Extract home timezone from user_data
    home_timezone = None
    if user_data and "viewer" in user_data:
        for home in user_data["viewer"].get("homes", []):
            if home.get("id") == home_id:
                home_timezone = home.get("timeZone")
                break

    if not home_timezone:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="timezone_not_found",
        )

    # Ensure times are timezone-aware using HOME timezone (not HA server timezone!)
    # CRITICAL TWO-STEP PROCESS:
    # 1. GUI gives us naive datetime in HA SERVER timezone → localize to HA timezone
    # 2. Convert from HA timezone to HOME timezone (Tibber home location)
    home_tz = ZoneInfo(home_timezone)

    if start_time.tzinfo is None:
        # Step 1: Localize to HA server timezone
        start_time = dt_utils.as_local(start_time)
    # Step 2: Convert to home timezone
    start_time = start_time.astimezone(home_tz)

    if end_time.tzinfo is None:
        # Step 1: Localize to HA server timezone
        end_time = dt_utils.as_local(end_time)
    # Step 2: Convert to home timezone
    end_time = end_time.astimezone(home_tz)

    _LOGGER.info(
        "get_price service called: entry_id=%s, home_id=%s, range=%s to %s",
        entry_id,
        home_id,
        start_time,
        end_time,
    )

    try:
        # Get interval pool from entry runtime_data (one pool per config entry)
        pool = entry.runtime_data.interval_pool

        # Call the interval pool to get intervals (with intelligent caching)
        # Single-home architecture: pool knows its home_id, no parameter needed
        price_info, _api_called = await pool.get_intervals(
            api_client=api_client,
            user_data=user_data,
            start_time=start_time,
            end_time=end_time,
        )
        # Note: We ignore api_called flag here - service always returns requested data
        # regardless of whether it came from cache or was fetched fresh from API

    except Exception as error:
        _LOGGER.exception("Error fetching price data")
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="price_fetch_failed",
        ) from error

    else:
        # Add metadata to response
        response = {
            "home_id": home_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "interval_count": len(price_info),
            "price_info": price_info,
        }

        _LOGGER.info(
            "get_price service completed: fetched %d intervals",
            len(price_info),
        )

        return response
