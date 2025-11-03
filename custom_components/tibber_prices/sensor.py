"""Sensor platform for tibber_prices."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    CURRENCY_EURO,
    PERCENTAGE,
    EntityCategory,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.util import dt as dt_util

from .average_utils import (
    calculate_current_leading_avg,
    calculate_current_leading_max,
    calculate_current_leading_min,
    calculate_current_rolling_5interval_avg,
    calculate_current_trailing_avg,
    calculate_current_trailing_max,
    calculate_current_trailing_min,
    calculate_next_hour_rolling_5interval_avg,
)
from .const import (
    CONF_EXTENDED_DESCRIPTIONS,
    CONF_PRICE_RATING_THRESHOLD_HIGH,
    CONF_PRICE_RATING_THRESHOLD_LOW,
    DEFAULT_EXTENDED_DESCRIPTIONS,
    DEFAULT_PRICE_RATING_THRESHOLD_HIGH,
    DEFAULT_PRICE_RATING_THRESHOLD_LOW,
    DOMAIN,
    PRICE_LEVEL_MAPPING,
    PRICE_RATING_MAPPING,
    async_get_entity_description,
    get_entity_description,
    get_price_level_translation,
)
from .entity import TibberPricesEntity
from .price_utils import (
    MINUTES_PER_INTERVAL,
    aggregate_price_levels,
    aggregate_price_rating,
    find_price_data_for_interval,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import TibberPricesDataUpdateCoordinator
    from .data import TibberPricesConfigEntry

PRICE_UNIT = CURRENCY_EURO + "/" + UnitOfPower.KILO_WATT + UnitOfTime.HOURS
PRICE_UNIT_MINOR = "ct/" + UnitOfPower.KILO_WATT + UnitOfTime.HOURS
HOURS_IN_DAY = 24
LAST_HOUR_OF_DAY = 23
INTERVALS_PER_HOUR = 4  # 15-minute intervals
MAX_FORECAST_INTERVALS = 8  # Show up to 8 future intervals (2 hours with 15-min intervals)

# Main price sensors that users will typically use in automations
PRICE_SENSORS = (
    SensorEntityDescription(
        key="current_price",
        translation_key="current_price_cents",
        name="Current Electricity Price",
        icon="mdi:currency-eur",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=PRICE_UNIT_MINOR,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="next_interval_price",
        translation_key="next_interval_price_cents",
        name="Next Price",
        icon="mdi:clock-fast",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=PRICE_UNIT_MINOR,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="previous_interval_price",
        translation_key="previous_interval_price_cents",
        name="Previous Electricity Price",
        icon="mdi:history",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=PRICE_UNIT_MINOR,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="current_hour_average",
        translation_key="current_hour_average_cents",
        name="Current Hour Average Price",
        icon="mdi:currency-eur",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=PRICE_UNIT_MINOR,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="next_hour_average",
        translation_key="next_hour_average_cents",
        name="Next Hour Average Price",
        icon="mdi:clock-fast",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=PRICE_UNIT_MINOR,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="price_level",
        translation_key="price_level",
        name="Current Price Level",
        icon="mdi:gauge",
    ),
    SensorEntityDescription(
        key="next_interval_price_level",
        translation_key="next_interval_price_level",
        name="Next Price Level",
        icon="mdi:gauge-empty",
    ),
    SensorEntityDescription(
        key="previous_interval_price_level",
        translation_key="previous_interval_price_level",
        name="Previous Price Level",
        icon="mdi:gauge-empty",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="current_hour_price_level",
        translation_key="current_hour_price_level",
        name="Current Hour Price Level",
        icon="mdi:gauge",
    ),
    SensorEntityDescription(
        key="next_hour_price_level",
        translation_key="next_hour_price_level",
        name="Next Hour Price Level",
        icon="mdi:gauge-empty",
    ),
)

# Statistical price sensors
STATISTICS_SENSORS = (
    SensorEntityDescription(
        key="lowest_price_today",
        translation_key="lowest_price_today_cents",
        name="Today's Lowest Price",
        icon="mdi:arrow-collapse-down",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=PRICE_UNIT_MINOR,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="highest_price_today",
        translation_key="highest_price_today_cents",
        name="Today's Highest Price",
        icon="mdi:arrow-collapse-up",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=PRICE_UNIT_MINOR,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="average_price_today",
        translation_key="average_price_today_cents",
        name="Today's Average Price",
        icon="mdi:chart-line",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=PRICE_UNIT_MINOR,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="lowest_price_tomorrow",
        translation_key="lowest_price_tomorrow_cents",
        name="Tomorrow's Lowest Price",
        icon="mdi:arrow-collapse-down",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=PRICE_UNIT_MINOR,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="highest_price_tomorrow",
        translation_key="highest_price_tomorrow_cents",
        name="Tomorrow's Highest Price",
        icon="mdi:arrow-collapse-up",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=PRICE_UNIT_MINOR,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="average_price_tomorrow",
        translation_key="average_price_tomorrow_cents",
        name="Tomorrow's Average Price",
        icon="mdi:chart-line",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=PRICE_UNIT_MINOR,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="trailing_price_average",
        translation_key="trailing_price_average_cents",
        name="Trailing 24h Average Price",
        icon="mdi:chart-line",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=PRICE_UNIT_MINOR,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="leading_price_average",
        translation_key="leading_price_average_cents",
        name="Leading 24h Average Price",
        icon="mdi:chart-line-variant",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=PRICE_UNIT_MINOR,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="trailing_price_min",
        translation_key="trailing_price_min_cents",
        name="Trailing 24h Minimum Price",
        icon="mdi:arrow-collapse-down",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=PRICE_UNIT_MINOR,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="trailing_price_max",
        translation_key="trailing_price_max_cents",
        name="Trailing 24h Maximum Price",
        icon="mdi:arrow-collapse-up",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=PRICE_UNIT_MINOR,
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="leading_price_min",
        translation_key="leading_price_min_cents",
        name="Leading 24h Minimum Price",
        icon="mdi:arrow-collapse-down",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=PRICE_UNIT_MINOR,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="leading_price_max",
        translation_key="leading_price_max_cents",
        name="Leading 24h Maximum Price",
        icon="mdi:arrow-collapse-up",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=PRICE_UNIT_MINOR,
        suggested_display_precision=1,
    ),
)

# Rating sensors
RATING_SENSORS = (
    SensorEntityDescription(
        key="price_rating",
        translation_key="price_rating",
        name="Current Price Rating",
        icon="mdi:star-outline",
    ),
    SensorEntityDescription(
        key="next_interval_price_rating",
        translation_key="next_interval_price_rating",
        name="Next Price Rating",
        icon="mdi:star-half-full",
    ),
    SensorEntityDescription(
        key="previous_interval_price_rating",
        translation_key="previous_interval_price_rating",
        name="Previous Price Rating",
        icon="mdi:star-half-full",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="current_hour_price_rating",
        translation_key="current_hour_price_rating",
        name="Current Hour Price Rating",
        icon="mdi:star-outline",
    ),
    SensorEntityDescription(
        key="next_hour_price_rating",
        translation_key="next_hour_price_rating",
        name="Next Hour Price Rating",
        icon="mdi:star-half-full",
    ),
)

# Diagnostic sensors for data availability
DIAGNOSTIC_SENSORS = (
    SensorEntityDescription(
        key="data_timestamp",
        translation_key="data_timestamp",
        name="Data Expiration",
        icon="mdi:clock-check",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="price_forecast",
        translation_key="price_forecast",
        name="Price Forecast",
        icon="mdi:chart-line",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

# Combine all sensors
ENTITY_DESCRIPTIONS = (
    *PRICE_SENSORS,
    *STATISTICS_SENSORS,
    *RATING_SENSORS,
    *DIAGNOSTIC_SENSORS,
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: TibberPricesConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    async_add_entities(
        TibberPricesSensor(
            coordinator=entry.runtime_data.coordinator,
            entity_description=entity_description,
        )
        for entity_description in ENTITY_DESCRIPTIONS
    )


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

    def _get_value_getter(self) -> Callable | None:
        """Return the appropriate value getter method based on the sensor type."""
        key = self.entity_description.key

        # Map sensor keys to their handler methods
        handlers = {
            # Price level sensors
            "price_level": self._get_price_level_value,
            "next_interval_price_level": lambda: self._get_interval_level_value(interval_offset=1),
            "previous_interval_price_level": lambda: self._get_interval_level_value(interval_offset=-1),
            "current_hour_price_level": lambda: self._get_rolling_hour_level_value(hour_offset=0),
            "next_hour_price_level": lambda: self._get_rolling_hour_level_value(hour_offset=1),
            # Price sensors
            "current_price": lambda: self._get_interval_price_value(interval_offset=0, in_euro=False),
            "next_interval_price": lambda: self._get_interval_price_value(interval_offset=1, in_euro=False),
            "previous_interval_price": lambda: self._get_interval_price_value(interval_offset=-1, in_euro=False),
            # Rolling hour average (5 intervals: 2 before + current + 2 after)
            "current_hour_average": lambda: self._get_rolling_hour_average_value(
                in_euro=False, decimals=2, hour_offset=0
            ),
            "next_hour_average": lambda: self._get_rolling_hour_average_value(in_euro=False, decimals=2, hour_offset=1),
            # Statistics sensors
            "lowest_price_today": lambda: self._get_statistics_value(stat_func=min, in_euro=False, decimals=2),
            "highest_price_today": lambda: self._get_statistics_value(stat_func=max, in_euro=False, decimals=2),
            "average_price_today": lambda: self._get_statistics_value(
                stat_func=lambda prices: sum(prices) / len(prices),
                in_euro=False,
                decimals=2,
            ),
            # Tomorrow statistics sensors
            "lowest_price_tomorrow": lambda: self._get_statistics_value(
                stat_func=min, in_euro=False, decimals=2, day="tomorrow"
            ),
            "highest_price_tomorrow": lambda: self._get_statistics_value(
                stat_func=max, in_euro=False, decimals=2, day="tomorrow"
            ),
            "average_price_tomorrow": lambda: self._get_statistics_value(
                stat_func=lambda prices: sum(prices) / len(prices),
                in_euro=False,
                decimals=2,
                day="tomorrow",
            ),
            # Trailing and leading average sensors
            "trailing_price_average": lambda: self._get_average_value(
                average_type="trailing",
                in_euro=False,
                decimals=2,
            ),
            "leading_price_average": lambda: self._get_average_value(
                average_type="leading",
                in_euro=False,
                decimals=2,
            ),
            # Trailing and leading min/max sensors
            "trailing_price_min": lambda: self._get_minmax_value(
                stat_type="trailing",
                func_type="min",
                in_euro=False,
                decimals=2,
            ),
            "trailing_price_max": lambda: self._get_minmax_value(
                stat_type="trailing",
                func_type="max",
                in_euro=False,
                decimals=2,
            ),
            "leading_price_min": lambda: self._get_minmax_value(
                stat_type="leading",
                func_type="min",
                in_euro=False,
                decimals=2,
            ),
            "leading_price_max": lambda: self._get_minmax_value(
                stat_type="leading",
                func_type="max",
                in_euro=False,
                decimals=2,
            ),
            # Rating sensors
            "price_rating": lambda: self._get_rating_value(rating_type="current"),
            "next_interval_price_rating": lambda: self._get_interval_rating_value(interval_offset=1),
            "previous_interval_price_rating": lambda: self._get_interval_rating_value(interval_offset=-1),
            "current_hour_price_rating": lambda: self._get_rolling_hour_rating_value(hour_offset=0),
            "next_hour_price_rating": lambda: self._get_rolling_hour_rating_value(hour_offset=1),
            # Diagnostic sensors
            "data_timestamp": self._get_data_timestamp,
            # Price forecast sensor
            "price_forecast": self._get_price_forecast_value,
        }

        return handlers.get(key)

    def _get_current_interval_data(self) -> dict | None:
        """Get the price data for the current interval using coordinator utility."""
        return self.coordinator.get_current_interval()

    def _get_price_level_value(self) -> str | None:
        """Get the current price level value as a translated string for the state."""
        current_interval_data = self._get_current_interval_data()
        if not current_interval_data or "level" not in current_interval_data:
            return None
        level = current_interval_data["level"]
        self._last_price_level = level
        # Use the translation helper for price level, fallback to English if needed
        if self.hass:
            language = self.hass.config.language or "en"
            translated = get_price_level_translation(level, language)
            if translated:
                return translated
            if language != "en":
                fallback = get_price_level_translation(level, "en")
                if fallback:
                    return fallback
        return level

    def _get_interval_level_value(self, *, interval_offset: int) -> str | None:
        """Get price level for an interval with offset (e.g., next or previous interval)."""
        if not self.coordinator.data:
            return None

        price_info = self.coordinator.data.get("priceInfo", {})
        now = dt_util.now()
        target_time = now + timedelta(minutes=MINUTES_PER_INTERVAL * interval_offset)

        interval_data = find_price_data_for_interval(price_info, target_time)
        if not interval_data or "level" not in interval_data:
            return None

        level = interval_data["level"]
        # Translate the level
        if self.hass:
            language = self.hass.config.language or "en"
            translated = get_price_level_translation(level, language)
            if translated:
                return translated
            if language != "en":
                fallback = get_price_level_translation(level, "en")
                if fallback:
                    return fallback
        return level

    def _get_rolling_hour_level_value(self, *, hour_offset: int) -> str | None:
        """Get aggregated price level for a 5-interval rolling window."""
        if not self.coordinator.data:
            return None

        price_info = self.coordinator.data.get("priceInfo", {})
        yesterday_prices = price_info.get("yesterday", [])
        today_prices = price_info.get("today", [])
        tomorrow_prices = price_info.get("tomorrow", [])

        all_prices = yesterday_prices + today_prices + tomorrow_prices
        if not all_prices:
            return None

        center_idx = self._find_rolling_hour_center_index(all_prices, hour_offset)
        if center_idx is None:
            return None

        levels = self._collect_rolling_window_levels(all_prices, center_idx)
        if not levels:
            return None

        aggregated_level = aggregate_price_levels(levels)
        return self._translate_level(aggregated_level)

    def _find_rolling_hour_center_index(self, all_prices: list, hour_offset: int) -> int | None:
        """Find the center index for the rolling hour window."""
        now = dt_util.now()
        current_idx = None

        for idx, price_data in enumerate(all_prices):
            starts_at = dt_util.parse_datetime(price_data["startsAt"])
            if starts_at is None:
                continue
            starts_at = dt_util.as_local(starts_at)
            interval_end = starts_at + timedelta(minutes=15)

            if starts_at <= now < interval_end:
                current_idx = idx
                break

        if current_idx is None:
            return None

        return current_idx + (hour_offset * 4)

    def _collect_rolling_window_levels(self, all_prices: list, center_idx: int) -> list:
        """Collect levels from 2 intervals before to 2 intervals after."""
        levels = []
        for offset in range(-2, 3):  # -2, -1, 0, 1, 2
            idx = center_idx + offset
            if 0 <= idx < len(all_prices):
                level = all_prices[idx].get("level")
                if level is not None:
                    levels.append(level)
        return levels

    def _translate_level(self, level: str) -> str:
        """Translate the level to the user's language."""
        if not self.hass:
            return level

        language = self.hass.config.language or "en"
        translated = get_price_level_translation(level, language)
        if translated:
            return translated

        if language != "en":
            fallback = get_price_level_translation(level, "en")
            if fallback:
                return fallback

        return level

    def _get_price_value(self, price: float, *, in_euro: bool) -> float:
        """Convert price based on unit."""
        return price if in_euro else round((price * 100), 2)

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
                return self._get_price_value(float(price_data["total"]), in_euro=in_euro)

        # If we didn't find the price in the expected day's data, check the other day
        # This is a fallback for potential edge cases
        other_day_key = "today" if day_key == "tomorrow" else "tomorrow"
        for price_data in price_info.get(other_day_key, []):
            starts_at = dt_util.parse_datetime(price_data["startsAt"])
            if starts_at is None:
                continue

            starts_at = dt_util.as_local(starts_at)
            if starts_at.hour == target_hour and starts_at.date() == target_date:
                return self._get_price_value(float(price_data["total"]), in_euro=in_euro)

        return None

    def _get_interval_price_value(self, *, interval_offset: int, in_euro: bool) -> float | None:
        """Get price for the current interval or with offset, handling 15-minute intervals."""
        if not self.coordinator.data:
            return None

        all_intervals = self.coordinator.get_all_intervals()
        if not all_intervals:
            return None

        now = dt_util.now()

        current_idx = None
        for idx, interval in enumerate(all_intervals):
            starts_at = interval.get("startsAt")
            if starts_at:
                ts = dt_util.parse_datetime(starts_at)
                if ts and ts <= now < ts + timedelta(minutes=MINUTES_PER_INTERVAL):
                    current_idx = idx
                    break

        if current_idx is None:
            return None

        target_idx = current_idx + interval_offset
        if 0 <= target_idx < len(all_intervals):
            price = float(all_intervals[target_idx]["total"])
            return price if in_euro else round(price * 100, 2)

        return None

    def _get_statistics_value(
        self,
        *,
        stat_func: Callable[[list[float]], float],
        in_euro: bool,
        decimals: int | None = None,
        day: str = "today",
    ) -> float | None:
        """
        Handle statistics sensor values using the provided statistical function.

        Args:
            stat_func: The statistical function to apply (min, max, avg, etc.)
            in_euro: Whether to return the value in euros (True) or cents (False)
            decimals: Number of decimal places to round to
            day: Which day to calculate for - "today" or "tomorrow"

        Returns:
            The calculated value for the statistics sensor, or None if unavailable.

        """
        if not self.coordinator.data:
            return None

        price_info = self.coordinator.data.get("priceInfo", {})

        # Get local midnight boundaries based on the requested day
        local_midnight = dt_util.as_local(dt_util.start_of_local_day(dt_util.now()))
        if day == "tomorrow":
            local_midnight = local_midnight + timedelta(days=1)
        local_midnight_next_day = local_midnight + timedelta(days=1)

        # Collect all prices and their intervals from both today and tomorrow data that fall within the target day
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

        result = self._get_price_value(value, in_euro=in_euro)

        if decimals is not None:
            result = round(result, decimals)
        return result

    def _get_average_value(
        self,
        *,
        average_type: str,
        in_euro: bool,
        decimals: int | None = None,
    ) -> float | None:
        """
        Get trailing or leading 24-hour average price.

        Args:
            average_type: Either "trailing" or "leading"
            in_euro: If True, return value in euros; if False, return in cents
            decimals: Number of decimal places to round to, or None for no rounding

        Returns:
            The calculated average value, or None if unavailable

        """
        if average_type == "trailing":
            value = calculate_current_trailing_avg(self.coordinator.data)
        elif average_type == "leading":
            value = calculate_current_leading_avg(self.coordinator.data)
        else:
            return None

        if value is None:
            return None

        result = self._get_price_value(value, in_euro=in_euro)

        if decimals is not None:
            result = round(result, decimals)
        return result

    def _get_rolling_hour_average_value(
        self,
        *,
        in_euro: bool,
        decimals: int | None = None,
        hour_offset: int = 0,
    ) -> float | None:
        """
        Get rolling 5-interval average (2 previous + current + 2 next).

        This provides a smoothed "hour price" centered around a specific hour.
        With hour_offset=0, it's centered on the current interval.
        With hour_offset=1, it's centered on the interval 1 hour ahead.

        Args:
            in_euro: If True, return value in euros; if False, return in cents
            decimals: Number of decimal places to round to, or None for no rounding
            hour_offset: Number of hours to shift forward (0=current, 1=next hour)

        Returns:
            The calculated rolling average value, or None if unavailable

        """
        if hour_offset == 0:
            value = calculate_current_rolling_5interval_avg(self.coordinator.data)
        elif hour_offset == 1:
            value = calculate_next_hour_rolling_5interval_avg(self.coordinator.data)
        else:
            return None

        if value is None:
            return None

        result = self._get_price_value(value, in_euro=in_euro)

        if decimals is not None:
            result = round(result, decimals)
        return result

    def _get_minmax_value(
        self,
        *,
        stat_type: str,
        func_type: str,
        in_euro: bool,
        decimals: int | None = None,
    ) -> float | None:
        """
        Get trailing or leading 24-hour minimum or maximum price.

        Args:
            stat_type: Either "trailing" or "leading"
            func_type: Either "min" or "max"
            in_euro: If True, return value in euros; if False, return in cents
            decimals: Number of decimal places to round to, or None for no rounding

        Returns:
            The calculated min/max value, or None if unavailable

        """
        if stat_type == "trailing" and func_type == "min":
            value = calculate_current_trailing_min(self.coordinator.data)
        elif stat_type == "trailing" and func_type == "max":
            value = calculate_current_trailing_max(self.coordinator.data)
        elif stat_type == "leading" and func_type == "min":
            value = calculate_current_leading_min(self.coordinator.data)
        elif stat_type == "leading" and func_type == "max":
            value = calculate_current_leading_max(self.coordinator.data)
        else:
            return None

        if value is None:
            return None

        result = self._get_price_value(value, in_euro=in_euro)

        if decimals is not None:
            result = round(result, decimals)
        return result

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
            and "price_rating" in translations["sensor"]
            and "price_levels" in translations["sensor"]["price_rating"]
            and level in translations["sensor"]["price_rating"]["price_levels"]
        ):
            return translations["sensor"]["price_rating"]["price_levels"][level]
        # Fallback to English if not found
        if language != "en":
            en_cache_key = f"{DOMAIN}_translations_en"
            en_translations = self.hass.data.get(en_cache_key)
            if (
                en_translations
                and "sensor" in en_translations
                and "price_rating" in en_translations
                and "price_levels" in en_translations["sensor"]["price_rating"]
                and level in en_translations["sensor"]["price_rating"]["price_levels"]
            ):
                return en_translations["sensor"]["price_rating"]["price_levels"][level]
        return level

    def _get_rating_value(self, *, rating_type: str) -> str | None:
        """
        Get the price rating level from the current price interval in priceInfo.

        Returns the translated rating level as the main status, and stores the original
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
                return self._translate_rating_level(rating_level)

        self._last_rating_difference = None
        self._last_rating_level = None
        return None

    def _get_interval_rating_value(self, *, interval_offset: int) -> str | None:
        """Get price rating for an interval with offset (e.g., next or previous interval)."""
        if not self.coordinator.data:
            return None

        price_info = self.coordinator.data.get("priceInfo", {})
        now = dt_util.now()
        target_time = now + timedelta(minutes=MINUTES_PER_INTERVAL * interval_offset)

        interval_data = find_price_data_for_interval(price_info, target_time)
        if not interval_data:
            return None

        rating_level = interval_data.get("rating_level")
        if rating_level is not None:
            return self._translate_rating_level(rating_level)
        return None

    def _get_rolling_hour_rating_value(self, *, hour_offset: int) -> str | None:
        """Get aggregated price rating for a 5-interval rolling window."""
        if not self.coordinator.data:
            return None

        price_info = self.coordinator.data.get("priceInfo", {})
        yesterday_prices = price_info.get("yesterday", [])
        today_prices = price_info.get("today", [])
        tomorrow_prices = price_info.get("tomorrow", [])

        all_prices = yesterday_prices + today_prices + tomorrow_prices
        if not all_prices:
            return None

        now = dt_util.now()

        # Find the current interval
        current_idx = None
        for idx, price_data in enumerate(all_prices):
            starts_at = dt_util.parse_datetime(price_data["startsAt"])
            if starts_at is None:
                continue
            starts_at = dt_util.as_local(starts_at)
            interval_end = starts_at + timedelta(minutes=15)

            if starts_at <= now < interval_end:
                current_idx = idx
                break

        if current_idx is None:
            return None

        # Shift by hour_offset * 4 intervals (4 intervals = 1 hour)
        center_idx = current_idx + (hour_offset * 4)

        # Collect differences from 2 intervals before to 2 intervals after (5 total)
        differences = []
        for offset in range(-2, 3):  # -2, -1, 0, 1, 2
            idx = center_idx + offset
            if 0 <= idx < len(all_prices):
                difference = all_prices[idx].get("difference")
                if difference is not None:
                    differences.append(float(difference))

        if not differences:
            return None

        # Get thresholds from config
        threshold_low = self.coordinator.config_entry.options.get(
            CONF_PRICE_RATING_THRESHOLD_LOW,
            DEFAULT_PRICE_RATING_THRESHOLD_LOW,
        )
        threshold_high = self.coordinator.config_entry.options.get(
            CONF_PRICE_RATING_THRESHOLD_HIGH,
            DEFAULT_PRICE_RATING_THRESHOLD_HIGH,
        )

        # Aggregate using average difference
        aggregated_rating, _avg_diff = aggregate_price_rating(differences, threshold_low, threshold_high)

        return self._translate_rating_level(aggregated_rating)

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

    # Add method to get future price intervals
    def _get_price_forecast_value(self) -> str | None:
        """Get the highest or lowest price status for the price forecast entity."""
        future_prices = self._get_future_prices(max_intervals=MAX_FORECAST_INTERVALS)
        if not future_prices:
            return "No forecast data available"

        # Return a simple status message indicating how much forecast data is available
        return f"Forecast available for {len(future_prices)} intervals"

    def _get_future_prices(self, max_intervals: int | None = None) -> list[dict] | None:
        """
        Get future price data for multiple upcoming intervals.

        Args:
            max_intervals: Maximum number of future intervals to return

        Returns:
            List of upcoming price intervals with timestamps and prices

        """
        if not self.coordinator.data:
            return None

        price_info = self.coordinator.data.get("priceInfo", {})

        today_prices = price_info.get("today", [])
        tomorrow_prices = price_info.get("tomorrow", [])
        all_prices = today_prices + tomorrow_prices

        if not all_prices:
            return None

        now = dt_util.now()

        # Initialize the result list
        future_prices = []

        # Track the maximum intervals to return
        intervals_to_return = MAX_FORECAST_INTERVALS if max_intervals is None else max_intervals

        for day_key in ["today", "tomorrow"]:
            for price_data in price_info.get(day_key, []):
                starts_at = dt_util.parse_datetime(price_data["startsAt"])
                if starts_at is None:
                    continue

                starts_at = dt_util.as_local(starts_at)
                interval_end = starts_at + timedelta(minutes=MINUTES_PER_INTERVAL)

                if starts_at > now:
                    future_prices.append(
                        {
                            "interval_start": starts_at.isoformat(),
                            "interval_end": interval_end.isoformat(),
                            "price": float(price_data["total"]),
                            "price_cents": round(float(price_data["total"]) * 100, 2),
                            "level": price_data.get("level", "NORMAL"),
                            "rating": price_data.get("difference", None),
                            "rating_level": price_data.get("rating_level"),
                            "day": day_key,
                        }
                    )

        # Sort by start time
        future_prices.sort(key=lambda x: x["interval_start"])

        # Limit to the requested number of intervals
        return future_prices[:intervals_to_return] if future_prices else None

    def _add_price_forecast_attributes(self, attributes: dict) -> None:
        """Add forecast attributes for the price forecast sensor."""
        future_prices = self._get_future_prices(max_intervals=MAX_FORECAST_INTERVALS)
        if not future_prices:
            attributes["intervals"] = []
            attributes["hours"] = []
            attributes["data_available"] = False
            return

        attributes["intervals"] = future_prices
        attributes["data_available"] = True

        # Group by hour for easier consumption in dashboards
        hours = {}
        for interval in future_prices:
            starts_at = datetime.fromisoformat(interval["interval_start"])
            hour_key = starts_at.strftime("%Y-%m-%d %H")

            if hour_key not in hours:
                hours[hour_key] = {
                    "hour": starts_at.hour,
                    "day": interval["day"],
                    "date": starts_at.date().isoformat(),
                    "intervals": [],
                    "min_price": None,
                    "max_price": None,
                    "avg_price": 0,
                    "avg_rating": None,  # Initialize rating tracking
                    "ratings_available": False,  # Track if any ratings are available
                }

            # Create interval data with both price and rating info
            interval_data = {
                "minute": starts_at.minute,
                "price": interval["price"],
                "price_cents": interval["price_cents"],
                "level": interval["level"],  # Price level from priceInfo
                "time": starts_at.strftime("%H:%M"),
            }

            # Add rating data if available
            if interval["rating"] is not None:
                interval_data["rating"] = interval["rating"]
                interval_data["rating_level"] = interval["rating_level"]
                hours[hour_key]["ratings_available"] = True

            hours[hour_key]["intervals"].append(interval_data)

            # Track min/max/avg for the hour
            price = interval["price"]
            if hours[hour_key]["min_price"] is None or price < hours[hour_key]["min_price"]:
                hours[hour_key]["min_price"] = price
            if hours[hour_key]["max_price"] is None or price > hours[hour_key]["max_price"]:
                hours[hour_key]["max_price"] = price

        # Calculate averages
        for hour_data in hours.values():
            prices = [interval["price"] for interval in hour_data["intervals"]]
            if prices:
                hour_data["avg_price"] = sum(prices) / len(prices)
                hour_data["avg_price_cents"] = hour_data["avg_price"] * 100
                hour_data["min_price_cents"] = hour_data["min_price"] * 100
                hour_data["max_price_cents"] = hour_data["max_price"] * 100

                # Calculate average rating if ratings are available
                if hour_data["ratings_available"]:
                    ratings = [interval.get("rating") for interval in hour_data["intervals"] if "rating" in interval]
                    if ratings:
                        hour_data["avg_rating"] = sum(ratings) / len(ratings)

        # Convert to list sorted by hour
        attributes["hours"] = [hour_data for _, hour_data in sorted(hours.items())]

    @property
    def native_value(self) -> float | str | datetime | None:
        """Return the native value of the sensor."""
        try:
            if not self.coordinator.data or not self._value_getter:
                return None
            # For price_level, ensure we return the translated value as state
            if self.entity_description.key == "price_level":
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
    async def async_extra_state_attributes(self) -> dict | None:
        """Return additional state attributes asynchronously."""
        if not self.coordinator.data:
            return None

        attributes = self._get_sensor_attributes() or {}

        # Add description from the custom translations file
        if self.entity_description.translation_key and self.hass is not None:
            # Extract the base key (without _cents suffix if present)
            base_key = self.entity_description.translation_key
            base_key = base_key.removesuffix("_cents")

            # Get user's language preference
            language = self.hass.config.language if self.hass.config.language else "en"

            # Add basic description
            description = await async_get_entity_description(self.hass, "sensor", base_key, language, "description")
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
                    self.hass, "sensor", base_key, language, "long_description"
                )
                if long_desc:
                    attributes["long_description"] = long_desc

                # Add usage tips if available
                usage_tips = await async_get_entity_description(self.hass, "sensor", base_key, language, "usage_tips")
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
            # Extract the base key (without _cents suffix if present)
            base_key = self.entity_description.translation_key
            base_key = base_key.removesuffix("_cents")

            # Get user's language preference
            language = self.hass.config.language if self.hass.config.language else "en"

            # Add basic description from cache
            description = get_entity_description("sensor", base_key, language, "description")
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
                long_desc = get_entity_description("sensor", base_key, language, "long_description")
                if long_desc:
                    attributes["long_description"] = long_desc

                # Add usage tips if available in cache
                usage_tips = get_entity_description("sensor", base_key, language, "usage_tips")
                if usage_tips:
                    attributes["usage_tips"] = usage_tips

        return attributes if attributes else None

    def _get_sensor_attributes(self) -> dict | None:
        """Get attributes based on sensor type."""
        try:
            if not self.coordinator.data:
                return None

            key = self.entity_description.key
            attributes = {}

            # Group sensors by type and delegate to specific handlers
            if key in [
                "current_price",
                "price_level",
                "next_interval_price",
                "previous_interval_price",
                "current_hour_average",
                "next_hour_average",
                "next_interval_price_level",
                "previous_interval_price_level",
                "current_hour_price_level",
                "next_hour_price_level",
                "next_interval_price_rating",
                "previous_interval_price_rating",
                "current_hour_price_rating",
                "next_hour_price_rating",
            ]:
                self._add_current_price_attributes(attributes)
            elif key in [
                "trailing_price_average",
                "leading_price_average",
                "trailing_price_min",
                "trailing_price_max",
                "leading_price_min",
                "leading_price_max",
            ]:
                self._add_average_price_attributes(attributes)
            elif any(pattern in key for pattern in ["_price_today", "_price_tomorrow", "rating", "data_timestamp"]):
                self._add_statistics_attributes(attributes)
            elif key == "price_forecast":
                self._add_price_forecast_attributes(attributes)
            # For price_level, add the original level as attribute
            if key == "price_level" and hasattr(self, "_last_price_level") and self._last_price_level is not None:
                attributes["level_id"] = self._last_price_level
        except (KeyError, ValueError, TypeError) as ex:
            self.coordinator.logger.exception(
                "Error getting sensor attributes",
                extra={
                    "error": str(ex),
                    "entity": self.entity_description.key,
                },
            )
        else:
            return attributes if attributes else None

    def _add_current_price_attributes(self, attributes: dict) -> None:
        """Add attributes for current price sensors."""
        key = self.entity_description.key
        price_info = self.coordinator.data.get("priceInfo", {}) if self.coordinator.data else {}
        now = dt_util.now()

        # Determine which interval to use based on sensor type
        next_interval_sensors = [
            "next_interval_price",
            "next_interval_price_level",
            "next_interval_price_rating",
        ]
        previous_interval_sensors = [
            "previous_interval_price",
            "previous_interval_price_level",
            "previous_interval_price_rating",
        ]
        next_hour_sensors = [
            "next_hour_average",
            "next_hour_price_level",
            "next_hour_price_rating",
        ]
        current_hour_sensors = [
            "current_hour_average",
            "current_hour_price_level",
            "current_hour_price_rating",
        ]

        if key in next_interval_sensors:
            target_time = now + timedelta(minutes=MINUTES_PER_INTERVAL)
            interval_data = find_price_data_for_interval(price_info, target_time)
            attributes["timestamp"] = interval_data["startsAt"] if interval_data else None
        elif key in previous_interval_sensors:
            target_time = now - timedelta(minutes=MINUTES_PER_INTERVAL)
            interval_data = find_price_data_for_interval(price_info, target_time)
            attributes["timestamp"] = interval_data["startsAt"] if interval_data else None
        elif key in next_hour_sensors:
            # For next hour sensors, show timestamp 1 hour ahead
            target_time = now + timedelta(hours=1)
            interval_data = find_price_data_for_interval(price_info, target_time)
            attributes["timestamp"] = interval_data["startsAt"] if interval_data else None
        elif key in current_hour_sensors:
            # For current hour sensors, use current interval timestamp
            current_interval_data = self._get_current_interval_data()
            attributes["timestamp"] = current_interval_data["startsAt"] if current_interval_data else None
        else:
            # Default: use current interval timestamp
            current_interval_data = self._get_current_interval_data()
            attributes["timestamp"] = current_interval_data["startsAt"] if current_interval_data else None

        # Add price level info for price level sensors
        if key == "price_level":
            current_interval_data = self._get_current_interval_data()
            if current_interval_data and "level" in current_interval_data:
                self._add_price_level_attributes(attributes, current_interval_data["level"])

    def _add_price_level_attributes(self, attributes: dict, level: str) -> None:
        """
        Add price level specific attributes.

        Args:
            attributes: Dictionary to add attributes to
            level: The price level value (e.g., VERY_CHEAP, NORMAL, etc.)

        """
        if level in PRICE_LEVEL_MAPPING:
            attributes["level_value"] = PRICE_LEVEL_MAPPING[level]
        attributes["level_id"] = level

    def _find_price_timestamp(
        self,
        attributes: dict,
        price_info: Any,
        day_key: str,
        target_hour: int,
        target_date: date,
    ) -> None:
        """Find a price timestamp for a specific hour and date."""
        for price_data in price_info.get(day_key, []):
            starts_at = dt_util.parse_datetime(price_data["startsAt"])
            if starts_at is None:
                continue

            starts_at = dt_util.as_local(starts_at)
            if starts_at.hour == target_hour and starts_at.date() == target_date:
                attributes["timestamp"] = price_data["startsAt"]
                break

    def _add_statistics_attributes(self, attributes: dict) -> None:
        """Add attributes for statistics and rating sensors."""
        key = self.entity_description.key
        price_info = self.coordinator.data.get("priceInfo", {})
        now = dt_util.now()

        if key == "price_rating":
            interval_data = find_price_data_for_interval(price_info, now)
            attributes["timestamp"] = interval_data["startsAt"] if interval_data else None
            if hasattr(self, "_last_rating_difference") and self._last_rating_difference is not None:
                attributes["difference_" + PERCENTAGE] = self._last_rating_difference
            if hasattr(self, "_last_rating_level") and self._last_rating_level is not None:
                attributes["level_id"] = self._last_rating_level
                attributes["level_value"] = PRICE_RATING_MAPPING.get(self._last_rating_level, self._last_rating_level)
        elif key in [
            "lowest_price_today",
            "highest_price_today",
            "lowest_price_tomorrow",
            "highest_price_tomorrow",
        ]:
            # Use the timestamp from the interval that has the extreme price (already stored during value calculation)
            if hasattr(self, "_last_extreme_interval") and self._last_extreme_interval:
                attributes["timestamp"] = self._last_extreme_interval.get("startsAt")
            else:
                # Fallback: use the first timestamp of the appropriate day
                day_key = "tomorrow" if "tomorrow" in key else "today"
                attributes["timestamp"] = price_info.get(day_key, [{}])[0].get("startsAt")
        else:
            # Fallback: use the first timestamp of the appropriate day
            day_key = "tomorrow" if "tomorrow" in key else "today"
            first_timestamp = price_info.get(day_key, [{}])[0].get("startsAt")
            attributes["timestamp"] = first_timestamp

    def _add_average_price_attributes(self, attributes: dict) -> None:
        """Add attributes for trailing and leading average price sensors."""
        key = self.entity_description.key
        now = dt_util.now()

        # Determine if this is trailing or leading
        is_trailing = "trailing" in key

        # Get all price intervals
        price_info = self.coordinator.data.get("priceInfo", {})
        yesterday_prices = price_info.get("yesterday", [])
        today_prices = price_info.get("today", [])
        tomorrow_prices = price_info.get("tomorrow", [])
        all_prices = yesterday_prices + today_prices + tomorrow_prices

        if not all_prices:
            return

        # Calculate the time window
        if is_trailing:
            window_start = now - timedelta(hours=24)
            window_end = now
        else:
            window_start = now
            window_end = now + timedelta(hours=24)

        # Find all intervals in the window and get first/last timestamps
        intervals_in_window = []
        for price_data in all_prices:
            starts_at = dt_util.parse_datetime(price_data["startsAt"])
            if starts_at is None:
                continue
            starts_at = dt_util.as_local(starts_at)
            if window_start <= starts_at < window_end:
                intervals_in_window.append(price_data)

        # Add timestamp attribute (first interval in the window)
        if intervals_in_window:
            attributes["timestamp"] = intervals_in_window[0].get("startsAt")
            attributes["interval_count"] = len(intervals_in_window)

    async def async_update(self) -> None:
        """Force a refresh when homeassistant.update_entity is called."""
        await self.coordinator.async_request_refresh()
