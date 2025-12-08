"""Helper functions for sensor attributes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.tibber_prices.const import (
    CONF_AVERAGE_SENSOR_DISPLAY,
    DEFAULT_AVERAGE_SENSOR_DISPLAY,
)

if TYPE_CHECKING:
    from custom_components.tibber_prices.data import TibberPricesConfigEntry


def add_alternate_average_attribute(
    attributes: dict,
    cached_data: dict,
    base_key: str,
    *,
    config_entry: TibberPricesConfigEntry,
) -> None:
    """
    Add the alternate average value (mean or median) as attribute.

    If user selected "median" as state display, adds "price_mean" as attribute.
    If user selected "mean" as state display, adds "price_median" as attribute.

    Args:
        attributes: Dictionary to add attribute to
        cached_data: Cached calculation data containing mean/median values
        base_key: Base key for cached values (e.g., "average_price_today", "rolling_hour_0")
        config_entry: Config entry for user preferences

    """
    # Get user preference for which value to display in state
    display_mode = config_entry.options.get(
        CONF_AVERAGE_SENSOR_DISPLAY,
        DEFAULT_AVERAGE_SENSOR_DISPLAY,
    )

    # Add the alternate value as attribute
    if display_mode == "median":
        # State shows median → add mean as attribute
        mean_value = cached_data.get(f"{base_key}_mean")
        if mean_value is not None:
            attributes["price_mean"] = mean_value
    else:
        # State shows mean → add median as attribute
        median_value = cached_data.get(f"{base_key}_median")
        if median_value is not None:
            attributes["price_median"] = median_value
