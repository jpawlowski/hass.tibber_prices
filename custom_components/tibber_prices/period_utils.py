"""Utility functions for calculating price periods (best price and peak price)."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any, NamedTuple

if TYPE_CHECKING:
    from collections.abc import Callable

from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_PRICE_RATING_THRESHOLD_HIGH,
    DEFAULT_PRICE_RATING_THRESHOLD_LOW,
    DEFAULT_VOLATILITY_THRESHOLD_HIGH,
    DEFAULT_VOLATILITY_THRESHOLD_MODERATE,
    DEFAULT_VOLATILITY_THRESHOLD_VERY_HIGH,
)
from .price_utils import (
    aggregate_period_levels,
    aggregate_period_ratings,
    calculate_volatility_level,
)

_LOGGER = logging.getLogger(__name__)

MINUTES_PER_INTERVAL = 15

# Log indentation levels for visual hierarchy
INDENT_L0 = ""  # Top level (calculate_periods_with_relaxation)
INDENT_L1 = "  "  # Per-day loop
INDENT_L2 = "    "  # Flex/filter loop (_relax_single_day)
INDENT_L3 = "      "  # _resolve_period_overlaps function
INDENT_L4 = "        "  # Period-by-period analysis
INDENT_L5 = "          "  # Segment details


class PeriodConfig(NamedTuple):
    """Configuration for period calculation."""

    reverse_sort: bool
    flex: float
    min_distance_from_avg: float
    min_period_length: int
    threshold_low: float = DEFAULT_PRICE_RATING_THRESHOLD_LOW
    threshold_high: float = DEFAULT_PRICE_RATING_THRESHOLD_HIGH
    threshold_volatility_moderate: float = DEFAULT_VOLATILITY_THRESHOLD_MODERATE
    threshold_volatility_high: float = DEFAULT_VOLATILITY_THRESHOLD_HIGH
    threshold_volatility_very_high: float = DEFAULT_VOLATILITY_THRESHOLD_VERY_HIGH


class PeriodData(NamedTuple):
    """Data for building a period summary."""

    start_time: datetime
    end_time: datetime
    period_length: int
    period_idx: int
    total_periods: int


class PeriodStatistics(NamedTuple):
    """Calculated statistics for a period."""

    aggregated_level: str | None
    aggregated_rating: str | None
    rating_difference_pct: float | None
    price_avg: float
    price_min: float
    price_max: float
    price_spread: float
    volatility: str
    period_price_diff: float | None
    period_price_diff_pct: float | None


class ThresholdConfig(NamedTuple):
    """Threshold configuration for period calculations."""

    threshold_low: float | None
    threshold_high: float | None
    threshold_volatility_moderate: float
    threshold_volatility_high: float
    threshold_volatility_very_high: float
    reverse_sort: bool


def calculate_periods(
    all_prices: list[dict],
    *,
    config: PeriodConfig,
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
        config: Period configuration containing reverse_sort, flex, min_distance_from_avg,
                min_period_length, threshold_low, and threshold_high

    Returns:
        Dict with:
        - periods: List of lightweight period summaries (start/end times only)
        - metadata: Config and statistics
        - reference_data: Daily min/max/avg for on-demand annotation

    """
    # Extract config values
    reverse_sort = config.reverse_sort
    flex = config.flex
    min_distance_from_avg = config.min_distance_from_avg
    min_period_length = config.min_period_length
    threshold_low = config.threshold_low
    threshold_high = config.threshold_high

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
    thresholds = ThresholdConfig(
        threshold_low=threshold_low,
        threshold_high=threshold_high,
        threshold_volatility_moderate=config.threshold_volatility_moderate,
        threshold_volatility_high=config.threshold_volatility_high,
        threshold_volatility_very_high=config.threshold_volatility_very_high,
        reverse_sort=reverse_sort,
    )
    period_summaries = _extract_period_summaries(
        raw_periods,
        all_prices_sorted,
        price_context,
        thresholds,
    )

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
        if in_flex and meets_min_distance:
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


def _calculate_period_price_diff(
    price_avg: float,
    start_time: datetime,
    price_context: dict[str, Any],
) -> tuple[float | None, float | None]:
    """
    Calculate period price difference from daily reference (min or max).

    Uses reference price from start day of the period for consistency.

    Returns:
        Tuple of (period_price_diff, period_price_diff_pct) or (None, None) if no reference available.

    """
    if not price_context or not start_time:
        return None, None

    ref_prices = price_context.get("ref_prices", {})
    date_key = start_time.date()
    ref_price = ref_prices.get(date_key)

    if ref_price is None:
        return None, None

    # Convert reference price to minor units (ct/øre)
    ref_price_minor = round(ref_price * 100, 2)
    period_price_diff = round(price_avg - ref_price_minor, 2)
    period_price_diff_pct = None
    if ref_price_minor != 0:
        period_price_diff_pct = round((period_price_diff / ref_price_minor) * 100, 2)

    return period_price_diff, period_price_diff_pct


def _calculate_aggregated_rating_difference(period_price_data: list[dict]) -> float | None:
    """
    Calculate aggregated rating difference percentage for the period.

    Takes the average of all interval differences (from their respective thresholds).

    Args:
        period_price_data: List of price data dictionaries with "difference" field

    Returns:
        Average difference percentage, or None if no valid data

    """
    differences = []
    for price_data in period_price_data:
        diff = price_data.get("difference")
        if diff is not None:
            differences.append(float(diff))

    if not differences:
        return None

    return round(sum(differences) / len(differences), 2)


