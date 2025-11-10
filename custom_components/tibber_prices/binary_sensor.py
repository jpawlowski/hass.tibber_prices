"""Binary sensor platform for tibber_prices."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.util import dt as dt_util

from .coordinator import TIME_SENSITIVE_ENTITY_KEYS
from .entity import TibberPricesEntity

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import TibberPricesDataUpdateCoordinator
    from .data import TibberPricesConfigEntry

from .const import (
    CONF_EXTENDED_DESCRIPTIONS,
    DEFAULT_EXTENDED_DESCRIPTIONS,
    async_get_entity_description,
    get_entity_description,
)

MINUTES_PER_INTERVAL = 15
MIN_TOMORROW_INTERVALS_15MIN = 96

ENTITY_DESCRIPTIONS = (
    BinarySensorEntityDescription(
        key="peak_price_period",
        translation_key="peak_price_period",
        name="Peak Price Interval",
        icon="mdi:clock-alert",
    ),
    BinarySensorEntityDescription(
        key="best_price_period",
        translation_key="best_price_period",
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
    BinarySensorEntityDescription(
        key="tomorrow_data_available",
        translation_key="tomorrow_data_available",
        name="Tomorrow's Data Available",
        icon="mdi:calendar-check",
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

        if key == "peak_price_period":
            return self._peak_price_state
        if key == "best_price_period":
            return self._best_price_state
        if key == "connection":
            return lambda: True if self.coordinator.data else None
        if key == "tomorrow_data_available":
            return self._tomorrow_data_available_state

        return None

    def _best_price_state(self) -> bool | None:
        """Return True if the current time is within a best price period."""
        if not self.coordinator.data:
            return None
        attrs = self._get_price_intervals_attributes(reverse_sort=False)
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
        attrs = self._get_price_intervals_attributes(reverse_sort=True)
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

    def _get_tomorrow_data_available_attributes(self) -> dict | None:
        """Return attributes for tomorrow_data_available binary sensor."""
        if not self.coordinator.data:
            return None
        price_info = self.coordinator.data.get("priceInfo", {})
        tomorrow_prices = price_info.get("tomorrow", [])
        interval_count = len(tomorrow_prices)
        if interval_count == 0:
            status = "none"
        elif interval_count == MIN_TOMORROW_INTERVALS_15MIN:
            status = "full"
        else:
            status = "partial"
        return {
            "intervals_available": interval_count,
            "data_status": status,
        }

    def _get_attribute_getter(self) -> Callable | None:
        """Return the appropriate attribute getter method based on the sensor type."""
        key = self.entity_description.key

        if key == "peak_price_period":
            return lambda: self._get_price_intervals_attributes(reverse_sort=True)
        if key == "best_price_period":
            return lambda: self._get_price_intervals_attributes(reverse_sort=False)
        if key == "tomorrow_data_available":
            return self._get_tomorrow_data_available_attributes

        return None

    def _get_precomputed_period_data(self, *, reverse_sort: bool) -> dict | None:
        """
        Get precomputed period data from coordinator.

        Returns lightweight period summaries (no full price data to avoid redundancy).
        """
        if not self.coordinator.data:
            return None

        periods_data = self.coordinator.data.get("periods", {})
        period_type = "peak_price" if reverse_sort else "best_price"
        return periods_data.get(period_type)

    def _get_price_intervals_attributes(self, *, reverse_sort: bool) -> dict | None:
        """
        Get price interval attributes using precomputed data from coordinator.

        All data is already calculated in the coordinator - we just need to:
        1. Get period summaries from coordinator (already filtered and fully calculated)
        2. Add the current timestamp
        3. Find current or next period based on time

        Note: All calculations (filtering, aggregations, level/rating) are done in coordinator.
        """
        # Get precomputed period summaries from coordinator (already filtered and complete!)
        period_data = self._get_precomputed_period_data(reverse_sort=reverse_sort)
        if not period_data:
            return self._build_no_periods_result()

        period_summaries = period_data.get("periods", [])
        if not period_summaries:
            return self._build_no_periods_result()

        # Find current or next period based on current time
        now = dt_util.now()
        current_period = None

        # First pass: find currently active period
        for period in period_summaries:
            start = period.get("start")
            end = period.get("end")
            if start and end and start <= now < end:
                current_period = period
                break

        # Second pass: find next future period if none is active
        if not current_period:
            for period in period_summaries:
                start = period.get("start")
                if start and start > now:
                    current_period = period
                    break

        # Build final attributes
        return self._build_final_attributes_simple(current_period, period_summaries)

    def _build_no_periods_result(self) -> dict:
        """
        Build result when no periods exist (not filtered, just none available).

        Returns:
            A dict with empty periods and timestamp.

        """
        # Calculate timestamp: current time rounded down to last quarter hour
        now = dt_util.now()
        current_minute = (now.minute // 15) * 15
        timestamp = now.replace(minute=current_minute, second=0, microsecond=0)

        return {
            "timestamp": timestamp,
            "start": None,
            "end": None,
            "periods": [],
        }

    def _add_time_attributes(self, attributes: dict, current_period: dict, timestamp: datetime) -> None:
        """Add time-related attributes (priority 1)."""
        attributes["timestamp"] = timestamp
        if "start" in current_period:
            attributes["start"] = current_period["start"]
        if "end" in current_period:
            attributes["end"] = current_period["end"]
        if "duration_minutes" in current_period:
            attributes["duration_minutes"] = current_period["duration_minutes"]

    def _add_decision_attributes(self, attributes: dict, current_period: dict) -> None:
        """Add core decision attributes (priority 2)."""
        if "level" in current_period:
            attributes["level"] = current_period["level"]
        if "rating_level" in current_period:
            attributes["rating_level"] = current_period["rating_level"]
        if "rating_difference_%" in current_period:
            attributes["rating_difference_%"] = current_period["rating_difference_%"]

    def _add_price_attributes(self, attributes: dict, current_period: dict) -> None:
        """Add price statistics attributes (priority 3)."""
        if "price_avg" in current_period:
            attributes["price_avg"] = current_period["price_avg"]
        if "price_min" in current_period:
            attributes["price_min"] = current_period["price_min"]
        if "price_max" in current_period:
            attributes["price_max"] = current_period["price_max"]
        if "price_spread" in current_period:
            attributes["price_spread"] = current_period["price_spread"]
        if "volatility" in current_period:
            attributes["volatility"] = current_period["volatility"]

    def _add_comparison_attributes(self, attributes: dict, current_period: dict) -> None:
        """Add price comparison attributes (priority 4)."""
        if "period_price_diff_from_daily_min" in current_period:
            attributes["period_price_diff_from_daily_min"] = current_period["period_price_diff_from_daily_min"]
        if "period_price_diff_from_daily_min_%" in current_period:
            attributes["period_price_diff_from_daily_min_%"] = current_period["period_price_diff_from_daily_min_%"]

    def _add_detail_attributes(self, attributes: dict, current_period: dict) -> None:
        """Add detail information attributes (priority 5)."""
        if "period_interval_count" in current_period:
            attributes["period_interval_count"] = current_period["period_interval_count"]
        if "period_position" in current_period:
            attributes["period_position"] = current_period["period_position"]
        if "periods_total" in current_period:
            attributes["periods_total"] = current_period["periods_total"]
        if "periods_remaining" in current_period:
            attributes["periods_remaining"] = current_period["periods_remaining"]

    def _add_relaxation_attributes(self, attributes: dict, current_period: dict) -> None:
        """
        Add relaxation information attributes (priority 6).

        Only adds relaxation attributes if the period was actually relaxed.
        If relaxation_active is False or missing, no attributes are added.
        """
        if current_period.get("relaxation_active"):
            attributes["relaxation_active"] = True
            if "relaxation_level" in current_period:
                attributes["relaxation_level"] = current_period["relaxation_level"]
            if "relaxation_threshold_original_%" in current_period:
                attributes["relaxation_threshold_original_%"] = current_period["relaxation_threshold_original_%"]
            if "relaxation_threshold_applied_%" in current_period:
                attributes["relaxation_threshold_applied_%"] = current_period["relaxation_threshold_applied_%"]

    def _build_final_attributes_simple(
        self,
        current_period: dict | None,
        period_summaries: list[dict],
    ) -> dict:
        """
        Build the final attributes dictionary from coordinator's period summaries.

        All calculations are done in the coordinator - this just:
        1. Adds the current timestamp (only thing calculated every 15min)
        2. Uses the current/next period from summaries
        3. Adds nested period summaries

        Attributes are ordered following the documented priority:
        1. Time information (timestamp, start, end, duration)
        2. Core decision attributes (level, rating_level, rating_difference_%)
        3. Price statistics (price_avg, price_min, price_max, price_spread, volatility)
        4. Price differences (period_price_diff_from_daily_min, period_price_diff_from_daily_min_%)
        5. Detail information (period_interval_count, period_position, periods_total, periods_remaining)
        6. Relaxation information (relaxation_active, relaxation_level, relaxation_threshold_original_%,
           relaxation_threshold_applied_%) - only if period was relaxed
        7. Meta information (periods list)

        Args:
            current_period: The current or next period (already complete from coordinator)
            period_summaries: All period summaries from coordinator

        """
        now = dt_util.now()
        current_minute = (now.minute // 15) * 15
        timestamp = now.replace(minute=current_minute, second=0, microsecond=0)

        if current_period:
            # Build attributes in priority order using helper methods
            attributes = {}

            # 1. Time information
            self._add_time_attributes(attributes, current_period, timestamp)

            # 2. Core decision attributes
            self._add_decision_attributes(attributes, current_period)

            # 3. Price statistics
            self._add_price_attributes(attributes, current_period)

            # 4. Price differences
            self._add_comparison_attributes(attributes, current_period)

            # 5. Detail information
            self._add_detail_attributes(attributes, current_period)

            # 6. Relaxation information (only if period was relaxed)
            self._add_relaxation_attributes(attributes, current_period)

            # 7. Meta information (periods array)
            attributes["periods"] = period_summaries

            return attributes

        # No current/next period found - return all periods with timestamp
        return {
            "timestamp": timestamp,
            "periods": period_summaries,
        }

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
                    # Copy and remove internal fields before exposing to user
                    clean_attrs = {k: v for k, v in dynamic_attrs.items() if not k.startswith("_")}
                    attributes.update(clean_attrs)

            # Add descriptions from the custom translations file
            if self.entity_description.translation_key and self.hass is not None:
                # Get user's language preference
                language = self.hass.config.language if self.hass.config.language else "en"

                # Add basic description
                description = await async_get_entity_description(
                    self.hass,
                    "binary_sensor",
                    self.entity_description.translation_key,
                    language,
                    "description",
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
                        self.hass,
                        "binary_sensor",
                        self.entity_description.translation_key,
                        language,
                        "usage_tips",
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
                    # Copy and remove internal fields before exposing to user
                    clean_attrs = {k: v for k, v in dynamic_attrs.items() if not k.startswith("_")}
                    attributes.update(clean_attrs)

            # Add descriptions from the cache (non-blocking)
            if self.entity_description.translation_key and self.hass is not None:
                # Get user's language preference
                language = self.hass.config.language if self.hass.config.language else "en"

                # Add basic description from cache
                description = get_entity_description(
                    "binary_sensor",
                    self.entity_description.translation_key,
                    language,
                    "description",
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
                        "binary_sensor",
                        self.entity_description.translation_key,
                        language,
                        "long_description",
                    )
                    if long_desc:
                        attributes["long_description"] = long_desc

                    # Add usage tips if available in cache
                    usage_tips = get_entity_description(
                        "binary_sensor",
                        self.entity_description.translation_key,
                        language,
                        "usage_tips",
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

    async def async_update(self) -> None:
        """Force a refresh when homeassistant.update_entity is called."""
        await self.coordinator.async_request_refresh()
