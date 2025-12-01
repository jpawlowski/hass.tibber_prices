"""
Shared utilities for service handlers.

This module provides common helper functions used across multiple service handlers,
such as entry validation and data extraction.

Functions:
    get_entry_and_data: Validate config entry and extract coordinator data

Used by:
    - services/chartdata.py: Chart data export service
    - services/apexcharts.py: ApexCharts YAML generation
    - services/refresh_user_data.py: User data refresh

"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from custom_components.tibber_prices.const import DOMAIN
from custom_components.tibber_prices.coordinator.helpers import get_intervals_for_day_offsets
from homeassistant.exceptions import ServiceValidationError

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator import TibberPricesDataUpdateCoordinator
    from homeassistant.core import HomeAssistant


def get_entry_and_data(hass: HomeAssistant, entry_id: str) -> tuple[Any, Any, dict]:
    """
    Validate entry and extract coordinator and data.

    Args:
        hass: Home Assistant instance
        entry_id: Config entry ID to validate

    Returns:
        Tuple of (entry, coordinator, data)

    Raises:
        ServiceValidationError: If entry_id is missing or invalid

    """
    if not entry_id:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="missing_entry_id")
    entry = next(
        (e for e in hass.config_entries.async_entries(DOMAIN) if e.entry_id == entry_id),
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
