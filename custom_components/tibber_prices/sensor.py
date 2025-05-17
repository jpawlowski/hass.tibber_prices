"""Sensor platform for tibber_prices."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

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
)
from .entity import TibberPricesEntity

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import TibberPricesDataUpdateCoordinator
    from .data import TibberPricesConfigEntry

PRICE_UNIT_CENT = "ct/" + UnitOfPower.KILO_WATT + UnitOfTime.HOURS
PRICE_UNIT_EURO = CURRENCY_EURO + "/" + UnitOfPower.KILO_WATT + UnitOfTime.HOURS
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
        native_unit_of_measurement=PRICE_UNIT_CENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="current_price_eur",
        translation_key="current_price",
        name="Current Electricity Price",
        icon="mdi:currency-eur",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=PRICE_UNIT_EURO,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="next_interval_price",
        translation_key="next_interval_price_cents",
        name="Next Interval Electricity Price",
        icon="mdi:currency-eur-off",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=PRICE_UNIT_CENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="next_interval_price_eur",
        translation_key="next_interval_price",
        name="Next Interval Electricity Price",
        icon="mdi:currency-eur-off",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=PRICE_UNIT_EURO,
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
        native_unit_of_measurement=PRICE_UNIT_CENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="lowest_price_today_eur",
        translation_key="lowest_price_today",
        name="Today's Lowest Price",
        icon="mdi:currency-eur",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=PRICE_UNIT_EURO,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="highest_price_today",
        translation_key="highest_price_today_cents",
        name="Today's Highest Price",
        icon="mdi:currency-eur",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=PRICE_UNIT_CENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="highest_price_today_eur",
        translation_key="highest_price_today",
        name="Today's Highest Price",
        icon="mdi:currency-eur",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=PRICE_UNIT_EURO,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="average_price_today",
        translation_key="average_price_today_cents",
        name="Today's Average Price",
        icon="mdi:currency-eur",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=PRICE_UNIT_CENT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="average_price_today_eur",
        translation_key="average_price_today",
        name="Today's Average Price",
        icon="mdi:currency-eur",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=PRICE_UNIT_EURO,
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
    SensorEntityDescription(
        key="daily_rating",
        translation_key="daily_rating",
        name="Daily Price Rating",
        icon="mdi:calendar-today",
    ),
    SensorEntityDescription(
        key="monthly_rating",
        translation_key="monthly_rating",
        name="Monthly Price Rating",
        icon="mdi:calendar-month",
    ),
)

# Diagnostic sensors for data availability
DIAGNOSTIC_SENSORS = (
    SensorEntityDescription(
        key="data_timestamp",
        translation_key="data_timestamp",
        name="Latest Data Available",
        icon="mdi:clock-check",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="tomorrow_data_available",
        translation_key="tomorrow_data_available",
        name="Tomorrow's Data Status",
        icon="mdi:calendar-check",
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
            "price_rating": lambda: self._get_rating_value(rating_type="hourly"),
            "daily_rating": lambda: self._get_rating_value(rating_type="daily"),
            "monthly_rating": lambda: self._get_rating_value(rating_type="monthly"),
            # Diagnostic sensors
            "data_timestamp": self._get_data_timestamp,
            "tomorrow_data_available": self._get_tomorrow_data_status,
            # Price forecast sensor
            "price_forecast": self._get_price_forecast_value,
        }

        return handlers.get(key)

    def _get_current_interval_data(self) -> dict | None:
        """Get the price data for the current interval using adaptive interval detection."""
        if not self.coordinator.data:
            return None

        # Get the current time and price info
        now = dt_util.now()
        price_info = self.coordinator.data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]

        # Use our adaptive price data finder
        return find_price_data_for_interval(price_info, now)

    def _get_price_level_value(self) -> str | None:
        """
        Get the current price level value as a translated string for the state.

        The original (raw) value is stored for use as an attribute.

        Returns:
            The translated price level value for the state, or None if unavailable.

        """
        current_interval_data = self._get_current_interval_data()
        if not current_interval_data or "level" not in current_interval_data:
            self._last_price_level = None
            return None
        level = current_interval_data["level"]
        self._last_price_level = level
        # Use the translation helper for price level, fallback to English if needed
        if self.hass:
            language = self.hass.config.language or "en"
            from .const import get_price_level_translation

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

        price_info = self.coordinator.data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]

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
        """
        Get price for the current interval or with offset, handling different interval granularities.

        Args:
            interval_offset: Number of intervals to offset from current time
            in_euro: Whether to return value in EUR (True) or cents/kWh (False)

        Returns:
            Price value in the requested unit or None if not available

        """
        if not self.coordinator.data:
            return None

        price_info = self.coordinator.data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]

        # Determine data granularity
        today_prices = price_info.get("today", [])
        data_granularity = detect_interval_granularity(today_prices) if today_prices else MINUTES_PER_INTERVAL

        # Use HomeAssistant's dt_util to get the current time in the user's timezone
        now = dt_util.now()

        # Calculate the target time based on detected granularity
        target_datetime = now + timedelta(minutes=interval_offset * data_granularity)

        # Find appropriate price data
        price_data = find_price_data_for_interval(price_info, target_datetime, data_granularity)

        if price_data:
            return self._get_price_value(float(price_data["total"]), in_euro=in_euro)

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

        price_info = self.coordinator.data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]
        today_prices = price_info.get("today", [])
        if not today_prices:
            return None

        prices = [float(price["total"]) for price in today_prices]
        if not prices:
            return None

        value = stat_func(prices)
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
                and "price_rating" in en_translations["sensor"]
                and "price_levels" in en_translations["sensor"]["price_rating"]
                and level in en_translations["sensor"]["price_rating"]["price_levels"]
            ):
                return en_translations["sensor"]["price_rating"]["price_levels"][level]
        return level

    def _find_rating_entry(
        self, entries: list[dict], now: datetime, rating_type: str, subscription: dict
    ) -> dict | None:
        """Find the correct rating entry for the given type and time."""
        if not entries:
            return None
        predicate = None
        if rating_type == "hourly":
            price_info = subscription.get("priceInfo", {})
            today_prices = price_info.get("today", [])
            data_granularity = detect_interval_granularity(today_prices) if today_prices else MINUTES_PER_INTERVAL

            def interval_predicate(entry_time: datetime) -> bool:
                interval_end = entry_time + timedelta(minutes=data_granularity)
                return entry_time <= now < interval_end and entry_time.date() == now.date()

            predicate = interval_predicate
        elif rating_type == "daily":

            def daily_predicate(entry_time: datetime) -> bool:
                return dt_util.as_local(entry_time).date() == now.date()

            predicate = daily_predicate
        elif rating_type == "monthly":

            def monthly_predicate(entry_time: datetime) -> bool:
                local_time = dt_util.as_local(entry_time)
                return local_time.month == now.month and local_time.year == now.year

            predicate = monthly_predicate
        if predicate:
            for entry in entries:
                entry_time = dt_util.parse_datetime(entry["time"])
                if entry_time and predicate(entry_time):
                    return entry
            # For hourly, fallback to hour match if not found
            if rating_type == "hourly":
                for entry in entries:
                    entry_time = dt_util.parse_datetime(entry["time"])
                    if entry_time:
                        entry_time = dt_util.as_local(entry_time)
                        if entry_time.hour == now.hour and entry_time.date() == now.date():
                            return entry
        return None

    def _get_rating_value(self, *, rating_type: str) -> str | None:
        """
        Handle rating sensor values for hourly, daily, and monthly ratings.

        Returns the translated rating level as the main status, and stores the original
        level and percentage difference as attributes.
        """
        if not self.coordinator.data:
            self._last_rating_difference = None
            self._last_rating_level = None
            return None
        subscription = self.coordinator.data["data"]["viewer"]["homes"][0]["currentSubscription"]
        price_rating = subscription.get("priceRating", {}) or {}
        now = dt_util.now()
        rating_data = price_rating.get(rating_type, {})
        entries = rating_data.get("entries", []) if rating_data else []
        entry = self._find_rating_entry(entries, now, rating_type, dict(subscription))
        if entry:
            difference = entry.get("difference")
            level = entry.get("level")
            self._last_rating_difference = float(difference) if difference is not None else None
            self._last_rating_level = level if level is not None else None
            return self._translate_rating_level(level or "")
        self._last_rating_difference = None
        self._last_rating_level = None
        return None

    def _get_data_timestamp(self) -> datetime | None:
        """Get the latest data timestamp."""
        if not self.coordinator.data:
            return None

        price_info = self.coordinator.data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]
        latest_timestamp = None

        for day in ["today", "tomorrow"]:
            for price_data in price_info.get(day, []):
                timestamp = datetime.fromisoformat(price_data["startsAt"])
                if not latest_timestamp or timestamp > latest_timestamp:
                    latest_timestamp = timestamp

        return dt_util.as_utc(latest_timestamp) if latest_timestamp else None

    def _get_tomorrow_data_status(self) -> str | None:
        """Get tomorrow's data availability status."""
        if not self.coordinator.data:
            return None

        price_info = self.coordinator.data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]
        tomorrow_prices = price_info.get("tomorrow", [])

        if not tomorrow_prices:
            return "No"
        return "Yes" if len(tomorrow_prices) == HOURS_IN_DAY else "Partial"

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

        price_info = self.coordinator.data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]
        price_rating = (
            self.coordinator.data["data"]["viewer"]["homes"][0]["currentSubscription"].get("priceRating", {}) or {}
        )

        # Determine data granularity from the current price data
        today_prices = price_info.get("today", [])
        tomorrow_prices = price_info.get("tomorrow", [])
        all_prices = today_prices + tomorrow_prices

        if not all_prices:
            return None

        data_granularity = detect_interval_granularity(all_prices)
        now = dt_util.now()

        # Initialize the result list
        future_prices = []

        # Track the maximum intervals to return
        intervals_to_return = MAX_FORECAST_INTERVALS if max_intervals is None else max_intervals

        # Extract hourly rating data for enriching the forecast
        rating_data = {}
        hourly_rating = price_rating.get("hourly", {})
        if hourly_rating and "entries" in hourly_rating:
            for entry in hourly_rating.get("entries", []):
                if entry.get("time"):
                    timestamp = dt_util.parse_datetime(entry["time"])
                    if timestamp:
                        timestamp = dt_util.as_local(timestamp)
                        # Store with ISO format key for easier lookup
                        time_key = timestamp.replace(second=0, microsecond=0).isoformat()
                        rating_data[time_key] = {
                            "difference": float(entry.get("difference", 0)),
                            "rating_level": entry.get("level"),
                        }

        # Create a list of all future price data points
        for day_key in ["today", "tomorrow"]:
            for price_data in price_info.get(day_key, []):
                starts_at = dt_util.parse_datetime(price_data["startsAt"])
                if starts_at is None:
                    continue

                starts_at = dt_util.as_local(starts_at)
                interval_end = starts_at + timedelta(minutes=data_granularity)

                # Only include future intervals
                if starts_at > now:
                    # Format timestamp for rating lookup
                    starts_at_key = starts_at.replace(second=0, microsecond=0).isoformat()

                    # Try to find rating data for this interval
                    interval_rating = rating_data.get(starts_at_key) or {}

                    future_prices.append(
                        {
                            "interval_start": starts_at.isoformat(),  # Renamed from starts_at to interval_start
                            "interval_end": interval_end.isoformat(),
                            "price": float(price_data["total"]),
                            "price_cents": round(float(price_data["total"]) * 100, 2),
                            "level": price_data.get("level", "NORMAL"),  # Price level from priceInfo
                            "rating": interval_rating.get("difference", None),  # Rating from priceRating
                            "rating_level": interval_rating.get("rating_level"),  # Level from priceRating
                            "day": day_key,
                        }
                    )

        # Sort by start time
        future_prices.sort(key=lambda x: x["interval_start"])  # Updated sort key

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

        # Determine interval granularity for display purposes
        min_intervals_for_granularity_detection = 2
        if len(future_prices) >= min_intervals_for_granularity_detection:
            start1 = datetime.fromisoformat(future_prices[0]["interval_start"])
            start2 = datetime.fromisoformat(future_prices[1]["interval_start"])
            minutes_diff = int((start2 - start1).total_seconds() / 60)
            attributes["interval_minutes"] = minutes_diff
        else:
            attributes["interval_minutes"] = MINUTES_PER_INTERVAL

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
            if key in ["current_price", "current_price_eur", "price_level"]:
                self._add_current_price_attributes(attributes)
            elif any(
                pattern in key for pattern in ["_price_today", "rating", "data_timestamp", "tomorrow_data_available"]
            ):
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

        # Add timestamp for next interval price sensors
        if self.entity_description.key in ["next_interval_price", "next_interval_price_eur"]:
            # Get the next interval's data
            price_info = self.coordinator.data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]
            today_prices = price_info.get("today", [])
            data_granularity = detect_interval_granularity(today_prices) if today_prices else MINUTES_PER_INTERVAL
            now = dt_util.now()
            next_interval_time = now + timedelta(minutes=data_granularity)
            next_interval_data = find_price_data_for_interval(price_info, next_interval_time, data_granularity)
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
        """Add attributes for statistics, rating, and diagnostic sensors."""
        key = self.entity_description.key
        price_info = self.coordinator.data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]
        now = dt_util.now()
        if key == "price_rating":
            today_prices = price_info.get("today", [])
            data_granularity = detect_interval_granularity(today_prices) if today_prices else MINUTES_PER_INTERVAL
            interval_data = find_price_data_for_interval(price_info, now, data_granularity)
            attributes["timestamp"] = interval_data["startsAt"] if interval_data else None
            if hasattr(self, "_last_rating_difference") and self._last_rating_difference is not None:
                attributes["difference_" + PERCENTAGE] = self._last_rating_difference
            if hasattr(self, "_last_rating_level") and self._last_rating_level is not None:
                attributes["level_id"] = self._last_rating_level
                attributes["level_value"] = PRICE_RATING_MAPPING.get(self._last_rating_level, self._last_rating_level)
        elif key == "daily_rating":
            attributes["timestamp"] = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            if hasattr(self, "_last_rating_difference") and self._last_rating_difference is not None:
                attributes["difference_" + PERCENTAGE] = self._last_rating_difference
            if hasattr(self, "_last_rating_level") and self._last_rating_level is not None:
                attributes["level_id"] = self._last_rating_level
                attributes["level_value"] = PRICE_RATING_MAPPING.get(self._last_rating_level, self._last_rating_level)
        elif key == "monthly_rating":
            first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            attributes["timestamp"] = first_of_month.isoformat()
            if hasattr(self, "_last_rating_difference") and self._last_rating_difference is not None:
                attributes["difference_" + PERCENTAGE] = self._last_rating_difference
            if hasattr(self, "_last_rating_level") and self._last_rating_level is not None:
                attributes["level_id"] = self._last_rating_level
                attributes["level_value"] = PRICE_RATING_MAPPING.get(self._last_rating_level, self._last_rating_level)
        else:
            # Fallback: use the first timestamp of today
            first_timestamp = price_info.get("today", [{}])[0].get("startsAt")
            attributes["timestamp"] = first_timestamp


