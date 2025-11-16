"""Services for Tibber Prices integration."""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any, Final

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from homeassistant.util import dt as dt_util

from .api import (
    TibberPricesApiClientAuthenticationError,
    TibberPricesApiClientCommunicationError,
    TibberPricesApiClientError,
)
from .const import (
    CONF_PRICE_RATING_THRESHOLD_HIGH,
    CONF_PRICE_RATING_THRESHOLD_LOW,
    DEFAULT_PRICE_RATING_THRESHOLD_HIGH,
    DEFAULT_PRICE_RATING_THRESHOLD_LOW,
    DOMAIN,
    PRICE_LEVEL_CHEAP,
    PRICE_LEVEL_EXPENSIVE,
    PRICE_LEVEL_NORMAL,
    PRICE_LEVEL_VERY_CHEAP,
    PRICE_LEVEL_VERY_EXPENSIVE,
    PRICE_RATING_HIGH,
    PRICE_RATING_LOW,
    PRICE_RATING_NORMAL,
    format_price_unit_minor,
    get_translation,
)
from .sensor.helpers import aggregate_level_data, aggregate_rating_data

APEXCHARTS_YAML_SERVICE_NAME = "get_apexcharts_yaml"
CHARTDATA_SERVICE_NAME = "get_chartdata"
REFRESH_USER_DATA_SERVICE_NAME = "refresh_user_data"
ATTR_DAY: Final = "day"
ATTR_ENTRY_ID: Final = "entry_id"

APEXCHARTS_SERVICE_SCHEMA: Final = vol.Schema(
    {
        vol.Required(ATTR_ENTRY_ID): str,
        vol.Optional("day", default="today"): vol.In(["yesterday", "today", "tomorrow"]),
        vol.Optional("level_type", default="rating_level"): vol.In(["rating_level", "level"]),
    }
)


def _normalize_level_filter(value: list[str] | None) -> list[str] | None:
    """Convert level filter values to uppercase for case-insensitive comparison."""
    if value is None:
        return None
    return [v.upper() for v in value]


def _normalize_rating_level_filter(value: list[str] | None) -> list[str] | None:
    """Convert rating level filter values to uppercase for case-insensitive comparison."""
    if value is None:
        return None
    return [v.upper() for v in value]


CHARTDATA_SERVICE_SCHEMA: Final = vol.Schema(
    {
        vol.Required(ATTR_ENTRY_ID): str,
        vol.Optional(ATTR_DAY): vol.All(vol.Coerce(list), [vol.In(["yesterday", "today", "tomorrow"])]),
        vol.Optional("resolution", default="interval"): vol.In(["interval", "hourly"]),
        vol.Optional("output_format", default="array_of_objects"): vol.In(["array_of_objects", "array_of_arrays"]),
        vol.Optional("array_fields"): str,
        vol.Optional("minor_currency", default=False): bool,
        vol.Optional("round_decimals"): vol.All(vol.Coerce(int), vol.Range(min=0, max=10)),
        vol.Optional("include_level", default=False): bool,
        vol.Optional("include_rating_level", default=False): bool,
        vol.Optional("include_average", default=False): bool,
        vol.Optional("level_filter"): vol.All(
            vol.Coerce(list),
            _normalize_level_filter,
            [
                vol.In(
                    [
                        PRICE_LEVEL_VERY_CHEAP,
                        PRICE_LEVEL_CHEAP,
                        PRICE_LEVEL_NORMAL,
                        PRICE_LEVEL_EXPENSIVE,
                        PRICE_LEVEL_VERY_EXPENSIVE,
                    ]
                )
            ],
        ),
        vol.Optional("rating_level_filter"): vol.All(
            vol.Coerce(list),
            _normalize_rating_level_filter,
            [vol.In([PRICE_RATING_LOW, PRICE_RATING_NORMAL, PRICE_RATING_HIGH])],
        ),
        vol.Optional("insert_nulls", default="none"): vol.In(["none", "segments", "all"]),
        vol.Optional("add_trailing_null", default=False): bool,
        vol.Optional("timestamp_field", default="start_time"): str,
        vol.Optional("price_field", default="price_per_kwh"): str,
        vol.Optional("level_field", default="level"): str,
        vol.Optional("rating_level_field", default="rating_level"): str,
        vol.Optional("average_field", default="average"): str,
        vol.Optional("data_key", default="data"): str,
    }
)

