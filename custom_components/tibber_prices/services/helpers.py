"""
Shared utilities for service handlers.

This module provides common helper functions used across multiple service handlers,
such as entry validation and data extraction.

Functions:
    resolve_entry_id: Auto-resolve entry_id when only one config entry exists
    get_entry_and_data: Validate config entry and extract coordinator data

Used by:
    - services/chartdata.py: Chart data export service
    - services/apexcharts.py: ApexCharts YAML generation
    - services/refresh_user_data.py: User data refresh
    - services/find_best_start.py: Find best start time
    - services/plan_charging.py: Plan charging

"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from custom_components.tibber_prices.const import DOMAIN
from custom_components.tibber_prices.coordinator.helpers import get_intervals_for_day_offsets
from homeassistant.exceptions import ServiceValidationError

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator import TibberPricesDataUpdateCoordinator
    from homeassistant.core import HomeAssistant


def resolve_entry_id(hass: HomeAssistant, entry_id: str | None) -> str:
    """
    Resolve entry_id, auto-selecting if only one config entry exists.

    This provides a user-friendly experience where entry_id is optional
    when only a single Tibber home is configured.

    Args:
        hass: Home Assistant instance
        entry_id: Config entry ID (optional)

    Returns:
        Resolved entry_id string

    Raises:
        ServiceValidationError: If no entries exist or multiple entries exist without entry_id

    """
    entries = hass.config_entries.async_entries(DOMAIN)

    if not entries:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="no_entries_configured")

    # If entry_id provided, use it (will be validated by get_entry_and_data)
    if entry_id:
        return entry_id

    # Auto-select if only one entry exists
    if len(entries) == 1:
        return entries[0].entry_id

    # Multiple entries: require explicit entry_id
    # Build a helpful error message listing available entries
    entry_list = ", ".join(f"{e.title} ({e.entry_id})" for e in entries)
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="multiple_entries_require_entry_id",
        translation_placeholders={"entries": entry_list},
    )


def get_entry_and_data(hass: HomeAssistant, entry_id: str | None) -> tuple[Any, Any, dict]:
    """
    Validate entry and extract coordinator and data.

    If entry_id is None or empty, auto-resolves when only one entry exists.

    Args:
        hass: Home Assistant instance
        entry_id: Config entry ID to validate (optional if single entry)

    Returns:
        Tuple of (entry, coordinator, data)

    Raises:
        ServiceValidationError: If entry_id cannot be resolved or is invalid

    """
    # Auto-resolve entry_id if not provided
    resolved_entry_id = resolve_entry_id(hass, entry_id)

    entry = next(
        (e for e in hass.config_entries.async_entries(DOMAIN) if e.entry_id == resolved_entry_id),
        None,
    )
    if not entry or not hasattr(entry, "runtime_data") or not entry.runtime_data:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="invalid_entry_id")
    coordinator = entry.runtime_data.coordinator
    data = coordinator.data or {}
    return entry, coordinator, data


def has_tomorrow_data(coordinator: TibberPricesDataUpdateCoordinator) -> bool:
    """
    Check if tomorrow's price data is available in coordinator.

    Uses get_intervals_for_day_offsets() to automatically determine tomorrow
    based on current date.

    Args:
        coordinator: TibberPricesDataUpdateCoordinator instance

    Returns:
        True if tomorrow's data exists (at least one interval), False otherwise

    """
    coordinator_data = coordinator.data or {}
    tomorrow_intervals = get_intervals_for_day_offsets(coordinator_data, [1])
    return len(tomorrow_intervals) > 0
