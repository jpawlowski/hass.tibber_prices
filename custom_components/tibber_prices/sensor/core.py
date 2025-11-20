"""Core sensor class for Tibber Prices integration."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 - Used at runtime for _get_data_timestamp()
from typing import TYPE_CHECKING, Any

from custom_components.tibber_prices.binary_sensor.attributes import (
    get_price_intervals_attributes,
)
from custom_components.tibber_prices.const import (
    CONF_PRICE_RATING_THRESHOLD_HIGH,
    CONF_PRICE_RATING_THRESHOLD_LOW,
    DEFAULT_PRICE_RATING_THRESHOLD_HIGH,
    DEFAULT_PRICE_RATING_THRESHOLD_LOW,
    DOMAIN,
    format_price_unit_major,
    format_price_unit_minor,
)
from custom_components.tibber_prices.coordinator import (
    MINUTE_UPDATE_ENTITY_KEYS,
    TIME_SENSITIVE_ENTITY_KEYS,
)
from custom_components.tibber_prices.entity import TibberPricesEntity
from custom_components.tibber_prices.entity_utils import (
    add_icon_color_attribute,
    find_rolling_hour_center_index,
    get_price_value,
)
from custom_components.tibber_prices.entity_utils.icons import (
    TibberPricesIconContext,
    get_dynamic_icon,
)
from custom_components.tibber_prices.utils.average import (
    calculate_next_n_hours_avg,
)
from custom_components.tibber_prices.utils.price import (
    calculate_volatility_level,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import callback

from .attributes import (
    add_volatility_type_attributes,
    build_extra_state_attributes,
    build_sensor_attributes,
    get_future_prices,
    get_prices_for_volatility,
)
from .calculators import (
    TibberPricesDailyStatCalculator,
    TibberPricesIntervalCalculator,
    TibberPricesMetadataCalculator,
    TibberPricesRollingHourCalculator,
    TibberPricesTimingCalculator,
    TibberPricesTrendCalculator,
    TibberPricesVolatilityCalculator,
    TibberPricesWindow24hCalculator,
)
from .chart_data import (
    build_chart_data_attributes,
    call_chartdata_service_async,
    get_chart_data_state,
)
from .helpers import aggregate_level_data, aggregate_rating_data
from .value_getters import get_value_getter_mapping

if TYPE_CHECKING:
    from collections.abc import Callable

    from custom_components.tibber_prices.coordinator import (
        TibberPricesDataUpdateCoordinator,
    )
    from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService

HOURS_IN_DAY = 24
LAST_HOUR_OF_DAY = 23
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
        # Instantiate calculators
        self._metadata_calculator = TibberPricesMetadataCalculator(coordinator)
        self._volatility_calculator = TibberPricesVolatilityCalculator(coordinator)
        self._window_24h_calculator = TibberPricesWindow24hCalculator(coordinator)
        self._rolling_hour_calculator = TibberPricesRollingHourCalculator(coordinator)
        self._daily_stat_calculator = TibberPricesDailyStatCalculator(coordinator)
        self._interval_calculator = TibberPricesIntervalCalculator(coordinator)
        self._timing_calculator = TibberPricesTimingCalculator(coordinator)
        self._trend_calculator = TibberPricesTrendCalculator(coordinator)
        self._value_getter: Callable | None = self._get_value_getter()
        self._time_sensitive_remove_listener: Callable | None = None
        self._minute_update_remove_listener: Callable | None = None
        # Chart data export (for chart_data_export sensor) - from binary_sensor
        self._chart_data_last_update = None  # Track last service call timestamp
        self._chart_data_error = None  # Track last service call error
        self._chart_data_response = None  # Store service response for attributes

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

        # For chart_data_export, trigger initial service call
        if self.entity_description.key == "chart_data_export":
            await self._refresh_chart_data()

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
    def _handle_time_sensitive_update(self, time_service: TibberPricesTimeService) -> None:
        """
        Handle time-sensitive update from coordinator.

        Args:
            time_service: TibberPricesTimeService instance with reference time for this update cycle

        """
        # Store TimeService from Timer #2 for calculations during this update cycle
        self.coordinator.time = time_service

        # Clear cached trend values on time-sensitive updates
        if self.entity_description.key.startswith("price_trend_"):
            self._trend_calculator.clear_trend_cache()
        # Clear trend calculation cache for trend sensors
        elif self.entity_description.key in ("current_price_trend", "next_price_trend_change"):
            self._trend_calculator.clear_calculation_cache()
        self.async_write_ha_state()

    @callback
    def _handle_minute_update(self, time_service: TibberPricesTimeService) -> None:
        """
        Handle minute-by-minute update from coordinator.

        Args:
            time_service: TibberPricesTimeService instance with reference time for this update cycle

        """
        # Store TimeService from Timer #3 for calculations during this update cycle
        self.coordinator.time = time_service

        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Clear cached trend values when coordinator data changes
        if self.entity_description.key.startswith("price_trend_"):
            self._trend_calculator.clear_trend_cache()
        super()._handle_coordinator_update()

    def _get_value_getter(self) -> Callable | None:
        """Return the appropriate value getter method based on the sensor type."""
        # Use centralized mapping from value_getters module
        handlers = get_value_getter_mapping(
            interval_calculator=self._interval_calculator,
            rolling_hour_calculator=self._rolling_hour_calculator,
            daily_stat_calculator=self._daily_stat_calculator,
            window_24h_calculator=self._window_24h_calculator,
            trend_calculator=self._trend_calculator,
            timing_calculator=self._timing_calculator,
            volatility_calculator=self._volatility_calculator,
            metadata_calculator=self._metadata_calculator,
            get_next_avg_n_hours_value=self._get_next_avg_n_hours_value,
            get_price_forecast_value=self._get_price_forecast_value,
            get_data_timestamp=self._get_data_timestamp,
            get_chart_data_export_value=self._get_chart_data_export_value,
        )
        return handlers.get(self.entity_description.key)

    def _get_current_interval_data(self) -> dict | None:
        """Get the price data for the current interval using coordinator utility."""
        return self.coordinator.get_current_interval()

    # ========================================================================
    # UNIFIED INTERVAL VALUE METHODS (NEW)
    # ========================================================================

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

        return self._rolling_hour_calculator.aggregate_window_data(window_data, value_type)

    # ========================================================================
    # INTERVAL-BASED VALUE METHODS
    # ========================================================================

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

        # Get TimeService from coordinator
        time = self.coordinator.time

        # Get local midnight boundaries based on the requested day using TimeService
        local_midnight, local_midnight_next_day = time.get_day_boundaries(day)

        # Collect all prices and their intervals from both today and tomorrow data
        # that fall within the target day's local date boundaries
        price_intervals = []
        for day_key in ["today", "tomorrow"]:
            for price_data in price_info.get(day_key, []):
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

        # Get local midnight boundaries based on the requested day using TimeService
        time = self.coordinator.time
        local_midnight, local_midnight_next_day = time.get_day_boundaries(day)

        # Collect all intervals from both today and tomorrow data
        # that fall within the target day's local date boundaries
        day_intervals = []
        for day_key in ["yesterday", "today", "tomorrow"]:
            for price_data in price_info.get(day_key, []):
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

    def _get_next_avg_n_hours_value(self, hours: int) -> float | None:
        """
        Get average price for next N hours starting from next interval.

        Args:
            hours: Number of hours to look ahead (1, 2, 3, 4, 5, 6, 8, 12)

        Returns:
            Average price in minor currency units (e.g., cents), or None if unavailable

        """
        avg_price = calculate_next_n_hours_avg(self.coordinator.data, hours, time=self.coordinator.time)
        if avg_price is None:
            return None

        # Convert from major to minor currency units (e.g., EUR to cents)
        return round(avg_price * 100, 2)

    def _get_data_timestamp(self) -> datetime | None:
        """
        Get the latest data timestamp from price data.

        Returns timezone-aware datetime of the most recent price interval.
        Home Assistant automatically displays TIMESTAMP sensors in user's timezone.

        Returns:
            Latest interval timestamp (timezone-aware), or None if no data available.

        """
        if not self.coordinator.data:
            return None

        price_info = self.coordinator.data.get("priceInfo", {})
        latest_timestamp = None

        for day in ["today", "tomorrow"]:
            for price_data in price_info.get(day, []):
                starts_at = price_data.get("startsAt")  # Already datetime in local timezone
                if not starts_at:
                    continue
                if not latest_timestamp or starts_at > latest_timestamp:
                    latest_timestamp = starts_at

        # Return timezone-aware datetime (HA handles timezone display automatically)
        return latest_timestamp

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
        prices_to_analyze = get_prices_for_volatility(volatility_type, price_info, time=self.coordinator.time)

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
        add_volatility_type_attributes(
            self._last_volatility_attributes, volatility_type, price_info, thresholds, time=self.coordinator.time
        )

        # Return lowercase for ENUM device class
        return volatility.lower()

    # ========================================================================
    # BEST/PEAK PRICE TIMING METHODS (period-based time tracking)
    # ========================================================================

    # Add method to get future price intervals
    def _get_price_forecast_value(self) -> str | None:
        """Get the highest or lowest price status for the price forecast entity."""
        future_prices = get_future_prices(
            self.coordinator, max_intervals=MAX_FORECAST_INTERVALS, time=self.coordinator.time
        )
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
                return self._interval_calculator.get_price_level_value()
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
        attrs = get_price_intervals_attributes(self.coordinator.data, reverse_sort=False, time=self.coordinator.time)
        if not attrs:
            return False
        start = attrs.get("start")
        end = attrs.get("end")
        if not start or not end:
            return False
        time = self.coordinator.time
        now = time.now()
        return start <= now < end

    def _is_peak_price_period_active(self) -> bool:
        """Check if the current time is within a peak price period."""
        if not self.coordinator.data:
            return False
        attrs = get_price_intervals_attributes(self.coordinator.data, reverse_sort=True, time=self.coordinator.time)
        if not attrs:
            return False
        start = attrs.get("start")
        end = attrs.get("end")
        if not start or not end:
            return False
        time = self.coordinator.time
        return time.is_current_interval(start, end)

    @property
    def icon(self) -> str | None:
        """Return the icon based on sensor type and state."""
        key = self.entity_description.key
        value = self.native_value

        # Icon mapping for trend directions
        trend_icons = {
            "rising": "mdi:trending-up",
            "falling": "mdi:trending-down",
            "stable": "mdi:trending-neutral",
        }

        # Special handling for next_price_trend_change: Icon based on direction attribute
        if key == "next_price_trend_change":
            trend_change_attrs = self._trend_calculator.get_trend_change_attributes()
            if trend_change_attrs:
                direction = trend_change_attrs.get("direction")
                if isinstance(direction, str):
                    return trend_icons.get(direction, "mdi:help-circle-outline")
            return "mdi:help-circle-outline"

        # Special handling for current_price_trend: Icon based on current state value
        if key == "current_price_trend" and isinstance(value, str):
            return trend_icons.get(value, "mdi:help-circle-outline")

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
            context=TibberPricesIconContext(
                coordinator_data=self.coordinator.data,
                period_is_active_callback=period_is_active_callback,
                time=self.coordinator.time,
            ),
        )

        # Fall back to static icon from entity description
        return icon or self.entity_description.icon

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        try:
            if not self.coordinator.data:
                return None

            # Get sensor-specific attributes
            sensor_attrs = self._get_sensor_attributes()

            time = self.coordinator.time

            # Build complete attributes using unified builder
            return build_extra_state_attributes(
                entity_key=self.entity_description.key,
                translation_key=self.entity_description.translation_key,
                hass=self.hass,
                config_entry=self.coordinator.config_entry,
                coordinator_data=self.coordinator.data,
                sensor_attrs=sensor_attrs,
                time=time,
            )

        except (KeyError, ValueError, TypeError) as ex:
            self.coordinator.logger.exception(
                "Error getting sensor attributes",
                extra={
                    "error": str(ex),
                    "entity": self.entity_description.key,
                },
            )
            return None

    def _get_sensor_attributes(self) -> dict | None:
        """Get attributes based on sensor type."""
        key = self.entity_description.key

        # Special handling for chart_data_export - returns chart data in attributes
        if key == "chart_data_export":
            return self._get_chart_data_export_attributes()

        # Prepare cached data that attribute builders might need
        cached_data = {
            "trend_attributes": self._trend_calculator.get_trend_attributes(),
            "current_trend_attributes": self._trend_calculator.get_current_trend_attributes(),
            "trend_change_attributes": self._trend_calculator.get_trend_change_attributes(),
            "volatility_attributes": self._volatility_calculator.get_volatility_attributes(),
            "last_extreme_interval": self._daily_stat_calculator.get_last_extreme_interval(),
            "last_price_level": self._interval_calculator.get_last_price_level(),
            "last_rating_difference": self._interval_calculator.get_last_rating_difference(),
            "last_rating_level": self._interval_calculator.get_last_rating_level(),
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
            result = self._rolling_hour_calculator.get_rolling_hour_value(hour_offset=hour_offset, value_type="level")
            return result if isinstance(result, str) else None
        return None

    async def async_update(self) -> None:
        """Force a refresh when homeassistant.update_entity is called."""
        await self.coordinator.async_request_refresh()

        # For chart_data_export, also refresh the service call
        if self.entity_description.key == "chart_data_export":
            await self._refresh_chart_data()

    # ========================================================================
    # CHART DATA EXPORT METHODS
    # ========================================================================

    def _get_chart_data_export_value(self) -> str | None:
        """Return state for chart_data_export sensor."""
        return get_chart_data_state(
            chart_data_response=self._chart_data_response,
            chart_data_error=self._chart_data_error,
        )

    async def _refresh_chart_data(self) -> None:
        """Refresh chart data by calling get_chartdata service."""
        response, error = await call_chartdata_service_async(
            hass=self.hass,
            coordinator=self.coordinator,
            config_entry=self.coordinator.config_entry,
        )
        self._chart_data_response = response
        time = self.coordinator.time
        self._chart_data_last_update = time.now()
        self._chart_data_error = error
        # Trigger state update after refresh
        self.async_write_ha_state()

    def _get_chart_data_export_attributes(self) -> dict[str, object] | None:
        """
        Return chart data from last service call as attributes with metadata.

        Delegates to chart_data module for attribute building.
        """
        return build_chart_data_attributes(
            chart_data_response=self._chart_data_response,
            chart_data_last_update=self._chart_data_last_update,
            chart_data_error=self._chart_data_error,
        )
