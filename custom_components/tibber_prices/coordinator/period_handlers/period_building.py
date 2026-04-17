"""Period building and basic filtering logic."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any

from custom_components.tibber_prices.const import PRICE_LEVEL_MAPPING

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService

from .level_filtering import apply_level_filter, check_interval_criteria, compute_geometric_flex_bonus
from .types import CROSS_DAY_OVERNIGHT_VALIDATION_HOUR, TibberPricesIntervalCriteria

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


def build_periods(
    all_prices: list[dict],
    price_context: dict[str, Any],
    *,
    reverse_sort: bool,
    level_filter: str | None = None,
    gap_count: int = 0,
    time: TibberPricesTimeService,
    time_range: tuple[datetime, datetime] | None = None,
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
        time_range: Optional (start_inclusive, end_exclusive) window. When set, only intervals
            within [start, end) are considered as period candidates. Reference prices
            (from price_context) remain day-wide and are unaffected by this filter.
            Used by Phase 4 segment forcing to restrict detection to one segment side.

    """
    ref_prices = price_context["ref_prices"]
    avg_prices = price_context["avg_prices"]
    flex = price_context["flex"]
    min_distance_from_avg = price_context["min_distance_from_avg"]
    geometric_extra_flex: float = float(price_context.get("geometric_extra_flex", 0.0))
    day_patterns_by_date: dict[date, dict[str, Any]] | None = price_context.get("day_patterns_by_date")

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

    # Pre-compute criteria per day (flex/min_distance/reverse_sort are constant throughout;
    # only ref_price and avg_price vary by day — max 3 entries: yesterday/today/tomorrow)
    criteria_by_day: dict[date, TibberPricesIntervalCriteria] = {
        day: TibberPricesIntervalCriteria(
            ref_price=ref_prices[day],
            avg_price=avg_prices[day],
            flex=flex,
            min_distance_from_avg=min_distance_from_avg,
            reverse_sort=reverse_sort,
        )
        for day in ref_prices
    }

    for price_data in all_prices:
        starts_at = time.get_interval_time(price_data)
        if starts_at is None:
            continue

        # Filter by time range if specified (Phase 4 segment forcing)
        if time_range is not None and not (time_range[0] <= starts_at < time_range[1]):
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
        criteria = criteria_by_day[ref_date]

        # Compute geometric flex bonus if pattern-aware expansion is enabled
        geo_bonus = 0.0
        if geometric_extra_flex > 0 and day_patterns_by_date is not None:
            day_pattern_for_date = day_patterns_by_date.get(ref_date)
            geo_bonus = compute_geometric_flex_bonus(
                starts_at,
                day_pattern_for_date,
                extra_flex=geometric_extra_flex,
                reverse_sort=reverse_sort,
            )

        effective_criteria = criteria._replace(flex=criteria.flex + geo_bonus) if geo_bonus > 0 else criteria
        in_flex, meets_min_distance = check_interval_criteria(price_for_criteria, effective_criteria)

        # Cross-day boundary validation for peak periods:
        # Overnight intervals (00:00-05:59) must ALSO qualify against the previous
        # day's reference price. Without this, prices like 30ct become "peak" against
        # tomorrow's lower max (35ct) but weren't peak against today's higher max (39ct).
        if reverse_sort and in_flex and starts_at.hour < CROSS_DAY_OVERNIGHT_VALIDATION_HOUR:
            prev_day = date_key - timedelta(days=1)
            prev_criteria = criteria_by_day.get(prev_day)
            if prev_criteria is not None:
                prev_effective = (
                    prev_criteria._replace(flex=prev_criteria.flex + geo_bonus) if geo_bonus > 0 else prev_criteria
                )
                in_prev_flex, _ = check_interval_criteria(price_for_criteria, prev_effective)
                if not in_prev_flex:
                    # Fails against previous day → boundary artifact, treat as not in flex
                    in_flex = False
                    intervals_filtered_by_flex += 1

        # Track why intervals are filtered
        if not in_flex:
            intervals_filtered_by_flex += 1
        if not meets_min_distance:
            intervals_filtered_by_min_distance += 1

        # If this interval was smoothed, check if smoothing actually made a difference
        smoothing_was_impactful = False
        if price_data.get("_smoothed", False):
            # Check if original price would have passed the same criteria
            in_flex_original, meets_min_distance_original = check_interval_criteria(price_original, effective_criteria)
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
                    "geometric_bonus_applied": geo_bonus > 0,  # True if interval is in geometric zone
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


