"""Trend attribute builders for Tibber Prices sensors."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator.time_service import TimeService

from .timing import add_period_timing_attributes
from .volatility import add_volatility_attributes


def _add_timing_or_volatility_attributes(
    attributes: dict,
    key: str,
    cached_data: dict,
    native_value: Any = None,
    *,
    time: TimeService,
) -> None:
    """Add attributes for timing or volatility sensors."""
    if key.endswith("_volatility"):
        add_volatility_attributes(attributes=attributes, cached_data=cached_data, time=time)
    else:
        add_period_timing_attributes(attributes=attributes, key=key, state_value=native_value, time=time)


def _add_cached_trend_attributes(attributes: dict, key: str, cached_data: dict) -> None:
    """Add cached trend attributes if available."""
    if key.startswith("price_trend_") and cached_data.get("trend_attributes"):
        attributes.update(cached_data["trend_attributes"])
    elif key == "current_price_trend" and cached_data.get("current_trend_attributes"):
        # Add cached attributes (timestamp already set by platform)
        attributes.update(cached_data["current_trend_attributes"])
    elif key == "next_price_trend_change" and cached_data.get("trend_change_attributes"):
        # Add cached attributes (timestamp already set by platform)
        # State contains the timestamp of the trend change itself
        attributes.update(cached_data["trend_change_attributes"])
