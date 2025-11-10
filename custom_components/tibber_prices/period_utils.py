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
    # Build complete period summary (following attribute ordering from copilot-instructions.md)
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


def calculate_periods_with_relaxation(  # noqa: PLR0913, PLR0912, PLR0915, C901 - Complex multi-phase relaxation
    all_prices: list[dict],
    *,
    config: PeriodConfig,
    enable_relaxation: bool,
    min_periods: int,
    relaxation_step_pct: int,
    should_show_callback: Callable[[str | None, str | None], bool],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Calculate periods with optional filter relaxation.

    If min_periods is not reached with normal filters, this function gradually
    relaxes filters in multiple phases:

    Phase 1: Increase flex threshold step-by-step (up to 4 attempts)
    Phase 2: Disable volatility filter (set to "any")
    Phase 3: Disable level filter (set to "any")

    Args:
        all_prices: All price data points
        config: Base period configuration
        enable_relaxation: Whether relaxation is enabled
        min_periods: Minimum number of periods required (only used if enable_relaxation=True)
        relaxation_step_pct: Percentage of original flex to add per relaxation step
        should_show_callback: Callback function(volatility_override, level_override) -> bool
                             Returns True if periods should be shown with given filter overrides.
                             Pass None to use original configured filter values.

    Returns:
        Tuple of (periods_result, relaxation_metadata):
        - periods_result: Same format as calculate_periods() output
        - relaxation_metadata: Dict with relaxation information

    """
    # If relaxation is disabled, just run normal calculation
    if not enable_relaxation:
        periods_result = calculate_periods(all_prices, config=config)
        return periods_result, {
            "relaxation_active": False,
            "relaxation_attempted": False,
            "min_periods_requested": 0,
            "periods_found": len(periods_result["periods"]),
        }

    # Phase 0: Try with normal filters first
    # Check if periods should be shown with current filters
    if not should_show_callback(None, None):
        # Filters prevent showing any periods - skip normal calculation
        baseline_periods = []
        periods_found = 0
    else:
        baseline_result = calculate_periods(all_prices, config=config)
        baseline_periods = baseline_result["periods"]
        periods_found = len(baseline_periods)

    if periods_found >= min_periods:
        # Success with normal filters - reconstruct full result
        periods_result = calculate_periods(all_prices, config=config)
        return periods_result, {
            "relaxation_active": False,
            "relaxation_attempted": False,
            "min_periods_requested": min_periods,
            "periods_found": periods_found,
        }

    # Not enough periods - start relaxation
    # Keep accumulated_periods for incremental merging across phases
    accumulated_periods = baseline_periods.copy()
    _LOGGER.info(
        "Found %d baseline periods (need %d), starting filter relaxation",
        periods_found,
        min_periods,
    )

    original_flex = abs(config.flex)  # Use absolute value for calculations
    relaxation_increment = original_flex * (relaxation_step_pct / 100.0)
    phases_used = []

    # Phase 1: Relax flex threshold (up to 4 attempts)
    for step in range(1, 5):
        new_flex = original_flex + (step * relaxation_increment)
        new_flex = min(new_flex, 100.0)  # Cap at 100%

        # Restore sign for best/peak price
        if config.reverse_sort:
            new_flex = -new_flex  # Peak price uses negative values

        relaxed_config = config._replace(flex=new_flex)
        relaxed_result = calculate_periods(all_prices, config=relaxed_config)
        new_relaxed_periods = relaxed_result["periods"]

        # Convert to percentage for display (0.25 → 25.0)
        relaxation_level = f"price_diff_{round(abs(new_flex) * 100, 1)}%"
        phases_used.append(relaxation_level)

        # Merge with accumulated periods (baseline + previous relaxation phases), resolve overlaps
        merged_periods, standalone_count = _resolve_period_overlaps(
            accumulated_periods, new_relaxed_periods, config.min_period_length
        )
        total_count = len(baseline_periods) + standalone_count

        _LOGGER.debug(
            "Relaxation attempt %d: flex=%.2f%%, found %d new periods (%d standalone, %d extensions), total %d periods",
            step,
            abs(new_flex) * 100,
            len(new_relaxed_periods),
            standalone_count,
            len(new_relaxed_periods) - standalone_count,
            total_count,
        )

        if total_count >= min_periods:
            # Mark relaxed periods (those not from baseline)
            for period in merged_periods:
                if period.get("relaxation_active"):
                    _mark_periods_with_relaxation(
                        [period],
                        relaxation_level,
                        original_flex,
                        abs(new_flex),
                    )

            # Recalculate metadata after merge (position, total, remaining)
            _recalculate_period_metadata(merged_periods)

            # Update accumulated periods for potential next phase
            accumulated_periods = merged_periods.copy()

            # Reconstruct result with merged periods
            periods_result = relaxed_result.copy()
            periods_result["periods"] = merged_periods

            return periods_result, {
                "relaxation_active": True,
                "relaxation_attempted": True,
                "min_periods_requested": min_periods,
                "periods_found": total_count,
                "phases_used": phases_used,
                "final_level": relaxation_level,
            }

    # Phase 2: Relax volatility filter + reset and increase threshold
    _LOGGER.info(
        "Phase 1 insufficient (%d/%d periods), trying Phase 2: relax volatility filter", total_count, min_periods
    )

    if should_show_callback("any", None):  # Volatility filter can be disabled
        # Phase 2: Try with reset threshold and volatility=any (up to 4 steps)
        for step in range(1, 5):
            new_flex = original_flex + (step * relaxation_increment)
            new_flex = min(new_flex, 100.0)  # Cap at 100%

            # Restore sign for best/peak price
            if config.reverse_sort:
                new_flex = -new_flex

            relaxed_config = config._replace(flex=new_flex)
            relaxed_result = calculate_periods(all_prices, config=relaxed_config)
            new_relaxed_periods = relaxed_result["periods"]

            relaxation_level = f"volatility_any+price_diff_{round(abs(new_flex) * 100, 1)}%"
            phases_used.append(relaxation_level)

            # Merge with accumulated periods (baseline + previous relaxation phases), resolve overlaps
            merged_periods, standalone_count = _resolve_period_overlaps(
                accumulated_periods, new_relaxed_periods, config.min_period_length
            )
            total_count = len(baseline_periods) + standalone_count

            _LOGGER.debug(
                "Phase 2 attempt %d (volatility=any, flex=%.2f%%): found %d new periods "
                "(%d standalone, %d extensions), total %d periods",
                step,
                abs(new_flex) * 100,
                len(new_relaxed_periods),
                standalone_count,
                len(new_relaxed_periods) - standalone_count,
                total_count,
            )

            if total_count >= min_periods:
                # Mark relaxed periods (those not from baseline)
                for period in merged_periods:
                    if period.get("relaxation_active"):
                        _mark_periods_with_relaxation(
                            [period],
                            relaxation_level,
                            original_flex,
                            abs(new_flex),
                        )

                # Recalculate metadata after merge (position, total, remaining)
                _recalculate_period_metadata(merged_periods)

                # Update accumulated periods for potential next phase
                accumulated_periods = merged_periods.copy()

                # Reconstruct result with merged periods
                periods_result = relaxed_result.copy()
                periods_result["periods"] = merged_periods

                return periods_result, {
                    "relaxation_active": True,
                    "relaxation_attempted": True,
                    "min_periods_requested": min_periods,
                    "periods_found": total_count,
                    "phases_used": phases_used,
                    "final_level": relaxation_level,
                }
    else:
        _LOGGER.debug("Phase 2 skipped: volatility filter prevents showing periods")

    # Phase 3: Relax level filter + reset and increase threshold
    _LOGGER.info("Phase 2 insufficient (%d/%d periods), trying Phase 3: relax level filter", total_count, min_periods)

    if should_show_callback("any", "any"):  # Both filters can be disabled
        # Phase 3: Try with reset threshold and both filters=any (up to 4 steps)
        for step in range(1, 5):
            new_flex = original_flex + (step * relaxation_increment)
            new_flex = min(new_flex, 100.0)  # Cap at 100%

            # Restore sign for best/peak price
            if config.reverse_sort:
                new_flex = -new_flex

            relaxed_config = config._replace(flex=new_flex)
            relaxed_result = calculate_periods(all_prices, config=relaxed_config)
            new_relaxed_periods = relaxed_result["periods"]

            relaxation_level = f"all_filters_off+price_diff_{round(abs(new_flex) * 100, 1)}%"
            phases_used.append(relaxation_level)

            # Merge with accumulated periods (baseline + previous relaxation phases), resolve overlaps
            merged_periods, standalone_count = _resolve_period_overlaps(
                accumulated_periods, new_relaxed_periods, config.min_period_length
            )
            total_count = len(baseline_periods) + standalone_count

            _LOGGER.debug(
                "Phase 3 attempt %d (all_filters=any, flex=%.2f%%): found %d new periods "
                "(%d standalone, %d extensions), total %d periods",
                step,
                abs(new_flex) * 100,
                len(new_relaxed_periods),
                standalone_count,
                len(new_relaxed_periods) - standalone_count,
                total_count,
            )

            if total_count >= min_periods:
                # Mark relaxed periods (those not from baseline)
                for period in merged_periods:
                    if period.get("relaxation_active"):
                        _mark_periods_with_relaxation(
                            [period],
                            relaxation_level,
                            original_flex,
                            abs(new_flex),
                        )

                # Recalculate metadata after merge (position, total, remaining)
                _recalculate_period_metadata(merged_periods)

                # Update accumulated periods (final result)
                accumulated_periods = merged_periods.copy()

                # Reconstruct result with merged periods

            if total_count >= min_periods:
                # Mark relaxed periods (those not from baseline)
                for period in merged_periods:
                    if period.get("relaxation_active"):
                        _mark_periods_with_relaxation(
                            [period],
                            relaxation_level,
                            original_flex,
                            abs(new_flex),
                        )

                # Reconstruct result with merged periods
                periods_result = relaxed_result.copy()
                periods_result["periods"] = merged_periods

                return periods_result, {
                    "relaxation_active": True,
                    "relaxation_attempted": True,
                    "min_periods_requested": min_periods,
                    "periods_found": total_count,
                    "phases_used": phases_used,
                    "final_level": relaxation_level,
                }
    else:
        _LOGGER.debug("Phase 3 skipped: level filter prevents showing periods")

    # All relaxation phases exhausted - return what we have
    # Use accumulated periods (may include baseline + partial relaxation results)
    _LOGGER.warning(
        "All relaxation phases exhausted - found only %d of %d requested periods. Returning available periods.",
        total_count,
        min_periods,
    )

    # Use accumulated periods (includes baseline + any successful relaxation merges)
    final_periods = accumulated_periods.copy()
    final_count = len(baseline_periods) + sum(
        1 for p in final_periods if p.get("relaxation_active") and not p.get("is_extension")
    )

    # Mark relaxed periods with final relaxation level (best we could do)
    if final_periods:
        final_relaxation_level = phases_used[-1] if phases_used else "none"

        for period in final_periods:
            if period.get("relaxation_active"):
                _mark_periods_with_relaxation(
                    [period],
                    final_relaxation_level,
                    original_flex,
                    original_flex,  # Return original since we couldn't meet minimum
                )

        # Recalculate metadata one final time
        _recalculate_period_metadata(final_periods)

    # Reconstruct result structure
    # Use last relaxed_result if available, otherwise baseline_result
    if "relaxed_result" in locals():
        periods_result = relaxed_result.copy()
    else:
        # No relaxation happened - construct minimal result
        periods_result = {"periods": [], "metadata": {}, "reference_data": {}}

    periods_result["periods"] = final_periods

    return periods_result, {
        "relaxation_active": True,
        "relaxation_attempted": True,
        "relaxation_incomplete": True,
        "min_periods_requested": min_periods,
        "periods_found": final_count,
        "phases_used": phases_used,
        "final_level": phases_used[-1] if phases_used else "none",
    }


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


def _resolve_period_overlaps(  # noqa: PLR0912 - Complex overlap resolution with segment validation
    existing_periods: list[dict],
    new_relaxed_periods: list[dict],
    min_period_length: int,
) -> tuple[list[dict], int]:
    """
    Resolve overlaps between existing periods and newly found relaxed periods.

    Existing periods (baseline + previous relaxation phases) have priority and remain unchanged.
    Newly relaxed periods are adjusted to not overlap with existing periods.

    After splitting relaxed periods to avoid overlaps, each segment is validated against
    min_period_length. Segments shorter than this threshold are discarded.

    This function is called incrementally after each relaxation phase:
    - Phase 1: existing = baseline
    - Phase 2: existing = baseline + Phase 1 results
    - Phase 3: existing = baseline + Phase 1 + Phase 2 results

    Args:
        existing_periods: All previously found periods (baseline + earlier relaxation phases)
        new_relaxed_periods: Periods found in current relaxation phase (will be adjusted)
        min_period_length: Minimum period length in minutes (segments shorter than this are discarded)

    Returns:
        Tuple of (merged_periods, count_standalone_relaxed):
        - merged_periods: All periods (existing + adjusted new), sorted by start time
        - count_standalone_relaxed: Number of new relaxed periods that count toward min_periods
                                   (excludes extensions of existing periods)

    """
    if not new_relaxed_periods:
        return existing_periods.copy(), 0

    if not existing_periods:
        # No overlaps possible - all relaxed periods are standalone
        return new_relaxed_periods.copy(), len(new_relaxed_periods)

    merged = existing_periods.copy()
    count_standalone = 0

    for relaxed in new_relaxed_periods:
        relaxed_start = relaxed["start"]
        relaxed_end = relaxed["end"]

        # Find all overlapping existing periods
        overlaps = []
        for existing in existing_periods:
            existing_start = existing["start"]
            existing_end = existing["end"]

            # Check for overlap
            if relaxed_start < existing_end and relaxed_end > existing_start:
                overlaps.append((existing_start, existing_end))

        if not overlaps:
            # No overlap - add as standalone period
            merged.append(relaxed)
            count_standalone += 1
        else:
            # Has overlaps - split the relaxed period into non-overlapping segments
            segments = _split_period_by_overlaps(relaxed_start, relaxed_end, overlaps)

            for seg_start, seg_end in segments:
                # Calculate segment duration in minutes
                segment_duration_minutes = int((seg_end - seg_start).total_seconds() / 60)

                # Skip segment if it's too short
                if segment_duration_minutes < min_period_length:
                    continue

                # Check if segment is directly adjacent to existing period (= extension)
                is_extension = False
                for existing in existing_periods:
                    if seg_end == existing["start"] or seg_start == existing["end"]:
                        is_extension = True
                        break

                # Create adjusted period segment
                adjusted_period = relaxed.copy()
                adjusted_period["start"] = seg_start
                adjusted_period["end"] = seg_end
                adjusted_period["duration_minutes"] = segment_duration_minutes

                # Mark as adjusted and potentially as extension
                adjusted_period["adjusted_for_overlap"] = True
                adjusted_period["original_start"] = relaxed_start
                adjusted_period["original_end"] = relaxed_end

                if is_extension:
                    adjusted_period["is_extension"] = True
                else:
                    # Standalone segment counts toward min_periods
                    count_standalone += 1

                merged.append(adjusted_period)

    # Sort all periods by start time
    merged.sort(key=lambda p: p["start"])

    return merged, count_standalone


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