REFRESH_USER_DATA_SERVICE_SCHEMA: Final = vol.Schema(
    {
        vol.Required(ATTR_ENTRY_ID): str,
    }
)

# --- Entry point: Service handler ---


def _aggregate_hourly_exact(  # noqa: PLR0913, PLR0912
    intervals: list[dict],
    timestamp_field: str,
    price_field: str,
    *,
    use_minor_currency: bool = False,
    round_decimals: int | None = None,
    include_level: bool = False,
    include_rating_level: bool = False,
    level_filter: list[str] | None = None,
    rating_level_filter: list[str] | None = None,
    include_average: bool = False,
    level_field: str = "level",
    rating_level_field: str = "rating_level",
    average_field: str = "average",
    day_average: float | None = None,
    threshold_low: float = DEFAULT_PRICE_RATING_THRESHOLD_LOW,
    threshold_high: float = DEFAULT_PRICE_RATING_THRESHOLD_HIGH,
) -> list[dict]:
    """
    Aggregate 15-minute intervals to exact hourly averages.

    Each hour uses exactly 4 intervals (00:00, 00:15, 00:30, 00:45).
    Returns data points at the start of each hour.
    """
    if not intervals:
        return []

    hourly_data = []
    i = 0

    while i < len(intervals):
        interval = intervals[i]
        start_time_str = interval.get("startsAt")

        if not start_time_str:
            i += 1
            continue

        # Parse the timestamp
        start_time = dt_util.parse_datetime(start_time_str)
        if not start_time:
            i += 1
            continue

        # Check if this is the start of an hour (:00)
        if start_time.minute != 0:
            i += 1
            continue

        # Collect 4 intervals for this hour (with optional filtering)
        hour_intervals = []
        hour_interval_data = []  # Complete interval data for aggregation functions
        for j in range(4):
            if i + j < len(intervals):
                interval = intervals[i + j]

                # Apply level filter if specified
                if level_filter is not None and "level" in interval and interval["level"] not in level_filter:
                    continue

                # Apply rating_level filter if specified
                if (
                    rating_level_filter is not None
                    and "rating_level" in interval
                    and interval["rating_level"] not in rating_level_filter
                ):
                    continue

                price = interval.get("total")
                if price is not None:
                    hour_intervals.append(price)
                    hour_interval_data.append(interval)

        # Calculate average if we have data
        if hour_intervals:
            avg_price = sum(hour_intervals) / len(hour_intervals)

            # Convert to minor currency (cents/øre) if requested
            avg_price = round(avg_price * 100, 2) if use_minor_currency else round(avg_price, 4)

            # Apply custom rounding if specified
            if round_decimals is not None:
                avg_price = round(avg_price, round_decimals)

            data_point = {timestamp_field: start_time_str, price_field: avg_price}

            # Add aggregated level using same logic as sensors
            if include_level and hour_interval_data:
                aggregated_level = aggregate_level_data(hour_interval_data)
                if aggregated_level:
                    data_point[level_field] = aggregated_level.upper()  # Convert back to uppercase

            # Add aggregated rating_level using same logic as sensors
            if include_rating_level and hour_interval_data:
                aggregated_rating = aggregate_rating_data(hour_interval_data, threshold_low, threshold_high)
                if aggregated_rating:
                    data_point[rating_level_field] = aggregated_rating.upper()  # Convert back to uppercase

            # Add average if requested
            if include_average and day_average is not None:
                data_point[average_field] = day_average

            hourly_data.append(data_point)

        # Move to next hour (skip 4 intervals)
        i += 4

    return hourly_data


