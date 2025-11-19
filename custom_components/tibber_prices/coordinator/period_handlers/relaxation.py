"""Relaxation strategy for finding minimum periods per day."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import date

    from custom_components.tibber_prices.coordinator.time_service import TimeService

    from .types import PeriodConfig

from .period_merging import (
    recalculate_period_metadata,
    resolve_period_overlaps,
)
from .types import (
    INDENT_L0,
    INDENT_L1,
    INDENT_L2,
)

_LOGGER = logging.getLogger(__name__)


def group_periods_by_day(periods: list[dict]) -> dict[date, list[dict]]:
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


def group_prices_by_day(all_prices: list[dict], *, time: TimeService) -> dict[date, list[dict]]:
    """
    Group price intervals by the day they belong to (today and future only).

    Args:
        all_prices: List of price dicts with "startsAt" timestamp
        time: TimeService instance (required)

    Returns:
        Dict mapping date to list of price intervals for that day (only today and future)

    """
    today = time.now().date()
    prices_by_day: dict[date, list[dict]] = {}

    for price in all_prices:
        starts_at = price["startsAt"]  # Already datetime in local timezone
        if starts_at:
            price_date = starts_at.date()
            # Only include today and future days
            if price_date >= today:
                prices_by_day.setdefault(price_date, []).append(price)

    return prices_by_day


def check_min_periods_per_day(
    periods: list[dict], min_periods: int, all_prices: list[dict], *, time: TimeService
) -> bool:
    """
    Check if minimum periods requirement is met for each day individually.

    Returns True if we should STOP relaxation (enough periods found per day).
    Returns False if we should CONTINUE relaxation (not enough periods yet).

    Args:
        periods: List of period summary dicts
        min_periods: Minimum number of periods required per day
        all_prices: All available price intervals (used to determine which days have data)
        time: TimeService instance (required)

    Returns:
        True if every day with price data has at least min_periods, False otherwise

    """
    if not periods:
        return False  # No periods at all, continue relaxation

    # Get all days that have price data (today and future only, not yesterday)
    today = time.now().date()
    available_days = set()
    for price in all_prices:
        starts_at = time.get_interval_time(price)
        if starts_at:
            price_date = starts_at.date()
            # Only count today and future days (not yesterday)
            if price_date >= today:
                available_days.add(price_date)

    if not available_days:
        return False  # No price data for today/future, continue relaxation

    # Group found periods by day
    periods_by_day = group_periods_by_day(periods)

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


def mark_periods_with_relaxation(
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


def calculate_periods_with_relaxation(  # noqa: PLR0913, PLR0915 - Per-day relaxation requires many parameters and statements
    all_prices: list[dict],
    *,
    config: PeriodConfig,
    enable_relaxation: bool,
    min_periods: int,
    relaxation_step_pct: int,
    max_relaxation_attempts: int,
    should_show_callback: Callable[[str | None], bool],
    time: TimeService,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Calculate periods with optional per-day filter relaxation.

    NEW: Each day gets its own independent relaxation loop. Today can be in Phase 1
    while tomorrow is in Phase 3, ensuring each day finds enough periods.

    If min_periods is not reached with normal filters, this function gradually
    relaxes filters in multiple phases FOR EACH DAY SEPARATELY:

    Phase 1: Increase flex threshold step-by-step (up to 4 attempts)
    Phase 2: Disable level filter (set to "any")

    Args:
        all_prices: All price data points
        config: Base period configuration
        enable_relaxation: Whether relaxation is enabled
        min_periods: Minimum number of periods required PER DAY
        relaxation_step_pct: Percentage of the original flex threshold to add per relaxation
            step (controls how aggressively flex widens with each attempt)
        max_relaxation_attempts: Maximum number of flex levels (attempts) to try per day
            before giving up (each attempt runs the full filter matrix)
        should_show_callback: Callback function(level_override) -> bool
            Returns True if periods should be shown with given filter overrides. Pass None
            to use original configured filter values.
        time: TimeService instance (required)

    Returns:
        Tuple of (periods_result, relaxation_metadata):
        - periods_result: Same format as calculate_periods() output, with periods from all days
        - relaxation_metadata: Dict with relaxation information (aggregated across all days)

    """
    # Import here to avoid circular dependency
    from .core import (  # noqa: PLC0415
        calculate_periods,
    )

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
            "%sRelaxation strategy: %.1f%% flex increment per step (%d flex levels x 4 filter combinations)",
            INDENT_L0,
            relaxation_step_pct,
            max_relaxation_attempts,
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
    prices_by_day = group_prices_by_day(all_prices, time=time)

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
        day_result = calculate_periods(day_prices, config=config, time=time)
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
        day_relaxed_result, day_metadata = relax_single_day(
            day_prices=day_prices,
            config=config,
            min_periods=min_periods,
            relaxation_step_pct=relaxation_step_pct,
            max_relaxation_attempts=max_relaxation_attempts,
            should_show_callback=should_show_callback,
            baseline_periods=day_periods,
            day_label=str(day),
            time=time,
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
    recalculate_period_metadata(all_periods, time=time)

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


def relax_single_day(  # noqa: PLR0913 - Comprehensive filter relaxation per day
    day_prices: list[dict],
    config: PeriodConfig,
    min_periods: int,
    relaxation_step_pct: int,
    max_relaxation_attempts: int,
    should_show_callback: Callable[[str | None], bool],
    baseline_periods: list[dict],
    day_label: str,
    *,
    time: TimeService,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Run comprehensive relaxation for a single day.

    NEW STRATEGY: For each flex level, try all filter combinations before increasing flex.
    This finds solutions faster by relaxing filters first (cheaper than increasing flex).

    Per flex level (6.25%, 7.5%, 8.75%, 10%), try in order:
    1. Original filters (level=configured)
    2. Relax level filter (level=any)

    This ensures we find the minimal relaxation needed. Example:
    - If periods exist at flex=6.25% with level=any, we find them before trying flex=7.5%

    Args:
        day_prices: Price data for this specific day only
        config: Base period configuration
        min_periods: Minimum periods needed for this day
        relaxation_step_pct: Relaxation increment percentage
        max_relaxation_attempts: Maximum number of flex levels (attempts) to try for this day
        should_show_callback: Filter visibility callback(level_override)
                             Returns True if periods should be shown with given overrides.
        baseline_periods: Periods found with normal filters
        day_label: Label for logging (e.g., "2025-11-11")
        time: TimeService instance (required)

    Returns:
        Tuple of (periods_result, metadata) for this day

    """
    # Import here to avoid circular dependency
    from .core import (  # noqa: PLC0415
        calculate_periods,
    )

    accumulated_periods = baseline_periods.copy()
    original_flex = abs(config.flex)
    relaxation_increment = original_flex * (relaxation_step_pct / 100.0)
    phases_used = []
    relaxed_result = None

    baseline_standalone = len([p for p in baseline_periods if not p.get("is_extension")])

    attempts = max(1, int(max_relaxation_attempts))

    # Flex levels: original + N steps (e.g., 5% → 6.25% → ...)
    for flex_step in range(1, attempts + 1):
        new_flex = original_flex + (flex_step * relaxation_increment)
        new_flex = min(new_flex, 100.0)

        if config.reverse_sort:
            new_flex = -new_flex

        # Try filter combinations for this flex level
        # Each tuple contains: level_override, label_suffix
        filter_attempts = [
            (None, ""),  # Original config
            ("any", "+level_any"),  # Relax level filter
        ]

        for lvl_override, label_suffix in filter_attempts:
            # Check if this combination is allowed by user config
            if not should_show_callback(lvl_override):
                continue

            # Calculate periods with this flex + filter combination
            # Apply level override if specified
            level_filter_value = lvl_override if lvl_override is not None else config.level_filter

            # Log filter changes
            flex_pct = round(abs(new_flex) * 100, 1)
            if lvl_override is not None:
                _LOGGER.debug(
                    "%sDay %s flex=%.1f%%: OVERRIDING level_filter: %s → %s",
                    INDENT_L2,
                    day_label,
                    flex_pct,
                    config.level_filter or "None",
                    str(lvl_override).upper(),
                )

            relaxed_config = config._replace(
                flex=new_flex,
                level_filter=level_filter_value,
            )
            relaxed_result = calculate_periods(day_prices, config=relaxed_config, time=time)
            new_periods = relaxed_result["periods"]

            # Build relaxation level label BEFORE marking periods
            relaxation_level = f"price_diff_{flex_pct}%{label_suffix}"
            phases_used.append(relaxation_level)

            # Mark NEW periods with their specific relaxation metadata BEFORE merging
            for period in new_periods:
                period["relaxation_active"] = True
                # Set the metadata immediately - this preserves which phase found this period
                mark_periods_with_relaxation([period], relaxation_level, original_flex, abs(new_flex))

            # Merge with accumulated periods
            merged, standalone_count = resolve_period_overlaps(
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
                recalculate_period_metadata(merged, time=time)
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

    recalculate_period_metadata(accumulated_periods, time=time)

    if relaxed_result:
        result = relaxed_result.copy()
    else:
        result = {"periods": accumulated_periods, "metadata": {}, "reference_data": {}}
    result["periods"] = accumulated_periods

    return result, {"phases_used": phases_used}
