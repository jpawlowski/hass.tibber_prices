"""Tibber API Client."""

from __future__ import annotations

import asyncio
import logging
import socket
from datetime import timedelta
from enum import Enum
from typing import Any

import aiohttp
import async_timeout

from homeassistant.const import __version__ as ha_version
from homeassistant.util import dt as dt_util

from .const import VERSION

_LOGGER = logging.getLogger(__name__)

HTTP_TOO_MANY_REQUESTS = 429
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403


class QueryType(Enum):
    """Types of queries that can be made to the API."""

    PRICE_INFO = "price_info"
    DAILY_RATING = "daily"
    HOURLY_RATING = "hourly"
    MONTHLY_RATING = "monthly"
    VIEWER = "viewer"


class TibberPricesApiClientError(Exception):
    """Exception to indicate a general API error."""

    UNKNOWN_ERROR = "Unknown GraphQL error"
    MALFORMED_ERROR = "Malformed GraphQL error: {error}"
    GRAPHQL_ERROR = "GraphQL error: {message}"
    EMPTY_DATA_ERROR = "Empty data received for {query_type}"
    GENERIC_ERROR = "Something went wrong! {exception}"
    RATE_LIMIT_ERROR = "Rate limit exceeded"


class TibberPricesApiClientCommunicationError(TibberPricesApiClientError):
    """Exception to indicate a communication error."""

    TIMEOUT_ERROR = "Timeout error fetching information - {exception}"
    CONNECTION_ERROR = "Error fetching information - {exception}"


class TibberPricesApiClientAuthenticationError(TibberPricesApiClientError):
    """Exception to indicate an authentication error."""

    INVALID_CREDENTIALS = "Invalid credentials"


def _verify_response_or_raise(response: aiohttp.ClientResponse) -> None:
    """Verify that the response is valid."""
    if response.status in (HTTP_UNAUTHORIZED, HTTP_FORBIDDEN):
        raise TibberPricesApiClientAuthenticationError(TibberPricesApiClientAuthenticationError.INVALID_CREDENTIALS)
    if response.status == HTTP_TOO_MANY_REQUESTS:
        raise TibberPricesApiClientError(TibberPricesApiClientError.RATE_LIMIT_ERROR)
    response.raise_for_status()