async def _get_chartdata(call: ServiceCall) -> dict[str, Any]:  # noqa: PLR0912, PLR0915, C901
    """Return price data in a simple chart-friendly format similar to Tibber Core integration."""
    hass = call.hass
    entry_id_raw = call.data.get(ATTR_ENTRY_ID)
    if entry_id_raw is None:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="missing_entry_id")
    entry_id: str = str(entry_id_raw)

    days_raw = call.data.get(ATTR_DAY)
    # If no day specified, return all available data (today + tomorrow)
    if days_raw is None:
        days = ["today", "tomorrow"]
    # Convert single string to list for uniform processing
    elif isinstance(days_raw, str):
        days = [days_raw]
    else:
        days = days_raw

    timestamp_field = call.data.get("timestamp_field", "start_time")
    price_field = call.data.get("price_field", "price_per_kwh")
    level_field = call.data.get("level_field", "level")
    rating_level_field = call.data.get("rating_level_field", "rating_level")
    average_field = call.data.get("average_field", "average")
    data_key = call.data.get("data_key", "data")
    resolution = call.data.get("resolution", "interval")
    output_format = call.data.get("output_format", "array_of_objects")
    minor_currency = call.data.get("minor_currency", False)
    round_decimals = call.data.get("round_decimals")
    include_level = call.data.get("include_level", False)
    include_rating_level = call.data.get("include_rating_level", False)
    include_average = call.data.get("include_average", False)
    insert_nulls = call.data.get("insert_nulls", "none")
    add_trailing_null = call.data.get("add_trailing_null", False)
    # Filter values are already normalized to uppercase by schema validators
    level_filter = call.data.get("level_filter")
    rating_level_filter = call.data.get("rating_level_filter")

    # If array_fields is specified, implicitly enable fields that are used
    array_fields_template = call.data.get("array_fields")
    if array_fields_template and output_format == "array_of_arrays":
        if level_field in array_fields_template:
            include_level = True
        if rating_level_field in array_fields_template:
            include_rating_level = True
        if average_field in array_fields_template:
            include_average = True

    _, coordinator, _ = _get_entry_and_data(hass, entry_id)

    # Get thresholds from config for rating aggregation
    threshold_low = coordinator.config_entry.options.get(
        CONF_PRICE_RATING_THRESHOLD_LOW, DEFAULT_PRICE_RATING_THRESHOLD_LOW
    )
    threshold_high = coordinator.config_entry.options.get(
        CONF_PRICE_RATING_THRESHOLD_HIGH, DEFAULT_PRICE_RATING_THRESHOLD_HIGH
    )

    # Get price data for all requested days
    price_info = coordinator.data.get("priceInfo", {})
    chart_data = []

    # Collect all timestamps if insert_nulls='all' (needed to insert NULLs for missing filter matches)
    all_timestamps = set()
    if insert_nulls == "all" and (level_filter or rating_level_filter):
        for day in days:
            day_prices = price_info.get(day, [])
            for interval in day_prices:
                start_time = interval.get("startsAt")
                if start_time:
                    all_timestamps.add(start_time)
        all_timestamps = sorted(all_timestamps)

    # Calculate average if requested
    day_averages = {}
    if include_average:
        for day in days:
            day_prices = price_info.get(day, [])
            if day_prices:
                prices = [p["total"] for p in day_prices if p.get("total") is not None]
                if prices:
                    avg = sum(prices) / len(prices)
                    # Apply same transformations as to regular prices
                    avg = round(avg * 100, 2) if minor_currency else round(avg, 4)
                    if round_decimals is not None:
                        avg = round(avg, round_decimals)
                    day_averages[day] = avg

    for day in days:
        day_prices = price_info.get(day, [])

        if resolution == "interval":
            # Original 15-minute intervals
            if insert_nulls == "all" and (level_filter or rating_level_filter):
                # Mode 'all': Insert NULL for all timestamps where filter doesn't match
                # Build a map of timestamp -> interval for quick lookup
                interval_map = {
                    interval.get("startsAt"): interval for interval in day_prices if interval.get("startsAt")
                }

                # Process all timestamps, filling gaps with NULL
                for start_time in all_timestamps:
                    interval = interval_map.get(start_time)

                    if interval is None:
                        # No data for this timestamp - skip entirely
                        continue

                    price = interval.get("total")
                    if price is None:
                        continue

                    # Check if this interval matches the filter
                    matches_filter = False
                    if level_filter and "level" in interval:
                        matches_filter = interval["level"] in level_filter
                    elif rating_level_filter and "rating_level" in interval:
                        matches_filter = interval["rating_level"] in rating_level_filter

                    # If filter is set but doesn't match, insert NULL price
                    if not matches_filter:
                        price = None
                    elif price is not None:
                        # Convert to minor currency (cents/øre) if requested
                        price = round(price * 100, 2) if minor_currency else round(price, 4)
                        # Apply custom rounding if specified
                        if round_decimals is not None:
                            price = round(price, round_decimals)

                    data_point = {timestamp_field: start_time, price_field: price}

                    # Add level if requested (only when price is not NULL)
                    if include_level and "level" in interval and price is not None:
                        data_point[level_field] = interval["level"]

                    # Add rating_level if requested (only when price is not NULL)
                    if include_rating_level and "rating_level" in interval and price is not None:
                        data_point[rating_level_field] = interval["rating_level"]

                    # Add average if requested
                    if include_average and day in day_averages:
                        data_point[average_field] = day_averages[day]

                    chart_data.append(data_point)
            elif insert_nulls == "segments" and (level_filter or rating_level_filter):
                # Mode 'segments': Add NULL points at segment boundaries for clean gaps
                # Determine which field to check based on filter type
                filter_field = "rating_level" if rating_level_filter else "level"
                filter_values = rating_level_filter if rating_level_filter else level_filter

                for i in range(len(day_prices) - 1):
                    interval = day_prices[i]
                    next_interval = day_prices[i + 1]

                    start_time = interval.get("startsAt")
                    price = interval.get("total")
                    next_start_time = next_interval.get("startsAt")

                    if start_time is None or price is None:
                        continue

                    interval_value = interval.get(filter_field)
                    next_value = next_interval.get(filter_field)

                    # Check if current interval matches filter
                    if interval_value in filter_values:
                        # Convert price
                        converted_price = round(price * 100, 2) if minor_currency else round(price, 4)
                        if round_decimals is not None:
                            converted_price = round(converted_price, round_decimals)

                        # Add current point
                        data_point = {timestamp_field: start_time, price_field: converted_price}

                        if include_level and "level" in interval:
                            data_point[level_field] = interval["level"]
                        if include_rating_level and "rating_level" in interval:
                            data_point[rating_level_field] = interval["rating_level"]
                        if include_average and day in day_averages:
                            data_point[average_field] = day_averages[day]

                        chart_data.append(data_point)

                        # Check if next interval is different level (segment boundary)
                        if next_value != interval_value:
                            # Hold current price until next timestamp (stepline effect)
                            hold_point = {timestamp_field: next_start_time, price_field: converted_price}
                            if include_level and "level" in interval:
                                hold_point[level_field] = interval["level"]
                            if include_rating_level and "rating_level" in interval:
                                hold_point[rating_level_field] = interval["rating_level"]
                            if include_average and day in day_averages:
                                hold_point[average_field] = day_averages[day]
                            chart_data.append(hold_point)

                            # Add NULL point to create gap
                            null_point = {timestamp_field: next_start_time, price_field: None}
                            chart_data.append(null_point)

                # Handle last interval of the day - extend to midnight
                if day_prices:
                    last_interval = day_prices[-1]
                    last_start_time = last_interval.get("startsAt")
                    last_price = last_interval.get("total")
                    last_value = last_interval.get(filter_field)

                    if last_start_time and last_price is not None and last_value in filter_values:
                        # Parse timestamp and calculate midnight of next day
                        last_dt = dt_util.parse_datetime(last_start_time)
                        if last_dt:
                            last_dt = dt_util.as_local(last_dt)
                            # Calculate next day at 00:00
                            next_day = last_dt.replace(hour=0, minute=0, second=0, microsecond=0)
                            next_day = next_day + timedelta(days=1)
                            midnight_timestamp = next_day.isoformat()

                            # Try to get real price from tomorrow's first interval
                            next_day_name = None
                            if day == "yesterday":
                                next_day_name = "today"
                            elif day == "today":
                                next_day_name = "tomorrow"
                            # For "tomorrow", we don't have a "day after tomorrow"

                            midnight_price = None
                            midnight_interval = None

                            if next_day_name:
                                next_day_prices = price_info.get(next_day_name, [])
                                if next_day_prices:
                                    first_next = next_day_prices[0]
                                    first_next_value = first_next.get(filter_field)
                                    # Only use tomorrow's price if it matches the same filter
                                    if first_next_value == last_value:
                                        midnight_price = first_next.get("total")
                                        midnight_interval = first_next

                            # Fallback: use last interval's price if no tomorrow data or different level
                            if midnight_price is None:
                                midnight_price = last_price
                                midnight_interval = last_interval

                            # Convert price
                            converted_price = (
                                round(midnight_price * 100, 2) if minor_currency else round(midnight_price, 4)
                            )
                            if round_decimals is not None:
                                converted_price = round(converted_price, round_decimals)

                            # Add point at midnight with appropriate price (extends graph to end of day)
                            end_point = {timestamp_field: midnight_timestamp, price_field: converted_price}
                            if midnight_interval is not None:
                                if include_level and "level" in midnight_interval:
                                    end_point[level_field] = midnight_interval["level"]
                                if include_rating_level and "rating_level" in midnight_interval:
                                    end_point[rating_level_field] = midnight_interval["rating_level"]
                            if include_average and day in day_averages:
                                end_point[average_field] = day_averages[day]
                            chart_data.append(end_point)
            else:
                # Mode 'none' (default): Only return matching intervals, no NULL insertion
                for interval in day_prices:
                    start_time = interval.get("startsAt")
                    price = interval.get("total")

                    if start_time is not None and price is not None:
                        # Apply level filter if specified
                        if level_filter is not None and "level" in interval and interval["level"] not in level_filter:
                            continue

                        # Apply rating_level filter if specified
                        if (
                            rating_level_filter is not None
                            and "rating_level" in interval
                            and interval["rating_level"] not in rating_level_filter
                        ):
                            continue

                        # Convert to minor currency (cents/øre) if requested
                        price = round(price * 100, 2) if minor_currency else round(price, 4)

                        # Apply custom rounding if specified
                        if round_decimals is not None:
                            price = round(price, round_decimals)

                        data_point = {timestamp_field: start_time, price_field: price}

                        # Add level if requested
                        if include_level and "level" in interval:
                            data_point[level_field] = interval["level"]

                        # Add rating_level if requested
                        if include_rating_level and "rating_level" in interval:
                            data_point[rating_level_field] = interval["rating_level"]

                        # Add average if requested
                        if include_average and day in day_averages:
                            data_point[average_field] = day_averages[day]

                        chart_data.append(data_point)

        elif resolution == "hourly":
            # Hourly averages (4 intervals per hour: :00, :15, :30, :45)
            chart_data.extend(
                _aggregate_hourly_exact(
                    day_prices,
                    timestamp_field,
                    price_field,
                    use_minor_currency=minor_currency,
                    round_decimals=round_decimals,
                    include_level=include_level,
                    include_rating_level=include_rating_level,
                    level_filter=level_filter,
                    rating_level_filter=rating_level_filter,
                    include_average=include_average,
                    level_field=level_field,
                    rating_level_field=rating_level_field,
                    average_field=average_field,
                    day_average=day_averages.get(day),
                    threshold_low=threshold_low,
                    threshold_high=threshold_high,
                )
            )

    # Convert to array of arrays format if requested
    if output_format == "array_of_arrays":
        array_fields_template = call.data.get("array_fields")

        # Default: nur timestamp und price
        if not array_fields_template:
            array_fields_template = f"{{{timestamp_field}}}, {{{price_field}}}"

        # Parse template to extract field names
        field_pattern = re.compile(r"\{([^}]+)\}")
        field_names = field_pattern.findall(array_fields_template)

        if not field_names:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_array_fields",
                translation_placeholders={"template": array_fields_template},
            )

        # Convert to [[field1, field2, ...], ...] format
        points = []
        for item in chart_data:
            row = []
            for field_name in field_names:
                # Get value from item, or None if field doesn't exist
                value = item.get(field_name)
                row.append(value)
            points.append(row)

        # Add final null point for stepline rendering if requested
        # (some chart libraries need this to prevent extrapolation to viewport edge)
        if add_trailing_null and points:
            null_row = [points[-1][0]] + [None] * (len(field_names) - 1)
            points.append(null_row)

        return {data_key: points}

    # Add trailing null point for array_of_objects format if requested
    if add_trailing_null and chart_data:
        # Create a null point with only timestamp from last item, all other fields as None
        last_item = chart_data[-1]
        null_point = {timestamp_field: last_item.get(timestamp_field)}
        # Set all other potential fields to None
        for field in [price_field, level_field, rating_level_field, average_field]:
            if field in last_item:
                null_point[field] = None
        chart_data.append(null_point)

    return {data_key: chart_data}


