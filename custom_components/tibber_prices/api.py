"""Tibber API Client."""

from __future__ import annotations

import socket
from typing import Any

import aiohttp
import async_timeout
from homeassistant.const import __version__ as ha_version


class TibberPricesApiClientError(Exception):
    """Exception to indicate a general API error."""

    UNKNOWN_ERROR = "Unknown GraphQL error"
    MALFORMED_ERROR = "Malformed GraphQL error: {error}"
    GRAPHQL_ERROR = "GraphQL error: {message}"
    GENERIC_ERROR = "Something went wrong! {exception}"


class TibberPricesApiClientCommunicationError(
    TibberPricesApiClientError,
):
    """Exception to indicate a communication error."""

    TIMEOUT_ERROR = "Timeout error fetching information - {exception}"
    CONNECTION_ERROR = "Error fetching information - {exception}"


class TibberPricesApiClientAuthenticationError(
    TibberPricesApiClientError,
):
    """Exception to indicate an authentication error."""


def _verify_response_or_raise(response: aiohttp.ClientResponse) -> None:
    """Verify that the response is valid."""
    if response.status in (401, 403):
        msg = "Invalid credentials"
        raise TibberPricesApiClientAuthenticationError(
            msg,
        )
    response.raise_for_status()


async def _verify_graphql_response(response_json: dict) -> None:
    """
    Verify the GraphQL response for errors.

    GraphQL errors follow this structure:
    {
        "errors": [{
            "message": "error message",
            "locations": [...],
            "path": [...],
            "extensions": {
                "code": "ERROR_CODE"
            }
        }]
    }
    """
    if "errors" not in response_json:
        return

    errors = response_json["errors"]
    if not errors:
        raise TibberPricesApiClientError(TibberPricesApiClientError.UNKNOWN_ERROR)

    error = errors[0]  # Take first error
    if not isinstance(error, dict):
        raise TibberPricesApiClientError(
            TibberPricesApiClientError.MALFORMED_ERROR.format(error=error)
        )

    message = error.get("message", "Unknown error")
    extensions = error.get("extensions", {})

    # Check for authentication errors first
    if extensions.get("code") == "UNAUTHENTICATED":
        raise TibberPricesApiClientAuthenticationError(message)

    # Handle all other GraphQL errors
    raise TibberPricesApiClientError(
        TibberPricesApiClientError.GRAPHQL_ERROR.format(message=message)
    )


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
                """,
            },
        )

    async def async_get_data(self) -> Any:
        """Get data from the API."""
        return await self._api_wrapper(
            data={
                "query": """
                    query {
                        viewer {
                            homes {
                                timeZone
                                currentSubscription {
                                    status
                                }
                            }
                        }
                    }
                """,
            },
        )

    async def async_set_title(self, value: str) -> Any:
        """Get data from the API."""
        return await self._api_wrapper(
            data={"title": value},
        )

    async def _api_wrapper(
        self,
        data: dict | None = None,
        headers: dict | None = None,
    ) -> Any:
        """Get information from the API."""
        try:
            async with async_timeout.timeout(10):
                headers = headers or {}
                if headers.get("Authorization") is None:
                    headers["Authorization"] = f"Bearer {self._access_token}"
                if headers.get("Accept") is None:
                    headers["Accept"] = "application/json"
                if headers.get("User-Agent") is None:
                    headers["User-Agent"] = (
                        f"HomeAssistant/{ha_version} (tibber_prices; +https://github.com/jpawlowski/hass.tibber_prices/)"
                    )
                response = await self._session.request(
                    method="POST",
                    url="https://api.tibber.com/v1-beta/gql",
                    headers=headers,
                    json=data,
                )
                _verify_response_or_raise(response)
                response_json = await response.json()
                await _verify_graphql_response(response_json)
                return response_json

        except TimeoutError as exception:
            raise TibberPricesApiClientCommunicationError(
                TibberPricesApiClientCommunicationError.TIMEOUT_ERROR.format(
                    exception=exception
                )
            ) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            raise TibberPricesApiClientCommunicationError(
                TibberPricesApiClientCommunicationError.CONNECTION_ERROR.format(
                    exception=exception
                )
            ) from exception
        except TibberPricesApiClientAuthenticationError:
            # Re-raise authentication errors directly
            raise
        except Exception as exception:  # pylint: disable=broad-except
            raise TibberPricesApiClientError(
                TibberPricesApiClientError.GENERIC_ERROR.format(exception=exception)
            ) from exception
