"""
Data formatting utilities for services.

This module contains data transformation and formatting functions used across
multiple service handlers, including level normalization, hourly aggregation,
and period data extraction.

Functions:
    normalize_level_filter: Convert level filter values to uppercase
    normalize_rating_level_filter: Convert rating level filter values to uppercase
    aggregate_hourly_exact: Aggregate 15-minute intervals to exact hourly averages
    get_period_data: Extract period summary data instead of interval data
    get_level_translation: Get translated name for price level or rating level

Used by:
    - services/chartdata.py: Main data export service
    - services/apexcharts.py: ApexCharts YAML generation

"""

from __future__ import annotations

from typing import Any

from custom_components.tibber_prices.const import (
    DEFAULT_PRICE_RATING_THRESHOLD_HIGH,
    DEFAULT_PRICE_RATING_THRESHOLD_LOW,
    get_translation,
)
from custom_components.tibber_prices.coordinator.helpers import (
    get_intervals_for_day_offsets,
)
from custom_components.tibber_prices.sensor.helpers import aggregate_level_data, aggregate_rating_data


def normalize_level_filter(value: list[str] | None) -> list[str] | None:
    """Convert level filter values to uppercase for case-insensitive comparison."""
    if value is None:
        return None
    return [v.upper() for v in value]


def normalize_rating_level_filter(value: list[str] | None) -> list[str] | None:
    """Convert rating level filter values to uppercase for case-insensitive comparison."""
    if value is None:
        return None
    return [v.upper() for v in value]