def _get_level_translation(level_key: str, level_type: str, language: str) -> str:
    """Get translated name for a price level or rating level."""
    level_key_lower = level_key.lower()
    # Use correct translation key based on level_type
    if level_type == "rating_level":
        name = get_translation(["selector", "rating_level_filter", "options", level_key_lower], language)
    else:
        name = get_translation(["selector", "level_filter", "options", level_key_lower], language)
    # Fallback to original key if translation not found
    return name or level_key


async def _get_apexcharts_yaml(call: ServiceCall) -> dict[str, Any]:
    """Return a YAML snippet for an ApexCharts card using the get_apexcharts_data service for each level."""
    hass = call.hass
    entry_id_raw = call.data.get(ATTR_ENTRY_ID)
    if entry_id_raw is None:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="missing_entry_id")
    entry_id: str = str(entry_id_raw)

    day = call.data.get("day", "today")
    level_type = call.data.get("level_type", "rating_level")

    # Get user's language from hass config
    user_language = hass.config.language or "en"

    # Get coordinator to access price data (for currency)
    _, coordinator, _ = _get_entry_and_data(hass, entry_id)
    price_info = coordinator.data.get("priceInfo", {})
    currency = price_info.get("currency", "EUR")
    price_unit = format_price_unit_minor(currency)

    # Get a sample entity_id for the series (first sensor from this entry)
    entity_registry = async_get_entity_registry(hass)
    sample_entity = None
    for entity in entity_registry.entities.values():
        if entity.config_entry_id == entry_id and entity.domain == "sensor":
            sample_entity = entity.entity_id
            break

    if level_type == "rating_level":
        series_levels = [
            (PRICE_RATING_LOW, "#2ecc71"),
            (PRICE_RATING_NORMAL, "#f1c40f"),
            (PRICE_RATING_HIGH, "#e74c3c"),
        ]
    else:
        series_levels = [
            (PRICE_LEVEL_VERY_CHEAP, "#2ecc71"),
            (PRICE_LEVEL_CHEAP, "#27ae60"),
            (PRICE_LEVEL_NORMAL, "#f1c40f"),
            (PRICE_LEVEL_EXPENSIVE, "#e67e22"),
            (PRICE_LEVEL_VERY_EXPENSIVE, "#e74c3c"),
        ]
    series = []
    for level_key, color in series_levels:
        # Get translated name for the level using helper function
        name = _get_level_translation(level_key, level_type, user_language)
        # Use server-side insert_nulls='segments' for clean gaps
        if level_type == "rating_level":
            filter_param = f"rating_level_filter: ['{level_key}']"
        else:
            filter_param = f"level_filter: ['{level_key}']"

        data_generator = (
            f"const response = await hass.callWS({{ "
            f"type: 'call_service', "
            f"domain: 'tibber_prices', "
            f"service: 'get_chartdata', "
            f"return_response: true, "
            f"service_data: {{ entry_id: '{entry_id}', day: ['{day}'], {filter_param}, "
            f"output_format: 'array_of_arrays', insert_nulls: 'segments', minor_currency: true }} }}); "
            f"return response.response.data;"
        )
        # Only show extremas for HIGH and LOW levels (not NORMAL)
        show_extremas = level_key != "NORMAL"
        series.append(
            {
                "entity": sample_entity or "sensor.tibber_prices",
                "name": name,
                "type": "area",
                "color": color,
                "yaxis_id": "price",
                "show": {"extremas": show_extremas, "legend_value": False},
                "data_generator": data_generator,
                "stroke_width": 1,
            }
        )

    # Get translated title based on level_type
    title_key = "title_rating_level" if level_type == "rating_level" else "title_level"
    title = get_translation(["apexcharts", title_key], user_language) or (
        "Price Phases Daily Progress" if level_type == "rating_level" else "Price Level"
    )

    # Add translated day to title
    day_translated = get_translation(["selector", "day", "options", day], user_language) or day.capitalize()
    title = f"{title} - {day_translated}"

    # Configure span based on selected day
    if day == "yesterday":
        span_config = {"start": "day", "offset": "-1d"}
    elif day == "tomorrow":
        span_config = {"start": "day", "offset": "+1d"}
    else:  # today
        span_config = {"start": "day"}

    return {
        "type": "custom:apexcharts-card",
        "update_interval": "5m",
        "span": span_config,
        "header": {
            "show": True,
            "title": title,
            "show_states": False,
        },
        "apex_config": {
            "chart": {
                "animations": {"enabled": False},
                "toolbar": {"show": True, "tools": {"zoom": True, "pan": True}},
                "zoom": {"enabled": True},
            },
            "stroke": {"curve": "stepline", "width": 2},
            "fill": {
                "type": "gradient",
                "opacity": 0.4,
                "gradient": {
                    "shade": "dark",
                    "type": "vertical",
                    "shadeIntensity": 0.5,
                    "opacityFrom": 0.7,
                    "opacityTo": 0.2,
                },
            },
            "dataLabels": {"enabled": False},
            "tooltip": {
                "x": {"format": "HH:mm"},
                "y": {"title": {"formatter": f"function() {{ return '{price_unit}'; }}"}},
            },
            "legend": {
                "show": True,
                "position": "top",
                "horizontalAlign": "left",
                "markers": {"radius": 2},
            },
            "grid": {
                "show": True,
                "borderColor": "#40475D",
                "strokeDashArray": 4,
                "xaxis": {"lines": {"show": True}},
                "yaxis": {"lines": {"show": True}},
            },
            "markers": {"size": 0},
        },
        "yaxis": [
            {
                "id": "price",
                "decimals": 2,
                "min": 0,
                "apex_config": {"title": {"text": price_unit}},
            },
        ],
        "now": {"show": True, "color": "#8e24aa", "label": "🕒 LIVE"},
        "all_series_config": {
            "stroke_width": 1,
            "group_by": {"func": "raw", "duration": "15min"},
        },
        "series": series,
    }


