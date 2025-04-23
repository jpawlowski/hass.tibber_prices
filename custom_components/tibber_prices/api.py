"""Tibber API Client."""

from __future__ import annotations

import asyncio
import logging
import socket
from datetime import timedelta
from enum import Enum, auto
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


class TransformMode(Enum):
    """Data transformation mode."""

    TRANSFORM = auto()  # Transform price info data
    SKIP = auto()  # Return raw data without transformation


class QueryType(Enum):
    """Types of queries that can be made to the API."""

    PRICE_INFO = "price_info"
    DAILY_RATING = "daily"
    HOURLY_RATING = "hourly"
    MONTHLY_RATING = "monthly"
    TEST = "test"


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


async def _verify_graphql_response(response_json: dict) -> None:
    """Verify the GraphQL response for errors and data completeness."""
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


def _is_data_empty(data: dict, query_type: str) -> bool:
    """
    Check if the response data is empty or incomplete.

    For price info:
    - Must have either range/edges or yesterday data
    - Must have today data
    - If neither range/edges nor yesterday data exists, data is considered empty
    - If today data is empty, data is considered empty
    - tomorrow can be empty if we have valid historical and today data

    For rating data:
    - Must have thresholdPercentages
    - Must have non-empty entries for the specific rating type
    """
    _LOGGER.debug("Checking if data is empty for query_type %s", query_type)

    try:
        subscription = data["viewer"]["homes"][0]["currentSubscription"]

        if query_type == "price_info":
            price_info = subscription["priceInfo"]

            # Check historical data (either range or yesterday)
            has_range = (
                "range" in price_info
                and price_info["range"] is not None
                and "edges" in price_info["range"]
                and price_info["range"]["edges"]
            )
            has_yesterday = (
                "yesterday" in price_info and price_info["yesterday"] is not None and len(price_info["yesterday"]) > 0
            )
            has_historical = has_range or has_yesterday

            # Check today's data
            has_today = "today" in price_info and price_info["today"] is not None and len(price_info["today"]) > 0

            # Data is empty if we don't have historical data or today's data
            is_empty = not has_historical or not has_today

            _LOGGER.debug(
                "Price info check - historical data (range: %s, yesterday: %s), today: %s, is_empty: %s",
                bool(has_range),
                bool(has_yesterday),
                bool(has_today),
                is_empty,
            )
            return is_empty

        if query_type in ["daily", "hourly", "monthly"]:
            rating = subscription["priceRating"]

            # Check threshold percentages
            has_thresholds = (
                "thresholdPercentages" in rating
                and rating["thresholdPercentages"] is not None
                and "low" in rating["thresholdPercentages"]
                and "high" in rating["thresholdPercentages"]
            )
            if not has_thresholds:
                _LOGGER.debug("Missing or invalid threshold percentages for %s rating", query_type)
                return True

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
            return is_empty

        _LOGGER.debug("Unknown query type %s, treating as non-empty", query_type)
    except (KeyError, IndexError, TypeError) as error:
        _LOGGER.debug("Error checking data emptiness: %s", error)
        return True
    else:
        return False


def _prepare_headers(access_token: str) -> dict[str, str]:
    """Prepare headers for API request."""
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "User-Agent": f"HomeAssistant/{ha_version} tibber_prices/{VERSION}",
    }


def _transform_data(data: dict, query_type: QueryType) -> dict:
    """Transform API response data based on query type."""
    if not data or "viewer" not in data:
        _LOGGER.debug("No data to transform or missing viewer key")
        return data

    _LOGGER.debug("Starting data transformation for query type %s", query_type)

    if query_type == QueryType.PRICE_INFO:
        return _transform_price_info(data)
    if query_type in (
        QueryType.DAILY_RATING,
        QueryType.HOURLY_RATING,
        QueryType.MONTHLY_RATING,
    ):
        return data
    if query_type == QueryType.TEST:
        return data

    _LOGGER.warning("Unknown query type %s, returning raw data", query_type)
    return data