def aggregate_hourly_exact(  # noqa: PLR0913, PLR0912, PLR0915
    intervals: list[dict],
    start_time_field: str,
    price_field: str,
    *,
    coordinator: Any,
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
    period_timestamps: set[str] | None = None,
) -> list[dict]:
    """
    Aggregate 15-minute intervals to exact hourly averages.

    Each hour uses exactly 4 intervals (00:00, 00:15, 00:30, 00:45).
    Returns data points at the start of each hour.

    Args:
        intervals: List of 15-minute price intervals
        start_time_field: Custom name for start time field
        price_field: Custom name for price field
        coordinator: Data update coordinator instance (required)
        use_minor_currency: Convert to minor currency units (cents/øre)
        round_decimals: Optional decimal rounding
        include_level: Include aggregated level field
        include_rating_level: Include aggregated rating_level field
        level_filter: Filter intervals by level values
        rating_level_filter: Filter intervals by rating_level values
        include_average: Include day average in output
        level_field: Custom name for level field
        rating_level_field: Custom name for rating_level field
        average_field: Custom name for average field
        day_average: Day average value to include
        threshold_low: Rating level threshold (low/normal boundary)
        threshold_high: Rating level threshold (normal/high boundary)
        period_timestamps: Set of timestamps to filter by (period filter)

    Returns:
        List of hourly data points with aggregated values

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

        # Get timestamp (already datetime in local timezone)
        time = coordinator.time
        start_time = start_time_str  # Already datetime object
        if not start_time:
            i += 1
            continue

        # Check if this is the start of an hour (:00)
        if start_time.minute != 0:
            i += 1
            continue

        # Collect intervals for this hour (with optional filtering)
        intervals_per_hour = time.minutes_to_intervals(60)
        hour_intervals = []
        hour_interval_data = []  # Complete interval data for aggregation functions
        for j in range(intervals_per_hour):
            if i + j < len(intervals):
                interval = intervals[i + j]

                # Apply period filter if specified (check startsAt timestamp)
                if period_timestamps is not None:
                    interval_start = interval.get("startsAt")
                    if interval_start and interval_start not in period_timestamps:
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

            data_point = {
                start_time_field: start_time_str.isoformat()
                if hasattr(start_time_str, "isoformat")
                else start_time_str,
                price_field: avg_price,
            }

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

        # Move to next hour (skip intervals_per_hour)
        i += time.minutes_to_intervals(60)

    return hourly_data


def get_period_data(  # noqa: PLR0913, PLR0912, PLR0915
    *,
    coordinator: Any,
    period_filter: str,
    days: list[str],
    output_format: str,
    minor_currency: bool,
    round_decimals: int | None,
    level_filter: list[str] | None,
    rating_level_filter: list[str] | None,
    include_level: bool,
    include_rating_level: bool,
    start_time_field: str,
    end_time_field: str,
    price_field: str,
    level_field: str,
    rating_level_field: str,
    data_key: str,
    add_trailing_null: bool,
) -> dict[str, Any]:
    """
    Get period summary data instead of interval data.

    When period_filter is specified, returns the precomputed period summaries
    from the coordinator instead of filtering intervals.

    Note: Period prices (price_avg) are stored in minor currency units (ct/øre).
    They are converted to major currency unless minor_currency=True.

    Args:
        coordinator: Data coordinator with period summaries
        period_filter: "best_price" or "peak_price"
        days: List of days to include
        output_format: "array_of_objects" or "array_of_arrays"
        minor_currency: If False, convert prices from minor to major units
        round_decimals: Optional decimal rounding
        level_filter: Optional level filter
        rating_level_filter: Optional rating level filter
        include_level: Whether to include level field in output
        include_rating_level: Whether to include rating_level field in output
        start_time_field: Custom name for start time field
        end_time_field: Custom name for end time field
        price_field: Custom name for price field
        level_field: Custom name for level field
        rating_level_field: Custom name for rating_level field
        data_key: Top-level key name in response
        add_trailing_null: Whether to add trailing null point

    Returns:
        Dictionary with period data in requested format

    """
    periods_data = coordinator.data.get("pricePeriods", {})
    period_data = periods_data.get(period_filter)

    if not period_data:
        return {data_key: []}

    period_summaries = period_data.get("periods", [])
    if not period_summaries:
        return {data_key: []}

    chart_data = []

    # Filter periods by day if requested
    filtered_periods = []
    if days:
        # Use helper to get intervals for requested days, extract their dates
        # Map day keys to offsets: yesterday=-1, today=0, tomorrow=1
        day_offset_map = {"yesterday": -1, "today": 0, "tomorrow": 1}
        offsets = [day_offset_map[day] for day in days]
        day_intervals = get_intervals_for_day_offsets(coordinator.data, offsets)
        allowed_dates = {interval["startsAt"].date() for interval in day_intervals if interval.get("startsAt")}

        # Filter periods to those within allowed dates
        for period in period_summaries:
            start = period.get("start")
            if start and start.date() in allowed_dates:
                filtered_periods.append(period)
    else:
        filtered_periods = period_summaries

    # Apply level and rating_level filters
    for period in filtered_periods:
        # Apply level filter (normalize to uppercase for comparison)
        if level_filter and "level" in period and period["level"].upper() not in level_filter:
            continue

        # Apply rating_level filter (normalize to uppercase for comparison)
        if (
            rating_level_filter
            and "rating_level" in period
            and period["rating_level"].upper() not in rating_level_filter
        ):
            continue

        # Build data point based on output format
        if output_format == "array_of_objects":
            # Map period fields to custom field names
            # Period has: start, end, level, rating_level, price_avg, price_min, price_max
            data_point = {}

            # Start time
            start = period["start"]
            data_point[start_time_field] = start.isoformat() if hasattr(start, "isoformat") else start

            # End time
            end = period.get("end")
            data_point[end_time_field] = end.isoformat() if end and hasattr(end, "isoformat") else end

            # Price (use price_avg from period, stored in minor units)
            price_avg = period.get("price_avg", 0.0)
            # Convert to major currency unless minor_currency=True
            if not minor_currency:
                price_avg = price_avg / 100
            if round_decimals is not None:
                price_avg = round(price_avg, round_decimals)
            data_point[price_field] = price_avg

            # Level (only if requested and present)
            if include_level and "level" in period:
                data_point[level_field] = period["level"].upper()

            # Rating level (only if requested and present)
            if include_rating_level and "rating_level" in period:
                data_point[rating_level_field] = period["rating_level"].upper()

            chart_data.append(data_point)

        else:  # array_of_arrays
            # For array_of_arrays, include: [start, price_avg]
            price_avg = period.get("price_avg", 0.0)
            # Convert to major currency unless minor_currency=True
            if not minor_currency:
                price_avg = price_avg / 100
            if round_decimals is not None:
                price_avg = round(price_avg, round_decimals)
            start = period["start"]
            start_serialized = start.isoformat() if hasattr(start, "isoformat") else start
            chart_data.append([start_serialized, price_avg])

    # Add trailing null point if requested
    if add_trailing_null and chart_data:
        if output_format == "array_of_objects":
            null_point = {start_time_field: None, end_time_field: None}
            for field in [price_field, level_field, rating_level_field]:
                null_point[field] = None
            chart_data.append(null_point)
        else:  # array_of_arrays
            chart_data.append([None, None])

    return {data_key: chart_data}


def get_level_translation(level_key: str, level_type: str, language: str) -> str:
    """Get translated name for a price level or rating level."""
    level_key_lower = level_key.lower()
    # Use correct translation key based on level_type
    if level_type == "rating_level":
        name = get_translation(["selector", "rating_level_filter", "options", level_key_lower], language)
    else:
        name = get_translation(["selector", "level_filter", "options", level_key_lower], language)
    # Fallback to original key if translation not found
    return name or level_key
