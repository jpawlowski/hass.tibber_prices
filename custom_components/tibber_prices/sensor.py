"""Sensor platform for tibber_prices."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CURRENCY_EURO, EntityCategory
from homeassistant.util import dt as dt_util

from .entity import TibberPricesEntity

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import TibberPricesDataUpdateCoordinator
    from .data import TibberPricesConfigEntry

PRICE_UNIT = "ct/kWh"
HOURS_IN_DAY = 24

# Main price sensors that users will typically use in automations
PRICE_SENSORS = (
    SensorEntityDescription(
        key="current_price_eur",
        translation_key="current_price",
        name="Current Electricity Price",
        icon="mdi:currency-eur",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_EURO,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="current_price",
        translation_key="current_price_cents",
        name="Current Electricity Price",
        icon="mdi:currency-eur",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="ct/kWh",
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="next_hour_price_eur",
        translation_key="next_hour_price",
        name="Next Hour Electricity Price",
        icon="mdi:currency-eur-off",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_EURO,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="next_hour_price",
        translation_key="next_hour_price_cents",
        name="Next Hour Electricity Price",
        icon="mdi:currency-eur-off",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="ct/kWh",
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
        key="lowest_price_today_eur",
        translation_key="lowest_price_today",
        name="Today's Lowest Price",
        icon="mdi:currency-eur",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_EURO,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="lowest_price_today",
        translation_key="lowest_price_today_cents",
        name="Today's Lowest Price",
        icon="mdi:currency-eur",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="ct/kWh",
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="highest_price_today_eur",
        translation_key="highest_price_today",
        name="Today's Highest Price",
        icon="mdi:currency-eur",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_EURO,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="highest_price_today",
        translation_key="highest_price_today_cents",
        name="Today's Highest Price",
        icon="mdi:currency-eur",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="ct/kWh",
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="average_price_today_eur",
        translation_key="average_price_today",
        name="Today's Average Price",
        icon="mdi:currency-eur",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_EURO,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="average_price_today",
        translation_key="average_price_today_cents",
        name="Today's Average Price",
        icon="mdi:currency-eur",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="ct/kWh",
        suggested_display_precision=2,
    ),
)

# Rating sensors
RATING_SENSORS = (
    SensorEntityDescription(
        key="hourly_rating",
        translation_key="hourly_rating",
        name="Hourly Price Rating",
        icon="mdi:clock-outline",
        native_unit_of_measurement="%",
    ),
    SensorEntityDescription(
        key="daily_rating",
        translation_key="daily_rating",
        name="Daily Price Rating",
        icon="mdi:calendar-today",
        native_unit_of_measurement="%",
    ),
    SensorEntityDescription(
        key="monthly_rating",
        translation_key="monthly_rating",
        name="Monthly Price Rating",
        icon="mdi:calendar-month",
        native_unit_of_measurement="%",
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
            "current_price": lambda: self._get_hourly_price_value(hour_offset=0, in_euro=False),
            "current_price_eur": lambda: self._get_hourly_price_value(hour_offset=0, in_euro=True),
            "next_hour_price": lambda: self._get_hourly_price_value(hour_offset=1, in_euro=False),
            "next_hour_price_eur": lambda: self._get_hourly_price_value(hour_offset=1, in_euro=True),
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
            "hourly_rating": lambda: self._get_rating_value(rating_type="hourly"),
            "daily_rating": lambda: self._get_rating_value(rating_type="daily"),
            "monthly_rating": lambda: self._get_rating_value(rating_type="monthly"),
            # Diagnostic sensors
            "data_timestamp": self._get_data_timestamp,
            "tomorrow_data_available": self._get_tomorrow_data_status,
        }

        return handlers.get(key)

    def _get_current_hour_data(self) -> dict | None:
        """Get the price data for the current hour."""
        if not self.coordinator.data:
            return None
        now = datetime.now(tz=UTC).astimezone()
        price_info = self.coordinator.data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]
        for price_data in price_info.get("today", []):
            starts_at = datetime.fromisoformat(price_data["startsAt"])
            if starts_at.hour == now.hour:
                return price_data
        return None

    def _get_price_level_value(self) -> str | None:
        """Get the current price level value."""
        current_hour_data = self._get_current_hour_data()
        return current_hour_data["level"] if current_hour_data else None

    def _get_price_value(self, price: float, *, in_euro: bool) -> float:
        """Convert price based on unit."""
        return price if in_euro else round((price * 100), 2)

    def _get_hourly_price_value(self, *, hour_offset: int, in_euro: bool) -> float | None:
        """Get price for current hour or with offset."""
        if not self.coordinator.data:
            return None

        price_info = self.coordinator.data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]
        now = datetime.now(tz=UTC).astimezone()
        target_hour = (now.hour + hour_offset) % 24

        for price_data in price_info.get("today", []):
            starts_at = datetime.fromisoformat(price_data["startsAt"])
            if starts_at.hour == target_hour:
                return self._get_price_value(float(price_data["total"]), in_euro=in_euro)

        return None

    def _get_statistics_value(
        self, *, stat_func: Callable[[list[float]], float], in_euro: bool, decimals: int | None = None
    ) -> float | None:
        """Handle statistics sensor values using the provided statistical function."""
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

    def _get_rating_value(self, *, rating_type: str) -> float | None:
        """Handle rating sensor values."""
        if not self.coordinator.data:
            return None

        subscription = self.coordinator.data["data"]["viewer"]["homes"][0]["currentSubscription"]
        price_rating = subscription.get("priceRating", {}) or {}
        now = datetime.now(tz=UTC).astimezone()

        rating_data = price_rating.get(rating_type, {})
        entries = rating_data.get("entries", []) if rating_data else []

        if rating_type == "hourly":
            for entry in entries:
                entry_time = datetime.fromisoformat(entry["time"])
                if entry_time.hour == now.hour:
                    return round(float(entry["difference"]) * 100, 1)
        elif rating_type == "daily":
            for entry in entries:
                entry_time = datetime.fromisoformat(entry["time"])
                if entry_time.date() == now.date():
                    return round(float(entry["difference"]) * 100, 1)
        elif rating_type == "monthly":
            for entry in entries:
                entry_time = datetime.fromisoformat(entry["time"])
                if entry_time.month == now.month and entry_time.year == now.year:
                    return round(float(entry["difference"]) * 100, 1)

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

    @property
    def native_value(self) -> float | str | datetime | None:
        """Return the native value of the sensor."""
        try:
            if not self.coordinator.data or not self._value_getter:
                return None
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

            # Import only within the method to avoid circular imports
            from .const import (
                CONF_EXTENDED_DESCRIPTIONS,
                DEFAULT_EXTENDED_DESCRIPTIONS,
                async_get_entity_description,
            )

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

            # Import synchronous function to get cached descriptions
            from .const import (
                CONF_EXTENDED_DESCRIPTIONS,
                DEFAULT_EXTENDED_DESCRIPTIONS,
                get_entity_description,
            )

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
            key = self.entity_description.key
            attributes: dict[str, Any] = {}

            # Get the timestamp attribute for different sensor types
            price_info = self.coordinator.data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]

            current_hour_data = self._get_current_hour_data()
            now = datetime.now(tz=UTC).astimezone()

            # Price sensors timestamps
            if key in ["current_price", "current_price_eur", "price_level"]:
                attributes["timestamp"] = current_hour_data["startsAt"] if current_hour_data else None
            elif key in ["next_hour_price", "next_hour_price_eur"]:
                next_hour = (now.hour + 1) % 24
                for price_data in price_info.get("today", []):
                    starts_at = datetime.fromisoformat(price_data["startsAt"])
                    if starts_at.hour == next_hour:
                        attributes["timestamp"] = price_data["startsAt"]
                        break
            # Statistics, rating, and diagnostic sensors
            elif any(
                pattern in key for pattern in ["_price_today", "rating", "data_timestamp", "tomorrow_data_available"]
            ):
                first_timestamp = price_info.get("today", [{}])[0].get("startsAt")
                attributes["timestamp"] = first_timestamp

        except (KeyError, ValueError, TypeError) as ex:
            self.coordinator.logger.exception(
                "Error getting sensor attributes",
                extra={
                    "error": str(ex),
                    "entity": self.entity_description.key,
                },
            )
            return None
        else:
            return attributes if attributes else None
