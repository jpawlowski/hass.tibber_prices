"""Binary sensor core class for tibber_prices."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.tibber_prices.coordinator import TIME_SENSITIVE_ENTITY_KEYS
from custom_components.tibber_prices.coordinator.core import get_connection_state
from custom_components.tibber_prices.coordinator.helpers import get_intervals_for_day_offsets
from custom_components.tibber_prices.entity import TibberPricesEntity
from custom_components.tibber_prices.entity_utils import get_binary_sensor_icon
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.restore_state import RestoreEntity

from .attributes import (
    build_async_extra_state_attributes,
    build_sync_extra_state_attributes,
    get_price_intervals_attributes,
    get_tomorrow_data_available_attributes,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from custom_components.tibber_prices.coordinator import (
        TibberPricesDataUpdateCoordinator,
    )
    from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService


class TibberPricesBinarySensor(TibberPricesEntity, BinarySensorEntity, RestoreEntity):
    """tibber_prices binary_sensor class with state restoration."""

    # Attributes excluded from recorder history
    # See: https://developers.home-assistant.io/docs/core/entity/#excluding-state-attributes-from-recorder-history
    _unrecorded_attributes = frozenset(
        {
            "timestamp",
            # Descriptions/Help Text (static, large)
            "description",
            "usage_tips",
            # Large Nested Structures
            "periods",  # Array of all period summaries
            # Frequently Changing Diagnostics
            "icon_color",
            "data_status",
            # Static/Rarely Changing
            "level_value",
            "rating_value",
            "level_id",
            "rating_id",
            # Relaxation Details
            "relaxation_level",
            "relaxation_threshold_original_%",
            "relaxation_threshold_applied_%",
            # Redundant/Derived
            "price_spread",
            "volatility",
            "rating_difference_%",
            "period_price_diff_from_daily_min",
            "period_price_diff_from_daily_min_%",
            "periods_total",
            "periods_remaining",
        }
    )

    def __init__(
        self,
        coordinator: TibberPricesDataUpdateCoordinator,
        entity_description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary_sensor class."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{entity_description.key}"
        self._state_getter: Callable | None = self._get_value_getter()
        self._time_sensitive_remove_listener: Callable | None = None

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()

        # Restore last state if available
        if (last_state := await self.async_get_last_state()) is not None and last_state.state in ("on", "off"):
            # Restore binary state (on/off) - will be used until first coordinator update
            self._attr_is_on = last_state.state == "on"

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
    def _handle_time_sensitive_update(self, time_service: TibberPricesTimeService) -> None:
        """
        Handle time-sensitive update from coordinator.

        Args:
            time_service: TibberPricesTimeService instance with reference time for this update cycle

        """
        # Store TimeService from Timer #2 for calculations during this update cycle
        self.coordinator.time = time_service

        self.async_write_ha_state()

    def _get_value_getter(self) -> Callable | None:
        """Return the appropriate value getter method based on the sensor type."""
        key = self.entity_description.key

        state_getters = {
            "peak_price_period": self._peak_price_state,
            "best_price_period": self._best_price_state,
            "connection": lambda: get_connection_state(self.coordinator),
            "tomorrow_data_available": self._tomorrow_data_available_state,
            "has_ventilation_system": self._has_ventilation_system_state,
            "realtime_consumption_enabled": self._realtime_consumption_enabled_state,
        }

        return state_getters.get(key)

    def _best_price_state(self) -> bool | None:
        """Return True if the current time is within a best price period."""
        if not self.coordinator.data:
            return None
        attrs = get_price_intervals_attributes(
            self.coordinator.data,
            reverse_sort=False,
            time=self.coordinator.time,
            config_entry=self.coordinator.config_entry,
        )
        if not attrs:
            return False  # Should not happen, but safety fallback
        start = attrs.get("start")
        end = attrs.get("end")
        if not start or not end:
            return False  # No period found = sensor is off
        time = self.coordinator.time
        return time.is_time_in_period(start, end)

    def _peak_price_state(self) -> bool | None:
        """Return True if the current time is within a peak price period."""
        if not self.coordinator.data:
            return None
        attrs = get_price_intervals_attributes(
            self.coordinator.data,
            reverse_sort=True,
            time=self.coordinator.time,
            config_entry=self.coordinator.config_entry,
        )
        if not attrs:
            return False  # Should not happen, but safety fallback
        start = attrs.get("start")
        end = attrs.get("end")
        if not start or not end:
            return False  # No period found = sensor is off
        time = self.coordinator.time
        return time.is_time_in_period(start, end)

    def _tomorrow_data_available_state(self) -> bool | None:
        """Return True if tomorrow's data is fully available, False if not, None if unknown."""
        # Auth errors: Cannot reliably check - return unknown
        # User must fix auth via reauth flow before we can determine tomorrow data availability
        if isinstance(self.coordinator.last_exception, ConfigEntryAuthFailed):
            return None

        # No data: unknown state (initializing or error)
        if not self.coordinator.data:
            return None

        # Check tomorrow data availability (normal operation)
        tomorrow_prices = get_intervals_for_day_offsets(self.coordinator.data, [1])
        tomorrow_date = self.coordinator.time.get_local_date(offset_days=1)
        interval_count = len(tomorrow_prices)

        # Get expected intervals for tomorrow (handles DST)
        expected_intervals = self.coordinator.time.get_expected_intervals_for_day(tomorrow_date)

        if interval_count == expected_intervals:
            return True
        if interval_count == 0:
            return False
        return False

    @property
    def available(self) -> bool:
        """
        Return if entity is available.

        Override base implementation for connection sensor which should
        always be available to show connection state.
        """
        # Connection sensor is always available (shows connection state)
        if self.entity_description.key == "connection":
            return True

        # All other binary sensors use base availability logic
        return super().available

    @property
    def force_update(self) -> bool:
        """
        Force update for connection sensor to record all state changes.

        Connection sensor should write every state change to history,
        even if the state (on/off) is the same, to track connectivity issues.
        """
        return self.entity_description.key == "connection"

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
        return get_tomorrow_data_available_attributes(self.coordinator.data, time=self.coordinator.time)

    def _get_sensor_attributes(self) -> dict | None:
        """
        Get sensor-specific attributes.

        Returns a dictionary of sensor-specific attributes, or None if no
        attributes are needed.
        """
        key = self.entity_description.key

        if key == "peak_price_period":
            return get_price_intervals_attributes(
                self.coordinator.data,
                reverse_sort=True,
                time=self.coordinator.time,
                config_entry=self.coordinator.config_entry,
            )
        if key == "best_price_period":
            return get_price_intervals_attributes(
                self.coordinator.data,
                reverse_sort=False,
                time=self.coordinator.time,
                config_entry=self.coordinator.config_entry,
            )
        if key == "tomorrow_data_available":
            return self._get_tomorrow_data_available_attributes()

        return None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # All binary sensors get push updates when coordinator has new data:
        # - tomorrow_data_available: Reflects new data availability immediately after API fetch
        # - connection: Reflects connection state changes immediately
        # - chart_data_export: Updates chart data when price data changes
        # - peak_price_period, best_price_period: Update when periods change (also get Timer #2 updates)
        # - data_lifecycle_status: Gets both push and Timer #2 updates
        self.async_write_ha_state()

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
        Check if there are any future periods.

        Returns True if any period starts in the future (no time limit).
        This ensures icons show "waiting" state whenever periods are scheduled.
        """
        attrs = self._get_sensor_attributes()
        if not attrs or "periods" not in attrs:
            return False

        time = self.coordinator.time
        periods = attrs.get("periods", [])

        # Check if any period starts in the future (no time limit)
        for period in periods:
            start_str = period.get("start")
            if start_str:
                # Already datetime object (periods come from coordinator.data)
                start_time = start_str if not isinstance(start_str, str) else time.parse_datetime(start_str)

                # Period starts in the future
                if start_time and time.is_in_future(start_time):
                    return True

        return False

    @property
    async def async_extra_state_attributes(self) -> dict | None:
        """Return additional state attributes asynchronously."""
        try:
            # Get the sensor-specific attributes
            if not self.coordinator.data:
                return None

            sensor_attrs = self._get_sensor_attributes()

            # Use extracted function to build all attributes
            return await build_async_extra_state_attributes(
                self.entity_description.key,
                self.entity_description.translation_key,
                self.hass,
                config_entry=self.coordinator.config_entry,
                sensor_attrs=sensor_attrs,
                is_on=self.is_on,
                time=self.coordinator.time,
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
            # Get the sensor-specific attributes
            if not self.coordinator.data:
                return None

            sensor_attrs = self._get_sensor_attributes()

            # Use extracted function to build all attributes
            return build_sync_extra_state_attributes(
                self.entity_description.key,
                self.entity_description.translation_key,
                self.hass,
                config_entry=self.coordinator.config_entry,
                sensor_attrs=sensor_attrs,
                is_on=self.is_on,
                time=self.coordinator.time,
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
        # Always refresh coordinator data
        await self.coordinator.async_request_refresh()