def _transform_price_info(data: dict) -> dict:
    """Transform the price info data structure."""
    if not data or "viewer" not in data:
        _LOGGER.debug("No data to transform or missing viewer key")
        return data

    _LOGGER.debug("Starting price info transformation")
    price_info = data["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]

    # Get today and yesterday dates using Home Assistant's dt_util
    today_local = dt_util.now().date()
    yesterday_local = today_local - timedelta(days=1)
    _LOGGER.debug("Processing data for yesterday's date: %s", yesterday_local)

    # Transform edges data
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

    return data


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
        self._max_retries = 3
        self._retry_delay = 2

    async def async_test_connection(self) -> Any:
        """Test connection to the API."""
        return await self._api_wrapper(
            data={
                "query": """
                    query {
                        viewer {
                            name
                        }
                    }
                """
            },
            query_type=QueryType.TEST,
        )

    async def async_get_price_info(self) -> Any:
        """Get price info data including today, tomorrow and last 48 hours."""
        return await self._api_wrapper(
            data={
                "query": """
                    {viewer{homes{currentSubscription{priceInfo{
                        range(resolution:HOURLY,last:48){edges{node{
                            startsAt total energy tax level
                        }}}
                        today{startsAt total energy tax level}
                        tomorrow{startsAt total energy tax level}
                    }}}}}"""
            },
            query_type=QueryType.PRICE_INFO,
        )

    async def async_get_daily_price_rating(self) -> Any:
        """Get daily price rating data."""
        return await self._api_wrapper(
            data={
                "query": """
                    {viewer{homes{currentSubscription{priceRating{
                        thresholdPercentages{low high}
                        daily{entries{time total energy tax difference level}}
                    }}}}}"""
            },
            query_type=QueryType.DAILY_RATING,
        )

    async def async_get_hourly_price_rating(self) -> Any:
        """Get hourly price rating data."""
        return await self._api_wrapper(
            data={
                "query": """
                    {viewer{homes{currentSubscription{priceRating{
                        thresholdPercentages{low high}
                        hourly{entries{time total energy tax difference level}}
                    }}}}}"""
            },
            query_type=QueryType.HOURLY_RATING,
        )

    async def async_get_monthly_price_rating(self) -> Any:
        """Get monthly price rating data."""
        return await self._api_wrapper(
            data={
                "query": """
                    {viewer{homes{currentSubscription{priceRating{
                        thresholdPercentages{low high}
                        monthly{
                            currency
                            entries{time total energy tax difference level}
                        }
                    }}}}}"""
            },
            query_type=QueryType.MONTHLY_RATING,
        )

    async def async_get_data(self) -> Any:
        """Get all data from the API by combining multiple queries."""
        # Get all data concurrently
        price_info = await self.async_get_price_info()
        daily_rating = await self.async_get_daily_price_rating()
        hourly_rating = await self.async_get_hourly_price_rating()
        monthly_rating = await self.async_get_monthly_price_rating()

        # Extract the base paths to make the code more readable
        def get_base_path(response: dict) -> dict:
            """Get the base subscription path from the response."""
            return response["viewer"]["homes"][0]["currentSubscription"]

        def get_rating_data(response: dict) -> dict:
            """Get the price rating data from the response."""
            return get_base_path(response)["priceRating"]

        price_info_data = get_base_path(price_info)["priceInfo"]

        # Combine the results
        return {
            "data": {
                "viewer": {
                    "homes": [
                        {
                            "currentSubscription": {
                                "priceInfo": price_info_data,
                                "priceRating": {
                                    "thresholdPercentages": get_rating_data(daily_rating)["thresholdPercentages"],
                                    "daily": get_rating_data(daily_rating)["daily"],
                                    "hourly": get_rating_data(hourly_rating)["hourly"],
                                    "monthly": get_rating_data(monthly_rating)["monthly"],
                                },
                            }
                        }
                    ]
                }
            }
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

        await _verify_graphql_response(response_json)

        return _transform_data(response_json["data"], query_type)

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
                response_data = await self._make_request(
                    headers,
                    data or {},
                    query_type,
                )

                if query_type != QueryType.TEST and _is_data_empty(response_data, query_type.value):
                    _LOGGER.debug("Empty data detected for query_type: %s", query_type)
                    raise TibberPricesApiClientError(
                        TibberPricesApiClientError.EMPTY_DATA_ERROR.format(query_type=query_type.value)
                    )

                return response_data

    async def _api_wrapper(
        self,
        data: dict | None = None,
        headers: dict | None = None,
        query_type: QueryType = QueryType.TEST,
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
