"""Period building and basic filtering logic."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from custom_components.tibber_prices.const import PRICE_LEVEL_MAPPING

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService

from .level_filtering import (
    apply_level_filter,
    check_interval_criteria,
)
from .types import TibberPricesIntervalCriteria

_LOGGER = logging.getLogger(__name__)
_LOGGER_DETAILS = logging.getLogger(__name__ + ".details")

# Module-local log indentation (each module starts at level 0)
INDENT_L0 = ""  # Entry point / main function


def split_intervals_by_day(
    all_prices: list[dict], *, time: TibberPricesTimeService
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


def build_periods(  # noqa: PLR0913, PLR0915, PLR0912 - Complex period building logic requires many arguments, statements, and branches
    all_prices: list[dict],
    price_context: dict[str, Any],
    *,
    reverse_sort: bool,
    level_filter: str | None = None,
    gap_count: int = 0,
    time: TibberPricesTimeService,
) -> list[list[dict]]:
    """
    Build periods, allowing periods to cross midnight (day boundary).

    Periods can span multiple days. Each interval is evaluated against the reference
    price (min/max) and average price of its own day. This ensures fair filtering
    criteria even when periods cross midnight, where prices can jump significantly
    due to different forecasting uncertainty (prices at day end vs. day start).

    Args:
        all_prices: All price data points
        price_context: Dict with ref_prices, avg_prices, flex, min_distance_from_avg
        reverse_sort: True for peak price (high prices), False for best price (low prices)
        level_filter: Level filter string ("cheap", "expensive", "any", None)
        gap_count: Number of allowed consecutive intervals deviating by exactly 1 level step
        time: TibberPricesTimeService instance (required)

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
        _LOGGER_DETAILS.debug(
            "%sLevel filter active: %s (order %s, require interval level %s filter level%s)",
            INDENT_L0,
            level_filter.upper(),
            level_order,
            filter_direction,
            gap_info,
        )
    else:
        status = "RELAXED to ANY" if (level_filter and level_filter.lower() == "any") else "DISABLED (not configured)"
        _LOGGER_DETAILS.debug("%sLevel filter: %s (accepting all levels)", INDENT_L0, status)

    periods: list[list[dict]] = []
    current_period: list[dict] = []
    consecutive_gaps = 0  # Track consecutive intervals that deviate by 1 level step
    intervals_checked = 0
    intervals_filtered_by_level = 0
    intervals_filtered_by_flex = 0
    intervals_filtered_by_min_distance = 0

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

        # CRITICAL: Always use reference price from the interval's own day
        # Each interval must meet the criteria of its own day, not the period start day.
        # This ensures fair filtering even when periods cross midnight, where prices
        # can jump significantly (last intervals of a day have more risk buffer than
        # first intervals of next day, as they're set with different uncertainty levels).
        ref_date = date_key

        # Check flex and minimum distance criteria (using smoothed price and interval's own day reference)
        criteria = TibberPricesIntervalCriteria(
            ref_price=ref_prices[ref_date],
            avg_price=avg_prices[ref_date],
            flex=flex,
            min_distance_from_avg=min_distance_from_avg,
            reverse_sort=reverse_sort,
        )
        in_flex, meets_min_distance = check_interval_criteria(price_for_criteria, criteria)

        # Track why intervals are filtered
        if not in_flex:
            intervals_filtered_by_flex += 1
        if not meets_min_distance:
            intervals_filtered_by_min_distance += 1

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

    # Log detailed filter statistics
    if intervals_checked > 0:
        _LOGGER_DETAILS.debug(
            "%sFilter statistics: %d intervals checked",
            INDENT_L0,
            intervals_checked,
        )
        if intervals_filtered_by_flex > 0:
            flex_pct = (intervals_filtered_by_flex / intervals_checked) * 100
            _LOGGER_DETAILS.debug(
                "%s  Filtered by FLEX (price too far from ref): %d/%d (%.1f%%)",
                INDENT_L0,
                intervals_filtered_by_flex,
                intervals_checked,
                flex_pct,
            )
        if intervals_filtered_by_min_distance > 0:
            distance_pct = (intervals_filtered_by_min_distance / intervals_checked) * 100
            _LOGGER_DETAILS.debug(
                "%s  Filtered by MIN_DISTANCE (price too close to avg): %d/%d (%.1f%%)",
                INDENT_L0,
                intervals_filtered_by_min_distance,
                intervals_checked,
                distance_pct,
            )
        if level_filter_active and intervals_filtered_by_level > 0:
            level_pct = (intervals_filtered_by_level / intervals_checked) * 100
            _LOGGER_DETAILS.debug(
                "%s  Filtered by LEVEL (wrong price level): %d/%d (%.1f%%)",
                INDENT_L0,
                intervals_filtered_by_level,
                intervals_checked,
                level_pct,
            )

    return periods


