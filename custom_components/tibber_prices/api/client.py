"""Tibber API Client."""

from __future__ import annotations

import asyncio
import logging
import re
import socket
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import aiohttp

from .exceptions import (
    TibberPricesApiClientAuthenticationError,
    TibberPricesApiClientCommunicationError,
    TibberPricesApiClientError,
    TibberPricesApiClientPermissionError,
)
from .helpers import (
    flatten_price_info,
    flatten_price_rating,
    prepare_headers,
    verify_graphql_response,
    verify_response_or_raise,
)
from .queries import TibberPricesQueryType

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService

_LOGGER = logging.getLogger(__name__)


class TibberPricesApiClient:
    """Tibber API Client."""

    def __init__(
        self,
        access_token: str,
        session: aiohttp.ClientSession,
        version: str,
    ) -> None:
        """Tibber API Client."""
        self._access_token = access_token
        self._session = session
        self._version = version
        self._request_semaphore = asyncio.Semaphore(2)  # Max 2 concurrent requests
        self.time: TibberPricesTimeService | None = None  # Set externally by coordinator (optional during config flow)
        self._last_request_time = None  # Set on first request
        self._min_request_interval = timedelta(seconds=1)  # Min 1 second between requests
        self._max_retries = 5
        self._retry_delay = 2  # Base retry delay in seconds

        # Timeout configuration - more granular control
        self._connect_timeout = 10  # Connection timeout in seconds
        self._request_timeout = 25  # Total request timeout in seconds
        self._socket_connect_timeout = 5  # Socket connection timeout

    async def async_get_viewer_details(self) -> Any:
        """Get comprehensive viewer and home details from Tibber API."""
        return await self._api_wrapper(
            data={
                "query": """
                    {
                        viewer {
                            userId
                            name
                            login
                            accountType
                            homes {
                                id
                                type
                                appNickname
                                appAvatar
                                size
                                timeZone
                                mainFuseSize
                                numberOfResidents
                                primaryHeatingSource
                                hasVentilationSystem
                                address {
                                    address1
                                    address2
                                    address3
                                    postalCode
                                    city
                                    country
                                    latitude
                                    longitude
                                }
                                owner {
                                    id
                                    firstName
                                    lastName
                                    isCompany
                                    name
                                    contactInfo {
                                        email
                                        mobile
                                    }
                                    language
                                }
                                meteringPointData {
                                    consumptionEan
                                    gridCompany
                                    gridAreaCode
                                    priceAreaCode
                                    productionEan
                                    energyTaxType
                                    vatType
                                    estimatedAnnualConsumption
                                }
                                currentSubscription {
                                    id
                                    status
                                    validFrom
                                    validTo
                                    priceInfo {
                                        current {
                                            currency
                                        }
                                    }
                                }
                                features {
                                    realTimeConsumptionEnabled
                                }
                            }
                        }
                    }
                """
            },
            query_type=TibberPricesQueryType.USER,
        )

    async def async_get_price_info(self, home_ids: set[str]) -> dict:
        """
        Get price info data in flat format for specified homes.

        Args:
            home_ids: Set of home IDs to fetch data for.

        Returns:
            Dictionary with homes data keyed by home_id.

        """
        return await self._get_price_info_for_specific_homes(home_ids)

    async def _get_price_info_for_specific_homes(self, home_ids: set[str]) -> dict:
        """Get price info for specific homes using GraphQL aliases."""
        if not self.time:
            msg = "TimeService not initialized - required for price info processing"
            raise TibberPricesApiClientError(msg)

        if not home_ids:
            return {"homes": {}}

        # Build query with aliases for each home
        # Example: home1: home(id: "abc") { ... }
        home_queries = []
        for idx, home_id in enumerate(sorted(home_ids)):
            alias = f"home{idx}"
            home_query = f"""
                {alias}: home(id: "{home_id}") {{
                    id
                    consumption(resolution:DAILY,last:1) {{
                        pageInfo{{currency}}
                    }}
                    currentSubscription {{
                        priceInfoRange(resolution:QUARTER_HOURLY,last:192) {{
                            edges{{node{{
                                startsAt total energy tax level
                            }}}}
                        }}
                        priceInfo(resolution:QUARTER_HOURLY) {{
                            today{{startsAt total energy tax level}}
                            tomorrow{{startsAt total energy tax level}}
                        }}
                    }}
                }}
            """
            home_queries.append(home_query)

        query = "{viewer{" + "".join(home_queries) + "}}"

        _LOGGER.debug("Fetching price info for %d specific home(s)", len(home_ids))

        data = await self._api_wrapper(
            data={"query": query},
            query_type=TibberPricesQueryType.PRICE_INFO,
        )

        # Parse aliased response
        viewer = data.get("viewer", {})
        homes_data = {}

        for idx, home_id in enumerate(sorted(home_ids)):
            alias = f"home{idx}"
            home = viewer.get(alias)

            if not home:
                _LOGGER.debug("Home %s not found in API response", home_id)
                homes_data[home_id] = {}
                continue

            if "currentSubscription" in home and home["currentSubscription"] is not None:
                # Extract currency from consumption data if available
                currency = None
                if home.get("consumption"):
                    page_info = home["consumption"].get("pageInfo")
                    if page_info:
                        currency = page_info.get("currency")

                homes_data[home_id] = flatten_price_info(
                    home["currentSubscription"],
                    currency,
                    time=self.time,
                )
            else:
                _LOGGER.debug(
                    "Home %s has no active subscription - price data will be unavailable",
                    home_id,
                )
                homes_data[home_id] = {}

        data["homes"] = homes_data
        return data

    async def async_get_daily_price_rating(self) -> dict:
        """Get daily price rating data in flat format for all homes."""
        data = await self._api_wrapper(
            data={
                "query": """
                    {viewer{homes{id,currentSubscription{priceRating{
                        daily{
                            currency
                            entries{time total energy tax difference level}
                        }
                    }}}}}"""
            },
            query_type=TibberPricesQueryType.DAILY_RATING,
        )
        homes = data.get("viewer", {}).get("homes", [])

        homes_data = {}
        for home in homes:
            home_id = home.get("id")
            if home_id:
                if "currentSubscription" in home and home["currentSubscription"] is not None:
                    homes_data[home_id] = flatten_price_rating(home["currentSubscription"])
                else:
                    _LOGGER.debug(
                        "Home %s has no active subscription - daily rating data will be unavailable",
                        home_id,
                    )
                    homes_data[home_id] = {}

        data["homes"] = homes_data
        return data

    async def async_get_hourly_price_rating(self) -> dict:
        """Get hourly price rating data in flat format for all homes."""
        data = await self._api_wrapper(
            data={
                "query": """
                    {viewer{homes{id,currentSubscription{priceRating{
                        hourly{
                            currency
                            entries{time total energy tax difference level}
                        }
                    }}}}}"""
            },
            query_type=TibberPricesQueryType.HOURLY_RATING,
        )
        homes = data.get("viewer", {}).get("homes", [])

        homes_data = {}
        for home in homes:
            home_id = home.get("id")
            if home_id:
                if "currentSubscription" in home and home["currentSubscription"] is not None:
                    homes_data[home_id] = flatten_price_rating(home["currentSubscription"])
                else:
                    _LOGGER.debug(
                        "Home %s has no active subscription - hourly rating data will be unavailable",
                        home_id,
                    )
                    homes_data[home_id] = {}

        data["homes"] = homes_data
        return data

    async def async_get_monthly_price_rating(self) -> dict:
        """Get monthly price rating data in flat format for all homes."""
        data = await self._api_wrapper(
            data={
                "query": """
                    {viewer{homes{id,currentSubscription{priceRating{
                        monthly{
                            currency
                            entries{time total energy tax difference level}
                        }
                    }}}}}"""
            },
            query_type=TibberPricesQueryType.MONTHLY_RATING,
        )
        homes = data.get("viewer", {}).get("homes", [])

        homes_data = {}
        for home in homes:
            home_id = home.get("id")
            if home_id:
                if "currentSubscription" in home and home["currentSubscription"] is not None:
                    homes_data[home_id] = flatten_price_rating(home["currentSubscription"])
                else:
                    _LOGGER.debug(
                        "Home %s has no active subscription - monthly rating data will be unavailable",
                        home_id,
                    )
                    homes_data[home_id] = {}

        data["homes"] = homes_data
        return data

    async def _make_request(
        self,
        headers: dict[str, str],
        data: dict,
        query_type: TibberPricesQueryType,
    ) -> dict[str, Any]:
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

            verify_response_or_raise(response)
            response_json = await response.json()
            _LOGGER.debug("Received API response: %s", response_json)

            await verify_graphql_response(response_json, query_type)

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
                "Request timeout after %d seconds - slow network or server overload",
                self._request_timeout,
            )
            raise TibberPricesApiClientCommunicationError(
                TibberPricesApiClientCommunicationError.TIMEOUT_ERROR.format(exception=str(error))
            ) from error

        except socket.gaierror as error:
            self._handle_dns_error(error)
            raise  # Ensure type checker knows this path always raises

        except OSError as error:
            self._handle_network_error(error)
            raise  # Ensure type checker knows this path always raises

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
        query_type: TibberPricesQueryType,
    ) -> Any:
        """Handle a single API request with rate limiting."""
        async with self._request_semaphore:
            # Rate limiting: ensure minimum interval between requests
            if self.time and self._last_request_time:
                now = self.time.now()
                time_since_last_request = now - self._last_request_time
                if time_since_last_request < self._min_request_interval:
                    sleep_time = (self._min_request_interval - time_since_last_request).total_seconds()
                    _LOGGER.debug(
                        "Rate limiting: waiting %s seconds before next request",
                        sleep_time,
                    )
                    await asyncio.sleep(sleep_time)

            if self.time:
                self._last_request_time = self.time.now()
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
        if isinstance(
            error,
            (
                TibberPricesApiClientAuthenticationError,
                TibberPricesApiClientPermissionError,
            ),
        ):
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
        query_type: TibberPricesQueryType = TibberPricesQueryType.USER,
    ) -> Any:
        """Get information from the API with rate limiting and retry logic."""
        headers = headers or prepare_headers(self._access_token, self._version)
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
