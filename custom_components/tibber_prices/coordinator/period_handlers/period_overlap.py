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

    _LOGGER.debug(
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


def resolve_period_overlaps(
    existing_periods: list[dict],
    new_relaxed_periods: list[dict],
) -> tuple[list[dict], int]:
    """
    Resolve overlaps between existing periods and newly found relaxed periods.

    Adjacent or overlapping periods are merged into single continuous periods.
    The newer period's relaxation attributes override the older period's.

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
    _LOGGER.debug(
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
        tolerance_seconds = 60  # 1 minute tolerance
        is_duplicate = False
        for existing in merged:
            if (
                abs((relaxed_start - existing["start"]).total_seconds()) < tolerance_seconds
                and abs((relaxed_end - existing["end"]).total_seconds()) < tolerance_seconds
            ):
                is_duplicate = True
                _LOGGER.debug(
                    "%sSkipping duplicate period %s-%s (already exists)",
                    INDENT_L1,
                    relaxed_start.strftime("%H:%M"),
                    relaxed_end.strftime("%H:%M"),
                )
                break

        if is_duplicate:
            continue

        # Find periods that are adjacent or overlapping (should be merged)
        periods_to_merge = []
        for idx, existing in enumerate(merged):
            existing_start = existing["start"]
            existing_end = existing["end"]

            # Check if adjacent (no gap) or overlapping
            is_adjacent = relaxed_end == existing_start or relaxed_start == existing_end
            is_overlapping = relaxed_start < existing_end and relaxed_end > existing_start

            if is_adjacent or is_overlapping:
                periods_to_merge.append((idx, existing))
                _LOGGER.debug(
                    "%sPeriod %s-%s %s with existing period %s-%s",
                    INDENT_L1,
                    relaxed_start.strftime("%H:%M"),
                    relaxed_end.strftime("%H:%M"),
                    "overlaps" if is_overlapping else "is adjacent to",
                    existing_start.strftime("%H:%M"),
                    existing_end.strftime("%H:%M"),
                )

        if not periods_to_merge:
            # No merge needed - add as new period
            merged.append(relaxed)
            periods_added += 1
            _LOGGER.debug(
                "%sAdded new period %s-%s (no overlap/adjacency)",
                INDENT_L1,
                relaxed_start.strftime("%H:%M"),
                relaxed_end.strftime("%H:%M"),
            )
        else:
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
