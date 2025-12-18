"""Calculator for rolling hour average values (5-interval windows)."""

from __future__ import annotations

from custom_components.tibber_prices.const import (
    CONF_PRICE_RATING_THRESHOLD_HIGH,
    CONF_PRICE_RATING_THRESHOLD_LOW,
    DEFAULT_PRICE_RATING_THRESHOLD_HIGH,
    DEFAULT_PRICE_RATING_THRESHOLD_LOW,
)
from custom_components.tibber_prices.coordinator.helpers import get_intervals_for_day_offsets
from custom_components.tibber_prices.entity_utils import find_rolling_hour_center_index
from custom_components.tibber_prices.sensor.helpers import (
    aggregate_average_data,
    aggregate_level_data,
    aggregate_rating_data,
)

from .base import TibberPricesBaseCalculator


class TibberPricesRollingHourCalculator(TibberPricesBaseCalculator):
    """
    Calculator for rolling hour values (5-interval windows).

    Handles sensors that aggregate data from a 5-interval window (60 minutes):
    2 intervals before + center interval + 2 intervals after.
    """

    def get_rolling_hour_value(
        self,
        *,
        hour_offset: int = 0,
        value_type: str = "price",
    ) -> str | float | tuple[float | None, float | None] | None:
        """
        Unified method to get aggregated values from 5-interval rolling window.

        Window: 2 before + center + 2 after = 5 intervals (60 minutes total).

        Args:
            hour_offset: 0 (current hour), 1 (next hour), etc.
            value_type: "price" | "level" | "rating".

        Returns:
            Aggregated value based on type:
            - "price": float or tuple[float, float | None] (avg, median)
            - "level": str (aggregated level: "very_cheap", "cheap", etc.)
            - "rating": str (aggregated rating: "low", "normal", "high")

        """
        if not self.has_data():
            return None

        # Get all available price data (yesterday, today, tomorrow)
        all_prices = get_intervals_for_day_offsets(self.coordinator_data, [-1, 0, 1])

        if not all_prices:
            return None

        # Find center index for the rolling window
        time = self.coordinator.time
        now = time.now()
        center_idx = find_rolling_hour_center_index(all_prices, now, hour_offset, time=time)
        if center_idx is None:
            return None

        # Collect data from 5-interval window (-2, -1, 0, +1, +2)
        window_data = []
        for offset in range(-2, 3):
            idx = center_idx + offset
            if 0 <= idx < len(all_prices):
                window_data.append(all_prices[idx])

        if not window_data:
            return None

        return self.aggregate_window_data(window_data, value_type)

    def aggregate_window_data(
        self,
        window_data: list[dict],
        value_type: str,
    ) -> str | float | tuple[float | None, float | None] | None:
        """
        Aggregate data from multiple intervals based on value type.

        Args:
            window_data: List of price interval dictionaries.
            value_type: "price" | "level" | "rating".

        Returns:
            Aggregated value based on type:
            - "price": tuple[float, float | None] (avg, median)
            - "level": str
            - "rating": str

        """
        # Get thresholds from config for rating aggregation
        threshold_low = self.config.get(
            CONF_PRICE_RATING_THRESHOLD_LOW,
            DEFAULT_PRICE_RATING_THRESHOLD_LOW,
        )
        threshold_high = self.config.get(
            CONF_PRICE_RATING_THRESHOLD_HIGH,
            DEFAULT_PRICE_RATING_THRESHOLD_HIGH,
        )

        # Handle price aggregation - return tuple directly
        if value_type == "price":
            return aggregate_average_data(window_data, self.config_entry)

        # Map other value types to aggregation functions
        aggregators = {
            "level": lambda data: aggregate_level_data(data),
            "rating": lambda data: aggregate_rating_data(data, threshold_low, threshold_high),
        }

        aggregator = aggregators.get(value_type)
        if aggregator:
            return aggregator(window_data)
        return None
