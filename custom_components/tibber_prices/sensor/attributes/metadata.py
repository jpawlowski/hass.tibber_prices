"""Metadata attribute builders for Tibber Prices sensors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.tibber_prices.utils.price import find_price_data_for_interval

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator.core import (
        TibberPricesDataUpdateCoordinator,
    )
    from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService


def get_current_interval_data(
    coordinator: TibberPricesDataUpdateCoordinator,
    *,
    time: TibberPricesTimeService,
) -> dict | None:
    """
    Get current interval's price data.

    Args:
        coordinator: The data update coordinator
        time: TibberPricesTimeService instance (required)

    Returns:
        Current interval data or None if not found

    """
    if not coordinator.data:
        return None

    now = time.now()

    return find_price_data_for_interval(coordinator.data, now, time=time)