def filter_periods_by_min_length(
    periods: list[list[dict]], min_period_length: int, *, time: TibberPricesTimeService
) -> list[list[dict]]:
    """Filter periods to only include those meeting the minimum length requirement."""
    min_intervals = time.minutes_to_intervals(min_period_length)
    return [period for period in periods if len(period) >= min_intervals]


def add_interval_ends(periods: list[list[dict]], *, time: TibberPricesTimeService) -> None:
    """Add interval_end to each interval in-place."""
    interval_duration = time.get_interval_duration()
    for period in periods:
        for interval in period:
            start = interval.get("interval_start")
            if start:
                interval["interval_end"] = start + interval_duration


def filter_periods_by_end_date(periods: list[list[dict]], *, time: TibberPricesTimeService) -> list[list[dict]]:
    """
    Filter periods to keep only relevant ones for yesterday, today, and tomorrow.

    Keep periods that:
    - End yesterday or later (>= start of yesterday)

    This removes:
    - Periods that ended before yesterday (day-before-yesterday or earlier)

    Rationale: Coordinator caches periods for yesterday/today/tomorrow so that:
    - Binary sensors can filter for today+tomorrow (current/next periods)
    - Services can access yesterday's periods when user requests "yesterday" data
    """
    now = time.now()
    # Calculate start of yesterday (midnight yesterday)
    yesterday_start = time.start_of_local_day(now) - time.get_interval_duration() * 96  # 96 intervals = 24 hours

    filtered = []
    for period in periods:
        if not period:
            continue

        # Get the end time of the period (last interval's end)
        last_interval = period[-1]
        period_end = last_interval.get("interval_end")

        if not period_end:
            continue

        # Keep if period ends yesterday or later
        if period_end >= yesterday_start:
            filtered.append(period)

    return filtered


def _categorize_periods_for_supersession(
    period_summaries: list[dict],
    today: date,
    tomorrow: date,
    late_hour_threshold: int,
    early_hour_limit: int,
) -> tuple[list[dict], list[dict], list[dict]]:
    """Categorize periods into today-late, tomorrow-early, and other."""
    today_late: list[dict] = []
    tomorrow_early: list[dict] = []
    other: list[dict] = []

    for period in period_summaries:
        period_start = period.get("start")
        period_end = period.get("end")

        if not period_start or not period_end:
            other.append(period)
        # Today late-night periods: START today at or after late_hour_threshold (e.g., 20:00)
        # Note: period_end could be tomorrow (e.g., 23:30-00:00 spans midnight)
        elif period_start.date() == today and period_start.hour >= late_hour_threshold:
            today_late.append(period)
        # Tomorrow early-morning periods: START tomorrow before early_hour_limit (e.g., 08:00)
        elif period_start.date() == tomorrow and period_start.hour < early_hour_limit:
            tomorrow_early.append(period)
        else:
            other.append(period)

    return today_late, tomorrow_early, other