def _filter_best_superseded_periods(
    today_late: list[dict],
    tomorrow_early: list[dict],
    other: list[dict],
    improvement_threshold: float,
) -> list[dict]:
    """Filter best-price today-late periods superseded by cheaper tomorrow alternatives."""
    if not tomorrow_early:
        return other + today_late + tomorrow_early

    # Find the cheapest tomorrow early period
    best_tomorrow = min(tomorrow_early, key=lambda p: p.get("price_mean", float("inf")))
    best_tomorrow_price = best_tomorrow.get("price_mean")

    if best_tomorrow_price is None:
        return other + today_late + tomorrow_early

    kept_today = _filter_superseded_today_periods(
        today_late,
        best_tomorrow,
        best_tomorrow_price,
        improvement_threshold,
    )

    return other + kept_today + tomorrow_early


def _filter_peak_superseded_periods(
    today_late: list[dict],
    tomorrow_early: list[dict],
    other: list[dict],
    improvement_threshold: float,
) -> list[dict]:
    """
    Filter peak-price tomorrow-early periods that are artifacts of day-boundary reclassification.

    If today has a genuine late-night peak and tomorrow's early-morning "peak" is
    significantly LOWER in price, the tomorrow period is a cross-day artifact:
    the same overnight prices are classified differently because they sit near
    a different day's maximum.

    """
    if not today_late or not tomorrow_early:
        return other + today_late + tomorrow_early

    # Find the strongest today late peak (highest mean price)
    best_today_peak = max(today_late, key=lambda p: p.get("price_mean", 0))
    best_today_price = best_today_peak.get("price_mean")

    if best_today_price is None or best_today_price <= 0:
        return other + today_late + tomorrow_early

    kept_tomorrow: list[dict] = []
    for tomorrow_period in tomorrow_early:
        tomorrow_price = tomorrow_period.get("price_mean")

        if tomorrow_price is None:
            kept_tomorrow.append(tomorrow_period)
            continue

        # How much LOWER is tomorrow's peak vs today's peak? (as percentage)
        price_drop_pct = ((best_today_price - tomorrow_price) / best_today_price * 100) if best_today_price > 0 else 0

        if price_drop_pct >= improvement_threshold:
            _LOGGER.info(
                "Peak supersession: Tomorrow %s-%s (%.2f) is %.1f%% below today's peak %s-%s (%.2f) → filtered as artifact",
                tomorrow_period["start"].strftime("%H:%M"),
                tomorrow_period["end"].strftime("%H:%M"),
                tomorrow_price,
                price_drop_pct,
                best_today_peak["start"].strftime("%H:%M"),
                best_today_peak["end"].strftime("%H:%M"),
                best_today_price,
            )
        else:
            kept_tomorrow.append(tomorrow_period)

    return other + today_late + kept_tomorrow


