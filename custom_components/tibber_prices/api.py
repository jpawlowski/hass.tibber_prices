"""Tibber API Client."""

from __future__ import annotations

import asyncio
import logging
import socket
from datetime import timedelta
from enum import Enum
from typing import Any

import aiohttp

from homeassistant.const import __version__ as ha_version
from homeassistant.util import dt as dt_util

from .const import VERSION

_LOGGER = logging.getLogger(__name__)

HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_TOO_MANY_REQUESTS = 429


class QueryType(Enum):
    """Types of queries that can be made to the API."""

    PRICE_INFO = "price_info"
    DAILY_RATING = "daily"
    HOURLY_RATING = "hourly"
    MONTHLY_RATING = "monthly"
    USER = "user"


class TibberPricesApiClientError(Exception):
    """Exception to indicate a general API error."""

    UNKNOWN_ERROR = "Unknown GraphQL error"
    MALFORMED_ERROR = "Malformed GraphQL error: {error}"
    GRAPHQL_ERROR = "GraphQL error: {message}"
    EMPTY_DATA_ERROR = "Empty data received for {query_type}"
    GENERIC_ERROR = "Something went wrong! {exception}"
    RATE_LIMIT_ERROR = "Rate limit exceeded. Please wait {retry_after} seconds before retrying"
    INVALID_QUERY_ERROR = "Invalid GraphQL query: {message}"


class TibberPricesApiClientCommunicationError(TibberPricesApiClientError):
    """Exception to indicate a communication error."""

    TIMEOUT_ERROR = "Timeout error fetching information - {exception}"
    CONNECTION_ERROR = "Error fetching information - {exception}"


class TibberPricesApiClientAuthenticationError(TibberPricesApiClientError):
    """Exception to indicate an authentication error."""

    INVALID_CREDENTIALS = "Invalid access token or expired credentials"


class TibberPricesApiClientPermissionError(TibberPricesApiClientError):
    """Exception to indicate insufficient permissions."""

    INSUFFICIENT_PERMISSIONS = "Access forbidden - insufficient permissions for this operation"


def _verify_response_or_raise(response: aiohttp.ClientResponse) -> None:
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


async def _verify_graphql_response(response_json: dict, query_type: QueryType) -> None:
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
            _LOGGER.warning("Tibber API rate limited via GraphQL: %s (retry after %s)", message, retry_after)
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
    if _is_data_empty(response_json["data"], query_type.value):
        _LOGGER.debug("Empty data detected for query_type: %s", query_type)
        raise TibberPricesApiClientError(
            TibberPricesApiClientError.EMPTY_DATA_ERROR.format(query_type=query_type.value)
        )