def _filter_superseded_today_periods(
    today_late_periods: list[dict],
    best_tomorrow: dict,
    best_tomorrow_price: float,
    improvement_threshold: float,
) -> list[dict]:
    """Filter today periods that are superseded by a better tomorrow period."""
    kept: list[dict] = []

    for today_period in today_late_periods:
        today_price = today_period.get("price_mean")

        if today_price is None:
            kept.append(today_period)
            continue

        # Calculate how much better tomorrow is (as percentage)
        improvement_pct = ((today_price - best_tomorrow_price) / today_price * 100) if today_price > 0 else 0

        _LOGGER.debug(
            "Supersession check: Today %s-%s (%.4f) vs Tomorrow %s-%s (%.4f) = %.1f%% improvement (threshold: %.1f%%)",
            today_period["start"].strftime("%H:%M"),
            today_period["end"].strftime("%H:%M"),
            today_price,
            best_tomorrow["start"].strftime("%H:%M"),
            best_tomorrow["end"].strftime("%H:%M"),
            best_tomorrow_price,
            improvement_pct,
            improvement_threshold,
        )

        if improvement_pct >= improvement_threshold:
            _LOGGER.info(
                "Period superseded: Today %s-%s (%.2f) replaced by Tomorrow %s-%s (%.2f, %.1f%% better)",
                today_period["start"].strftime("%H:%M"),
                today_period["end"].strftime("%H:%M"),
                today_price,
                best_tomorrow["start"].strftime("%H:%M"),
                best_tomorrow["end"].strftime("%H:%M"),
                best_tomorrow_price,
                improvement_pct,
            )
        else:
            kept.append(today_period)

    return kept


def filter_superseded_periods(
    period_summaries: list[dict],
    *,
    time: TibberPricesTimeService,
    reverse_sort: bool,
) -> list[dict]:
    """
    Filter out late-night today periods that are superseded by better tomorrow periods.

    When tomorrow's data becomes available, some late-night periods that were found
    through relaxation may no longer make sense. If tomorrow has a significantly
    better period in the early morning, the late-night today period is obsolete.

    Example:
    - Today 23:30-00:00 at 0.70 kr (found via relaxation, was best available)
    - Tomorrow 04:00-05:30 at 0.50 kr (much better alternative)
    → The today period is superseded and should be filtered out

    This only applies to best-price periods (reverse_sort=False).
    Peak-price periods are not filtered this way.

    """
    from .types import (  # noqa: PLC0415
        CROSS_DAY_LATE_PERIOD_START_HOUR,
        CROSS_DAY_MAX_EXTENSION_HOUR,
        SUPERSESSION_PRICE_IMPROVEMENT_PCT,
    )

    _LOGGER.debug(
        "filter_superseded_periods called: %d periods, reverse_sort=%s",
        len(period_summaries) if period_summaries else 0,
        reverse_sort,
    )

    # Only filter for best-price periods
    if reverse_sort or not period_summaries:
        return period_summaries

    now = time.now()
    today = now.date()
    tomorrow = today + timedelta(days=1)

    # Categorize periods
    today_late, tomorrow_early, other = _categorize_periods_for_supersession(
        period_summaries,
        today,
        tomorrow,
        CROSS_DAY_LATE_PERIOD_START_HOUR,
        CROSS_DAY_MAX_EXTENSION_HOUR,
    )

    _LOGGER.debug(
        "Supersession categorization: today_late=%d, tomorrow_early=%d, other=%d",
        len(today_late),
        len(tomorrow_early),
        len(other),
    )

    # If no tomorrow early periods, nothing to compare against
    if not tomorrow_early:
        _LOGGER.debug("No tomorrow early periods - skipping supersession check")
        return period_summaries

    # Find the best tomorrow early period (lowest mean price)
    best_tomorrow = min(tomorrow_early, key=lambda p: p.get("price_mean", float("inf")))
    best_tomorrow_price = best_tomorrow.get("price_mean")

    if best_tomorrow_price is None:
        return period_summaries

    # Filter superseded today periods
    kept_today = _filter_superseded_today_periods(
        today_late,
        best_tomorrow,
        best_tomorrow_price,
        SUPERSESSION_PRICE_IMPROVEMENT_PCT,
    )

    # Reconstruct and sort by start time
    result = other + kept_today + tomorrow_early
    result.sort(key=lambda p: p.get("start") or time.now())

    return result


