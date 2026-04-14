"""
Pure algorithms for finding cheapest price windows.

Two independent algorithms:
1. find_cheapest_contiguous_window — Sliding window for appliance scheduling
2. find_cheapest_n_intervals — Cheapest N picks for flexible-load scheduling

These are stateless pure functions with no Home Assistant dependencies.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import statistics
from typing import Any


def find_cheapest_contiguous_window(
    intervals: list[dict[str, Any]],
    duration_intervals: int,
    *,
    reverse: bool = False,
) -> dict[str, Any] | None:
    """
    Find the cheapest (or most expensive) contiguous window of exactly N intervals.

    Uses a sliding window algorithm (O(n)) to find the window with the
    lowest (or highest) average price.

    Args:
        intervals: Sorted list of price interval dicts with 'startsAt' and 'total' keys.
            Must be pre-sorted by startsAt in ascending order.
        duration_intervals: Number of consecutive intervals required.
        reverse: If True, find the most expensive window instead of cheapest.

    Returns:
        Dict with window details (start, end, intervals, statistics),
        or None if not enough intervals available.

    """
    n = len(intervals)
    if n == 0 or duration_intervals <= 0 or n < duration_intervals:
        return None

    # Calculate initial window sum
    window_sum = sum(intervals[i]["total"] for i in range(duration_intervals))
    best_sum = window_sum
    best_start = 0

    # Slide the window
    for i in range(1, n - duration_intervals + 1):
        window_sum += intervals[i + duration_intervals - 1]["total"]
        window_sum -= intervals[i - 1]["total"]
        if (window_sum > best_sum) if reverse else (window_sum < best_sum):
            best_sum = window_sum
            best_start = i

    best_intervals = intervals[best_start : best_start + duration_intervals]
    return {
        "start": best_intervals[0]["startsAt"],
        "end_interval_start": best_intervals[-1]["startsAt"],
        "intervals": best_intervals,
    }


def find_cheapest_n_intervals(
    intervals: list[dict[str, Any]],
    count: int,
    min_segment_intervals: int = 1,
    *,
    reverse: bool = False,
) -> dict[str, Any] | None:
    """
    Find the cheapest (or most expensive) N intervals, not necessarily contiguous.

    Picks the cheapest (or most expensive) intervals by price, then groups them
    into contiguous segments. If min_segment_intervals > 1, short segments are
    discarded and replaced with next-cheapest/most-expensive available intervals
    until all segments meet the minimum length.

    Args:
        intervals: Sorted list of price interval dicts with 'startsAt' and 'total' keys.
            Must be pre-sorted by startsAt in ascending order.
        count: Number of intervals to select.
        min_segment_intervals: Minimum contiguous length for each segment.
            Default 1 means no constraint.
        reverse: If True, find the most expensive intervals instead of cheapest.

    Returns:
        Dict with schedule details (segments, intervals, statistics),
        or None if not enough intervals available.

    """
    n = len(intervals)
    if n == 0 or count <= 0 or n < count:
        return None

    if min_segment_intervals <= 1:
        # Simple case: pick cheapest/most expensive N, then sort chronologically
        indexed = [(i, iv) for i, iv in enumerate(intervals)]
        indexed.sort(key=lambda x: x[1]["total"], reverse=reverse)
        selected_indices = sorted(idx for idx, _ in indexed[:count])
        selected = [intervals[i] for i in selected_indices]
        segments = group_intervals_into_segments(selected)
        return {
            "intervals": selected,
            "segments": segments,
        }

    # Complex case: enforce minimum segment length
    return _find_with_min_segment(intervals, count, min_segment_intervals, reverse=reverse)


def _find_with_min_segment(
    intervals: list[dict[str, Any]],
    count: int,
    min_segment: int,
    *,
    reverse: bool = False,
) -> dict[str, Any] | None:
    """
    Find cheapest/most expensive N intervals with minimum segment length constraint.

    Iteratively picks intervals, discards segments that are too
    short, and replaces them with next-best alternatives.

    Converges in at most `count` iterations (worst case: every replacement
    creates a new short segment that gets discarded).
    """
    n = len(intervals)

    # Build index lookup: interval original index → position
    # Price-sorted indices for picking cheapest/most expensive available
    price_order = sorted(range(n), key=lambda i: intervals[i]["total"], reverse=reverse)

    selected: set[int] = set()
    excluded: set[int] = set()

    # Initial pick: cheapest 'count' intervals
    picked = 0
    for idx in price_order:
        if picked >= count:
            break
        if idx not in excluded:
            selected.add(idx)
            picked += 1

    if len(selected) < count:
        return None

    # Iterative refinement: discard short segments, replace with next-cheapest
    max_iterations = count + 1  # Safety bound
    for _ in range(max_iterations):
        sorted_selected = sorted(selected)
        segments = _group_indices_into_segments(sorted_selected)

        short_segments = [seg for seg in segments if len(seg) < min_segment]
        if not short_segments:
            break  # All segments meet minimum length

        # Exclude all indices in short segments
        for seg in short_segments:
            for idx in seg:
                selected.discard(idx)
                excluded.add(idx)

        # Refill from price order
        needed = count - len(selected)
        for idx in price_order:
            if needed <= 0:
                break
            if idx not in selected and idx not in excluded:
                selected.add(idx)
                needed -= 1

        if len(selected) < count:
            # Not enough intervals available after exclusions
            # Return best effort with what we have
            break

    sorted_selected = sorted(selected)
    result_intervals = [intervals[i] for i in sorted_selected]
    segments = group_intervals_into_segments(result_intervals)

    return {
        "intervals": result_intervals,
        "segments": segments,
    }


def _group_indices_into_segments(indices: list[int]) -> list[list[int]]:
    """Group sorted integer indices into contiguous runs."""
    if not indices:
        return []

    segments: list[list[int]] = [[indices[0]]]
    for i in range(1, len(indices)):
        if indices[i] == indices[i - 1] + 1:
            segments[-1].append(indices[i])
        else:
            segments.append([indices[i]])
    return segments


def group_intervals_into_segments(
    intervals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Group chronologically sorted intervals into contiguous segments.

    Two intervals are contiguous if the second starts exactly 15 minutes
    after the first.

    Args:
        intervals: Chronologically sorted interval dicts with 'startsAt' key.

    Returns:
        List of segment dicts, each containing:
        - start: ISO timestamp of first interval
        - end_interval_start: ISO timestamp of last interval in segment
        - duration_minutes: Total segment duration
        - interval_count: Number of intervals in segment
        - intervals: The interval dicts in this segment

    """
    if not intervals:
        return []

    segments: list[dict[str, Any]] = []
    current_segment: list[dict[str, Any]] = [intervals[0]]

    for i in range(1, len(intervals)):
        prev_start = _parse_timestamp(intervals[i - 1]["startsAt"])
        curr_start = _parse_timestamp(intervals[i]["startsAt"])

        if curr_start - prev_start == timedelta(minutes=15):
            current_segment.append(intervals[i])
        else:
            segments.append(_build_segment(current_segment))
            current_segment = [intervals[i]]

    segments.append(_build_segment(current_segment))
    return segments


