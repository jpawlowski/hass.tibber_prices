"""Binary sensor core class for tibber_prices."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from custom_components.tibber_prices.coordinator import TIME_SENSITIVE_ENTITY_KEYS
from custom_components.tibber_prices.entity import TibberPricesEntity
from custom_components.tibber_prices.entity_utils import get_binary_sensor_icon
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import callback
from homeassistant.util import dt as dt_util

from .attributes import (
    build_async_extra_state_attributes,
    build_sync_extra_state_attributes,
    get_price_intervals_attributes,
    get_tomorrow_data_available_attributes,
)
from .definitions import (
    MIN_TOMORROW_INTERVALS_15MIN,
    PERIOD_LOOKAHEAD_HOURS,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from custom_components.tibber_prices.coordinator import (
        TibberPricesDataUpdateCoordinator,
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
        self._time_sensitive_remove_listener: Callable | None = None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()

        # Register with coordinator for time-sensitive updates if applicable
        if self.entity_description.key in TIME_SENSITIVE_ENTITY_KEYS:
            self._time_sensitive_remove_listener = self.coordinator.async_add_time_sensitive_listener(
                self._handle_time_sensitive_update
            )

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        await super().async_will_remove_from_hass()

        # Remove time-sensitive listener if registered
        if self._time_sensitive_remove_listener:
            self._time_sensitive_remove_listener()
            self._time_sensitive_remove_listener = None

    @callback
    def _handle_time_sensitive_update(self) -> None:
        """Handle time-sensitive update from coordinator."""
        self.async_write_ha_state()

    def _get_state_getter(self) -> Callable | None:
        """Return the appropriate state getter method based on the sensor type."""
        key = self.entity_description.key

        state_getters = {
            "peak_price_period": self._peak_price_state,
            "best_price_period": self._best_price_state,
            "connection": lambda: True if self.coordinator.data else None,
            "tomorrow_data_available": self._tomorrow_data_available_state,
            "has_ventilation_system": self._has_ventilation_system_state,
            "realtime_consumption_enabled": self._realtime_consumption_enabled_state,
        }

        return state_getters.get(key)

    def _best_price_state(self) -> bool | None:
        """Return True if the current time is within a best price period."""
        if not self.coordinator.data:
            return None
        attrs = get_price_intervals_attributes(self.coordinator.data, reverse_sort=False)
        if not attrs:
            return False  # Should not happen, but safety fallback
        start = attrs.get("start")
        end = attrs.get("end")
        if not start or not end:
            return False  # No period found = sensor is off
        now = dt_util.now()
        return start <= now < end

    def _peak_price_state(self) -> bool | None:
        """Return True if the current time is within a peak price period."""
        if not self.coordinator.data:
            return None
        attrs = get_price_intervals_attributes(self.coordinator.data, reverse_sort=True)
        if not attrs:
            return False  # Should not happen, but safety fallback
        start = attrs.get("start")
        end = attrs.get("end")
        if not start or not end:
            return False  # No period found = sensor is off
        now = dt_util.now()
        return start <= now < end

    def _tomorrow_data_available_state(self) -> bool | None:
        """Return True if tomorrow's data is fully available, False if not, None if unknown."""
        if not self.coordinator.data:
            return None
        price_info = self.coordinator.data.get("priceInfo", {})
        tomorrow_prices = price_info.get("tomorrow", [])
        interval_count = len(tomorrow_prices)
        if interval_count == MIN_TOMORROW_INTERVALS_15MIN:
            return True
        if interval_count == 0:
            return False
        return False

    def _has_ventilation_system_state(self) -> bool | None:
        """Return True if the home has a ventilation system."""
        if not self.coordinator.data:
            return None

        user_homes = self.coordinator.get_user_homes()
        if not user_homes:
            return None

        home_id = self.coordinator.config_entry.data.get("home_id")
        if not home_id:
            return None

        home_data = next((home for home in user_homes if home.get("id") == home_id), None)
        if not home_data:
            return None

        value = home_data.get("hasVentilationSystem")
        return value if isinstance(value, bool) else None

    def _realtime_consumption_enabled_state(self) -> bool | None:
        """Return True if realtime consumption is enabled."""
        if not self.coordinator.data:
            return None

        user_homes = self.coordinator.get_user_homes()
        if not user_homes:
            return None

        home_id = self.coordinator.config_entry.data.get("home_id")
        if not home_id:
            return None

        home_data = next((home for home in user_homes if home.get("id") == home_id), None)
        if not home_data:
            return None

        features = home_data.get("features")
        if not features:
            return None

        value = features.get("realTimeConsumptionEnabled")
        return value if isinstance(value, bool) else None

    def _get_tomorrow_data_available_attributes(self) -> dict | None:
        """Return attributes for tomorrow_data_available binary sensor."""
        return get_tomorrow_data_available_attributes(self.coordinator.data)

    def _get_attribute_getter(self) -> Callable | None:
        """Return the appropriate attribute getter method based on the sensor type."""
        key = self.entity_description.key

        if key == "peak_price_period":
            return lambda: get_price_intervals_attributes(self.coordinator.data, reverse_sort=True)
        if key == "best_price_period":
            return lambda: get_price_intervals_attributes(self.coordinator.data, reverse_sort=False)
        if key == "tomorrow_data_available":
            return self._get_tomorrow_data_available_attributes

        return None

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
    def icon(self) -> str | None:
        """Return the icon based on binary sensor state."""
        key = self.entity_description.key

        # Use shared icon utility
        icon = get_binary_sensor_icon(
            key,
            is_on=self.is_on,
            has_future_periods_callback=self._has_future_periods,
        )

        # Fall back to static icon from entity description
        return icon or self.entity_description.icon

    def _has_future_periods(self) -> bool:
        """
        Check if there are periods starting within the next 6 hours.

        Returns True if any period starts between now and PERIOD_LOOKAHEAD_HOURS from now.
        This provides a practical planning horizon instead of hard midnight cutoff.
        """
        if not self._attribute_getter:
            return False

        attrs = self._attribute_getter()
        if not attrs or "periods" not in attrs:
            return False

        now = dt_util.now()
        horizon = now + timedelta(hours=PERIOD_LOOKAHEAD_HOURS)
        periods = attrs.get("periods", [])

        # Check if any period starts within the look-ahead window
        for period in periods:
            start_str = period.get("start")
            if start_str:
                # Parse datetime if it's a string, otherwise use as-is
                start_time = dt_util.parse_datetime(start_str) if isinstance(start_str, str) else start_str

                if start_time:
                    start_time_local = dt_util.as_local(start_time)
                    # Period starts in the future but within our horizon
                    if now < start_time_local <= horizon:
                        return True

        return False

    @property
    async def async_extra_state_attributes(self) -> dict | None:
        """Return additional state attributes asynchronously."""
        try:
            # Get the dynamic attributes if the getter is available
            if not self.coordinator.data:
                return None

            dynamic_attrs = None
            if self._attribute_getter:
                dynamic_attrs = self._attribute_getter()

            # Use extracted function to build all attributes
            return await build_async_extra_state_attributes(
                self.entity_description.key,
                self.entity_description.translation_key,
                self.hass,
                config_entry=self.coordinator.config_entry,
                dynamic_attrs=dynamic_attrs,
                is_on=self.is_on,
            )

        except (KeyError, ValueError, TypeError) as ex:
            self.coordinator.logger.exception(
                "Error getting binary sensor attributes",
                extra={
                    "error": str(ex),
                    "entity": self.entity_description.key,
                },
            )
            return None

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return additional state attributes synchronously."""
        try:
            # Start with dynamic attributes if available
            if not self.coordinator.data:
                return None

            dynamic_attrs = None
            if self._attribute_getter:
                dynamic_attrs = self._attribute_getter()

            # Use extracted function to build all attributes
            return build_sync_extra_state_attributes(
                self.entity_description.key,
                self.entity_description.translation_key,
                self.hass,
                config_entry=self.coordinator.config_entry,
                dynamic_attrs=dynamic_attrs,
                is_on=self.is_on,
            )

        except (KeyError, ValueError, TypeError) as ex:
            self.coordinator.logger.exception(
                "Error getting binary sensor attributes",
                extra={
                    "error": str(ex),
                    "entity": self.entity_description.key,
                },
            )
            return None

    async def async_update(self) -> None:
        """Force a refresh when homeassistant.update_entity is called."""
        await self.coordinator.async_request_refresh()