def _calculate_period_price_statistics(period_price_data: list[dict]) -> dict[str, float]:
    """
    Calculate price statistics for a period.

    Args:
        period_price_data: List of price data dictionaries with "total" field

    Returns:
        Dictionary with price_avg, price_min, price_max, price_spread (all in minor units: ct/øre)

    """
    prices_minor = [round(float(p["total"]) * 100, 2) for p in period_price_data]

    if not prices_minor:
        return {
            "price_avg": 0.0,
            "price_min": 0.0,
            "price_max": 0.0,
            "price_spread": 0.0,
        }

    price_avg = round(sum(prices_minor) / len(prices_minor), 2)
    price_min = round(min(prices_minor), 2)
    price_max = round(max(prices_minor), 2)
    price_spread = round(price_max - price_min, 2)

    return {
        "price_avg": price_avg,
        "price_min": price_min,
        "price_max": price_max,
        "price_spread": price_spread,
    }


def _build_period_summary_dict(
    period_data: PeriodData,
    stats: PeriodStatistics,
    *,
    reverse_sort: bool,
) -> dict:
    """
    Build the complete period summary dictionary.

    Args:
        period_data: Period timing and position data
        stats: Calculated period statistics
        reverse_sort: True for peak price, False for best price (keyword-only)

    Returns:
        Complete period summary dictionary following attribute ordering

    """
    # Build complete period summary (following attribute ordering from AGENTS.md)
    summary = {
        # 1. Time information (when does this apply?)
        "start": period_data.start_time,
        "end": period_data.end_time,
        "duration_minutes": period_data.period_length * MINUTES_PER_INTERVAL,
        # 2. Core decision attributes (what should I do?)
        "level": stats.aggregated_level,
        "rating_level": stats.aggregated_rating,
        "rating_difference_%": stats.rating_difference_pct,
        # 3. Price statistics (how much does it cost?)
        "price_avg": stats.price_avg,
        "price_min": stats.price_min,
        "price_max": stats.price_max,
        "price_spread": stats.price_spread,
        "volatility": stats.volatility,
        # 4. Price differences will be added below if available
        # 5. Detail information (additional context)
        "period_interval_count": period_data.period_length,
        "period_position": period_data.period_idx,
        "periods_total": period_data.total_periods,
        "periods_remaining": period_data.total_periods - period_data.period_idx,
    }

    # Add period price difference attributes based on sensor type (step 4)
    if stats.period_price_diff is not None:
        if reverse_sort:
            # Peak price sensor: compare to daily maximum
            summary["period_price_diff_from_daily_max"] = stats.period_price_diff
            if stats.period_price_diff_pct is not None:
                summary["period_price_diff_from_daily_max_%"] = stats.period_price_diff_pct
        else:
            # Best price sensor: compare to daily minimum
            summary["period_price_diff_from_daily_min"] = stats.period_price_diff
            if stats.period_price_diff_pct is not None:
                summary["period_price_diff_from_daily_min_%"] = stats.period_price_diff_pct

    return summary


def _extract_period_summaries(
    periods: list[list[dict]],
    all_prices: list[dict],
    price_context: dict[str, Any],
    thresholds: ThresholdConfig,
) -> list[dict]:
    """
    Extract complete period summaries with all aggregated attributes.

    Returns sensor-ready period summaries with:
    - Timestamps and positioning (start, end, hour, minute, time)
    - Aggregated price statistics (price_avg, price_min, price_max, price_spread)
    - Volatility categorization (low/moderate/high/very_high based on absolute spread)
    - Rating difference percentage (aggregated from intervals)
    - Period price differences (period_price_diff_from_daily_min/max)
    - Aggregated level and rating_level
    - Interval count (number of 15-min intervals in period)

    All data is pre-calculated and ready for display - no further processing needed.

    Args:
        periods: List of periods, where each period is a list of interval dictionaries
        all_prices: All price data from the API (enriched with level, difference, rating_level)
        price_context: Dictionary with ref_prices and avg_prices per day
        thresholds: Threshold configuration for calculations

    """
    # Build lookup dictionary for full price data by timestamp
    price_lookup: dict[str, dict] = {}
    for price_data in all_prices:
        starts_at = dt_util.parse_datetime(price_data["startsAt"])
        if starts_at:
            starts_at = dt_util.as_local(starts_at)
            price_lookup[starts_at.isoformat()] = price_data

    summaries = []
    total_periods = len(periods)

    for period_idx, period in enumerate(periods, 1):
        if not period:
            continue

        first_interval = period[0]
        last_interval = period[-1]

        start_time = first_interval.get("interval_start")
        end_time = last_interval.get("interval_end")

        if not start_time or not end_time:
            continue

        # Look up full price data for each interval in the period
        period_price_data: list[dict] = []
        for interval in period:
            start = interval.get("interval_start")
            if not start:
                continue
            start_iso = start.isoformat()
            price_data = price_lookup.get(start_iso)
            if price_data:
                period_price_data.append(price_data)

        # Calculate aggregated level and rating_level
        aggregated_level = None
        aggregated_rating = None

        if period_price_data:
            # Aggregate level (from API's "level" field)
            aggregated_level = aggregate_period_levels(period_price_data)

            # Aggregate rating_level (from calculated "rating_level" and "difference" fields)
            if thresholds.threshold_low is not None and thresholds.threshold_high is not None:
                aggregated_rating, _ = aggregate_period_ratings(
                    period_price_data,
                    thresholds.threshold_low,
                    thresholds.threshold_high,
                )

        # Calculate price statistics (in minor units: ct/øre)
        price_stats = _calculate_period_price_statistics(period_price_data)

        # Calculate period price difference from daily reference
        period_price_diff, period_price_diff_pct = _calculate_period_price_diff(
            price_stats["price_avg"], start_time, price_context
        )

        # Calculate volatility (categorical) and aggregated rating difference (numeric)
        volatility = calculate_volatility_level(
            price_stats["price_spread"],
            threshold_moderate=thresholds.threshold_volatility_moderate,
            threshold_high=thresholds.threshold_volatility_high,
            threshold_very_high=thresholds.threshold_volatility_very_high,
        ).lower()
        rating_difference_pct = _calculate_aggregated_rating_difference(period_price_data)

        # Build period data and statistics objects
        period_data = PeriodData(
            start_time=start_time,
            end_time=end_time,
            period_length=len(period),
            period_idx=period_idx,
            total_periods=total_periods,
        )

        stats = PeriodStatistics(
            aggregated_level=aggregated_level,
            aggregated_rating=aggregated_rating,
            rating_difference_pct=rating_difference_pct,
            price_avg=price_stats["price_avg"],
            price_min=price_stats["price_min"],
            price_max=price_stats["price_max"],
            price_spread=price_stats["price_spread"],
            volatility=volatility,
            period_price_diff=period_price_diff,
            period_price_diff_pct=period_price_diff_pct,
        )

        # Build complete period summary
        summary = _build_period_summary_dict(period_data, stats, reverse_sort=thresholds.reverse_sort)
        summaries.append(summary)

    return summaries


