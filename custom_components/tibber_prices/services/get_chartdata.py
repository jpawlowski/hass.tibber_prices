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

import math
import re
from datetime import datetime, timedelta
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
    PRICE_LEVEL_MAPPING,
    PRICE_LEVEL_NORMAL,
    PRICE_LEVEL_VERY_CHEAP,
    PRICE_LEVEL_VERY_EXPENSIVE,
    PRICE_RATING_HIGH,
    PRICE_RATING_LOW,
    PRICE_RATING_MAPPING,
    PRICE_RATING_NORMAL,
    format_price_unit_base,
    format_price_unit_subunit,
    get_currency_info,
    get_currency_name,
)
from custom_components.tibber_prices.coordinator.helpers import (
    get_intervals_for_day_offsets,
)
from homeassistant.exceptions import ServiceValidationError

from .formatters import aggregate_hourly_exact, get_period_data, normalize_level_filter, normalize_rating_level_filter
from .helpers import get_entry_and_data, has_tomorrow_data

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


def _is_transition_to_more_expensive(
    current_value: str | None,
    next_value: str | None,
    *,
    use_rating: bool = False,
) -> bool:
    """
    Check if transition from current to next level/rating is to a more expensive segment.

    Args:
        current_value: Current level or rating value
        next_value: Next level or rating value
        use_rating: If True, use rating hierarchy; if False, use level hierarchy

    Returns:
        True if transitioning to a more expensive segment

    """
    hierarchy = PRICE_RATING_MAPPING if use_rating else PRICE_LEVEL_MAPPING

    current_rank = hierarchy.get(current_value, 0) if current_value else 0
    next_rank = hierarchy.get(next_value, 0) if next_value else 0

    return next_rank > current_rank


