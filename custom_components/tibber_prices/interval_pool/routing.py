"""
Routing Module - API endpoint selection for price intervals.

This module handles intelligent routing between different Tibber API endpoints:

- PRICE_INFO: Recent data (from "day before yesterday midnight" onwards)
- PRICE_INFO_RANGE: Historical data (before "day before yesterday midnight")
- Automatic splitting and merging when range spans the boundary

CRITICAL: Uses REAL TIME (dt_utils.now()) for API boundary calculation,
NOT TimeService.now() which may be shifted for internal simulation.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from custom_components.tibber_prices.api.exceptions import TibberPricesApiClientError
from homeassistant.util import dt as dt_utils

if TYPE_CHECKING:
    from datetime import datetime

    from custom_components.tibber_prices.api.client import TibberPricesApiClient

_LOGGER = logging.getLogger(__name__)
_LOGGER_DETAILS = logging.getLogger(__name__ + ".details")


async def get_price_intervals_for_range(
    api_client: TibberPricesApiClient,
    home_id: str,
    user_data: dict[str, Any],
    start_time: datetime,
    end_time: datetime,
) -> list[dict[str, Any]]:
    """
    Get price intervals for a specific time range with automatic routing.

    Automatically routes to the correct API endpoint based on the time range:
    - PRICE_INFO_RANGE: For intervals exclusively before "day before yesterday midnight" (real time)
    - PRICE_INFO: For intervals from "day before yesterday midnight" onwards
    - Both: If range spans across the boundary, splits the request

    CRITICAL: Uses REAL TIME (dt_utils.now()) for API boundary calculation,
    NOT TimeService.now() which may be shifted for internal simulation.
    This ensures predictable API responses.

    CACHING STRATEGY: Returns ALL intervals from API response, NOT filtered.
    The caller (pool.py) will cache everything and then filter to user request.
    This maximizes cache efficiency - one API call can populate cache for
    multiple subsequent queries.

    Args:
        api_client: TibberPricesApiClient instance for API calls.
        home_id: Home ID to fetch price data for.
        user_data: User data dict containing home metadata (including timezone).
        start_time: Start of the range (inclusive, timezone-aware).
        end_time: End of the range (exclusive, timezone-aware).

    Returns:
        List of ALL price interval dicts from API (unfiltered).
        - PRICE_INFO: Returns ~384 intervals (day-before-yesterday to tomorrow)
        - PRICE_INFO_RANGE: Returns intervals for requested historical range
        - Both: Returns all intervals from both endpoints

    Raises:
        TibberPricesApiClientError: If arguments invalid or requests fail.

    """
    if not user_data:
        msg = "User data required for timezone-aware price fetching - fetch user data first"
        raise TibberPricesApiClientError(msg)

    if not home_id:
        msg = "Home ID is required"
        raise TibberPricesApiClientError(msg)

    if start_time >= end_time:
        msg = f"Invalid time range: start_time ({start_time}) must be before end_time ({end_time})"
        raise TibberPricesApiClientError(msg)

    # Calculate boundary: day before yesterday midnight (REAL TIME, not TimeService)
    boundary = _calculate_boundary(api_client, user_data, home_id)

    _LOGGER_DETAILS.debug(
        "Routing price interval request for home %s: range %s to %s, boundary %s",
        home_id,
        start_time,
        end_time,
        boundary,
    )

    # Route based on time range
    if end_time <= boundary:
        # Entire range is historical (before day before yesterday) → use PRICE_INFO_RANGE
        _LOGGER_DETAILS.debug("Range is fully historical, using PRICE_INFO_RANGE")
        result = await api_client.async_get_price_info_range(
            home_id=home_id,
            user_data=user_data,
            start_time=start_time,
            end_time=end_time,
        )
        return result["price_info"]

    if start_time >= boundary:
        # Entire range is recent (from day before yesterday onwards) → use PRICE_INFO
        _LOGGER_DETAILS.debug("Range is fully recent, using PRICE_INFO")
        result = await api_client.async_get_price_info(home_id, user_data)

        # Return ALL intervals (unfiltered) for maximum cache efficiency
        # Pool will cache everything, then filter to user request
        return result["price_info"]

    # Range spans boundary → split request
    _LOGGER_DETAILS.debug("Range spans boundary, splitting request")

    # Fetch historical part (start_time to boundary)
    historical_result = await api_client.async_get_price_info_range(
        home_id=home_id,
        user_data=user_data,
        start_time=start_time,
        end_time=boundary,
    )

    # Fetch recent part (boundary onwards)
    recent_result = await api_client.async_get_price_info(home_id, user_data)

    # Return ALL intervals (unfiltered) for maximum cache efficiency
    # Pool will cache everything, then filter to user request
    return historical_result["price_info"] + recent_result["price_info"]


def _calculate_boundary(
    api_client: TibberPricesApiClient,
    user_data: dict[str, Any],
    home_id: str,
) -> datetime:
    """
    Calculate the API boundary (day before yesterday midnight).

    Uses the API client's helper method to extract timezone and calculate boundary.

    Args:
        api_client: TibberPricesApiClient instance.
        user_data: User data dict containing home metadata.
        home_id: Home ID to get timezone for.

    Returns:
        Timezone-aware datetime for day before yesterday midnight.

    """
    # Extract timezone for this home
    home_timezones = api_client._extract_home_timezones(user_data)  # noqa: SLF001
    home_tz = home_timezones.get(home_id)

    # Calculate boundary using API client's method
    return api_client._calculate_day_before_yesterday_midnight(home_tz)  # noqa: SLF001


def _parse_timestamp(timestamp_str: str) -> datetime:
    """
    Parse ISO timestamp string to timezone-aware datetime.

    Args:
        timestamp_str: ISO format timestamp string.

    Returns:
        Timezone-aware datetime object.

    Raises:
        ValueError: If timestamp string cannot be parsed.

    """
    result = dt_utils.parse_datetime(timestamp_str)
    if result is None:
        msg = f"Failed to parse timestamp: {timestamp_str}"
        raise ValueError(msg)
    return result
