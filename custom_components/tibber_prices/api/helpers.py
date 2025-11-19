"""Helper functions for API response processing."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.const import __version__ as ha_version

if TYPE_CHECKING:
    import aiohttp

    from custom_components.tibber_prices.coordinator.time_service import TimeService

    from .queries import QueryType

from .exceptions import (
    TibberPricesApiClientAuthenticationError,
    TibberPricesApiClientError,
    TibberPricesApiClientPermissionError,
)

_LOGGER = logging.getLogger(__name__)

HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_TOO_MANY_REQUESTS = 429


def verify_response_or_raise(response: aiohttp.ClientResponse) -> None:
    """Verify that the response is valid."""
    if response.status == HTTP_UNAUTHORIZED:
        _LOGGER.error("Tibber API authentication failed - check access token")
        raise TibberPricesApiClientAuthenticationError(TibberPricesApiClientAuthenticationError.INVALID_CREDENTIALS)
    if response.status == HTTP_FORBIDDEN:
        _LOGGER.error("Tibber API access forbidden - insufficient permissions")
        raise TibberPricesApiClientPermissionError(TibberPricesApiClientPermissionError.INSUFFICIENT_PERMISSIONS)
    if response.status == HTTP_TOO_MANY_REQUESTS:
        # Check for Retry-After header that Tibber might send
        retry_after = response.headers.get("Retry-After", "unknown")
        _LOGGER.warning("Tibber API rate limit exceeded - retry after %s seconds", retry_after)
        raise TibberPricesApiClientError(TibberPricesApiClientError.RATE_LIMIT_ERROR.format(retry_after=retry_after))
    if response.status == HTTP_BAD_REQUEST:
        _LOGGER.error("Tibber API rejected request - likely invalid GraphQL query")
        raise TibberPricesApiClientError(
            TibberPricesApiClientError.INVALID_QUERY_ERROR.format(message="Bad request - likely invalid GraphQL query")
        )
    response.raise_for_status()


async def verify_graphql_response(response_json: dict, query_type: QueryType) -> None:
    """Verify the GraphQL response for errors and data completeness, including empty data."""
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

    # Empty data check (for retry logic) - always check, regardless of query_type
    if is_data_empty(response_json["data"], query_type.value):
        _LOGGER.debug("Empty data detected for query_type: %s", query_type)
        raise TibberPricesApiClientError(
            TibberPricesApiClientError.EMPTY_DATA_ERROR.format(query_type=query_type.value)
        )


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

    For rating data:
    - Must have thresholdPercentages
    - Must have non-empty entries for the specific rating type
    """
    _LOGGER.debug("Checking if data is empty for query_type %s", query_type)

    is_empty = False
    try:
        if query_type == "user":
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
            _LOGGER.debug(
                "Viewer check - has_user_id: %s, has_homes: %s, is_empty: %s",
                has_user_id,
                has_homes,
                is_empty,
            )

        elif query_type == "price_info":
            # Check for home aliases (home0, home1, etc.)
            viewer = data.get("viewer", {})
            home_aliases = [key for key in viewer if key.startswith("home") and key[4:].isdigit()]

            if not home_aliases:
                _LOGGER.debug("No home aliases found in price_info response")
                is_empty = True
            else:
                # Check first home for valid data
                _LOGGER.debug("Checking price_info with %d home(s)", len(home_aliases))
                first_home = viewer.get(home_aliases[0])

                if (
                    not first_home
                    or "currentSubscription" not in first_home
                    or first_home["currentSubscription"] is None
                ):
                    _LOGGER.debug("Missing currentSubscription in first home")
                    is_empty = True
                else:
                    subscription = first_home["currentSubscription"]

                    # Check priceInfoRange (192 quarter-hourly intervals)
                    has_historical = (
                        "priceInfoRange" in subscription
                        and subscription["priceInfoRange"] is not None
                        and "edges" in subscription["priceInfoRange"]
                        and subscription["priceInfoRange"]["edges"]
                    )

                    # Check priceInfo for today's data
                    has_price_info = "priceInfo" in subscription and subscription["priceInfo"] is not None
                    has_today = (
                        has_price_info
                        and "today" in subscription["priceInfo"]
                        and subscription["priceInfo"]["today"] is not None
                        and len(subscription["priceInfo"]["today"]) > 0
                    )

                    # Data is empty if we don't have historical data or today's data
                    is_empty = not has_historical or not has_today

                    _LOGGER.debug(
                        "Price info check - priceInfoRange: %s, today: %s, is_empty: %s",
                        bool(has_historical),
                        bool(has_today),
                        is_empty,
                    )

        elif query_type in ["daily", "hourly", "monthly"]:
            # Check for homes existence and non-emptiness before accessing
            if (
                "viewer" not in data
                or "homes" not in data["viewer"]
                or not isinstance(data["viewer"]["homes"], list)
                or len(data["viewer"]["homes"]) == 0
                or "currentSubscription" not in data["viewer"]["homes"][0]
                or data["viewer"]["homes"][0]["currentSubscription"] is None
                or "priceRating" not in data["viewer"]["homes"][0]["currentSubscription"]
            ):
                _LOGGER.debug("Missing homes/currentSubscription/priceRating in rating check")
                is_empty = True
            else:
                rating = data["viewer"]["homes"][0]["currentSubscription"]["priceRating"]

                # Check rating entries
                has_entries = (
                    query_type in rating
                    and rating[query_type] is not None
                    and "entries" in rating[query_type]
                    and rating[query_type]["entries"] is not None
                    and len(rating[query_type]["entries"]) > 0
                )

                is_empty = not has_entries
                _LOGGER.debug(
                    "%s rating check - entries count: %d, is_empty: %s",
                    query_type,
                    len(rating[query_type]["entries"]) if has_entries else 0,
                    is_empty,
                )
        else:
            _LOGGER.debug("Unknown query type %s, treating as non-empty", query_type)
            is_empty = False
    except (KeyError, IndexError, TypeError) as error:
        _LOGGER.debug("Error checking data emptiness: %s", error)
        is_empty = True

    return is_empty