def _calculate_metadata(  # noqa: PLR0912, PLR0913, PLR0915
    chart_data: list[dict[str, Any]],
    price_field: str,
    start_time_field: str,
    currency: str,
    *,
    resolution: str,
    subunit_currency: bool = False,
) -> dict[str, Any]:
    """
    Calculate metadata for chart visualization.

    Args:
        chart_data: The chart data array
        price_field: Name of the price field in chart_data
        start_time_field: Name of the start time field
        currency: Currency code (e.g., "EUR", "NOK")
        resolution: Resolution type ("interval" or "hourly")
        subunit_currency: Whether prices are in subunit currency units

    Returns:
        Metadata dictionary with price statistics, yaxis suggestions, and time info

    """
    # Get currency info (returns tuple: base_symbol, subunit_symbol, subunit_name)
    base_symbol, subunit_symbol, subunit_name = get_currency_info(currency)

    # Build currency object with only the active unit
    if subunit_currency:
        currency_obj = {
            "code": currency,
            "symbol": subunit_symbol,
            "name": subunit_name,  # Already capitalized in CURRENCY_INFO
            "unit": format_price_unit_subunit(currency),
        }
    else:
        currency_obj = {
            "code": currency,
            "symbol": base_symbol,
            "name": get_currency_name(currency),  # Full currency name (e.g., "Euro")
            "unit": format_price_unit_base(currency),
        }

    # Extract all prices (excluding None values)
    prices = [item[price_field] for item in chart_data if item.get(price_field) is not None]

    if not prices:
        return {}

    # Parse timestamps to determine day boundaries
    # Group by date (midnight-to-midnight)
    dates_seen = set()
    for item in chart_data:
        timestamp_str = item.get(start_time_field)
        if timestamp_str and item.get(price_field) is not None:
            # Parse ISO timestamp
            dt = datetime.fromisoformat(timestamp_str) if isinstance(timestamp_str, str) else timestamp_str
            date = dt.date()
            dates_seen.add(date)

    # Sort dates to ensure consistent day numbering
    sorted_dates = sorted(dates_seen)

    # Split data by day - dynamically handle any number of days
    days_data: dict[str, list[float]] = {}
    for i, _date in enumerate(sorted_dates, start=1):
        day_key = f"day{i}"
        days_data[day_key] = []

    # Assign prices to their respective days
    for item in chart_data:
        timestamp_str = item.get(start_time_field)
        price = item.get(price_field)
        if timestamp_str and price is not None:
            dt = datetime.fromisoformat(timestamp_str) if isinstance(timestamp_str, str) else timestamp_str
            date = dt.date()
            # Find which day this date corresponds to
            day_index = sorted_dates.index(date) + 1
            day_key = f"day{day_index}"
            days_data[day_key].append(price)

    def calc_stats(data: list[float]) -> dict[str, float]:
        """Calculate comprehensive statistics for a dataset."""
        if not data:
            return {}
        min_val = min(data)
        max_val = max(data)
        mean_val = sum(data) / len(data)
        median_val = sorted(data)[len(data) // 2]

        # Calculate mean_position and median_position (0-1 scale)
        price_range = max_val - min_val
        mean_position = (mean_val - min_val) / price_range if price_range > 0 else 0.5
        median_position = (median_val - min_val) / price_range if price_range > 0 else 0.5

        # Position precision: 2 decimals for subunit currency, 4 for base currency
        position_decimals = 2 if subunit_currency else 4
        # Price precision: 2 decimals for subunit currency, 4 for base currency
        price_decimals = 2 if subunit_currency else 4

        return {
            "min": round(min_val, price_decimals),
            "max": round(max_val, price_decimals),
            "mean": round(mean_val, price_decimals),
            "mean_position": round(mean_position, position_decimals),
            "median": round(median_val, price_decimals),
            "median_position": round(median_position, position_decimals),
        }

    # Calculate stats for combined and per-day data
    combined_stats = calc_stats(prices)

    # Calculate stats for each day dynamically
    per_day_stats: dict[str, dict[str, float]] = {}
    for day_key, day_data in days_data.items():
        if day_data:
            per_day_stats[day_key] = calc_stats(day_data)

    # Calculate suggested yaxis bounds (floor(min) - 1 and ceil(max) + 1)
    yaxis_min = math.floor(combined_stats["min"]) - 1 if combined_stats else 0
    yaxis_max = math.ceil(combined_stats["max"]) + 1 if combined_stats else 100

    # Get time range from chart data
    timestamps = [item[start_time_field] for item in chart_data if item.get(start_time_field)]
    time_range = {}

    if timestamps:
        time_range = {
            "start": timestamps[0],
            "end": timestamps[-1],
            "days_included": list(days_data.keys()),
        }

    # Determine interval duration in minutes based on resolution
    interval_duration_minutes = 15 if resolution == "interval" else 60

    # Calculate suggested yaxis bounds
    # For subunit currency (ct, øre): integer values (floor/ceil)
    # For base currency (€, kr): 2 decimal places precision
    if subunit_currency:
        yaxis_min = math.floor(combined_stats["min"]) - 1 if combined_stats else 0
        yaxis_max = math.ceil(combined_stats["max"]) + 1 if combined_stats else 100
    else:
        # Base currency: round to 2 decimal places with padding
        yaxis_min = round(math.floor(combined_stats["min"] * 100) / 100 - 0.01, 2) if combined_stats else 0
        yaxis_max = round(math.ceil(combined_stats["max"] * 100) / 100 + 0.01, 2) if combined_stats else 1.0

    return {
        "currency": currency_obj,
        "resolution": interval_duration_minutes,
        "data_count": len(chart_data),
        "price_stats": {"combined": combined_stats, **per_day_stats},
        "yaxis_suggested": {"min": yaxis_min, "max": yaxis_max},
        "time_range": time_range,
    }


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
        vol.Optional("subunit_currency", default=False): bool,
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
        vol.Optional("metadata", default="include"): vol.In(["include", "only", "none"]),
    }
)


