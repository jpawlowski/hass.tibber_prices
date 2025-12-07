"""Helper functions for API response processing."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.const import __version__ as ha_version

if TYPE_CHECKING:
    import aiohttp

    from .queries import TibberPricesQueryType

from .exceptions import (
    TibberPricesApiClientAuthenticationError,
    TibberPricesApiClientError,
    TibberPricesApiClientPermissionError,
)

_LOGGER = logging.getLogger(__name__)
_LOGGER_DETAILS = logging.getLogger(__name__ + ".details")

HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_TOO_MANY_REQUESTS = 429
HTTP_INTERNAL_SERVER_ERROR = 500
HTTP_BAD_GATEWAY = 502
HTTP_SERVICE_UNAVAILABLE = 503
HTTP_GATEWAY_TIMEOUT = 504


def verify_response_or_raise(response: aiohttp.ClientResponse) -> None:
    """
    Verify HTTP response and map to appropriate exceptions.

    Error Mapping:
    - 401 Unauthorized → AuthenticationError (non-retryable)
    - 403 Forbidden → PermissionError (non-retryable)
    - 429 Rate Limit → ApiClientError with retry support
    - 400 Bad Request → ApiClientError (non-retryable, invalid query)
    - 5xx Server Errors → CommunicationError (retryable)
    - Other errors → Let aiohttp.raise_for_status() handle
    """
    # Authentication failures - non-retryable
    if response.status == HTTP_UNAUTHORIZED:
        _LOGGER.error("Tibber API authentication failed - check access token")
        raise TibberPricesApiClientAuthenticationError(TibberPricesApiClientAuthenticationError.INVALID_CREDENTIALS)

    # Permission denied - non-retryable
    if response.status == HTTP_FORBIDDEN:
        _LOGGER.error("Tibber API access forbidden - insufficient permissions")
        raise TibberPricesApiClientPermissionError(TibberPricesApiClientPermissionError.INSUFFICIENT_PERMISSIONS)

    # Rate limiting - retryable with explicit delay
    if response.status == HTTP_TOO_MANY_REQUESTS:
        # Check for Retry-After header that Tibber might send
        retry_after = response.headers.get("Retry-After", "unknown")
        _LOGGER.warning("Tibber API rate limit exceeded - retry after %s seconds", retry_after)
        raise TibberPricesApiClientError(TibberPricesApiClientError.RATE_LIMIT_ERROR.format(retry_after=retry_after))

    # Bad request - non-retryable (invalid query)
    if response.status == HTTP_BAD_REQUEST:
        _LOGGER.error("Tibber API rejected request - likely invalid GraphQL query")
        raise TibberPricesApiClientError(
            TibberPricesApiClientError.INVALID_QUERY_ERROR.format(message="Bad request - likely invalid GraphQL query")
        )

    # Server errors 5xx - retryable (temporary server issues)
    if response.status in (
        HTTP_INTERNAL_SERVER_ERROR,
        HTTP_BAD_GATEWAY,
        HTTP_SERVICE_UNAVAILABLE,
        HTTP_GATEWAY_TIMEOUT,
    ):
        _LOGGER.warning(
            "Tibber API server error %d - temporary issue, will retry",
            response.status,
        )
        # Let this be caught as aiohttp.ClientResponseError in _api_wrapper
        # where it's converted to CommunicationError with retry logic
        response.raise_for_status()

    # All other HTTP errors - let aiohttp handle
    response.raise_for_status()


async def verify_graphql_response(response_json: dict, query_type: TibberPricesQueryType) -> None:
    """
    Verify GraphQL response and map error codes to appropriate exceptions.

    GraphQL Error Code Mapping:
    - UNAUTHENTICATED → AuthenticationError (triggers reauth flow)
    - FORBIDDEN → PermissionError (non-retryable)
    - RATE_LIMITED/TOO_MANY_REQUESTS → ApiClientError (retryable)
    - VALIDATION_ERROR/GRAPHQL_VALIDATION_FAILED → ApiClientError (non-retryable)
    - Other codes → Generic ApiClientError (with code in message)
    - Empty data → ApiClientError (non-retryable, API has no data)
    """
    if "errors" in response_json:
        errors = response_json["errors"]
        if not errors:
            _LOGGER.error("Tibber API returned empty errors array")
            raise TibberPricesApiClientError(TibberPricesApiClientError.UNKNOWN_ERROR)

        error = errors[0]  # Take first error
        if not isinstance(error, dict):
            _LOGGER.error("Tibber API returned malformed error: %s", error)
            raise TibberPricesApiClientError(TibberPricesApiClientError.MALFORMED_ERROR.format(error=error))

        message = error.get("message", "Unknown error")
        extensions = error.get("extensions", {})
        error_code = extensions.get("code")

        # Handle specific Tibber API error codes
        if error_code == "UNAUTHENTICATED":
            _LOGGER.error("Tibber API authentication error: %s", message)
            raise TibberPricesApiClientAuthenticationError(TibberPricesApiClientAuthenticationError.INVALID_CREDENTIALS)
        if error_code == "FORBIDDEN":
            _LOGGER.error("Tibber API permission error: %s", message)
            raise TibberPricesApiClientPermissionError(TibberPricesApiClientPermissionError.INSUFFICIENT_PERMISSIONS)
        if error_code in ["RATE_LIMITED", "TOO_MANY_REQUESTS"]:
            # Some GraphQL APIs return rate limit info in extensions
            retry_after = extensions.get("retryAfter", "unknown")
            _LOGGER.warning(
                "Tibber API rate limited via GraphQL: %s (retry after %s)",
                message,
                retry_after,
            )
            raise TibberPricesApiClientError(
                TibberPricesApiClientError.RATE_LIMIT_ERROR.format(retry_after=retry_after)
            )
        if error_code in ["VALIDATION_ERROR", "GRAPHQL_VALIDATION_FAILED"]:
            _LOGGER.error("Tibber API validation error: %s", message)
            raise TibberPricesApiClientError(TibberPricesApiClientError.INVALID_QUERY_ERROR.format(message=message))

        _LOGGER.error("Tibber API GraphQL error (code: %s): %s", error_code or "unknown", message)
        raise TibberPricesApiClientError(TibberPricesApiClientError.GRAPHQL_ERROR.format(message=message))

    if "data" not in response_json or response_json["data"] is None:
        _LOGGER.error("Tibber API response missing data object")
        raise TibberPricesApiClientError(
            TibberPricesApiClientError.GRAPHQL_ERROR.format(message="Response missing data object")
        )

    # Empty data check - validate response completeness
    # This is NOT a retryable error - API simply has no data for the requested range
    if is_data_empty(response_json["data"], query_type.value):
        _LOGGER_DETAILS.debug("Empty data detected for query_type: %s - API has no data available", query_type)
        raise TibberPricesApiClientError(
            TibberPricesApiClientError.EMPTY_DATA_ERROR.format(query_type=query_type.value)
        )


def _check_user_data_empty(data: dict) -> bool:
    """Check if user data is empty or incomplete."""
    has_user_id = (
        "viewer" in data
        and isinstance(data["viewer"], dict)
        and "userId" in data["viewer"]
        and data["viewer"]["userId"] is not None
    )
    has_homes = (
        "viewer" in data
        and isinstance(data["viewer"], dict)
        and "homes" in data["viewer"]
        and isinstance(data["viewer"]["homes"], list)
        and len(data["viewer"]["homes"]) > 0
    )
    is_empty = not has_user_id or not has_homes
    _LOGGER_DETAILS.debug(
        "Viewer check - has_user_id: %s, has_homes: %s, is_empty: %s",
        has_user_id,
        has_homes,
        is_empty,
    )
    return is_empty


def _check_price_info_empty(data: dict) -> bool:
    """
    Check if price_info data is empty or incomplete.

    Note: Missing currentSubscription is VALID (home without active contract).
    Only check for structural issues, not missing data that legitimately might not exist.
    """
    viewer = data.get("viewer", {})
    home_data = viewer.get("home")

    if not home_data:
        _LOGGER_DETAILS.debug("No home data found in price_info response")
        return True

    _LOGGER_DETAILS.debug("Checking price_info for single home")

    # Missing currentSubscription is VALID - home has no active contract
    # This is not an "empty data" error, it's a legitimate state
    if "currentSubscription" not in home_data or home_data["currentSubscription"] is None:
        _LOGGER_DETAILS.debug("No currentSubscription - home has no active contract (valid state)")
        return False  # NOT empty - this is expected for homes without subscription

    subscription = home_data["currentSubscription"]

    # Check priceInfoRange (yesterday data - optional, may not be available)
    has_yesterday = (
        "priceInfoRange" in subscription
        and subscription["priceInfoRange"] is not None
        and "edges" in subscription["priceInfoRange"]
        and subscription["priceInfoRange"]["edges"]
    )

    # Check priceInfo for today's data (required if subscription exists)
    has_price_info = "priceInfo" in subscription and subscription["priceInfo"] is not None
    has_today = (
        has_price_info
        and "today" in subscription["priceInfo"]
        and subscription["priceInfo"]["today"] is not None
        and len(subscription["priceInfo"]["today"]) > 0
    )

    # Only require today's data - yesterday is optional
    # If subscription exists but no today data, that's a structural problem
    is_empty = not has_today

    _LOGGER_DETAILS.debug(
        "Price info check - priceInfoRange: %s, today: %s, is_empty: %s",
        bool(has_yesterday),
        bool(has_today),
        is_empty,
    )
    return is_empty


def _check_price_info_range_empty(data: dict) -> bool:
    """
    Check if price_info_range data is empty or incomplete.

    For historical range queries, empty edges array is VALID (no data available
    for that time range, e.g., too old). Only structural problems are errors.
    """
    viewer = data.get("viewer", {})
    home_data = viewer.get("home")

    if not home_data:
        _LOGGER_DETAILS.debug("No home data found in price_info_range response")
        return True

    subscription = home_data.get("currentSubscription")
    if not subscription:
        _LOGGER_DETAILS.debug("Missing currentSubscription in home")
        return True

    # For price_info_range, check if the structure exists
    # Empty edges array is VALID (no data for that time range)
    price_info_range = subscription.get("priceInfoRange")
    if price_info_range is None:
        _LOGGER_DETAILS.debug("Missing priceInfoRange in subscription")
        return True

    if "edges" not in price_info_range:
        _LOGGER_DETAILS.debug("Missing edges key in priceInfoRange")
        return True

    edges = price_info_range["edges"]
    if not isinstance(edges, list):
        _LOGGER_DETAILS.debug("priceInfoRange edges is not a list")
        return True

    # Empty edges is VALID for historical queries (data not available)
    _LOGGER_DETAILS.debug(
        "Price info range check - structure valid, edge_count: %s (empty is OK for old data)",
        len(edges),
    )
    return False  # Structure is valid, even if edges is empty


def is_data_empty(data: dict, query_type: str) -> bool:
    """
    Check if the response data is empty or incomplete.

    For viewer data:
    - Must have userId and homes
    - If either is missing, data is considered empty
    - If homes is empty, data is considered empty
    - If userId is None, data is considered empty

    For price info:
    - Must have range data
    - Must have today data
    - tomorrow can be empty if we have valid historical and today data

    For price info range:
    - Must have priceInfoRange with edges
    Used by interval pool for historical data fetching
    """
    _LOGGER_DETAILS.debug("Checking if data is empty for query_type %s", query_type)

    try:
        if query_type == "user":
            return _check_user_data_empty(data)
        if query_type == "price_info":
            return _check_price_info_empty(data)
        if query_type == "price_info_range":
            return _check_price_info_range_empty(data)

        # Unknown query type
        _LOGGER_DETAILS.debug("Unknown query type %s, treating as non-empty", query_type)
    except (KeyError, IndexError, TypeError) as error:
        _LOGGER_DETAILS.debug("Error checking data emptiness: %s", error)
        return True
    else:
        return False


def prepare_headers(access_token: str, version: str) -> dict[str, str]:
    """Prepare headers for API request."""
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "User-Agent": f"HomeAssistant/{ha_version} tibber_prices/{version}",
    }


def flatten_price_info(subscription: dict) -> list[dict]:
    """
    Transform and flatten priceInfo from full API data structure.

    Returns a flat list of all price intervals ordered as:
    [day_before_yesterday_prices, yesterday_prices, today_prices, tomorrow_prices]

    priceInfoRange fetches 192 quarter-hourly intervals starting from the day before
    yesterday midnight (2 days of historical data), which provides sufficient data
    for calculating trailing 24h averages for all intervals including yesterday.

    Args:
        subscription: The currentSubscription dictionary from API response.

    Returns:
        A flat list containing all price dictionaries (startsAt, total, level).

    """
    price_info_range = subscription.get("priceInfoRange", {})

    # Transform priceInfoRange edges data (extract historical quarter-hourly prices)
    # This contains 192 intervals (2 days) starting from day before yesterday midnight
    historical_prices = []
    if "edges" in price_info_range:
        edges = price_info_range["edges"]

        for edge in edges:
            if "node" not in edge:
                _LOGGER.debug("Skipping edge without node: %s", edge)
                continue
            historical_prices.append(edge["node"])

    # Return all intervals as a single flattened array
    return (
        historical_prices
        + subscription.get("priceInfo", {}).get("today", [])
        + subscription.get("priceInfo", {}).get("tomorrow", [])
    )
