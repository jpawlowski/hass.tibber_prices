"""
Trend calculator for price trend analysis sensors.

This module handles all trend-related calculations:
- Price outlook (1h-12h): Current price vs average of the next N hours
- Price trajectory (2h-12h): First-half vs second-half average in the window (shows turning points)
- Current trend (pure future-based 3h outlook with volatility adjustment)
- Next trend change prediction (with configurable N-interval hysteresis, default 3)
- Trend duration tracking (lightweight price direction scan with noise tolerance)

Caching strategy:
- Outlook/Trajectory: Cached per sensor update to ensure consistency between state and attributes
- Current trend + next change: Cached centrally for 60s to avoid duplicate calculations
"""

from typing import TYPE_CHECKING, Any, ClassVar

from custom_components.tibber_prices.const import (
    get_display_unit_factor,
    get_price_round_decimals,
)
from custom_components.tibber_prices.coordinator.helpers import get_intervals_for_day_offsets
from custom_components.tibber_prices.utils.average import calculate_mean, calculate_next_n_hours_mean
from custom_components.tibber_prices.utils.price import (
    calculate_price_trend,
    find_price_data_for_interval,
)

from .base import TibberPricesBaseCalculator

if TYPE_CHECKING:
    from datetime import datetime

    from custom_components.tibber_prices.coordinator import (
        TibberPricesDataUpdateCoordinator,
    )

# Constants
MIN_HOURS_FOR_LATER_HALF = 1  # Minimum hours needed to calculate half-window averages (activates at 2h+)