async def handle_chartdata(call: ServiceCall) -> dict[str, Any]:  # noqa: PLR0912, PLR0915, C901
    """
    Return price data in chart-friendly format.

    This service exports Tibber price data in customizable formats for chart visualization.
    Supports both 15-minute intervals and hourly aggregation, with optional filtering by
    price level, rating level, or period (best_price/peak_price).

    Default behavior (no day parameter):
    - Returns rolling 2-day window for continuous chart display
    - If tomorrow data available: today + tomorrow
    - If tomorrow data NOT available: yesterday + today

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

    # Get coordinator to check data availability
    _, coordinator, _ = get_entry_and_data(hass, entry_id)

    days_raw = call.data.get(ATTR_DAY)
    # If no day specified, use rolling 2-day window:
    # - If tomorrow data available: today + tomorrow
    # - If tomorrow data NOT available: yesterday + today
    if days_raw is None:
        days = ["today", "tomorrow"] if has_tomorrow_data(coordinator) else ["yesterday", "today"]
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
    subunit_currency = call.data.get("subunit_currency", False)
    metadata = call.data.get("metadata", "include")
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

    # === METADATA-ONLY MODE ===
    # Early return: calculate and return only metadata, skip all data processing
    if metadata == "only":
        # Get minimal data to calculate metadata (just timestamps and prices)
        # Use helper to get intervals for requested days
        day_offset_map = {"yesterday": -1, "today": 0, "tomorrow": 1}
        offsets = [day_offset_map[day] for day in days]
        all_intervals = get_intervals_for_day_offsets(coordinator.data, offsets)

        # Build minimal chart_data for metadata calculation
        chart_data_for_meta = []
        for interval in all_intervals:
            start_time = interval.get("startsAt")
            price = interval.get("total")
            if start_time is not None and price is not None:
                # Convert price to requested currency
                converted_price = round(price * 100, 2) if subunit_currency else round(price, 4)
                chart_data_for_meta.append(
                    {
                        start_time_field: start_time.isoformat() if hasattr(start_time, "isoformat") else start_time,
                        price_field: converted_price,
                    }
                )

        # Calculate metadata
        metadata = _calculate_metadata(
            chart_data=chart_data_for_meta,
            price_field=price_field,
            start_time_field=start_time_field,
            currency=coordinator.data.get("currency", "EUR"),
            resolution=resolution,
            subunit_currency=subunit_currency,
        )

        return {"metadata": metadata}

    # Filter values are already normalized to uppercase by schema validators

    # If array_fields is specified, implicitly enable fields that are used
    array_fields_template = call.data.get("array_fields")
    if array_fields_template and output_format == "array_of_arrays":
        if level_field in array_fields_template:
            include_level = True
        if rating_level_field in array_fields_template:
            include_rating_level = True
        if average_field in array_fields_template:
            include_average = True

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
            subunit_currency=subunit_currency,
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
            insert_nulls=insert_nulls,
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

    # Calculate average if requested (per day for average_field)
    # Also build a mapping from date -> day_key for later lookup
    day_averages: dict[str, float] = {}
    date_to_day_key: dict[Any, str] = {}  # Maps date object to "yesterday"/"today"/"tomorrow"

    for day in days:
        # Use helper to get intervals for this day
        # Map day key to offset: yesterday=-1, today=0, tomorrow=1
        day_offset = {"yesterday": -1, "today": 0, "tomorrow": 1}[day]
        day_intervals = get_intervals_for_day_offsets(coordinator.data, [day_offset])

        # Build date -> day_key mapping from actual interval data
        for interval in day_intervals:
            start_time = interval.get("startsAt")
            if start_time and hasattr(start_time, "date"):
                date_to_day_key[start_time.date()] = day

        # Calculate average if requested
        if include_average:
            prices = [p["total"] for p in day_intervals if p.get("total") is not None]
            if prices:
                avg = sum(prices) / len(prices)
                # Apply same transformations as to regular prices
                avg = round(avg * 100, 2) if subunit_currency else round(avg, 4)
                if round_decimals is not None:
                    avg = round(avg, round_decimals)
                day_averages[day] = avg

    # Collect ALL intervals for the selected days as one continuous list
    # This simplifies processing - no special midnight handling needed
    day_offsets = [{"yesterday": -1, "today": 0, "tomorrow": 1}[day] for day in days]
    all_prices = get_intervals_for_day_offsets(coordinator.data, day_offsets)

    # Helper to get day key from interval timestamp for average lookup
    def _get_day_key_for_interval(interval_start: Any) -> str | None:
        """Determine which day key (yesterday/today/tomorrow) an interval belongs to."""
        if not interval_start or not hasattr(interval_start, "date"):
            return None
        # Use pre-built mapping from actual interval data (TimeService-compatible)
        return date_to_day_key.get(interval_start.date())

    if resolution == "interval":
        # Original 15-minute intervals
        if insert_nulls == "all" and (level_filter or rating_level_filter):
            # Mode 'all': Insert NULL for all timestamps where filter doesn't match
            # Build a map of timestamp -> interval for quick lookup
            interval_map = {interval.get("startsAt"): interval for interval in all_prices if interval.get("startsAt")}

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
                    # Convert to subunit currency (cents/øre) if requested
                    price = round(price * 100, 2) if subunit_currency else round(price, 4)
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
                day_key = _get_day_key_for_interval(start_time)
                if include_average and day_key and day_key in day_averages:
                    data_point[average_field] = day_averages[day_key]

                chart_data.append(data_point)

        elif insert_nulls == "segments" and (level_filter or rating_level_filter):
            # Mode 'segments': Add NULL points at segment boundaries for clean gaps
            # Process ALL intervals as one continuous list - no special midnight handling needed
            filter_field = "rating_level" if rating_level_filter else "level"
            filter_values = rating_level_filter if rating_level_filter else level_filter
            use_rating = rating_level_filter is not None

            for i in range(len(all_prices) - 1):
                interval = all_prices[i]
                next_interval = all_prices[i + 1]

                start_time = interval.get("startsAt")
                price = interval.get("total")
                next_price = next_interval.get("total")
                next_start_time = next_interval.get("startsAt")

                if start_time is None or price is None:
                    continue

                interval_value = interval.get(filter_field)
                next_value = next_interval.get(filter_field)
                prev_value = all_prices[i - 1].get(filter_field) if i > 0 else None
                prev_price = all_prices[i - 1].get("total") if i > 0 else None

                # Check if current interval matches filter
                if interval_value in filter_values:  # type: ignore[operator]
                    # Convert price
                    converted_price = round(price * 100, 2) if subunit_currency else round(price, 4)
                    if round_decimals is not None:
                        converted_price = round(converted_price, round_decimals)

                    # Check if this is the START of a new segment (previous interval had different level)
                    # and the transition was from a CHEAPER level (price increase)
                    is_segment_start = prev_value != interval_value and prev_value not in filter_values  # type: ignore[operator]
                    is_from_cheaper = (
                        _is_transition_to_more_expensive(prev_value, interval_value, use_rating=use_rating)
                        if prev_value
                        else False
                    )

                    # Add current point FIRST (tooltip will show here - at the actual price!)
                    data_point = {
                        start_time_field: start_time.isoformat() if hasattr(start_time, "isoformat") else start_time,
                        price_field: converted_price,
                    }

                    if include_level and "level" in interval:
                        data_point[level_field] = interval["level"]
                    if include_rating_level and "rating_level" in interval:
                        data_point[rating_level_field] = interval["rating_level"]

                    day_key = _get_day_key_for_interval(start_time)
                    if include_average and day_key and day_key in day_averages:
                        data_point[average_field] = day_averages[day_key]

                    chart_data.append(data_point)

                    # AFTER the real point: Add END-BRIDGE to draw vertical line DOWN to previous price
                    # This ensures the vertical upward transition line is drawn in THIS (more expensive) color
                    # but the tooltip shows the actual (higher) price
                    if connect_segments and is_segment_start and is_from_cheaper and prev_price is not None:
                        converted_prev_price = round(prev_price * 100, 2) if subunit_currency else round(prev_price, 4)
                        if round_decimals is not None:
                            converted_prev_price = round(converted_prev_price, round_decimals)

                        # End-bridge: draws line DOWN to previous (cheaper) price
                        end_bridge = {
                            start_time_field: start_time.isoformat()
                            if hasattr(start_time, "isoformat")
                            else start_time,
                            price_field: converted_prev_price,  # Go DOWN to previous (cheaper) price
                        }
                        if include_level and "level" in interval:
                            end_bridge[level_field] = interval["level"]  # Keep THIS level for color
                        if include_rating_level and "rating_level" in interval:
                            end_bridge[rating_level_field] = interval["rating_level"]
                        if include_average and day_key and day_key in day_averages:
                            end_bridge[average_field] = day_averages[day_key]
                        chart_data.append(end_bridge)

                        # NULL to stop this "bridge sequence" - prevents line from going to next point
                        null_point = {start_time_field: data_point[start_time_field], price_field: None}
                        chart_data.append(null_point)

                    chart_data.append(data_point)

                    # Check if next interval is different level (segment boundary = END of this segment)
                    if next_value != interval_value:
                        next_start_serialized = (
                            next_start_time.isoformat()
                            if next_start_time and hasattr(next_start_time, "isoformat")
                            else next_start_time
                        )

                        is_to_more_expensive = _is_transition_to_more_expensive(
                            interval_value, next_value, use_rating=use_rating
                        )

                        if connect_segments and next_price is not None:
                            # Connect segments visually at boundaries
                            # Strategy: The vertical line should be drawn by the MORE EXPENSIVE segment
                            #
                            # - Price INCREASE (cheap → expensive): Vertical line belongs to NEXT segment
                            #   → THIS segment just holds at current price, NEXT segment draws the bridge UP
                            #   → We add a hold point here, the start-bridge logic handles the NEXT segment
                            #
                            # - Price DECREASE (expensive → cheap): Vertical line belongs to THIS segment
                            #   → THIS segment draws the bridge DOWN to next price

                            if is_to_more_expensive:
                                # Transition to MORE EXPENSIVE level (price increase)
                                # Just hold at current price - the NEXT segment will draw the upward line
                                # via its start-bridge logic
                                hold_point = {
                                    start_time_field: next_start_serialized,
                                    price_field: converted_price,  # Hold at CURRENT price
                                }
                                if include_level and "level" in interval:
                                    hold_point[level_field] = interval["level"]
                                if include_rating_level and "rating_level" in interval:
                                    hold_point[rating_level_field] = interval["rating_level"]
                                if include_average and day_key and day_key in day_averages:
                                    hold_point[average_field] = day_averages[day_key]
                                chart_data.append(hold_point)
                            else:
                                # Transition to LESS EXPENSIVE or SAME level (price decrease/stable)
                                # Draw the bridge DOWN to the next price in THIS level's color
                                converted_next_price = (
                                    round(next_price * 100, 2) if subunit_currency else round(next_price, 4)
                                )
                                if round_decimals is not None:
                                    converted_next_price = round(converted_next_price, round_decimals)

                                bridge_point = {
                                    start_time_field: next_start_serialized,
                                    price_field: converted_next_price,
                                }
                                if include_level and "level" in interval:
                                    bridge_point[level_field] = interval["level"]
                                if include_rating_level and "rating_level" in interval:
                                    bridge_point[rating_level_field] = interval["rating_level"]
                                if include_average and day_key and day_key in day_averages:
                                    bridge_point[average_field] = day_averages[day_key]
                                chart_data.append(bridge_point)

                            # NULL point: stops the current series
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
                            if include_average and day_key and day_key in day_averages:
                                hold_point[average_field] = day_averages[day_key]
                            chart_data.append(hold_point)

                            # Add NULL point to create gap
                            null_point = {start_time_field: next_start_serialized, price_field: None}
                            chart_data.append(null_point)

            # Handle LAST interval of the entire selection (not per-day)
            # The main loop processes up to n-1, so we need to add the last interval
            if all_prices:
                last_interval = all_prices[-1]
                last_start_time = last_interval.get("startsAt")
                last_price = last_interval.get("total")
                last_value = last_interval.get(filter_field)

                if last_start_time and last_price is not None and last_value in filter_values:  # type: ignore[operator]
                    # Add the last interval as a data point
                    converted_last_price = round(last_price * 100, 2) if subunit_currency else round(last_price, 4)
                    if round_decimals is not None:
                        converted_last_price = round(converted_last_price, round_decimals)

                    last_data_point = {
                        start_time_field: last_start_time.isoformat()
                        if hasattr(last_start_time, "isoformat")
                        else last_start_time,
                        price_field: converted_last_price,
                    }
                    if include_level and "level" in last_interval:
                        last_data_point[level_field] = last_interval["level"]
                    if include_rating_level and "rating_level" in last_interval:
                        last_data_point[rating_level_field] = last_interval["rating_level"]

                    day_key = _get_day_key_for_interval(last_start_time)
                    if include_average and day_key and day_key in day_averages:
                        last_data_point[average_field] = day_averages[day_key]
                    chart_data.append(last_data_point)

                    # Extend to end of selected time range (midnight after last day)
                    last_dt = last_start_time
                    if last_dt:
                        # Calculate midnight after the last interval
                        next_midnight = last_dt.replace(hour=0, minute=0, second=0, microsecond=0)
                        next_midnight = next_midnight + timedelta(days=1)
                        midnight_timestamp = next_midnight.isoformat()

                        # Add hold point at midnight
                        end_point = {start_time_field: midnight_timestamp, price_field: converted_last_price}
                        if include_level and "level" in last_interval:
                            end_point[level_field] = last_interval["level"]
                        if include_rating_level and "rating_level" in last_interval:
                            end_point[rating_level_field] = last_interval["rating_level"]
                        if include_average and day_key and day_key in day_averages:
                            end_point[average_field] = day_averages[day_key]
                        chart_data.append(end_point)

                        # Add NULL to end series
                        null_point = {start_time_field: midnight_timestamp, price_field: None}
                        chart_data.append(null_point)

        else:
            # Mode 'none' (default): Only return matching intervals, no NULL insertion
            for interval in all_prices:
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

                    # Convert to subunit currency (cents/øre) if requested
                    price = round(price * 100, 2) if subunit_currency else round(price, 4)

                    # Apply custom rounding if specified
                    if round_decimals is not None:
                        price = round(price, round_decimals)

                    data_point = {
                        start_time_field: start_time.isoformat() if hasattr(start_time, "isoformat") else start_time,
                        price_field: price,
                    }

                    # Add level if requested
                    if include_level and "level" in interval:
                        data_point[level_field] = interval["level"]

                    # Add rating_level if requested
                    if include_rating_level and "rating_level" in interval:
                        data_point[rating_level_field] = interval["rating_level"]

                    # Add average if requested
                    day_key = _get_day_key_for_interval(start_time)
                    if include_average and day_key and day_key in day_averages:
                        data_point[average_field] = day_averages[day_key]

                    chart_data.append(data_point)

    elif resolution == "hourly":
        # Hourly averages (4 intervals per hour: :00, :15, :30, :45)
        # Process all intervals together for hourly aggregation
        chart_data.extend(
            aggregate_hourly_exact(
                all_prices,
                start_time_field,
                price_field,
                coordinator=coordinator,
                use_subunit_currency=subunit_currency,
                round_decimals=round_decimals,
                include_level=include_level,
                include_rating_level=include_rating_level,
                level_filter=level_filter,
                rating_level_filter=rating_level_filter,
                include_average=include_average,
                level_field=level_field,
                rating_level_field=rating_level_field,
                average_field=average_field,
                day_average=None,  # Not used when processing all days together
                threshold_low=threshold_low,
                period_timestamps=period_timestamps,
                threshold_high=threshold_high,
            )
        )

    # Remove trailing null values ONLY for insert_nulls='segments' mode.
    # For 'all' mode, trailing nulls are intentional (show no-match until end of day).
    # For 'segments' mode, trailing nulls cause ApexCharts header to show "N/A".
    # Internal nulls at segment boundaries are preserved for gap visualization.
    if insert_nulls == "segments":
        while chart_data and chart_data[-1].get(price_field) is None:
            chart_data.pop()

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

        # Calculate metadata (before adding trailing null to chart_data)
        result = {data_key: points}
        if metadata in ("include", "only"):
            metadata_obj = _calculate_metadata(
                chart_data=chart_data,
                price_field=price_field,
                start_time_field=start_time_field,
                currency=coordinator.data.get("currency", "EUR"),
                resolution=resolution,
                subunit_currency=subunit_currency,
            )
            if metadata_obj:
                result["metadata"] = metadata_obj  # type: ignore[index]
        return result

    # Calculate metadata (before adding trailing null)
    result = {data_key: chart_data}
    if metadata in ("include", "only"):
        metadata_obj = _calculate_metadata(
            chart_data=chart_data,
            price_field=price_field,
            start_time_field=start_time_field,
            currency=coordinator.data.get("currency", "EUR"),
            resolution=resolution,
            subunit_currency=subunit_currency,
        )
        if metadata_obj:
            result["metadata"] = metadata_obj  # type: ignore[index]

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

    return result
