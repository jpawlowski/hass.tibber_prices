"""Helper functions for sensor attributes."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from custom_components.tibber_prices.data import TibberPricesConfigEntry


def add_alternate_average_attribute(
    attributes: dict,
    cached_data: dict,
    base_key: str,
    *,
    config_entry: TibberPricesConfigEntry,  # noqa: ARG001
) -> None:
    """
    Add both average values (mean and median) as attributes.

    This ensures automations work consistently regardless of which value
    is displayed in the state. Both values are always available as attributes.

    Note: To avoid duplicate recording, the value used as state should be
    excluded from recorder via dynamic _unrecorded_attributes in sensor core.

    Args:
        attributes: Dictionary to add attribute to
        cached_data: Cached calculation data containing mean/median values
        base_key: Base key for cached values (e.g., "average_price_today", "rolling_hour_0")
        config_entry: Config entry for user preferences (used to determine which value is in state)

    """
    # Always add both mean and median values as attributes
    mean_value = cached_data.get(f"{base_key}_mean")
    if mean_value is not None:
        attributes["price_mean"] = mean_value

    median_value = cached_data.get(f"{base_key}_median")
    if median_value is not None:
        attributes["price_median"] = median_value
