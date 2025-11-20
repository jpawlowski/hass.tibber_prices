"""Calculator for interval-based sensors (current/next/previous interval values)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.tibber_prices.utils.price import find_price_data_for_interval

from .base import TibberPricesBaseCalculator

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator import (
        TibberPricesDataUpdateCoordinator,
    )


class TibberPricesIntervalCalculator(TibberPricesBaseCalculator):
    """
    Calculator for interval-based sensors.

    Handles sensors that retrieve values (price/level/rating) for specific intervals
    relative to the current time (current, next, previous).
    """

    def __init__(self, coordinator: TibberPricesDataUpdateCoordinator) -> None:
        """
        Initialize calculator.

        Args:
            coordinator: The data update coordinator.

        """
        super().__init__(coordinator)
        # State attributes for specific sensors
        self._last_price_level: str | None = None
        self._last_rating_level: str | None = None
        self._last_rating_difference: float | None = None

    def get_interval_value(
        self,
        *,
        interval_offset: int,
        value_type: str,
        in_euro: bool = False,
    ) -> str | float | None:
        """
        Unified method to get values (price/level/rating) for intervals with offset.

        Args:
            interval_offset: Offset from current interval (0=current, 1=next, -1=previous).
            value_type: Type of value to retrieve ("price", "level", "rating").
            in_euro: For prices only - return in EUR if True, cents if False.

        Returns:
            For "price": float in EUR or cents.
            For "level" or "rating": lowercase enum string.
            None if data unavailable.

        """
        if not self.coordinator_data:
            return None

        price_info = self.price_info
        time = self.coordinator.time
        # Use TimeService to get interval offset time
        target_time = time.get_interval_offset_time(interval_offset)

        interval_data = find_price_data_for_interval(price_info, target_time, time=time)
        if not interval_data:
            return None

        # Extract value based on type
        if value_type == "price":
            price = interval_data.get("total")
            if price is None:
                return None
            price = float(price)
            return price if in_euro else round(price * 100, 2)

        if value_type == "level":
            level = interval_data.get("level")
            return level.lower() if level else None

        # For rating: extract rating_level
        rating = interval_data.get("rating_level")
        return rating.lower() if rating else None

    def get_price_level_value(self) -> str | None:
        """
        Get the current price level value as enum string for the state.

        Stores the level in internal state for attribute building.

        Returns:
            Price level (lowercase), or None if unavailable.

        """
        current_interval_data = self.get_current_interval_data()
        if not current_interval_data or "level" not in current_interval_data:
            return None
        level = current_interval_data["level"]
        self._last_price_level = level
        # Convert API level (e.g., "NORMAL") to lowercase enum value (e.g., "normal")
        return level.lower() if level else None

    def get_rating_value(self, *, rating_type: str) -> str | None:
        """
        Get the price rating level from the current price interval in priceInfo.

        Returns the rating level enum value, and stores the original
        level and percentage difference as attributes.

        Args:
            rating_type: Must be "current" (other values return None).

        Returns:
            Rating level (lowercase), or None if unavailable.

        """
        if not self.coordinator_data or rating_type != "current":
            self._last_rating_difference = None
            self._last_rating_level = None
            return None

        time = self.coordinator.time
        now = time.now()
        price_info = self.price_info
        current_interval = find_price_data_for_interval(price_info, now, time=time)

        if current_interval:
            rating_level = current_interval.get("rating_level")
            difference = current_interval.get("difference")
            if rating_level is not None:
                self._last_rating_difference = float(difference) if difference is not None else None
                self._last_rating_level = rating_level
                # Convert API rating (e.g., "NORMAL") to lowercase enum value (e.g., "normal")
                return rating_level.lower() if rating_level else None

        self._last_rating_difference = None
        self._last_rating_level = None
        return None

    def get_current_interval_data(self) -> dict | None:
        """
        Get the price data for the current interval using coordinator utility.

        Returns:
            Dictionary with interval data, or None if unavailable.

        """
        return self.coordinator.get_current_interval()

    def get_last_price_level(self) -> str | None:
        """
        Get the last stored price level (from get_price_level_value call).

        Returns:
            Price level string, or None if no level stored.

        """
        return self._last_price_level

    def get_last_rating_level(self) -> str | None:
        """
        Get the last stored rating level (from get_rating_value call).

        Returns:
            Rating level string, or None if no level stored.

        """
        return self._last_rating_level

    def get_last_rating_difference(self) -> float | None:
        """
        Get the last stored rating difference (from get_rating_value call).

        Returns:
            Rating difference percentage, or None if no difference stored.

        """
        return self._last_rating_difference
