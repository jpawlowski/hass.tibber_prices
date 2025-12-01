"""
Chart data export service handler.

This module implements the `get_chartdata` service, which exports price data in various
formats for chart visualization (ApexCharts, custom dashboards, external integrations).

Features:
- Multiple output formats (array_of_objects, array_of_arrays)
- Custom field naming
- Level/rating filtering
- Period filtering (best_price, peak_price)
- Resolution options (15min intervals, hourly aggregation)
- NULL insertion modes for clean gap visualization
- Currency conversion (major/minor units)
- Custom decimal rounding

Service: tibber_prices.get_chartdata
Response: JSON with chart-ready data

"""

from __future__ import annotations

import re
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Final

import voluptuous as vol

from custom_components.tibber_prices.const import (
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
)
from custom_components.tibber_prices.coordinator.helpers import (
    get_intervals_for_day_offsets,
)
from homeassistant.exceptions import ServiceValidationError

from .formatters import aggregate_hourly_exact, get_period_data, normalize_level_filter, normalize_rating_level_filter
from .helpers import get_entry_and_data

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall

# Service constants
CHARTDATA_SERVICE_NAME: Final = "get_chartdata"
ATTR_DAY: Final = "day"
ATTR_ENTRY_ID: Final = "entry_id"

# Service schema
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
            normalize_level_filter,
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
            normalize_rating_level_filter,
            [vol.In([PRICE_RATING_LOW, PRICE_RATING_NORMAL, PRICE_RATING_HIGH])],
        ),
        vol.Optional("insert_nulls", default="none"): vol.In(["none", "segments", "all"]),
        vol.Optional("connect_segments", default=False): bool,
        vol.Optional("add_trailing_null", default=False): bool,
        vol.Optional("period_filter"): vol.In(["best_price", "peak_price"]),
        vol.Optional("start_time_field", default="start_time"): str,
        vol.Optional("end_time_field", default="end_time"): str,
        vol.Optional("price_field", default="price_per_kwh"): str,
        vol.Optional("level_field", default="level"): str,
        vol.Optional("rating_level_field", default="rating_level"): str,
        vol.Optional("average_field", default="average"): str,
        vol.Optional("data_key", default="data"): str,
    }
)