def prepare_headers(access_token: str, version: str) -> dict[str, str]:
    """Prepare headers for API request."""
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "User-Agent": f"HomeAssistant/{ha_version} tibber_prices/{version}",
    }


def flatten_price_info(subscription: dict, currency: str | None = None, *, time: TimeService) -> dict:
    """
    Transform and flatten priceInfo from full API data structure.

    Now handles priceInfoRange (192 quarter-hourly intervals) separately from
    priceInfo (today and tomorrow data). Currency is stored as a separate attribute.
    """
    price_info = subscription.get("priceInfo", {})
    price_info_range = subscription.get("priceInfoRange", {})

    # Get today and yesterday dates using TimeService
    today_local = time.now().date()
    yesterday_local = today_local - timedelta(days=1)
    _LOGGER.debug("Processing data for yesterday's date: %s", yesterday_local)

    # Transform priceInfoRange edges data (extract yesterday's quarter-hourly prices)
    yesterday_prices = []
    if "edges" in price_info_range:
        edges = price_info_range["edges"]

        for edge in edges:
            if "node" not in edge:
                _LOGGER.debug("Skipping edge without node: %s", edge)
                continue

            price_data = edge["node"]
            # Parse timestamp using TimeService for proper timezone handling
            starts_at = time.get_interval_time(price_data)
            if starts_at is None:
                _LOGGER.debug("Could not parse timestamp: %s", price_data["startsAt"])
                continue

            price_date = starts_at.date()

            # Only include prices from yesterday
            if price_date == yesterday_local:
                yesterday_prices.append(price_data)

        _LOGGER.debug("Found %d price entries for yesterday", len(yesterday_prices))

    return {
        "yesterday": yesterday_prices,
        "today": price_info.get("today", []),
        "tomorrow": price_info.get("tomorrow", []),
        "currency": currency,
    }


def flatten_price_rating(subscription: dict) -> dict:
    """Extract and flatten priceRating from subscription, including currency."""
    price_rating = subscription.get("priceRating", {})

    def extract_entries_and_currency(rating: dict) -> tuple[list, str | None]:
        if rating is None:
            return [], None
        return rating.get("entries", []), rating.get("currency")

    hourly_entries, hourly_currency = extract_entries_and_currency(price_rating.get("hourly"))
    daily_entries, daily_currency = extract_entries_and_currency(price_rating.get("daily"))
    monthly_entries, monthly_currency = extract_entries_and_currency(price_rating.get("monthly"))
    # Prefer hourly, then daily, then monthly for top-level currency
    currency = hourly_currency or daily_currency or monthly_currency
    return {
        "hourly": hourly_entries,
        "daily": daily_entries,
        "monthly": monthly_entries,
        "currency": currency,
    }
