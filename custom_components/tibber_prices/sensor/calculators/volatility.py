"""Calculator for price volatility analysis."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.tibber_prices.entity_utils import add_icon_color_attribute
from custom_components.tibber_prices.sensor.attributes import (
    add_volatility_type_attributes,
    get_prices_for_volatility,
)
from custom_components.tibber_prices.utils.price import calculate_volatility_level

from .base import BaseCalculator

if TYPE_CHECKING:
    from typing import Any


class VolatilityCalculator(BaseCalculator):
    """
    Calculator for price volatility analysis.

    Calculates volatility levels (low, moderate, high, very_high) using coefficient
    of variation for different time periods (today, tomorrow, next 24h, today+tomorrow).
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Initialize calculator.

        Args:
            *args: Positional arguments passed to BaseCalculator.
            **kwargs: Keyword arguments passed to BaseCalculator.

        """
        super().__init__(*args, **kwargs)
        self._last_volatility_attributes: dict[str, Any] = {}

    def get_volatility_value(self, *, volatility_type: str) -> str | None:
        """
        Calculate price volatility using coefficient of variation for different time periods.

        Also stores detailed attributes in self._last_volatility_attributes for use in
        extra_state_attributes.

        Args:
            volatility_type: One of "today", "tomorrow", "next_24h", "today_tomorrow".

        Returns:
            Volatility level: "low", "moderate", "high", "very_high", or None if unavailable.

        """
        if not self.coordinator_data:
            return None

        price_info = self.price_info

        # Get volatility thresholds from config
        thresholds = {
            "threshold_moderate": self.config.get("volatility_threshold_moderate", 5.0),
            "threshold_high": self.config.get("volatility_threshold_high", 15.0),
            "threshold_very_high": self.config.get("volatility_threshold_very_high", 30.0),
        }

        # Get prices based on volatility type
        prices_to_analyze = get_prices_for_volatility(volatility_type, price_info, time=self.coordinator.time)

        if not prices_to_analyze:
            return None

        # Calculate spread and basic statistics
        price_min = min(prices_to_analyze)
        price_max = max(prices_to_analyze)
        spread = price_max - price_min
        price_avg = sum(prices_to_analyze) / len(prices_to_analyze)

        # Convert to minor currency units (ct/øre) for display
        spread_minor = spread * 100

        # Calculate volatility level with custom thresholds (pass price list, not spread)
        volatility = calculate_volatility_level(prices_to_analyze, **thresholds)

        # Store attributes for this sensor
        self._last_volatility_attributes = {
            "price_spread": round(spread_minor, 2),
            "price_volatility": volatility,
            "price_min": round(price_min * 100, 2),
            "price_max": round(price_max * 100, 2),
            "price_avg": round(price_avg * 100, 2),
            "interval_count": len(prices_to_analyze),
        }

        # Add icon_color for dynamic styling
        add_icon_color_attribute(self._last_volatility_attributes, key="volatility", state_value=volatility)

        # Add type-specific attributes
        add_volatility_type_attributes(
            self._last_volatility_attributes, volatility_type, price_info, thresholds, time=self.coordinator.time
        )

        # Return lowercase for ENUM device class
        return volatility.lower()

    def get_volatility_attributes(self) -> dict[str, Any]:
        """
        Get stored volatility attributes from last calculation.

        Returns:
            Dictionary of volatility attributes, or empty dict if no calculation yet.

        """
        return self._last_volatility_attributes