async def _refresh_user_data(call: ServiceCall) -> dict[str, Any]:
    """Refresh user data for a specific config entry and return updated information."""
    entry_id = call.data.get(ATTR_ENTRY_ID)
    hass = call.hass

    if not entry_id:
        return {
            "success": False,
            "message": "Entry ID is required",
        }

    # Get the entry and coordinator
    try:
        _, coordinator, _ = _get_entry_and_data(hass, entry_id)
    except ServiceValidationError as ex:
        return {
            "success": False,
            "message": f"Invalid entry ID: {ex}",
        }

    # Force refresh user data using the public method
    try:
        updated = await coordinator.refresh_user_data()
    except (
        TibberPricesApiClientAuthenticationError,
        TibberPricesApiClientCommunicationError,
        TibberPricesApiClientError,
    ) as ex:
        return {
            "success": False,
            "message": f"API error refreshing user data: {ex!s}",
        }
    else:
        if updated:
            user_profile = coordinator.get_user_profile()
            homes = coordinator.get_user_homes()

            return {
                "success": True,
                "message": "User data refreshed successfully",
                "user_profile": user_profile,
                "homes_count": len(homes),
                "homes": homes,
                "last_updated": user_profile.get("last_updated"),
            }
        return {
            "success": False,
            "message": "User data was already up to date",
        }


# --- Helpers ---


def _get_entry_and_data(hass: HomeAssistant, entry_id: str) -> tuple[Any, Any, dict]:
    """Validate entry and extract coordinator and data."""
    if not entry_id:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="missing_entry_id")
    entry = next(
        (e for e in hass.config_entries.async_entries(DOMAIN) if e.entry_id == entry_id),
        None,
    )
    if not entry or not hasattr(entry, "runtime_data") or not entry.runtime_data:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="invalid_entry_id")
    coordinator = entry.runtime_data.coordinator
    data = coordinator.data or {}
    return entry, coordinator, data


# --- Service registration ---


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Tibber Prices integration."""
    hass.services.async_register(
        DOMAIN,
        APEXCHARTS_YAML_SERVICE_NAME,
        _get_apexcharts_yaml,
        schema=APEXCHARTS_SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        CHARTDATA_SERVICE_NAME,
        _get_chartdata,
        schema=CHARTDATA_SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        REFRESH_USER_DATA_SERVICE_NAME,
        _refresh_user_data,
        schema=REFRESH_USER_DATA_SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
