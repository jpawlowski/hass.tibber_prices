"""Sensor platform for tibber_prices."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CURRENCY_EURO, PERCENTAGE, EntityCategory, UnitOfPower, UnitOfTime
from homeassistant.util import dt as dt_util

from .const import (
    CONF_EXTENDED_DESCRIPTIONS,
    DEFAULT_EXTENDED_DESCRIPTIONS,
    DOMAIN,
    PRICE_LEVEL_MAPPING,
    PRICE_RATING_MAPPING,
    async_get_entity_description,
    get_entity_description,
    get_price_level_translation,
)
from .entity import TibberPricesEntity
from .price_utils import find_price_data_for_interval

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
MINUTES_PER_INTERVAL = 15
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
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="current_price_eur",
        translation_key="current_price",
        name="Current Electricity Price",
        icon="mdi:currency-eur",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=PRICE_UNIT,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="next_interval_price",
        translation_key="next_interval_price_cents",
        name="Next Interval Electricity Price",
        icon="mdi:currency-eur-off",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=PRICE_UNIT_MINOR,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="next_interval_price_eur",
        translation_key="next_interval_price",
        name="Next Interval Electricity Price",
        icon="mdi:currency-eur-off",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=PRICE_UNIT,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="price_level",
        translation_key="price_level",
        name="Current Price Level",
        icon="mdi:meter-electric",
    ),
)

# Statistical price sensors
STATISTICS_SENSORS = (
    SensorEntityDescription(
        key="lowest_price_today",
        translation_key="lowest_price_today_cents",
        name="Today's Lowest Price",
        icon="mdi:currency-eur",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=PRICE_UNIT_MINOR,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="lowest_price_today_eur",
        translation_key="lowest_price_today",
        name="Today's Lowest Price",
        icon="mdi:currency-eur",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=PRICE_UNIT,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="highest_price_today",
        translation_key="highest_price_today_cents",
        name="Today's Highest Price",
        icon="mdi:currency-eur",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=PRICE_UNIT_MINOR,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="highest_price_today_eur",
        translation_key="highest_price_today",
        name="Today's Highest Price",
        icon="mdi:currency-eur",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=PRICE_UNIT,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="average_price_today",
        translation_key="average_price_today_cents",
        name="Today's Average Price",
        icon="mdi:currency-eur",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=PRICE_UNIT_MINOR,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="average_price_today_eur",
        translation_key="average_price_today",
        name="Today's Average Price",
        icon="mdi:currency-eur",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=PRICE_UNIT,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
    ),
)

# Rating sensors
RATING_SENSORS = (
    SensorEntityDescription(
        key="price_rating",
        translation_key="price_rating",
        name="Current Price Rating",
        icon="mdi:clock-outline",
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
            # Price level
            "price_level": self._get_price_level_value,
            # Price sensors
            "current_price": lambda: self._get_interval_price_value(interval_offset=0, in_euro=False),
            "current_price_eur": lambda: self._get_interval_price_value(interval_offset=0, in_euro=True),
            "next_interval_price": lambda: self._get_interval_price_value(interval_offset=1, in_euro=False),
            "next_interval_price_eur": lambda: self._get_interval_price_value(interval_offset=1, in_euro=True),
            # Statistics sensors
            "lowest_price_today": lambda: self._get_statistics_value(stat_func=min, in_euro=False, decimals=2),
            "lowest_price_today_eur": lambda: self._get_statistics_value(stat_func=min, in_euro=True, decimals=4),
            "highest_price_today": lambda: self._get_statistics_value(stat_func=max, in_euro=False, decimals=2),
            "highest_price_today_eur": lambda: self._get_statistics_value(stat_func=max, in_euro=True, decimals=4),
            "average_price_today": lambda: self._get_statistics_value(
                stat_func=lambda prices: sum(prices) / len(prices), in_euro=False, decimals=2
            ),
            "average_price_today_eur": lambda: self._get_statistics_value(
                stat_func=lambda prices: sum(prices) / len(prices), in_euro=True, decimals=4
            ),
            # Rating sensors
            "price_rating": lambda: self._get_rating_value(rating_type="current"),
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
        self, *, stat_func: Callable[[list[float]], float], in_euro: bool, decimals: int | None = None
    ) -> float | None:
        """
        Handle statistics sensor values using the provided statistical function.

        Returns:
            The calculated value for the statistics sensor, or None if unavailable.

        """
        if not self.coordinator.data:
            return None

        price_info = self.coordinator.data.get("priceInfo", {})

        # Get local midnight boundaries
        local_midnight = dt_util.as_local(dt_util.start_of_local_day(dt_util.now()))
        local_midnight_tomorrow = local_midnight + timedelta(days=1)

        # Collect all prices and their intervals from both today and tomorrow data that fall within local today
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

                # Include price if it starts within today's local date boundaries
                if local_midnight <= starts_at < local_midnight_tomorrow:
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
                "current_price_eur",
                "price_level",
                "next_interval_price",
                "next_interval_price_eur",
            ]:
                self._add_current_price_attributes(attributes)
            elif any(pattern in key for pattern in ["_price_today", "rating", "data_timestamp"]):
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
        current_interval_data = self._get_current_interval_data()
        attributes["timestamp"] = current_interval_data["startsAt"] if current_interval_data else None

        # Add price level info for the price level sensor
        if self.entity_description.key == "price_level" and current_interval_data and "level" in current_interval_data:
            self._add_price_level_attributes(attributes, current_interval_data["level"])

        if self.entity_description.key in ["next_interval_price", "next_interval_price_eur"]:
            price_info = self.coordinator.data.get("priceInfo", {})
            now = dt_util.now()
            next_interval_time = now + timedelta(minutes=MINUTES_PER_INTERVAL)
            next_interval_data = find_price_data_for_interval(price_info, next_interval_time)
            attributes["timestamp"] = next_interval_data["startsAt"] if next_interval_data else None

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
        self, attributes: dict, price_info: Any, day_key: str, target_hour: int, target_date: date
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
        elif key in ["lowest_price_today", "lowest_price_today_eur", "highest_price_today", "highest_price_today_eur"]:
            # Use the timestamp from the interval that has the extreme price (already stored during value calculation)
            if hasattr(self, "_last_extreme_interval") and self._last_extreme_interval:
                attributes["timestamp"] = self._last_extreme_interval.get("startsAt")
            else:
                # Fallback: use the first timestamp of today
                attributes["timestamp"] = price_info.get("today", [{}])[0].get("startsAt")
        else:
            # Fallback: use the first timestamp of today
            first_timestamp = price_info.get("today", [{}])[0].get("startsAt")
            attributes["timestamp"] = first_timestamp

    async def async_update(self) -> None:
        """Force a refresh when homeassistant.update_entity is called."""
        await self.coordinator.async_request_refresh()
