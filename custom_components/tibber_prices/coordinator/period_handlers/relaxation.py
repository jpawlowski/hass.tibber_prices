"""Relaxation strategy for finding minimum periods per day."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import date

    from custom_components.tibber_prices.coordinator.time_service import TimeService

    from .types import PeriodConfig

from .period_overlap import (
    recalculate_period_metadata,
    resolve_period_overlaps,
)
from .types import (
    INDENT_L0,
    INDENT_L1,
    INDENT_L2,
)

_LOGGER = logging.getLogger(__name__)

# Flex thresholds for warnings (see docs/development/period-calculation-theory.md)
# With relaxation active, high base flex is counterproductive (reduces relaxation effectiveness)
FLEX_WARNING_THRESHOLD_RELAXATION = 0.25  # 25% - INFO: suggest lowering to 15-20%
MAX_FLEX_HARD_LIMIT = 0.50  # 50% - hard maximum flex value
FLEX_HIGH_THRESHOLD_RELAXATION = 0.30  # 30% - WARNING: base flex too high for relaxation mode


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
    for day in available_days:
        day_periods = periods_by_day.get(day, [])
        period_count = len(day_periods)
        if period_count < min_periods:
            _LOGGER.debug(
                "Day %s has only %d periods (need %d) - continuing relaxation",
                day,
                period_count,
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

    Phase 1: Increase flex threshold step-by-step (up to max_relaxation_attempts)
    Phase 2: Disable level filter (set to "any")

    Args:
        all_prices: All price data points
        config: Base period configuration
        enable_relaxation: Whether relaxation is enabled
        min_periods: Minimum number of periods required PER DAY
        max_relaxation_attempts: Maximum number of flex levels (attempts) to try per day
            before giving up (each attempt runs the full filter matrix). With 3% increment
            per step, 11 attempts allows escalation from 15% to 48% flex.
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
            "%sRelaxation strategy: 3%% fixed flex increment per step (%d flex levels x 2 filter combinations)",
            INDENT_L0,
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

    # Validate we have price data for today/future
    today = time.now().date()
    future_prices = [p for p in all_prices if time.get_interval_time(p).date() >= today]

    if not future_prices:
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

    # Count available days for logging
    prices_by_day = group_prices_by_day(all_prices, time=time)
    total_days = len(prices_by_day)

    _LOGGER.info(
        "Calculating baseline periods for %d days...",
        total_days,
    )
    _LOGGER.debug(
        "%sProcessing ALL %d price intervals together (allows midnight crossing)",
        INDENT_L1,
        len(future_prices),
    )

    # === BASELINE CALCULATION (process ALL prices together) ===
    baseline_result = calculate_periods(future_prices, config=config, time=time)
    all_periods = baseline_result["periods"]

    # Count periods per day for min_periods check
    periods_by_day = group_periods_by_day(all_periods)
    days_meeting_requirement = 0

    for day in sorted(prices_by_day.keys()):
        day_periods = periods_by_day.get(day, [])
        period_count = len(day_periods)

        _LOGGER.debug(
            "%sDay %s baseline: Found %d periods%s",
            INDENT_L1,
            day,
            period_count,
            f" (need {min_periods})" if enable_relaxation else "",
        )

        if period_count >= min_periods:
            days_meeting_requirement += 1

    # Check if relaxation is needed
    relaxation_was_needed = False
    all_phases_used: list[str] = []

    if enable_relaxation and days_meeting_requirement < total_days:
        # At least one day doesn't have enough periods
        _LOGGER.debug(
            "%sBaseline insufficient (%d/%d days met target) - starting relaxation",
            INDENT_L1,
            days_meeting_requirement,
            total_days,
        )
        relaxation_was_needed = True

        # Run relaxation on ALL prices together
        relaxed_result, relax_metadata = relax_all_prices(
            all_prices=future_prices,
            config=config,
            min_periods=min_periods,
            max_relaxation_attempts=max_relaxation_attempts,
            should_show_callback=should_show_callback,
            baseline_periods=all_periods,
            time=time,
        )

        all_periods = relaxed_result["periods"]
        if relax_metadata.get("phases_used"):
            all_phases_used = relax_metadata["phases_used"]

        # Recount after relaxation
        periods_by_day = group_periods_by_day(all_periods)
        days_meeting_requirement = 0
        for day in sorted(prices_by_day.keys()):
            day_periods = periods_by_day.get(day, [])
            period_count = len(day_periods)
            if period_count >= min_periods:
                days_meeting_requirement += 1
    elif enable_relaxation:
        _LOGGER.debug(
            "%sAll %d days met target with baseline - no relaxation needed",
            INDENT_L1,
            total_days,
        )

    # Sort periods by start time
    all_periods.sort(key=lambda p: p["start"])

    # Recalculate metadata for combined periods
    recalculate_period_metadata(all_periods, time=time)

    # Build final result
    final_result = baseline_result.copy()
    final_result["periods"] = all_periods

    total_periods = len(all_periods)

    return final_result, {
        "relaxation_active": relaxation_was_needed,
        "relaxation_attempted": relaxation_was_needed,
        "min_periods_requested": min_periods,
        "periods_found": total_periods,
        "phases_used": list(set(all_phases_used)),  # Unique phases used across all days
        "days_processed": total_days,
        "days_meeting_requirement": days_meeting_requirement,
        "relaxation_incomplete": days_meeting_requirement < total_days,
    }


def relax_all_prices(  # noqa: PLR0913 - Comprehensive filter relaxation requires many parameters and statements
    all_prices: list[dict],
    config: PeriodConfig,
    min_periods: int,
    max_relaxation_attempts: int,
    should_show_callback: Callable[[str | None], bool],
    baseline_periods: list[dict],
    *,
    time: TimeService,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Relax filters for all prices until min_periods per day is reached.

    Strategy: Try increasing flex by 3% increments, then relax level filter.
    Processes all prices together, allowing periods to cross midnight boundaries.
    Returns when ALL days have min_periods (or max attempts exhausted).

    Args:
        all_prices: All price intervals (today + future)
        config: Base period configuration
        min_periods: Target number of periods PER DAY
        max_relaxation_attempts: Maximum flex levels to try
        should_show_callback: Callback to check if a flex level should be shown
        baseline_periods: Baseline periods (before relaxation)
        time: TimeService instance

    Returns:
        Tuple of (result_dict, metadata_dict)

    """
    # Import here to avoid circular dependency
    from .core import (  # noqa: PLC0415
        calculate_periods,
    )

    flex_increment = 0.03  # 3% per step (hard-coded for reliability)
    base_flex = abs(config.flex)
    original_level_filter = config.level_filter
    existing_periods = list(baseline_periods)  # Start with baseline
    phases_used = []

    # Get available days from prices for checking
    prices_by_day = group_prices_by_day(all_prices, time=time)
    total_days = len(prices_by_day)

    # Try flex levels (3% increments)
    attempts = max(1, int(max_relaxation_attempts))
    for attempt in range(1, attempts + 1):
        current_flex = base_flex + (attempt * flex_increment)

        # Stop if we exceed hard maximum
        if current_flex > MAX_FLEX_HARD_LIMIT:
            _LOGGER.debug(
                "%s    Reached 50%% flex hard limit",
                INDENT_L2,
            )
            break

        phase_label = f"flex={current_flex * 100:.1f}%"

        # Skip this flex level if callback says not to show it
        if not should_show_callback(phase_label):
            continue

        # Try current flex with level="any" (in relaxation mode)
        if original_level_filter != "any":
            _LOGGER.debug(
                "%s    Flex=%.1f%%: OVERRIDING level_filter: %s → ANY",
                INDENT_L2,
                current_flex * 100,
                original_level_filter,
            )

        relaxed_config = config._replace(
            flex=current_flex if config.flex >= 0 else -current_flex,
            level_filter="any",
        )

        phase_label_full = f"flex={current_flex * 100:.1f}% +level_any"
        _LOGGER.debug(
            "%s    Trying %s: config has %d intervals (all days together), level_filter=%s",
            INDENT_L2,
            phase_label_full,
            len(all_prices),
            relaxed_config.level_filter,
        )

        # Process ALL prices together (allows midnight crossing)
        result = calculate_periods(all_prices, config=relaxed_config, time=time)
        new_periods = result["periods"]

        _LOGGER.debug(
            "%s    %s: calculate_periods returned %d periods",
            INDENT_L2,
            phase_label_full,
            len(new_periods),
        )

        # Resolve overlaps between existing and new periods
        combined, standalone_count = resolve_period_overlaps(
            existing_periods=existing_periods,
            new_relaxed_periods=new_periods,
        )

        # Count periods per day to check if requirement met
        periods_by_day = group_periods_by_day(combined)
        days_meeting_requirement = 0

        for day in sorted(prices_by_day.keys()):
            day_periods = periods_by_day.get(day, [])
            period_count = len(day_periods)
            if period_count >= min_periods:
                days_meeting_requirement += 1

            _LOGGER.debug(
                "%s      Day %s: %d periods%s",
                INDENT_L2,
                day,
                period_count,
                " ✓" if period_count >= min_periods else f" (need {min_periods})",
            )

        total_periods = len(combined)
        _LOGGER.debug(
            "%s    %s: found %d periods total, %d/%d days meet requirement",
            INDENT_L2,
            phase_label_full,
            total_periods,
            days_meeting_requirement,
            total_days,
        )

        existing_periods = combined
        phases_used.append(phase_label_full)

        # Check if ALL days reached target
        if days_meeting_requirement >= total_days:
            _LOGGER.info(
                "Success with %s - all %d days have %d+ periods (%d total)",
                phase_label_full,
                total_days,
                min_periods,
                total_periods,
            )
            break

    # Build final result
    final_result = (
        result.copy() if "result" in locals() else {"periods": baseline_periods, "metadata": {}, "reference_data": {}}
    )
    final_result["periods"] = existing_periods

    return final_result, {
        "phases_used": phases_used,
        "periods_found": len(existing_periods),
    }
