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
from custom_components.tibber_prices.binary_sensor.attributes import (
    get_price_intervals_attributes,
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
    format_price_unit_major,
    format_price_unit_minor,
    get_entity_description,
)
from custom_components.tibber_prices.coordinator import (
    MINUTE_UPDATE_ENTITY_KEYS,
    TIME_SENSITIVE_ENTITY_KEYS,
)
from custom_components.tibber_prices.entity import TibberPricesEntity
from custom_components.tibber_prices.entity_utils import (
    add_icon_color_attribute,
    get_dynamic_icon,
)
from custom_components.tibber_prices.entity_utils.icons import IconContext
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
from homeassistant.const import EntityCategory
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
PROGRESS_GRACE_PERIOD_SECONDS = 60  # Show 100% for 1 minute after period ends


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
        self._minute_update_remove_listener: Callable | None = None
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

        # Register with coordinator for minute-by-minute updates if applicable
        if self.entity_description.key in MINUTE_UPDATE_ENTITY_KEYS:
            self._minute_update_remove_listener = self.coordinator.async_add_minute_update_listener(
                self._handle_minute_update
            )

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        await super().async_will_remove_from_hass()

        # Remove time-sensitive listener if registered
        if self._time_sensitive_remove_listener:
            self._time_sensitive_remove_listener()
            self._time_sensitive_remove_listener = None

        # Remove minute-update listener if registered
        if self._minute_update_remove_listener:
            self._minute_update_remove_listener()
            self._minute_update_remove_listener = None

    @callback
    def _handle_time_sensitive_update(self) -> None:
        """Handle time-sensitive update from coordinator."""
        # Clear cached trend values on time-sensitive updates
        if self.entity_description.key.startswith("price_trend_"):
            self._cached_trend_value = None
            self._trend_attributes = {}
        self.async_write_ha_state()

    @callback
    def _handle_minute_update(self) -> None:
        """Handle minute-by-minute update from coordinator."""
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
            "current_interval_price_major": lambda: self._get_interval_value(
                interval_offset=0, value_type="price", in_euro=True
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
            "current_hour_average_price": lambda: self._get_rolling_hour_value(hour_offset=0, value_type="price"),
            "next_hour_average_price": lambda: self._get_rolling_hour_value(hour_offset=1, value_type="price"),
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
            # Daily aggregated level sensors
            "yesterday_price_level": lambda: self._get_daily_aggregated_value(day="yesterday", value_type="level"),
            "today_price_level": lambda: self._get_daily_aggregated_value(day="today", value_type="level"),
            "tomorrow_price_level": lambda: self._get_daily_aggregated_value(day="tomorrow", value_type="level"),
            # Daily aggregated rating sensors
            "yesterday_price_rating": lambda: self._get_daily_aggregated_value(day="yesterday", value_type="rating"),
            "today_price_rating": lambda: self._get_daily_aggregated_value(day="today", value_type="rating"),
            "tomorrow_price_rating": lambda: self._get_daily_aggregated_value(day="tomorrow", value_type="rating"),
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
            # Home metadata sensors
            "home_type": lambda: self._get_home_metadata_value("type"),
            "home_size": lambda: self._get_home_metadata_value("size"),
            "main_fuse_size": lambda: self._get_home_metadata_value("mainFuseSize"),
            "number_of_residents": lambda: self._get_home_metadata_value("numberOfResidents"),
            "primary_heating_source": lambda: self._get_home_metadata_value("primaryHeatingSource"),
            # Metering point sensors
            "grid_company": lambda: self._get_metering_point_value("gridCompany"),
            "grid_area_code": lambda: self._get_metering_point_value("gridAreaCode"),
            "price_area_code": lambda: self._get_metering_point_value("priceAreaCode"),
            "consumption_ean": lambda: self._get_metering_point_value("consumptionEan"),
            "production_ean": lambda: self._get_metering_point_value("productionEan"),
            "energy_tax_type": lambda: self._get_metering_point_value("energyTaxType"),
            "vat_type": lambda: self._get_metering_point_value("vatType"),
            "estimated_annual_consumption": lambda: self._get_metering_point_value("estimatedAnnualConsumption"),
            # Subscription sensors
            "subscription_status": lambda: self._get_subscription_value("status"),
            # Volatility sensors
            "today_volatility": lambda: self._get_volatility_value(volatility_type="today"),
            "tomorrow_volatility": lambda: self._get_volatility_value(volatility_type="tomorrow"),
            "next_24h_volatility": lambda: self._get_volatility_value(volatility_type="next_24h"),
            "today_tomorrow_volatility": lambda: self._get_volatility_value(volatility_type="today_tomorrow"),
            # ================================================================
            # BEST/PEAK PRICE TIMING SENSORS (period-based time tracking)
            # ================================================================
            # Best Price timing sensors
            "best_price_end_time": lambda: self._get_period_timing_value(
                period_type="best_price", value_type="end_time"
            ),
            "best_price_period_duration": lambda: self._get_period_timing_value(
                period_type="best_price", value_type="period_duration"
            ),
            "best_price_remaining_minutes": lambda: self._get_period_timing_value(
                period_type="best_price", value_type="remaining_minutes"
            ),
            "best_price_progress": lambda: self._get_period_timing_value(
                period_type="best_price", value_type="progress"
            ),
            "best_price_next_start_time": lambda: self._get_period_timing_value(
                period_type="best_price", value_type="next_start_time"
            ),
            "best_price_next_in_minutes": lambda: self._get_period_timing_value(
                period_type="best_price", value_type="next_in_minutes"
            ),
            # Peak Price timing sensors
            "peak_price_end_time": lambda: self._get_period_timing_value(
                period_type="peak_price", value_type="end_time"
            ),
            "peak_price_period_duration": lambda: self._get_period_timing_value(
                period_type="peak_price", value_type="period_duration"
            ),
            "peak_price_remaining_minutes": lambda: self._get_period_timing_value(
                period_type="peak_price", value_type="remaining_minutes"
            ),
            "peak_price_progress": lambda: self._get_period_timing_value(
                period_type="peak_price", value_type="progress"
            ),
            "peak_price_next_start_time": lambda: self._get_period_timing_value(
                period_type="peak_price", value_type="next_start_time"
            ),
            "peak_price_next_in_minutes": lambda: self._get_period_timing_value(
                period_type="peak_price", value_type="next_in_minutes"
            ),
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

    def _get_daily_aggregated_value(
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
            day: "yesterday", "today", or "tomorrow" - which calendar day to calculate for
            value_type: "level" or "rating" - type of aggregation to perform

        Returns:
            Aggregated level/rating value (lowercase), or None if unavailable

        """
        if not self.coordinator.data:
            return None

        price_info = self.coordinator.data.get("priceInfo", {})

        # Get local midnight boundaries based on the requested day
        local_midnight = dt_util.as_local(dt_util.start_of_local_day(dt_util.now()))
        if day == "tomorrow":
            local_midnight = local_midnight + timedelta(days=1)
        elif day == "yesterday":
            local_midnight = local_midnight - timedelta(days=1)
        local_midnight_next_day = local_midnight + timedelta(days=1)

        # Collect all intervals from both today and tomorrow data
        # that fall within the target day's local date boundaries
        day_intervals = []
        for day_key in ["yesterday", "today", "tomorrow"]:
            for price_data in price_info.get(day_key, []):
                starts_at_str = price_data.get("startsAt")
                if not starts_at_str:
                    continue

                starts_at = dt_util.parse_datetime(starts_at_str)
                if starts_at is None:
                    continue

                # Convert to local timezone for comparison
                starts_at = dt_util.as_local(starts_at)

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
            threshold_low = self.coordinator.config_entry.options.get(
                CONF_PRICE_RATING_THRESHOLD_LOW,
                DEFAULT_PRICE_RATING_THRESHOLD_LOW,
            )
            threshold_high = self.coordinator.config_entry.options.get(
                CONF_PRICE_RATING_THRESHOLD_HIGH,
                DEFAULT_PRICE_RATING_THRESHOLD_HIGH,
            )
            return aggregate_rating_data(day_intervals, threshold_low, threshold_high)

        return None

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

    # ========================================================================
    # BEST/PEAK PRICE TIMING METHODS (period-based time tracking)
    # ========================================================================

    def _get_period_timing_value(
        self,
        *,
        period_type: str,
        value_type: str,
    ) -> datetime | float | None:
        """
        Get timing-related values for best_price/peak_price periods.

        This method provides timing information based on whether a period is currently
        active or not, ensuring sensors always provide useful information.

        Value types behavior:
        - end_time: Active period → current end | No active → next period end | None if no periods
        - next_start_time: Active period → next-next start | No active → next start | None if no more
        - remaining_minutes: Active period → minutes to end | No active → 0
        - progress: Active period → 0-100% | No active → 0
        - next_in_minutes: Active period → minutes to next-next | No active → minutes to next | None if no more

        Args:
            period_type: "best_price" or "peak_price"
            value_type: "end_time", "remaining_minutes", "progress", "next_start_time", "next_in_minutes"

        Returns:
            - datetime for end_time/next_start_time
            - float for remaining_minutes/next_in_minutes/progress (or 0 when not active)
            - None if no relevant period data available

        """
        if not self.coordinator.data:
            return None

        # Get period data from coordinator
        periods_data = self.coordinator.data.get("periods", {})
        period_data = periods_data.get(period_type)

        if not period_data or not period_data.get("periods"):
            # No periods available - return 0 for numeric sensors, None for timestamps
            return 0 if value_type in ("remaining_minutes", "progress", "next_in_minutes") else None

        period_summaries = period_data["periods"]
        now = dt_util.now()

        # Find current, previous and next periods
        current_period = self._find_active_period(period_summaries, now)
        previous_period = self._find_previous_period(period_summaries, now)
        next_period = self._find_next_period(period_summaries, now, skip_current=bool(current_period))

        # Delegate to specific calculators
        return self._calculate_timing_value(value_type, current_period, previous_period, next_period, now)

    def _calculate_timing_value(
        self,
        value_type: str,
        current_period: dict | None,
        previous_period: dict | None,
        next_period: dict | None,
        now: datetime,
    ) -> datetime | float | None:
        """Calculate specific timing value based on type and available periods."""
        # Define calculation strategies for each value type
        calculators = {
            "end_time": lambda: (
                current_period.get("end") if current_period else (next_period.get("end") if next_period else None)
            ),
            "period_duration": lambda: self._calc_period_duration(current_period, next_period),
            "next_start_time": lambda: next_period.get("start") if next_period else None,
            "remaining_minutes": lambda: (self._calc_remaining_minutes(current_period, now) if current_period else 0),
            "progress": lambda: self._calc_progress_with_grace_period(current_period, previous_period, now),
            "next_in_minutes": lambda: (self._calc_next_in_minutes(next_period, now) if next_period else None),
        }

        calculator = calculators.get(value_type)
        return calculator() if calculator else None

    def _find_active_period(self, periods: list, now: datetime) -> dict | None:
        """Find currently active period."""
        for period in periods:
            start = period.get("start")
            end = period.get("end")
            if start and end and start <= now < end:
                return period
        return None

    def _find_previous_period(self, periods: list, now: datetime) -> dict | None:
        """Find the most recent period that has already ended."""
        past_periods = [p for p in periods if p.get("end") and p.get("end") <= now]

        if not past_periods:
            return None

        # Sort by end time descending to get the most recent one
        past_periods.sort(key=lambda p: p["end"], reverse=True)
        return past_periods[0]

    def _find_next_period(self, periods: list, now: datetime, *, skip_current: bool = False) -> dict | None:
        """
        Find next future period.

        Args:
            periods: List of period dictionaries
            now: Current time
            skip_current: If True, skip the first future period (to get next-next)

        Returns:
            Next period dict or None if no future periods

        """
        future_periods = [p for p in periods if p.get("start") and p.get("start") > now]

        if not future_periods:
            return None

        # Sort by start time to ensure correct order
        future_periods.sort(key=lambda p: p["start"])

        # Return second period if skip_current=True (next-next), otherwise first (next)
        if skip_current and len(future_periods) > 1:
            return future_periods[1]
        if not skip_current and future_periods:
            return future_periods[0]

        return None

    def _calc_remaining_minutes(self, period: dict, now: datetime) -> float:
        """Calculate minutes until period ends."""
        end = period.get("end")
        if not end:
            return 0
        delta = end - now
        return max(0, delta.total_seconds() / 60)

    def _calc_next_in_minutes(self, period: dict, now: datetime) -> float:
        """Calculate minutes until period starts."""
        start = period.get("start")
        if not start:
            return 0
        delta = start - now
        return max(0, delta.total_seconds() / 60)

    def _calc_period_duration(self, current_period: dict | None, next_period: dict | None) -> float | None:
        """
        Calculate total duration of active or next period in minutes.

        Returns duration of current period if active, otherwise duration of next period.
        This gives users a consistent view of period length regardless of timing.

        Args:
            current_period: Currently active period (if any)
            next_period: Next upcoming period (if any)

        Returns:
            Duration in minutes, or None if no periods available

        """
        period = current_period or next_period
        if not period:
            return None

        start = period.get("start")
        end = period.get("end")
        if not start or not end:
            return None

        duration = (end - start).total_seconds() / 60
        return max(0, duration)

    def _calc_progress(self, period: dict, now: datetime) -> float:
        """Calculate progress percentage (0-100) of current period."""
        start = period.get("start")
        end = period.get("end")
        if not start or not end:
            return 0
        total_duration = (end - start).total_seconds()
        if total_duration <= 0:
            return 0
        elapsed = (now - start).total_seconds()
        progress = (elapsed / total_duration) * 100
        return min(100, max(0, progress))

    def _calc_progress_with_grace_period(
        self, current_period: dict | None, previous_period: dict | None, now: datetime
    ) -> float:
        """
        Calculate progress with grace period after period end.

        Shows 100% for 1 minute after period ends to allow triggers on 100% completion.
        This prevents the progress from jumping directly from ~99% to 0% without ever
        reaching 100%, which would make automations like "when progress = 100%" impossible.
        """
        # If we have an active period, calculate normal progress
        if current_period:
            return self._calc_progress(current_period, now)

        # No active period - check if we just finished one (within grace period)
        if previous_period:
            previous_end = previous_period.get("end")
            if previous_end:
                seconds_since_end = (now - previous_end).total_seconds()
                # Grace period: Show 100% for defined time after period ended
                if 0 <= seconds_since_end <= PROGRESS_GRACE_PERIOD_SECONDS:
                    return 100

        # No active period and either no previous period or grace period expired
        return 0

    # Add method to get future price intervals
    def _get_price_forecast_value(self) -> str | None:
        """Get the highest or lowest price status for the price forecast entity."""
        future_prices = get_future_prices(self.coordinator, max_intervals=MAX_FORECAST_INTERVALS)
        if not future_prices:
            return "No forecast data available"

        # Return a simple status message indicating how much forecast data is available
        return f"Forecast available for {len(future_prices)} intervals"

    def _get_home_metadata_value(self, field: str) -> str | int | None:
        """
        Get home metadata value from user data.

        String values are converted to lowercase for ENUM device_class compatibility.
        """
        user_homes = self.coordinator.get_user_homes()
        if not user_homes:
            return None

        # Find the home matching this sensor's home_id
        home_id = self.coordinator.config_entry.data.get("home_id")
        if not home_id:
            return None

        home_data = next((home for home in user_homes if home.get("id") == home_id), None)
        if not home_data:
            return None

        value = home_data.get(field)

        # Convert string to lowercase for ENUM device_class
        if isinstance(value, str):
            return value.lower()

        return value

    def _get_metering_point_value(self, field: str) -> str | int | None:
        """Get metering point data value from user data."""
        user_homes = self.coordinator.get_user_homes()
        if not user_homes:
            return None

        home_id = self.coordinator.config_entry.data.get("home_id")
        if not home_id:
            return None

        home_data = next((home for home in user_homes if home.get("id") == home_id), None)
        if not home_data:
            return None

        metering_point = home_data.get("meteringPointData")
        if not metering_point:
            return None

        return metering_point.get(field)

    def _get_subscription_value(self, field: str) -> str | None:
        """
        Get subscription value from user data.

        String values are converted to lowercase for ENUM device_class compatibility.
        """
        user_homes = self.coordinator.get_user_homes()
        if not user_homes:
            return None

        home_id = self.coordinator.config_entry.data.get("home_id")
        if not home_id:
            return None

        home_data = next((home for home in user_homes if home.get("id") == home_id), None)
        if not home_data:
            return None

        subscription = home_data.get("currentSubscription")
        if not subscription:
            return None

        value = subscription.get(field)

        # Convert string to lowercase for ENUM device_class
        if isinstance(value, str):
            return value.lower()

        return value

    @property
    def available(self) -> bool:
        """
        Return if entity is available.

        For diagnostic sensors, hide them if they have no data (return None).
        User requirement: Don't show sensors with "Unknown" state.
        """
        # First check if coordinator is available
        if not super().available:
            return False

        # For diagnostic sensors with no data, hide them completely
        if self.entity_description.entity_category == EntityCategory.DIAGNOSTIC:
            try:
                value = self.native_value
            except (KeyError, ValueError, TypeError):
                # If we can't get the value, hide the sensor
                return False
            else:
                # Hide sensor if value is None (no data available)
                return value is not None

        # For all other sensors, use default availability
        return True

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
        """Return the unit of measurement dynamically based on currency or entity description."""
        # For MONETARY sensors, return currency-specific unit
        if self.entity_description.device_class == SensorDeviceClass.MONETARY:
            currency = None
            if self.coordinator.data:
                price_info = self.coordinator.data.get("priceInfo", {})
                currency = price_info.get("currency")

            # Use major currency unit for Energy Dashboard sensor
            if self.entity_description.key == "current_interval_price_major":
                return format_price_unit_major(currency)

            # Use minor currency unit for all other price sensors
            return format_price_unit_minor(currency)

        # For all other sensors, use unit from entity description
        return self.entity_description.native_unit_of_measurement

    def _is_best_price_period_active(self) -> bool:
        """Check if the current time is within a best price period."""
        if not self.coordinator.data:
            return False
        attrs = get_price_intervals_attributes(self.coordinator.data, reverse_sort=False)
        if not attrs:
            return False
        start = attrs.get("start")
        end = attrs.get("end")
        if not start or not end:
            return False
        now = dt_util.now()
        return start <= now < end

    def _is_peak_price_period_active(self) -> bool:
        """Check if the current time is within a peak price period."""
        if not self.coordinator.data:
            return False
        attrs = get_price_intervals_attributes(self.coordinator.data, reverse_sort=True)
        if not attrs:
            return False
        start = attrs.get("start")
        end = attrs.get("end")
        if not start or not end:
            return False
        now = dt_util.now()
        return start <= now < end

    @property
    def icon(self) -> str | None:
        """Return the icon based on sensor type and state."""
        key = self.entity_description.key
        value = self.native_value

        # Create callback for period active state check (used by timing sensors)
        period_is_active_callback = None
        if key.startswith("best_price_"):
            period_is_active_callback = self._is_best_price_period_active
        elif key.startswith("peak_price_"):
            period_is_active_callback = self._is_peak_price_period_active

        # Use centralized icon logic with context
        icon = get_dynamic_icon(
            key=key,
            value=value,
            context=IconContext(
                coordinator_data=self.coordinator.data,
                period_is_active_callback=period_is_active_callback,
            ),
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
        if key in ["current_hour_average_price", "next_hour_average_price"]:
            hour_offset = 0 if key == "current_hour_average_price" else 1
            result = self._get_rolling_hour_value(hour_offset=hour_offset, value_type="level")
            return result if isinstance(result, str) else None
        return None

    async def async_update(self) -> None:
        """Force a refresh when homeassistant.update_entity is called."""
        await self.coordinator.async_request_refresh()