def _build_segment(intervals: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a segment dict from a list of contiguous intervals."""
    return {
        "start": intervals[0]["startsAt"],
        "end_interval_start": intervals[-1]["startsAt"],
        "duration_minutes": len(intervals) * 15,
        "interval_count": len(intervals),
        "intervals": intervals,
    }


def calculate_window_statistics(
    intervals: list[dict[str, Any]],
    unit_factor: int = 1,
    round_decimals: int = 4,
    interval_minutes: int = 15,
    power_profile: list[int] | None = None,
) -> dict[str, float | None]:
    """
    Calculate price statistics for a list of intervals.

    Args:
        intervals: List of interval dicts with 'total' key (base currency).
        unit_factor: Multiplication factor for display (100 for subunit, 1 for base).
        round_decimals: Number of decimal places for rounding.
        interval_minutes: Duration of each interval in minutes (for cost calculation).
        power_profile: Optional list of power values in watts, one per interval.
            If shorter than the interval list, the last value is repeated.
            When provided, estimated_total_cost reflects variable power draw instead
            of a constant 1 kW load, and estimated_load_kwh is added to the result.

    Returns:
        Dict with price_mean, price_median, price_min, price_max, price_spread,
        and estimated_total_cost (total cost for the given or constant 1 kW load).
        When power_profile is provided, also includes estimated_load_kwh.

    """
    if not intervals:
        result: dict[str, float | None] = {
            "price_mean": None,
            "price_median": None,
            "price_min": None,
            "price_max": None,
            "price_spread": None,
            "estimated_total_cost": None,
        }
        if power_profile is not None:
            result["estimated_load_kwh"] = None
        return result

    prices = [iv["total"] * unit_factor for iv in intervals]
    mean = round(statistics.mean(prices), round_decimals)
    median = round(statistics.median(prices), round_decimals)
    price_min = round(min(prices), round_decimals)
    price_max = round(max(prices), round_decimals)
    spread = round(price_max - price_min, round_decimals)

    hours_per_interval = interval_minutes / 60

    if power_profile is not None:
        # Extend profile to cover all intervals by repeating the last value
        last_watts = power_profile[-1] if power_profile else 1000
        profile = list(power_profile) + [last_watts] * max(0, len(intervals) - len(power_profile))
        load_kwh_per_interval = [w / 1000 * hours_per_interval for w in profile[: len(intervals)]]
        estimated_cost = round(
            sum(p * kwh for p, kwh in zip(prices, load_kwh_per_interval, strict=False)), round_decimals
        )
        estimated_load_kwh = round(sum(load_kwh_per_interval), round_decimals)
        return {
            "price_mean": mean,
            "price_median": median,
            "price_min": price_min,
            "price_max": price_max,
            "price_spread": spread,
            "estimated_total_cost": estimated_cost,
            "estimated_load_kwh": estimated_load_kwh,
        }

    # Estimated cost for running a 1 kW constant load during all intervals
    # Each interval covers interval_minutes/60 hours, price is per kWh
    estimated_cost = round(sum(p * hours_per_interval for p in prices), round_decimals)

    return {
        "price_mean": mean,
        "price_median": median,
        "price_min": price_min,
        "price_max": price_max,
        "price_spread": spread,
        "estimated_total_cost": estimated_cost,
    }


def _parse_timestamp(ts: str | datetime) -> datetime:
    """Parse an ISO timestamp string or pass through a datetime object."""
    if isinstance(ts, datetime):
        return ts
    return datetime.fromisoformat(ts)