async def handle_chartdata(call: ServiceCall) -> dict[str, Any]:  # noqa: PLR0912, PLR0915, C901
    """
    Return price data in chart-friendly format.

    This service exports Tibber price data in customizable formats for chart visualization.
    Supports both 15-minute intervals and hourly aggregation, with optional filtering by
    price level, rating level, or period (best_price/peak_price).

    See services.yaml for detailed parameter documentation.

    Args:
        call: Service call with parameters

    Returns:
        Dictionary with chart data in requested format

    Raises:
        ServiceValidationError: If entry_id is missing or invalid

    """
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

    start_time_field = call.data.get("start_time_field", "start_time")
    end_time_field = call.data.get("end_time_field", "end_time")
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
    connect_segments = call.data.get("connect_segments", False)
    add_trailing_null = call.data.get("add_trailing_null", False)
    period_filter = call.data.get("period_filter")
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

    _, coordinator, _ = get_entry_and_data(hass, entry_id)

    # Get thresholds from config for rating aggregation
    threshold_low = coordinator.config_entry.options.get(
        CONF_PRICE_RATING_THRESHOLD_LOW, DEFAULT_PRICE_RATING_THRESHOLD_LOW
    )
    threshold_high = coordinator.config_entry.options.get(
        CONF_PRICE_RATING_THRESHOLD_HIGH, DEFAULT_PRICE_RATING_THRESHOLD_HIGH
    )

    # === SPECIAL HANDLING: Period Filter ===
    # When period_filter is set, return period summaries instead of interval data
    # Period summaries are already complete objects with aggregated data
    if period_filter:
        return get_period_data(
            coordinator=coordinator,
            period_filter=period_filter,
            days=days,
            output_format=output_format,
            minor_currency=minor_currency,
            round_decimals=round_decimals,
            level_filter=level_filter,
            rating_level_filter=rating_level_filter,
            include_level=include_level,
            include_rating_level=include_rating_level,
            start_time_field=start_time_field,
            end_time_field=end_time_field,
            price_field=price_field,
            level_field=level_field,
            rating_level_field=rating_level_field,
            data_key=data_key,
            add_trailing_null=add_trailing_null,
        )

    # === NORMAL HANDLING: Interval Data ===
    # Get price data for all requested days
    chart_data = []

    # Build set of timestamps that match period_filter if specified
    period_timestamps = None
    if period_filter:
        period_timestamps = set()
        periods_data = coordinator.data.get("pricePeriods", {})
        period_data = periods_data.get(period_filter)
        if period_data:
            period_summaries = period_data.get("periods", [])
            # Period summaries don't contain intervals, only start/end timestamps
            # Build set of all 15-minute intervals within period ranges
            for period_summary in period_summaries:
                start = period_summary.get("start")
                end = period_summary.get("end")
                if start and end:
                    # Generate all 15-minute timestamps within this period
                    current = start
                    while current < end:
                        period_timestamps.add(current.isoformat())
                        current = current + coordinator.time.get_interval_duration()

    # Collect all timestamps if insert_nulls='all' (needed to insert NULLs for missing filter matches)
    all_timestamps = set()
    if insert_nulls == "all" and (level_filter or rating_level_filter):
        # Use helper to get intervals for requested days
        # Map day keys to offsets: yesterday=-1, today=0, tomorrow=1
        day_offset_map = {"yesterday": -1, "today": 0, "tomorrow": 1}
        offsets = [day_offset_map[day] for day in days]
        day_intervals = get_intervals_for_day_offsets(coordinator.data, offsets)
        all_timestamps = {interval["startsAt"] for interval in day_intervals if interval.get("startsAt")}
        all_timestamps = sorted(all_timestamps)

    # Calculate average if requested
    day_averages = {}
    if include_average:
        for day in days:
            # Use helper to get intervals for this day
            # Build minimal coordinator_data for single day query
            # Map day key to offset: yesterday=-1, today=0, tomorrow=1
            day_offset = {"yesterday": -1, "today": 0, "tomorrow": 1}[day]
            day_intervals = get_intervals_for_day_offsets(coordinator.data, [day_offset])

            # Collect prices from intervals
            prices = [p["total"] for p in day_intervals if p.get("total") is not None]

            if prices:
                avg = sum(prices) / len(prices)
                # Apply same transformations as to regular prices
                avg = round(avg * 100, 2) if minor_currency else round(avg, 4)
                if round_decimals is not None:
                    avg = round(avg, round_decimals)
                day_averages[day] = avg

    for day in days:
        # Use helper to get intervals for this day
        # Map day key to offset: yesterday=-1, today=0, tomorrow=1
        day_offset = {"yesterday": -1, "today": 0, "tomorrow": 1}[day]
        day_prices = get_intervals_for_day_offsets(coordinator.data, [day_offset])

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

                    data_point = {
                        start_time_field: start_time.isoformat() if hasattr(start_time, "isoformat") else start_time,
                        price_field: price,
                    }

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
                    next_price = next_interval.get("total")
                    next_start_time = next_interval.get("startsAt")

                    if start_time is None or price is None:
                        continue

                    interval_value = interval.get(filter_field)
                    next_value = next_interval.get(filter_field)

                    # Check if current interval matches filter
                    if interval_value in filter_values:  # type: ignore[operator]
                        # Convert price
                        converted_price = round(price * 100, 2) if minor_currency else round(price, 4)
                        if round_decimals is not None:
                            converted_price = round(converted_price, round_decimals)

                        # Add current point
                        data_point = {
                            start_time_field: start_time.isoformat()
                            if hasattr(start_time, "isoformat")
                            else start_time,
                            price_field: converted_price,
                        }

                        if include_level and "level" in interval:
                            data_point[level_field] = interval["level"]
                        if include_rating_level and "rating_level" in interval:
                            data_point[rating_level_field] = interval["rating_level"]
                        if include_average and day in day_averages:
                            data_point[average_field] = day_averages[day]

                        chart_data.append(data_point)

                        # Check if next interval is different level (segment boundary)
                        if next_value != interval_value:
                            next_start_serialized = (
                                next_start_time.isoformat()
                                if next_start_time and hasattr(next_start_time, "isoformat")
                                else next_start_time
                            )

                            if connect_segments and next_price is not None:
                                # Connect segments visually by adding transition points
                                # Convert next price for comparison and use
                                converted_next_price = (
                                    round(next_price * 100, 2) if minor_currency else round(next_price, 4)
                                )
                                if round_decimals is not None:
                                    converted_next_price = round(converted_next_price, round_decimals)

                                if next_price < price:
                                    # Price goes DOWN: Add point at end of current segment with lower price
                                    # This draws the line downward from current level
                                    connect_point = {
                                        start_time_field: next_start_serialized,
                                        price_field: converted_next_price,
                                    }
                                    if include_level and "level" in interval:
                                        connect_point[level_field] = interval["level"]
                                    if include_rating_level and "rating_level" in interval:
                                        connect_point[rating_level_field] = interval["rating_level"]
                                    if include_average and day in day_averages:
                                        connect_point[average_field] = day_averages[day]
                                    chart_data.append(connect_point)
                                else:
                                    # Price goes UP or stays same: Add hold point with current price
                                    # This extends the current level to the boundary before the gap
                                    hold_point = {
                                        start_time_field: next_start_serialized,
                                        price_field: converted_price,
                                    }
                                    if include_level and "level" in interval:
                                        hold_point[level_field] = interval["level"]
                                    if include_rating_level and "rating_level" in interval:
                                        hold_point[rating_level_field] = interval["rating_level"]
                                    if include_average and day in day_averages:
                                        hold_point[average_field] = day_averages[day]
                                    chart_data.append(hold_point)

                                # Add NULL point to create gap after transition
                                null_point = {start_time_field: next_start_serialized, price_field: None}
                                chart_data.append(null_point)
                            else:
                                # Original behavior: Hold current price until next timestamp
                                hold_point = {
                                    start_time_field: next_start_serialized,
                                    price_field: converted_price,
                                }
                                if include_level and "level" in interval:
                                    hold_point[level_field] = interval["level"]
                                if include_rating_level and "rating_level" in interval:
                                    hold_point[rating_level_field] = interval["rating_level"]
                                if include_average and day in day_averages:
                                    hold_point[average_field] = day_averages[day]
                                chart_data.append(hold_point)

                                # Add NULL point to create gap
                                null_point = {start_time_field: next_start_serialized, price_field: None}
                                chart_data.append(null_point)

                # Handle last interval of the day - extend to midnight
                if day_prices:
                    last_interval = day_prices[-1]
                    last_start_time = last_interval.get("startsAt")
                    last_price = last_interval.get("total")
                    last_value = last_interval.get(filter_field)

                    if last_start_time and last_price is not None and last_value in filter_values:  # type: ignore[operator]
                        # Timestamp is already datetime in local timezone
                        last_dt = last_start_time  # Already datetime object
                        if last_dt:
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
                                # Use helper to get first interval of next day
                                # Map day key to offset: yesterday=-1, today=0, tomorrow=1
                                next_day_offset = {"yesterday": -1, "today": 0, "tomorrow": 1}[next_day_name]
                                next_day_intervals = get_intervals_for_day_offsets(coordinator.data, [next_day_offset])
                                if next_day_intervals:
                                    first_next = next_day_intervals[0]
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
                            end_point = {start_time_field: midnight_timestamp, price_field: converted_price}
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
                        # Apply period filter if specified
                        if (
                            period_filter is not None
                            and period_timestamps is not None
                            and start_time not in period_timestamps
                        ):
                            continue

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

                        data_point = {
                            start_time_field: start_time.isoformat()
                            if hasattr(start_time, "isoformat")
                            else start_time,
                            price_field: price,
                        }

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
                aggregate_hourly_exact(
                    day_prices,
                    start_time_field,
                    price_field,
                    coordinator=coordinator,
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
                    period_timestamps=period_timestamps,
                    threshold_high=threshold_high,
                )
            )

    # Convert to array of arrays format if requested
    if output_format == "array_of_arrays":
        array_fields_template = call.data.get("array_fields")

        # Default: nur timestamp und price
        if not array_fields_template:
            array_fields_template = f"{{{start_time_field}}}, {{{price_field}}}"

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
        null_point = {start_time_field: last_item.get(start_time_field)}
        # Set all other potential fields to None
        for field in [price_field, level_field, rating_level_field, average_field]:
            if field in last_item:
                null_point[field] = None
        chart_data.append(null_point)

    return {data_key: chart_data}
