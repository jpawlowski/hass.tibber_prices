"""GraphQL queries and query types for Tibber API."""

from __future__ import annotations

from enum import Enum


class TibberPricesQueryType(Enum):
    """Types of queries that can be made to the API."""

    PRICE_INFO = "price_info"
    DAILY_RATING = "daily"
    HOURLY_RATING = "hourly"
    MONTHLY_RATING = "monthly"
    USER = "user"
