"""Binary sensor platform for tibber_prices."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import callback
from homeassistant.util import dt as dt_util

from .coordinator import TIME_SENSITIVE_ENTITY_KEYS
from .entity import TibberPricesEntity

if TYPE_CHECKING:
    from collections.abc import Callable

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
        if not attrs or "start" not in attrs or "end" not in attrs:
            return None
        now = dt_util.now()
        start = attrs.get("start")
        end = attrs.get("end")
        return start <= now < end if start and end else None

    def _peak_price_state(self) -> bool | None:
        """Return True if the current time is within a peak price period."""
        if not self.coordinator.data:
            return None
        attrs = self._get_price_intervals_attributes(reverse_sort=True)
        if not attrs or "start" not in attrs or "end" not in attrs:
            return None
        now = dt_util.now()
        start = attrs.get("start")
        end = attrs.get("end")
        return start <= now < end if start and end else None

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

    def _get_period_intervals_from_price_info(self, period_summaries: list[dict], *, reverse_sort: bool) -> list[dict]:
        """
        Build full interval data from period summaries and priceInfo.

        This avoids storing price data redundantly by fetching it on-demand from priceInfo.
        """
        if not self.coordinator.data or not period_summaries:
            return []

        price_info = self.coordinator.data.get("priceInfo", {})
        yesterday = price_info.get("yesterday", [])
        today = price_info.get("today", [])
        tomorrow = price_info.get("tomorrow", [])

        # Build a quick lookup for prices by timestamp
        all_prices = yesterday + today + tomorrow
        price_lookup = {}
        for price_data in all_prices:
            starts_at = dt_util.parse_datetime(price_data["startsAt"])
            if starts_at:
                starts_at = dt_util.as_local(starts_at)
                price_lookup[starts_at.isoformat()] = price_data

        # Get reference data for annotations
        period_data = self._get_precomputed_period_data(reverse_sort=reverse_sort)
        if not period_data:
            return []

        ref_data = period_data.get("reference_data", {})
        ref_prices = ref_data.get("ref_prices", {})
        avg_prices = ref_data.get("avg_prices", {})

        # Build annotated intervals from period summaries
        intervals = []
        period_count = len(period_summaries)

        for period_idx, period_summary in enumerate(period_summaries, 1):
            period_start = period_summary.get("start")
            period_end = period_summary.get("end")
            interval_starts = period_summary.get("interval_starts", [])
            interval_count = len(interval_starts)
            duration_minutes = period_summary.get("duration_minutes", 0)
            periods_remaining = period_count - period_idx

            for interval_idx, start_iso in enumerate(interval_starts, 1):
                # Get price data from priceInfo
                price_data = price_lookup.get(start_iso)
                if not price_data:
                    continue

                starts_at = dt_util.parse_datetime(price_data["startsAt"])
                if not starts_at:
                    continue
                starts_at = dt_util.as_local(starts_at)
                date_key = starts_at.date().isoformat()

                price_raw = float(price_data["total"])
                price_minor = round(price_raw * 100, 2)

                # Get reference values for this day
                ref_price = ref_prices.get(date_key, 0.0)
                avg_price = avg_prices.get(date_key, 0.0)

                # Calculate price difference
                price_diff = price_raw - ref_price
                price_diff_minor = round(price_diff * 100, 2)
                price_diff_pct = (price_diff / ref_price) * 100 if ref_price != 0 else 0.0

                interval_remaining = interval_count - interval_idx
                interval_end = starts_at + timedelta(minutes=MINUTES_PER_INTERVAL)

                annotated = {
                    # Period-level attributes
                    "period_start": period_start,
                    "period_end": period_end,
                    "hour": period_start.hour if period_start else None,
                    "minute": period_start.minute if period_start else None,
                    "time": f"{period_start.hour:02d}:{period_start.minute:02d}" if period_start else None,
                    "duration_minutes": duration_minutes,
                    "remaining_minutes_in_period": interval_remaining * MINUTES_PER_INTERVAL,
                    "periods_total": period_count,
                    "periods_remaining": periods_remaining,
                    "period_position": period_idx,
                    # Interval-level attributes
                    "price": price_minor,
                    # Internal fields
                    "_interval_start": starts_at,
                    "_interval_end": interval_end,
                    "_ref_price": ref_price,
                    "_avg_price": avg_price,
                }

                # Add price difference attributes based on sensor type
                if reverse_sort:
                    annotated["price_diff_from_max"] = price_diff_minor
                    annotated[f"price_diff_from_max_{PERCENTAGE}"] = round(price_diff_pct, 2)
                else:
                    annotated["price_diff_from_min"] = price_diff_minor
                    annotated[f"price_diff_from_min_{PERCENTAGE}"] = round(price_diff_pct, 2)

                intervals.append(annotated)

        return intervals

    def _get_price_intervals_attributes(self, *, reverse_sort: bool) -> dict | None:
        """
        Get price interval attributes using precomputed data from coordinator.

        This method now:
        1. Gets lightweight period summaries from coordinator
        2. Fetches actual price data from priceInfo on-demand
        3. Builds annotations without storing data redundantly
        """
        # Get precomputed period summaries from coordinator
        period_data = self._get_precomputed_period_data(reverse_sort=reverse_sort)
        if not period_data:
            return None

        period_summaries = period_data.get("periods", [])
        if not period_summaries:
            return None

        # Build full interval data from summaries + priceInfo
        intervals = self._get_period_intervals_from_price_info(period_summaries, reverse_sort=reverse_sort)
        if not intervals:
            return None

        # Find current or next interval
        current_interval = self._find_current_or_next_interval(intervals)

        # Build periods summary (merge with original summaries to include level/rating_level)
        periods_summary = self._build_periods_summary(intervals, period_summaries)

        # Build final attributes
        return self._build_final_attributes(current_interval, periods_summary, intervals)

    def _find_current_or_next_interval(self, intervals: list[dict]) -> dict | None:
        """Find the current or next interval from the filtered list."""
        now = dt_util.now()
        # First pass: find currently active interval
        for interval in intervals:
            start = interval.get("_interval_start")
            end = interval.get("_interval_end")
            if start and end and start <= now < end:
                return interval.copy()
        # Second pass: find next future interval
        for interval in intervals:
            start = interval.get("_interval_start")
            if start and start > now:
                return interval.copy()
        return None

    def _build_periods_summary(self, intervals: list[dict], original_summaries: list[dict]) -> list[dict]:
        """
        Build a summary of periods with consistent attribute structure.

        Returns a list of period summaries with the same attributes as top-level,
        making the structure predictable and easy to use in automations.

        Args:
            intervals: List of interval dictionaries with period information
            original_summaries: Original period summaries from coordinator (with level/rating_level)

        """
        if not intervals:
            return []

        # Build a lookup for original summaries by start time
        original_lookup: dict[str, dict] = {}
        for summary in original_summaries:
            start = summary.get("start")
            if start:
                key = start.isoformat() if hasattr(start, "isoformat") else str(start)
                original_lookup[key] = summary

        # Group intervals by period (they have the same period_start)
        periods_dict: dict[str, list[dict]] = {}
        for interval in intervals:
            period_key = interval.get("period_start")
            if period_key:
                key_str = period_key.isoformat() if hasattr(period_key, "isoformat") else str(period_key)
                if key_str not in periods_dict:
                    periods_dict[key_str] = []
                periods_dict[key_str].append(interval)

        # Build summary for each period with consistent attribute names
        summaries = []
        for period_intervals in periods_dict.values():
            if not period_intervals:
                continue

            first = period_intervals[0]
            prices = [i["price"] for i in period_intervals if "price" in i]

            # Get level and rating_level from original summaries first
            aggregated_level = None
            aggregated_rating_level = None
            period_start = first.get("period_start")
            if period_start:
                key = period_start.isoformat() if hasattr(period_start, "isoformat") else str(period_start)
                original = original_lookup.get(key)
                if original:
                    aggregated_level = original.get("level")
                    aggregated_rating_level = original.get("rating_level")

            # Follow attribute ordering from copilot-instructions.md
            summary = {
                "start": first.get("period_start"),
                "end": first.get("period_end"),
                "duration_minutes": first.get("duration_minutes"),
                "level": aggregated_level,
                "rating_level": aggregated_rating_level,
                "price_avg": round(sum(prices) / len(prices), 2) if prices else 0,
                "price_min": round(min(prices), 2) if prices else 0,
                "price_max": round(max(prices), 2) if prices else 0,
                "hour": first.get("hour"),
                "minute": first.get("minute"),
                "time": first.get("time"),
                "periods_total": first.get("periods_total"),
                "periods_remaining": first.get("periods_remaining"),
                "period_position": first.get("period_position"),
                "interval_count": len(period_intervals),
            }

            # Add price_diff attributes if present (price differences step 4)
            self._add_price_diff_for_period(summary, period_intervals, first)

            summaries.append(summary)

        return summaries

    def _build_final_attributes(
        self,
        current_interval: dict | None,
        periods_summary: list[dict],
        filtered_result: list[dict],
    ) -> dict:
        """
        Build the final attributes dictionary from period summary and current interval.

        Combines period-level attributes with current interval-specific attributes,
        ensuring price_diff reflects the current interval's position vs daily min/max.
        """
        now = dt_util.now()
        current_minute = (now.minute // 15) * 15
        timestamp = now.replace(minute=current_minute, second=0, microsecond=0)

        if current_interval and periods_summary:
            # Find the current period in the summary based on period_start
            current_period_start = current_interval.get("period_start")
            current_period_summary = None

            for period in periods_summary:
                if period.get("start") == current_period_start:
                    current_period_summary = period
                    break

            if current_period_summary:
                # Follow attribute ordering from copilot-instructions.md
                attributes = {
                    "timestamp": timestamp,
                    "start": current_period_summary.get("start"),
                    "end": current_period_summary.get("end"),
                    "duration_minutes": current_period_summary.get("duration_minutes"),
                    "level": current_period_summary.get("level"),
                    "rating_level": current_period_summary.get("rating_level"),
                    "price_avg": current_period_summary.get("price_avg"),
                    "price_min": current_period_summary.get("price_min"),
                    "price_max": current_period_summary.get("price_max"),
                    "hour": current_period_summary.get("hour"),
                    "minute": current_period_summary.get("minute"),
                    "time": current_period_summary.get("time"),
                    "periods_total": current_period_summary.get("periods_total"),
                    "periods_remaining": current_period_summary.get("periods_remaining"),
                    "period_position": current_period_summary.get("period_position"),
                    "interval_count": current_period_summary.get("interval_count"),
                }

                # Add period price_diff attributes if present
                if "period_price_diff_from_daily_min" in current_period_summary:
                    attributes["period_price_diff_from_daily_min"] = current_period_summary[
                        "period_price_diff_from_daily_min"
                    ]
                    if "period_price_diff_from_daily_min_%" in current_period_summary:
                        attributes["period_price_diff_from_daily_min_%"] = current_period_summary[
                            "period_price_diff_from_daily_min_%"
                        ]
                elif "period_price_diff_from_daily_max" in current_period_summary:
                    attributes["period_price_diff_from_daily_max"] = current_period_summary[
                        "period_price_diff_from_daily_max"
                    ]
                    if "period_price_diff_from_daily_max_%" in current_period_summary:
                        attributes["period_price_diff_from_daily_max_%"] = current_period_summary[
                            "period_price_diff_from_daily_max_%"
                        ]

                # Add interval-specific price_diff attributes (separate from period average)
                # Shows the reference interval's position vs daily min/max:
                # - If period is active: current 15-min interval vs daily min/max
                # - If period hasn't started: first interval of the period vs daily min/max
                # This value is what determines if an interval is part of a period (compared to flex setting)
                if "price_diff_from_min" in current_interval:
                    attributes["interval_price_diff_from_daily_min"] = current_interval["price_diff_from_min"]
                    attributes["interval_price_diff_from_daily_min_%"] = current_interval.get("price_diff_from_min_%")
                elif "price_diff_from_max" in current_interval:
                    attributes["interval_price_diff_from_daily_max"] = current_interval["price_diff_from_max"]
                    attributes["interval_price_diff_from_daily_max_%"] = current_interval.get("price_diff_from_max_%")

                # Nested structures last (meta information step 6)
                attributes["periods"] = periods_summary
                return attributes

            # Fallback if current period not found in summary
            return {
                "timestamp": timestamp,
                "periods": periods_summary,
                "interval_count": len(filtered_result),
            }

        # No periods found
        return {
            "timestamp": timestamp,
            "periods": [],
            "interval_count": 0,
        }

    def _add_price_diff_for_period(self, summary: dict, period_intervals: list[dict], first: dict) -> None:
        """
        Add price difference attributes for the period based on sensor type.

        Uses the reference price (min/max) from the start day of the period to ensure
        consistent comparison, especially for periods spanning midnight.

        Calculates how the period's average price compares to the daily min/max,
        helping to explain why the period qualifies based on flex settings.
        """
        # Determine sensor type and get the reference price from the first interval
        # (which represents the start of the period and its day's reference value)
        if "price_diff_from_min" in first:
            # Best price sensor: calculate difference from the period's start day minimum
            period_start = first.get("period_start")
            if not period_start:
                return

            # Get all prices in minor units (cents/øre) from the period
            prices = [i["price"] for i in period_intervals if "price" in i]
            if not prices:
                return

            period_avg_price = sum(prices) / len(prices)

            # Extract the reference min price from first interval's calculation
            # We can back-calculate it from the first interval's price and diff
            first_price_minor = first.get("price")
            first_diff_minor = first.get("price_diff_from_min")

            if first_price_minor is not None and first_diff_minor is not None:
                ref_min_price = first_price_minor - first_diff_minor
                period_diff = period_avg_price - ref_min_price

                # Period average price difference from daily minimum
                summary["period_price_diff_from_daily_min"] = round(period_diff, 2)
                if ref_min_price != 0:
                    period_diff_pct = (period_diff / ref_min_price) * 100
                    summary["period_price_diff_from_daily_min_%"] = round(period_diff_pct, 2)

        elif "price_diff_from_max" in first:
            # Peak price sensor: calculate difference from the period's start day maximum
            period_start = first.get("period_start")
            if not period_start:
                return

            # Get all prices in minor units (cents/øre) from the period
            prices = [i["price"] for i in period_intervals if "price" in i]
            if not prices:
                return

            period_avg_price = sum(prices) / len(prices)

            # Extract the reference max price from first interval's calculation
            first_price_minor = first.get("price")
            first_diff_minor = first.get("price_diff_from_max")

            if first_price_minor is not None and first_diff_minor is not None:
                ref_max_price = first_price_minor - first_diff_minor
                period_diff = period_avg_price - ref_max_price

                # Period average price difference from daily maximum
                summary["period_price_diff_from_daily_max"] = round(period_diff, 2)
                if ref_max_price != 0:
                    period_diff_pct = (period_diff / ref_max_price) * 100
                    summary["period_price_diff_from_daily_max_%"] = round(period_diff_pct, 2)

    def _get_price_hours_attributes(self, *, attribute_name: str, reverse_sort: bool) -> dict | None:
        """Get price hours attributes."""
        if not self.coordinator.data:
            return None

        price_info = self.coordinator.data.get("priceInfo", {})

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
