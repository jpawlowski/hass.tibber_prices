"""Tibber API Client."""

from __future__ import annotations

import asyncio
import base64
import logging
import re
import socket
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import aiohttp

from homeassistant.util import dt as dt_utils

from .exceptions import (
    TibberPricesApiClientAuthenticationError,
    TibberPricesApiClientCommunicationError,
    TibberPricesApiClientError,
    TibberPricesApiClientPermissionError,
)
from .helpers import (
    flatten_price_info,
    prepare_headers,
    verify_graphql_response,
    verify_response_or_raise,
)
from .queries import TibberPricesQueryType

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService

_LOGGER = logging.getLogger(__name__)
_LOGGER_API_DETAILS = logging.getLogger(__name__ + ".details")


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

    async def async_get_price_info_for_range(
        self,
        home_id: str,
        user_data: dict[str, Any],
        start_time: datetime,
        end_time: datetime,
    ) -> dict:
        """
        Get price info for a specific time range with automatic routing.

        This is a convenience wrapper around interval_pool.get_price_intervals_for_range().

        Args:
            home_id: Home ID to fetch price data for.
            user_data: User data dict containing home metadata (including timezone).
            start_time: Start of the range (inclusive, timezone-aware).
            end_time: End of the range (exclusive, timezone-aware).

        Returns:
            Dict with "home_id" and "price_info" (list of intervals).

        Raises:
            TibberPricesApiClientError: If arguments invalid or requests fail.

        """
        # Import here to avoid circular dependency (interval_pool imports TibberPricesApiClient)
        from custom_components.tibber_prices.interval_pool import (  # noqa: PLC0415
            get_price_intervals_for_range,
        )

        price_info = await get_price_intervals_for_range(
            api_client=self,
            home_id=home_id,
            user_data=user_data,
            start_time=start_time,
            end_time=end_time,
        )

        return {
            "home_id": home_id,
            "price_info": price_info,
        }

    async def async_get_price_info(self, home_id: str, user_data: dict[str, Any]) -> dict:
        """
        Get price info for a single home.

        Uses timezone-aware cursor calculation based on the home's actual timezone
        from Tibber API (not HA system timezone). This ensures correct "day before yesterday
        midnight" calculation for homes in different timezones.

        Args:
            home_id: Home ID to fetch price data for.
            user_data: User data dict containing home metadata (including timezone).
                      REQUIRED - must be fetched before calling this method.

        Returns:
            Dict with "home_id", "price_info", and other home data.

        Raises:
            TibberPricesApiClientError: If TimeService not initialized or user_data missing.

        """
        if not self.time:
            msg = "TimeService not initialized - required for price info processing"
            raise TibberPricesApiClientError(msg)

        if not user_data:
            msg = "User data required for timezone-aware price fetching - fetch user data first"
            raise TibberPricesApiClientError(msg)

        if not home_id:
            msg = "Home ID is required"
            raise TibberPricesApiClientError(msg)

        # Build home_id -> timezone mapping from user_data
        home_timezones = self._extract_home_timezones(user_data)

        # Get timezone for this home (fallback to HA system timezone)
        home_tz = home_timezones.get(home_id)

        # Calculate cursor: day before yesterday midnight in home's timezone
        cursor = self._calculate_cursor_for_home(home_tz)

        # Simple single-home query (no alias needed)
        query = f"""
            {{viewer{{
                home(id: "{home_id}") {{
                    id
                    currentSubscription {{
                        priceInfoRange(resolution:QUARTER_HOURLY, first:192, after: "{cursor}") {{
                            pageInfo{{ count }}
                            edges{{node{{
                                startsAt total level
                            }}}}
                        }}
                        priceInfo(resolution:QUARTER_HOURLY) {{
                            today{{startsAt total level}}
                            tomorrow{{startsAt total level}}
                        }}
                    }}
                }}
            }}}}
        """

        _LOGGER.debug("Fetching price info for home %s", home_id)

        data = await self._api_wrapper(
            data={"query": query},
            query_type=TibberPricesQueryType.PRICE_INFO,
        )

        # Parse response
        viewer = data.get("viewer", {})
        home = viewer.get("home")

        if not home:
            msg = f"Home {home_id} not found in API response"
            _LOGGER.warning(msg)
            return {"home_id": home_id, "price_info": []}

        if "currentSubscription" in home and home["currentSubscription"] is not None:
            price_info = flatten_price_info(home["currentSubscription"])
        else:
            _LOGGER.warning(
                "Home %s has no active subscription - price data will be unavailable",
                home_id,
            )
            price_info = []

        return {
            "home_id": home_id,
            "price_info": price_info,
        }

    async def async_get_price_info_range(
        self,
        home_id: str,
        user_data: dict[str, Any],
        start_time: datetime,
        end_time: datetime,
    ) -> dict:
        """
        Get historical price info for a specific time range using priceInfoRange endpoint.

        Uses the priceInfoRange GraphQL endpoint for flexible historical data queries.
        Intended for intervals BEFORE "day before yesterday midnight" (outside PRICE_INFO scope).

        Automatically handles API pagination if Tibber limits batch size.

        Args:
            home_id: Home ID to fetch price data for.
            user_data: User data dict containing home metadata (including timezone).
            start_time: Start of the range (inclusive, timezone-aware).
            end_time: End of the range (exclusive, timezone-aware).

        Returns:
            Dict with "home_id" and "price_info" (list of intervals).

        Raises:
            TibberPricesApiClientError: If arguments invalid or request fails.

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

        _LOGGER_API_DETAILS.debug(
            "fetch_price_info_range called with: start_time=%s (type=%s, tzinfo=%s), end_time=%s (type=%s, tzinfo=%s)",
            start_time,
            type(start_time),
            start_time.tzinfo,
            end_time,
            type(end_time),
            end_time.tzinfo,
        )

        # Calculate cursor and interval count
        start_cursor = self._encode_cursor(start_time)
        interval_count = self._calculate_interval_count(start_time, end_time)

        _LOGGER_API_DETAILS.debug(
            "Calculated cursor for range: start_time=%s, cursor_time=%s, encoded=%s",
            start_time,
            start_time,
            start_cursor,
        )

        # Fetch all intervals with automatic paging
        price_info = await self._fetch_price_info_with_paging(
            home_id=home_id,
            start_cursor=start_cursor,
            interval_count=interval_count,
        )

        return {
            "home_id": home_id,
            "price_info": price_info,
        }

    def _calculate_interval_count(self, start_time: datetime, end_time: datetime) -> int:
        """Calculate number of intervals needed based on date range."""
        time_diff = end_time - start_time
        resolution_change_date = datetime(2025, 10, 1, tzinfo=start_time.tzinfo)

        if start_time < resolution_change_date:
            # Pre-resolution-change: hourly intervals only
            interval_count = int(time_diff.total_seconds() / 3600)  # 3600s = 1h
            _LOGGER_API_DETAILS.debug(
                "Time range is pre-2025-10-01: expecting hourly intervals (count: %d)",
                interval_count,
            )
        else:
            # Post-resolution-change: quarter-hourly intervals
            interval_count = int(time_diff.total_seconds() / 900)  # 900s = 15min
            _LOGGER_API_DETAILS.debug(
                "Time range is post-2025-10-01: expecting quarter-hourly intervals (count: %d)",
                interval_count,
            )

        return interval_count

    async def _fetch_price_info_with_paging(
        self,
        home_id: str,
        start_cursor: str,
        interval_count: int,
    ) -> list[dict[str, Any]]:
        """
        Fetch price info with automatic pagination if API limits batch size.

        GraphQL Cursor Pagination:
        - endCursor points to the last returned element (inclusive)
        - Use 'after: endCursor' to get elements AFTER that cursor
        - If count < requested, more pages available

        Args:
            home_id: Home ID to fetch price data for.
            start_cursor: Base64-encoded start cursor.
            interval_count: Total number of intervals to fetch.

        Returns:
            List of all price interval dicts across all pages.

        """
        price_info = []
        remaining_intervals = interval_count
        cursor = start_cursor
        page = 0

        while remaining_intervals > 0:
            page += 1

            # Fetch one page
            page_data = await self._fetch_single_page(
                home_id=home_id,
                cursor=cursor,
                requested_count=remaining_intervals,
                page=page,
            )

            if not page_data:
                break

            # Extract intervals and pagination info
            page_intervals = page_data["intervals"]
            returned_count = page_data["count"]
            end_cursor = page_data["end_cursor"]
            has_next_page = page_data.get("has_next_page", False)

            price_info.extend(page_intervals)

            _LOGGER_API_DETAILS.debug(
                "Page %d: Received %d intervals for home %s (total so far: %d/%d, endCursor=%s, hasNextPage=%s)",
                page,
                returned_count,
                home_id,
                len(price_info),
                interval_count,
                end_cursor,
                has_next_page,
            )

            # Update remaining count
            remaining_intervals -= returned_count

            # Check if we need more pages
            # Continue if: (1) we still need more intervals AND (2) API has more data
            if remaining_intervals > 0 and end_cursor:
                cursor = end_cursor
                _LOGGER_API_DETAILS.debug(
                    "Still need %d more intervals - fetching next page with cursor %s",
                    remaining_intervals,
                    cursor,
                )
            else:
                # Done: Either we have all intervals we need, or API has no more data
                if remaining_intervals > 0:
                    _LOGGER.warning(
                        "API has no more data - received %d out of %d requested intervals (missing %d)",
                        len(price_info),
                        interval_count,
                        remaining_intervals,
                    )
                else:
                    _LOGGER.debug(
                        "Pagination complete - received all %d requested intervals",
                        interval_count,
                    )
                break

        _LOGGER_API_DETAILS.debug(
            "Fetched %d total historical intervals for home %s across %d page(s)",
            len(price_info),
            home_id,
            page,
        )

        return price_info

    async def _fetch_single_page(
        self,
        home_id: str,
        cursor: str,
        requested_count: int,
        page: int,
    ) -> dict[str, Any] | None:
        """
        Fetch a single page of price intervals.

        Args:
            home_id: Home ID to fetch price data for.
            cursor: Base64-encoded cursor for this page.
            requested_count: Number of intervals to request.
            page: Page number (for logging).

        Returns:
            Dict with "intervals", "count", and "end_cursor" keys, or None if no data.

        """
        query = f"""
            {{viewer{{
                home(id: "{home_id}") {{
                    id
                    currentSubscription {{
                        priceInfoRange(resolution:QUARTER_HOURLY, first:{requested_count}, after: "{cursor}") {{
                            pageInfo{{
                                count
                                hasNextPage
                                startCursor
                                endCursor
                            }}
                            edges{{
                                cursor
                                node{{
                                    startsAt total level
                                }}
                            }}
                        }}
                    }}
                }}
            }}}}
        """

        _LOGGER_API_DETAILS.debug(
            "Fetching historical price info for home %s (page %d): %d intervals from cursor %s",
            home_id,
            page,
            requested_count,
            cursor,
        )

        data = await self._api_wrapper(
            data={"query": query},
            query_type=TibberPricesQueryType.PRICE_INFO_RANGE,
        )

        # Parse response
        viewer = data.get("viewer", {})
        home = viewer.get("home")

        if not home:
            _LOGGER.warning("Home %s not found in API response", home_id)
            return None

        if "currentSubscription" not in home or home["currentSubscription"] is None:
            _LOGGER.warning("Home %s has no active subscription - price data will be unavailable", home_id)
            return None

        # Extract priceInfoRange data
        subscription = home["currentSubscription"]
        price_info_range = subscription.get("priceInfoRange", {})
        page_info = price_info_range.get("pageInfo", {})
        edges = price_info_range.get("edges", [])

        # Flatten edges to interval list
        intervals = [edge["node"] for edge in edges if "node" in edge]

        return {
            "intervals": intervals,
            "count": page_info.get("count", len(intervals)),
            "end_cursor": page_info.get("endCursor"),
            "has_next_page": page_info.get("hasNextPage", False),
        }

    def _extract_home_timezones(self, user_data: dict[str, Any]) -> dict[str, str]:
        """
        Extract home_id -> timezone mapping from user_data.

        Args:
            user_data: User data dict from async_get_viewer_details() (required).

        Returns:
            Dict mapping home_id to timezone string (e.g., "Europe/Oslo").

        """
        home_timezones = {}
        viewer = user_data.get("viewer", {})
        homes = viewer.get("homes", [])

        for home in homes:
            home_id = home.get("id")
            timezone = home.get("timeZone")

            if home_id and timezone:
                home_timezones[home_id] = timezone
                _LOGGER_API_DETAILS.debug("Extracted timezone %s for home %s", timezone, home_id)
            elif home_id:
                _LOGGER.warning("Home %s has no timezone in user data, will use fallback", home_id)

        return home_timezones

    def _calculate_day_before_yesterday_midnight(self, home_timezone: str | None) -> datetime:
        """
        Calculate day before yesterday midnight in home's timezone.

        CRITICAL: Uses REAL TIME (dt_utils.now()), NOT TimeService.now().
        This ensures API boundary calculations are based on actual current time,
        not simulated time from TimeService.

        Args:
            home_timezone: Timezone string (e.g., "Europe/Oslo").
                          If None, falls back to HA system timezone.

        Returns:
            Timezone-aware datetime for day before yesterday midnight.

        """
        # Get current REAL time (not TimeService)
        now = dt_utils.now()

        # Convert to home's timezone or fallback to HA system timezone
        if home_timezone:
            try:
                tz = ZoneInfo(home_timezone)
                now_in_home_tz = now.astimezone(tz)
            except (KeyError, ValueError, OSError) as error:
                _LOGGER.warning(
                    "Invalid timezone %s (%s), falling back to HA system timezone",
                    home_timezone,
                    error,
                )
                now_in_home_tz = dt_utils.as_local(now)
        else:
            # Fallback to HA system timezone
            now_in_home_tz = dt_utils.as_local(now)

        # Calculate day before yesterday midnight
        return (now_in_home_tz - timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)

    def _encode_cursor(self, timestamp: datetime) -> str:
        """
        Encode a timestamp as base64 cursor for GraphQL API.

        Args:
            timestamp: Timezone-aware datetime to encode.

        Returns:
            Base64-encoded ISO timestamp string.

        """
        iso_string = timestamp.isoformat()
        return base64.b64encode(iso_string.encode()).decode()

    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """
        Parse ISO timestamp string to timezone-aware datetime.

        Args:
            timestamp_str: ISO format timestamp string.

        Returns:
            Timezone-aware datetime object.

        """
        return dt_utils.parse_datetime(timestamp_str) or dt_utils.now()

    def _calculate_cursor_for_home(self, home_timezone: str | None) -> str:
        """
        Calculate cursor (day before yesterday midnight) for a home's timezone.

        Convenience wrapper around _calculate_day_before_yesterday_midnight()
        and _encode_cursor() for backward compatibility with existing code.

        Args:
            home_timezone: Timezone string (e.g., "Europe/Oslo", "America/New_York").
                          If None, falls back to HA system timezone.

        Returns:
            Base64-encoded ISO timestamp string for use as GraphQL cursor.

        """
        day_before_yesterday_midnight = self._calculate_day_before_yesterday_midnight(home_timezone)
        return self._encode_cursor(day_before_yesterday_midnight)

    async def _make_request(
        self,
        headers: dict[str, str],
        data: dict,
        query_type: TibberPricesQueryType,
    ) -> dict[str, Any]:
        """Make an API request with comprehensive error handling for network issues."""
        _LOGGER_API_DETAILS.debug("Making API request with data: %s", data)

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
            _LOGGER_API_DETAILS.debug("Received API response: %s", response_json)

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
                    _LOGGER_API_DETAILS.debug(
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

        # Non-retryable: Invalid queries, bad requests, empty data
        # Empty data means API has no data for the requested range - retrying won't help
        if "Invalid GraphQL query" in error_msg or "Bad request" in error_msg or "Empty data received" in error_msg:
            return False, 0

        # Rate limits - only retry if server explicitly says so
        if "Rate limit exceeded" in error_msg or "rate limited" in error_msg.lower():
            delay = self._extract_retry_delay(error, retry)
            return True, delay

        # Other API errors - not retryable (assume permanent issue)
        return False, 0

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
