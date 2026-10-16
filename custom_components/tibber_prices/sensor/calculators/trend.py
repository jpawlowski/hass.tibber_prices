"""
Trend calculator for price trend analysis sensors.

This module handles all trend-related calculations:
- Price outlook (1h-12h): Current price vs average of the next N hours
- Price trajectory (2h-12h): First-half vs second-half average in the window (shows turning points)
- Current trend: robust trend line through 1.5h back and 1.5h ahead (see utils/trend.py)
- Next trend change and trend duration: read from the same confirmed trend timeline
  (configurable N-interval confirmation, default 3), so state, start and next change agree

Caching strategy:
- Outlook/Trajectory: Cached per sensor update to ensure consistency between state and attributes
- Current trend + next change: Cached centrally for 60s to avoid duplicate calculations
"""

from typing import TYPE_CHECKING, Any

from custom_components.tibber_prices.const import (
    CONF_PRICE_TREND_CHANGE_CONFIRMATION,
    CONF_PRICE_TREND_MIN_PRICE_CHANGE,
    CONF_PRICE_TREND_MIN_PRICE_CHANGE_STRONGLY,
    CONF_PRICE_TREND_THRESHOLD_FALLING,
    CONF_PRICE_TREND_THRESHOLD_RISING,
    CONF_PRICE_TREND_THRESHOLD_STRONGLY_FALLING,
    CONF_PRICE_TREND_THRESHOLD_STRONGLY_RISING,
    CONF_VOLATILITY_THRESHOLD_HIGH,
    CONF_VOLATILITY_THRESHOLD_MODERATE,
    get_display_precision,
    get_display_unit_factor,
)
from custom_components.tibber_prices.coordinator.helpers import get_intervals_for_day_offsets
from custom_components.tibber_prices.entity_utils.colors import get_icon_color
from custom_components.tibber_prices.sensor.helpers import aggregate_average_data
from custom_components.tibber_prices.utils.average import calculate_mean, calculate_next_n_hours_mean
from custom_components.tibber_prices.utils.price import calculate_price_trend, find_price_data_for_interval
from custom_components.tibber_prices.utils.trend import TibberPricesTrendThresholds, build_trend_timeline

from .base import TibberPricesBaseCalculator

if TYPE_CHECKING:
    from datetime import datetime

    from custom_components.tibber_prices.coordinator import TibberPricesDataUpdateCoordinator

# Constants
MIN_HOURS_FOR_LATER_HALF = 1  # Minimum hours needed to calculate half-window averages (activates at 2h+)
PRICE_AVG_AFTER_CHANGE_INTERVALS = 12  # price_avg_after_change: the 3 hours after the change
TREND_CACHE_SECONDS = 60  # Recheck the trend once a minute (the countdown sensor updates every 30s)


