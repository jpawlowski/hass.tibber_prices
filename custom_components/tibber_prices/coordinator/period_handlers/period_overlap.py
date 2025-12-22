"""Period overlap resolution logic."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService

_LOGGER = logging.getLogger(__name__)
_LOGGER_DETAILS = logging.getLogger(__name__ + ".details")

# Module-local log indentation (each module starts at level 0)
INDENT_L0 = ""  # Entry point / main function
INDENT_L1 = "  "  # Nested logic / loop iterations
INDENT_L2 = "    "  # Deeper nesting


def _estimate_merged_cv(period1: dict, period2: dict) -> float | None:
    """
    Estimate the CV of a merged period from two period summaries.

    Since we don't have the raw prices, we estimate using the combined min/max range.
    This is a conservative estimate - the actual CV could be higher or lower.

    Formula: CV ≈ (range / 2) / mean * 100
    Where range = max - min, mean = (min + max) / 2

    This approximation assumes roughly uniform distribution within the range.
    """
    p1_min = period1.get("price_min")
    p1_max = period1.get("price_max")
    p2_min = period2.get("price_min")
    p2_max = period2.get("price_max")

    if None in (p1_min, p1_max, p2_min, p2_max):
        return None

    # Cast to float - None case handled above
    combined_min = min(float(p1_min), float(p2_min))  # type: ignore[arg-type]
    combined_max = max(float(p1_max), float(p2_max))  # type: ignore[arg-type]

    if combined_min <= 0:
        return None

    combined_mean = (combined_min + combined_max) / 2
    price_range = combined_max - combined_min

    # CV estimate based on range (assuming uniform distribution)
    # For uniform distribution: std_dev ≈ range / sqrt(12) ≈ range / 3.46
    return (price_range / 3.46) / combined_mean * 100


def recalculate_period_metadata(periods: list[dict], *, time: TibberPricesTimeService) -> None:
    """
    Recalculate period metadata after merging periods.

    Updates period_position, periods_total, and periods_remaining for all periods
    based on chronological order.

    This must be called after resolve_period_overlaps() to ensure metadata
    reflects the final merged period list.

    Args:
        periods: List of period summary dicts (mutated in-place)
        time: TibberPricesTimeService instance (required)

    """
    if not periods:
        return

    # Sort periods chronologically by start time
    periods.sort(key=lambda p: p.get("start") or time.now())

    # Update metadata for all periods
    total_periods = len(periods)

    for position, period in enumerate(periods, 1):
        period["period_position"] = position
        period["periods_total"] = total_periods
        period["periods_remaining"] = total_periods - position


def merge_adjacent_periods(period1: dict, period2: dict) -> dict:
    """
    Merge two adjacent or overlapping periods into one.

    The newer period's relaxation attributes override the older period's.
    Takes the earliest start time and latest end time.

    Relaxation attributes from the newer period (period2) override those from period1:
    - relaxation_active
    - relaxation_level
    - relaxation_threshold_original_%
    - relaxation_threshold_applied_%
    - period_interval_level_gap_count
    - period_interval_smoothed_count

    Args:
        period1: First period (older baseline or relaxed period)
        period2: Second period (newer relaxed period with higher flex)

    Returns:
        Merged period dict with combined time span and newer period's attributes

    """
    # Take earliest start and latest end
    merged_start = min(period1["start"], period2["start"])
    merged_end = max(period1["end"], period2["end"])
    merged_duration = int((merged_end - merged_start).total_seconds() / 60)

    # Start with period1 as base
    merged = period1.copy()

    # Update time boundaries
    merged["start"] = merged_start
    merged["end"] = merged_end
    merged["duration_minutes"] = merged_duration

    # Override with period2's relaxation attributes (newer/higher flex wins)
    relaxation_attrs = [
        "relaxation_active",
        "relaxation_level",
        "relaxation_threshold_original_%",
        "relaxation_threshold_applied_%",
        "period_interval_level_gap_count",
        "period_interval_smoothed_count",
    ]

    for attr in relaxation_attrs:
        if attr in period2:
            merged[attr] = period2[attr]

    # Mark as merged (for debugging)
    merged["merged_from"] = {
        "period1_start": period1["start"].isoformat(),
        "period1_end": period1["end"].isoformat(),
        "period2_start": period2["start"].isoformat(),
        "period2_end": period2["end"].isoformat(),
    }

    _LOGGER_DETAILS.debug(
        "%sMerged periods: %s-%s + %s-%s → %s-%s (duration: %d min)",
        INDENT_L2,
        period1["start"].strftime("%H:%M"),
        period1["end"].strftime("%H:%M"),
        period2["start"].strftime("%H:%M"),
        period2["end"].strftime("%H:%M"),
        merged_start.strftime("%H:%M"),
        merged_end.strftime("%H:%M"),
        merged_duration,
    )

    return merged


def _check_merge_quality_gate(periods_to_merge: list[tuple[int, dict]], relaxed: dict) -> bool:
    """
    Check if merging would create a period that's too heterogeneous.

    Returns True if merge is allowed, False if blocked by Quality Gate.
    """
    from .types import PERIOD_MAX_CV  # noqa: PLC0415

    relaxed_start = relaxed["start"]
    relaxed_end = relaxed["end"]

    for _idx, existing in periods_to_merge:
        estimated_cv = _estimate_merged_cv(existing, relaxed)
        if estimated_cv is not None and estimated_cv > PERIOD_MAX_CV:
            _LOGGER.debug(
                "Merge blocked by Quality Gate: %s-%s + %s-%s would have CV≈%.1f%% (max: %.1f%%)",
                existing["start"].strftime("%H:%M"),
                existing["end"].strftime("%H:%M"),
                relaxed_start.strftime("%H:%M"),
                relaxed_end.strftime("%H:%M"),
                estimated_cv,
                PERIOD_MAX_CV,
            )
            return False
    return True


def _would_swallow_existing(relaxed: dict, existing_periods: list[dict]) -> bool:
    """
    Check if the relaxed period would "swallow" any existing period.

    A period is "swallowed" if the new relaxed period completely contains it.
    In this case, we should NOT merge - the existing smaller period is more
    homogeneous and should be preserved.

    This prevents relaxation from replacing good small periods with larger,
    more heterogeneous ones.

    Returns:
        True if any existing period would be swallowed (merge should be blocked)
        False if safe to proceed with merge evaluation

    """
    relaxed_start = relaxed["start"]
    relaxed_end = relaxed["end"]

    for existing in existing_periods:
        existing_start = existing["start"]
        existing_end = existing["end"]

        # Check if relaxed completely contains existing
        if relaxed_start <= existing_start and relaxed_end >= existing_end:
            _LOGGER.debug(
                "Blocking merge: %s-%s would swallow %s-%s (keeping smaller period)",
                relaxed_start.strftime("%H:%M"),
                relaxed_end.strftime("%H:%M"),
                existing_start.strftime("%H:%M"),
                existing_end.strftime("%H:%M"),
            )
            return True

    return False


def _is_duplicate_period(relaxed: dict, existing_periods: list[dict], tolerance_seconds: int = 60) -> bool:
    """Check if relaxed period is a duplicate of any existing period."""
    relaxed_start = relaxed["start"]
    relaxed_end = relaxed["end"]

    for existing in existing_periods:
        if (
            abs((relaxed_start - existing["start"]).total_seconds()) < tolerance_seconds
            and abs((relaxed_end - existing["end"]).total_seconds()) < tolerance_seconds
        ):
            _LOGGER_DETAILS.debug(
                "%sSkipping duplicate period %s-%s (already exists)",
                INDENT_L1,
                relaxed_start.strftime("%H:%M"),
                relaxed_end.strftime("%H:%M"),
            )
            return True
    return False


def _find_adjacent_or_overlapping(relaxed: dict, existing_periods: list[dict]) -> list[tuple[int, dict]]:
    """Find all periods that are adjacent to or overlapping with the relaxed period."""
    relaxed_start = relaxed["start"]
    relaxed_end = relaxed["end"]
    periods_to_merge = []

    for idx, existing in enumerate(existing_periods):
        existing_start = existing["start"]
        existing_end = existing["end"]

        # Check if adjacent (no gap) or overlapping
        is_adjacent = relaxed_end == existing_start or relaxed_start == existing_end
        is_overlapping = relaxed_start < existing_end and relaxed_end > existing_start

        if is_adjacent or is_overlapping:
            periods_to_merge.append((idx, existing))
            _LOGGER_DETAILS.debug(
                "%sPeriod %s-%s %s with existing period %s-%s",
                INDENT_L1,
                relaxed_start.strftime("%H:%M"),
                relaxed_end.strftime("%H:%M"),
                "overlaps" if is_overlapping else "is adjacent to",
                existing_start.strftime("%H:%M"),
                existing_end.strftime("%H:%M"),
            )

    return periods_to_merge


def resolve_period_overlaps(
    existing_periods: list[dict],
    new_relaxed_periods: list[dict],
) -> tuple[list[dict], int]:
    """
    Resolve overlaps between existing periods and newly found relaxed periods.

    Adjacent or overlapping periods are merged into single continuous periods.
    The newer period's relaxation attributes override the older period's.

    Quality Gate: Merging is blocked if the combined period would have
    an estimated CV above PERIOD_MAX_CV (25%), to prevent creating
    periods with excessive internal price variation.

    This function is called incrementally after each relaxation phase:
    - Phase 1: existing = baseline, new = first relaxation
    - Phase 2: existing = baseline + phase 1, new = second relaxation
    - Phase 3: existing = baseline + phase 1 + phase 2, new = third relaxation

    Args:
        existing_periods: All previously found periods (baseline + earlier relaxation phases)
        new_relaxed_periods: Periods found in current relaxation phase (will be merged if adjacent)

    Returns:
        Tuple of (merged_periods, new_periods_count):
        - merged_periods: All periods after merging, sorted by start time
        - new_periods_count: Number of new periods added (some may have been merged)

    """
    _LOGGER_DETAILS.debug(
        "%sresolve_period_overlaps called: existing=%d, new=%d",
        INDENT_L0,
        len(existing_periods),
        len(new_relaxed_periods),
    )

    if not new_relaxed_periods:
        return existing_periods.copy(), 0

    if not existing_periods:
        # No existing periods - return all new periods
        return new_relaxed_periods.copy(), len(new_relaxed_periods)

    merged = existing_periods.copy()
    periods_added = 0

    for relaxed in new_relaxed_periods:
        relaxed_start = relaxed["start"]
        relaxed_end = relaxed["end"]

        # Check if this period is duplicate (exact match within tolerance)
        if _is_duplicate_period(relaxed, merged):
            continue

        # Check if this period would "swallow" an existing smaller period
        # In that case, skip it - the smaller existing period is more homogeneous
        if _would_swallow_existing(relaxed, merged):
            continue

        # Find periods that are adjacent or overlapping (should be merged)
        periods_to_merge = _find_adjacent_or_overlapping(relaxed, merged)

        if not periods_to_merge:
            # No merge needed - add as new period
            merged.append(relaxed)
            periods_added += 1
            _LOGGER_DETAILS.debug(
                "%sAdded new period %s-%s (no overlap/adjacency)",
                INDENT_L1,
                relaxed_start.strftime("%H:%M"),
                relaxed_end.strftime("%H:%M"),
            )
            continue

        # Quality Gate: Check if merging would create a period that's too heterogeneous
        should_merge = _check_merge_quality_gate(periods_to_merge, relaxed)

        if not should_merge:
            # Don't merge - add as separate period instead
            merged.append(relaxed)
            periods_added += 1
            _LOGGER_DETAILS.debug(
                "%sAdded new period %s-%s separately (merge blocked by CV gate)",
                INDENT_L1,
                relaxed_start.strftime("%H:%M"),
                relaxed_end.strftime("%H:%M"),
            )
            continue

        # Merge with all adjacent/overlapping periods
        # Start with the new relaxed period
        merged_period = relaxed.copy()

        # Remove old periods (in reverse order to maintain indices)
        for idx, existing in reversed(periods_to_merge):
            merged_period = merge_adjacent_periods(existing, merged_period)
            merged.pop(idx)

        # Add the merged result
        merged.append(merged_period)

        # Count as added if we merged exactly one existing period
        # (means we extended/merged, not replaced multiple)
        if len(periods_to_merge) == 1:
            periods_added += 1

    # Sort all periods by start time
    merged.sort(key=lambda p: p["start"])

    return merged, periods_added