def _is_period_eligible_for_extension(
    period: dict,
    today: date,
    late_hour_threshold: int,
) -> bool:
    """
    Check if a period is eligible for cross-day extension.

    Eligibility criteria:
    - Period has valid start and end times
    - Period ends on today (not yesterday or tomorrow)
    - Period ends late (after late_hour_threshold, e.g. 20:00)

    """
    period_end = period.get("end")
    period_start = period.get("start")

    if not period_end or not period_start:
        return False

    if period_end.date() != today:
        return False

    return period_end.hour >= late_hour_threshold


def _find_extension_intervals(
    period_end: datetime,
    price_lookup: dict[str, dict],
    criteria: Any,
    max_extension_time: datetime,
    interval_duration: timedelta,
) -> list[dict]:
    """
    Find consecutive intervals after period_end that meet criteria.

    Iterates forward from period_end, adding intervals while they
    meet the flex and min_distance criteria. Stops at first failure
    or when reaching max_extension_time.

    """
    from .level_filtering import check_interval_criteria  # noqa: PLC0415

    extension_intervals: list[dict] = []
    check_time = period_end

    while check_time < max_extension_time:
        price_data = price_lookup.get(check_time.isoformat())
        if not price_data:
            break  # No more data

        price = float(price_data["total"])
        in_flex, meets_min_distance = check_interval_criteria(price, criteria)

        if not (in_flex and meets_min_distance):
            break  # Criteria no longer met

        extension_intervals.append(price_data)
        check_time = check_time + interval_duration

    return extension_intervals


def _collect_original_period_prices(
    period_start: datetime,
    period_end: datetime,
    price_lookup: dict[str, dict],
    interval_duration: timedelta,
) -> list[float]:
    """Collect prices from original period for CV calculation."""
    prices: list[float] = []
    current = period_start
    while current < period_end:
        price_data = price_lookup.get(current.isoformat())
        if price_data:
            prices.append(float(price_data["total"]))
        current = current + interval_duration
    return prices


def _build_extended_period(
    period: dict,
    extension_intervals: list[dict],
    combined_prices: list[float],
    combined_cv: float,
    interval_duration: timedelta,
) -> dict:
    """Create extended period dict with updated statistics."""
    period_start = period["start"]
    period_end = period["end"]
    new_end = period_end + (interval_duration * len(extension_intervals))

    extended = period.copy()
    extended["end"] = new_end
    extended["duration_minutes"] = int((new_end - period_start).total_seconds() / 60)
    extended["period_interval_count"] = len(combined_prices)
    extended["cross_day_extended"] = True
    extended["cross_day_extension_intervals"] = len(extension_intervals)

    # Recalculate price statistics
    extended["price_min"] = min(combined_prices)
    extended["price_max"] = max(combined_prices)
    extended["price_mean"] = sum(combined_prices) / len(combined_prices)
    extended["price_spread"] = extended["price_max"] - extended["price_min"]
    extended["price_coefficient_variation_%"] = round(combined_cv, 1)

    return extended