class TibberPricesTrendCalculator(TibberPricesBaseCalculator):
    """
    Calculator for price trend sensors.

    Handles four types of trend analysis:
    1. Outlook sensors (price_outlook_1h-12h): Current vs next N hours average
    2. Trajectory sensors (price_trajectory_2h-12h): First half vs second half of window
    3. Current trend (current_price_trend): Trend line centered on now (±1.5h)
    4. Next change (next_price_trend_change): Next segment of the confirmed trend timeline

    Caching:
    - Simple trends: Per-sensor cache (_cached_trend_value, _trend_attributes)
    - Current/Next: Centralized cache (_trend_calculation_cache) with 60s TTL
    """

    def __init__(self, coordinator: TibberPricesDataUpdateCoordinator) -> None:
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
        # Without this, the volatility factor in calculate_price_trend() would analyze
        # prices from the start of the day instead of the actual lookahead window.
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

        # Determine icon color via centralized mapping (same as colors.py)
        icon_color = get_icon_color(f"price_outlook_{hours}h", trend_state) or "var(--state-icon-color)"

        # Convert prices to display currency unit based on configuration
        factor = get_display_unit_factor(self.config_entry)
        precision = get_display_precision(self.config_entry)

        # Store attributes in sensor-specific dictionary AND cache the trend value
        # Show effective thresholds (after volatility adjustment) so users can understand
        # why a trend was detected even when diff_pct seems below configured thresholds
        self._trend_attributes = {
            "timestamp": next_interval_start,
            "trend_value": trend_value,
            f"trend_{hours}h_%": round(diff_pct, 1),
            f"next_{hours}h_avg": round(future_mean * factor, precision),
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
                self._trend_attributes[f"second_half_{hours}h_avg"] = round(later_half_avg * factor, precision)

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

        # "previous_direction" is the direction group before the current one (rising,
        # stable or falling); next_price_trend_change's "from_direction" is the current
        # 5-level trend instead.
        current_trend_state = trend_info["current_trend_state"]
        self._current_trend_attributes = {
            "previous_direction": trend_info["from_direction"],
            "price_direction_duration_minutes": trend_info["trend_duration_minutes"],
            "price_direction_since": (
                trend_info["trend_start_time"].isoformat() if trend_info["trend_start_time"] else None
            ),
            "icon_color": get_icon_color("current_price_trend", current_trend_state),
        }

        return current_trend_state

    def get_next_trend_change_value(self) -> datetime | None:
        """
        Calculate when the next price trend change will occur.

        Uses centralized _calculate_trend_info() for consistency with current_price_trend sensor.

        Returns:
            Timestamp of next trend change, or None if none is confirmed in the known prices

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
        if hours < 2:
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
        precision = get_display_precision(self.config_entry)
        time_obj = self.coordinator.time
        total_intervals = time_obj.minutes_to_intervals(hours * 60)
        first_half_count = total_intervals // 2
        second_half_count = total_intervals - first_half_count

        self._trajectory_attributes = {
            "timestamp": next_interval_start,
            "trend_value": trend_value,
            f"trajectory_{hours}h_%": round(diff_pct, 1),
            f"first_half_{hours}h_avg": round(first_half_avg * factor, precision),
            f"second_half_{hours}h_avg": round(second_half_avg * factor, precision),
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
            "icon_color": get_icon_color(f"price_trajectory_{hours}h", trajectory_state),
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
        Centralized trend calculation for the current trend and next trend change sensors.

        All three values come from one timeline (utils/trend.py), so they always agree.
        The heavy part is cached there per price data; this cache only spares the
        per-minute bookkeeping for TREND_CACHE_SECONDS.

        Returns:
            Dictionary with trend information for both sensors.

        """
        time = self.coordinator.time
        now = time.now()
        if (
            self._trend_calculation_cache is not None
            and self._trend_calculation_timestamp is not None
            and (now - self._trend_calculation_timestamp).total_seconds() < TREND_CACHE_SECONDS
        ):
            return self._trend_calculation_cache

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

        thresholds = self._get_trend_thresholds()
        prices = [_price(interval) for interval in all_intervals]
        timeline = build_trend_timeline(prices, current_index, thresholds)

        trend_start_time = (
            time.get_interval_time(all_intervals[timeline.start_index]) if timeline.start_index is not None else None
        )
        next_change_time = (
            time.get_interval_time(all_intervals[timeline.change_index]) if timeline.change_index is not None else None
        )
        minutes_until_change = time.minutes_until_rounded(next_change_time) if next_change_time else None

        trend_change_attributes = None
        if next_change_time and timeline.change_index is not None and timeline.change and timeline.change.change:
            factor = get_display_unit_factor(self.config_entry)
            precision = get_display_precision(self.config_entry)
            change_index = timeline.change_index
            trend_change_attributes = {
                "direction": timeline.change.trend,
                "from_direction": timeline.trend,
                "minutes_until_change": minutes_until_change,
                "price_now": _display_price(current_interval, factor, precision),
                "price_at_change": _display_price(all_intervals[change_index], factor, precision),
                # Average of the 3 hours after the change interval (as before the trend line)
                "price_avg_after_change": aggregate_average_data(
                    all_intervals[change_index + 1 : change_index + PRICE_AVG_AFTER_CHANGE_INTERVALS + 1],
                    self.config_entry,
                )[0],
                "trend_diff_%": round(timeline.change.change.diff_pct, 1),
                **thresholds.effective(timeline.change.volatility_factor),
                "volatility_factor": timeline.change.volatility_factor,
            }

        result = {
            "current_trend_state": timeline.trend,
            "next_change_time": next_change_time,
            "trend_change_attributes": trend_change_attributes,
            "trend_start_time": trend_start_time,
            "from_direction": timeline.previous_group,
            "trend_duration_minutes": -time.minutes_until_rounded(trend_start_time) if trend_start_time else None,
            "minutes_until_change": minutes_until_change,
        }
        self._trend_calculation_cache = result
        self._trend_calculation_timestamp = now
        return result

    def _get_trend_thresholds(self) -> TibberPricesTrendThresholds:
        """Trend settings from the options, falling back to the integration defaults."""
        defaults = TibberPricesTrendThresholds()
        options = self.config
        return TibberPricesTrendThresholds(
            rising=options.get(CONF_PRICE_TREND_THRESHOLD_RISING, defaults.rising),
            falling=options.get(CONF_PRICE_TREND_THRESHOLD_FALLING, defaults.falling),
            strongly_rising=options.get(CONF_PRICE_TREND_THRESHOLD_STRONGLY_RISING, defaults.strongly_rising),
            strongly_falling=options.get(CONF_PRICE_TREND_THRESHOLD_STRONGLY_FALLING, defaults.strongly_falling),
            # Config values are stored in base currency (EUR/NOK) - no conversion needed
            min_abs_diff=options.get(CONF_PRICE_TREND_MIN_PRICE_CHANGE, defaults.min_abs_diff),
            min_abs_diff_strongly=options.get(
                CONF_PRICE_TREND_MIN_PRICE_CHANGE_STRONGLY, defaults.min_abs_diff_strongly
            ),
            volatility_moderate=options.get(CONF_VOLATILITY_THRESHOLD_MODERATE, defaults.volatility_moderate),
            volatility_high=options.get(CONF_VOLATILITY_THRESHOLD_HIGH, defaults.volatility_high),
            confirmation=int(options.get(CONF_PRICE_TREND_CHANGE_CONFIRMATION, defaults.confirmation)),
        )

    def _find_current_interval_index(self, all_intervals: list, current_interval_start: datetime) -> int | None:
        """Find the index of current interval in all_intervals list."""
        time = self.coordinator.time
        for idx, interval in enumerate(all_intervals):
            interval_start = time.get_interval_time(interval)
            if interval_start and interval_start == current_interval_start:
                return idx
        return None


def _price(interval: dict) -> float | None:
    """Return the interval's total price, None if it is missing."""
    total = interval.get("total")
    return float(total) if total is not None else None


def _display_price(interval: dict, factor: int, precision: int) -> float | None:
    """Return the interval's total in display units, None if it is missing."""
    price = _price(interval)
    return round(price * factor, precision) if price is not None else None
