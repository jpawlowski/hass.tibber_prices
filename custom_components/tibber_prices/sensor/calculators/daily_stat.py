"""Calculator for daily statistics (min/max/avg within calendar day)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.tibber_prices.const import (
    CONF_PRICE_RATING_THRESHOLD_HIGH,
    CONF_PRICE_RATING_THRESHOLD_LOW,
    DEFAULT_PRICE_RATING_THRESHOLD_HIGH,
    DEFAULT_PRICE_RATING_THRESHOLD_LOW,
)
from custom_components.tibber_prices.entity_utils import get_price_value
from custom_components.tibber_prices.sensor.helpers import (
    aggregate_level_data,
    aggregate_rating_data,
)

from .base import TibberPricesBaseCalculator

if TYPE_CHECKING:
    from collections.abc import Callable

    from custom_components.tibber_prices.coordinator import (
        TibberPricesDataUpdateCoordinator,
    )


class TibberPricesDailyStatCalculator(TibberPricesBaseCalculator):
    """
    Calculator for daily statistics.

    Handles sensors that calculate min/max/avg prices or aggregate level/rating
    for entire calendar days (yesterday/today/tomorrow).
    """

    def __init__(self, coordinator: TibberPricesDataUpdateCoordinator) -> None:
        """
        Initialize calculator.

        Args:
            coordinator: The data update coordinator.

        """
        super().__init__(coordinator)
        self._last_extreme_interval: dict | None = None

    def get_daily_stat_value(
        self,
        *,
        day: str = "today",
        stat_func: Callable[[list[float]], float] | Callable[[list[float]], tuple[float, float | None]],
    ) -> float | tuple[float, float | None] | None:
        """
        Unified method for daily statistics (min/max/avg within calendar day).

        Calculates statistics for a specific calendar day using local timezone
        boundaries. Stores the extreme interval for use in attributes.

        Args:
            day: "today" or "tomorrow" - which calendar day to calculate for.
            stat_func: Statistical function (min, max, or lambda for avg/median).

        Returns:
            Price value in minor currency units (cents/øre), or None if unavailable.
            For average functions: tuple of (avg, median) where median may be None.
            For min/max functions: single float value.

        """
        if not self.has_data():
            return None

        # Get local midnight boundaries based on the requested day using TimeService
        time = self.coordinator.time
        local_midnight, local_midnight_next_day = time.get_day_boundaries(day)

        # Collect all prices and their intervals from both today and tomorrow data
        # that fall within the target day's local date boundaries
        price_intervals = []
        for day_offset in [0, 1]:  # today=0, tomorrow=1
            for price_data in self.get_intervals(day_offset):
                starts_at = price_data.get("startsAt")  # Already datetime in local timezone
                if not starts_at:
                    continue

                # Include price if it starts within the target day's local date boundaries
                if local_midnight <= starts_at < local_midnight_next_day:
                    total_price = price_data.get("total")
                    if total_price is not None:
                        price_intervals.append(
                            {
                                "price": float(total_price),
                                "interval": price_data,
                            }
                        )

        if not price_intervals:
            return None

        # Find the extreme value and store its interval for later use in attributes
        prices = [pi["price"] for pi in price_intervals]
        result = stat_func(prices)

        # Check if result is a tuple (avg, median) from average functions
        if isinstance(result, tuple):
            value, median = result
            # Store the interval (for avg, use first interval as reference)
            if price_intervals:
                self._last_extreme_interval = price_intervals[0]["interval"]
            # Convert both to minor currency units
            avg_result = round(get_price_value(value, in_euro=False), 2)
            median_result = round(get_price_value(median, in_euro=False), 2) if median is not None else None
            return avg_result, median_result

        # Single value result (min/max functions)
        value = result

        # Store the interval with the extreme price for use in attributes
        for pi in price_intervals:
            if pi["price"] == value:
                self._last_extreme_interval = pi["interval"]
                break

        # Always return in minor currency units (cents/øre) with 2 decimals
        result = get_price_value(value, in_euro=False)
        return round(result, 2)

    def get_daily_aggregated_value(
        self,
        *,
        day: str = "today",
        value_type: str = "level",
    ) -> str | None:
        """
        Get aggregated price level or rating for a specific calendar day.

        Aggregates all intervals within a calendar day using the same logic
        as rolling hour sensors, but for the entire day.

        Args:
            day: "yesterday", "today", or "tomorrow" - which calendar day to calculate for.
            value_type: "level" or "rating" - type of aggregation to perform.

        Returns:
            Aggregated level/rating value (lowercase), or None if unavailable.

        """
        if not self.has_data():
            return None

        # Get local midnight boundaries based on the requested day using TimeService
        time = self.coordinator.time
        local_midnight, local_midnight_next_day = time.get_day_boundaries(day)

        # Collect all intervals from both today and tomorrow data
        # that fall within the target day's local date boundaries
        day_intervals = []
        for day_offset in [-1, 0, 1]:  # yesterday=-1, today=0, tomorrow=1
            for price_data in self.get_intervals(day_offset):
                starts_at = price_data.get("startsAt")  # Already datetime in local timezone
                if not starts_at:
                    continue

                # Include interval if it starts within the target day's local date boundaries
                if local_midnight <= starts_at < local_midnight_next_day:
                    day_intervals.append(price_data)

        if not day_intervals:
            return None

        # Use the same aggregation logic as rolling hour sensors
        if value_type == "level":
            return aggregate_level_data(day_intervals)
        if value_type == "rating":
            # Get thresholds from config
            threshold_low = self.config.get(
                CONF_PRICE_RATING_THRESHOLD_LOW,
                DEFAULT_PRICE_RATING_THRESHOLD_LOW,
            )
            threshold_high = self.config.get(
                CONF_PRICE_RATING_THRESHOLD_HIGH,
                DEFAULT_PRICE_RATING_THRESHOLD_HIGH,
            )
            return aggregate_rating_data(day_intervals, threshold_low, threshold_high)

        return None

    def get_last_extreme_interval(self) -> dict | None:
        """
        Get the last stored extreme interval (from min/max calculation).

        Returns:
            Dictionary with interval data, or None if no extreme interval stored.

        """
        return self._last_extreme_interval
