"""Binary sensor core class for tibber_prices."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import yaml

from custom_components.tibber_prices.const import CONF_CHART_DATA_CONFIG, DOMAIN
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
        self._chart_data_last_update = None  # Track last service call timestamp
        self._chart_data_error = None  # Track last service call error

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()

        # Register with coordinator for time-sensitive updates if applicable
        if self.entity_description.key in TIME_SENSITIVE_ENTITY_KEYS:
            self._time_sensitive_remove_listener = self.coordinator.async_add_time_sensitive_listener(
                self._handle_time_sensitive_update
            )

        # For chart_data_export, trigger initial service call
        if self.entity_description.key == "chart_data_export":
            await self._refresh_chart_data()

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
            "chart_data_export": self._chart_data_export_state,
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

    def _chart_data_export_state(self) -> bool | None:
        """Return True if chart data export was successful."""
        if not self.coordinator.data:
            return None

        # Try to fetch chart data - state is ON if successful
        # Note: This is called in property context, so we can't use async
        # We'll check if data was cached from last async call
        chart_data = self._get_cached_chart_data()
        return chart_data is not None

    def _get_cached_chart_data(self) -> dict | None:
        """Get cached chart data from last service call."""
        # Store service response in instance variable for reuse
        if not hasattr(self, "_chart_data_cache"):
            self._chart_data_cache = None
        return self._chart_data_cache

    async def _call_chartdata_service_async(self) -> dict | None:
        """Call get_chartdata service with user-configured YAML (async)."""
        # Get user-configured YAML
        yaml_config = self.coordinator.config_entry.options.get(CONF_CHART_DATA_CONFIG, "")

        # Parse YAML if provided, otherwise use empty dict (service defaults)
        service_params = {}
        if yaml_config and yaml_config.strip():
            try:
                parsed = yaml.safe_load(yaml_config)
                # Ensure we have a dict (yaml.safe_load can return str, int, etc.)
                if isinstance(parsed, dict):
                    service_params = parsed
                else:
                    self.coordinator.logger.warning(
                        "YAML configuration must be a dictionary, got %s. Using service defaults.",
                        type(parsed).__name__,
                        extra={"entity": self.entity_description.key},
                    )
                    service_params = {}
            except yaml.YAMLError as err:
                self.coordinator.logger.warning(
                    "Invalid chart data YAML configuration: %s. Using service defaults.",
                    err,
                    extra={"entity": self.entity_description.key},
                )
                service_params = {}  # Fall back to service defaults

        # Add required entry_id parameter
        service_params["entry_id"] = self.coordinator.config_entry.entry_id

        # Call get_chartdata service using official HA service system
        try:
            response = await self.hass.services.async_call(
                DOMAIN,
                "get_chartdata",
                service_params,
                blocking=True,
                return_response=True,
            )
        except Exception as ex:
            self.coordinator.logger.exception(
                "Chart data service call failed",
                extra={"entity": self.entity_description.key},
            )
            self._chart_data_cache = None
            self._chart_data_last_update = dt_util.now()
            self._chart_data_error = str(ex)
            return None
        else:
            self._chart_data_cache = response
            self._chart_data_last_update = dt_util.now()
            self._chart_data_error = None
            return response

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
        if key == "chart_data_export":
            return self._get_chart_data_export_attributes

        return None

    def _get_chart_data_export_attributes(self) -> dict[str, object] | None:
        """
        Return chart data from service call as attributes with metadata.

        Strategy to avoid attribute name collisions:
        - If service returns dict with SINGLE top-level key → use directly
        - If service returns dict with MULTIPLE top-level keys → wrap in {"data": {...}}
        - If service returns array/primitive → wrap in {"data": <response>}

        Attribute order: timestamp, error (if any), descriptions, service data (at the end).
        """
        chart_data = self._get_cached_chart_data()

        # Build base attributes with metadata
        # timestamp = when service was last called (not current interval)
        attributes: dict[str, object] = {
            "timestamp": self._chart_data_last_update.isoformat() if self._chart_data_last_update else None,
        }

        # Add error message if service call failed
        if self._chart_data_error:
            attributes["error"] = self._chart_data_error

        # Note: descriptions will be added by build_async_extra_state_attributes
        # and will appear before service data because we return attributes first,
        # then they get merged with descriptions, then service data is appended

        if not chart_data:
            # No data - only metadata (timestamp, error)
            return attributes

        # Service data goes at the END - append after metadata
        # If response is a dict with multiple top-level keys, wrap it
        # to avoid collision with our own attributes (timestamp, error, etc.)
        if isinstance(chart_data, dict):
            if len(chart_data) > 1:
                # Multiple keys → wrap to prevent collision
                attributes["data"] = chart_data
            else:
                # Single key → safe to merge directly
                attributes.update(chart_data)
        else:
            # If response is array/list/primitive, wrap it in "data" key
            attributes["data"] = chart_data

        return attributes

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Chart data export: No automatic refresh needed.
        # Data only refreshes on:
        # 1. Initial sensor activation (async_added_to_hass)
        # 2. Config changes via Options Flow (triggers re-add)
        # Hourly coordinator updates don't change the chart data content.
        super()._handle_coordinator_update()

    async def _refresh_chart_data(self) -> None:
        """
        Refresh chart data by calling service.

        Called only on:
        - Initial sensor activation (async_added_to_hass)
        - Config changes via Options Flow (triggers re-add → async_added_to_hass)

        NOT called on routine coordinator updates to avoid unnecessary service calls.
        """
        await self._call_chartdata_service_async()
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
            # For chart_data_export, use custom attribute builder with descriptions
            if self.entity_description.key == "chart_data_export":
                chart_attrs = self._get_chart_data_export_attributes()
                # Add descriptions like other sensors
                return await build_async_extra_state_attributes(
                    self.entity_description.key,
                    self.entity_description.translation_key,
                    self.hass,
                    config_entry=self.coordinator.config_entry,
                    dynamic_attrs=chart_attrs,
                    is_on=self.is_on,
                )

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
            # For chart_data_export, use custom attribute builder with descriptions
            if self.entity_description.key == "chart_data_export":
                chart_attrs = self._get_chart_data_export_attributes()
                # Add descriptions like other sensors
                return build_sync_extra_state_attributes(
                    self.entity_description.key,
                    self.entity_description.translation_key,
                    self.hass,
                    config_entry=self.coordinator.config_entry,
                    dynamic_attrs=chart_attrs,
                    is_on=self.is_on,
                )

            # Get the dynamic attributes if the getter is available
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
        # Always refresh coordinator data
        await self.coordinator.async_request_refresh()

        # For chart_data_export, also refresh the service call
        if self.entity_description.key == "chart_data_export":
            await self._refresh_chart_data()
