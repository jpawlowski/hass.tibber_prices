"""Utility functions for calculating price periods (best price and peak price)."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

MINUTES_PER_INTERVAL = 15


def calculate_periods(
    all_prices: list[dict],
    *,
    reverse_sort: bool,
    flex: float,
    min_distance_from_avg: float,
    min_period_length: int,
) -> dict[str, Any]:
    """
    Calculate price periods (best or peak) from price data.

    This function identifies periods but does NOT store full interval data redundantly.
    It returns lightweight period summaries that reference the original price data.

    Steps:
    1. Split prices by day and calculate daily averages
    2. Calculate reference prices (min/max per day)
    3. Build periods based on criteria
    4. Filter by minimum length
    5. Merge adjacent periods at midnight
    6. Extract period summaries (start/end times, not full price data)

    Args:
        all_prices: All price data points from yesterday/today/tomorrow
        reverse_sort: True for peak price (max reference), False for best price (min reference)
        flex: Flexibility threshold as decimal (e.g., 0.05 = 5%)
        min_distance_from_avg: Minimum distance from average as percentage (e.g., 10.0 = 10%)
        min_period_length: Minimum period length in minutes

    Returns:
        Dict with:
        - periods: List of lightweight period summaries (start/end times only)
        - metadata: Config and statistics
        - reference_data: Daily min/max/avg for on-demand annotation

    """
    if not all_prices:
        return {
            "periods": [],
            "metadata": {
                "total_periods": 0,
                "config": {
                    "reverse_sort": reverse_sort,
                    "flex": flex,
                    "min_distance_from_avg": min_distance_from_avg,
                    "min_period_length": min_period_length,
                },
            },
            "reference_data": {
                "ref_prices": {},
                "avg_prices": {},
            },
        }

    # Ensure prices are sorted chronologically
    all_prices_sorted = sorted(all_prices, key=lambda p: p["startsAt"])

    # Step 1: Split by day and calculate averages
    intervals_by_day, avg_price_by_day = _split_intervals_by_day(all_prices_sorted)

    # Step 2: Calculate reference prices (min or max per day)
    ref_prices = _calculate_reference_prices(intervals_by_day, reverse_sort=reverse_sort)

    # Step 3: Build periods
    price_context = {
        "ref_prices": ref_prices,
        "avg_prices": avg_price_by_day,
        "flex": flex,
        "min_distance_from_avg": min_distance_from_avg,
    }
    raw_periods = _build_periods(all_prices_sorted, price_context, reverse_sort=reverse_sort)

    # Step 4: Filter by minimum length
    raw_periods = _filter_periods_by_min_length(raw_periods, min_period_length)

    # Step 5: Merge adjacent periods at midnight
    raw_periods = _merge_adjacent_periods_at_midnight(raw_periods)

    # Step 6: Add interval ends
    _add_interval_ends(raw_periods)

    # Step 7: Filter periods by end date (keep periods ending today or later)
    raw_periods = _filter_periods_by_end_date(raw_periods)

    # Step 8: Extract lightweight period summaries (no full price data)
    # Note: Filtering for current/future is done here based on end date,
    # not start date. This preserves periods that started yesterday but end today.
    period_summaries = _extract_period_summaries(raw_periods)

    return {
        "periods": period_summaries,  # Lightweight summaries only
        "metadata": {
            "total_periods": len(period_summaries),
            "config": {
                "reverse_sort": reverse_sort,
                "flex": flex,
                "min_distance_from_avg": min_distance_from_avg,
                "min_period_length": min_period_length,
            },
        },
        "reference_data": {
            "ref_prices": {k.isoformat(): v for k, v in ref_prices.items()},
            "avg_prices": {k.isoformat(): v for k, v in avg_price_by_day.items()},
        },
    }


def _split_intervals_by_day(all_prices: list[dict]) -> tuple[dict[date, list[dict]], dict[date, float]]:
    """Split intervals by day and calculate average price per day."""
    intervals_by_day: dict[date, list[dict]] = {}
    avg_price_by_day: dict[date, float] = {}

    for price_data in all_prices:
        dt = dt_util.parse_datetime(price_data["startsAt"])
        if dt is None:
            continue
        dt = dt_util.as_local(dt)
        date_key = dt.date()
        intervals_by_day.setdefault(date_key, []).append(price_data)

    for date_key, intervals in intervals_by_day.items():
        avg_price_by_day[date_key] = sum(float(p["total"]) for p in intervals) / len(intervals)

    return intervals_by_day, avg_price_by_day


def _calculate_reference_prices(intervals_by_day: dict[date, list[dict]], *, reverse_sort: bool) -> dict[date, float]:
    """Calculate reference prices for each day (min for best, max for peak)."""
    ref_prices: dict[date, float] = {}
    for date_key, intervals in intervals_by_day.items():
        prices = [float(p["total"]) for p in intervals]
        ref_prices[date_key] = max(prices) if reverse_sort else min(prices)
    return ref_prices


def _build_periods(
    all_prices: list[dict],
    price_context: dict[str, Any],
    *,
    reverse_sort: bool,
) -> list[list[dict]]:
    """
    Build periods, allowing periods to cross midnight (day boundary).

    Periods are built day-by-day, comparing each interval to its own day's reference.
    When a day boundary is crossed, the current period is ended.
    Adjacent periods at midnight are merged in a later step.

    """
    ref_prices = price_context["ref_prices"]
    avg_prices = price_context["avg_prices"]
    flex = price_context["flex"]
    min_distance_from_avg = price_context["min_distance_from_avg"]

    periods: list[list[dict]] = []
    current_period: list[dict] = []
    last_ref_date: date | None = None

    for price_data in all_prices:
        starts_at = dt_util.parse_datetime(price_data["startsAt"])
        if starts_at is None:
            continue
        starts_at = dt_util.as_local(starts_at)
        date_key = starts_at.date()
        ref_price = ref_prices[date_key]
        avg_price = avg_prices[date_key]
        price = float(price_data["total"])

        # Calculate percentage difference from reference
        percent_diff = ((price - ref_price) / ref_price) * 100 if ref_price != 0 else 0.0
        percent_diff = round(percent_diff, 2)

        # Check if interval qualifies for the period
        in_flex = percent_diff >= flex * 100 if reverse_sort else percent_diff <= flex * 100
        within_avg_boundary = price >= avg_price if reverse_sort else price <= avg_price

        # Minimum distance from average
        if reverse_sort:
            # Peak price: must be at least min_distance_from_avg% above average
            min_distance_threshold = avg_price * (1 + min_distance_from_avg / 100)
            meets_min_distance = price >= min_distance_threshold
        else:
            # Best price: must be at least min_distance_from_avg% below average
            min_distance_threshold = avg_price * (1 - min_distance_from_avg / 100)
            meets_min_distance = price <= min_distance_threshold

        # Split period if day changes
        if last_ref_date is not None and date_key != last_ref_date and current_period:
            periods.append(current_period)
            current_period = []

        last_ref_date = date_key

        # Add to period if all criteria are met
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
            # Criteria no longer met, end current period
            periods.append(current_period)
            current_period = []

    # Add final period if exists
    if current_period:
        periods.append(current_period)

    return periods


def _filter_periods_by_min_length(periods: list[list[dict]], min_period_length: int) -> list[list[dict]]:
    """Filter periods to only include those meeting the minimum length requirement."""
    min_intervals = min_period_length // MINUTES_PER_INTERVAL
    return [period for period in periods if len(period) >= min_intervals]


def _merge_adjacent_periods_at_midnight(periods: list[list[dict]]) -> list[list[dict]]:
    """
    Merge adjacent periods that meet at midnight.

    When two periods are detected separately for consecutive days but are directly
    adjacent at midnight (15 minutes apart), merge them into a single period.

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

            last_start = current_period[-1].get("interval_start")
            next_start = next_period[0].get("interval_start")

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


