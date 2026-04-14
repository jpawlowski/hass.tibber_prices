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
    get_price_round_decimals,
)
from custom_components.tibber_prices.coordinator.helpers import get_intervals_for_day_offsets
from custom_components.tibber_prices.entity_utils import add_icon_color_attribute, find_rolling_hour_center_index
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
        decimals = get_price_round_decimals(self.config_entry)
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
            "price_spread": round(spread_display, decimals),
            "price_min": round(price_min * factor, decimals),
            "price_max": round(price_max * factor, decimals),
            "price_mean": round(price_mean * factor, decimals),
        }

        # Add IQR attributes when enough data is available (stay in price_* group)
        if iqr_stats is not None:
            attrs["price_median"] = round(iqr_stats["median"] * factor, decimals)
            attrs["price_q25"] = round(iqr_stats["q25"] * factor, decimals)
            attrs["price_q75"] = round(iqr_stats["q75"] * factor, decimals)
            attrs["price_typical_spread"] = round(iqr_stats["iqr"] * factor, decimals)
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

    def get_percentile_rank_value(
        self,
        *,
        percentile_type: str,
        subject: str = "current_interval",
    ) -> float | None:
        """
        Calculate the percentile rank of a subject price within a reference set.

        The result is 0-100: percentage of reference prices strictly cheaper than
        the subject price. 0% = cheapest, ~99% = most expensive.

        Also stores detailed attributes in self._last_percentile_rank_attributes
        for use in extra_state_attributes.

        Args:
            percentile_type: Reference window - one of "today", "tomorrow", "today_tomorrow".
            subject: Price to rank - one of "current_interval" (default), "next_interval",
                     "previous_interval", "current_hour", "next_hour".

        Returns:
            Percentile rank (0.0-100.0) or None if unavailable.

        """
        if not self.has_data():
            return None

        # Get the price of the subject to rank
        subject_price = self._get_subject_price(subject)
        if subject_price is None:
            return None

        # Get reference prices for this type (reuse volatility helper)
        reference_prices = get_prices_for_volatility(
            percentile_type,
            self.coordinator.data,
            time=self.coordinator.time,
        )
        if not reference_prices:
            return None

        # Calculate percentile rank
        rank = calculate_percentile_rank(subject_price, reference_prices)
        if rank is None:
            return None

        # Convert to display units for attribute storage
        factor = get_display_unit_factor(self.config_entry)
        decimals = get_price_round_decimals(self.config_entry)
        price_attr_key = self._get_subject_price_attr_key(subject)

        self._last_percentile_rank_attributes = {
            price_attr_key: round(subject_price * factor, decimals),
            "prices_below_count": bisect.bisect_left(sorted(reference_prices), subject_price),
            "interval_count": len(reference_prices),
            "reference_min": round(min(reference_prices) * factor, decimals),
            "reference_max": round(max(reference_prices) * factor, decimals),
            "reference_mean": round(calculate_mean(reference_prices) * factor, decimals),
        }

        return rank

    def _get_subject_price(self, subject: str) -> float | None:
        """
        Get the price of the subject to rank.

        Args:
            subject: One of "current_interval", "next_interval", "previous_interval",
                     "current_hour", "next_hour".

        Returns:
            Price as float or None if unavailable.

        """
        if subject == "current_interval":
            interval = self.find_interval_at_offset(0)
        elif subject == "next_interval":
            interval = self.find_interval_at_offset(1)
        elif subject == "previous_interval":
            interval = self.find_interval_at_offset(-1)
        elif subject in ("current_hour", "next_hour"):
            hour_offset = 0 if subject == "current_hour" else 1
            return self._get_rolling_hour_avg_price(hour_offset)
        else:
            return None

        if interval is None:
            return None
        raw = interval.get("total")
        return float(raw) if raw is not None else None

    def _get_subject_price_attr_key(self, subject: str) -> str:
        """Return the attribute key name for the subject's price."""
        return {
            "current_interval": "current_price",
            "next_interval": "next_price",
            "previous_interval": "previous_price",
            "current_hour": "current_hour_avg_price",
            "next_hour": "next_hour_avg_price",
        }.get(subject, "ranked_price")

    def _get_rolling_hour_avg_price(self, hour_offset: int) -> float | None:
        """
        Get the rolling 1h average price for the given hour offset.

        Uses the same 5-interval window as current_hour_average_price.

        Args:
            hour_offset: 0 for current hour, 1 for next hour.

        Returns:
            Average price as float or None if unavailable.

        """
        all_prices = get_intervals_for_day_offsets(self.coordinator_data, [-1, 0, 1])
        if not all_prices:
            return None

        time = self.coordinator.time
        now = time.now()
        center_idx = find_rolling_hour_center_index(all_prices, now, hour_offset, time=time)
        if center_idx is None:
            return None

        window: list[float] = []
        for offset in range(-2, 3):
            idx = center_idx + offset
            if 0 <= idx < len(all_prices):
                raw = all_prices[idx].get("total")
                if raw is not None:
                    window.append(float(raw))

        return calculate_mean(window) if window else None

    def get_percentile_rank_attributes(self) -> dict[str, Any]:
        """
        Get stored percentile rank attributes from last calculation.

        Returns:
            Dictionary of percentile rank attributes, or empty dict if no calculation yet.

        """
        return self._last_percentile_rank_attributes
