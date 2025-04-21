"""Sensor platform for tibber_prices."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CURRENCY_EURO, EntityCategory
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .entity import TibberPricesEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import TibberPricesDataUpdateCoordinator
    from .data import TibberPricesConfigEntry

# Main price sensors that users will typically use in automations
PRICE_SENSORS = (
    SensorEntityDescription(
        key="current_price",
        translation_key="current_price",
        name="Current Electricity Price",
        icon="mdi:currency-eur",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=CURRENCY_EURO,
    ),
    SensorEntityDescription(
        key="next_hour_price",
        translation_key="next_hour_price",
        name="Next Hour Electricity Price",
        icon="mdi:currency-eur-off",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=CURRENCY_EURO,
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
        translation_key="lowest_price_today",
        name="Today's Lowest Price",
        icon="mdi:currency-eur",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=CURRENCY_EURO,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="highest_price_today",
        translation_key="highest_price_today",
        name="Today's Highest Price",
        icon="mdi:currency-eur",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=CURRENCY_EURO,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="average_price_today",
        translation_key="average_price_today",
        name="Today's Average Price",
        icon="mdi:currency-eur",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=CURRENCY_EURO,
        entity_category=EntityCategory.DIAGNOSTIC,
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
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="daily_rating",
        translation_key="daily_rating",
        name="Daily Price Rating",
        icon="mdi:calendar-today",
        native_unit_of_measurement="%",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="monthly_rating",
        translation_key="monthly_rating",
        name="Monthly Price Rating",
        icon="mdi:calendar-month",
        native_unit_of_measurement="%",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

# Diagnostic sensors for data availability
DIAGNOSTIC_SENSORS = (
    SensorEntityDescription(
        key="data_timestamp",
        translation_key="data_timestamp",
        name="Last Data Update",
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
    hass: HomeAssistant,
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

    @property
    def native_value(self) -> float | str | datetime | None:
        """Return the native value of the sensor."""
        try:
            if not self.coordinator.data:
                return None

            subscription = self.coordinator.data["data"]["viewer"]["homes"][0]["currentSubscription"]
            price_info = subscription["priceInfo"]
            price_rating = subscription.get("priceRating") or {}

            # Get current hour's data
            now = datetime.now()
            current_hour_data = None
            for price_data in price_info.get("today", []):
                starts_at = datetime.fromisoformat(price_data["startsAt"])
                if starts_at.hour == now.hour:
                    current_hour_data = price_data
                    break

            if self.entity_description.key == "current_price":
                return float(current_hour_data["total"]) if current_hour_data else None

            elif self.entity_description.key == "next_hour_price":
                next_hour = (now.hour + 1) % 24
                for price_data in price_info.get("today", []):
                    starts_at = datetime.fromisoformat(price_data["startsAt"])
                    if starts_at.hour == next_hour:
                        return float(price_data["total"])
                return None

            elif self.entity_description.key == "lowest_price_today":
                today_prices = price_info.get("today", [])
                if not today_prices:
                    return None
                return min(float(price["total"]) for price in today_prices)

            elif self.entity_description.key == "highest_price_today":
                today_prices = price_info.get("today", [])
                if not today_prices:
                    return None
                return max(float(price["total"]) for price in today_prices)

            elif self.entity_description.key == "average_price_today":
                today_prices = price_info.get("today", [])
                if not today_prices:
                    return None
                return sum(float(price["total"]) for price in today_prices) / len(today_prices)

            elif self.entity_description.key == "price_level":
                return current_hour_data["level"] if current_hour_data else None

            elif self.entity_description.key == "hourly_rating":
                hourly = price_rating.get("hourly", {})
                entries = hourly.get("entries", []) if hourly else []
                if not entries:
                    return None
                for entry in entries:
                    starts_at = datetime.fromisoformat(entry["time"])
                    if starts_at.hour == now.hour:
                        return round(float(entry["difference"]) * 100, 1)
                return None

            elif self.entity_description.key == "daily_rating":
                daily = price_rating.get("daily", {})
                entries = daily.get("entries", []) if daily else []
                if not entries:
                    return None
                for entry in entries:
                    starts_at = datetime.fromisoformat(entry["time"])
                    if starts_at.date() == now.date():
                        return round(float(entry["difference"]) * 100, 1)
                return None

            elif self.entity_description.key == "monthly_rating":
                monthly = price_rating.get("monthly", {})
                entries = monthly.get("entries", []) if monthly else []
                if not entries:
                    return None
                for entry in entries:
                    starts_at = datetime.fromisoformat(entry["time"])
                    if starts_at.month == now.month and starts_at.year == now.year:
                        return round(float(entry["difference"]) * 100, 1)
                return None

            elif self.entity_description.key == "data_timestamp":
                # Return the latest timestamp from any data we have
                latest_timestamp = None

                # Check today's data
                for price_data in price_info.get("today", []):
                    timestamp = datetime.fromisoformat(price_data["startsAt"])
                    if not latest_timestamp or timestamp > latest_timestamp:
                        latest_timestamp = timestamp

                # Check tomorrow's data
                for price_data in price_info.get("tomorrow", []):
                    timestamp = datetime.fromisoformat(price_data["startsAt"])
                    if not latest_timestamp or timestamp > latest_timestamp:
                        latest_timestamp = timestamp

                return dt_util.as_utc(latest_timestamp) if latest_timestamp else None

            elif self.entity_description.key == "tomorrow_data_available":
                tomorrow_prices = price_info.get("tomorrow", [])
                if not tomorrow_prices:
                    return "No"
                # Check if we have a full day of data (24 hours)
                return "Yes" if len(tomorrow_prices) == 24 else "Partial"

            return None

        except (KeyError, ValueError, TypeError) as ex:
            self.coordinator.logger.error(
                "Error getting sensor value",
                extra={
                    "error": str(ex),
                    "entity": self.entity_description.key,
                },
            )
            return None

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return additional state attributes."""
        try:
            if not self.coordinator.data:
                return None

            subscription = self.coordinator.data["data"]["viewer"]["homes"][0]["currentSubscription"]
            price_info = subscription["priceInfo"]

            attributes = {}

            if self.entity_description.key == "current_price":
                attributes["timestamp"] = price_info.get("current", {}).get("startsAt")
            elif self.entity_description.key == "next_hour_price":
                attributes["timestamp"] = price_info.get("current", {}).get("startsAt")
            elif self.entity_description.key == "price_level":
                attributes["timestamp"] = price_info.get("current", {}).get("startsAt")
            elif self.entity_description.key == "lowest_price_today":
                attributes["timestamp"] = price_info.get("today", [{}])[0].get("startsAt")
            elif self.entity_description.key == "highest_price_today":
                attributes["timestamp"] = price_info.get("today", [{}])[0].get("startsAt")
            elif self.entity_description.key == "average_price_today":
                attributes["timestamp"] = price_info.get("today", [{}])[0].get("startsAt")
            elif self.entity_description.key == "hourly_rating":
                attributes["timestamp"] = price_info.get("current", {}).get("startsAt")
            elif self.entity_description.key == "daily_rating":
                attributes["timestamp"] = price_info.get("today", [{}])[0].get("startsAt")
            elif self.entity_description.key == "monthly_rating":
                attributes["timestamp"] = price_info.get("today", [{}])[0].get("startsAt")
            elif self.entity_description.key == "data_timestamp":
                attributes["timestamp"] = price_info.get("today", [{}])[0].get("startsAt")
            elif self.entity_description.key == "tomorrow_data_available":
                attributes["timestamp"] = price_info.get("today", [{}])[0].get("startsAt")

            # Add translated description
            if self.hass is not None:
                key = f"entity.sensor.{self.entity_description.translation_key}.description"
                language_config = getattr(self.hass.config, 'language', None)
                if isinstance(language_config, dict):
                    description = language_config.get(key)
                    if description is not None:
                        attributes["description"] = description

            return attributes if attributes else None

        except (KeyError, ValueError, TypeError) as ex:
            self.coordinator.logger.error(
                "Error getting sensor attributes",
                extra={
                    "error": str(ex),
                    "entity": self.entity_description.key,
                },
            )
            return None
