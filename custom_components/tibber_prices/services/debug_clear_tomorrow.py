"""
Debug service to clear tomorrow's data from the interval pool.

This service is intended for testing the tomorrow data refresh cycle without
having to wait for the next day or restart Home Assistant.

WARNING: This is a debug/development tool. Use with caution in production.

Usage:
    service: tibber_prices.debug_clear_tomorrow
    data: {}

After calling this service:
1. The tomorrow data will be removed from the interval pool
2. The lifecycle sensor will show "searching_tomorrow" (after 13:00)
3. The next Timer #1 cycle will fetch tomorrow data from the API
4. You can observe the full refresh cycle in real-time

"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from custom_components.tibber_prices.const import DOMAIN

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator import TibberPricesDataUpdateCoordinator
    from homeassistant.core import ServiceCall, ServiceResponse

_LOGGER = logging.getLogger(__name__)

DEBUG_CLEAR_TOMORROW_SERVICE_NAME = "debug_clear_tomorrow"
DEBUG_CLEAR_TOMORROW_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): str,
    }
)


async def handle_debug_clear_tomorrow(call: ServiceCall) -> ServiceResponse:
    """
    Handle the debug_clear_tomorrow service call.

    Removes tomorrow's intervals from the interval pool to allow testing
    of the tomorrow data refresh cycle.

    Returns:
        Dict with operation results (intervals removed, pool stats before/after).

    """
    hass = call.hass

    # Get entry_id from call data or use first available
    entry_id = call.data.get("entry_id")

    if entry_id:
        entry = next(
            (e for e in hass.config_entries.async_entries(DOMAIN) if e.entry_id == entry_id),
            None,
        )
    else:
        # Use first available entry
        entries = hass.config_entries.async_entries(DOMAIN)
        entry = entries[0] if entries else None

    if not entry or not hasattr(entry, "runtime_data") or not entry.runtime_data:
        return {"success": False, "error": "No valid config entry found"}

    coordinator: TibberPricesDataUpdateCoordinator = entry.runtime_data.coordinator

    # Get pool manager from coordinator
    pool = coordinator._price_data_manager._interval_pool  # noqa: SLF001

    # Get stats before
    stats_before = pool.get_pool_stats()

    # Calculate tomorrow's date range
    now = coordinator.time.now()
    now_local = coordinator.time.as_local(now)
    tomorrow_start = (now_local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_end = (now_local + timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)

    _LOGGER.info(
        "DEBUG: Clearing tomorrow's data from pool (range: %s to %s)",
        tomorrow_start.isoformat(),
        tomorrow_end.isoformat(),
    )

    # Remove tomorrow's intervals from the pool index
    removed_count = await _clear_intervals_in_range(pool, tomorrow_start.isoformat(), tomorrow_end.isoformat())

    # Also remove tomorrow's intervals from coordinator.data["priceInfo"]
    # This ensures sensors show "unknown" for tomorrow data
    removed_from_coordinator = _clear_intervals_from_coordinator(coordinator, tomorrow_start, tomorrow_end)

    # Get stats after
    stats_after = pool.get_pool_stats()

    # Force coordinator to re-check tomorrow data status and update ALL sensors
    # This updates the lifecycle sensor and makes tomorrow sensors show "unknown"
    coordinator.async_update_listeners()

    result: dict[str, Any] = {
        "success": True,
        "intervals_removed_from_pool": removed_count,
        "intervals_removed_from_coordinator": removed_from_coordinator,
        "tomorrow_range": {
            "start": tomorrow_start.isoformat(),
            "end": tomorrow_end.isoformat(),
        },
        "pool_stats_before": {
            "cache_intervals_total": stats_before.get("cache_intervals_total"),
            "cache_newest_interval": stats_before.get("cache_newest_interval"),
        },
        "pool_stats_after": {
            "cache_intervals_total": stats_after.get("cache_intervals_total"),
            "cache_newest_interval": stats_after.get("cache_newest_interval"),
        },
        "message": f"Removed {removed_count} tomorrow intervals. Next Timer #1 cycle will fetch new data.",
    }

    _LOGGER.info("DEBUG: Clear tomorrow complete - %s", result)

    return result


def _clear_intervals_from_coordinator(
    coordinator: TibberPricesDataUpdateCoordinator,
    start_dt: datetime,
    end_dt: datetime,
) -> int:
    """
    Remove intervals from coordinator.data["priceInfo"] in the given time range.

    This ensures sensors show "unknown" for the removed intervals.

    Args:
        coordinator: TibberPricesDataUpdateCoordinator instance.
        start_dt: Start datetime (inclusive).
        end_dt: End datetime (exclusive).

    Returns:
        Number of intervals removed.

    """
    if not coordinator.data or "priceInfo" not in coordinator.data:
        return 0

    price_info = coordinator.data["priceInfo"]
    original_count = len(price_info)

    # Filter out intervals in the range
    # Intervals have startsAt as datetime objects (after parse_all_timestamps)
    filtered = []
    for interval in price_info:
        starts_at = interval.get("startsAt")
        if starts_at is None:
            filtered.append(interval)
            continue

        # Handle both datetime and string formats
        starts_at_dt = datetime.fromisoformat(starts_at) if isinstance(starts_at, str) else starts_at

        # Keep intervals outside the removal range
        if starts_at_dt < start_dt or starts_at_dt >= end_dt:
            filtered.append(interval)

    # Update coordinator.data in place
    coordinator.data["priceInfo"] = filtered

    removed_count = original_count - len(filtered)
    _LOGGER.debug(
        "DEBUG: Removed %d intervals from coordinator.data (had %d, now %d)",
        removed_count,
        original_count,
        len(filtered),
    )

    return removed_count


async def _clear_intervals_in_range(
    pool: Any,
    start_iso: str,
    end_iso: str,
) -> int:
    """
    Remove intervals in the given time range from the pool.

    This manipulates the pool's internal cache to remove specific intervals.
    Used only for debug/testing purposes.

    Args:
        pool: IntervalPoolManager instance.
        start_iso: ISO timestamp string (inclusive).
        end_iso: ISO timestamp string (exclusive).

    Returns:
        Number of intervals removed.

    """
    # Access internal index
    index = pool._index  # noqa: SLF001

    # Parse range
    start_dt = datetime.fromisoformat(start_iso)
    end_dt = datetime.fromisoformat(end_iso)

    # Find all timestamps in range
    removed_count = 0
    current_dt = start_dt

    while current_dt < end_dt:
        current_key = current_dt.isoformat()[:19]

        # Check if this timestamp exists in index
        location = index.get(current_key)
        if location is not None:
            # Remove from index
            index.remove(current_key)
            removed_count += 1

        # Move to next 15-min interval
        current_dt += timedelta(minutes=15)

    # Note: We only remove from the index, not from the fetch_groups.
    # The intervals will remain in fetch_groups but won't be found via index lookup.
    # This is simpler and safe - GC will clean up orphaned intervals eventually.

    # Persist the updated pool state via manager's save method
    await pool._auto_save_pool_state()  # noqa: SLF001

    return removed_count
