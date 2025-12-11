"""
Trend calculator for price trend analysis sensors.

This module handles all trend-related calculations:
- Simple price trends (1h-12h future comparison)
- Current trend with momentum analysis
- Next trend change prediction
- Trend duration tracking

Caching strategy:
- Simple trends: Cached per sensor update to ensure consistency between state and attributes
- Current trend + next change: Cached centrally for 60s to avoid duplicate calculations
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from custom_components.tibber_prices.const import get_display_unit_factor
from custom_components.tibber_prices.coordinator.helpers import get_intervals_for_day_offsets
from custom_components.tibber_prices.utils.average import calculate_next_n_hours_avg
from custom_components.tibber_prices.utils.price import (
    calculate_price_trend,
    find_price_data_for_interval,
)

from .base import TibberPricesBaseCalculator

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator import (
        TibberPricesDataUpdateCoordinator,
    )

# Constants
MIN_HOURS_FOR_LATER_HALF = 3  # Minimum hours needed to calculate later half average


class TibberPricesTrendCalculator(TibberPricesBaseCalculator):
    """
    Calculator for price trend sensors.

    Handles three types of trend analysis:
    1. Simple trends (price_trend_1h-12h): Current vs next N hours average
    2. Current trend (current_price_trend): Momentum + 3h outlook with volatility adjustment
    3. Next change (next_price_trend_change): Scan forward for trend reversal

    Caching:
    - Simple trends: Per-sensor cache (_cached_trend_value, _trend_attributes)
    - Current/Next: Centralized cache (_trend_calculation_cache) with 60s TTL
    """

    def __init__(self, coordinator: "TibberPricesDataUpdateCoordinator") -> None:
        """Initialize trend calculator with caching state."""
        super().__init__(coordinator)
        # Per-sensor trend caches (for price_trend_Nh sensors)
        self._cached_trend_value: str | None = None
        self._trend_attributes: dict[str, Any] = {}
        # Centralized trend calculation cache (for current_price_trend + next_price_trend_change)
        self._trend_calculation_cache: dict[str, Any] | None = None
        self._trend_calculation_timestamp: datetime | None = None
        # Separate attribute storage for current_price_trend and next_price_trend_change
        self._current_trend_attributes: dict[str, Any] | None = None
        self._trend_change_attributes: dict[str, Any] | None = None

    def get_price_trend_value(self, *, hours: int) -> str | None:
        """
        Calculate price trend comparing current interval vs next N hours average.

        This is for simple trend sensors (price_trend_1h through price_trend_12h).
        Results are cached per sensor to ensure consistency between state and attributes.

        Args:
            hours: Number of hours to look ahead for trend calculation

        Returns:
            Trend state: "rising" | "falling" | "stable", or None if unavailable

        """
        # Return cached value if available to ensure consistency between
        # native_value and extra_state_attributes
        if self._cached_trend_value is not None and self._trend_attributes:
            return self._cached_trend_value

        if not self.has_data():
            return None

        # Get current interval price and timestamp
        current_interval = self.coordinator.get_current_interval()
        if not current_interval or "total" not in current_interval:
            return None

        current_interval_price = float(current_interval["total"])
        time = self.coordinator.time
        current_starts_at = time.get_interval_time(current_interval)
        if current_starts_at is None:
            return None

        # Get next interval timestamp (basis for calculation)
        next_interval_start = time.get_next_interval_start()

        # Get future average price
        future_avg, _ = calculate_next_n_hours_avg(self.coordinator.data, hours, time=self.coordinator.time)
        if future_avg is None:
            return None

        # Get configured thresholds from options
        threshold_rising = self.config.get("price_trend_threshold_rising", 5.0)
        threshold_falling = self.config.get("price_trend_threshold_falling", -5.0)
        volatility_threshold_moderate = self.config.get("volatility_threshold_moderate", 15.0)
        volatility_threshold_high = self.config.get("volatility_threshold_high", 30.0)

        # Prepare data for volatility-adaptive thresholds
        today_prices = self.intervals_today
        tomorrow_prices = self.intervals_tomorrow
        all_intervals = today_prices + tomorrow_prices
        lookahead_intervals = self.coordinator.time.minutes_to_intervals(hours * 60)

        # Calculate trend with volatility-adaptive thresholds
        trend_state, diff_pct = calculate_price_trend(
            current_interval_price,
            future_avg,
            threshold_rising=threshold_rising,
            threshold_falling=threshold_falling,
            volatility_adjustment=True,  # Always enabled
            lookahead_intervals=lookahead_intervals,
            all_intervals=all_intervals,
            volatility_threshold_moderate=volatility_threshold_moderate,
            volatility_threshold_high=volatility_threshold_high,
        )

        # Determine icon color based on trend state
        icon_color = {
            "rising": "var(--error-color)",  # Red/Orange for rising prices (expensive)
            "falling": "var(--success-color)",  # Green for falling prices (cheaper)
            "stable": "var(--state-icon-color)",  # Default gray for stable prices
        }.get(trend_state, "var(--state-icon-color)")

        # Convert prices to display currency unit based on configuration
        factor = get_display_unit_factor(self.config_entry)

        # Store attributes in sensor-specific dictionary AND cache the trend value
        self._trend_attributes = {
            "timestamp": next_interval_start,
            f"trend_{hours}h_%": round(diff_pct, 1),
            f"next_{hours}h_avg": round(future_avg * factor, 2),
            "interval_count": lookahead_intervals,
            "threshold_rising": threshold_rising,
            "threshold_falling": threshold_falling,
            "icon_color": icon_color,
        }

        # Calculate additional attributes for better granularity
        if hours > MIN_HOURS_FOR_LATER_HALF:
            # Get second half average for longer periods
            later_half_avg = self._calculate_later_half_average(hours, next_interval_start)
            if later_half_avg is not None:
                self._trend_attributes[f"second_half_{hours}h_avg"] = round(later_half_avg * factor, 2)

                # Calculate incremental change: how much does the later half differ from current?
                # CRITICAL: Use abs() for negative prices and allow calculation for all non-zero prices
                # Example: current=-10, later=-5 → diff=5, pct=5/abs(-10)*100=+50% (correctly shows increase)
                if current_interval_price != 0:
                    later_half_diff = ((later_half_avg - current_interval_price) / abs(current_interval_price)) * 100
                    self._trend_attributes[f"second_half_{hours}h_diff_from_current_%"] = round(later_half_diff, 1)

        # Cache the trend value for consistency
        self._cached_trend_value = trend_state

        return trend_state

    def get_current_trend_value(self) -> str | None:
        """
        Get the current price trend that is valid until the next change.

        Uses centralized _calculate_trend_info() for consistency with next_price_trend_change sensor.

        Returns:
            Current trend state: "rising", "falling", or "stable"

        """
        trend_info = self._calculate_trend_info()

        if not trend_info:
            return None

        # Set attributes for this sensor
        self._current_trend_attributes = {
            "from_direction": trend_info["from_direction"],
            "trend_duration_minutes": trend_info["trend_duration_minutes"],
        }

        return trend_info["current_trend_state"]

    def get_next_trend_change_value(self) -> datetime | None:
        """
        Calculate when the next price trend change will occur.

        Uses centralized _calculate_trend_info() for consistency with current_price_trend sensor.

        Returns:
            Timestamp of next trend change, or None if no change expected in next 24h

        """
        trend_info = self._calculate_trend_info()

        if not trend_info:
            return None

        # Set attributes for this sensor
        self._trend_change_attributes = trend_info["trend_change_attributes"]

        return trend_info["next_change_time"]

    def get_trend_attributes(self) -> dict[str, Any]:
        """Get cached trend attributes for simple trend sensors (price_trend_Nh)."""
        return self._trend_attributes

    def get_current_trend_attributes(self) -> dict[str, Any] | None:
        """Get cached attributes for current_price_trend sensor."""
        return self._current_trend_attributes

    def get_trend_change_attributes(self) -> dict[str, Any] | None:
        """Get cached attributes for next_price_trend_change sensor."""
        return self._trend_change_attributes

    def clear_trend_cache(self) -> None:
        """Clear simple trend cache (called on coordinator update)."""
        self._cached_trend_value = None
        self._trend_attributes = {}

    def clear_calculation_cache(self) -> None:
        """Clear centralized trend calculation cache (called on coordinator update)."""
        self._trend_calculation_cache = None
        self._trend_calculation_timestamp = None

    # ========================================================================
    # PRIVATE HELPER METHODS
    # ========================================================================

    def _calculate_later_half_average(self, hours: int, next_interval_start: datetime) -> float | None:
        """
        Calculate average price for the later half of the future time window.

        This provides additional granularity by showing what happens in the second half
        of the prediction window, helping distinguish between near-term and far-term trends.

        Args:
            hours: Total hours in the prediction window
            next_interval_start: Start timestamp of the next interval

        Returns:
            Average price for the later half intervals, or None if insufficient data

        """
        if not self.has_data():
            return None

        today_prices = self.intervals_today
        tomorrow_prices = self.intervals_tomorrow
        all_prices = today_prices + tomorrow_prices

        if not all_prices:
            return None

        # Calculate which intervals belong to the later half
        time = self.coordinator.time
        total_intervals = time.minutes_to_intervals(hours * 60)
        first_half_intervals = total_intervals // 2
        interval_duration = time.get_interval_duration()
        later_half_start = next_interval_start + (interval_duration * first_half_intervals)
        later_half_end = next_interval_start + (interval_duration * total_intervals)

        # Collect prices in the later half
        later_prices = []
        for price_data in all_prices:
            starts_at = time.get_interval_time(price_data)
            if starts_at is None:
                continue

            if later_half_start <= starts_at < later_half_end:
                price = price_data.get("total")
                if price is not None:
                    later_prices.append(float(price))

        if later_prices:
            return sum(later_prices) / len(later_prices)

        return None

    def _calculate_trend_info(self) -> dict[str, Any] | None:
        """
        Centralized trend calculation for current_price_trend and next_price_trend_change sensors.

        This method calculates all trend-related information in one place to avoid duplication
        and ensure consistency between the two sensors. Results are cached per coordinator update.

        Returns:
            Dictionary with trend information for both sensors.

        """
        trend_cache_duration_seconds = 60  # Cache for 1 minute

        # Check if we have a valid cache
        time = self.coordinator.time
        now = time.now()
        if (
            self._trend_calculation_cache is not None
            and self._trend_calculation_timestamp is not None
            and (now - self._trend_calculation_timestamp).total_seconds() < trend_cache_duration_seconds
        ):
            return self._trend_calculation_cache

        # Validate coordinator data
        if not self.has_data():
            return None

        all_intervals = get_intervals_for_day_offsets(self.coordinator_data, [-1, 0, 1])
        current_interval = find_price_data_for_interval(self.coordinator.data, now, time=time)

        if not all_intervals or not current_interval:
            return None

        current_interval_start = time.get_interval_time(current_interval)

        if not current_interval_start:
            return None

        current_index = self._find_current_interval_index(all_intervals, current_interval_start)
        if current_index is None:
            return None

        # Get configured thresholds
        thresholds = self._get_thresholds_config()

        # Step 1: Calculate current momentum from trailing data (1h weighted)
        current_price = float(current_interval["total"])
        current_momentum = self._calculate_momentum(current_price, all_intervals, current_index)

        # Step 2: Calculate 3h baseline trend for comparison
        current_trend_3h = self._calculate_standard_trend(all_intervals, current_index, current_interval, thresholds)

        # Step 3: Calculate final trend FIRST (momentum + future outlook)
        min_intervals_for_trend = 4
        standard_lookahead = 12  # 3 hours
        lookahead_intervals = standard_lookahead

        # Get future data
        future_intervals = all_intervals[current_index + 1 : current_index + lookahead_intervals + 1]
        future_prices = [float(fi["total"]) for fi in future_intervals if "total" in fi]

        # Combine momentum + future outlook to get ACTUAL current trend
        if len(future_intervals) >= min_intervals_for_trend and future_prices:
            future_avg = sum(future_prices) / len(future_prices)
            current_trend_state = self._combine_momentum_with_future(
                current_momentum=current_momentum,
                current_price=current_price,
                future_avg=future_avg,
                context={
                    "all_intervals": all_intervals,
                    "current_index": current_index,
                    "lookahead_intervals": lookahead_intervals,
                    "thresholds": thresholds,
                },
            )
        else:
            # Not enough future data - use 3h baseline as fallback
            current_trend_state = current_trend_3h

        # Step 4: Find next trend change FROM the current trend state (not momentum!)
        scan_params = {
            "current_index": current_index,
            "current_trend_state": current_trend_state,  # Use FINAL trend, not momentum
            "current_interval": current_interval,
            "now": now,
        }

        next_change_time = self._scan_for_trend_change(all_intervals, scan_params, thresholds)

        # Step 5: Find when current trend started (scan backward)
        trend_start_time, from_direction = self._find_trend_start_time(
            all_intervals, current_index, current_trend_state, thresholds
        )

        # Calculate duration of current trend
        trend_duration_minutes = None
        if trend_start_time:
            time = self.coordinator.time
            # Duration is negative of minutes_until (time in the past)
            trend_duration_minutes = -int(time.minutes_until(trend_start_time))

        # Calculate minutes until change
        minutes_until_change = None
        if next_change_time:
            time = self.coordinator.time
            minutes_until_change = int(time.minutes_until(next_change_time))

        result = {
            "current_trend_state": current_trend_state,
            "next_change_time": next_change_time,
            "trend_change_attributes": self._trend_change_attributes,
            "trend_start_time": trend_start_time,
            "from_direction": from_direction,
            "trend_duration_minutes": trend_duration_minutes,
            "minutes_until_change": minutes_until_change,
        }

        # Cache the result
        self._trend_calculation_cache = result
        self._trend_calculation_timestamp = now

        return result

    def _get_thresholds_config(self) -> dict[str, float]:
        """Get configured thresholds for trend calculation."""
        return {
            "rising": self.config.get("price_trend_threshold_rising", 5.0),
            "falling": self.config.get("price_trend_threshold_falling", -5.0),
            "moderate": self.config.get("volatility_threshold_moderate", 15.0),
            "high": self.config.get("volatility_threshold_high", 30.0),
        }

    def _calculate_momentum(self, current_price: float, all_intervals: list, current_index: int) -> str:
        """
        Calculate price momentum from weighted trailing average (last 1h).

        Args:
            current_price: Current interval price
            all_intervals: All price intervals
            current_index: Index of current interval

        Returns:
            Momentum direction: "rising", "falling", or "stable"

        """
        # Look back 1 hour (4 intervals) for quick reaction
        lookback_intervals = 4
        min_intervals = 2  # Need at least 30 minutes of history

        trailing_intervals = all_intervals[max(0, current_index - lookback_intervals) : current_index]

        if len(trailing_intervals) < min_intervals:
            return "stable"  # Not enough history

        # Weighted average: newer intervals count more
        # Weights: [0.5, 0.75, 1.0, 1.25] for 4 intervals (grows linearly)
        weights = [0.5 + 0.25 * i for i in range(len(trailing_intervals))]
        trailing_prices = [float(interval["total"]) for interval in trailing_intervals if "total" in interval]

        if not trailing_prices or len(trailing_prices) != len(weights):
            return "stable"

        weighted_sum = sum(price * weight for price, weight in zip(trailing_prices, weights, strict=True))
        weighted_avg = weighted_sum / sum(weights)

        # Calculate momentum with 3% threshold
        momentum_threshold = 0.03
        diff = (current_price - weighted_avg) / weighted_avg

        if diff > momentum_threshold:
            return "rising"
        if diff < -momentum_threshold:
            return "falling"
        return "stable"

    def _combine_momentum_with_future(
        self,
        *,
        current_momentum: str,
        current_price: float,
        future_avg: float,
        context: dict,
    ) -> str:
        """
        Combine momentum analysis with future outlook to determine final trend.

        Args:
            current_momentum: Current momentum direction (rising/falling/stable)
            current_price: Current interval price
            future_avg: Average price in future window
            context: Dict with all_intervals, current_index, lookahead_intervals, thresholds

        Returns:
            Final trend direction: "rising", "falling", or "stable"

        """
        if current_momentum == "rising":
            # We're in uptrend - does it continue?
            return "rising" if future_avg >= current_price * 0.98 else "falling"

        if current_momentum == "falling":
            # We're in downtrend - does it continue?
            return "falling" if future_avg <= current_price * 1.02 else "rising"

        # current_momentum == "stable" - what's coming?
        all_intervals = context["all_intervals"]
        current_index = context["current_index"]
        lookahead_intervals = context["lookahead_intervals"]
        thresholds = context["thresholds"]

        lookahead_for_volatility = all_intervals[current_index : current_index + lookahead_intervals]
        trend_state, _ = calculate_price_trend(
            current_price,
            future_avg,
            threshold_rising=thresholds["rising"],
            threshold_falling=thresholds["falling"],
            volatility_adjustment=True,
            lookahead_intervals=lookahead_intervals,
            all_intervals=lookahead_for_volatility,
            volatility_threshold_moderate=thresholds["moderate"],
            volatility_threshold_high=thresholds["high"],
        )
        return trend_state

    def _calculate_standard_trend(
        self,
        all_intervals: list,
        current_index: int,
        current_interval: dict,
        thresholds: dict,
    ) -> str:
        """Calculate standard 3h trend as baseline."""
        min_intervals_for_trend = 4
        standard_lookahead = 12  # 3 hours

        standard_future_intervals = all_intervals[current_index + 1 : current_index + standard_lookahead + 1]

        if len(standard_future_intervals) < min_intervals_for_trend:
            return "stable"

        standard_future_prices = [float(fi["total"]) for fi in standard_future_intervals if "total" in fi]
        if not standard_future_prices:
            return "stable"

        standard_future_avg = sum(standard_future_prices) / len(standard_future_prices)
        current_price = float(current_interval["total"])

        standard_lookahead_volatility = all_intervals[current_index : current_index + standard_lookahead]
        current_trend_3h, _ = calculate_price_trend(
            current_price,
            standard_future_avg,
            threshold_rising=thresholds["rising"],
            threshold_falling=thresholds["falling"],
            volatility_adjustment=True,
            lookahead_intervals=standard_lookahead,
            all_intervals=standard_lookahead_volatility,
            volatility_threshold_moderate=thresholds["moderate"],
            volatility_threshold_high=thresholds["high"],
        )

        return current_trend_3h

    def _find_current_interval_index(self, all_intervals: list, current_interval_start: datetime) -> int | None:
        """Find the index of current interval in all_intervals list."""
        time = self.coordinator.time
        for idx, interval in enumerate(all_intervals):
            interval_start = time.get_interval_time(interval)
            if interval_start and interval_start == current_interval_start:
                return idx
        return None

    def _find_trend_start_time(
        self,
        all_intervals: list,
        current_index: int,
        current_trend_state: str,
        thresholds: dict,
    ) -> tuple[datetime | None, str | None]:
        """
        Find when the current trend started by scanning backward.

        Args:
            all_intervals: List of all price intervals
            current_index: Index of current interval
            current_trend_state: Current trend state ("rising", "falling", "stable")
            thresholds: Threshold configuration

        Returns:
            Tuple of (start_time, from_direction):
            - start_time: When current trend began, or None if at data boundary
            - from_direction: Previous trend direction, or None if unknown

        """
        intervals_in_3h = 12  # 3 hours = 12 intervals @ 15min each

        # Scan backward to find when trend changed TO current state
        time = self.coordinator.time
        for i in range(current_index - 1, max(-1, current_index - 97), -1):
            if i < 0:
                break

            interval = all_intervals[i]
            interval_start = time.get_interval_time(interval)
            if not interval_start:
                continue

            # Calculate trend at this past interval
            future_intervals = all_intervals[i + 1 : i + intervals_in_3h + 1]
            if len(future_intervals) < intervals_in_3h:
                break  # Not enough data to calculate trend

            future_prices = [float(fi["total"]) for fi in future_intervals if "total" in fi]
            if not future_prices:
                continue

            future_avg = sum(future_prices) / len(future_prices)
            price = float(interval["total"])

            # Calculate trend at this past point
            lookahead_for_volatility = all_intervals[i : i + intervals_in_3h]
            trend_state, _ = calculate_price_trend(
                price,
                future_avg,
                threshold_rising=thresholds["rising"],
                threshold_falling=thresholds["falling"],
                volatility_adjustment=True,
                lookahead_intervals=intervals_in_3h,
                all_intervals=lookahead_for_volatility,
                volatility_threshold_moderate=thresholds["moderate"],
                volatility_threshold_high=thresholds["high"],
            )

            # Check if trend was different from current trend state
            if trend_state != current_trend_state:
                # Found the change point - the NEXT interval is where current trend started
                next_interval = all_intervals[i + 1]
                trend_start = time.get_interval_time(next_interval)
                if trend_start:
                    return trend_start, trend_state

        # Reached data boundary - current trend extends beyond available data
        return None, None

    def _scan_for_trend_change(
        self,
        all_intervals: list,
        scan_params: dict,
        thresholds: dict,
    ) -> datetime | None:
        """
        Scan future intervals for trend change.

        Args:
            all_intervals: List of all price intervals
            scan_params: Dict with current_index, current_trend_state, current_interval, now
            thresholds: Dict with rising, falling, moderate, high threshold values

        Returns:
            Timestamp of next trend change, or None if no change in next 24h

        """
        time = self.coordinator.time
        intervals_in_3h = 12  # 3 hours = 12 intervals @ 15min each
        current_index = scan_params["current_index"]
        current_trend_state = scan_params["current_trend_state"]
        current_interval = scan_params["current_interval"]
        now = scan_params["now"]

        for i in range(current_index + 1, min(current_index + 97, len(all_intervals))):
            interval = all_intervals[i]
            interval_start = time.get_interval_time(interval)
            if not interval_start:
                continue

            # Skip if this interval is in the past
            if interval_start <= now:
                continue

            # Calculate trend at this future interval
            future_intervals = all_intervals[i + 1 : i + intervals_in_3h + 1]
            if len(future_intervals) < intervals_in_3h:
                break  # Not enough data to calculate trend

            future_prices = [float(fi["total"]) for fi in future_intervals if "total" in fi]
            if not future_prices:
                continue

            future_avg = sum(future_prices) / len(future_prices)
            current_price = float(interval["total"])

            # Calculate trend at this future point
            lookahead_for_volatility = all_intervals[i : i + intervals_in_3h]
            trend_state, _ = calculate_price_trend(
                current_price,
                future_avg,
                threshold_rising=thresholds["rising"],
                threshold_falling=thresholds["falling"],
                volatility_adjustment=True,
                lookahead_intervals=intervals_in_3h,
                all_intervals=lookahead_for_volatility,
                volatility_threshold_moderate=thresholds["moderate"],
                volatility_threshold_high=thresholds["high"],
            )

            # Check if trend changed from current trend state
            # We want to find ANY change from current state, including changes to/from stable
            if trend_state != current_trend_state:
                # Store details for attributes
                time = self.coordinator.time
                minutes_until = int(time.minutes_until(interval_start))

                # Convert prices to display currency unit
                factor = get_display_unit_factor(self.config_entry)

                self._trend_change_attributes = {
                    "direction": trend_state,
                    "from_direction": current_trend_state,
                    "minutes_until_change": minutes_until,
                    "current_price_now": round(float(current_interval["total"]) * factor, 2),
                    "price_at_change": round(current_price * factor, 2),
                    "avg_after_change": round(future_avg * factor, 2),
                    "trend_diff_%": round((future_avg - current_price) / current_price * 100, 1),
                }
                return interval_start

        return None
