"""Core period calculation API - main entry points."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

    from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService

    from .types import TibberPricesPeriodConfig

from .outlier_filtering import (
    filter_price_outliers,
)
from .period_building import (
    add_interval_ends,
    build_periods,
    calculate_reference_prices,
    extend_periods_across_midnight,
    filter_periods_by_end_date,
    filter_periods_by_min_length,
    filter_superseded_periods,
    split_intervals_by_day,
)
from .period_statistics import (
    extract_period_summaries,
)
from .shape_extension import extend_periods_for_shape
from .types import TibberPricesThresholdConfig

# Flex limits to prevent degenerate behavior (see docs/development/period-calculation-theory.md)
MAX_SAFE_FLEX = 0.50  # 50% - hard cap: above this, period detection becomes unreliable
MAX_OUTLIER_FLEX = 0.25  # 25% - cap for outlier filtering: above this, spike detection too permissive
MIN_SEGMENT_FORCING_INTERVALS = 8  # Minimum intervals per day half to attempt segment forcing (< 2 hours is too few)


def calculate_periods(
    all_prices: list[dict],
    *,
    config: TibberPricesPeriodConfig,
    time: TibberPricesTimeService,
    day_patterns_by_date: dict | None = None,
    time_range: tuple[datetime, datetime] | None = None,
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
    5. Add interval ends
    6. Filter periods by end date
    7. Extract period summaries (start/end times, not full price data)

    Args:
        all_prices: All price data points from yesterday/today/tomorrow.
        config: Period configuration containing reverse_sort, flex, min_distance_from_avg,
                min_period_length, threshold_low, and threshold_high.
        time: TibberPricesTimeService instance (required).
        day_patterns_by_date: Optional dict mapping date → day pattern dict for geometric flex bonus.
        time_range: Optional (start_inclusive, end_exclusive) window passed through to
            build_periods(). When set, only intervals within [start, end) are considered
            as period candidates. Used by Phase 4 segment forcing.

    Returns:
        Dict with:
        - periods: List of lightweight period summaries (start/end times only)
        - metadata: Config and statistics
        - reference_data: Daily min/max/avg for on-demand annotation

    """
    # Import logger at the start of function
    import logging  # noqa: PLC0415

    from .types import INDENT_L0  # noqa: PLC0415

    _LOGGER = logging.getLogger(__name__)  # noqa: N806

    # Extract config values
    reverse_sort = config.reverse_sort
    flex_raw = config.flex  # Already normalized to positive by get_period_config()
    min_distance_from_avg = config.min_distance_from_avg
    min_period_length = config.min_period_length
    threshold_low = config.threshold_low
    threshold_high = config.threshold_high

    # CRITICAL: Hard cap flex at 50% to prevent degenerate behavior
    # Above 50%, period detection becomes unreliable (too many intervals qualify)
    # NOTE: flex_raw is already positive from normalization in get_period_config()
    flex = flex_raw
    if flex_raw > MAX_SAFE_FLEX:
        flex = MAX_SAFE_FLEX
        _LOGGER.warning(
            "Flex %.1f%% exceeds maximum safe value! Capping at %.0f%%. "
            "Recommendation: Use 15-20%% with relaxation enabled, or 25-35%% without relaxation.",
            flex_raw * 100,
            MAX_SAFE_FLEX * 100,
        )

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
    intervals_by_day, avg_price_by_day = split_intervals_by_day(all_prices_sorted, time=time)

    # Step 2: Calculate reference prices (min or max per day)
    ref_prices = calculate_reference_prices(intervals_by_day, reverse_sort=reverse_sort)

    # Step 2.5: Filter price outliers (smoothing for period formation only)
    # This runs BEFORE period formation to prevent isolated price spikes
    # from breaking up otherwise continuous periods

    # CRITICAL: Cap flexibility for outlier filtering at 25%
    # High flex (>25%) makes outlier detection too permissive, accepting
    # unstable price contexts as "normal". This breaks period formation.
    # User's flex setting still applies to period criteria (in_flex check).

    # Import details logger locally (core.py imports logger locally in function)
    _LOGGER_DETAILS = logging.getLogger(__name__ + ".details")  # noqa: N806

    outlier_flex = min(abs(flex) * 100, MAX_OUTLIER_FLEX * 100)
    if abs(flex) * 100 > MAX_OUTLIER_FLEX * 100:
        _LOGGER_DETAILS.debug(
            "%sOutlier filtering: Using capped flex %.1f%% (user setting: %.1f%%)",
            INDENT_L0,
            outlier_flex,
            abs(flex) * 100,
        )

    all_prices_smoothed = filter_price_outliers(
        all_prices_sorted,
        outlier_flex,  # Use capped flex for outlier detection
        min_period_length,
    )

    # Step 3: Build periods
    price_context = {
        "ref_prices": ref_prices,
        "avg_prices": avg_price_by_day,
        "intervals_by_day": intervals_by_day,  # Needed for day volatility calculation
        "flex": flex,
        "min_distance_from_avg": min_distance_from_avg,
        "geometric_extra_flex": config.geometric_extra_flex,  # Extra flex for geometric zone
        "day_patterns_by_date": day_patterns_by_date,  # Pattern data keyed by date (may be None)
    }
    raw_periods = build_periods(
        all_prices_smoothed,  # Use smoothed prices for period formation
        price_context,
        reverse_sort=reverse_sort,
        level_filter=config.level_filter,
        gap_count=config.gap_count,
        time=time,
        time_range=time_range,
    )

    _LOGGER.debug(
        "%sAfter build_periods: %d raw periods found (flex=%.1f%%, level_filter=%s)",
        INDENT_L0,
        len(raw_periods),
        abs(flex) * 100,
        config.level_filter or "None",
    )

    # Step 3.5: Segment forcing for W/M-shaped days (opt-in, default disabled)
    # For days detected as W-shape (DOUBLE_VALLEY for best) or M-shape (DOUBLE_PEAK for peak),
    # ensures each price valley/peak segment has at least segment_min_periods periods.
    if config.segment_forcing and day_patterns_by_date:
        raw_periods = _apply_segment_forcing(
            all_prices_smoothed,
            raw_periods,
            price_context,
            config,
            day_patterns_by_date=day_patterns_by_date,
            time=time,
        )
        _LOGGER.debug(
            "%sAfter segment_forcing: %d periods total",
            INDENT_L0,
            len(raw_periods),
        )

    # Step 4: Filter by minimum length
    raw_periods = filter_periods_by_min_length(raw_periods, min_period_length, time=time)
    _LOGGER.debug(
        "%sAfter filter_by_min_length (>= %d min): %d periods remain",
        INDENT_L0,
        min_period_length,
        len(raw_periods),
    )

    # Step 5: Add interval ends
    add_interval_ends(raw_periods, time=time)

    # Step 6: Filter periods by end date (keep periods ending yesterday or later)
    # This ensures coordinator cache contains yesterday/today/tomorrow periods
    # Sensors filter further for today+tomorrow, services can access all cached periods
    raw_periods = filter_periods_by_end_date(raw_periods, time=time)

    # Step 7: Extract lightweight period summaries (no full price data)
    # Note: Periods are filtered by end date to keep yesterday/today/tomorrow.
    # This preserves periods that started day-before-yesterday but end yesterday.
    thresholds = TibberPricesThresholdConfig(
        threshold_low=threshold_low,
        threshold_high=threshold_high,
        threshold_volatility_moderate=config.threshold_volatility_moderate,
        threshold_volatility_high=config.threshold_volatility_high,
        threshold_volatility_very_high=config.threshold_volatility_very_high,
        reverse_sort=reverse_sort,
    )
    period_summaries = extract_period_summaries(
        raw_periods,
        all_prices_sorted,
        price_context,
        thresholds,
        time=time,
    )

    # Step 7.5: Extend periods into adjacent VERY_CHEAP / VERY_EXPENSIVE intervals
    # This is an opt-in feature (disabled by default) that adds contiguous
    # extreme-level intervals on each side of an already-found period.
    if config.extend_to_extreme and config.max_extension_intervals > 0:
        period_summaries = extend_periods_for_shape(
            period_summaries,
            all_prices_sorted,
            price_context,
            reverse_sort=reverse_sort,
            max_extension_intervals=config.max_extension_intervals,
            thresholds=thresholds,
            time=time,
        )

    # Step 8: Cross-day extension for late-night periods
    # If a best-price period ends near midnight and tomorrow has continued low prices,
    # extend the period across midnight to give users the full cheap window
    period_summaries = extend_periods_across_midnight(
        period_summaries,
        all_prices_sorted,
        price_context,
        time=time,
        reverse_sort=reverse_sort,
    )

    # Step 9: Filter superseded periods
    # When tomorrow data is available, late-night today periods that were found via
    # relaxation may be obsolete if tomorrow has significantly better alternatives
    period_summaries = filter_superseded_periods(
        period_summaries,
        time=time,
        reverse_sort=reverse_sort,
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


# ─── Segment forcing helpers ──────────────────────────────────────────────────


def _period_belongs_to_side(
    period: list[dict],
    side_times: set,
    time: "TibberPricesTimeService",
) -> bool:
    """Return True if the majority of a period's intervals are in side_times."""
    if not period:
        return False
    in_side = sum(1 for iv in period if time.get_interval_time(iv) in side_times)
    return in_side * 2 >= len(period)


def _apply_segment_forcing(  # noqa: PLR0913
    all_prices_smoothed: list[dict],
    periods: list[list[dict]],
    price_context: dict[str, Any],
    config: "TibberPricesPeriodConfig",
    *,
    day_patterns_by_date: dict,
    time: "TibberPricesTimeService",
) -> list[list[dict]]:
    """
    Force at least segment_min_periods periods per segment for W/M-shaped days.

    For DOUBLE_VALLEY days (best price): splits at the central price peak and
    ensures each valley side has the required number of periods.
    For DOUBLE_PEAK days (peak price): splits at the central price valley and
    ensures each peak side has the required number of periods.

    Args:
        all_prices_smoothed: Outlier-filtered prices used for period building.
        periods: Already-found periods from the global build_periods call.
        price_context: Context dict with reference/average prices + filter settings.
        config: Period configuration including segment_forcing parameters.
        day_patterns_by_date: Detected day patterns keyed by date.
        time: TibberPricesTimeService instance.

    Returns:
        Updated periods list with any new segment-forced periods appended.

    """
    import logging  # noqa: PLC0415

    from .period_building import build_periods  # noqa: PLC0415
    from .types import DAY_PATTERN_DOUBLE_PEAK, DAY_PATTERN_DOUBLE_VALLEY, INDENT_L1, INDENT_L2  # noqa: PLC0415

    _LOGGER = logging.getLogger(__name__)  # noqa: N806

    reverse_sort = config.reverse_sort
    target_pattern = DAY_PATTERN_DOUBLE_PEAK if reverse_sort else DAY_PATTERN_DOUBLE_VALLEY
    segment_min_periods = config.segment_min_periods

    merged_periods = list(periods)

    for day_date, day_pattern in day_patterns_by_date.items():
        if day_pattern is None or day_pattern.get("pattern") != target_pattern:
            continue

        # Collect and sort this day's intervals
        day_intervals = sorted(
            (
                iv
                for iv in all_prices_smoothed
                if (t := time.get_interval_time(iv)) is not None and t.date() == day_date
            ),
            key=time.get_interval_time,  # type: ignore[arg-type]
        )
        if len(day_intervals) < MIN_SEGMENT_FORCING_INTERVALS:  # need at least a few intervals per segment
            continue

        # Find the central extremum in the middle 50% of the day
        # DOUBLE_VALLEY → central peak = highest price between the two valleys
        # DOUBLE_PEAK   → central valley = lowest price between the two peaks
        n = len(day_intervals)
        middle = day_intervals[n // 4 : 3 * n // 4]
        if not middle:
            continue

        if not reverse_sort:
            split_iv = max(middle, key=lambda iv: iv.get("total") or 0)
        else:
            split_iv = min(middle, key=lambda iv: iv.get("total") or float("inf"))

        split_time = time.get_interval_time(split_iv)
        if split_time is None:
            continue

        side_a = [iv for iv in day_intervals if (t := time.get_interval_time(iv)) is not None and t <= split_time]
        side_b = [iv for iv in day_intervals if (t := time.get_interval_time(iv)) is not None and t > split_time]

        _LOGGER.debug(
            "%sSegment forcing %s (%s): split at %s (%d+%d intervals)",
            INDENT_L1,
            day_date,
            target_pattern,
            split_time.strftime("%H:%M"),
            len(side_a),
            len(side_b),
        )

        for side_name, side_intervals in (("A", side_a), ("B", side_b)):
            side_times = {time.get_interval_time(iv) for iv in side_intervals}
            count_in_side = sum(1 for p in merged_periods if _period_belongs_to_side(p, side_times, time))

            _LOGGER.debug(
                "%sSide %s: %d existing periods (need %d)",
                INDENT_L2,
                side_name,
                count_in_side,
                segment_min_periods,
            )

            if count_in_side >= segment_min_periods:
                continue

            # Run period detection restricted to this segment side via time_range.
            # The full all_prices_smoothed (including other days) is passed so that
            # reference price context remains day-wide; time_range restricts which
            # intervals are EVALUATED as period candidates to this side only.
            sorted_side = sorted(side_intervals, key=time.get_interval_time)  # type: ignore[arg-type]
            side_start = time.get_interval_time(sorted_side[0])
            # end = one interval duration past the last interval's start
            side_end = time.get_interval_time(sorted_side[-1])
            if side_start is None or side_end is None:
                continue
            side_end = side_end + time.get_interval_duration()
            new_raw = build_periods(
                all_prices_smoothed,
                price_context,
                reverse_sort=reverse_sort,
                level_filter=config.level_filter,
                gap_count=config.gap_count,
                time=time,
                time_range=(side_start, side_end),
            )

            # Add non-duplicate periods; flag them with segment_forced=True
            added = 0
            for new_period in new_raw:
                new_times = {time.get_interval_time(iv) for iv in new_period if time.get_interval_time(iv) is not None}
                is_dup = any(
                    bool(
                        new_times
                        & {time.get_interval_time(iv) for iv in existing if time.get_interval_time(iv) is not None}
                    )
                    for existing in merged_periods
                )
                if not is_dup:
                    merged_periods.append([{**iv, "segment_forced": True} for iv in new_period])
                    added += 1

            _LOGGER.debug(
                "%sSide %s: added %d forced periods (%d candidates from restricted run)",
                INDENT_L2,
                side_name,
                added,
                len(new_raw),
            )

    return merged_periods
