"""Calculator for price volatility analysis."""

from __future__ import annotations

import bisect
from typing import TYPE_CHECKING

from custom_components.tibber_prices.const import (
    CONF_VOLATILITY_THRESHOLD_HIGH,
    CONF_VOLATILITY_THRESHOLD_MODERATE,
    CONF_VOLATILITY_THRESHOLD_VERY_HIGH,
    DEFAULT_VOLATILITY_THRESHOLD_HIGH,
    DEFAULT_VOLATILITY_THRESHOLD_MODERATE,
    DEFAULT_VOLATILITY_THRESHOLD_VERY_HIGH,
    get_display_unit_factor,
)
from custom_components.tibber_prices.entity_utils import add_icon_color_attribute
from custom_components.tibber_prices.sensor.attributes import (
    add_volatility_type_attributes,
    get_prices_for_volatility,
)
from custom_components.tibber_prices.utils.average import calculate_mean
from custom_components.tibber_prices.utils.price import (
    calculate_iqr_stats,
    calculate_percentile_rank,
    calculate_volatility_with_cv,
)

from .base import TibberPricesBaseCalculator

if TYPE_CHECKING:
    from typing import Any


class TibberPricesVolatilityCalculator(TibberPricesBaseCalculator):
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
        self._last_percentile_rank_attributes: dict[str, Any] = {}

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
        if not self.has_data():
            return None

        # Get volatility thresholds from config
        thresholds = {
            "threshold_moderate": self.config.get(
                CONF_VOLATILITY_THRESHOLD_MODERATE,
                DEFAULT_VOLATILITY_THRESHOLD_MODERATE,
            ),
            "threshold_high": self.config.get(CONF_VOLATILITY_THRESHOLD_HIGH, DEFAULT_VOLATILITY_THRESHOLD_HIGH),
            "threshold_very_high": self.config.get(
                CONF_VOLATILITY_THRESHOLD_VERY_HIGH,
                DEFAULT_VOLATILITY_THRESHOLD_VERY_HIGH,
            ),
        }

        # Get prices based on volatility type
        prices_to_analyze = get_prices_for_volatility(
            volatility_type,
            self.coordinator.data,
            time=self.coordinator.time,
        )

        if not prices_to_analyze:
            return None

        # Calculate spread and basic statistics
        price_min = min(prices_to_analyze)
        price_max = max(prices_to_analyze)
        spread = price_max - price_min
        # Use arithmetic mean for volatility calculation (required for coefficient of variation)
        price_mean = calculate_mean(prices_to_analyze)

        # Convert to display currency unit based on configuration
        factor = get_display_unit_factor(self.config_entry)
        spread_display = spread * factor

        # Calculate volatility level AND coefficient of variation
        volatility, cv = calculate_volatility_with_cv(prices_to_analyze, **thresholds)

        # Calculate IQR statistics (robust to outliers)
        iqr_stats = calculate_iqr_stats(prices_to_analyze)

        # Store attributes for this sensor
        # Build attributes with all price_* together, interval_count last
        attrs: dict[str, Any] = {
            "price_volatility": volatility.lower(),
            "price_coefficient_variation_%": round(cv, 2) if cv is not None else None,
            "price_spread": round(spread_display, 2),
            "price_min": round(price_min * factor, 2),
            "price_max": round(price_max * factor, 2),
            "price_mean": round(price_mean * factor, 2),
        }

        # Add IQR attributes when enough data is available (stay in price_* group)
        if iqr_stats is not None:
            attrs["price_median"] = round(iqr_stats["median"] * factor, 2)
            attrs["price_q25"] = round(iqr_stats["q25"] * factor, 2)
            attrs["price_q75"] = round(iqr_stats["q75"] * factor, 2)
            attrs["price_typical_spread"] = round(iqr_stats["iqr"] * factor, 2)
            if iqr_stats["iqr_pct"] is not None:
                attrs["price_typical_spread_%"] = round(iqr_stats["iqr_pct"], 2)
            attrs["price_spike_count"] = iqr_stats["outlier_count"]

        attrs["interval_count"] = len(prices_to_analyze)
        self._last_volatility_attributes = attrs

        # Add icon_color for dynamic styling
        add_icon_color_attribute(self._last_volatility_attributes, key="volatility", state_value=volatility)

        # Add type-specific attributes
        add_volatility_type_attributes(
            self._last_volatility_attributes,
            volatility_type,
            self.coordinator.data,
            thresholds,
            time=self.coordinator.time,
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

    def get_percentile_rank_value(self, *, percentile_type: str) -> float | None:
        """
        Calculate the percentile rank of the current price within a reference set.

        The result is 0-100: percentage of reference prices strictly cheaper than
        the current interval price. 0% = cheapest, ~99% = most expensive.

        Also stores detailed attributes in self._last_percentile_rank_attributes
        for use in extra_state_attributes.

        Args:
            percentile_type: One of "today", "tomorrow", "today_tomorrow".

        Returns:
            Percentile rank (0.0-100.0) or None if unavailable.

        """
        if not self.has_data():
            return None

        # Get current interval price
        current_interval = self.coordinator.get_current_interval()
        if current_interval is None:
            return None
        current_price_raw = current_interval.get("total")
        if current_price_raw is None:
            return None
        current_price = float(current_price_raw)

        # Get reference prices for this type (reuse volatility helper)
        reference_prices = get_prices_for_volatility(
            percentile_type,
            self.coordinator.data,
            time=self.coordinator.time,
        )
        if not reference_prices:
            return None

        # Calculate percentile rank
        rank = calculate_percentile_rank(current_price, reference_prices)
        if rank is None:
            return None

        # Convert to display units for attribute storage
        factor = get_display_unit_factor(self.config_entry)

        self._last_percentile_rank_attributes = {
            "current_price": round(current_price * factor, 2),
            "prices_below_count": bisect.bisect_left(sorted(reference_prices), current_price),
            "interval_count": len(reference_prices),
            "reference_min": round(min(reference_prices) * factor, 2),
            "reference_max": round(max(reference_prices) * factor, 2),
            "reference_mean": round(calculate_mean(reference_prices) * factor, 2),
        }

        return rank

    def get_percentile_rank_attributes(self) -> dict[str, Any]:
        """
        Get stored percentile rank attributes from last calculation.

        Returns:
            Dictionary of percentile rank attributes, or empty dict if no calculation yet.

        """
        return self._last_percentile_rank_attributes