def detect_interval_granularity(price_data: list[dict]) -> int:
    """
    Detect the granularity of price intervals in minutes.

    Args:
        price_data: List of price data points with startsAt timestamps

    Returns:
        Minutes per interval (e.g., 60 for hourly, 15 for 15-minute intervals)

    """
    min_datapoints_for_granularity = 2
    if not price_data or len(price_data) < min_datapoints_for_granularity:
        return MINUTES_PER_INTERVAL  # Default to target value

    # Sort data points by timestamp
    sorted_data = sorted(price_data, key=lambda x: x["startsAt"])

    # Calculate the time differences between consecutive timestamps
    intervals = []
    for i in range(1, min(10, len(sorted_data))):  # Sample up to 10 intervals
        start_time_1 = dt_util.parse_datetime(sorted_data[i - 1]["startsAt"])
        start_time_2 = dt_util.parse_datetime(sorted_data[i]["startsAt"])

        if start_time_1 and start_time_2:
            diff_minutes = (start_time_2 - start_time_1).total_seconds() / 60
            intervals.append(round(diff_minutes))

    # If no valid intervals found, return default
    if not intervals:
        return MINUTES_PER_INTERVAL

    # Return the most common interval (mode)
    return max(set(intervals), key=intervals.count)


def get_interval_for_timestamp(timestamp: datetime, granularity: int) -> int:
    """
    Calculate the interval index within an hour for a given timestamp.

    Args:
        timestamp: The timestamp to calculate interval for
        granularity: Minutes per interval

    Returns:
        Interval index (0-based) within the hour

    """
    # Calculate which interval this timestamp falls into
    intervals_per_hour = 60 // granularity
    return (timestamp.minute // granularity) % intervals_per_hour


def _match_hourly_price_data(day_prices: list, target_time: datetime) -> dict | None:
    """Match price data for hourly granularity."""
    for price_data in day_prices:
        starts_at = dt_util.parse_datetime(price_data["startsAt"])
        if starts_at is None:
            continue

        starts_at = dt_util.as_local(starts_at)
        if starts_at.hour == target_time.hour and starts_at.date() == target_time.date():
            return price_data
    return None


def _match_granular_price_data(day_prices: list, target_time: datetime, data_granularity: int) -> dict | None:
    """Match price data for sub-hourly granularity."""
    for price_data in day_prices:
        starts_at = dt_util.parse_datetime(price_data["startsAt"])
        if starts_at is None:
            continue

        starts_at = dt_util.as_local(starts_at)
        interval_end = starts_at + timedelta(minutes=data_granularity)
        # Check if target time falls within this interval
        if starts_at <= target_time < interval_end and starts_at.date() == target_time.date():
            return price_data
    return None


def find_price_data_for_interval(
    price_info: Any, target_time: datetime, data_granularity: int | None = None
) -> dict | None:
    """
    Find the price data for a specific timestamp, handling different interval granularities.

    Args:
        price_info: The price info dictionary from Tibber API
        target_time: The target timestamp to find price data for
        data_granularity: Override detected granularity with this value (minutes)

    Returns:
        Price data dict if found, None otherwise

    """
    # Determine which day's data to search
    day_key = "tomorrow" if target_time.date() > dt_util.now().date() else "today"
    search_days = [day_key, "tomorrow" if day_key == "today" else "today"]

    # Try to find price data in today or tomorrow
    for search_day in search_days:
        day_prices = price_info.get(search_day, [])
        if not day_prices:
            continue

        # Detect the granularity if not provided
        if data_granularity is None:
            data_granularity = detect_interval_granularity(day_prices)

        # Check for a match with appropriate granularity
        if data_granularity >= MINUTES_PER_INTERVAL * 4:  # 60 minutes = hourly
            result = _match_hourly_price_data(day_prices, target_time)
        else:
            result = _match_granular_price_data(day_prices, target_time, data_granularity)

        if result:
            return result

    # If not found and we have sub-hourly granularity, try to fall back to hourly data
    if data_granularity is not None and data_granularity < MINUTES_PER_INTERVAL * 4:
        hour_start = target_time.replace(minute=0, second=0, microsecond=0)

        for search_day in search_days:
            day_prices = price_info.get(search_day, [])
            result = _match_hourly_price_data(day_prices, hour_start)
            if result:
                return result

    return None