def filter_superseded_periods(
    period_summaries: list[dict],
    *,
    time: TibberPricesTimeService,
    reverse_sort: bool,
) -> list[dict]:
    """
    Filter out cross-day periods that are artifacts of day-boundary price reclassification.

    For BEST PRICE (reverse_sort=False):
    When tomorrow's data becomes available, some late-night periods that were found
    through relaxation may no longer make sense. If tomorrow has a significantly
    better (cheaper) period in the early morning, the late-night today period is obsolete.

    For PEAK PRICE (reverse_sort=True):
    Inverted logic: tomorrow's early-morning periods that are significantly LOWER
    than today's late-night peak are cross-day artifacts. Overnight prices often
    qualify as "peak" against tomorrow's (lower) daily max, but don't represent
    genuine high-price windows when viewed across the day boundary.

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

    if not period_summaries:
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

    if reverse_sort:
        # PEAK: Filter tomorrow-early periods superseded by today-late peaks
        result = _filter_peak_superseded_periods(
            today_late,
            tomorrow_early,
            other,
            SUPERSESSION_PRICE_IMPROVEMENT_PCT,
        )
    else:
        # BEST: Filter today-late periods superseded by cheaper tomorrow alternatives
        result = _filter_best_superseded_periods(
            today_late,
            tomorrow_early,
            other,
            SUPERSESSION_PRICE_IMPROVEMENT_PCT,
        )

    result.sort(key=lambda p: p.get("start") or time.now())
    return result


def filter_weak_peak_periods(
    period_summaries: list[dict],
    avg_prices: dict,
    *,
    time: TibberPricesTimeService,
) -> list[dict]:
    """
    Filter peak periods whose mean price is barely above the daily average.

    A genuine peak period should have prices meaningfully above the daily average.
    Periods that are only marginally above average are typically cross-day artifacts
    where overnight prices qualify as "peak" against a low daily maximum.

    Safety: At least one period per day is always preserved (the one with the
    highest premium above average). This prevents removing all peaks on flat days.

    Only applies to peak periods. Best-price filtering is not needed because
    cheap periods near the daily average are still useful for scheduling.

    """
    from .types import CROSS_DAY_OVERNIGHT_VALIDATION_HOUR, PEAK_MIN_PREMIUM_ABOVE_AVG_PCT  # noqa: PLC0415

    if not period_summaries:
        return period_summaries

    # Calculate premium for each period and group by day
    period_premiums: list[tuple[dict, float, date]] = []
    for period in period_summaries:
        period_mean = period.get("price_mean")
        period_start = period.get("start")

        if period_mean is None or period_start is None:
            period_premiums.append((period, float("inf"), date.min))
            continue

        day_key = period_start.date()
        daily_avg = avg_prices.get(day_key) or avg_prices.get(str(day_key))

        if daily_avg is None or daily_avg <= 0:
            period_premiums.append((period, float("inf"), day_key))
            continue

        # For overnight/morning periods (before 06:00), use the HIGHER of
        # current day and previous day averages. This prevents overnight prices
        # from appearing as "peaks" when tomorrow's average is lower due to
        # midday valleys (e.g., solar surplus). A genuine peak must be high
        # relative to BOTH days' price landscape.
        effective_avg = daily_avg
        if period_start.hour < CROSS_DAY_OVERNIGHT_VALIDATION_HOUR:
            prev_day = day_key - timedelta(days=1)
            prev_avg = avg_prices.get(prev_day) or avg_prices.get(str(prev_day))
            if prev_avg is not None and prev_avg > daily_avg:
                effective_avg = prev_avg
                _LOGGER_DETAILS.debug(
                    "%sWeak peak check: Period %s uses prev-day avg %.4f instead of %.4f (overnight cross-day)",
                    INDENT_L0,
                    period_start.strftime("%H:%M"),
                    prev_avg,
                    daily_avg,
                )

        premium_pct = ((period_mean - effective_avg) / effective_avg) * 100
        period_premiums.append((period, premium_pct, day_key))

    # Find the best (highest premium) period per day
    best_per_day: dict[date, float] = {}
    for _period, premium, day in period_premiums:
        if day not in best_per_day or premium > best_per_day[day]:
            best_per_day[day] = premium

    # Filter: keep periods that pass threshold OR are the best for their day
    kept: list[dict] = []
    removed = 0
    for period, premium, day in period_premiums:
        is_best_for_day = premium >= best_per_day.get(day, float("-inf"))

        if premium >= PEAK_MIN_PREMIUM_ABOVE_AVG_PCT:
            kept.append(period)
        elif is_best_for_day:
            # Preserve at least one period per day even if below threshold
            kept.append(period)
            _LOGGER_DETAILS.debug(
                "%sWeak peak preserved (best for day %s): premium=%.1f%% < threshold=%.1f%%",
                INDENT_L0,
                day,
                premium,
                PEAK_MIN_PREMIUM_ABOVE_AVG_PCT,
            )
        else:
            period_start = period.get("start")
            _LOGGER.info(
                "Weak peak filtered: Period %s-%s mean=%.2f is only %.1f%% above daily avg (need ≥%.1f%%)",
                period_start.strftime("%H:%M") if period_start else "?",
                period["end"].strftime("%H:%M") if period.get("end") else "?",
                period.get("price_mean", 0),
                premium,
                PEAK_MIN_PREMIUM_ABOVE_AVG_PCT,
            )
            removed += 1

    if removed > 0:
        _LOGGER.info(
            "Weak peak filter: %d/%d periods kept (removed %d below %.0f%% premium threshold)",
            len(kept),
            len(period_summaries),
            removed,
            PEAK_MIN_PREMIUM_ABOVE_AVG_PCT,
        )

    return kept


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
    *,
    max_intervals: int = 0,
    period_mean_price: float = 0.0,
    max_price_deviation: float = 0.0,
    reverse_sort: bool = False,
) -> list[dict]:
    """
    Find consecutive intervals after period_end that meet criteria.

    Iterates forward from period_end, adding intervals while they
    meet the flex and min_distance criteria. Stops at first failure
    or when reaching max_extension_time.

    Additional guards:
    - max_intervals: Hard cap on number of extension intervals (0 = unlimited)
    - period_mean_price + max_price_deviation: Stop extending when the candidate
      interval's price deviates too far from the original period's mean price.
      For peak periods (reverse_sort=True): stops when price drops below
      mean × (1 - deviation). For best periods: stops when price rises above
      mean × (1 + deviation).

    """
    from .level_filtering import check_interval_criteria  # noqa: PLC0415

    extension_intervals: list[dict] = []
    check_time = period_end

    while check_time < max_extension_time:
        # Hard cap on extension length
        if max_intervals > 0 and len(extension_intervals) >= max_intervals:
            break

        price_data = price_lookup.get(check_time.isoformat())
        if not price_data:
            break  # No more data

        price = float(price_data["total"])

        # Price deviation gate: stop if price drifts too far from original period mean
        if period_mean_price > 0 and max_price_deviation > 0:
            if reverse_sort:
                # Peak: stop if price drops below mean × (1 - deviation)
                if price < period_mean_price * (1 - max_price_deviation):
                    break
            elif price > period_mean_price * (1 + max_price_deviation):
                # Best: stop if price rises above mean × (1 + deviation)
                break

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
        CROSS_DAY_MAX_EXTENSION_INTERVALS,
        CROSS_DAY_MAX_PRICE_DEVIATION,
        CROSS_DAY_PROPORTIONAL_EXTENSION_FACTOR,
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

        # Collect original prices once (reused for cap calculation, deviation gate, and CV check)
        original_prices = _collect_original_period_prices(
            period["start"],
            period["end"],
            price_lookup,
            interval_duration,
        )

        # Calculate max extension intervals: min(hard cap, proportional cap)
        original_interval_count = max(1, len(original_prices))
        proportional_cap = int(original_interval_count * CROSS_DAY_PROPORTIONAL_EXTENSION_FACTOR)
        max_intervals = min(CROSS_DAY_MAX_EXTENSION_INTERVALS, proportional_cap)

        # Original period mean price for deviation gate
        period_mean_price = sum(original_prices) / len(original_prices) if original_prices else 0.0

        # Find extension intervals (with cap + price deviation gate)
        extension_intervals = _find_extension_intervals(
            period["end"],
            price_lookup,
            criteria,
            max_extension_time,
            interval_duration,
            max_intervals=max_intervals,
            period_mean_price=period_mean_price,
            max_price_deviation=CROSS_DAY_MAX_PRICE_DEVIATION,
            reverse_sort=reverse_sort,
        )

        if not extension_intervals:
            extended_summaries.append(period)
            continue

        # CV check using already-collected original prices
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
                "Cross-day extension: Period %s-%s extended to %s (+%d intervals, max=%d, CV=%.1f%%)",
                period["start"].strftime("%H:%M"),
                period["end"].strftime("%H:%M"),
                extended_period["end"].strftime("%H:%M"),
                len(extension_intervals),
                max_intervals,
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
