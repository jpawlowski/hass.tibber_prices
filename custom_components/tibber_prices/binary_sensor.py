"""Binary sensor platform for tibber_prices."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

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
from .sensor import find_price_data_for_interval

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import TibberPricesDataUpdateCoordinator
    from .data import TibberPricesConfigEntry

from .const import (
    CONF_BEST_PRICE_FLEX,
    CONF_BEST_PRICE_MIN_DISTANCE_FROM_AVG,
    CONF_BEST_PRICE_MIN_PERIOD_LENGTH,
    CONF_EXTENDED_DESCRIPTIONS,
    CONF_PEAK_PRICE_FLEX,
    CONF_PEAK_PRICE_MIN_DISTANCE_FROM_AVG,
    CONF_PEAK_PRICE_MIN_PERIOD_LENGTH,
    DEFAULT_BEST_PRICE_FLEX,
    DEFAULT_BEST_PRICE_MIN_DISTANCE_FROM_AVG,
    DEFAULT_BEST_PRICE_MIN_PERIOD_LENGTH,
    DEFAULT_EXTENDED_DESCRIPTIONS,
    DEFAULT_PEAK_PRICE_FLEX,
    DEFAULT_PEAK_PRICE_MIN_DISTANCE_FROM_AVG,
    DEFAULT_PEAK_PRICE_MIN_PERIOD_LENGTH,
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

        # Cache for expensive period calculations to avoid recalculating twice
        # (once for is_on, once for attributes)
        self._period_cache: dict[str, Any] = {}
        self._cache_key: str = ""

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
        # Invalidate cache when data potentially changes
        self._cache_key = ""
        self._period_cache = {}
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

    def _generate_cache_key(self, *, reverse_sort: bool) -> str:
        """
        Generate a cache key based on coordinator data and config options.

        This ensures we recalculate when data or configuration changes,
        but reuse cached results for multiple property accesses.
        """
        if not self.coordinator.data:
            return ""

        # Include timestamp to invalidate when data changes
        timestamp = self.coordinator.data.get("timestamp", "")

        # Include relevant config options that affect period calculation
        options = self.coordinator.config_entry.options
        data = self.coordinator.config_entry.data

        if reverse_sort:
            flex = options.get(CONF_PEAK_PRICE_FLEX, data.get(CONF_PEAK_PRICE_FLEX, DEFAULT_PEAK_PRICE_FLEX))
            min_dist = options.get(
                CONF_PEAK_PRICE_MIN_DISTANCE_FROM_AVG,
                data.get(CONF_PEAK_PRICE_MIN_DISTANCE_FROM_AVG, DEFAULT_PEAK_PRICE_MIN_DISTANCE_FROM_AVG),
            )
            min_len = options.get(
                CONF_PEAK_PRICE_MIN_PERIOD_LENGTH,
                data.get(CONF_PEAK_PRICE_MIN_PERIOD_LENGTH, DEFAULT_PEAK_PRICE_MIN_PERIOD_LENGTH),
            )
        else:
            flex = options.get(CONF_BEST_PRICE_FLEX, data.get(CONF_BEST_PRICE_FLEX, DEFAULT_BEST_PRICE_FLEX))
            min_dist = options.get(
                CONF_BEST_PRICE_MIN_DISTANCE_FROM_AVG,
                data.get(CONF_BEST_PRICE_MIN_DISTANCE_FROM_AVG, DEFAULT_BEST_PRICE_MIN_DISTANCE_FROM_AVG),
            )
            min_len = options.get(
                CONF_BEST_PRICE_MIN_PERIOD_LENGTH,
                data.get(CONF_BEST_PRICE_MIN_PERIOD_LENGTH, DEFAULT_BEST_PRICE_MIN_PERIOD_LENGTH),
            )

        return f"{timestamp}_{reverse_sort}_{flex}_{min_dist}_{min_len}"

    def _get_flex_option(self, option_key: str, default: float) -> float:
        """
        Get a float option from config entry.

        Converts percentage values to decimal fractions.
        - CONF_BEST_PRICE_FLEX: positive 0-100 → 0.0-1.0
        - CONF_PEAK_PRICE_FLEX: negative -100 to 0 → -1.0 to 0.0

        Args:
            option_key: The config key (CONF_BEST_PRICE_FLEX or CONF_PEAK_PRICE_FLEX)
            default: Default value to use if not found

        Returns:
            Value converted to decimal fraction (e.g., 5 → 0.05, -5 → -0.05)

        """
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

        price_info = self.coordinator.data.get("priceInfo", {})
        today_prices = price_info.get("today", [])

        if not today_prices:
            return None

        now = dt_util.now()

        current_interval_data = find_price_data_for_interval({"today": today_prices}, now)

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
        # Extract and keep internal interval fields for logic (with _ prefix)
        interval_start = interval_copy.pop("interval_start", None)
        interval_end = interval_copy.pop("interval_end", None)
        # Remove other interval_* fields that are no longer needed
        interval_copy.pop("interval_hour", None)
        interval_copy.pop("interval_minute", None)
        interval_copy.pop("interval_time", None)
        # Remove startsAt - not needed anymore
        interval_copy.pop("startsAt", None)
        price_raw = interval_copy.pop("price", None)
        new_interval = {
            "period_start": annotation_ctx["period_start"],
            "period_end": annotation_ctx["period_end"],
            "hour": annotation_ctx["period_start_hour"],
            "minute": annotation_ctx["period_start_minute"],
            "time": annotation_ctx["period_start_time"],
            "duration_minutes": annotation_ctx["period_length"],
            "remaining_minutes_after_interval": interval_remaining * MINUTES_PER_INTERVAL,
            "periods_total": annotation_ctx["period_count"],
            "periods_remaining": annotation_ctx["periods_remaining"],
            "period_position": annotation_ctx["period_idx"],
            "price": round(price_raw * 100, 2) if price_raw is not None else None,
            # Keep internal fields for logic (state checks, filtering)
            "_interval_start": interval_start,
            "_interval_end": interval_end,
        }
        new_interval.update(interval_copy)

        # Add price_diff_from_min for best_price_period
        if annotation_ctx.get("diff_key") == "price_diff_from_min":
            price_diff = price_raw - annotation_ctx["ref_price"]
            new_interval["price_diff_from_min"] = round(price_diff * 100, 2)
            # Calculate percent difference from min price
            price_diff_percent = (
                ((price_raw - annotation_ctx["ref_price"]) / annotation_ctx["ref_price"]) * 100
                if annotation_ctx["ref_price"] != 0
                else 0.0
            )
            new_interval["price_diff_from_min_" + PERCENTAGE] = round(price_diff_percent, 2)

        # Add price_diff_from_max for peak_price_period
        elif annotation_ctx.get("diff_key") == "price_diff_from_max":
            price_diff = price_raw - annotation_ctx["ref_price"]
            new_interval["price_diff_from_max"] = round(price_diff * 100, 2)
            # Calculate percent difference from max price
            price_diff_percent = (
                ((price_raw - annotation_ctx["ref_price"]) / annotation_ctx["ref_price"]) * 100
                if annotation_ctx["ref_price"] != 0
                else 0.0
            )
            new_interval["price_diff_from_max_" + PERCENTAGE] = round(price_diff_percent, 2)

        return new_interval

    def _annotate_period_intervals(
        self,
        periods: list[list[dict]],
        ref_prices: dict,
        avg_price_by_day: dict,
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
            diff_pct_key = "price_diff_from_min_" + PERCENTAGE
        elif reference_type == "max":
            diff_key = "price_diff_from_max"
            diff_pct_key = "price_diff_from_max_" + PERCENTAGE
        else:
            diff_key = "price_diff"
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
            period_length = interval_count * MINUTES_PER_INTERVAL
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
                    "period_count": period_count,
                    "periods_remaining": periods_remaining,
                    "period_idx": period_idx,
                    "ref_price": ref_price,
                    "avg_price": avg_price,
                    "diff_key": diff_key,
                    "diff_pct_key": diff_pct_key,
                }
                new_interval = self._annotate_single_interval(
                    interval,
                    annotation_ctx,
                )
                result.append(new_interval)
        return result

    def _split_intervals_by_day(self, all_prices: list[dict]) -> tuple[dict, dict]:
        """Split intervals by day and calculate average price per day."""
        intervals_by_day: dict = {}
        avg_price_by_day: dict = {}
        for price_data in all_prices:
            dt = dt_util.parse_datetime(price_data["startsAt"])
            if dt is None:
                continue
            date = dt.date()
            intervals_by_day.setdefault(date, []).append(price_data)
        for date, intervals in intervals_by_day.items():
            avg_price_by_day[date] = sum(float(p["total"]) for p in intervals) / len(intervals)
        return intervals_by_day, avg_price_by_day

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
        price_context: dict,
        *,
        reverse_sort: bool,
    ) -> list[list[dict]]:
        """
        Build periods, allowing periods to cross midnight (day boundary).

        Strictly enforce flex threshold by percent diff, matching attribute calculation.
        Additionally enforces:
        1. Cap at daily average to prevent overlap between best and peak periods
        2. Minimum distance from average to ensure meaningful price difference

        Args:
            all_prices: All price data points
            price_context: Dict with ref_prices, avg_prices, flex, and min_distance_from_avg
            reverse_sort: True for peak price (descending), False for best price (ascending)

        Returns:
            List of periods, each period is a list of interval dicts

        """
        ref_prices = price_context["ref_prices"]
        avg_prices = price_context["avg_prices"]
        flex = price_context["flex"]
        min_distance_from_avg = price_context["min_distance_from_avg"]

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
            avg_price = avg_prices[date]
            price = float(price_data["total"])
            percent_diff = ((price - ref_price) / ref_price) * 100 if ref_price != 0 else 0.0
            percent_diff = round(percent_diff, 2)
            # For best price (flex >= 0): percent_diff <= flex*100 (prices up to flex% above reference)
            # For peak price (flex <= 0): percent_diff >= flex*100 (prices down to |flex|% below reference)
            in_flex = percent_diff <= flex * 100 if not reverse_sort else percent_diff >= flex * 100
            # Cap at daily average to prevent overlap between best and peak periods
            # Best price: only prices below average
            # Peak price: only prices above average
            within_avg_boundary = price <= avg_price if not reverse_sort else price >= avg_price
            # Enforce minimum distance from average (in percentage terms)
            # Best price: price must be at least min_distance_from_avg% below average
            # Peak price: price must be at least min_distance_from_avg% above average
            if not reverse_sort:
                # Best price: price <= avg * (1 - min_distance_from_avg/100)
                min_distance_threshold = avg_price * (1 - min_distance_from_avg / 100)
                meets_min_distance = price <= min_distance_threshold
            else:
                # Peak price: price >= avg * (1 + min_distance_from_avg/100)
                min_distance_threshold = avg_price * (1 + min_distance_from_avg / 100)
                meets_min_distance = price >= min_distance_threshold
            # Split period if day changes
            if last_ref_date is not None and date != last_ref_date and current_period:
                periods.append(current_period)
                current_period = []
            last_ref_date = date
            if in_flex and within_avg_boundary and meets_min_distance:
                current_period.append(
                    {
                        "interval_hour": starts_at.hour,
                        "interval_minute": starts_at.minute,
                        "interval_time": f"{starts_at.hour:02d}:{starts_at.minute:02d}",
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

    def _filter_periods_by_min_length(self, periods: list[list[dict]], *, reverse_sort: bool) -> list[list[dict]]:
        """
        Filter periods to only include those meeting the minimum length requirement.

        Args:
            periods: List of periods (each period is a list of interval dicts)
            reverse_sort: True for peak price, False for best price

        Returns:
            Filtered list of periods that meet minimum length requirement

        """
        options = self.coordinator.config_entry.options
        data = self.coordinator.config_entry.data

        # Use appropriate config based on sensor type
        if reverse_sort:  # Peak price
            conf_key = CONF_PEAK_PRICE_MIN_PERIOD_LENGTH
            default = DEFAULT_PEAK_PRICE_MIN_PERIOD_LENGTH
        else:  # Best price
            conf_key = CONF_BEST_PRICE_MIN_PERIOD_LENGTH
            default = DEFAULT_BEST_PRICE_MIN_PERIOD_LENGTH

        min_period_length = options.get(conf_key, data.get(conf_key, default))

        # Convert minutes to number of 15-minute intervals
        min_intervals = min_period_length // MINUTES_PER_INTERVAL

        # Filter out periods that are too short
        return [period for period in periods if len(period) >= min_intervals]

    def _merge_adjacent_periods_at_midnight(self, periods: list[list[dict]]) -> list[list[dict]]:
        """
        Merge adjacent periods that meet at midnight.

        When two periods are detected separately for today and tomorrow due to different
        daily average prices, but they are directly adjacent at midnight, merge them into
        a single period for better user experience.

        Args:
            periods: List of periods (each period is a list of interval dicts)

        Returns:
            List of periods with adjacent midnight periods merged

        """
        if not periods:
            return periods

        merged = []
        i = 0

        while i < len(periods):
            current_period = periods[i]

            # Check if there's a next period and if they meet at midnight
            if i + 1 < len(periods):
                next_period = periods[i + 1]

                # Get the last interval of current period and first interval of next period
                last_interval = current_period[-1]
                first_interval = next_period[0]

                last_start = last_interval.get("interval_start")
                next_start = first_interval.get("interval_start")

                # Check if they are adjacent (15 minutes apart) and cross midnight
                if last_start and next_start:
                    time_diff = next_start - last_start
                    last_date = last_start.date()
                    next_date = next_start.date()

                    # If they are 15 minutes apart and on different days (crossing midnight)
                    if time_diff == timedelta(minutes=MINUTES_PER_INTERVAL) and next_date > last_date:
                        # Merge the two periods
                        merged_period = current_period + next_period
                        merged.append(merged_period)
                        i += 2  # Skip both periods as we've merged them
                        continue

            # If no merge happened, just add the current period
            merged.append(current_period)
            i += 1

        return merged

    def _add_interval_ends(self, periods: list[list[dict]]) -> None:
        """Add interval_end to each interval using per-interval interval_length."""
        for period in periods:
            for idx, interval in enumerate(period):
                if idx + 1 < len(period):
                    interval["interval_end"] = period[idx + 1]["interval_start"]
                else:
                    interval["interval_end"] = interval["interval_start"] + timedelta(minutes=MINUTES_PER_INTERVAL)

    def _filter_intervals_today_tomorrow(self, result: list[dict]) -> list[dict]:
        """Filter intervals to only include those from today and tomorrow."""
        today = dt_util.now().date()
        tomorrow = today + timedelta(days=1)
        return [
            interval
            for interval in result
            if interval.get("_interval_start") and today <= interval["_interval_start"].date() <= tomorrow
        ]

    def _find_current_or_next_interval(self, filtered_result: list[dict]) -> dict | None:
        """Find the current or next interval from the filtered list."""
        now = dt_util.now()
        for interval in filtered_result:
            start = interval.get("_interval_start")
            end = interval.get("_interval_end")
            if start and end and start <= now < end:
                return interval.copy()
        for interval in filtered_result:
            start = interval.get("_interval_start")
            if start and start > now:
                return interval.copy()
        return None

    def _filter_periods_today_tomorrow(self, periods: list[list[dict]]) -> list[list[dict]]:
        """
        Filter periods to include those that are currently active or in the future.

        This includes periods that started yesterday but are still active now (crossing midnight),
        as well as periods happening today or tomorrow. We don't want to show all past periods
        from yesterday, only those that extend into today.
        """
        now = dt_util.now()
        today = now.date()
        tomorrow = today + timedelta(days=1)

        filtered = []
        for period in periods:
            if not period:
                continue

            # Get the period's end time (last interval's end)
            last_interval = period[-1]
            period_end = last_interval.get("interval_end")

            # Get the period's start time (first interval's start)
            first_interval = period[0]
            period_start = first_interval.get("interval_start")

            if not period_end or not period_start:
                continue

            # Include period if:
            # 1. It's still active (ends in the future), OR
            # 2. It has intervals today or tomorrow
            if period_end > now or any(
                interval.get("interval_start") and today <= interval["interval_start"].date() <= tomorrow
                for interval in period
            ):
                filtered.append(period)

        return filtered

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
                # Copy all attributes from the period summary
                attributes = {"timestamp": timestamp}
                attributes.update(current_period_summary)

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

                attributes["periods"] = periods_summary
                attributes["intervals_count"] = len(filtered_result)
                return attributes

            # Fallback if current period not found in summary
            return {
                "timestamp": timestamp,
                "periods": periods_summary,
                "intervals_count": len(filtered_result),
            }

        # No periods found
        return {
            "timestamp": timestamp,
            "periods": [],
            "intervals_count": 0,
        }

    def _get_price_intervals_attributes(self, *, reverse_sort: bool) -> dict | None:
        """
        Get price interval attributes with caching to avoid expensive recalculation.

        Uses a cache key based on coordinator data timestamp and config options.
        Returns simplified attributes without the full intervals list to reduce payload.
        """
        # Check cache first
        cache_key = self._generate_cache_key(reverse_sort=reverse_sort)
        if cache_key and cache_key == self._cache_key and self._period_cache:
            return self._period_cache

        # Cache miss - perform expensive calculation
        if not self.coordinator.data:
            return None

        price_info = self.coordinator.data.get("priceInfo", {})
        yesterday_prices = price_info.get("yesterday", [])
        today_prices = price_info.get("today", [])
        tomorrow_prices = price_info.get("tomorrow", [])
        all_prices = yesterday_prices + today_prices + tomorrow_prices

        if not all_prices:
            return None

        all_prices.sort(key=lambda p: p["startsAt"])
        intervals_by_day, avg_price_by_day = self._split_intervals_by_day(all_prices)
        ref_prices = self._calculate_reference_prices(intervals_by_day, reverse_sort=reverse_sort)

        flex = self._get_flex_option(
            CONF_BEST_PRICE_FLEX if not reverse_sort else CONF_PEAK_PRICE_FLEX,
            DEFAULT_BEST_PRICE_FLEX if not reverse_sort else DEFAULT_PEAK_PRICE_FLEX,
        )
        min_distance_from_avg = self._get_flex_option(
            CONF_BEST_PRICE_MIN_DISTANCE_FROM_AVG if not reverse_sort else CONF_PEAK_PRICE_MIN_DISTANCE_FROM_AVG,
            DEFAULT_BEST_PRICE_MIN_DISTANCE_FROM_AVG if not reverse_sort else DEFAULT_PEAK_PRICE_MIN_DISTANCE_FROM_AVG,
        )

        price_context = {
            "ref_prices": ref_prices,
            "avg_prices": avg_price_by_day,
            "flex": flex,
            "min_distance_from_avg": min_distance_from_avg,
        }

        periods = self._build_periods(all_prices, price_context, reverse_sort=reverse_sort)
        periods = self._filter_periods_by_min_length(periods, reverse_sort=reverse_sort)
        periods = self._merge_adjacent_periods_at_midnight(periods)
        self._add_interval_ends(periods)

        filtered_periods = self._filter_periods_today_tomorrow(periods)

        # Simplified annotation - only annotate enough to find current interval and provide summary
        result = self._annotate_period_intervals(
            filtered_periods,
            ref_prices,
            avg_price_by_day,
        )

        filtered_result = self._filter_intervals_today_tomorrow(result)
        current_interval = self._find_current_or_next_interval(filtered_result)

        if not current_interval and filtered_result:
            current_interval = filtered_result[0]

        # Build periods array first
        periods_summary = self._build_periods_summary(filtered_result) if filtered_result else []

        # Build final attributes using helper method
        attributes = self._build_final_attributes(current_interval, periods_summary, filtered_result)

        # Cache the result (with internal fields intact)
        self._cache_key = cache_key
        self._period_cache = attributes

        return attributes

    def _build_periods_summary(self, intervals: list[dict]) -> list[dict]:
        """
        Build a summary of periods with consistent attribute structure.

        Returns a list of period summaries with the same attributes as top-level,
        making the structure predictable and easy to use in automations.
        """
        if not intervals:
            return []

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

            # Use same attribute names as top-level for consistency
            summary = {
                "start": first.get("period_start"),
                "end": first.get("period_end"),
                "hour": first.get("hour"),
                "minute": first.get("minute"),
                "time": first.get("time"),
                "duration_minutes": first.get("duration_minutes"),
                "periods_total": first.get("periods_total"),
                "periods_remaining": first.get("periods_remaining"),
                "period_position": first.get("period_position"),
                "intervals_count": len(period_intervals),
                "price_avg": round(sum(prices) / len(prices), 2) if prices else 0,
                "price_min": round(min(prices), 2) if prices else 0,
                "price_max": round(max(prices), 2) if prices else 0,
            }

            # Add price_diff attributes if present
            self._add_price_diff_for_period(summary, period_intervals, first)

            summaries.append(summary)

        return summaries

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
