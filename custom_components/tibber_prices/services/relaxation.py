"""Service relaxation logic for progressive filter loosening.

When allow_relaxation is enabled (default), services progressively loosen
user-provided filters to guarantee a result whenever price data is available.

Relaxation phases (in order):
1. Halve min_distance_from_avg → remove it entirely
2. Expand level filters one step at a time → remove all level filters
3. Reduce duration by 1 interval per step (up to dynamic or user-specified cap)
"""

from __future__ import annotations

from dataclasses import dataclass
import logging

from .helpers import INTERVAL_MINUTES

_LOGGER = logging.getLogger(__name__)

PRICE_LEVEL_ORDER = ("very_cheap", "cheap", "normal", "expensive", "very_expensive")

#: Never reduce duration below this many intervals (30 min)
MIN_RELAXED_DURATION_INTERVALS = 2


@dataclass(frozen=True)
class RelaxationStep:
    """Parameters for a single relaxation attempt."""

    step_number: int
    min_distance_from_avg: float | None
    max_price_level: str | None
    min_price_level: str | None
    duration_reduction: int  # intervals subtracted from original duration
    phase: str  # "distance" | "level_filter" | "duration"


def calculate_max_duration_reduction_intervals(
    total_intervals: int,
    explicit_flexibility_minutes: int | None = None,
) -> int:
    """Calculate maximum number of intervals that duration can be reduced by.

    Args:
        total_intervals: Original requested duration in intervals.
        explicit_flexibility_minutes: User-specified cap in minutes (None = auto).

    Returns:
        Maximum number of intervals to reduce (0 = no reduction allowed).

    """
    if explicit_flexibility_minutes is not None:
        return max(0, explicit_flexibility_minutes // INTERVAL_MINUTES)
    # Dynamic: ~20% of duration, min 0 for short tasks, max 4 intervals (60 min)
    if total_intervals <= 3:
        return 0
    return min(4, max(1, total_intervals // 5))


def build_level_filter_steps(
    max_price_level: str | None,
    min_price_level: str | None,
    *,
    reverse: bool,
) -> list[tuple[str | None, str | None]]:
    """Build progressive level filter relaxation tuples (max_level, min_level).

    For cheapest (reverse=False): expand max_price_level upward.
    For most expensive (reverse=True): expand min_price_level downward.
    Then remove remaining filters.
    """
    if max_price_level is None and min_price_level is None:
        return []

    steps: list[tuple[str | None, str | None]] = []
    cur_max = max_price_level
    cur_min = min_price_level

    # Primary direction: widen the dominant constraint
    if not reverse and cur_max is not None:
        idx = PRICE_LEVEL_ORDER.index(cur_max)
        for next_idx in range(idx + 1, len(PRICE_LEVEL_ORDER)):
            cur_max = PRICE_LEVEL_ORDER[next_idx]
            steps.append((cur_max, cur_min))
        cur_max = None
        # If min still set, add intermediate step (max removed, min stays)
        if cur_min is not None:
            steps.append((None, cur_min))

    if reverse and cur_min is not None:
        idx = PRICE_LEVEL_ORDER.index(cur_min)
        for next_idx in range(idx - 1, -1, -1):
            cur_min = PRICE_LEVEL_ORDER[next_idx]
            steps.append((cur_max, cur_min))
        cur_min = None
        if cur_max is not None:
            steps.append((cur_max, None))

    # Final: remove all level filters
    if not steps or steps[-1] != (None, None):
        steps.append((None, None))

    return steps


def generate_relaxation_steps(
    *,
    min_distance_from_avg: float | None,
    max_price_level: str | None,
    min_price_level: str | None,
    total_intervals: int,
    min_duration_intervals: int,
    max_duration_reduction_intervals: int,
    reverse: bool,
) -> list[RelaxationStep]:
    """Generate progressive relaxation steps for service retry logic.

    Each step represents a complete set of filter parameters to try.
    Steps are ordered from least to most relaxed.

    Args:
        min_distance_from_avg: Original distance threshold (None = not set).
        max_price_level: Original max level filter (None = not set).
        min_price_level: Original min level filter (None = not set).
        total_intervals: Original requested duration in intervals.
        min_duration_intervals: Absolute minimum duration (never go below this).
        max_duration_reduction_intervals: Maximum intervals to reduce duration by.
        reverse: True for most_expensive services.

    Returns:
        List of RelaxationStep objects to try in order.

    """
    steps: list[RelaxationStep] = []
    step_num = 0

    # Track cumulative state — each phase inherits from previous
    cur_distance = min_distance_from_avg
    cur_max = max_price_level
    cur_min = min_price_level

    # Phase 1: Relax min_distance_from_avg
    if cur_distance is not None:
        halved = round(cur_distance / 2, 1)
        if halved >= 0.1:
            step_num += 1
            steps.append(
                RelaxationStep(
                    step_number=step_num,
                    min_distance_from_avg=halved,
                    max_price_level=cur_max,
                    min_price_level=cur_min,
                    duration_reduction=0,
                    phase="distance",
                )
            )
        step_num += 1
        steps.append(
            RelaxationStep(
                step_number=step_num,
                min_distance_from_avg=None,
                max_price_level=cur_max,
                min_price_level=cur_min,
                duration_reduction=0,
                phase="distance",
            )
        )
        cur_distance = None

    # Phase 2: Relax level filters
    level_steps = build_level_filter_steps(cur_max, cur_min, reverse=reverse)
    for lvl_max, lvl_min in level_steps:
        step_num += 1
        steps.append(
            RelaxationStep(
                step_number=step_num,
                min_distance_from_avg=None,
                max_price_level=lvl_max,
                min_price_level=lvl_min,
                duration_reduction=0,
                phase="level_filter",
            )
        )

    # Phase 3: Reduce duration (1 interval per step)
    for reduction in range(1, max_duration_reduction_intervals + 1):
        new_dur = total_intervals - reduction
        if new_dur >= min_duration_intervals:
            step_num += 1
            steps.append(
                RelaxationStep(
                    step_number=step_num,
                    min_distance_from_avg=None,
                    max_price_level=None,
                    min_price_level=None,
                    duration_reduction=reduction,
                    phase="duration",
                )
            )

    return steps