def _recalculate_period_metadata(periods: list[dict]) -> None:
    """
    Recalculate period metadata after merging periods.

    Updates period_position, periods_total, and periods_remaining for all periods
    based on chronological order.

    This must be called after _resolve_period_overlaps() to ensure metadata
    reflects the final merged period list.

    Args:
        periods: List of period summary dicts (mutated in-place)

    """
    if not periods:
        return

    # Sort periods chronologically by start time
    periods.sort(key=lambda p: p.get("start") or dt_util.now())

    # Update metadata for all periods
    total_periods = len(periods)

    for position, period in enumerate(periods, 1):
        period["period_position"] = position
        period["periods_total"] = total_periods
        period["periods_remaining"] = total_periods - position


def filter_periods_by_volatility(
    periods_data: dict[str, Any],
    min_volatility: str,
) -> dict[str, Any]:
    """
    Filter calculated periods based on their internal volatility.

    This applies period-level volatility filtering AFTER periods have been calculated.
    Removes periods that don't meet the minimum volatility requirement based on their
    own price spread (volatility attribute), not the daily volatility.

    Args:
        periods_data: Dict with "periods" and "intervals" lists from calculate_periods_with_relaxation()
        min_volatility: Minimum volatility level required ("low", "moderate", "high", "very_high")

    Returns:
        Filtered periods_data dict with updated periods, intervals, and metadata.

    """
    periods = periods_data.get("periods", [])
    if not periods:
        return periods_data

    # "low" means no filtering (accept any volatility level)
    if min_volatility == "low":
        return periods_data

    # Define volatility hierarchy (LOW < MODERATE < HIGH < VERY_HIGH)
    volatility_levels = ["LOW", "MODERATE", "HIGH", "VERY_HIGH"]

    # Map filter config values to actual level names
    config_to_level = {
        "low": "LOW",
        "moderate": "MODERATE",
        "high": "HIGH",
        "very_high": "VERY_HIGH",
    }

    min_level = config_to_level.get(min_volatility, "LOW")

    # Filter periods based on their volatility
    filtered_periods = []
    for period in periods:
        period_volatility = period.get("volatility", "MODERATE")

        # Check if period's volatility meets or exceeds minimum requirement
        try:
            period_idx = volatility_levels.index(period_volatility)
            min_idx = volatility_levels.index(min_level)
        except ValueError:
            # If level not found, don't filter out this period
            filtered_periods.append(period)
        else:
            if period_idx >= min_idx:
                filtered_periods.append(period)

    # If no periods left after filtering, return empty structure
    if not filtered_periods:
        return {
            "periods": [],
            "intervals": [],
            "metadata": {
                "total_intervals": 0,
                "total_periods": 0,
                "config": periods_data.get("metadata", {}).get("config", {}),
            },
        }

    # Collect intervals from filtered periods
    filtered_intervals = []
    for period in filtered_periods:
        filtered_intervals.extend(period.get("intervals", []))

    # Update metadata
    return {
        "periods": filtered_periods,
        "intervals": filtered_intervals,
        "metadata": {
            "total_intervals": len(filtered_intervals),
            "total_periods": len(filtered_periods),
            "config": periods_data.get("metadata", {}).get("config", {}),
        },
    }


