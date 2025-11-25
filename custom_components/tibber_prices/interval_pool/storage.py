"""Storage management for interval pool."""

from __future__ import annotations

import errno
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.storage import Store

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)
_LOGGER_DETAILS = logging.getLogger(__name__ + ".details")

# Storage version - increment when changing data structure
INTERVAL_POOL_STORAGE_VERSION = 1


def get_storage_key(entry_id: str) -> str:
    """
    Get storage key for interval pool based on config entry ID.

    Args:
        entry_id: Home Assistant config entry ID

    Returns:
        Storage key string

    """
    return f"tibber_prices.interval_pool.{entry_id}"


async def async_load_pool_state(
    hass: HomeAssistant,
    entry_id: str,
) -> dict[str, Any] | None:
    """
    Load interval pool state from storage.

    Args:
        hass: Home Assistant instance
        entry_id: Config entry ID

    Returns:
        Pool state dict or None if no cache exists

    """
    storage_key = get_storage_key(entry_id)
    store: Store = Store(hass, INTERVAL_POOL_STORAGE_VERSION, storage_key)

    try:
        stored = await store.async_load()
    except Exception:
        # Corrupted storage file, JSON parse error, or other exception
        _LOGGER.exception(
            "Failed to load interval pool storage for entry %s (corrupted file?), starting with empty pool",
            entry_id,
        )
        return None

    if stored is None:
        _LOGGER.debug("No interval pool cache found for entry %s (first run)", entry_id)
        return None

    # Validate storage structure (single-home format)
    if not isinstance(stored, dict):
        _LOGGER.warning(
            "Invalid interval pool storage structure for entry %s (not a dict), ignoring",
            entry_id,
        )
        return None

    # Check for new single-home format (version 1, home_id, fetch_groups)
    if "home_id" in stored and "fetch_groups" in stored:
        _LOGGER.debug(
            "Interval pool state loaded for entry %s (single-home format, %d fetch groups)",
            entry_id,
            len(stored.get("fetch_groups", [])),
        )
        return stored

    # Check for old multi-home format (homes dict) - treat as incompatible
    if "homes" in stored:
        _LOGGER.info(
            "Interval pool storage for entry %s uses old multi-home format (pre-2025-11-25). "
            "Treating as incompatible. Pool will rebuild from API.",
            entry_id,
        )
        return None

    # Unknown format
    _LOGGER.warning(
        "Invalid interval pool storage structure for entry %s (missing required keys), ignoring",
        entry_id,
    )
    return None


async def async_save_pool_state(
    hass: HomeAssistant,
    entry_id: str,
    pool_state: dict[str, Any],
) -> None:
    """
    Save interval pool state to storage.

    Args:
        hass: Home Assistant instance
        entry_id: Config entry ID
        pool_state: Pool state dict to save

    """
    storage_key = get_storage_key(entry_id)
    store: Store = Store(hass, INTERVAL_POOL_STORAGE_VERSION, storage_key)

    try:
        await store.async_save(pool_state)
        _LOGGER_DETAILS.debug(
            "Interval pool state saved for entry %s (%d fetch groups)",
            entry_id,
            len(pool_state.get("fetch_groups", [])),
        )
    except OSError as err:
        # Provide specific error messages based on errno
        if err.errno == errno.ENOSPC:  # Disk full
            _LOGGER.exception(
                "Cannot save interval pool storage for entry %s: Disk full!",
                entry_id,
            )
        elif err.errno == errno.EACCES:  # Permission denied
            _LOGGER.exception(
                "Cannot save interval pool storage for entry %s: Permission denied!",
                entry_id,
            )
        else:
            _LOGGER.exception(
                "Failed to save interval pool storage for entry %s",
                entry_id,
            )


async def async_remove_pool_storage(
    hass: HomeAssistant,
    entry_id: str,
) -> None:
    """
    Remove interval pool storage file.

    Used when config entry is removed.

    Args:
        hass: Home Assistant instance
        entry_id: Config entry ID

    """
    storage_key = get_storage_key(entry_id)
    store: Store = Store(hass, INTERVAL_POOL_STORAGE_VERSION, storage_key)

    try:
        await store.async_remove()
        _LOGGER.debug("Interval pool storage removed for entry %s", entry_id)
    except OSError as ex:
        _LOGGER.warning("Failed to remove interval pool storage for entry %s: %s", entry_id, ex)