def _add_interval_ends(periods: list[list[dict]]) -> None:
    """Add interval_end to each interval in-place."""
    for period in periods:
        for interval in period:
            start = interval.get("interval_start")
            if start:
                interval["interval_end"] = start + timedelta(minutes=MINUTES_PER_INTERVAL)


def _filter_periods_by_end_date(periods: list[list[dict]]) -> list[list[dict]]:
    """
    Filter periods to keep only relevant ones for today and tomorrow.

    Keep periods that:
    - End in the future (> now)
    - End today but after the start of the day (not exactly at midnight)

    This removes:
    - Periods that ended yesterday
    - Periods that ended exactly at midnight today (they're completely in the past)
    """
    now = dt_util.now()
    today = now.date()
    midnight_today = dt_util.start_of_local_day(now)

    filtered = []
    for period in periods:
        if not period:
            continue

        # Get the end time of the period (last interval's end)
        last_interval = period[-1]
        period_end = last_interval.get("interval_end")

        if not period_end:
            continue

        # Keep if period ends in the future
        if period_end > now:
            filtered.append(period)
            continue

        # Keep if period ends today but AFTER midnight (not exactly at midnight)
        if period_end.date() == today and period_end > midnight_today:
            filtered.append(period)

    return filtered


def _extract_period_summaries(periods: list[list[dict]]) -> list[dict]:
    """
    Extract lightweight period summaries without storing full price data.

    Returns minimal information needed to identify periods:
    - start/end timestamps
    - interval count
    - duration

    Sensors can use these summaries to query the actual price data from priceInfo on demand.
    """
    summaries = []

    for period in periods:
        if not period:
            continue

        first_interval = period[0]
        last_interval = period[-1]

        start_time = first_interval.get("interval_start")
        end_time = last_interval.get("interval_end")

        if not start_time or not end_time:
            continue

        summary = {
            "start": start_time,
            "end": end_time,
            "interval_count": len(period),
            "duration_minutes": len(period) * MINUTES_PER_INTERVAL,
            # Store interval timestamps for reference (minimal data)
            "interval_starts": [
                start.isoformat() for interval in period if (start := interval.get("interval_start")) is not None
            ],
        }

        summaries.append(summary)

    return summaries