async def _verify_graphql_response(response_json: dict, query_type: QueryType) -> None:
    """Verify the GraphQL response for errors and data completeness, including empty data."""
    if "errors" in response_json:
        errors = response_json["errors"]
        if not errors:
            raise TibberPricesApiClientError(TibberPricesApiClientError.UNKNOWN_ERROR)

        error = errors[0]  # Take first error
        if not isinstance(error, dict):
            raise TibberPricesApiClientError(TibberPricesApiClientError.MALFORMED_ERROR.format(error=error))

        message = error.get("message", "Unknown error")
        extensions = error.get("extensions", {})

        if extensions.get("code") == "UNAUTHENTICATED":
            raise TibberPricesApiClientAuthenticationError(TibberPricesApiClientAuthenticationError.INVALID_CREDENTIALS)

        raise TibberPricesApiClientError(TibberPricesApiClientError.GRAPHQL_ERROR.format(message=message))

    if "data" not in response_json or response_json["data"] is None:
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
        if query_type == "viewer":
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
        self._request_semaphore = asyncio.Semaphore(2)
        self._last_request_time = dt_util.now()
        self._min_request_interval = timedelta(seconds=1)
        self._max_retries = 5
        self._retry_delay = 2

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
            query_type=QueryType.VIEWER,
        )

    async def async_get_price_info(self, home_id: str) -> dict:
        """Get price info data in flat format for the specified home_id."""
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
        home = next((h for h in homes if h.get("id") == home_id), None)
        if home and "currentSubscription" in home:
            data["priceInfo"] = _flatten_price_info(home["currentSubscription"])
        else:
            data["priceInfo"] = {}
        return data

    async def async_get_daily_price_rating(self, home_id: str) -> dict:
        """Get daily price rating data in flat format for the specified home_id."""
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
        home = next((h for h in homes if h.get("id") == home_id), None)
        if home and "currentSubscription" in home:
            data["priceRating"] = _flatten_price_rating(home["currentSubscription"])
        else:
            data["priceRating"] = {}
        return data

    async def async_get_hourly_price_rating(self, home_id: str) -> dict:
        """Get hourly price rating data in flat format for the specified home_id."""
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
        home = next((h for h in homes if h.get("id") == home_id), None)
        if home and "currentSubscription" in home:
            data["priceRating"] = _flatten_price_rating(home["currentSubscription"])
        else:
            data["priceRating"] = {}
        return data

    async def async_get_monthly_price_rating(self, home_id: str) -> dict:
        """Get monthly price rating data in flat format for the specified home_id."""
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
        home = next((h for h in homes if h.get("id") == home_id), None)
        if home and "currentSubscription" in home:
            data["priceRating"] = _flatten_price_rating(home["currentSubscription"])
        else:
            data["priceRating"] = {}
        return data

    async def async_get_data(self, home_id: str) -> dict:
        """Get all data from the API by combining multiple queries in flat format for the specified home_id."""
        price_info = await self.async_get_price_info(home_id)
        daily_rating = await self.async_get_daily_price_rating(home_id)
        hourly_rating = await self.async_get_hourly_price_rating(home_id)
        monthly_rating = await self.async_get_monthly_price_rating(home_id)
        price_rating = {
            "thresholdPercentages": daily_rating["priceRating"].get("thresholdPercentages"),
            "daily": daily_rating["priceRating"].get("daily", []),
            "hourly": hourly_rating["priceRating"].get("hourly", []),
            "monthly": monthly_rating["priceRating"].get("monthly", []),
            "currency": (
                daily_rating["priceRating"].get("currency")
                or hourly_rating["priceRating"].get("currency")
                or monthly_rating["priceRating"].get("currency")
            ),
        }
        return {
            "priceInfo": price_info["priceInfo"],
            "priceRating": price_rating,
        }

    async def async_set_title(self, value: str) -> Any:
        """Get data from the API."""
        return await self._api_wrapper(
            data={"title": value},
        )

    async def _make_request(
        self,
        headers: dict[str, str],
        data: dict,
        query_type: QueryType,
    ) -> dict:
        """Make an API request with proper error handling."""
        _LOGGER.debug("Making API request with data: %s", data)

        response = await self._session.request(
            method="POST",
            url="https://api.tibber.com/v1-beta/gql",
            headers=headers,
            json=data,
        )

        _verify_response_or_raise(response)
        response_json = await response.json()
        _LOGGER.debug("Received API response: %s", response_json)

        await _verify_graphql_response(response_json, query_type)

        return response_json["data"]

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

            async with async_timeout.timeout(10):
                self._last_request_time = dt_util.now()
                return await self._make_request(
                    headers,
                    data or {},
                    query_type,
                )

    async def _api_wrapper(
        self,
        data: dict | None = None,
        headers: dict | None = None,
        query_type: QueryType = QueryType.VIEWER,
    ) -> Any:
        """Get information from the API with rate limiting and retry logic."""
        headers = headers or _prepare_headers(self._access_token)
        last_error: Exception | None = None

        for retry in range(self._max_retries + 1):
            try:
                return await self._handle_request(
                    headers,
                    data or {},
                    query_type,
                )

            except TibberPricesApiClientAuthenticationError:
                raise
            except (
                aiohttp.ClientError,
                socket.gaierror,
                TimeoutError,
                TibberPricesApiClientError,
            ) as error:
                last_error = (
                    error
                    if isinstance(error, TibberPricesApiClientError)
                    else TibberPricesApiClientError(
                        TibberPricesApiClientError.GENERIC_ERROR.format(exception=str(error))
                    )
                )

                if retry < self._max_retries:
                    delay = self._retry_delay * (2**retry)
                    _LOGGER.warning(
                        "Request failed, attempt %d/%d. Retrying in %d seconds: %s",
                        retry + 1,
                        self._max_retries,
                        delay,
                        str(error),
                    )
                    await asyncio.sleep(delay)
                    continue

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