class TibberPricesTrendCalculator(TibberPricesBaseCalculator):
    """
    Calculator for price trend sensors.

    Handles three types of trend analysis:
    1. Outlook sensors (price_outlook_1h-12h): Current vs next N hours average
    2. Trajectory sensors (price_trajectory_2h-12h): First half vs second half of window
    3. Current trend (current_price_trend): Pure future-based 3h outlook with volatility adjustment
    4. Next change (next_price_trend_change): Scan forward with configurable N-interval hysteresis (default 3)

    Caching:
    - Simple trends: Per-sensor cache (_cached_trend_value, _trend_attributes)
    - Current/Next: Centralized cache (_trend_calculation_cache) with 60s TTL
    """

    # Direction groups for trend change detection.
    # Only GROUP changes count as trend changes (not intensity changes within a group).
    # E.g., rising → strongly_rising is NOT a change; rising → stable IS a change.
    _DIRECTION_GROUPS: ClassVar[dict[str, str]] = {
        "strongly_falling": "falling",
        "falling": "falling",
        "stable": "stable",
        "rising": "rising",
        "strongly_rising": "rising",
    }

    def __init__(self, coordinator: "TibberPricesDataUpdateCoordinator") -> None:
        """Initialize trend calculator with caching state."""
        super().__init__(coordinator)
        # Per-sensor caches (for price_outlook_Xh and price_trajectory_Xh sensors)
        self._cached_trend_value: str | None = None
        self._trend_attributes: dict[str, Any] = {}
        self._trajectory_attributes: dict[str, Any] = {}
        # Centralized trend calculation cache (for current_price_trend + next_price_trend_change)
        self._trend_calculation_cache: dict[str, Any] | None = None
        self._trend_calculation_timestamp: datetime | None = None
        # Separate attribute storage for current_price_trend and next_price_trend_change
        self._current_trend_attributes: dict[str, Any] | None = None
        self._trend_change_attributes: dict[str, Any] | None = None

    def get_price_outlook_value(self, *, hours: int) -> str | None:
        """
        Calculate price outlook comparing current interval vs average of the next N hours.

        This is for price_outlook_Xh sensors. Answers: "Is the average of the next Xh
        cheaper or more expensive than right now?"
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

        # Get future mean price (ignore median for trend calculation)
        future_mean, _ = calculate_next_n_hours_mean(self.coordinator.data, hours, time=self.coordinator.time)
        if future_mean is None:
            return None

        # Get configured thresholds from options
        threshold_rising = self.config.get("price_trend_threshold_rising", 3.0)
        threshold_falling = self.config.get("price_trend_threshold_falling", -3.0)
        threshold_strongly_rising = self.config.get("price_trend_threshold_strongly_rising", 9.0)
        threshold_strongly_falling = self.config.get("price_trend_threshold_strongly_falling", -9.0)
        volatility_threshold_moderate = self.config.get("volatility_threshold_moderate", 15.0)
        volatility_threshold_high = self.config.get("volatility_threshold_high", 30.0)

        # Minimum absolute price change thresholds (noise floor)
        # Config values are stored in base currency (EUR/NOK) - no conversion needed
        min_abs_diff = self.config.get("price_trend_min_price_change", 0.005)
        min_abs_diff_strongly = self.config.get("price_trend_min_price_change_strongly", 0.015)

        # Prepare data for volatility-adaptive thresholds
        today_prices = self.intervals_today
        tomorrow_prices = self.intervals_tomorrow
        all_intervals = today_prices + tomorrow_prices
        lookahead_intervals = self.coordinator.time.minutes_to_intervals(hours * 60)

        # Find current interval index to slice correct volatility window.
        # Without this, _calculate_lookahead_volatility_factor() would analyze prices
        # from the start of the day instead of the actual lookahead window.
        current_idx = None
        for idx, interval in enumerate(all_intervals):
            if time.get_interval_time(interval) == current_starts_at:
                current_idx = idx
                break

        if current_idx is not None:
            volatility_window = all_intervals[current_idx : current_idx + lookahead_intervals]
        else:
            volatility_window = all_intervals[:lookahead_intervals]

        # Calculate trend with volatility-adaptive thresholds
        trend_state, diff_pct, trend_value, vol_factor = calculate_price_trend(
            current_interval_price,
            future_mean,
            threshold_rising=threshold_rising,
            threshold_falling=threshold_falling,
            threshold_strongly_rising=threshold_strongly_rising,
            threshold_strongly_falling=threshold_strongly_falling,
            min_abs_diff=min_abs_diff,
            min_abs_diff_strongly=min_abs_diff_strongly,
            volatility_adjustment=True,  # Always enabled
            lookahead_intervals=lookahead_intervals,
            all_intervals=volatility_window,
            volatility_threshold_moderate=volatility_threshold_moderate,
            volatility_threshold_high=volatility_threshold_high,
        )

        # Determine icon color based on trend state (5-level scale)
        # Strongly rising/falling uses more intense colors
        icon_color = {
            "strongly_rising": "var(--error-color)",  # Red for strongly rising (very expensive)
            "rising": "var(--warning-color)",  # Orange/Yellow for rising prices
            "stable": "var(--state-icon-color)",  # Default gray for stable prices
            "falling": "var(--success-color)",  # Green for falling prices (cheaper)
            "strongly_falling": "var(--success-color)",  # Green for strongly falling (great deal)
        }.get(trend_state, "var(--state-icon-color)")

        # Convert prices to display currency unit based on configuration
        factor = get_display_unit_factor(self.config_entry)
        decimals = get_price_round_decimals(self.config_entry)

        # Store attributes in sensor-specific dictionary AND cache the trend value
        # Show effective thresholds (after volatility adjustment) so users can understand
        # why a trend was detected even when diff_pct seems below configured thresholds
        self._trend_attributes = {
            "timestamp": next_interval_start,
            "trend_value": trend_value,
            f"trend_{hours}h_%": round(diff_pct, 1),
            f"next_{hours}h_avg": round(future_mean * factor, decimals),
            "interval_count": lookahead_intervals,
            "threshold_rising_%": round(threshold_rising * vol_factor, 1),
            "threshold_rising_strongly_%": round(threshold_strongly_rising * vol_factor, 1),
            "threshold_falling_%": round(threshold_falling * vol_factor, 1),
            "threshold_falling_strongly_%": round(threshold_strongly_falling * vol_factor, 1),
            "volatility_factor": vol_factor,
            "icon_color": icon_color,
        }

        # Calculate additional attributes for better granularity
        if hours > MIN_HOURS_FOR_LATER_HALF:
            # Get second half average for longer periods
            later_half_avg = self._calculate_later_half_average(hours, next_interval_start)
            if later_half_avg is not None:
                self._trend_attributes[f"second_half_{hours}h_avg"] = round(later_half_avg * factor, decimals)

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
        # Note: "previous_direction" (not "from_direction") because this shows the
        # price direction BEFORE the current trend (binary: rising/falling),
        # not the trend classification. next_price_trend_change uses "from_direction"
        # for the current 5-level trend state.
        self._current_trend_attributes = {
            "previous_direction": trend_info["from_direction"],
            "price_direction_duration_minutes": trend_info["trend_duration_minutes"],
            "price_direction_since": (
                trend_info["trend_start_time"].isoformat() if trend_info["trend_start_time"] else None
            ),
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

    def get_trend_change_in_minutes_value(self) -> float | None:
        """
        Calculate minutes until the next price trend change, as hours.

        Returns the same data as get_next_trend_change_value() but as a duration
        in minutes (converted to hours by value_getters). Shares cached attributes
        with the timestamp sensor.

        Returns:
            Minutes until next trend change, or None if no change expected

        """
        trend_info = self._calculate_trend_info()

        if not trend_info:
            return None

        # Share attributes with the timestamp sensor
        self._trend_change_attributes = trend_info["trend_change_attributes"]

        return trend_info["minutes_until_change"]

    def get_price_trajectory_value(self, *, hours: int) -> str | None:
        """
        Calculate price trajectory by comparing first-half vs second-half window average.

        This is for price_trajectory_Xh sensors. Answers: "Are prices rising or falling
        within the next Xh window?" — revealing turning points that price_outlook_Xh misses.

        Example at a price minimum (12:00):
        - price_outlook_4h: "strongly_falling" (Ø next 4h is below current high)
        - price_trajectory_4h: "rising" (second half is more expensive than first half)
        → Combined signal: act now, reversal is coming within the window.

        Args:
            hours: Number of hours in the window (must be >= 2)

        Returns:
            Trend state: "rising" | "falling" | "stable", or None if unavailable

        """
        if hours < 2:  # noqa: PLR2004
            return None

        if not self.has_data():
            return None

        current_interval = self.coordinator.get_current_interval()
        if not current_interval or "total" not in current_interval:
            return None

        current_interval_price = float(current_interval["total"])
        time = self.coordinator.time
        current_starts_at = time.get_interval_time(current_interval)
        if current_starts_at is None:
            return None

        next_interval_start = time.get_next_interval_start()

        # Get first-half and second-half averages
        first_half_avg = self._calculate_first_half_average(hours, next_interval_start)
        second_half_avg = self._calculate_later_half_average(hours, next_interval_start)

        if first_half_avg is None or second_half_avg is None:
            return None

        # Get configured thresholds (same as outlook sensors for consistency)
        threshold_rising = self.config.get("price_trend_threshold_rising", 3.0)
        threshold_falling = self.config.get("price_trend_threshold_falling", -3.0)
        threshold_strongly_rising = self.config.get("price_trend_threshold_strongly_rising", 9.0)
        threshold_strongly_falling = self.config.get("price_trend_threshold_strongly_falling", -9.0)
        volatility_threshold_moderate = self.config.get("volatility_threshold_moderate", 15.0)
        volatility_threshold_high = self.config.get("volatility_threshold_high", 30.0)
        min_abs_diff = self.config.get("price_trend_min_price_change", 0.005)
        min_abs_diff_strongly = self.config.get("price_trend_min_price_change_strongly", 0.015)

        # Build volatility window from full outlook period
        today_prices = self.intervals_today
        tomorrow_prices = self.intervals_tomorrow
        all_intervals = today_prices + tomorrow_prices
        lookahead_intervals = self.coordinator.time.minutes_to_intervals(hours * 60)

        current_idx = None
        for idx, interval in enumerate(all_intervals):
            if time.get_interval_time(interval) == current_starts_at:
                current_idx = idx
                break

        if current_idx is not None:
            volatility_window = all_intervals[current_idx : current_idx + lookahead_intervals]
        else:
            volatility_window = all_intervals[:lookahead_intervals]

        # Compare first half vs second half: does price rise or fall across the window?
        trajectory_state, diff_pct, trend_value, vol_factor = calculate_price_trend(
            first_half_avg,
            second_half_avg,
            threshold_rising=threshold_rising,
            threshold_falling=threshold_falling,
            threshold_strongly_rising=threshold_strongly_rising,
            threshold_strongly_falling=threshold_strongly_falling,
            min_abs_diff=min_abs_diff,
            min_abs_diff_strongly=min_abs_diff_strongly,
            volatility_adjustment=True,
            lookahead_intervals=lookahead_intervals,
            all_intervals=volatility_window,
            volatility_threshold_moderate=volatility_threshold_moderate,
            volatility_threshold_high=volatility_threshold_high,
        )

        factor = get_display_unit_factor(self.config_entry)
        decimals = get_price_round_decimals(self.config_entry)
        time_obj = self.coordinator.time
        total_intervals = time_obj.minutes_to_intervals(hours * 60)
        first_half_count = total_intervals // 2
        second_half_count = total_intervals - first_half_count

        self._trajectory_attributes = {
            "timestamp": next_interval_start,
            "trend_value": trend_value,
            f"trajectory_{hours}h_%": round(diff_pct, 1),
            f"first_half_{hours}h_avg": round(first_half_avg * factor, decimals),
            f"second_half_{hours}h_avg": round(second_half_avg * factor, decimals),
            f"first_half_{hours}h_diff_from_current_%": round(
                ((first_half_avg - current_interval_price) / abs(current_interval_price)) * 100, 1
            )
            if current_interval_price != 0
            else None,
            f"second_half_{hours}h_diff_from_current_%": round(
                ((second_half_avg - current_interval_price) / abs(current_interval_price)) * 100, 1
            )
            if current_interval_price != 0
            else None,
            "first_half_interval_count": first_half_count,
            "second_half_interval_count": second_half_count,
            "volatility_factor": vol_factor,
        }

        return trajectory_state

    def get_trend_attributes(self) -> dict[str, Any]:
        """Get cached outlook attributes for price_outlook_Xh sensors."""
        return self._trend_attributes

    def get_trajectory_attributes(self) -> dict[str, Any]:
        """Get cached trajectory attributes for price_trajectory_Xh sensors."""
        return self._trajectory_attributes

    def get_current_trend_attributes(self) -> dict[str, Any] | None:
        """Get cached attributes for current_price_trend sensor."""
        return self._current_trend_attributes

    def get_trend_change_attributes(self) -> dict[str, Any] | None:
        """Get cached attributes for next_price_trend_change sensor."""
        return self._trend_change_attributes

    def clear_trend_cache(self) -> None:
        """Clear outlook/trajectory trend cache (called on coordinator update)."""
        self._cached_trend_value = None
        self._trend_attributes = {}
        self._trajectory_attributes = {}

    def clear_calculation_cache(self) -> None:
        """Clear centralized trend calculation cache (called on coordinator update)."""
        self._trend_calculation_cache = None
        self._trend_calculation_timestamp = None

    # ========================================================================
    # PRIVATE HELPER METHODS
    # ========================================================================

    def _calculate_first_half_average(self, hours: int, next_interval_start: datetime) -> float | None:
        """
        Calculate average price for the first half of the future time window.

        This is the counterpart to _calculate_later_half_average and together they
        enable trajectory calculation (first half vs second half comparison).

        Args:
            hours: Total hours in the prediction window
            next_interval_start: Start timestamp of the next interval

        Returns:
            Average price for the first half intervals, or None if insufficient data

        """
        if not self.has_data():
            return None

        today_prices = self.intervals_today
        tomorrow_prices = self.intervals_tomorrow
        all_prices = today_prices + tomorrow_prices

        if not all_prices:
            return None

        time = self.coordinator.time
        total_intervals = time.minutes_to_intervals(hours * 60)
        first_half_intervals = total_intervals // 2
        interval_duration = time.get_interval_duration()
        first_half_end = next_interval_start + (interval_duration * first_half_intervals)

        # Collect prices in the first half: [next_interval_start, first_half_end)
        first_prices = []
        for price_data in all_prices:
            starts_at = time.get_interval_time(price_data)
            if starts_at is None:
                continue

            if next_interval_start <= starts_at < first_half_end:
                price = price_data.get("total")
                if price is not None:
                    first_prices.append(float(price))

        if first_prices:
            return calculate_mean(first_prices)

        return None

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
            return calculate_mean(later_prices)

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

        # Step 1: Calculate pure future-based 3h trend (no momentum)
        current_trend_state = self._calculate_standard_trend(all_intervals, current_index, current_interval, thresholds)

        # Step 2: Find next trend change by scanning forward
        scan_params = {
            "current_index": current_index,
            "current_trend_state": current_trend_state,
            "current_interval": current_interval,
            "now": now,
        }

        next_change_time = self._scan_for_trend_change(all_intervals, scan_params, thresholds)

        # Step 3: Find when current trend started (scan backward)
        # Use min_abs_diff as noise tolerance to ignore tiny price jitter
        trend_start_time, from_direction = self._find_trend_start_time(
            all_intervals,
            current_index,
            current_trend_state,
            noise_tolerance=thresholds["min_abs_diff"],
        )

        # Calculate duration of current trend
        trend_duration_minutes = None
        if trend_start_time:
            time = self.coordinator.time
            # Duration is negative of minutes_until (time in the past)
            trend_duration_minutes = -time.minutes_until_rounded(trend_start_time)

        # Calculate minutes until change
        minutes_until_change = None
        if next_change_time:
            time = self.coordinator.time
            minutes_until_change = time.minutes_until_rounded(next_change_time)

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
            "rising": self.config.get("price_trend_threshold_rising", 3.0),
            "falling": self.config.get("price_trend_threshold_falling", -3.0),
            "strongly_rising": self.config.get("price_trend_threshold_strongly_rising", 9.0),
            "strongly_falling": self.config.get("price_trend_threshold_strongly_falling", -9.0),
            "moderate": self.config.get("volatility_threshold_moderate", 15.0),
            "high": self.config.get("volatility_threshold_high", 30.0),
            # Config values are stored in base currency (EUR/NOK) - no conversion needed
            "min_abs_diff": self.config.get("price_trend_min_price_change", 0.005),
            "min_abs_diff_strongly": self.config.get("price_trend_min_price_change_strongly", 0.015),
        }

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

        standard_future_mean = calculate_mean(standard_future_prices)
        current_price = float(current_interval["total"])

        standard_lookahead_volatility = all_intervals[current_index : current_index + standard_lookahead]
        current_trend_3h, _, _, _ = calculate_price_trend(
            current_price,
            standard_future_mean,
            threshold_rising=thresholds["rising"],
            threshold_falling=thresholds["falling"],
            threshold_strongly_rising=thresholds["strongly_rising"],
            threshold_strongly_falling=thresholds["strongly_falling"],
            min_abs_diff=thresholds["min_abs_diff"],
            min_abs_diff_strongly=thresholds["min_abs_diff_strongly"],
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
        *,
        noise_tolerance: float = 0.0,
    ) -> tuple[datetime | None, str | None]:
        """
        Find when the current trend started by scanning backward for price direction change.

        Uses lightweight price comparison instead of recalculating full trend at each
        past interval. The trend start is where the price direction changed — i.e., where
        prices stopped moving in the current direction and started moving the other way.

        Price changes smaller than noise_tolerance (in base currency, e.g. EUR) are
        ignored. This prevents tiny jitter (e.g. 0.1ct fluctuation in a 10ct→20ct
        uptrend) from cutting the detected trend duration short.

        For "stable" trends, the start is where prices stopped rising or falling.

        Args:
            all_intervals: List of all price intervals
            current_index: Index of current interval
            current_trend_state: Current trend state (e.g., "rising", "falling", "stable")
            noise_tolerance: Minimum absolute price change (base currency) to count as
                             a direction change. Defaults to 0.0 (no tolerance).

        Returns:
            Tuple of (start_time, from_direction):
            - start_time: When current trend began, or None if at data boundary
            - from_direction: Previous price direction, or None if unknown

        """
        time = self.coordinator.time
        max_lookback = 97  # ~24h

        # Map current trend to expected price direction
        is_rising = current_trend_state in ("rising", "strongly_rising")
        is_falling = current_trend_state in ("falling", "strongly_falling")

        # Scan backward looking for where price direction changed
        prev_price = float(all_intervals[current_index]["total"]) if "total" in all_intervals[current_index] else None
        if prev_price is None:
            return None, None

        for i in range(current_index - 1, max(-1, current_index - max_lookback), -1):
            if i < 0:
                break

            interval = all_intervals[i]
            price = float(interval["total"]) if "total" in interval else None
            if price is None:
                continue

            interval_start = time.get_interval_time(interval)
            if not interval_start:
                continue

            # Calculate signed price difference: positive = price was rising, negative = falling
            price_diff = prev_price - price

            # Apply noise tolerance: ignore price changes below threshold
            direction_was_rising = price_diff > noise_tolerance
            direction_was_falling = price_diff < -noise_tolerance
            # If |price_diff| <= noise_tolerance → neither → continue scanning

            # Check if direction contradicts current trend
            if is_rising and direction_was_falling:
                # Price was falling here, but we're currently rising → trend started at next interval
                next_interval = all_intervals[i + 1]
                trend_start = time.get_interval_time(next_interval)
                return trend_start, "falling"

            if is_falling and direction_was_rising:
                # Price was rising here, but we're currently falling → trend started at next interval
                next_interval = all_intervals[i + 1]
                trend_start = time.get_interval_time(next_interval)
                return trend_start, "rising"

            if not is_rising and not is_falling and (direction_was_rising or direction_was_falling):
                # Current trend is "stable" — look for any clear directional movement
                next_interval = all_intervals[i + 1]
                trend_start = time.get_interval_time(next_interval)
                from_dir = "rising" if direction_was_rising else "falling"
                return trend_start, from_dir

            prev_price = price

        # Reached data boundary
        return None, None

    def _scan_for_trend_change(
        self,
        all_intervals: list,
        scan_params: dict,
        thresholds: dict,
    ) -> datetime | None:
        """
        Scan future intervals for trend change with hysteresis.

        Detection mechanic: For each future interval i, the sensor compares the price
        of interval i to the AVERAGE price of the following 3 hours (intervals i+1..i+12).
        A trend change is signalled when that 3h-ahead mean has already moved in the
        opposite direction from the current trend.

        Requires N consecutive intervals (configurable, default 3) showing a different
        trend before confirming a change. This prevents false positives from short-lived
        price spikes.

        Behaviour on V-shaped price days:
            On a sharp price drop toward a minimum, the 3h lookahead window begins
            including rising-flank prices before the actual minimum is reached. Once
            those rising prices push the 3h average above the current price, the scan
            reports a trend change. This typically fires 30-60 minutes before the exact
            price minimum - intentional, because the sensor answers "when will the
            broad direction change?" rather than "when is the exact turning point?".
            Users who need the precise minimum should compare with the Best Price
            period start (``best_price_next_start_time``), which uses the actual
            cheapest window.

        Args:
            all_intervals: List of all price intervals
            scan_params: Dict with current_index, current_trend_state, current_interval, now
            thresholds: Dict with rising, falling, moderate, high threshold values

        Returns:
            Timestamp of first interval of confirmed trend change, or None if no change

        """
        time = self.coordinator.time
        intervals_in_3h = 12  # 3 hours = 12 intervals @ 15min each
        required_consecutive = int(self.config.get("price_trend_change_confirmation", 3))

        # Reset attributes to prevent stale data from previous calculation.
        # Without this, old attributes persist when no trend change is found,
        # causing the sensor to show state=unknown with misleading old values.
        self._trend_change_attributes = None

        current_index = scan_params["current_index"]
        current_trend_state = scan_params["current_trend_state"]
        current_interval = scan_params["current_interval"]
        now = scan_params["now"]

        # Use direction groups: only group changes count as trend changes.
        # rising/strongly_rising → "rising", falling/strongly_falling → "falling", stable → "stable"
        current_group = self._DIRECTION_GROUPS.get(current_trend_state, "stable")

        # Track consecutive intervals with different trend direction group
        consecutive_different = 0
        first_change: dict[str, Any] | None = None  # {index, trend, mean, diff, vol_factor}

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

            future_mean = calculate_mean(future_prices)
            current_price = float(interval["total"])

            # Calculate trend at this future point
            lookahead_for_volatility = all_intervals[i : i + intervals_in_3h]
            trend_state, trend_diff, _, vol_factor = calculate_price_trend(
                current_price,
                future_mean,
                threshold_rising=thresholds["rising"],
                threshold_falling=thresholds["falling"],
                threshold_strongly_rising=thresholds["strongly_rising"],
                threshold_strongly_falling=thresholds["strongly_falling"],
                min_abs_diff=thresholds["min_abs_diff"],
                min_abs_diff_strongly=thresholds["min_abs_diff_strongly"],
                volatility_adjustment=True,
                lookahead_intervals=intervals_in_3h,
                all_intervals=lookahead_for_volatility,
                volatility_threshold_moderate=thresholds["moderate"],
                volatility_threshold_high=thresholds["high"],
            )

            new_group = self._DIRECTION_GROUPS.get(trend_state, "stable")

            if new_group != current_group:
                consecutive_different += 1
                if consecutive_different == 1:
                    # Remember the first different interval (5-level state for attributes)
                    first_change = {
                        "index": i,
                        "trend": trend_state,
                        "mean": future_mean,
                        "diff": trend_diff,
                        "vol_factor": vol_factor,
                    }

                if consecutive_different >= required_consecutive and first_change is not None:
                    # Confirmed: N consecutive intervals show different trend direction
                    change_interval = all_intervals[first_change["index"]]
                    change_time = time.get_interval_time(change_interval)
                    if change_time:
                        change_price = float(change_interval["total"])
                        minutes_until = time.minutes_until_rounded(change_time)
                        factor = get_display_unit_factor(self.config_entry)
                        decimals = get_price_round_decimals(self.config_entry)
                        vf = first_change["vol_factor"]

                        self._trend_change_attributes = {
                            "direction": first_change["trend"],
                            "from_direction": current_trend_state,
                            "minutes_until_change": minutes_until,
                            "price_now": round(float(current_interval["total"]) * factor, decimals),
                            "price_at_change": round(change_price * factor, decimals),
                            "price_avg_after_change": (
                                round(first_change["mean"] * factor, decimals)
                                if first_change["mean"]
                                else None
                            ),
                            "trend_diff_%": round(first_change["diff"], 1),
                            "threshold_rising_%": round(thresholds["rising"] * vf, 1),
                            "threshold_rising_strongly_%": round(thresholds["strongly_rising"] * vf, 1),
                            "threshold_falling_%": round(thresholds["falling"] * vf, 1),
                            "threshold_falling_strongly_%": round(thresholds["strongly_falling"] * vf, 1),
                            "volatility_factor": vf,
                        }
                        return change_time
            else:
                # Reset counter — trend matches current again
                consecutive_different = 0
                first_change = None

        return None
