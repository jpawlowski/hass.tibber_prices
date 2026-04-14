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
from custom_components.tibber_prices.utils.average import calculate_median

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
        self._last_energy_mean: float | None = None
        self._last_energy_median: float | None = None
        self._last_tax_mean: float | None = None
        self._last_tax_median: float | None = None

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
            Price value in subunit currency units (cents/øre), or None if unavailable.
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
            # Compute and cache energy/tax averages for attribute builders
            self._cache_energy_tax_averages(price_intervals)
            # Convert to display currency units based on config
            avg_result = get_price_value(value, config_entry=self.coordinator.config_entry)
            median_result = (
                get_price_value(median, config_entry=self.coordinator.config_entry)
                if median is not None
                else None
            )
            return avg_result, median_result

        # Single value result (min/max functions)
        value = result

        # Store the interval with the extreme price for use in attributes
        for pi in price_intervals:
            if pi["price"] == value:
                self._last_extreme_interval = pi["interval"]
                break

        # Return in configured display currency units with configured precision
        return get_price_value(value, config_entry=self.coordinator.config_entry)

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

    def get_last_energy_tax_averages(
        self,
    ) -> tuple[float | None, float | None, float | None, float | None]:
        """
        Get cached mean and median energy and tax values from last average calculation.

        Returns:
            Tuple of (energy_mean, energy_median, tax_mean, tax_median) in base currency,
            or (None, None, None, None).

        """
        return self._last_energy_mean, self._last_energy_median, self._last_tax_mean, self._last_tax_median

    def _cache_energy_tax_averages(self, price_intervals: list[dict]) -> None:
        """Compute and cache energy/tax mean and median from price intervals."""
        energy_prices: list[float] = []
        tax_prices: list[float] = []
        for pi in price_intervals:
            interval = pi["interval"]
            energy = interval.get("energy")
            if energy is not None:
                energy_prices.append(float(energy))
            tax = interval.get("tax")
            if tax is not None:
                tax_prices.append(float(tax))

        self._last_energy_mean = sum(energy_prices) / len(energy_prices) if energy_prices else None
        self._last_energy_median = calculate_median(energy_prices) if energy_prices else None
        self._last_tax_mean = sum(tax_prices) / len(tax_prices) if tax_prices else None
        self._last_tax_median = calculate_median(tax_prices) if tax_prices else None
