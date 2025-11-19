"""Period building and basic filtering logic."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from custom_components.tibber_prices.const import PRICE_LEVEL_MAPPING

if TYPE_CHECKING:
    from datetime import date

    from custom_components.tibber_prices.coordinator.time_service import TimeService

from .level_filtering import (
    apply_level_filter,
    check_interval_criteria,
)
from .types import IntervalCriteria

_LOGGER = logging.getLogger(__name__)

# Module-local log indentation (each module starts at level 0)
INDENT_L0 = ""  # Entry point / main function


def split_intervals_by_day(
    all_prices: list[dict], *, time: TimeService
) -> tuple[dict[date, list[dict]], dict[date, float]]:
    """Split intervals by day and calculate average price per day."""
    intervals_by_day: dict[date, list[dict]] = {}
    avg_price_by_day: dict[date, float] = {}

    for price_data in all_prices:
        dt = time.get_interval_time(price_data)
        if dt is None:
            continue
        date_key = dt.date()
        intervals_by_day.setdefault(date_key, []).append(price_data)

    for date_key, intervals in intervals_by_day.items():
        avg_price_by_day[date_key] = sum(float(p["total"]) for p in intervals) / len(intervals)

    return intervals_by_day, avg_price_by_day


def calculate_reference_prices(intervals_by_day: dict[date, list[dict]], *, reverse_sort: bool) -> dict[date, float]:
    """Calculate reference prices for each day (min for best, max for peak)."""
    ref_prices: dict[date, float] = {}
    for date_key, intervals in intervals_by_day.items():
        prices = [float(p["total"]) for p in intervals]
        ref_prices[date_key] = max(prices) if reverse_sort else min(prices)
    return ref_prices


def build_periods(  # noqa: PLR0913, PLR0915 - Complex period building logic requires many arguments and statements
    all_prices: list[dict],
    price_context: dict[str, Any],
    *,
    reverse_sort: bool,
    level_filter: str | None = None,
    gap_count: int = 0,
    time: TimeService,
) -> list[list[dict]]:
    """
    Build periods, allowing periods to cross midnight (day boundary).

    Periods are built day-by-day, comparing each interval to its own day's reference.
    When a day boundary is crossed, the current period is ended.
    Adjacent periods at midnight are merged in a later step.

    Args:
        all_prices: All price data points
        price_context: Dict with ref_prices, avg_prices, flex, min_distance_from_avg
        reverse_sort: True for peak price (high prices), False for best price (low prices)
        level_filter: Level filter string ("cheap", "expensive", "any", None)
        gap_count: Number of allowed consecutive intervals deviating by exactly 1 level step
        time: TimeService instance (required)

    """
    ref_prices = price_context["ref_prices"]
    avg_prices = price_context["avg_prices"]
    flex = price_context["flex"]
    min_distance_from_avg = price_context["min_distance_from_avg"]

    # Calculate level_order if level_filter is active
    level_order = None
    level_filter_active = False
    if level_filter and level_filter.lower() != "any":
        level_order = PRICE_LEVEL_MAPPING.get(level_filter.upper(), 0)
        level_filter_active = True
        filter_direction = "≥" if reverse_sort else "≤"
        gap_info = f", gap_tolerance={gap_count}" if gap_count > 0 else ""
        _LOGGER.debug(
            "%sLevel filter active: %s (order %s, require interval level %s filter level%s)",
            INDENT_L0,
            level_filter.upper(),
            level_order,
            filter_direction,
            gap_info,
        )
    else:
        status = "RELAXED to ANY" if (level_filter and level_filter.lower() == "any") else "DISABLED (not configured)"
        _LOGGER.debug("%sLevel filter: %s (accepting all levels)", INDENT_L0, status)

    periods: list[list[dict]] = []
    current_period: list[dict] = []
    last_ref_date: date | None = None
    consecutive_gaps = 0  # Track consecutive intervals that deviate by 1 level step
    intervals_checked = 0
    intervals_filtered_by_level = 0

    for price_data in all_prices:
        starts_at = time.get_interval_time(price_data)
        if starts_at is None:
            continue
        date_key = starts_at.date()

        # Use smoothed price for criteria checks (flex/distance)
        # but preserve original price for period data
        price_for_criteria = float(price_data["total"])  # Smoothed if this interval was an outlier
        price_original = float(price_data.get("_original_price", price_data["total"]))

        intervals_checked += 1

        # Check flex and minimum distance criteria (using smoothed price)
        criteria = IntervalCriteria(
            ref_price=ref_prices[date_key],
            avg_price=avg_prices[date_key],
            flex=flex,
            min_distance_from_avg=min_distance_from_avg,
            reverse_sort=reverse_sort,
        )
        in_flex, meets_min_distance = check_interval_criteria(price_for_criteria, criteria)

        # If this interval was smoothed, check if smoothing actually made a difference
        smoothing_was_impactful = False
        if price_data.get("_smoothed", False):
            # Check if original price would have passed the same criteria
            in_flex_original, meets_min_distance_original = check_interval_criteria(price_original, criteria)
            # Smoothing was impactful if original would have failed but smoothed passed
            smoothing_was_impactful = (in_flex and meets_min_distance) and not (
                in_flex_original and meets_min_distance_original
            )

        # Level filter: Check if interval meets level requirement with gap tolerance
        meets_level, consecutive_gaps, is_level_gap = apply_level_filter(
            price_data, level_order, consecutive_gaps, gap_count, reverse_sort=reverse_sort
        )
        if not meets_level:
            intervals_filtered_by_level += 1

        # Split period if day changes
        if last_ref_date is not None and date_key != last_ref_date and current_period:
            periods.append(current_period)
            current_period = []
            consecutive_gaps = 0  # Reset gap counter on day boundary

        last_ref_date = date_key

        # Add to period if all criteria are met
        if in_flex and meets_min_distance and meets_level:
            current_period.append(
                {
                    "interval_hour": starts_at.hour,
                    "interval_minute": starts_at.minute,
                    "interval_time": f"{starts_at.hour:02d}:{starts_at.minute:02d}",
                    "price": price_original,  # Use original price in period data
                    "interval_start": starts_at,
                    # Only True if smoothing changed whether the interval qualified for period inclusion
                    "smoothing_was_impactful": smoothing_was_impactful,
                    "is_level_gap": is_level_gap,  # Track if kept due to level gap tolerance
                }
            )
        elif current_period:
            # Criteria no longer met, end current period
            periods.append(current_period)
            current_period = []
            consecutive_gaps = 0  # Reset gap counter

    # Add final period if exists
    if current_period:
        periods.append(current_period)

    # Log summary
    if level_filter_active and intervals_checked > 0:
        filtered_pct = (intervals_filtered_by_level / intervals_checked) * 100
        _LOGGER.debug(
            "%sLevel filter summary: %d/%d intervals filtered (%.1f%%)",
            INDENT_L0,
            intervals_filtered_by_level,
            intervals_checked,
            filtered_pct,
        )

    return periods


def filter_periods_by_min_length(
    periods: list[list[dict]], min_period_length: int, *, time: TimeService
) -> list[list[dict]]:
    """Filter periods to only include those meeting the minimum length requirement."""
    min_intervals = time.minutes_to_intervals(min_period_length)
    return [period for period in periods if len(period) >= min_intervals]


def add_interval_ends(periods: list[list[dict]], *, time: TimeService) -> None:
    """Add interval_end to each interval in-place."""
    interval_duration = time.get_interval_duration()
    for period in periods:
        for interval in period:
            start = interval.get("interval_start")
            if start:
                interval["interval_end"] = start + interval_duration


def filter_periods_by_end_date(periods: list[list[dict]], *, time: TimeService) -> list[list[dict]]:
    """
    Filter periods to keep only relevant ones for today and tomorrow.

    Keep periods that:
    - End in the future (> now)
    - End today but after the start of the day (not exactly at midnight)

    This removes:
    - Periods that ended yesterday
    - Periods that ended exactly at midnight today (they're completely in the past)
    """
    now = time.now()
    today = now.date()
    midnight_today = time.start_of_local_day(now)

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
        if time.is_in_future(period_end):
            filtered.append(period)
            continue

        # Keep if period ends today but AFTER midnight (not exactly at midnight)
        if period_end.date() == today and period_end > midnight_today:
            filtered.append(period)

    return filtered
