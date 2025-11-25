"""Interval Pool - Intelligent interval caching and routing."""

from .manager import TibberPricesIntervalPool
from .routing import get_price_intervals_for_range
from .storage import (
    INTERVAL_POOL_STORAGE_VERSION,
    async_load_pool_state,
    async_remove_pool_storage,
    async_save_pool_state,
    get_storage_key,
)

__all__ = [
    "INTERVAL_POOL_STORAGE_VERSION",
    "TibberPricesIntervalPool",
    "async_load_pool_state",
    "async_remove_pool_storage",
    "async_save_pool_state",
    "get_price_intervals_for_range",
    "get_storage_key",
]
