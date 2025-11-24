"""GraphQL queries and query types for Tibber API."""

from __future__ import annotations

from enum import Enum


class TibberPricesQueryType(Enum):
    """
    Types of queries that can be made to the API.

    CRITICAL: Query type selection is dictated by Tibber's API design and caching strategy.

    PRICE_INFO:
        - Used for current day-relative data (day before yesterday/yesterday/today/tomorrow)
        - API automatically determines "today" and "tomorrow" based on current time
        - MUST be used when querying any data from these 4 days, even if you only need
          specific intervals, because Tibber's API requires this endpoint for current data
        - Provides the core dataset needed for live data, recent historical context
          (important until tomorrow's data arrives), and tomorrow's forecast
        - Tibber likely has optimized caching for this frequently-accessed data range

    PRICE_INFO_RANGE:
        - Used for historical data older than day before yesterday
        - Allows flexible date range queries with cursor-based pagination
        - Required for any intervals beyond the 4-day window of PRICE_INFO
        - Use this for historical analysis, comparisons, or trend calculations

    USER:
        - Fetches user account data and home metadata
        - Separate from price data queries

    """

    PRICE_INFO = "price_info"
    PRICE_INFO_RANGE = "price_info_range"
    USER = "user"
