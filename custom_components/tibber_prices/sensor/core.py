"""Core sensor class for Tibber Prices integration."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from custom_components.tibber_prices.average_utils import (
    calculate_current_leading_avg,
    calculate_current_leading_max,
    calculate_current_leading_min,
    calculate_current_trailing_avg,
    calculate_current_trailing_max,
    calculate_current_trailing_min,
    calculate_next_n_hours_avg,
)
from custom_components.tibber_prices.const import (
    CONF_EXTENDED_DESCRIPTIONS,
    CONF_PRICE_RATING_THRESHOLD_HIGH,
    CONF_PRICE_RATING_THRESHOLD_LOW,
    CONF_PRICE_TREND_THRESHOLD_FALLING,
    CONF_PRICE_TREND_THRESHOLD_RISING,
    DEFAULT_EXTENDED_DESCRIPTIONS,
    DEFAULT_PRICE_RATING_THRESHOLD_HIGH,
    DEFAULT_PRICE_RATING_THRESHOLD_LOW,
    DEFAULT_PRICE_TREND_THRESHOLD_FALLING,
    DEFAULT_PRICE_TREND_THRESHOLD_RISING,
    DOMAIN,
    async_get_entity_description,
    format_price_unit_minor,
    get_entity_description,
)
from custom_components.tibber_prices.coordinator import TIME_SENSITIVE_ENTITY_KEYS
from custom_components.tibber_prices.entity import TibberPricesEntity
from custom_components.tibber_prices.entity_utils import (
    add_icon_color_attribute,
    get_dynamic_icon,
)
from custom_components.tibber_prices.price_utils import (
    MINUTES_PER_INTERVAL,
    calculate_price_trend,
    calculate_volatility_level,
    find_price_data_for_interval,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import callback
from homeassistant.util import dt as dt_util

from .attributes import (
    add_volatility_type_attributes,
    build_sensor_attributes,
    get_future_prices,
    get_prices_for_volatility,
)
from .helpers import (
    aggregate_level_data,
    aggregate_price_data,
    aggregate_rating_data,
    find_rolling_hour_center_index,
    get_price_value,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from custom_components.tibber_prices.coordinator import (
        TibberPricesDataUpdateCoordinator,
    )

HOURS_IN_DAY = 24
LAST_HOUR_OF_DAY = 23
INTERVALS_PER_HOUR = 4  # 15-minute intervals
MAX_FORECAST_INTERVALS = 8  # Show up to 8 future intervals (2 hours with 15-min intervals)
MIN_HOURS_FOR_LATER_HALF = 3  # Minimum hours needed to calculate later half average


class TibberPricesSensor(TibberPricesEntity, SensorEntity):
    """tibber_prices Sensor class."""

    def __init__(
        self,
        coordinator: TibberPricesDataUpdateCoordinator,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor class."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{entity_description.key}"
        self._attr_has_entity_name = True
        self._value_getter: Callable | None = self._get_value_getter()
        self._time_sensitive_remove_listener: Callable | None = None
        self._trend_attributes: dict[str, Any] = {}  # Sensor-specific trend attributes
        self._cached_trend_value: str | None = None  # Cache for trend state

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()

        # Register with coordinator for time-sensitive updates if applicable
        if self.entity_description.key in TIME_SENSITIVE_ENTITY_KEYS:
            self._time_sensitive_remove_listener = self.coordinator.async_add_time_sensitive_listener(
                self._handle_time_sensitive_update
            )

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        await super().async_will_remove_from_hass()

        # Remove time-sensitive listener if registered
        if self._time_sensitive_remove_listener:
            self._time_sensitive_remove_listener()
            self._time_sensitive_remove_listener = None

    @callback
    def _handle_time_sensitive_update(self) -> None:
        """Handle time-sensitive update from coordinator."""
        # Clear cached trend values on time-sensitive updates
        if self.entity_description.key.startswith("price_trend_"):
            self._cached_trend_value = None
            self._trend_attributes = {}
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Clear cached trend values when coordinator data changes
        if self.entity_description.key.startswith("price_trend_"):
            self._cached_trend_value = None
            self._trend_attributes = {}
        super()._handle_coordinator_update()

    def _get_value_getter(self) -> Callable | None:
        """Return the appropriate value getter method based on the sensor type."""
        key = self.entity_description.key

        # Map sensor keys to their handler methods
        handlers = {
            # ================================================================
            # INTERVAL-BASED SENSORS (using unified _get_interval_value)
            # ================================================================
            # Price level sensors
            "current_interval_price_level": self._get_price_level_value,
            "next_interval_price_level": lambda: self._get_interval_value(interval_offset=1, value_type="level"),
            "previous_interval_price_level": lambda: self._get_interval_value(interval_offset=-1, value_type="level"),
            # Price sensors (in cents)
            "current_interval_price": lambda: self._get_interval_value(
                interval_offset=0, value_type="price", in_euro=False
            ),
            "next_interval_price": lambda: self._get_interval_value(
                interval_offset=1, value_type="price", in_euro=False
            ),
            "previous_interval_price": lambda: self._get_interval_value(
                interval_offset=-1, value_type="price", in_euro=False
            ),
            # Rating sensors
            "current_interval_price_rating": lambda: self._get_rating_value(rating_type="current"),
            "next_interval_price_rating": lambda: self._get_interval_value(interval_offset=1, value_type="rating"),
            "previous_interval_price_rating": lambda: self._get_interval_value(interval_offset=-1, value_type="rating"),
            # ================================================================
            # ROLLING HOUR SENSORS (5-interval windows) - Use unified method
            # ================================================================
            "current_hour_price_level": lambda: self._get_rolling_hour_value(hour_offset=0, value_type="level"),
            "next_hour_price_level": lambda: self._get_rolling_hour_value(hour_offset=1, value_type="level"),
            # Rolling hour average (5 intervals: 2 before + current + 2 after)
            "current_hour_average": lambda: self._get_rolling_hour_value(hour_offset=0, value_type="price"),
            "next_hour_average": lambda: self._get_rolling_hour_value(hour_offset=1, value_type="price"),
            "current_hour_price_rating": lambda: self._get_rolling_hour_value(hour_offset=0, value_type="rating"),
            "next_hour_price_rating": lambda: self._get_rolling_hour_value(hour_offset=1, value_type="rating"),
            # ================================================================
            # DAILY STATISTICS SENSORS
            # ================================================================
            "lowest_price_today": lambda: self._get_daily_stat_value(day="today", stat_func=min),
            "highest_price_today": lambda: self._get_daily_stat_value(day="today", stat_func=max),
            "average_price_today": lambda: self._get_daily_stat_value(
                day="today",
                stat_func=lambda prices: sum(prices) / len(prices),
            ),
            # Tomorrow statistics sensors
            "lowest_price_tomorrow": lambda: self._get_daily_stat_value(day="tomorrow", stat_func=min),
            "highest_price_tomorrow": lambda: self._get_daily_stat_value(day="tomorrow", stat_func=max),
            "average_price_tomorrow": lambda: self._get_daily_stat_value(
                day="tomorrow",
                stat_func=lambda prices: sum(prices) / len(prices),
            ),
            # ================================================================
            # 24H WINDOW SENSORS (trailing/leading from current)
            # ================================================================
            # Trailing and leading average sensors
            "trailing_price_average": lambda: self._get_24h_window_value(
                stat_func=calculate_current_trailing_avg,
            ),
            "leading_price_average": lambda: self._get_24h_window_value(
                stat_func=calculate_current_leading_avg,
            ),
            # Trailing and leading min/max sensors
            "trailing_price_min": lambda: self._get_24h_window_value(
                stat_func=calculate_current_trailing_min,
            ),
            "trailing_price_max": lambda: self._get_24h_window_value(
                stat_func=calculate_current_trailing_max,
            ),
            "leading_price_min": lambda: self._get_24h_window_value(
                stat_func=calculate_current_leading_min,
            ),
            "leading_price_max": lambda: self._get_24h_window_value(
                stat_func=calculate_current_leading_max,
            ),
            # ================================================================
            # FUTURE FORECAST SENSORS
            # ================================================================
            # Future average sensors (next N hours from next interval)
            "next_avg_1h": lambda: self._get_next_avg_n_hours_value(hours=1),
            "next_avg_2h": lambda: self._get_next_avg_n_hours_value(hours=2),
            "next_avg_3h": lambda: self._get_next_avg_n_hours_value(hours=3),
            "next_avg_4h": lambda: self._get_next_avg_n_hours_value(hours=4),
            "next_avg_5h": lambda: self._get_next_avg_n_hours_value(hours=5),
            "next_avg_6h": lambda: self._get_next_avg_n_hours_value(hours=6),
            "next_avg_8h": lambda: self._get_next_avg_n_hours_value(hours=8),
            "next_avg_12h": lambda: self._get_next_avg_n_hours_value(hours=12),
            # Price trend sensors
            "price_trend_1h": lambda: self._get_price_trend_value(hours=1),
            "price_trend_2h": lambda: self._get_price_trend_value(hours=2),
            "price_trend_3h": lambda: self._get_price_trend_value(hours=3),
            "price_trend_4h": lambda: self._get_price_trend_value(hours=4),
            "price_trend_5h": lambda: self._get_price_trend_value(hours=5),
            "price_trend_6h": lambda: self._get_price_trend_value(hours=6),
            "price_trend_8h": lambda: self._get_price_trend_value(hours=8),
            "price_trend_12h": lambda: self._get_price_trend_value(hours=12),
            # Diagnostic sensors
            "data_timestamp": self._get_data_timestamp,
            # Price forecast sensor
            "price_forecast": self._get_price_forecast_value,
            # Volatility sensors
            "today_volatility": lambda: self._get_volatility_value(volatility_type="today"),
            "tomorrow_volatility": lambda: self._get_volatility_value(volatility_type="tomorrow"),
            "next_24h_volatility": lambda: self._get_volatility_value(volatility_type="next_24h"),
            "today_tomorrow_volatility": lambda: self._get_volatility_value(volatility_type="today_tomorrow"),
        }

        return handlers.get(key)

    def _get_current_interval_data(self) -> dict | None:
        """Get the price data for the current interval using coordinator utility."""
        return self.coordinator.get_current_interval()

    # ========================================================================
    # UNIFIED INTERVAL VALUE METHODS (NEW)
    # ========================================================================

    def _get_interval_value(
        self,
        *,
        interval_offset: int,
        value_type: str,
        in_euro: bool = False,
    ) -> str | float | None:
        """
        Unified method to get values (price/level/rating) for intervals with offset.

        Args:
            interval_offset: Offset from current interval (0=current, 1=next, -1=previous)
            value_type: Type of value to retrieve ("price", "level", "rating")
            in_euro: For prices only - return in EUR if True, cents if False

        Returns:
            For "price": float in EUR or cents
            For "level" or "rating": lowercase enum string
            None if data unavailable

        """
        if not self.coordinator.data:
            return None

        price_info = self.coordinator.data.get("priceInfo", {})
        now = dt_util.now()
        target_time = now + timedelta(minutes=MINUTES_PER_INTERVAL * interval_offset)

        interval_data = find_price_data_for_interval(price_info, target_time)
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

    def _get_price_level_value(self) -> str | None:
        """Get the current price level value as enum string for the state."""
        current_interval_data = self._get_current_interval_data()
        if not current_interval_data or "level" not in current_interval_data:
            return None
        level = current_interval_data["level"]
        self._last_price_level = level
        # Convert API level (e.g., "NORMAL") to lowercase enum value (e.g., "normal")
        return level.lower() if level else None

    # _get_interval_level_value() has been replaced by unified _get_interval_value()
    # See line 814 for the new implementation

    # ========================================================================
    # ROLLING HOUR METHODS (unified)
    # ========================================================================

    def _get_rolling_hour_value(
        self,
        *,
        hour_offset: int = 0,
        value_type: str = "price",
    ) -> str | float | None:
        """
        Unified method to get aggregated values from 5-interval rolling window.

        Window: 2 before + center + 2 after = 5 intervals (60 minutes total).

        Args:
            hour_offset: 0 (current hour), 1 (next hour), etc.
            value_type: "price" | "level" | "rating"

        Returns:
            Aggregated value based on type:
            - "price": float (average price in minor currency units)
            - "level": str (aggregated level: "very_cheap", "cheap", etc.)
            - "rating": str (aggregated rating: "low", "normal", "high")

        """
        if not self.coordinator.data:
            return None

        # Get all available price data
        price_info = self.coordinator.data.get("priceInfo", {})
        all_prices = price_info.get("yesterday", []) + price_info.get("today", []) + price_info.get("tomorrow", [])

        if not all_prices:
            return None

        # Find center index for the rolling window
        now = dt_util.now()
        center_idx = find_rolling_hour_center_index(all_prices, now, hour_offset)
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

        return self._aggregate_window_data(window_data, value_type)

    def _aggregate_window_data(
        self,
        window_data: list[dict],
        value_type: str,
    ) -> str | float | None:
        """Aggregate data from multiple intervals based on value type."""
        # Get thresholds from config for rating aggregation
        threshold_low = self.coordinator.config_entry.options.get(
            CONF_PRICE_RATING_THRESHOLD_LOW,
            DEFAULT_PRICE_RATING_THRESHOLD_LOW,
        )
        threshold_high = self.coordinator.config_entry.options.get(
            CONF_PRICE_RATING_THRESHOLD_HIGH,
            DEFAULT_PRICE_RATING_THRESHOLD_HIGH,
        )

        # Map value types to aggregation functions
        aggregators = {
            "price": lambda data: aggregate_price_data(data),
            "level": lambda data: aggregate_level_data(data),
            "rating": lambda data: aggregate_rating_data(data, threshold_low, threshold_high),
        }

        aggregator = aggregators.get(value_type)
        if aggregator:
            return aggregator(window_data)
        return None

    # ========================================================================
    # INTERVAL-BASED VALUE METHODS
    # ========================================================================

    def _get_hourly_price_value(self, *, hour_offset: int, in_euro: bool) -> float | None:
        """Get price for current hour or with offset."""
        if not self.coordinator.data:
            return None
        price_info = self.coordinator.data.get("priceInfo", {})

        # Use HomeAssistant's dt_util to get the current time in the user's timezone
        now = dt_util.now()

        # Calculate the exact target datetime (not just the hour)
        # This properly handles day boundaries
        target_datetime = now.replace(microsecond=0) + timedelta(hours=hour_offset)
        target_hour = target_datetime.hour
        target_date = target_datetime.date()

        # Determine which day's data we need
        day_key = "tomorrow" if target_date > now.date() else "today"

        for price_data in price_info.get(day_key, []):
            # Parse the timestamp and convert to local time
            starts_at = dt_util.parse_datetime(price_data["startsAt"])
            if starts_at is None:
                continue

            # Make sure it's in the local timezone for proper comparison
            starts_at = dt_util.as_local(starts_at)

            # Compare using both hour and date for accuracy
            if starts_at.hour == target_hour and starts_at.date() == target_date:
                return get_price_value(float(price_data["total"]), in_euro=in_euro)

        # If we didn't find the price in the expected day's data, check the other day
        # This is a fallback for potential edge cases
        other_day_key = "today" if day_key == "tomorrow" else "tomorrow"
        for price_data in price_info.get(other_day_key, []):
            starts_at = dt_util.parse_datetime(price_data["startsAt"])
            if starts_at is None:
                continue

            starts_at = dt_util.as_local(starts_at)
            if starts_at.hour == target_hour and starts_at.date() == target_date:
                return get_price_value(float(price_data["total"]), in_euro=in_euro)

        return None

    # ========================================================================
    # UNIFIED STATISTICS METHODS
    # ========================================================================
    # Replaces: _get_statistics_value, _get_average_value, _get_minmax_value
    # Groups daily stats (calendar day boundaries) separate from 24h windows
    # ========================================================================

    def _get_daily_stat_value(
        self,
        *,
        day: str = "today",
        stat_func: Callable[[list[float]], float],
    ) -> float | None:
        """
        Unified method for daily statistics (min/max/avg within calendar day).

        Calculates statistics for a specific calendar day using local timezone
        boundaries. Stores the extreme interval for use in attributes.

        Args:
            day: "today" or "tomorrow" - which calendar day to calculate for
            stat_func: Statistical function (min, max, or lambda for avg)

        Returns:
            Price value in minor currency units (cents/øre), or None if unavailable

        """
        if not self.coordinator.data:
            return None

        price_info = self.coordinator.data.get("priceInfo", {})

        # Get local midnight boundaries based on the requested day
        local_midnight = dt_util.as_local(dt_util.start_of_local_day(dt_util.now()))
        if day == "tomorrow":
            local_midnight = local_midnight + timedelta(days=1)
        local_midnight_next_day = local_midnight + timedelta(days=1)

        # Collect all prices and their intervals from both today and tomorrow data
        # that fall within the target day's local date boundaries
        price_intervals = []
        for day_key in ["today", "tomorrow"]:
            for price_data in price_info.get(day_key, []):
                starts_at_str = price_data.get("startsAt")
                if not starts_at_str:
                    continue

                starts_at = dt_util.parse_datetime(starts_at_str)
                if starts_at is None:
                    continue

                # Convert to local timezone for comparison
                starts_at = dt_util.as_local(starts_at)

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
        value = stat_func(prices)

        # Store the interval with the extreme price for use in attributes
        for pi in price_intervals:
            if pi["price"] == value:
                self._last_extreme_interval = pi["interval"]
                break

        # Always return in minor currency units (cents/øre) with 2 decimals
        result = get_price_value(value, in_euro=False)
        return round(result, 2)

    def _get_24h_window_value(
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
            stat_func: Function from average_utils (e.g., calculate_current_trailing_avg)

        Returns:
            Price value in minor currency units (cents/øre), or None if unavailable

        """
        if not self.coordinator.data:
            return None

        value = stat_func(self.coordinator.data)

        if value is None:
            return None

        # Always return in minor currency units (cents/øre) with 2 decimals
        result = get_price_value(value, in_euro=False)
        return round(result, 2)

    def _translate_rating_level(self, level: str) -> str:
        """Translate the rating level using custom translations, falling back to English or the raw value."""
        if not self.hass or not level:
            return level
        language = self.hass.config.language or "en"
        cache_key = f"{DOMAIN}_translations_{language}"
        translations = self.hass.data.get(cache_key)
        if (
            translations
            and "sensor" in translations
            and "current_interval_price_rating" in translations["sensor"]
            and "price_levels" in translations["sensor"]["current_interval_price_rating"]
            and level in translations["sensor"]["current_interval_price_rating"]["price_levels"]
        ):
            return translations["sensor"]["current_interval_price_rating"]["price_levels"][level]
        # Fallback to English if not found
        if language != "en":
            en_cache_key = f"{DOMAIN}_translations_en"
            en_translations = self.hass.data.get(en_cache_key)
            if (
                en_translations
                and "sensor" in en_translations
                and "current_interval_price_rating" in en_translations
                and "price_levels" in en_translations["sensor"]["current_interval_price_rating"]
                and level in en_translations["sensor"]["current_interval_price_rating"]["price_levels"]
            ):
                return en_translations["sensor"]["current_interval_price_rating"]["price_levels"][level]
        return level

    def _get_rating_value(self, *, rating_type: str) -> str | None:
        """
        Get the price rating level from the current price interval in priceInfo.

        Returns the rating level enum value, and stores the original
        level and percentage difference as attributes.
        """
        if not self.coordinator.data or rating_type != "current":
            self._last_rating_difference = None
            self._last_rating_level = None
            return None

        now = dt_util.now()
        price_info = self.coordinator.data.get("priceInfo", {})
        current_interval = find_price_data_for_interval(price_info, now)

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

    # _get_interval_rating_value() has been replaced by unified _get_interval_value()
    # See line 814 for the new implementation

    def _get_next_avg_n_hours_value(self, *, hours: int) -> float | None:
        """
        Get average price for next N hours starting from next interval.

        Args:
            hours: Number of hours to look ahead (1, 2, 3, 4, 5, 6, 8, 12)

        Returns:
            Average price in minor currency units (e.g., cents), or None if unavailable

        """
        avg_price = calculate_next_n_hours_avg(self.coordinator.data, hours)
        if avg_price is None:
            return None

        # Convert from major to minor currency units (e.g., EUR to cents)
        return round(avg_price * 100, 2)

    def _get_price_trend_value(self, *, hours: int) -> str | None:
        """
        Calculate price trend comparing current interval vs next N hours average.

        Args:
            hours: Number of hours to look ahead for trend calculation

        Returns:
            Trend state: "rising" | "falling" | "stable", or None if unavailable

        """
        # Return cached value if available to ensure consistency between
        # native_value and extra_state_attributes
        if self._cached_trend_value is not None and self._trend_attributes:
            return self._cached_trend_value

        if not self.coordinator.data:
            return None

        # Get current interval price and timestamp
        current_interval = self._get_current_interval_data()
        if not current_interval or "total" not in current_interval:
            return None

        current_interval_price = float(current_interval["total"])
        current_starts_at = dt_util.parse_datetime(current_interval["startsAt"])
        if current_starts_at is None:
            return None
        current_starts_at = dt_util.as_local(current_starts_at)

        # Get next interval timestamp (basis for calculation)
        next_interval_start = current_starts_at + timedelta(minutes=MINUTES_PER_INTERVAL)

        # Get future average price and detailed interval data
        future_avg = calculate_next_n_hours_avg(self.coordinator.data, hours)
        if future_avg is None:
            return None

        # Get configured thresholds from options
        threshold_rising = self.coordinator.config_entry.options.get(
            CONF_PRICE_TREND_THRESHOLD_RISING,
            DEFAULT_PRICE_TREND_THRESHOLD_RISING,
        )
        threshold_falling = self.coordinator.config_entry.options.get(
            CONF_PRICE_TREND_THRESHOLD_FALLING,
            DEFAULT_PRICE_TREND_THRESHOLD_FALLING,
        )

        # Calculate trend with configured thresholds
        trend_state, diff_pct = calculate_price_trend(
            current_interval_price, future_avg, threshold_rising=threshold_rising, threshold_falling=threshold_falling
        )

        # Determine icon color based on trend state
        icon_color = {
            "rising": "var(--error-color)",  # Red/Orange for rising prices (expensive)
            "falling": "var(--success-color)",  # Green for falling prices (cheaper)
            "stable": "var(--state-icon-color)",  # Default gray for stable prices
        }.get(trend_state, "var(--state-icon-color)")

        # Store attributes in sensor-specific dictionary AND cache the trend value
        self._trend_attributes = {
            "timestamp": next_interval_start.isoformat(),
            f"trend_{hours}h_%": round(diff_pct, 1),
            f"next_{hours}h_avg": round(future_avg * 100, 2),
            "interval_count": hours * 4,
            "threshold_rising": threshold_rising,
            "threshold_falling": threshold_falling,
            "icon_color": icon_color,
        }

        # Calculate additional attributes for better granularity
        if hours > MIN_HOURS_FOR_LATER_HALF:
            # Get second half average for longer periods
            later_half_avg = self._calculate_later_half_average(hours, next_interval_start)
            if later_half_avg is not None:
                self._trend_attributes[f"second_half_{hours}h_avg"] = round(later_half_avg * 100, 2)

                # Calculate incremental change: how much does the later half differ from current?
                if current_interval_price > 0:
                    later_half_diff = ((later_half_avg - current_interval_price) / current_interval_price) * 100
                    self._trend_attributes[f"second_half_{hours}h_diff_from_current_%"] = round(later_half_diff, 1)

        # Cache the trend value for consistency
        self._cached_trend_value = trend_state

        return trend_state

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
        if not self.coordinator.data:
            return None

        price_info = self.coordinator.data.get("priceInfo", {})
        today_prices = price_info.get("today", [])
        tomorrow_prices = price_info.get("tomorrow", [])
        all_prices = today_prices + tomorrow_prices

        if not all_prices:
            return None

        # Calculate which intervals belong to the later half
        total_intervals = hours * 4
        first_half_intervals = total_intervals // 2
        later_half_start = next_interval_start + timedelta(minutes=MINUTES_PER_INTERVAL * first_half_intervals)
        later_half_end = next_interval_start + timedelta(minutes=MINUTES_PER_INTERVAL * total_intervals)

        # Collect prices in the later half
        later_prices = []
        for price_data in all_prices:
            starts_at = dt_util.parse_datetime(price_data["startsAt"])
            if starts_at is None:
                continue
            starts_at = dt_util.as_local(starts_at)

            if later_half_start <= starts_at < later_half_end:
                price = price_data.get("total")
                if price is not None:
                    later_prices.append(float(price))

        if later_prices:
            return sum(later_prices) / len(later_prices)

        return None

    def _get_data_timestamp(self) -> datetime | None:
        """Get the latest data timestamp."""
        if not self.coordinator.data:
            return None

        price_info = self.coordinator.data.get("priceInfo", {})
        latest_timestamp = None

        for day in ["today", "tomorrow"]:
            for price_data in price_info.get(day, []):
                timestamp = datetime.fromisoformat(price_data["startsAt"])
                if not latest_timestamp or timestamp > latest_timestamp:
                    latest_timestamp = timestamp

        return dt_util.as_utc(latest_timestamp) if latest_timestamp else None

    def _get_volatility_value(self, *, volatility_type: str) -> str | None:
        """
        Calculate price volatility using coefficient of variation for different time periods.

        Args:
            volatility_type: One of "today", "tomorrow", "next_24h", "today_tomorrow"

        Returns:
            Volatility level: "low", "moderate", "high", "very_high", or None if unavailable

        """
        if not self.coordinator.data:
            return None

        price_info = self.coordinator.data.get("priceInfo", {})

        # Get volatility thresholds from config
        thresholds = {
            "threshold_moderate": self.coordinator.config_entry.options.get("volatility_threshold_moderate", 5.0),
            "threshold_high": self.coordinator.config_entry.options.get("volatility_threshold_high", 15.0),
            "threshold_very_high": self.coordinator.config_entry.options.get("volatility_threshold_very_high", 30.0),
        }

        # Get prices based on volatility type
        prices_to_analyze = get_prices_for_volatility(volatility_type, price_info)

        if not prices_to_analyze:
            return None

        # Calculate spread and basic statistics
        price_min = min(prices_to_analyze)
        price_max = max(prices_to_analyze)
        spread = price_max - price_min
        price_avg = sum(prices_to_analyze) / len(prices_to_analyze)

        # Convert to minor currency units (ct/øre) for display
        spread_minor = spread * 100

        # Calculate volatility level with custom thresholds (pass price list, not spread)
        volatility = calculate_volatility_level(prices_to_analyze, **thresholds)

        # Store attributes for this sensor
        self._last_volatility_attributes = {
            "price_spread": round(spread_minor, 2),
            "price_volatility": volatility,
            "price_min": round(price_min * 100, 2),
            "price_max": round(price_max * 100, 2),
            "price_avg": round(price_avg * 100, 2),
            "interval_count": len(prices_to_analyze),
        }

        # Add icon_color for dynamic styling
        add_icon_color_attribute(self._last_volatility_attributes, key="volatility", state_value=volatility)

        # Add type-specific attributes
        add_volatility_type_attributes(self._last_volatility_attributes, volatility_type, price_info, thresholds)

        # Return lowercase for ENUM device class
        return volatility.lower()

    # Add method to get future price intervals
    def _get_price_forecast_value(self) -> str | None:
        """Get the highest or lowest price status for the price forecast entity."""
        future_prices = get_future_prices(self.coordinator, max_intervals=MAX_FORECAST_INTERVALS)
        if not future_prices:
            return "No forecast data available"

        # Return a simple status message indicating how much forecast data is available
        return f"Forecast available for {len(future_prices)} intervals"

    @property
    def native_value(self) -> float | str | datetime | None:
        """Return the native value of the sensor."""
        try:
            if not self.coordinator.data or not self._value_getter:
                return None
            # For price_level, ensure we return the translated value as state
            if self.entity_description.key == "current_interval_price_level":
                return self._get_price_level_value()
            return self._value_getter()
        except (KeyError, ValueError, TypeError) as ex:
            self.coordinator.logger.exception(
                "Error getting sensor value",
                extra={
                    "error": str(ex),
                    "entity": self.entity_description.key,
                },
            )
            return None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement dynamically based on currency."""
        if self.entity_description.device_class != SensorDeviceClass.MONETARY:
            return None

        currency = None
        if self.coordinator.data:
            price_info = self.coordinator.data.get("priceInfo", {})
            currency = price_info.get("currency")

        return format_price_unit_minor(currency)

    @property
    def icon(self) -> str | None:
        """Return the icon based on sensor type and state."""
        key = self.entity_description.key
        value = self.native_value

        # Use centralized icon logic
        icon = get_dynamic_icon(
            key=key,
            value=value,
            coordinator_data=self.coordinator.data,
        )

        # Fall back to static icon from entity description
        return icon or self.entity_description.icon

    @property
    async def async_extra_state_attributes(self) -> dict | None:
        """Return additional state attributes asynchronously."""
        if not self.coordinator.data:
            return None

        attributes = self._get_sensor_attributes() or {}

        # Add description from the custom translations file
        if self.entity_description.translation_key and self.hass is not None:
            # Get user's language preference
            language = self.hass.config.language if self.hass.config.language else "en"

            # Add basic description
            description = await async_get_entity_description(
                self.hass, "sensor", self.entity_description.translation_key, language, "description"
            )
            if description:
                attributes["description"] = description

            # Check if extended descriptions are enabled in the config
            extended_descriptions = self.coordinator.config_entry.options.get(
                CONF_EXTENDED_DESCRIPTIONS,
                self.coordinator.config_entry.data.get(CONF_EXTENDED_DESCRIPTIONS, DEFAULT_EXTENDED_DESCRIPTIONS),
            )

            # Add extended descriptions if enabled
            if extended_descriptions:
                # Add long description if available
                long_desc = await async_get_entity_description(
                    self.hass, "sensor", self.entity_description.translation_key, language, "long_description"
                )
                if long_desc:
                    attributes["long_description"] = long_desc

                # Add usage tips if available
                usage_tips = await async_get_entity_description(
                    self.hass, "sensor", self.entity_description.translation_key, language, "usage_tips"
                )
                if usage_tips:
                    attributes["usage_tips"] = usage_tips

        return attributes if attributes else None

    @property
    def extra_state_attributes(self) -> dict | None:
        """
        Return additional state attributes (synchronous version).

        This synchronous method is required by Home Assistant and will
        first return basic attributes, then add cached descriptions
        without any blocking I/O operations.
        """
        if not self.coordinator.data:
            return None

        # Start with the basic attributes
        attributes = self._get_sensor_attributes() or {}

        # Add descriptions from the cache if available (non-blocking)
        if self.entity_description.translation_key and self.hass is not None:
            # Get user's language preference
            language = self.hass.config.language if self.hass.config.language else "en"
            translation_key = self.entity_description.translation_key

            # Add basic description from cache
            description = get_entity_description("sensor", translation_key, language, "description")
            if description:
                attributes["description"] = description

            # Check if extended descriptions are enabled in the config
            extended_descriptions = self.coordinator.config_entry.options.get(
                CONF_EXTENDED_DESCRIPTIONS,
                self.coordinator.config_entry.data.get(CONF_EXTENDED_DESCRIPTIONS, DEFAULT_EXTENDED_DESCRIPTIONS),
            )

            # Add extended descriptions if enabled (from cache only)
            if extended_descriptions:
                # Add long description if available in cache
                long_desc = get_entity_description("sensor", translation_key, language, "long_description")
                if long_desc:
                    attributes["long_description"] = long_desc

                # Add usage tips if available in cache
                usage_tips = get_entity_description("sensor", translation_key, language, "usage_tips")
                if usage_tips:
                    attributes["usage_tips"] = usage_tips

        return attributes if attributes else None

    def _get_sensor_attributes(self) -> dict | None:
        """Get attributes based on sensor type."""
        key = self.entity_description.key

        # Prepare cached data that attribute builders might need
        cached_data = {
            "trend_attributes": getattr(self, "_trend_attributes", None),
            "volatility_attributes": getattr(self, "_last_volatility_attributes", None),
            "last_extreme_interval": getattr(self, "_last_extreme_interval", None),
            "last_price_level": getattr(self, "_last_price_level", None),
            "last_rating_difference": getattr(self, "_last_rating_difference", None),
            "last_rating_level": getattr(self, "_last_rating_level", None),
            "data_timestamp": getattr(self, "_data_timestamp", None),
            "rolling_hour_level": self._get_rolling_hour_level_for_cached_data(key),
        }

        # Use the centralized attribute builder
        return build_sensor_attributes(
            key=key,
            coordinator=self.coordinator,
            native_value=self.native_value,
            cached_data=cached_data,
        )

    def _get_rolling_hour_level_for_cached_data(self, key: str) -> str | None:
        """Get rolling hour level for cached data if needed for icon color."""
        if key in ["current_hour_average", "next_hour_average"]:
            hour_offset = 0 if key == "current_hour_average" else 1
            result = self._get_rolling_hour_value(hour_offset=hour_offset, value_type="level")
            return result if isinstance(result, str) else None
        return None

    async def async_update(self) -> None:
        """Force a refresh when homeassistant.update_entity is called."""
        await self.coordinator.async_request_refresh()
