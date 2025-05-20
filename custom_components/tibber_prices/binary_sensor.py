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

MIN_TOMORROW_INTERVALS_HOURLY = 24
MIN_TOMORROW_INTERVALS_15MIN = 96
TOMORROW_INTERVAL_COUNTS = {MIN_TOMORROW_INTERVALS_HOURLY, MIN_TOMORROW_INTERVALS_15MIN}

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
        """Return True if the current time is within a best price period."""
        if not self.coordinator.data:
            return None
        attrs = self._get_price_intervals_attributes(reverse_sort=False)
        if not attrs or "interval_start" not in attrs or "interval_end" not in attrs:
            return None
        now = dt_util.now()
        start = attrs.get("interval_start")
        end = attrs.get("interval_end")
        return start <= now < end if start and end else None

    def _peak_price_state(self) -> bool | None:
        """Return True if the current time is within a peak price period."""
        if not self.coordinator.data:
            return None
        attrs = self._get_price_intervals_attributes(reverse_sort=True)
        if not attrs or "interval_start" not in attrs or "interval_end" not in attrs:
            return None
        now = dt_util.now()
        start = attrs.get("interval_start")
        end = attrs.get("interval_end")
        return start <= now < end if start and end else None

    def _tomorrow_data_available_state(self) -> bool | None:
        """Return True if tomorrow's data is fully available, False if not, None if unknown."""
        if not self.coordinator.data:
            return None
        price_info = self.coordinator.data["priceInfo"]
        tomorrow_prices = price_info.get("tomorrow", [])
        interval_count = len(tomorrow_prices)
        if interval_count in TOMORROW_INTERVAL_COUNTS:
            return True
        if interval_count == 0:
            return False
        return False

    def _get_tomorrow_data_available_attributes(self) -> dict | None:
        """Return attributes for tomorrow_data_available binary sensor."""
        if not self.coordinator.data:
            return None
        price_info = self.coordinator.data["priceInfo"]
        tomorrow_prices = price_info.get("tomorrow", [])
        interval_count = len(tomorrow_prices)
        if interval_count == 0:
            status = "none"
        elif interval_count in TOMORROW_INTERVAL_COUNTS:
            status = "full"
        else:
            status = "partial"
        return {
            "intervals_available": interval_count,
            "status": status,
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

    def _get_current_price_data(self) -> tuple[list[float], float] | None:
        """Get current price data if available."""
        if not self.coordinator.data:
            return None

        price_info = self.coordinator.data["priceInfo"]
        today_prices = price_info.get("today", [])

        if not today_prices:
            return None

        now = dt_util.now()

        # Detect interval granularity
        interval_length = detect_interval_granularity(today_prices)

        # Find price data for current interval
        current_interval_data = find_price_data_for_interval({"today": today_prices}, now, interval_length)

        if not current_interval_data:
            return None

        prices = [float(price["total"]) for price in today_prices]
        prices.sort()
        return prices, float(current_interval_data["total"])

    def _annotate_single_interval(
        self,
        interval: dict,
        annotation_ctx: dict,
    ) -> dict:
        """Annotate a single interval with all required attributes for Home Assistant UI and automations."""
        interval_copy = interval.copy()
        interval_remaining = annotation_ctx["interval_count"] - annotation_ctx["interval_idx"]
        # Extract interval-related fields for attribute ordering and clarity
        interval_start = interval_copy.pop("interval_start", None)
        interval_end = interval_copy.pop("interval_end", None)
        interval_hour = interval_copy.pop("interval_hour", None)
        interval_minute = interval_copy.pop("interval_minute", None)
        interval_time = interval_copy.pop("interval_time", None)
        interval_length_minute = interval_copy.pop("interval_length_minute", annotation_ctx["interval_length"])
        price = interval_copy.pop("price", None)
        new_interval = {
            "period_start": annotation_ctx["period_start"],
            "period_end": annotation_ctx["period_end"],
            "hour": annotation_ctx["period_start_hour"],
            "minute": annotation_ctx["period_start_minute"],
            "time": annotation_ctx["period_start_time"],
            "period_length_minute": annotation_ctx["period_length"],
            "period_remaining_minute_after_interval": interval_remaining * annotation_ctx["interval_length"],
            "periods_total": annotation_ctx["period_count"],
            "periods_remaining": annotation_ctx["periods_remaining"],
            "period_position": annotation_ctx["period_idx"],
            "interval_total": annotation_ctx["interval_count"],
            "interval_remaining": interval_remaining,
            "interval_position": annotation_ctx["interval_idx"],
            "interval_start": interval_start,
            "interval_end": interval_end,
            "interval_hour": interval_hour,
            "interval_minute": interval_minute,
            "interval_time": interval_time,
            "interval_length_minute": interval_length_minute,
            "price": price,
        }
        # Merge any extra fields from the original interval (future-proofing)
        new_interval.update(interval_copy)
        new_interval["price_ct"] = round(new_interval["price"] * 100, 2)
        price_diff = new_interval["price"] - annotation_ctx["ref_price"]
        new_interval[annotation_ctx["diff_key"]] = round(price_diff, 4)
        new_interval[annotation_ctx["diff_ct_key"]] = round(price_diff * 100, 2)
        # Calculate percent difference from reference price (min or max)
        price_diff_percent = (
            ((new_interval["price"] - annotation_ctx["ref_price"]) / annotation_ctx["ref_price"]) * 100
            if annotation_ctx["ref_price"] != 0
            else 0.0
        )
        new_interval[annotation_ctx["diff_pct_key"]] = round(price_diff_percent, 2)
        # Calculate difference from average price for the day
        avg_diff = new_interval["price"] - annotation_ctx["avg_price"]
        new_interval["price_diff_from_avg"] = round(avg_diff, 4)
        new_interval["price_diff_from_avg_ct"] = round(avg_diff * 100, 2)
        avg_diff_percent = (
            ((new_interval["price"] - annotation_ctx["avg_price"]) / annotation_ctx["avg_price"]) * 100
            if annotation_ctx["avg_price"] != 0
            else 0.0
        )
        new_interval["price_diff_from_avg_" + PERCENTAGE] = round(avg_diff_percent, 2)
        return new_interval

    def _annotate_period_intervals(
        self,
        periods: list[list[dict]],
        ref_prices: dict,
        avg_price_by_day: dict,
        interval_length: int,
    ) -> list[dict]:
        """
        Return flattened and annotated intervals with period info and requested properties.

        Uses the correct reference price for each interval's date.
        """
        reference_type = None
        if self.entity_description.key == "best_price_period":
            reference_type = "min"
        elif self.entity_description.key == "peak_price_period":
            reference_type = "max"
        else:
            reference_type = "ref"
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
        for period_idx, period in enumerate(periods, 1):
            period_start = period[0]["interval_start"] if period else None
            period_start_hour = period_start.hour if period_start else None
            period_start_minute = period_start.minute if period_start else None
            period_start_time = f"{period_start_hour:02d}:{period_start_minute:02d}" if period_start else None
            period_end = period[-1]["interval_end"] if period else None
            interval_count = len(period)
            period_length = interval_count * interval_length
            periods_remaining = len(periods) - period_idx
            for interval_idx, interval in enumerate(period, 1):
                interval_start = interval.get("interval_start")
                interval_date = interval_start.date() if interval_start else None
                avg_price = avg_price_by_day.get(interval_date, 0)
                ref_price = ref_prices.get(interval_date, 0)
                annotation_ctx = {
                    "period_start": period_start,
                    "period_end": period_end,
                    "period_start_hour": period_start_hour,
                    "period_start_minute": period_start_minute,
                    "period_start_time": period_start_time,
                    "period_length": period_length,
                    "interval_count": interval_count,
                    "interval_idx": interval_idx,
                    "interval_length": interval_length,
                    "period_count": period_count,
                    "periods_remaining": periods_remaining,
                    "period_idx": period_idx,
                    "ref_price": ref_price,
                    "avg_price": avg_price,
                    "diff_key": diff_key,
                    "diff_ct_key": diff_ct_key,
                    "diff_pct_key": diff_pct_key,
                }
                new_interval = self._annotate_single_interval(
                    interval,
                    annotation_ctx,
                )
                result.append(new_interval)
        return result

    def _split_intervals_by_day(self, all_prices: list[dict]) -> tuple[dict, dict, dict]:
        """Split intervals by day, calculate interval minutes and average price per day."""
        intervals_by_day: dict = {}
        interval_length_by_day: dict = {}
        avg_price_by_day: dict = {}
        for price_data in all_prices:
            dt = dt_util.parse_datetime(price_data["startsAt"])
            if dt is None:
                continue
            date = dt.date()
            intervals_by_day.setdefault(date, []).append(price_data)
        for date, intervals in intervals_by_day.items():
            interval_length_by_day[date] = detect_interval_granularity(intervals)
            avg_price_by_day[date] = sum(float(p["total"]) for p in intervals) / len(intervals)
        return intervals_by_day, interval_length_by_day, avg_price_by_day

    def _calculate_reference_prices(self, intervals_by_day: dict, *, reverse_sort: bool) -> dict:
        """Calculate reference prices for each day."""
        ref_prices: dict = {}
        for date, intervals in intervals_by_day.items():
            prices = [float(p["total"]) for p in intervals]
            if reverse_sort is False:
                ref_prices[date] = min(prices)
            else:
                ref_prices[date] = max(prices)
        return ref_prices

    def _build_periods(
        self,
        all_prices: list[dict],
        ref_prices: dict,
        interval_length_by_day: dict,
        flex: float,
        *,
        reverse_sort: bool,
    ) -> list[list[dict]]:
        """
        Build periods, allowing periods to cross midnight (day boundary).

        Strictly enforce flex threshold by percent diff, matching attribute calculation.
        """
        periods: list[list[dict]] = []
        current_period: list[dict] = []
        last_ref_date = None
        for price_data in all_prices:
            starts_at = dt_util.parse_datetime(price_data["startsAt"])
            if starts_at is None:
                continue
            starts_at = dt_util.as_local(starts_at)
            date = starts_at.date()
            ref_price = ref_prices[date]
            interval_length = interval_length_by_day[date]
            price = float(price_data["total"])
            percent_diff = ((price - ref_price) / ref_price) * 100 if ref_price != 0 else 0.0
            percent_diff = round(percent_diff, 2)
            # For best price: percent_diff <= flex*100; for peak: percent_diff >= -flex*100
            in_flex = percent_diff <= flex * 100 if not reverse_sort else percent_diff >= -flex * 100
            # Split period if day or interval length changes
            if (
                last_ref_date is not None
                and (date != last_ref_date or interval_length != interval_length_by_day[last_ref_date])
                and current_period
            ):
                periods.append(current_period)
                current_period = []
            last_ref_date = date
            if in_flex:
                current_period.append(
                    {
                        "interval_hour": starts_at.hour,
                        "interval_minute": starts_at.minute,
                        "interval_time": f"{starts_at.hour:02d}:{starts_at.minute:02d}",
                        "interval_length_minute": interval_length,
                        "price": price,
                        "interval_start": starts_at,
                    }
                )
            elif current_period:
                periods.append(current_period)
                current_period = []
        if current_period:
            periods.append(current_period)
        return periods

    def _add_interval_ends(self, periods: list[list[dict]]) -> None:
        """Add interval_end to each interval using per-interval interval_length."""
        for period in periods:
            for idx, interval in enumerate(period):
                if idx + 1 < len(period):
                    interval["interval_end"] = period[idx + 1]["interval_start"]
                else:
                    interval["interval_end"] = interval["interval_start"] + timedelta(
                        minutes=interval["interval_length_minute"]
                    )

    def _filter_intervals_today_tomorrow(self, result: list[dict]) -> list[dict]:
        """Filter intervals to only include those from today and tomorrow."""
        today = dt_util.now().date()
        tomorrow = today + timedelta(days=1)
        return [
            interval
            for interval in result
            if interval.get("interval_start") and today <= interval["interval_start"].date() <= tomorrow
        ]

    def _find_current_or_next_interval(self, filtered_result: list[dict]) -> dict | None:
        """Find the current or next interval from the filtered list."""
        now = dt_util.now()
        for interval in filtered_result:
            start = interval.get("interval_start")
            end = interval.get("interval_end")
            if start and end and start <= now < end:
                return interval.copy()
        for interval in filtered_result:
            start = interval.get("interval_start")
            if start and start > now:
                return interval.copy()
        return None

    def _filter_periods_today_tomorrow(self, periods: list[list[dict]]) -> list[list[dict]]:
        """Filter periods to only those with at least one interval in today or tomorrow."""
        today = dt_util.now().date()
        tomorrow = today + timedelta(days=1)
        return [
            period
            for period in periods
            if any(
                interval.get("interval_start") and today <= interval["interval_start"].date() <= tomorrow
                for interval in period
            )
        ]

    def _get_price_intervals_attributes(self, *, reverse_sort: bool) -> dict | None:
        """Get price interval attributes with support for 15-minute intervals and period grouping."""
        if not self.coordinator.data:
            return None
        price_info = self.coordinator.data["priceInfo"]
        yesterday_prices = price_info.get("yesterday", [])
        today_prices = price_info.get("today", [])
        tomorrow_prices = price_info.get("tomorrow", [])
        all_prices = yesterday_prices + today_prices + tomorrow_prices
        if not all_prices:
            return None
        all_prices.sort(key=lambda p: p["startsAt"])
        intervals_by_day, interval_length_by_day, avg_price_by_day = self._split_intervals_by_day(all_prices)
        ref_prices = self._calculate_reference_prices(intervals_by_day, reverse_sort=reverse_sort)
        flex = self._get_flex_option(
            CONF_BEST_PRICE_FLEX if not reverse_sort else CONF_PEAK_PRICE_FLEX,
            DEFAULT_BEST_PRICE_FLEX if not reverse_sort else DEFAULT_PEAK_PRICE_FLEX,
        )
        periods = self._build_periods(
            all_prices,
            ref_prices,
            interval_length_by_day,
            flex,
            reverse_sort=reverse_sort,
        )
        self._add_interval_ends(periods)
        # Only use periods relevant for today/tomorrow for annotation and attribute calculation
        filtered_periods = self._filter_periods_today_tomorrow(periods)
        # Use the last interval's interval_length for period annotation (approximate)
        result = self._annotate_period_intervals(
            filtered_periods,
            ref_prices,
            avg_price_by_day,
            filtered_periods[-1][-1]["interval_length_minute"] if filtered_periods and filtered_periods[-1] else 60,
        )
        filtered_result = self._filter_intervals_today_tomorrow(result)
        current_interval = self._find_current_or_next_interval(filtered_result)
        attributes = {**current_interval} if current_interval else {}
        attributes["intervals"] = filtered_result
        return attributes

    def _get_price_hours_attributes(self, *, attribute_name: str, reverse_sort: bool) -> dict | None:
        """Get price hours attributes."""
        if not self.coordinator.data:
            return None

        price_info = self.coordinator.data["priceInfo"]

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