def extend_periods_across_midnight(
    period_summaries: list[dict],
    all_prices: list[dict],
    price_context: dict[str, Any],
    *,
    time: TibberPricesTimeService,
    reverse_sort: bool,
) -> list[dict]:
    """
    Extend late-night periods across midnight if favorable prices continue.

    When a period ends close to midnight and tomorrow's data shows continued
    favorable prices, extend the period into the next day. This prevents
    artificial period breaks at midnight when it's actually better to continue.

    Example: Best price period 22:00-23:45 today could extend to 04:00 tomorrow
    if prices remain low overnight.

    Rules:
    - Only extends periods ending after CROSS_DAY_LATE_PERIOD_START_HOUR (20:00)
    - Won't extend beyond CROSS_DAY_MAX_EXTENSION_HOUR (08:00) next day
    - Extension must pass same flex criteria as original period
    - Quality Gate (CV check) applies to extended period

    Args:
        period_summaries: List of period summary dicts (already processed)
        all_prices: All price intervals including tomorrow
        price_context: Dict with ref_prices, avg_prices, flex, min_distance_from_avg
        time: Time service instance
        reverse_sort: True for peak price, False for best price

    Returns:
        Updated list of period summaries with extensions applied

    """
    from custom_components.tibber_prices.utils.price import calculate_coefficient_of_variation  # noqa: PLC0415

    from .types import (  # noqa: PLC0415
        CROSS_DAY_LATE_PERIOD_START_HOUR,
        CROSS_DAY_MAX_EXTENSION_HOUR,
        PERIOD_MAX_CV,
        TibberPricesIntervalCriteria,
    )

    if not period_summaries or not all_prices:
        return period_summaries

    # Build price lookup by timestamp
    price_lookup: dict[str, dict] = {}
    for price_data in all_prices:
        interval_time = time.get_interval_time(price_data)
        if interval_time:
            price_lookup[interval_time.isoformat()] = price_data

    ref_prices = price_context.get("ref_prices", {})
    avg_prices = price_context.get("avg_prices", {})
    flex = price_context.get("flex", 0.15)
    min_distance = price_context.get("min_distance_from_avg", 0)

    now = time.now()
    today = now.date()
    tomorrow = today + timedelta(days=1)
    interval_duration = time.get_interval_duration()

    # Max extension time (e.g., 08:00 tomorrow)
    max_extension_time = time.start_of_local_day(now) + timedelta(days=1, hours=CROSS_DAY_MAX_EXTENSION_HOUR)

    extended_summaries = []

    for period in period_summaries:
        # Check eligibility for extension
        if not _is_period_eligible_for_extension(period, today, CROSS_DAY_LATE_PERIOD_START_HOUR):
            extended_summaries.append(period)
            continue

        # Get tomorrow's reference prices
        tomorrow_ref = ref_prices.get(tomorrow) or ref_prices.get(str(tomorrow))
        tomorrow_avg = avg_prices.get(tomorrow) or avg_prices.get(str(tomorrow))

        if tomorrow_ref is None or tomorrow_avg is None:
            extended_summaries.append(period)
            continue

        # Set up criteria for extension check
        criteria = TibberPricesIntervalCriteria(
            ref_price=tomorrow_ref,
            avg_price=tomorrow_avg,
            flex=flex,
            min_distance_from_avg=min_distance,
            reverse_sort=reverse_sort,
        )

        # Find extension intervals
        extension_intervals = _find_extension_intervals(
            period["end"],
            price_lookup,
            criteria,
            max_extension_time,
            interval_duration,
        )

        if not extension_intervals:
            extended_summaries.append(period)
            continue

        # Collect all prices for CV check
        original_prices = _collect_original_period_prices(
            period["start"],
            period["end"],
            price_lookup,
            interval_duration,
        )
        extension_prices = [float(p["total"]) for p in extension_intervals]
        combined_prices = original_prices + extension_prices

        # Quality Gate: Check CV of extended period
        combined_cv = calculate_coefficient_of_variation(combined_prices)

        if combined_cv is not None and combined_cv <= PERIOD_MAX_CV:
            # Extension passes quality gate
            extended_period = _build_extended_period(
                period,
                extension_intervals,
                combined_prices,
                combined_cv,
                interval_duration,
            )

            _LOGGER.info(
                "Cross-day extension: Period %s-%s extended to %s (+%d intervals, CV=%.1f%%)",
                period["start"].strftime("%H:%M"),
                period["end"].strftime("%H:%M"),
                extended_period["end"].strftime("%H:%M"),
                len(extension_intervals),
                combined_cv,
            )
            extended_summaries.append(extended_period)
        else:
            # Extension would exceed quality gate
            _LOGGER_DETAILS.debug(
                "%sCross-day extension rejected for period %s-%s: CV=%.1f%% > %.1f%%",
                INDENT_L0,
                period["start"].strftime("%H:%M"),
                period["end"].strftime("%H:%M"),
                combined_cv or 0,
                PERIOD_MAX_CV,
            )
            extended_summaries.append(period)

    return extended_summaries
