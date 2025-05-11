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
from homeassistant.util import dt as dt_util

from .entity import TibberPricesEntity
from .sensor import detect_interval_granularity, find_price_data_for_interval

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import TibberPricesDataUpdateCoordinator
    from .data import TibberPricesConfigEntry

ENTITY_DESCRIPTIONS = (
    BinarySensorEntityDescription(
        key="peak_interval",
        translation_key="peak_interval",
        name="Peak Price Interval",
        icon="mdi:clock-alert",
    ),
    BinarySensorEntityDescription(
        key="best_price_interval",
        translation_key="best_price_interval",
        name="Best Price Interval",
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

        if key == "peak_interval":
            return lambda: self._get_price_threshold_state(threshold_percentage=0.8, high_is_active=True)
        if key == "best_price_interval":
            return lambda: self._get_price_threshold_state(threshold_percentage=0.2, high_is_active=False)
        if key == "connection":
            return lambda: True if self.coordinator.data else None

        return None

    def _get_attribute_getter(self) -> Callable | None:
        """Return the appropriate attribute getter method based on the sensor type."""
        key = self.entity_description.key

        if key == "peak_interval":
            return lambda: self._get_price_intervals_attributes(attribute_name="peak_intervals", reverse_sort=True)
        if key == "best_price_interval":
            return lambda: self._get_price_intervals_attributes(
                attribute_name="best_price_intervals", reverse_sort=False
            )

        return None

    def _get_current_price_data(self) -> tuple[list[float], float] | None:
        """Get current price data if available."""
        if not self.coordinator.data:
            return None

        price_info = self.coordinator.data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]
        today_prices = price_info.get("today", [])

        if not today_prices:
            return None

        now = dt_util.now()

        # Detect interval granularity
        interval_minutes = detect_interval_granularity(today_prices)

        # Find price data for current interval
        current_interval_data = find_price_data_for_interval({"today": today_prices}, now, interval_minutes)

        if not current_interval_data:
            return None

        prices = [float(price["total"]) for price in today_prices]
        prices.sort()
        return prices, float(current_interval_data["total"])

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

    def _get_price_intervals_attributes(self, *, attribute_name: str, reverse_sort: bool) -> dict | None:
        """
        Get price interval attributes with support for 15-minute intervals.

        Args:
            attribute_name: The attribute name to use in the result dictionary
            reverse_sort: Whether to sort prices in reverse (high to low)

        Returns:
            Dictionary with interval data or None if not available

        """
        if not self.coordinator.data:
            return None

        price_info = self.coordinator.data["data"]["viewer"]["homes"][0]["currentSubscription"]["priceInfo"]
        today_prices = price_info.get("today", [])

        if not today_prices:
            return None

        # Detect the granularity of the data
        interval_minutes = detect_interval_granularity(today_prices)

        # Build a list of price data with timestamps and values
        price_intervals = []
        for price_data in today_prices:
            starts_at = dt_util.parse_datetime(price_data["startsAt"])
            if starts_at is None:
                continue

            starts_at = dt_util.as_local(starts_at)
            price_intervals.append(
                {
                    "starts_at": starts_at,
                    "price": float(price_data["total"]),
                    "hour": starts_at.hour,
                    "minute": starts_at.minute,
                }
            )

        # Sort by price (high to low for peak, low to high for best)
        sorted_intervals = sorted(price_intervals, key=lambda x: x["price"], reverse=reverse_sort)[:5]

        # Format the result based on granularity
        hourly_interval_minutes = 60
        result = []
        for interval in sorted_intervals:
            if interval_minutes < hourly_interval_minutes:  # More granular than hourly
                result.append(
                    {
                        "hour": interval["hour"],
                        "minute": interval["minute"],
                        "time": f"{interval['hour']:02d}:{interval['minute']:02d}",
                        "price": interval["price"],
                    }
                )
            else:  # Hourly data (for backward compatibility)
                result.append(
                    {
                        "hour": interval["hour"],
                        "price": interval["price"],
                    }
                )

        return {attribute_name: result}

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
    async def async_extra_state_attributes(self) -> dict | None:
        """Return additional state attributes asynchronously."""
        try:
            # Get the dynamic attributes if the getter is available
            if not self.coordinator.data:
                return None

            attributes = {}
            if self._attribute_getter:
                dynamic_attrs = self._attribute_getter()
                if dynamic_attrs:
                    attributes.update(dynamic_attrs)

            # Add descriptions from the custom translations file
            if self.entity_description.translation_key and self.hass is not None:
                # Get user's language preference
                language = self.hass.config.language if self.hass.config.language else "en"

                # Import async function to get descriptions
                from .const import (
                    CONF_EXTENDED_DESCRIPTIONS,
                    DEFAULT_EXTENDED_DESCRIPTIONS,
                    async_get_entity_description,
                )

                # Add basic description
                description = await async_get_entity_description(
                    self.hass, "binary_sensor", self.entity_description.translation_key, language, "description"
                )
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
                        self.hass,
                        "binary_sensor",
                        self.entity_description.translation_key,
                        language,
                        "long_description",
                    )
                    if long_desc:
                        attributes["long_description"] = long_desc

                    # Add usage tips if available
                    usage_tips = await async_get_entity_description(
                        self.hass, "binary_sensor", self.entity_description.translation_key, language, "usage_tips"
                    )
                    if usage_tips:
                        attributes["usage_tips"] = usage_tips

        except (KeyError, ValueError, TypeError) as ex:
            self.coordinator.logger.exception(
                "Error getting binary sensor attributes",
                extra={
                    "error": str(ex),
                    "entity": self.entity_description.key,
                },
            )
            return None
        else:
            return attributes if attributes else None

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return additional state attributes synchronously."""
        try:
            # Start with dynamic attributes if available
            if not self.coordinator.data:
                return None

            attributes = {}
            if self._attribute_getter:
                dynamic_attrs = self._attribute_getter()
                if dynamic_attrs:
                    attributes.update(dynamic_attrs)

            # Add descriptions from the cache (non-blocking)
            if self.entity_description.translation_key and self.hass is not None:
                # Get user's language preference
                language = self.hass.config.language if self.hass.config.language else "en"

                # Import synchronous function to get cached descriptions
                from .const import (
                    CONF_EXTENDED_DESCRIPTIONS,
                    DEFAULT_EXTENDED_DESCRIPTIONS,
                    get_entity_description,
                )

                # Add basic description from cache
                description = get_entity_description(
                    "binary_sensor", self.entity_description.translation_key, language, "description"
                )
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
                    long_desc = get_entity_description(
                        "binary_sensor", self.entity_description.translation_key, language, "long_description"
                    )
                    if long_desc:
                        attributes["long_description"] = long_desc

                    # Add usage tips if available in cache
                    usage_tips = get_entity_description(
                        "binary_sensor", self.entity_description.translation_key, language, "usage_tips"
                    )
                    if usage_tips:
                        attributes["usage_tips"] = usage_tips

        except (KeyError, ValueError, TypeError) as ex:
            self.coordinator.logger.exception(
                "Error getting binary sensor attributes",
                extra={
                    "error": str(ex),
                    "entity": self.entity_description.key,
                },
            )
            return None
        else:
            return attributes if attributes else None
