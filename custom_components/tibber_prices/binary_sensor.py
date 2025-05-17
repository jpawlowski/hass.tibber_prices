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
from homeassistant.util import dt as dt_util

from .entity import TibberPricesEntity
from .sensor import detect_interval_granularity, find_price_data_for_interval

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import TibberPricesDataUpdateCoordinator
    from .data import TibberPricesConfigEntry

from .const import (
    CONF_BEST_PRICE_FLEX,
    CONF_PEAK_PRICE_FLEX,
    DEFAULT_BEST_PRICE_FLEX,
    DEFAULT_PEAK_PRICE_FLEX,
)

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

        if key == "peak_price_period":
            return self._peak_price_state
        if key == "best_price_period":
            return self._best_price_state
        if key == "connection":
            return lambda: True if self.coordinator.data else None

        return None

    def _get_flex_option(self, option_key: str, default: float) -> float:
        """Get a float option from config entry options or fallback to default. Accepts 0-100."""
        options = self.coordinator.config_entry.options
        data = self.coordinator.config_entry.data
        value = options.get(option_key, data.get(option_key, default))
        try:
            value = float(value) / 100
        except (TypeError, ValueError):
            value = default
        return value

    def _best_price_state(self) -> bool | None:
        """Return True if current price is within +flex% of the day's minimum price."""
        price_data = self._get_current_price_data()
        if not price_data:
            return None
        prices, current_price = price_data
        min_price = min(prices)
        flex = self._get_flex_option(CONF_BEST_PRICE_FLEX, DEFAULT_BEST_PRICE_FLEX)
        threshold = min_price * (1 + flex)
        return current_price <= threshold

    def _peak_price_state(self) -> bool | None:
        """Return True if current price is within -flex% of the day's maximum price."""
        price_data = self._get_current_price_data()
        if not price_data:
            return None
        prices, current_price = price_data
        max_price = max(prices)
        flex = self._get_flex_option(CONF_PEAK_PRICE_FLEX, DEFAULT_PEAK_PRICE_FLEX)
        threshold = max_price * (1 - flex)
        return current_price >= threshold

    def _get_price_threshold_state(self, *, threshold_percentage: float, high_is_active: bool) -> bool | None:
        """Deprecate: use _best_price_state or _peak_price_state for those sensors."""
        price_data = self._get_current_price_data()
        if not price_data:
            return None

        prices, current_price = price_data
        threshold_index = int(len(prices) * threshold_percentage)

        if high_is_active:
            return current_price >= prices[threshold_index]

        return current_price <= prices[threshold_index]

    def _get_attribute_getter(self) -> Callable | None:
        """Return the appropriate attribute getter method based on the sensor type."""
        key = self.entity_description.key

        if key == "peak_price_period":
            return lambda: self._get_price_intervals_attributes(reverse_sort=True)
        if key == "best_price_period":
            return lambda: self._get_price_intervals_attributes(reverse_sort=False)

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

    def _annotate_period_intervals(
        self,
        periods: list[list[dict]],
        ref_price: float,
        avg_price: float,
        interval_minutes: int,
    ) -> list[dict]:
        """Return flattened and annotated intervals with period info and requested properties."""
        # Determine reference type for naming
        reference_type = None
        if self.entity_description.key == "best_price_period":
            reference_type = "min"
        elif self.entity_description.key == "peak_price_period":
            reference_type = "max"
        else:
            reference_type = "ref"
        # Set attribute name suffixes
        if reference_type == "min":
            diff_key = "price_diff_from_min"
            diff_ct_key = "price_diff_from_min_ct"
            diff_pct_key = "price_diff_from_min_" + PERCENTAGE
        elif reference_type == "max":
            diff_key = "price_diff_from_max"
            diff_ct_key = "price_diff_from_max_ct"
            diff_pct_key = "price_diff_from_max_" + PERCENTAGE
        else:
            diff_key = "price_diff"
            diff_ct_key = "price_diff_ct"
            diff_pct_key = "price_diff_" + PERCENTAGE
        result = []
        period_count = len(periods)
        for idx, period in enumerate(periods, 1):
            period_start = period[0]["interval_start"] if period else None
            period_start_hour = period_start.hour if period_start else None
            period_start_minute = period_start.minute if period_start else None
            period_start_time = f"{period_start_hour:02d}:{period_start_minute:02d}" if period_start else None
            period_end = period[-1]["interval_end"] if period else None
            interval_count = len(period)
            period_length = interval_count * interval_minutes
            periods_remaining = len(periods) - idx
            for interval_idx, interval in enumerate(period, 1):
                interval_copy = interval.copy()
                interval_remaining = interval_count - interval_idx
                # Compose new dict with period-related keys first, then interval timing, then price info
                new_interval = {
                    "period_start": period_start,
                    "period_end": period_end,
                    "hour": period_start_hour,
                    "minute": period_start_minute,
                    "time": period_start_time,
                    "period_length_minute": period_length,
                    "period_remaining_minute_after_interval": interval_remaining * interval_minutes,
                    "periods_total": period_count,
                    "periods_remaining": periods_remaining,
                    "interval_total": interval_count,
                    "interval_remaining": interval_remaining,
                    "interval_position": interval_idx,
                }
                # Add interval timing
                new_interval["interval_start"] = interval_copy.pop("interval_start", None)
                new_interval["interval_end"] = interval_copy.pop("interval_end", None)
                # Add hour, minute, time, price if present in interval_copy
                for k in ("interval_hour", "interval_minute", "interval_time", "price"):
                    if k in interval_copy:
                        new_interval[k] = interval_copy.pop(k)
                # Add the rest of the interval info (e.g. price_ct, price_difference_*, etc.)
                new_interval.update(interval_copy)
                new_interval["price_ct"] = round(new_interval["price"] * 100, 2)
                price_diff = new_interval["price"] - ref_price
                new_interval[diff_key] = round(price_diff, 4)
                new_interval[diff_ct_key] = round(price_diff * 100, 2)
                price_diff_percent = ((new_interval["price"] - ref_price) / ref_price) * 100 if ref_price != 0 else 0.0
                new_interval[diff_pct_key] = round(price_diff_percent, 2)
                # Add difference to average price of the day (avg_price is now passed in)
                avg_diff = new_interval["price"] - avg_price
                new_interval["price_diff_from_avg"] = round(avg_diff, 4)
                new_interval["price_diff_from_avg_ct"] = round(avg_diff * 100, 2)
                avg_diff_percent = ((new_interval["price"] - avg_price) / avg_price) * 100 if avg_price != 0 else 0.0
                new_interval["price_diff_from_avg_" + PERCENTAGE] = round(avg_diff_percent, 2)
                result.append(new_interval)
        return result

    def _get_price_intervals_attributes(self, *, reverse_sort: bool) -> dict | None:
        """
        Get price interval attributes with support for 15-minute intervals and period grouping.

        Args:
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

        interval_minutes = detect_interval_granularity(today_prices)

        # Use entity type to determine flex and logic, but always use 'price_intervals' as attribute name
        if reverse_sort is False:  # best_price_period entity
            flex = self._get_flex_option(CONF_BEST_PRICE_FLEX, DEFAULT_BEST_PRICE_FLEX)
            prices = [float(p["total"]) for p in today_prices]
            min_price = min(prices)

            def in_range(price: float) -> bool:
                return price <= min_price * (1 + flex)

            ref_price = min_price
        elif reverse_sort is True:  # peak_price_period entity
            flex = self._get_flex_option(CONF_PEAK_PRICE_FLEX, DEFAULT_PEAK_PRICE_FLEX)
            prices = [float(p["total"]) for p in today_prices]
            max_price = max(prices)

            def in_range(price: float) -> bool:
                return price >= max_price * (1 - flex)

            ref_price = max_price
        else:
            return None

        # Calculate average price for the day (all intervals, not just periods)
        all_prices = [float(p["total"]) for p in today_prices]
        avg_price = sum(all_prices) / len(all_prices) if all_prices else 0.0

        # Build intervals with period grouping
        periods = []
        current_period = []
        for price_data in today_prices:
            starts_at = dt_util.parse_datetime(price_data["startsAt"])
            if starts_at is None:
                continue
            starts_at = dt_util.as_local(starts_at)
            price = float(price_data["total"])
            if in_range(price):
                current_period.append(
                    {
                        "interval_hour": starts_at.hour,
                        "interval_minute": starts_at.minute,
                        "interval_time": f"{starts_at.hour:02d}:{starts_at.minute:02d}",
                        "price": price,
                        "interval_start": starts_at,
                        # interval_end will be filled later
                    }
                )
            elif current_period:
                periods.append(current_period)
                current_period = []
        if current_period:
            periods.append(current_period)

        # Add interval_end to each interval (next interval's start or None)
        for period in periods:
            for idx, interval in enumerate(period):
                if idx + 1 < len(period):
                    interval["interval_end"] = period[idx + 1]["interval_start"]
                else:
                    # Try to estimate end as start + interval_minutes
                    interval["interval_end"] = interval["interval_start"] + timedelta(minutes=interval_minutes)

        result = self._annotate_period_intervals(periods, ref_price, avg_price, interval_minutes)

        # Find the current or next interval (by time) from the annotated result
        now = dt_util.now()
        current_interval = None
        for interval in result:
            start = interval.get("interval_start")
            end = interval.get("interval_end")
            if start and end and start <= now < end:
                current_interval = interval.copy()
                break
        else:
            # If no current interval, show the next period's first interval (if available)
            for interval in result:
                start = interval.get("interval_start")
                if start and start > now:
                    current_interval = interval.copy()
                    break

        attributes = {**current_interval} if current_interval else {}
        attributes["intervals"] = result
        return attributes

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
