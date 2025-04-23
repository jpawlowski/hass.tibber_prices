"""Binary sensor platform for tibber_prices."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory

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
    _hass: HomeAssistant,
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
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{entity_description.key}"
        )

    def _get_current_price_data(self) -> tuple[list[float], float] | None:
        """Get current price data if available."""
        if not (
            self.coordinator.data
            and (
                today_prices := self.coordinator.data["data"]["viewer"]["homes"][0][
                    "currentSubscription"
                ]["priceInfo"].get("today", [])
            )
        ):
            return None

        now = datetime.now(tz=UTC).astimezone()
        current_hour_data = next(
            (
                price_data
                for price_data in today_prices
                if datetime.fromisoformat(price_data["startsAt"]).hour == now.hour
            ),
            None,
        )
        if not current_hour_data:
            return None

        prices = [float(price["total"]) for price in today_prices]
        prices.sort()
        return prices, float(current_hour_data["total"])

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary_sensor is on."""
        try:
            price_data = self._get_current_price_data()
            if not price_data:
                return None

            prices, current_price = price_data
            match self.entity_description.key:
                case "peak_hour":
                    threshold_index = int(len(prices) * 0.8)
                    return current_price >= prices[threshold_index]
                case "best_price_hour":
                    threshold_index = int(len(prices) * 0.2)
                    return current_price <= prices[threshold_index]
                case "connection":
                    return True
                case _:
                    return None

        except (KeyError, ValueError, TypeError) as ex:
            self.coordinator.logger.exception(
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

            subscription = self.coordinator.data["data"]["viewer"]["homes"][0][
                "currentSubscription"
            ]
            price_info = subscription["priceInfo"]
            attributes = {}

            if self.entity_description.key in ["peak_hour", "best_price_hour"]:
                today_prices = price_info.get("today", [])
                if today_prices:
                    prices = [
                        (
                            datetime.fromisoformat(price["startsAt"]).hour,
                            float(price["total"]),
                        )
                        for price in today_prices
                    ]

                    if self.entity_description.key == "peak_hour":
                        # Get top 5 peak hours
                        peak_hours = sorted(prices, key=lambda x: x[1], reverse=True)[
                            :5
                        ]
                        attributes["peak_hours"] = [
                            {"hour": hour, "price": price} for hour, price in peak_hours
                        ]
                    else:
                        # Get top 5 best price hours
                        best_hours = sorted(prices, key=lambda x: x[1])[:5]
                        attributes["best_price_hours"] = [
                            {"hour": hour, "price": price} for hour, price in best_hours
                        ]
                    return attributes
            else:
                return None

        except (KeyError, ValueError, TypeError) as ex:
            self.coordinator.logger.exception(
                "Error getting binary sensor attributes",
                extra={
                    "error": str(ex),
                    "entity": self.entity_description.key,
                },
            )
            return None
