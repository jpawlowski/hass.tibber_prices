"""Period merging and overlap resolution logic."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.util import dt as dt_util

from .types import MINUTES_PER_INTERVAL

_LOGGER = logging.getLogger(__name__)

# Module-local log indentation (each module starts at level 0)
INDENT_L0 = ""  # Entry point / main function
INDENT_L1 = "  "  # Nested logic / loop iterations
INDENT_L2 = "    "  # Deeper nesting


def merge_adjacent_periods_at_midnight(periods: list[list[dict]]) -> list[list[dict]]:
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


def recalculate_period_metadata(periods: list[dict]) -> None:
    """
    Recalculate period metadata after merging periods.

    Updates period_position, periods_total, and periods_remaining for all periods
    based on chronological order.

    This must be called after resolve_period_overlaps() to ensure metadata
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


def split_period_by_overlaps(
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


def resolve_period_overlaps(  # noqa: PLR0912, PLR0915, C901 - Complex overlap resolution with replacement and extension logic
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
        "%sresolve_period_overlaps called: existing=%d, new=%d, baseline=%d",
        INDENT_L0,
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
                    INDENT_L1,
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
                    INDENT_L1,
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
                            INDENT_L1,
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
                            INDENT_L1,
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
                            INDENT_L2,
                            period_to_remove["start"].strftime("%H:%M"),
                            period_to_remove["end"].strftime("%H:%M"),
                            relaxed_start.strftime("%H:%M"),
                            relaxed_end.strftime("%H:%M"),
                        )

            # Split the relaxed period into non-overlapping segments
            segments = split_period_by_overlaps(relaxed_start, relaxed_end, overlaps)

            # If no segments (completely overlapped), but we replaced periods, add the full period
            if not segments and periods_to_replace:
                _LOGGER.debug(
                    "%sAdding full replacement period %s-%s (no non-overlapping segments)",
                    INDENT_L2,
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
                        INDENT_L2,
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
