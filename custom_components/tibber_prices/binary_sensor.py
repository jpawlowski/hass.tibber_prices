"""Binary sensor platform for tibber_prices."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

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
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{entity_description.key}"
        self._state_getter: Callable | None = self._get_state_getter()
        self._attribute_getter: Callable | None = self._get_attribute_getter()

    def _get_state_getter(self) -> Callable | None:
        """Return the appropriate state getter method based on the sensor type."""
        key = self.entity_description.key

        if key == "peak_hour":
            return lambda: self._get_price_threshold_state(threshold_percentage=0.8, high_is_active=True)
        if key == "best_price_hour":
            return lambda: self._get_price_threshold_state(threshold_percentage=0.2, high_is_active=False)
        if key == "connection":
            return lambda: True if self.coordinator.data else None

        return None

    def _get_attribute_getter(self) -> Callable | None:
        """Return the appropriate attribute getter method based on the sensor type."""
        key = self.entity_description.key

        if key == "peak_hour":
            return lambda: self._get_price_hours_attributes(attribute_name="peak_hours", reverse_sort=True)
        if key == "best_price_hour":
            return lambda: self._get_price_hours_attributes(attribute_name="best_price_hours", reverse_sort=False)

        return None

    def _get_current_price_data(self) -> tuple[list[float], float] | None:
        """Get current price data if available."""
        if not (
            self.coordinator.data
            and (
                today_prices := self.coordinator.data["data"]["viewer"]["homes"][0]["currentSubscription"][
                    "priceInfo"
                ].get("today", [])
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

    def _get_price_threshold_state(self, *, threshold_percentage: float, high_is_active: bool) -> bool | None:
        """
        Determine if current price is above/below threshold.

        Args:
            threshold_percentage: The percentage point in the sorted list (0.0-1.0)
            high_is_active: If True, value >= threshold is active, otherwise value <= threshold is active

        """
        price_data = self._get_current_price_data()
        if not price_data:
            return None

        prices, current_price = price_data
        threshold_index = int(len(prices) * threshold_percentage)

        if high_is_active:
            return current_price >= prices[threshold_index]

        return current_price <= prices[threshold_index]

    def _get_price_hours_attributes(self, *, attribute_name: str, reverse_sort: bool) -> dict | None:
        """Get price hours attributes."""
        if not self.coordinator.data:
            return None

        price_info = self.coordinator.data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]

        today_prices = price_info.get("today", [])
        if not today_prices:
            return None

        prices = [
            (
                datetime.fromisoformat(price["startsAt"]).hour,
                float(price["total"]),
            )
            for price in today_prices
        ]

        # Sort by price (high to low for peak, low to high for best)
        sorted_hours = sorted(prices, key=lambda x: x[1], reverse=reverse_sort)[:5]

        return {attribute_name: [{"hour": hour, "price": price} for hour, price in sorted_hours]}

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary_sensor is on."""
        try:
            if not self.coordinator.data or not self._state_getter:
                return None

            return self._state_getter()

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
            if not self.coordinator.data or not self._attribute_getter:
                return None

            return self._attribute_getter()

        except (KeyError, ValueError, TypeError) as ex:
            self.coordinator.logger.exception(
                "Error getting binary sensor attributes",
                extra={
                    "error": str(ex),
                    "entity": self.entity_description.key,
                },
            )
            return None
