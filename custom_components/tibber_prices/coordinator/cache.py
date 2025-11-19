"""Cache management for coordinator module."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, NamedTuple

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.helpers.storage import Store

    from .time_service import TimeService

_LOGGER = logging.getLogger(__name__)


class CacheData(NamedTuple):
    """Cache data structure."""

    price_data: dict[str, Any] | None
    user_data: dict[str, Any] | None
    last_price_update: datetime | None
    last_user_update: datetime | None
    last_midnight_check: datetime | None


async def load_cache(
    store: Store,
    log_prefix: str,
    *,
    time: TimeService,
) -> CacheData:
    """Load cached data from storage."""
    try:
        stored = await store.async_load()
        if stored:
            cached_price_data = stored.get("price_data")
            cached_user_data = stored.get("user_data")

            # Restore timestamps
            last_price_update = None
            last_user_update = None
            last_midnight_check = None

            if last_price_update_str := stored.get("last_price_update"):
                last_price_update = time.parse_datetime(last_price_update_str)
            if last_user_update_str := stored.get("last_user_update"):
                last_user_update = time.parse_datetime(last_user_update_str)
            if last_midnight_check_str := stored.get("last_midnight_check"):
                last_midnight_check = time.parse_datetime(last_midnight_check_str)

            _LOGGER.debug("%s Cache loaded successfully", log_prefix)
            return CacheData(
                price_data=cached_price_data,
                user_data=cached_user_data,
                last_price_update=last_price_update,
                last_user_update=last_user_update,
                last_midnight_check=last_midnight_check,
            )

        _LOGGER.debug("%s No cache found, will fetch fresh data", log_prefix)
    except OSError as ex:
        _LOGGER.warning("%s Failed to load cache: %s", log_prefix, ex)

    return CacheData(
        price_data=None,
        user_data=None,
        last_price_update=None,
        last_user_update=None,
        last_midnight_check=None,
    )


async def store_cache(
    store: Store,
    cache_data: CacheData,
    log_prefix: str,
) -> None:
    """Store cache data."""
    data = {
        "price_data": cache_data.price_data,
        "user_data": cache_data.user_data,
        "last_price_update": (cache_data.last_price_update.isoformat() if cache_data.last_price_update else None),
        "last_user_update": (cache_data.last_user_update.isoformat() if cache_data.last_user_update else None),
        "last_midnight_check": (cache_data.last_midnight_check.isoformat() if cache_data.last_midnight_check else None),
    }

    try:
        await store.async_save(data)
        _LOGGER.debug("%s Cache stored successfully", log_prefix)
    except OSError:
        _LOGGER.exception("%s Failed to store cache", log_prefix)


def is_cache_valid(
    cache_data: CacheData,
    log_prefix: str,
    *,
    time: TimeService,
) -> bool:
    """
    Validate if cached price data is still current.

    Returns False if:
    - No cached data exists
    - Cached data is from a different calendar day (in local timezone)
    - Midnight turnover has occurred since cache was saved

    """
    if cache_data.price_data is None or cache_data.last_price_update is None:
        return False

    current_local_date = time.as_local(time.now()).date()
    last_update_local_date = time.as_local(cache_data.last_price_update).date()

    if current_local_date != last_update_local_date:
        _LOGGER.debug(
            "%s Cache date mismatch: cached=%s, current=%s",
            log_prefix,
            last_update_local_date,
            current_local_date,
        )
        return False

    return True