def _group_periods_by_day(periods: list[dict]) -> dict[date, list[dict]]:
    """
    Group periods by the day they end in.

    This ensures periods crossing midnight are counted towards the day they end,
    not the day they start. Example: Period 23:00 yesterday - 02:00 today counts
    as "today" since it ends today.

    Args:
        periods: List of period summary dicts with "start" and "end" datetime

    Returns:
        Dict mapping date to list of periods ending on that date

    """
    periods_by_day: dict[date, list[dict]] = {}

    for period in periods:
        # Use end time for grouping so periods crossing midnight are counted
        # towards the day they end (more relevant for min_periods check)
        end_time = period.get("end")
        if end_time:
            day = end_time.date()
            periods_by_day.setdefault(day, []).append(period)

    return periods_by_day


def _group_prices_by_day(all_prices: list[dict]) -> dict[date, list[dict]]:
    """
    Group price intervals by the day they belong to (today and future only).

    Args:
        all_prices: List of price dicts with "startsAt" timestamp

    Returns:
        Dict mapping date to list of price intervals for that day (only today and future)

    """
    today = dt_util.now().date()
    prices_by_day: dict[date, list[dict]] = {}

    for price in all_prices:
        starts_at = dt_util.parse_datetime(price["startsAt"])
        if starts_at:
            price_date = dt_util.as_local(starts_at).date()
            # Only include today and future days
            if price_date >= today:
                prices_by_day.setdefault(price_date, []).append(price)

    return prices_by_day


def _check_min_periods_per_day(periods: list[dict], min_periods: int, all_prices: list[dict]) -> bool:
    """
    Check if minimum periods requirement is met for each day individually.

    Returns True if we should STOP relaxation (enough periods found per day).
    Returns False if we should CONTINUE relaxation (not enough periods yet).

    Args:
        periods: List of period summary dicts
        min_periods: Minimum number of periods required per day
        all_prices: All available price intervals (used to determine which days have data)

    Returns:
        True if every day with price data has at least min_periods, False otherwise

    """
    if not periods:
        return False  # No periods at all, continue relaxation

    # Get all days that have price data (today and future only, not yesterday)
    today = dt_util.now().date()
    available_days = set()
    for price in all_prices:
        starts_at = dt_util.parse_datetime(price["startsAt"])
        if starts_at:
            price_date = dt_util.as_local(starts_at).date()
            # Only count today and future days (not yesterday)
            if price_date >= today:
                available_days.add(price_date)

    if not available_days:
        return False  # No price data for today/future, continue relaxation

    # Group found periods by day
    periods_by_day = _group_periods_by_day(periods)

    # Check each day with price data: ALL must have at least min_periods
    # Only count standalone periods (exclude extensions)
    for day in available_days:
        day_periods = periods_by_day.get(day, [])
        # Count only standalone periods (not extensions)
        standalone_count = sum(1 for p in day_periods if not p.get("is_extension"))
        if standalone_count < min_periods:
            _LOGGER.debug(
                "Day %s has only %d standalone periods (need %d) - continuing relaxation",
                day,
                standalone_count,
                min_periods,
            )
            return False  # This day doesn't have enough, continue relaxation

    # All days with price data have enough periods, stop relaxation
    return True


