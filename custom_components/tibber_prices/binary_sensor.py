"""Binary sensor platform for tibber_prices."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory

from .const import NAME, DOMAIN
from .entity import TibberPricesEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import TibberPricesDataUpdateCoordinator
    from .data import TibberPricesConfigEntry

ENTITY_DESCRIPTIONS = (
    BinarySensorEntityDescription(
        key="peak_hour",
        translation_key="peak_hour",
        name="Peak Hour",
        icon="mdi:clock-alert",
    ),
    BinarySensorEntityDescription(
        key="best_price_hour",
        translation_key="best_price_hour",
        name="Best Price Hour",
        icon="mdi:clock-check",
    ),
    BinarySensorEntityDescription(
        key="connection",
        translation_key="connection",
        name="Tibber API Connection",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TibberPricesConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary_sensor platform."""
    async_add_entities(
        TibberPricesBinarySensor(
            coordinator=entry.runtime_data.coordinator,
            entity_description=entity_description,
        )
        for entity_description in ENTITY_DESCRIPTIONS
    )


class TibberPricesBinarySensor(TibberPricesEntity, BinarySensorEntity):
    """tibber_prices binary_sensor class."""

    def __init__(
        self,
        coordinator: TibberPricesDataUpdateCoordinator,
        entity_description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary_sensor class."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{entity_description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary_sensor is on."""
        try:
            if not self.coordinator.data:
                return None

            subscription = self.coordinator.data["data"]["viewer"]["homes"][0]["currentSubscription"]
            price_info = subscription["priceInfo"]

            now = datetime.now()
            current_hour_data = None
            today_prices = price_info.get("today", [])

            if not today_prices:
                return None

            # Find current hour's data
            for price_data in today_prices:
                starts_at = datetime.fromisoformat(price_data["startsAt"])
                if starts_at.hour == now.hour:
                    current_hour_data = price_data
                    break

            if not current_hour_data:
                return None

            if self.entity_description.key == "peak_hour":
                # Consider it a peak hour if the price is in the top 20% of today's prices
                prices = [float(price["total"]) for price in today_prices]
                prices.sort()
                threshold_index = int(len(prices) * 0.8)
                peak_threshold = prices[threshold_index]
                return float(current_hour_data["total"]) >= peak_threshold

            elif self.entity_description.key == "best_price_hour":
                # Consider it a best price hour if the price is in the bottom 20% of today's prices
                prices = [float(price["total"]) for price in today_prices]
                prices.sort()
                threshold_index = int(len(prices) * 0.2)
                best_threshold = prices[threshold_index]
                return float(current_hour_data["total"]) <= best_threshold

            elif self.entity_description.key == "connection":
                # Check if we have valid current data
                return bool(current_hour_data)

            return None

        except (KeyError, ValueError, TypeError) as ex:
            self.coordinator.logger.error(
                "Error getting binary sensor state",
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

            if self.entity_description.key in ["peak_hour", "best_price_hour"]:
                today_prices = price_info.get("today", [])
                if today_prices:
                    prices = [(datetime.fromisoformat(price["startsAt"]).hour, float(price["total"]))
                             for price in today_prices]

                    if self.entity_description.key == "peak_hour":
                        # Get top 5 peak hours
                        peak_hours = sorted(prices, key=lambda x: x[1], reverse=True)[:5]
                        attributes["peak_hours"] = [
                            {"hour": hour, "price": price} for hour, price in peak_hours
                        ]
                    else:
                        # Get top 5 best price hours
                        best_hours = sorted(prices, key=lambda x: x[1])[:5]
                        attributes["best_price_hours"] = [
                            {"hour": hour, "price": price} for hour, price in best_hours
                        ]

            return attributes if attributes else None

        except (KeyError, ValueError, TypeError) as ex:
            self.coordinator.logger.error(
                "Error getting binary sensor attributes",
                extra={
                    "error": str(ex),
                    "entity": self.entity_description.key,
                },
            )
            return None
