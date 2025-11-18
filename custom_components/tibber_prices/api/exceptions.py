"""Custom exceptions for API client."""

from __future__ import annotations


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
