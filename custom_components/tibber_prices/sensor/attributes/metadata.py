"""Metadata attribute builders for Tibber Prices sensors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.tibber_prices.utils.price import find_price_data_for_interval
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator.core import (
        TibberPricesDataUpdateCoordinator,
    )


def get_current_interval_data(
    coordinator: TibberPricesDataUpdateCoordinator,
) -> dict | None:
    """
    Get the current price interval data.

    Args:
        coordinator: The data update coordinator

    Returns:
        Current interval data dict, or None if unavailable

    """
    if not coordinator.data:
        return None

    price_info = coordinator.data.get("priceInfo", {})
    now = dt_util.now()

    return find_price_data_for_interval(price_info, now)