def _is_data_empty(data: dict, query_type: str) -> bool:
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
                "Viewer check - has_user_id: %s, has_homes: %s, is_empty: %s", has_user_id, has_homes, is_empty
            )

        elif query_type == "price_info":
            # Check for homes existence and non-emptiness before accessing
            if (
                "viewer" not in data
                or "homes" not in data["viewer"]
                or not isinstance(data["viewer"]["homes"], list)
                or len(data["viewer"]["homes"]) == 0
                or "currentSubscription" not in data["viewer"]["homes"][0]
                or data["viewer"]["homes"][0]["currentSubscription"] is None
                or "priceInfo" not in data["viewer"]["homes"][0]["currentSubscription"]
            ):
                _LOGGER.debug("Missing homes/currentSubscription/priceInfo in price_info check")
                is_empty = True
            else:
                price_info = data["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]

                # Check historical data (either range or yesterday)
                has_historical = (
                    "range" in price_info
                    and price_info["range"] is not None
                    and "edges" in price_info["range"]
                    and price_info["range"]["edges"]
                )

                # Check today's data
                has_today = "today" in price_info and price_info["today"] is not None and len(price_info["today"]) > 0

                # Data is empty if we don't have historical data or today's data
                is_empty = not has_historical or not has_today

                _LOGGER.debug(
                    "Price info check - historical data historical: %s, today: %s, is_empty: %s",
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

                # Check threshold percentages
                has_thresholds = (
                    "thresholdPercentages" in rating
                    and rating["thresholdPercentages"] is not None
                    and "low" in rating["thresholdPercentages"]
                    and "high" in rating["thresholdPercentages"]
                )
                if not has_thresholds:
                    _LOGGER.debug("Missing or invalid threshold percentages for %s rating", query_type)
                    is_empty = True
                else:
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
                        "%s rating check - has_thresholds: %s, entries count: %d, is_empty: %s",
                        query_type,
                        has_thresholds,
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


def _prepare_headers(access_token: str) -> dict[str, str]:
    """Prepare headers for API request."""
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "User-Agent": f"HomeAssistant/{ha_version} tibber_prices/{VERSION}",
    }


def _flatten_price_info(subscription: dict) -> dict:
    """Transform and flatten priceInfo from full API data structure."""
    price_info = subscription.get("priceInfo", {})

    # Get today and yesterday dates using Home Assistant's dt_util
    today_local = dt_util.now().date()
    yesterday_local = today_local - timedelta(days=1)
    _LOGGER.debug("Processing data for yesterday's date: %s", yesterday_local)

    # Transform edges data (extract yesterday's prices)
    if "range" in price_info and "edges" in price_info["range"]:
        edges = price_info["range"]["edges"]
        yesterday_prices = []

        for edge in edges:
            if "node" not in edge:
                _LOGGER.debug("Skipping edge without node: %s", edge)
                continue

            price_data = edge["node"]
            # Parse timestamp using dt_util for proper timezone handling
            starts_at = dt_util.parse_datetime(price_data["startsAt"])
            if starts_at is None:
                _LOGGER.debug("Could not parse timestamp: %s", price_data["startsAt"])
                continue

            # Convert to local timezone
            starts_at = dt_util.as_local(starts_at)
            price_date = starts_at.date()

            # Only include prices from yesterday
            if price_date == yesterday_local:
                yesterday_prices.append(price_data)

        _LOGGER.debug("Found %d price entries for yesterday", len(yesterday_prices))
        # Replace the entire range object with yesterday prices
        price_info["yesterday"] = yesterday_prices
        del price_info["range"]

    return {
        "yesterday": price_info.get("yesterday", []),
        "today": price_info.get("today", []),
        "tomorrow": price_info.get("tomorrow", []),
    }


def _flatten_price_rating(subscription: dict) -> dict:
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
        "thresholdPercentages": price_rating.get("thresholdPercentages"),
        "currency": currency,
    }


