"""Sensor platform for tibber_prices."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CURRENCY_EURO, EntityCategory
from homeassistant.util import dt as dt_util

from .entity import TibberPricesEntity

if TYPE_CHECKING:
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
    ),
    SensorEntityDescription(
        key="current_price",
        translation_key="current_price_cents",
        name="Current Electricity Price",
        icon="mdi:currency-eur",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="ct/kWh",
    ),
    SensorEntityDescription(
        key="next_hour_price_eur",
        translation_key="next_hour_price",
        name="Next Hour Electricity Price",
        icon="mdi:currency-eur-off",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_EURO,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="next_hour_price",
        translation_key="next_hour_price_cents",
        name="Next Hour Electricity Price",
        icon="mdi:currency-eur-off",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="ct/kWh",
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
    ),
    SensorEntityDescription(
        key="lowest_price_today",
        translation_key="lowest_price_today_cents",
        name="Today's Lowest Price",
        icon="mdi:currency-eur",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="ct/kWh",
    ),
    SensorEntityDescription(
        key="highest_price_today_eur",
        translation_key="highest_price_today",
        name="Today's Highest Price",
        icon="mdi:currency-eur",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_EURO,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="highest_price_today",
        translation_key="highest_price_today_cents",
        name="Today's Highest Price",
        icon="mdi:currency-eur",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="ct/kWh",
    ),
    SensorEntityDescription(
        key="average_price_today_eur",
        translation_key="average_price_today",
        name="Today's Average Price",
        icon="mdi:currency-eur",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=CURRENCY_EURO,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="average_price_today",
        translation_key="average_price_today_cents",
        name="Today's Average Price",
        icon="mdi:currency-eur",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="ct/kWh",
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
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{entity_description.key}"
        )
        self._attr_has_entity_name = True

    def _get_current_hour_data(self) -> dict | None:
        """Get the price data for the current hour."""
        if not self.coordinator.data:
            return None
        now = datetime.now(tz=UTC).astimezone()
        price_info = self.coordinator.data["data"]["viewer"]["homes"][0][
            "currentSubscription"
        ]["priceInfo"]
        for price_data in price_info.get("today", []):
            starts_at = datetime.fromisoformat(price_data["startsAt"])
            if starts_at.hour == now.hour:
                return price_data
        return None

    def _get_price_value(self, price: float) -> float:
        """Convert price based on unit."""
        return (
            price * 100
            if self.entity_description.native_unit_of_measurement == "ct/kWh"
            else price
        )

    def _get_price_sensor_value(self) -> float | None:
        """Handle price sensor values."""
        if not self.coordinator.data:
            return None

        subscription = self.coordinator.data["data"]["viewer"]["homes"][0][
            "currentSubscription"
        ]
        price_info = subscription["priceInfo"]
        now = datetime.now(tz=UTC).astimezone()
        current_hour_data = self._get_current_hour_data()

        key = self.entity_description.key
        if key in ["current_price", "current_price_eur"]:
            if not current_hour_data:
                return None
            return (
                self._get_price_value(float(current_hour_data["total"]))
                if key == "current_price"
                else float(current_hour_data["total"])
            )

        if key in ["next_hour_price", "next_hour_price_eur"]:
            next_hour = (now.hour + 1) % 24
            for price_data in price_info.get("today", []):
                starts_at = datetime.fromisoformat(price_data["startsAt"])
                if starts_at.hour == next_hour:
                    return (
                        self._get_price_value(float(price_data["total"]))
                        if key == "next_hour_price"
                        else float(price_data["total"])
                    )
            return None

        return None

    def _get_statistics_value(self) -> float | None:
        """Handle statistics sensor values."""
        if not self.coordinator.data:
            return None

        price_info = self.coordinator.data["data"]["viewer"]["homes"][0][
            "currentSubscription"
        ]["priceInfo"]
        today_prices = price_info.get("today", [])
        if not today_prices:
            return None

        key = self.entity_description.key
        prices = [float(price["total"]) for price in today_prices]

        if key in ["lowest_price_today", "lowest_price_today_eur"]:
            value = min(prices)
        elif key in ["highest_price_today", "highest_price_today_eur"]:
            value = max(prices)
        elif key in ["average_price_today", "average_price_today_eur"]:
            value = sum(prices) / len(prices)
        else:
            return None

        return self._get_price_value(value) if key.endswith("today") else value

    def _get_rating_value(self) -> float | None:
        """Handle rating sensor values."""
        if not self.coordinator.data:
            return None

        def check_hourly(entry: dict) -> bool:
            return datetime.fromisoformat(entry["time"]).hour == now.hour

        def check_daily(entry: dict) -> bool:
            return datetime.fromisoformat(entry["time"]).date() == now.date()

        def check_monthly(entry: dict) -> bool:
            dt = datetime.fromisoformat(entry["time"])
            return dt.month == now.month and dt.year == now.year

        subscription = self.coordinator.data["data"]["viewer"]["homes"][0][
            "currentSubscription"
        ]
        price_rating = subscription.get("priceRating", {}) or {}
        now = datetime.now(tz=UTC).astimezone()

        key = self.entity_description.key
        if key == "hourly_rating":
            rating_data = price_rating.get("hourly", {})
            entries = rating_data.get("entries", []) if rating_data else []
            time_match = check_hourly
        elif key == "daily_rating":
            rating_data = price_rating.get("daily", {})
            entries = rating_data.get("entries", []) if rating_data else []
            time_match = check_daily
        elif key == "monthly_rating":
            rating_data = price_rating.get("monthly", {})
            entries = rating_data.get("entries", []) if rating_data else []
            time_match = check_monthly
        else:
            return None

        for entry in entries:
            if time_match(entry):
                return round(float(entry["difference"]) * 100, 1)
        return None

    def _get_diagnostic_value(self) -> datetime | str | None:
        """Handle diagnostic sensor values."""
        if not self.coordinator.data:
            return None

        price_info = self.coordinator.data["data"]["viewer"]["homes"][0][
            "currentSubscription"
        ]["priceInfo"]
        key = self.entity_description.key

        if key == "data_timestamp":
            latest_timestamp = None
            for day in ["today", "tomorrow"]:
                for price_data in price_info.get(day, []):
                    timestamp = datetime.fromisoformat(price_data["startsAt"])
                    if not latest_timestamp or timestamp > latest_timestamp:
                        latest_timestamp = timestamp
            return dt_util.as_utc(latest_timestamp) if latest_timestamp else None

        if key == "tomorrow_data_available":
            tomorrow_prices = price_info.get("tomorrow", [])
            if not tomorrow_prices:
                return "No"
            return "Yes" if len(tomorrow_prices) == HOURS_IN_DAY else "Partial"

        return None

    @property
    def native_value(self) -> float | str | datetime | None:
        """Return the native value of the sensor."""
        result = None
        try:
            if self.coordinator.data:
                key = self.entity_description.key
                current_hour_data = self._get_current_hour_data()

                if key == "price_level":
                    result = current_hour_data["level"] if current_hour_data else None
                elif key in [
                    "current_price",
                    "current_price_eur",
                    "next_hour_price",
                    "next_hour_price_eur",
                ]:
                    result = self._get_price_sensor_value()
                elif "price_today" in key:
                    result = self._get_statistics_value()
                elif "rating" in key:
                    result = self._get_rating_value()
                elif key in ["data_timestamp", "tomorrow_data_available"]:
                    result = self._get_diagnostic_value()
                else:
                    result = None
            else:
                result = None
        except (KeyError, ValueError, TypeError) as ex:
            self.coordinator.logger.exception(
                "Error getting sensor value",
                extra={
                    "error": str(ex),
                    "entity": self.entity_description.key,
                },
            )
            result = None
        return result

    @property
    def extra_state_attributes(self) -> dict | None:  # noqa: PLR0912
        """Return additional state attributes."""
        try:
            if not self.coordinator.data:
                return None

            subscription = self.coordinator.data["data"]["viewer"]["homes"][0][
                "currentSubscription"
            ]
            price_info = subscription["priceInfo"]

            attributes = {}

            # Get current hour's data for timestamp
            now = datetime.now(tz=UTC).astimezone()
            current_hour_data = self._get_current_hour_data()

            if self.entity_description.key in ["current_price", "current_price_eur"]:
                attributes["timestamp"] = (
                    current_hour_data["startsAt"] if current_hour_data else None
                )

            if self.entity_description.key in [
                "next_hour_price",
                "next_hour_price_eur",
            ]:
                next_hour = (now.hour + 1) % 24
                for price_data in price_info.get("today", []):
                    starts_at = datetime.fromisoformat(price_data["startsAt"])
                    if starts_at.hour == next_hour:
                        attributes["timestamp"] = price_data["startsAt"]
                        break

            if self.entity_description.key == "price_level":
                attributes["timestamp"] = (
                    current_hour_data["startsAt"] if current_hour_data else None
                )

            if self.entity_description.key == "lowest_price_today":
                attributes["timestamp"] = price_info.get("today", [{}])[0].get(
                    "startsAt"
                )

            if self.entity_description.key == "highest_price_today":
                attributes["timestamp"] = price_info.get("today", [{}])[0].get(
                    "startsAt"
                )

            if self.entity_description.key == "average_price_today":
                attributes["timestamp"] = price_info.get("today", [{}])[0].get(
                    "startsAt"
                )

            if self.entity_description.key == "hourly_rating":
                attributes["timestamp"] = (
                    current_hour_data["startsAt"] if current_hour_data else None
                )

            if self.entity_description.key == "daily_rating":
                attributes["timestamp"] = price_info.get("today", [{}])[0].get(
                    "startsAt"
                )

            if self.entity_description.key == "monthly_rating":
                attributes["timestamp"] = price_info.get("today", [{}])[0].get(
                    "startsAt"
                )

            if self.entity_description.key == "data_timestamp":
                attributes["timestamp"] = price_info.get("today", [{}])[0].get(
                    "startsAt"
                )

            if self.entity_description.key == "tomorrow_data_available":
                attributes["timestamp"] = price_info.get("today", [{}])[0].get(
                    "startsAt"
                )

            # Add translated description
            if self.hass is not None:
                base_key = "entity.sensor"
                key = (
                    f"{base_key}.{self.entity_description.translation_key}.description"
                )
                language_config = getattr(self.hass.config, "language", None)
                if isinstance(language_config, dict):
                    description = language_config.get(key)
                    if description is not None:
                        attributes["description"] = description

            return attributes if attributes else None  # noqa: TRY300

        except (KeyError, ValueError, TypeError) as ex:
            self.coordinator.logger.exception(
                "Error getting sensor attributes",
                extra={
                    "error": str(ex),
                    "entity": self.entity_description.key,
                },
            )
            return None
