"""
Tibber GraphQL API client package.

This package handles all communication with Tibber's GraphQL API:
- GraphQL query construction and execution
- Authentication and session management
- Error handling and retry logic
- Response parsing and validation

Main components:
- client.py: TibberPricesApiClient (aiohttp-based GraphQL client)
- queries.py: GraphQL query definitions
- exceptions.py: API-specific error classes
- helpers.py: Response parsing utilities
"""

from .client import TibberPricesApiClient
from .exceptions import (
    TibberPricesApiClientAuthenticationError,
    TibberPricesApiClientCommunicationError,
    TibberPricesApiClientError,
    TibberPricesApiClientPermissionError,
)

__all__ = [
    "TibberPricesApiClient",
    "TibberPricesApiClientAuthenticationError",
    "TibberPricesApiClientCommunicationError",
    "TibberPricesApiClientError",
    "TibberPricesApiClientPermissionError",
]