class TibberPricesApiClient:
    """Tibber API Client."""

    def __init__(
        self,
        access_token: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Tibber API Client."""
        self._access_token = access_token
        self._session = session
        self._request_semaphore = asyncio.Semaphore(2)  # Max 2 concurrent requests
        self._last_request_time = dt_util.now()
        self._min_request_interval = timedelta(seconds=1)  # Min 1 second between requests
        self._max_retries = 5
        self._retry_delay = 2  # Base retry delay in seconds

        # Timeout configuration - more granular control
        self._connect_timeout = 10  # Connection timeout in seconds
        self._request_timeout = 25  # Total request timeout in seconds
        self._socket_connect_timeout = 5  # Socket connection timeout

    async def async_get_viewer_details(self) -> Any:
        """Test connection to the API."""
        return await self._api_wrapper(
            data={
                "query": """
                    {
                        viewer {
                            userId
                            name
                            login
                            homes {
                                id
                                type
                                appNickname
                                address {
                                    address1
                                    postalCode
                                    city
                                    country
                                }
                            }
                        }
                    }
                """
            },
            query_type=QueryType.USER,
        )

    async def async_get_price_info(self) -> dict:
        """Get price info data in flat format for all homes."""
        data = await self._api_wrapper(
            data={
                "query": """
                    {viewer{homes{id,currentSubscription{priceInfo{
                        range(resolution:HOURLY,last:48){edges{node{
                            startsAt total energy tax level
                        }}}
                        today{startsAt total energy tax level}
                        tomorrow{startsAt total energy tax level}
                    }}}}}"""
            },
            query_type=QueryType.PRICE_INFO,
        )
        homes = data.get("viewer", {}).get("homes", [])

        homes_data = {}
        for home in homes:
            home_id = home.get("id")
            if home_id:
                if "currentSubscription" in home:
                    homes_data[home_id] = _flatten_price_info(home["currentSubscription"])
                else:
                    homes_data[home_id] = {}

        data["homes"] = homes_data
        return data

    async def async_get_daily_price_rating(self) -> dict:
        """Get daily price rating data in flat format for all homes."""
        data = await self._api_wrapper(
            data={
                "query": """
                    {viewer{homes{id,currentSubscription{priceRating{
                        thresholdPercentages{low high}
                        daily{
                            currency
                            entries{time total energy tax difference level}
                        }
                    }}}}}"""
            },
            query_type=QueryType.DAILY_RATING,
        )
        homes = data.get("viewer", {}).get("homes", [])

        homes_data = {}
        for home in homes:
            home_id = home.get("id")
            if home_id:
                if "currentSubscription" in home:
                    homes_data[home_id] = _flatten_price_rating(home["currentSubscription"])
                else:
                    homes_data[home_id] = {}

        data["homes"] = homes_data
        return data

    async def async_get_hourly_price_rating(self) -> dict:
        """Get hourly price rating data in flat format for all homes."""
        data = await self._api_wrapper(
            data={
                "query": """
                    {viewer{homes{id,currentSubscription{priceRating{
                        thresholdPercentages{low high}
                        hourly{
                            currency
                            entries{time total energy tax difference level}
                        }
                    }}}}}"""
            },
            query_type=QueryType.HOURLY_RATING,
        )
        homes = data.get("viewer", {}).get("homes", [])

        homes_data = {}
        for home in homes:
            home_id = home.get("id")
            if home_id:
                if "currentSubscription" in home:
                    homes_data[home_id] = _flatten_price_rating(home["currentSubscription"])
                else:
                    homes_data[home_id] = {}

        data["homes"] = homes_data
        return data

    async def async_get_monthly_price_rating(self) -> dict:
        """Get monthly price rating data in flat format for all homes."""
        data = await self._api_wrapper(
            data={
                "query": """
                    {viewer{homes{id,currentSubscription{priceRating{
                        thresholdPercentages{low high}
                        monthly{
                            currency
                            entries{time total energy tax difference level}
                        }
                    }}}}}"""
            },
            query_type=QueryType.MONTHLY_RATING,
        )
        homes = data.get("viewer", {}).get("homes", [])

        homes_data = {}
        for home in homes:
            home_id = home.get("id")
            if home_id:
                if "currentSubscription" in home:
                    homes_data[home_id] = _flatten_price_rating(home["currentSubscription"])
                else:
                    homes_data[home_id] = {}

        data["homes"] = homes_data
        return data

    async def async_get_data(self) -> dict:
        """Get all data from the API by combining multiple queries in flat format for all homes."""
        price_info = await self.async_get_price_info()
        daily_rating = await self.async_get_daily_price_rating()
        hourly_rating = await self.async_get_hourly_price_rating()
        monthly_rating = await self.async_get_monthly_price_rating()

        all_home_ids = set()
        all_home_ids.update(price_info.get("homes", {}).keys())
        all_home_ids.update(daily_rating.get("homes", {}).keys())
        all_home_ids.update(hourly_rating.get("homes", {}).keys())
        all_home_ids.update(monthly_rating.get("homes", {}).keys())

        homes_combined = {}
        for home_id in all_home_ids:
            daily_data = daily_rating.get("homes", {}).get(home_id, {})
            hourly_data = hourly_rating.get("homes", {}).get(home_id, {})
            monthly_data = monthly_rating.get("homes", {}).get(home_id, {})

            price_rating = {
                "thresholdPercentages": daily_data.get("thresholdPercentages"),
                "daily": daily_data.get("daily", []),
                "hourly": hourly_data.get("hourly", []),
                "monthly": monthly_data.get("monthly", []),
                "currency": (daily_data.get("currency") or hourly_data.get("currency") or monthly_data.get("currency")),
            }

            homes_combined[home_id] = {
                "priceInfo": price_info.get("homes", {}).get(home_id, {}),
                "priceRating": price_rating,
            }

        return {"homes": homes_combined}

    async def _make_request(
        self,
        headers: dict[str, str],
        data: dict,
        query_type: QueryType,
    ) -> dict:
        """Make an API request with comprehensive error handling for network issues."""
        _LOGGER.debug("Making API request with data: %s", data)

        try:
            # More granular timeout configuration for better network failure handling
            timeout = aiohttp.ClientTimeout(
                total=self._request_timeout,  # Total request timeout: 25s
                connect=self._connect_timeout,  # Connection timeout: 10s
                sock_connect=self._socket_connect_timeout,  # Socket connection: 5s
            )

            response = await self._session.request(
                method="POST",
                url="https://api.tibber.com/v1-beta/gql",
                headers=headers,
                json=data,
                timeout=timeout,
            )

            _verify_response_or_raise(response)
            response_json = await response.json()
            _LOGGER.debug("Received API response: %s", response_json)

            await _verify_graphql_response(response_json, query_type)

            return response_json["data"]

        except aiohttp.ClientResponseError as error:
            _LOGGER.exception("HTTP error during API request")
            raise TibberPricesApiClientCommunicationError(
                TibberPricesApiClientCommunicationError.CONNECTION_ERROR.format(exception=str(error))
            ) from error

        except aiohttp.ClientConnectorError as error:
            _LOGGER.exception("Connection error - server unreachable or network down")
            raise TibberPricesApiClientCommunicationError(
                TibberPricesApiClientCommunicationError.CONNECTION_ERROR.format(exception=str(error))
            ) from error

        except aiohttp.ServerDisconnectedError as error:
            _LOGGER.exception("Server disconnected during request")
            raise TibberPricesApiClientCommunicationError(
                TibberPricesApiClientCommunicationError.CONNECTION_ERROR.format(exception=str(error))
            ) from error

        except TimeoutError as error:
            _LOGGER.exception(
                "Request timeout after %d seconds - slow network or server overload", self._request_timeout
            )
            raise TibberPricesApiClientCommunicationError(
                TibberPricesApiClientCommunicationError.TIMEOUT_ERROR.format(exception=str(error))
            ) from error

        except socket.gaierror as error:
            self._handle_dns_error(error)

        except OSError as error:
            self._handle_network_error(error)

    def _handle_dns_error(self, error: socket.gaierror) -> None:
        """Handle DNS resolution errors with IPv4/IPv6 dual stack considerations."""
        error_msg = str(error)

        if "Name or service not known" in error_msg:
            _LOGGER.exception("DNS resolution failed - domain name not found")
        elif "Temporary failure in name resolution" in error_msg:
            _LOGGER.exception("DNS resolution temporarily failed - network or DNS server issue")
        elif "Address family for hostname not supported" in error_msg:
            _LOGGER.exception("DNS resolution failed - IPv4/IPv6 address family not supported")
        elif "No address associated with hostname" in error_msg:
            _LOGGER.exception("DNS resolution failed - no IPv4/IPv6 addresses found")
        else:
            _LOGGER.exception("DNS resolution failed - check internet connection: %s", error_msg)

        raise TibberPricesApiClientCommunicationError(
            TibberPricesApiClientCommunicationError.CONNECTION_ERROR.format(exception=str(error))
        ) from error

    def _handle_network_error(self, error: OSError) -> None:
        """Handle network-level errors with IPv4/IPv6 dual stack considerations."""
        error_msg = str(error)
        errno = getattr(error, "errno", None)

        # Common IPv4/IPv6 dual stack network error codes
        errno_network_unreachable = 101  # ENETUNREACH
        errno_host_unreachable = 113  # EHOSTUNREACH
        errno_connection_refused = 111  # ECONNREFUSED
        errno_connection_timeout = 110  # ETIMEDOUT

        if errno == errno_network_unreachable:
            _LOGGER.exception("Network unreachable - check internet connection or IPv4/IPv6 routing")
        elif errno == errno_host_unreachable:
            _LOGGER.exception("Host unreachable - routing issue or IPv4/IPv6 connectivity problem")
        elif errno == errno_connection_refused:
            _LOGGER.exception("Connection refused - server not accepting connections")
        elif errno == errno_connection_timeout:
            _LOGGER.exception("Connection timed out - network latency or server overload")
        elif "Address family not supported" in error_msg:
            _LOGGER.exception("Address family not supported - IPv4/IPv6 configuration issue")
        elif "Protocol not available" in error_msg:
            _LOGGER.exception("Protocol not available - IPv4/IPv6 stack configuration issue")
        elif "Network is down" in error_msg:
            _LOGGER.exception("Network interface is down - check network adapter")
        elif "Permission denied" in error_msg:
            _LOGGER.exception("Network permission denied - firewall or security restriction")
        else:
            _LOGGER.exception("Network error - internet may be down: %s", error_msg)

        raise TibberPricesApiClientCommunicationError(
            TibberPricesApiClientCommunicationError.CONNECTION_ERROR.format(exception=str(error))
        ) from error

    async def _handle_request(
        self,
        headers: dict[str, str],
        data: dict,
        query_type: QueryType,
    ) -> Any:
        """Handle a single API request with rate limiting."""
        async with self._request_semaphore:
            now = dt_util.now()
            time_since_last_request = now - self._last_request_time
            if time_since_last_request < self._min_request_interval:
                sleep_time = (self._min_request_interval - time_since_last_request).total_seconds()
                _LOGGER.debug(
                    "Rate limiting: waiting %s seconds before next request",
                    sleep_time,
                )
                await asyncio.sleep(sleep_time)

            self._last_request_time = dt_util.now()
            return await self._make_request(
                headers,
                data or {},
                query_type,
            )

    def _should_retry_error(self, error: Exception, retry: int) -> tuple[bool, int]:
        """Determine if an error should be retried and calculate delay."""
        # Check if we've exceeded max retries first
        if retry >= self._max_retries:
            return False, 0

        # Non-retryable errors - authentication and permission issues
        if isinstance(error, (TibberPricesApiClientAuthenticationError, TibberPricesApiClientPermissionError)):
            return False, 0

        # Handle API-specific errors
        if isinstance(error, TibberPricesApiClientError):
            return self._handle_api_error_retry(error, retry)

        # Network and timeout errors - retryable with exponential backoff
        if isinstance(error, (aiohttp.ClientError, socket.gaierror, TimeoutError)):
            delay = min(self._retry_delay * (2**retry), 30)  # Cap at 30 seconds
            return True, delay

        # Unknown errors - not retryable
        return False, 0

    def _handle_api_error_retry(self, error: TibberPricesApiClientError, retry: int) -> tuple[bool, int]:
        """Handle retry logic for API-specific errors."""
        error_msg = str(error)

        # Non-retryable: Invalid queries
        if "Invalid GraphQL query" in error_msg or "Bad request" in error_msg:
            return False, 0

        # Rate limits - special handling with extracted delay
        if "Rate limit exceeded" in error_msg or "rate limited" in error_msg.lower():
            delay = self._extract_retry_delay(error, retry)
            return True, delay

        # Empty data - retryable with capped exponential backoff
        if "Empty data received" in error_msg:
            delay = min(self._retry_delay * (2**retry), 60)  # Cap at 60 seconds
            return True, delay

        # Other API errors - retryable with capped exponential backoff
        delay = min(self._retry_delay * (2**retry), 30)  # Cap at 30 seconds
        return True, delay

    def _extract_retry_delay(self, error: Exception, retry: int) -> int:
        """Extract retry delay from rate limit error or use exponential backoff."""
        import re

        error_msg = str(error)

        # Try to extract Retry-After value from error message
        retry_after_match = re.search(r"retry after (\d+) seconds", error_msg.lower())
        if retry_after_match:
            try:
                retry_after = int(retry_after_match.group(1))
                return min(retry_after + 1, 300)  # Add buffer, max 5 minutes
            except ValueError:
                pass

        # Try to extract generic seconds value
        seconds_match = re.search(r"(\d+) seconds", error_msg)
        if seconds_match:
            try:
                seconds = int(seconds_match.group(1))
                return min(seconds + 1, 300)  # Add buffer, max 5 minutes
            except ValueError:
                pass

        # Fall back to exponential backoff with cap
        base_delay = self._retry_delay * (2**retry)
        return min(base_delay, 120)  # Cap at 2 minutes for rate limits

    async def _api_wrapper(
        self,
        data: dict | None = None,
        headers: dict | None = None,
        query_type: QueryType = QueryType.USER,
    ) -> Any:
        """Get information from the API with rate limiting and retry logic."""
        headers = headers or _prepare_headers(self._access_token)
        last_error: Exception | None = None

        for retry in range(self._max_retries + 1):
            try:
                return await self._handle_request(headers, data or {}, query_type)

            except (
                TibberPricesApiClientAuthenticationError,
                TibberPricesApiClientPermissionError,
            ):
                _LOGGER.exception("Non-retryable error occurred")
                raise
            except (
                TibberPricesApiClientError,
                aiohttp.ClientError,
                socket.gaierror,
                TimeoutError,
            ) as error:
                last_error = (
                    error
                    if isinstance(error, TibberPricesApiClientError)
                    else TibberPricesApiClientCommunicationError(
                        TibberPricesApiClientCommunicationError.CONNECTION_ERROR.format(exception=str(error))
                    )
                )

                should_retry, delay = self._should_retry_error(error, retry)
                if should_retry:
                    error_type = self._get_error_type(error)
                    _LOGGER.warning(
                        "Tibber %s error, attempt %d/%d. Retrying in %d seconds: %s",
                        error_type,
                        retry + 1,
                        self._max_retries,
                        delay,
                        str(error),
                    )
                    await asyncio.sleep(delay)
                    continue

                if "Invalid GraphQL query" in str(error):
                    _LOGGER.exception("Invalid query - not retrying")
                raise

        # Handle final error state
        if isinstance(last_error, TimeoutError):
            raise TibberPricesApiClientCommunicationError(
                TibberPricesApiClientCommunicationError.TIMEOUT_ERROR.format(exception=last_error)
            ) from last_error
        if isinstance(last_error, (aiohttp.ClientError, socket.gaierror)):
            raise TibberPricesApiClientCommunicationError(
                TibberPricesApiClientCommunicationError.CONNECTION_ERROR.format(exception=last_error)
            ) from last_error

        raise last_error or TibberPricesApiClientError(TibberPricesApiClientError.UNKNOWN_ERROR)

    def _get_error_type(self, error: Exception) -> str:
        """Get a descriptive error type for logging."""
        if "Rate limit" in str(error):
            return "rate limit"
        if isinstance(error, (aiohttp.ClientError, socket.gaierror, TimeoutError)):
            return "network"
        return "API"