def calculate_periods_with_relaxation(  # noqa: PLR0913, PLR0915 - Per-day relaxation requires many parameters and statements
    all_prices: list[dict],
    *,
    config: PeriodConfig,
    enable_relaxation: bool,
    min_periods: int,
    relaxation_step_pct: int,
    should_show_callback: Callable[[str | None, str | None], bool],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Calculate periods with optional per-day filter relaxation.

    NEW: Each day gets its own independent relaxation loop. Today can be in Phase 1
    while tomorrow is in Phase 3, ensuring each day finds enough periods.

    If min_periods is not reached with normal filters, this function gradually
    relaxes filters in multiple phases FOR EACH DAY SEPARATELY:

    Phase 1: Increase flex threshold step-by-step (up to 4 attempts)
    Phase 2: Disable volatility filter (set to "any")
    Phase 3: Disable level filter (set to "any")

    Args:
        all_prices: All price data points
        config: Base period configuration
        enable_relaxation: Whether relaxation is enabled
        min_periods: Minimum number of periods required PER DAY
        relaxation_step_pct: Percentage of original flex to add per relaxation step
        should_show_callback: Callback function(volatility_override, level_override) -> bool
                             Returns True if periods should be shown with given filter overrides.
                             Pass None to use original configured filter values.

    Returns:
        Tuple of (periods_result, relaxation_metadata):
        - periods_result: Same format as calculate_periods() output, with periods from all days
        - relaxation_metadata: Dict with relaxation information (aggregated across all days)

    """
    # Compact INFO-level summary
    period_type = "PEAK PRICE" if config.reverse_sort else "BEST PRICE"
    relaxation_status = "ON" if enable_relaxation else "OFF"
    if enable_relaxation:
        _LOGGER.info(
            "Calculating %s periods: relaxation=%s, target=%d/day, flex=%.1f%%",
            period_type,
            relaxation_status,
            min_periods,
            abs(config.flex) * 100,
        )
    else:
        _LOGGER.info(
            "Calculating %s periods: relaxation=%s, flex=%.1f%%",
            period_type,
            relaxation_status,
            abs(config.flex) * 100,
        )

    # Detailed DEBUG-level context header
    period_type_full = "PEAK PRICE (most expensive)" if config.reverse_sort else "BEST PRICE (cheapest)"
    _LOGGER.debug(
        "%s========== %s PERIODS ==========",
        INDENT_L0,
        period_type_full,
    )
    _LOGGER.debug(
        "%sRelaxation: %s",
        INDENT_L0,
        "ENABLED (user setting: ON)" if enable_relaxation else "DISABLED by user configuration",
    )
    _LOGGER.debug(
        "%sBase config: flex=%.1f%%, min_length=%d min",
        INDENT_L0,
        abs(config.flex) * 100,
        config.min_period_length,
    )
    if enable_relaxation:
        _LOGGER.debug(
            "%sRelaxation target: %d periods per day",
            INDENT_L0,
            min_periods,
        )
        _LOGGER.debug(
            "%sRelaxation strategy: %.1f%% flex increment per step (4 flex levels x 4 filter combinations)",
            INDENT_L0,
            relaxation_step_pct,
        )
        _LOGGER.debug(
            "%sEarly exit: After EACH filter combination when target reached",
            INDENT_L0,
        )
    _LOGGER.debug(
        "%s=============================================",
        INDENT_L0,
    )

    # Group prices by day (for both relaxation enabled/disabled)
    prices_by_day = _group_prices_by_day(all_prices)

    if not prices_by_day:
        # No price data for today/future
        _LOGGER.warning(
            "No price data available for today/future - cannot calculate periods",
        )
        return {"periods": [], "metadata": {}, "reference_data": {}}, {
            "relaxation_active": False,
            "relaxation_attempted": False,
            "min_periods_requested": min_periods if enable_relaxation else 0,
            "periods_found": 0,
        }

    total_days = len(prices_by_day)
    _LOGGER.info(
        "Calculating baseline periods for %d days...",
        total_days,
    )

    # === BASELINE CALCULATION (same for both modes) ===
    all_periods: list[dict] = []
    all_phases_used: list[str] = []
    relaxation_was_needed = False
    days_meeting_requirement = 0

    for day, day_prices in sorted(prices_by_day.items()):
        _LOGGER.debug(
            "%sProcessing day %s with %d price intervals",
            INDENT_L1,
            day,
            len(day_prices),
        )

        # Calculate baseline periods for this day
        day_result = calculate_periods(day_prices, config=config)
        day_periods = day_result["periods"]
        standalone_count = len([p for p in day_periods if not p.get("is_extension")])

        _LOGGER.debug(
            "%sDay %s baseline: Found %d standalone periods%s",
            INDENT_L1,
            day,
            standalone_count,
            f" (need {min_periods})" if enable_relaxation else "",
        )

        # Check if relaxation is needed for this day
        if not enable_relaxation or standalone_count >= min_periods:
            # No relaxation needed/possible - use baseline
            if enable_relaxation:
                _LOGGER.debug(
                    "%sDay %s: Target reached with baseline - no relaxation needed",
                    INDENT_L1,
                    day,
                )
            all_periods.extend(day_periods)
            days_meeting_requirement += 1
            continue

        # === RELAXATION PATH (only when enabled AND needed) ===
        _LOGGER.debug(
            "%sDay %s: Baseline insufficient - starting relaxation",
            INDENT_L1,
            day,
        )
        relaxation_was_needed = True

        # Run full relaxation for this specific day
        day_relaxed_result, day_metadata = _relax_single_day(
            day_prices=day_prices,
            config=config,
            min_periods=min_periods,
            relaxation_step_pct=relaxation_step_pct,
            should_show_callback=should_show_callback,
            baseline_periods=day_periods,
            day_label=str(day),
        )

        all_periods.extend(day_relaxed_result["periods"])
        if day_metadata.get("phases_used"):
            all_phases_used.extend(day_metadata["phases_used"])

        # Check if this day met the requirement after relaxation
        day_standalone = len([p for p in day_relaxed_result["periods"] if not p.get("is_extension")])
        if day_standalone >= min_periods:
            days_meeting_requirement += 1

    # Sort all periods by start time
    all_periods.sort(key=lambda p: p["start"])

    # Recalculate metadata for combined periods
    _recalculate_period_metadata(all_periods)

    # Build combined result
    if all_periods:
        # Use the last day's result as template
        final_result = day_result.copy()
        final_result["periods"] = all_periods
    else:
        final_result = {"periods": [], "metadata": {}, "reference_data": {}}

    total_standalone = len([p for p in all_periods if not p.get("is_extension")])

    return final_result, {
        "relaxation_active": relaxation_was_needed,
        "relaxation_attempted": relaxation_was_needed,
        "min_periods_requested": min_periods,
        "periods_found": total_standalone,
        "phases_used": list(set(all_phases_used)),  # Unique phases used across all days
        "days_processed": total_days,
        "days_meeting_requirement": days_meeting_requirement,
        "relaxation_incomplete": days_meeting_requirement < total_days,
    }


def _relax_single_day(  # noqa: PLR0913 - Comprehensive filter relaxation per day
    day_prices: list[dict],
    config: PeriodConfig,
    min_periods: int,
    relaxation_step_pct: int,
    should_show_callback: Callable[[str | None, str | None], bool],
    baseline_periods: list[dict],
    day_label: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Run comprehensive relaxation for a single day.

    NEW STRATEGY: For each flex level, try all filter combinations before increasing flex.
    This finds solutions faster by relaxing filters first (cheaper than increasing flex).

    Per flex level (6.25%, 7.5%, 8.75%, 10%), try in order:
    1. Original filters (volatility=configured, level=configured)
    2. Relax only volatility (volatility=any, level=configured)
    3. Relax only level (volatility=configured, level=any)
    4. Relax both (volatility=any, level=any)

    This ensures we find the minimal relaxation needed. Example:
    - If periods exist at flex=6.25% with level=any, we find them before trying flex=7.5%
    - If periods need both filters relaxed, we try that before increasing flex further

    Args:
        day_prices: Price data for this specific day only
        config: Base period configuration
        min_periods: Minimum periods needed for this day
        relaxation_step_pct: Relaxation increment percentage
        should_show_callback: Filter visibility callback(volatility_override, level_override)
                             Returns True if periods should be shown with given overrides.
        baseline_periods: Periods found with normal filters
        day_label: Label for logging (e.g., "2025-11-11")

    Returns:
        Tuple of (periods_result, metadata) for this day

    """
    accumulated_periods = baseline_periods.copy()
    original_flex = abs(config.flex)
    relaxation_increment = original_flex * (relaxation_step_pct / 100.0)
    phases_used = []
    relaxed_result = None

    baseline_standalone = len([p for p in baseline_periods if not p.get("is_extension")])

    # 4 flex levels: original + 3 steps (e.g., 5% → 6.25% → 7.5% → 8.75% → 10%)
    for flex_step in range(1, 5):
        new_flex = original_flex + (flex_step * relaxation_increment)
        new_flex = min(new_flex, 100.0)

        if config.reverse_sort:
            new_flex = -new_flex

        # Try filter combinations for this flex level
        # Each tuple contains: volatility_override, level_override, label_suffix
        filter_attempts = [
            (None, None, ""),  # Original config
            ("any", None, "+volatility_any"),  # Relax volatility only
            (None, "any", "+level_any"),  # Relax level only
            ("any", "any", "+all_filters_any"),  # Relax both
        ]

        for vol_override, lvl_override, label_suffix in filter_attempts:
            # Check if this combination is allowed by user config
            if not should_show_callback(vol_override, lvl_override):
                continue

            # Calculate periods with this flex + filter combination
            relaxed_config = config._replace(flex=new_flex)
            relaxed_result = calculate_periods(day_prices, config=relaxed_config)
            new_periods = relaxed_result["periods"]

            # Build relaxation level label BEFORE marking periods
            flex_pct = round(abs(new_flex) * 100, 1)
            relaxation_level = f"price_diff_{flex_pct}%{label_suffix}"
            phases_used.append(relaxation_level)

            # Mark NEW periods with their specific relaxation metadata BEFORE merging
            for period in new_periods:
                period["relaxation_active"] = True
                # Set the metadata immediately - this preserves which phase found this period
                _mark_periods_with_relaxation([period], relaxation_level, original_flex, abs(new_flex))

            # Merge with accumulated periods
            merged, standalone_count = _resolve_period_overlaps(
                accumulated_periods, new_periods, config.min_period_length, baseline_periods
            )

            total_standalone = standalone_count + baseline_standalone
            filters_label = label_suffix if label_suffix else "(original filters)"

            _LOGGER.debug(
                "%sDay %s flex=%.1f%% %s: found %d new periods, %d standalone total (%d baseline + %d new)",
                INDENT_L2,
                day_label,
                flex_pct,
                filters_label,
                len(new_periods),
                total_standalone,
                baseline_standalone,
                standalone_count,
            )

            accumulated_periods = merged.copy()

            # ✅ EARLY EXIT: Check after EACH filter combination
            if total_standalone >= min_periods:
                _LOGGER.info(
                    "Day %s: Success with flex=%.1f%% %s - found %d/%d periods (%d baseline + %d from relaxation)",
                    day_label,
                    flex_pct,
                    filters_label,
                    total_standalone,
                    min_periods,
                    baseline_standalone,
                    standalone_count,
                )
                _recalculate_period_metadata(merged)
                result = relaxed_result.copy()
                result["periods"] = merged
                return result, {"phases_used": phases_used}

    # ❌ Only reach here if ALL phases exhausted WITHOUT reaching min_periods
    final_standalone = len([p for p in accumulated_periods if not p.get("is_extension")])
    new_standalone = final_standalone - baseline_standalone

    _LOGGER.warning(
        "Day %s: All relaxation phases exhausted WITHOUT reaching goal - "
        "found %d/%d standalone periods (%d baseline + %d from relaxation)",
        day_label,
        final_standalone,
        min_periods,
        baseline_standalone,
        new_standalone,
    )

    _recalculate_period_metadata(accumulated_periods)

    if relaxed_result:
        result = relaxed_result.copy()
    else:
        result = {"periods": accumulated_periods, "metadata": {}, "reference_data": {}}
    result["periods"] = accumulated_periods

    return result, {"phases_used": phases_used}


def _mark_periods_with_relaxation(
    periods: list[dict],
    relaxation_level: str,
    original_threshold: float,
    applied_threshold: float,
) -> None:
    """
    Mark periods with relaxation information (mutates period dicts in-place).

    Uses consistent 'relaxation_*' prefix for all relaxation-related attributes.

    Args:
        periods: List of period dicts to mark
        relaxation_level: String describing the relaxation level
        original_threshold: Original flex threshold value (decimal, e.g., 0.19 for 19%)
        applied_threshold: Actually applied threshold value (decimal, e.g., 0.25 for 25%)

    """
    for period in periods:
        period["relaxation_active"] = True
        period["relaxation_level"] = relaxation_level
        # Convert decimal to percentage for display (0.19 → 19.0)
        period["relaxation_threshold_original_%"] = round(original_threshold * 100, 1)
        period["relaxation_threshold_applied_%"] = round(applied_threshold * 100, 1)


def _resolve_period_overlaps(  # noqa: PLR0912, PLR0915, C901 - Complex overlap resolution with replacement and extension logic
    existing_periods: list[dict],
    new_relaxed_periods: list[dict],
    min_period_length: int,
    baseline_periods: list[dict] | None = None,
) -> tuple[list[dict], int]:
    """
    Resolve overlaps between existing periods and newly found relaxed periods.

    Existing periods (baseline + previous relaxation phases) have priority and remain unchanged.
    Newly relaxed periods are adjusted to not overlap with existing periods.

    After splitting relaxed periods to avoid overlaps, each segment is validated against
    min_period_length. Segments shorter than this threshold are discarded.

    This function is called incrementally after each relaxation phase:
    - Phase 1: existing = accumulated, baseline = baseline
    - Phase 2: existing = accumulated, baseline = baseline
    - Phase 3: existing = accumulated, baseline = baseline

    Args:
        existing_periods: All previously found periods (baseline + earlier relaxation phases)
        new_relaxed_periods: Periods found in current relaxation phase (will be adjusted)
        min_period_length: Minimum period length in minutes (segments shorter than this are discarded)
        baseline_periods: Original baseline periods (for extension detection). Extensions only count
                         against baseline, not against other relaxation periods.

    Returns:
        Tuple of (merged_periods, count_standalone_relaxed):
        - merged_periods: All periods (existing + adjusted new), sorted by start time
        - count_standalone_relaxed: Number of new relaxed periods that count toward min_periods
                                   (excludes extensions of baseline periods only)

    """
    if baseline_periods is None:
        baseline_periods = existing_periods  # Fallback to existing if not provided

    _LOGGER.debug(
        "%s_resolve_period_overlaps called: existing=%d, new=%d, baseline=%d",
        INDENT_L3,
        len(existing_periods),
        len(new_relaxed_periods),
        len(baseline_periods),
    )

    if not new_relaxed_periods:
        return existing_periods.copy(), 0

    if not existing_periods:
        # No overlaps possible - all relaxed periods are standalone
        return new_relaxed_periods.copy(), len(new_relaxed_periods)

    merged = existing_periods.copy()
    count_standalone = 0

    for relaxed in new_relaxed_periods:
        # Skip if this exact period is already in existing_periods (duplicate from previous relaxation attempt)
        # Compare current start/end (before any splitting), not original_start/end
        # Note: original_start/end are set AFTER splitting and indicate split segments from same source
        relaxed_start = relaxed["start"]
        relaxed_end = relaxed["end"]

        is_duplicate = False
        for existing in existing_periods:
            # Only compare with existing periods that haven't been adjusted (unsplit originals)
            # If existing has original_start/end, it's already a split segment - skip comparison
            if "original_start" in existing:
                continue

            existing_start = existing["start"]
            existing_end = existing["end"]

            # Duplicate if same boundaries (within 1 minute tolerance)
            tolerance_seconds = 60  # 1 minute tolerance for duplicate detection
            if (
                abs((relaxed_start - existing_start).total_seconds()) < tolerance_seconds
                and abs((relaxed_end - existing_end).total_seconds()) < tolerance_seconds
            ):
                is_duplicate = True
                _LOGGER.debug(
                    "%sSkipping duplicate period %s-%s (already exists from previous relaxation)",
                    INDENT_L4,
                    relaxed_start.strftime("%H:%M"),
                    relaxed_end.strftime("%H:%M"),
                )
                break

        if is_duplicate:
            continue

        # Find all overlapping existing periods
        overlaps = []
        for existing in existing_periods:
            existing_start = existing["start"]
            existing_end = existing["end"]

            # Check for overlap
            if relaxed_start < existing_end and relaxed_end > existing_start:
                overlaps.append((existing_start, existing_end))

        if not overlaps:
            # No overlap - check if adjacent to baseline period (= extension)
            # Only baseline extensions don't count toward min_periods
            is_extension = False
            for baseline in baseline_periods:
                if relaxed_end == baseline["start"] or relaxed_start == baseline["end"]:
                    is_extension = True
                    break

            if is_extension:
                relaxed["is_extension"] = True
                _LOGGER.debug(
                    "%sMarking period %s-%s as extension (no overlap, adjacent to baseline)",
                    INDENT_L4,
                    relaxed_start.strftime("%H:%M"),
                    relaxed_end.strftime("%H:%M"),
                )
            else:
                count_standalone += 1

            merged.append(relaxed)
        else:
            # Has overlaps - check if this new period extends BASELINE periods
            # Extension = new period encompasses/extends baseline period(s)
            # Note: If new period encompasses OTHER RELAXED periods, that's a replacement, not extension!
            is_extension = False
            periods_to_replace = []

            for existing in existing_periods:
                existing_start = existing["start"]
                existing_end = existing["end"]

                # Check if new period completely encompasses existing period
                if relaxed_start <= existing_start and relaxed_end >= existing_end:
                    # Is this existing period a BASELINE period?
                    is_baseline = any(
                        bp["start"] == existing_start and bp["end"] == existing_end for bp in baseline_periods
                    )

                    if is_baseline:
                        # Extension of baseline → counts as extension
                        is_extension = True
                        _LOGGER.debug(
                            "%sNew period %s-%s extends BASELINE period %s-%s",
                            INDENT_L4,
                            relaxed_start.strftime("%H:%M"),
                            relaxed_end.strftime("%H:%M"),
                            existing_start.strftime("%H:%M"),
                            existing_end.strftime("%H:%M"),
                        )
                    else:
                        # Encompasses another relaxed period → REPLACEMENT, not extension
                        periods_to_replace.append(existing)
                        _LOGGER.debug(
                            "%sNew period %s-%s replaces relaxed period %s-%s (larger is better)",
                            INDENT_L4,
                            relaxed_start.strftime("%H:%M"),
                            relaxed_end.strftime("%H:%M"),
                            existing_start.strftime("%H:%M"),
                            existing_end.strftime("%H:%M"),
                        )

            # Remove periods that are being replaced by this larger period
            if periods_to_replace:
                for period_to_remove in periods_to_replace:
                    if period_to_remove in merged:
                        merged.remove(period_to_remove)
                        _LOGGER.debug(
                            "%sReplaced period %s-%s with larger period %s-%s",
                            INDENT_L5,
                            period_to_remove["start"].strftime("%H:%M"),
                            period_to_remove["end"].strftime("%H:%M"),
                            relaxed_start.strftime("%H:%M"),
                            relaxed_end.strftime("%H:%M"),
                        )

            # Split the relaxed period into non-overlapping segments
            segments = _split_period_by_overlaps(relaxed_start, relaxed_end, overlaps)

            # If no segments (completely overlapped), but we replaced periods, add the full period
            if not segments and periods_to_replace:
                _LOGGER.debug(
                    "%sAdding full replacement period %s-%s (no non-overlapping segments)",
                    INDENT_L5,
                    relaxed_start.strftime("%H:%M"),
                    relaxed_end.strftime("%H:%M"),
                )
                # Mark as extension if it extends baseline, otherwise standalone
                if is_extension:
                    relaxed["is_extension"] = True
                merged.append(relaxed)
                continue

            for seg_start, seg_end in segments:
                # Calculate segment duration in minutes
                segment_duration_minutes = int((seg_end - seg_start).total_seconds() / 60)

                # Skip segment if it's too short
                if segment_duration_minutes < min_period_length:
                    continue

                # Create adjusted period segment
                adjusted_period = relaxed.copy()
                adjusted_period["start"] = seg_start
                adjusted_period["end"] = seg_end
                adjusted_period["duration_minutes"] = segment_duration_minutes

                # Mark as adjusted and potentially as extension
                adjusted_period["adjusted_for_overlap"] = True
                adjusted_period["original_start"] = relaxed_start
                adjusted_period["original_end"] = relaxed_end

                # If the original period was an extension, all its segments are extensions too
                # OR if segment is adjacent to baseline
                segment_is_extension = is_extension
                if not segment_is_extension:
                    # Check if segment is directly adjacent to BASELINE period
                    for baseline in baseline_periods:
                        if seg_end == baseline["start"] or seg_start == baseline["end"]:
                            segment_is_extension = True
                            break

                if segment_is_extension:
                    adjusted_period["is_extension"] = True
                    _LOGGER.debug(
                        "%sMarking segment %s-%s as extension (original was extension or adjacent to baseline)",
                        INDENT_L5,
                        seg_start.strftime("%H:%M"),
                        seg_end.strftime("%H:%M"),
                    )
                else:
                    # Standalone segment counts toward min_periods
                    count_standalone += 1

                merged.append(adjusted_period)

    # Sort all periods by start time
    merged.sort(key=lambda p: p["start"])

    # Count ACTUAL standalone periods in final merged list (not just newly added ones)
    # This accounts for replacements where old standalone was replaced by new standalone
    final_standalone_count = len([p for p in merged if not p.get("is_extension")])

    # Subtract baseline standalone count to get NEW standalone from this relaxation
    baseline_standalone_count = len([p for p in baseline_periods if not p.get("is_extension")])
    new_standalone_count = final_standalone_count - baseline_standalone_count

    return merged, new_standalone_count


def _split_period_by_overlaps(
    period_start: datetime,
    period_end: datetime,
    overlaps: list[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    """
    Split a time period into segments that don't overlap with given ranges.

    Args:
        period_start: Start of period to split
        period_end: End of period to split
        overlaps: List of (start, end) tuples representing overlapping ranges

    Returns:
        List of (start, end) tuples for non-overlapping segments

    Example:
        period: 09:00-15:00
        overlaps: [(10:00-12:00), (14:00-16:00)]
        result: [(09:00-10:00), (12:00-14:00)]

    """
    # Sort overlaps by start time
    sorted_overlaps = sorted(overlaps, key=lambda x: x[0])

    segments = []
    current_pos = period_start

    for overlap_start, overlap_end in sorted_overlaps:
        # Add segment before this overlap (if any)
        if current_pos < overlap_start:
            segments.append((current_pos, overlap_start))

        # Move position past this overlap
        current_pos = max(current_pos, overlap_end)

    # Add final segment after all overlaps (if any)
    if current_pos < period_end:
        segments.append((current_pos, period_end))

    return segments
