"""Calculator for 24-hour sliding window statistics."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.tibber_prices.entity_utils import get_price_value

from .base import BaseCalculator

if TYPE_CHECKING:
    from collections.abc import Callable


class Window24hCalculator(BaseCalculator):
    """
    Calculator for 24-hour sliding window statistics.

    Handles sensors that calculate statistics over a 24-hour window relative to
    the current interval (trailing = previous 24h, leading = next 24h).
    """

    def get_24h_window_value(
        self,
        *,
        stat_func: Callable,
    ) -> float | None:
        """
        Unified method for 24-hour sliding window statistics.

        Calculates statistics over a 24-hour window relative to the current interval:
        - "trailing": Previous 24 hours (96 intervals before current)
        - "leading": Next 24 hours (96 intervals after current)

        Args:
            stat_func: Function from average_utils (e.g., calculate_current_trailing_avg).

        Returns:
            Price value in minor currency units (cents/øre), or None if unavailable.

        """
        if not self.coordinator_data:
            return None

        value = stat_func(self.coordinator_data, time=self.coordinator.time)

        if value is None:
            return None

        # Always return in minor currency units (cents/øre) with 2 decimals
        result = get_price_value(value, in_euro=False)
        return round(result, 2)
