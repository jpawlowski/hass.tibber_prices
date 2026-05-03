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

from custom_components.tibber_prices.utils.price import calculate_coefficient_of_variation


def find_cheapest_contiguous_window(
    intervals: list[dict[str, Any]],
    duration_intervals: int,
    *,
    reverse: bool = False,
    power_profile: list[int] | None = None,
) -> dict[str, Any] | None:
    """
    Find the cheapest (or most expensive) contiguous window of exactly N intervals.

    Uses a sliding window algorithm (O(n)) when no power profile is given.
    With a power profile, uses O(n\u00d7k) direct scoring so that the window with the
    lowest weighted cost (\u03a3 price[i] \u00d7 watt[i]) is selected instead of lowest
    average price. This ensures high-wattage phases of the cycle land on cheap intervals.

    Args:
        intervals: Sorted list of price interval dicts with 'startsAt' and 'total' keys.
            Must be pre-sorted by startsAt in ascending order.
        duration_intervals: Number of consecutive intervals required.
        reverse: If True, find the most expensive window instead of cheapest.
        power_profile: Optional watt value per interval. Only the first
            duration_intervals values are used (profile may be longer). When
            provided, scoring uses \u03a3 price[i] \u00d7 watt[i] instead of \u03a3 price[i].

    Returns:
        Dict with window details (start, end, intervals, statistics),
        or None if not enough intervals available.

    """
    n = len(intervals)
    if n == 0 or duration_intervals <= 0 or n < duration_intervals:
        return None

    best_intervals: list[dict[str, Any]] | None = None
    best_sum: float | None = None

    # Price-level filtering can create gaps in time. Search each truly contiguous
    # run independently so the returned window always matches real timestamps.
    for segment in group_intervals_into_segments(intervals):
        segment_intervals = segment["intervals"]
        if len(segment_intervals) < duration_intervals:
            continue

        if power_profile:
            # With a power profile the weights rotate with each window position,
            # so a simple O(1) sliding update is not possible. Recompute each score
            # directly. Only the first duration_intervals weights are used.
            segment_best_sum: float = sum(
                segment_intervals[k]["total"] * power_profile[k] for k in range(duration_intervals)
            )
            segment_best_start = 0
            for i in range(1, len(segment_intervals) - duration_intervals + 1):
                score = sum(segment_intervals[i + k]["total"] * power_profile[k] for k in range(duration_intervals))
                if (score > segment_best_sum) if reverse else (score < segment_best_sum):
                    segment_best_sum = score
                    segment_best_start = i
        else:
            window_sum = sum(segment_intervals[i]["total"] for i in range(duration_intervals))
            segment_best_sum = window_sum
            segment_best_start = 0
            for i in range(1, len(segment_intervals) - duration_intervals + 1):
                window_sum += segment_intervals[i + duration_intervals - 1]["total"]
                window_sum -= segment_intervals[i - 1]["total"]
                if (window_sum > segment_best_sum) if reverse else (window_sum < segment_best_sum):
                    segment_best_sum = window_sum
                    segment_best_start = i

        if best_sum is None or ((segment_best_sum > best_sum) if reverse else (segment_best_sum < best_sum)):
            best_sum = segment_best_sum
            best_intervals = segment_intervals[segment_best_start : segment_best_start + duration_intervals]

    if best_intervals is None:
        return None

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

    Uses dynamic programming to find an exact selection of `count` intervals
    where every contiguous run has at least `min_segment` intervals. Real time
    gaps break segments even if the filtered list remains index-contiguous.
    """
    n = len(intervals)

    contiguous_with_prev = [False] * n
    for i in range(1, n):
        prev_start = _parse_timestamp(intervals[i - 1]["startsAt"])
        curr_start = _parse_timestamp(intervals[i]["startsAt"])
        contiguous_with_prev[i] = curr_start - prev_start == timedelta(minutes=15)

    def is_better(new_cost: float, old_cost: float | None) -> bool:
        if old_cost is None:
            return True
        return new_cost > old_cost if reverse else new_cost < old_cost

    current_states: dict[tuple[int, int], float] = {(0, 0): 0.0}
    backpointers: list[dict[tuple[int, int], tuple[tuple[int, int], bool]]] = [{} for _ in range(n + 1)]

    for idx, interval in enumerate(intervals, start=1):
        next_states: dict[tuple[int, int], float] = {}
        next_back: dict[tuple[int, int], tuple[tuple[int, int], bool]] = {}
        interval_cost = float(interval["total"])

        for prev_state, prev_cost in current_states.items():
            selected_count, run_len = prev_state
            effective_run_len = run_len

            if idx > 1 and not contiguous_with_prev[idx - 1] and run_len != 0:
                if run_len < min_segment:
                    continue
                effective_run_len = 0

            if effective_run_len in (0, min_segment):
                skip_state = (selected_count, 0)
                if is_better(prev_cost, next_states.get(skip_state)):
                    next_states[skip_state] = prev_cost
                    next_back[skip_state] = (prev_state, False)

            if selected_count >= count:
                continue

            if effective_run_len == 0:
                new_run_len = 1
            elif effective_run_len < min_segment:
                new_run_len = effective_run_len + 1
            else:
                new_run_len = min_segment

            take_state = (selected_count + 1, new_run_len)
            take_cost = prev_cost + interval_cost
            if is_better(take_cost, next_states.get(take_state)):
                next_states[take_state] = take_cost
                next_back[take_state] = (prev_state, True)

        current_states = next_states
        backpointers[idx] = next_back

    best_state: tuple[int, int] | None = None
    best_cost: float | None = None
    for state, cost in current_states.items():
        selected_count, run_len = state
        if selected_count != count or run_len not in (0, min_segment):
            continue
        if is_better(cost, best_cost):
            best_state = state
            best_cost = cost

    if best_state is None:
        return None

    selected_indices: list[int] = []
    state = best_state
    for idx in range(n, 0, -1):
        prev_state, took_interval = backpointers[idx][state]
        if took_interval:
            selected_indices.append(idx - 1)
        state = prev_state

    selected_indices.reverse()
    result_intervals = [intervals[i] for i in selected_indices]
    segments = group_intervals_into_segments(result_intervals)

    if len(result_intervals) != count:
        return None
    if any(seg["interval_count"] < min_segment for seg in segments):
        return None

    return {
        "intervals": result_intervals,
        "segments": segments,
    }


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
            "coefficient_of_variation": None,
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

    # Calculate coefficient of variation (CV) as quality indicator
    cv = calculate_coefficient_of_variation(prices)
    cv_rounded = round(cv, round_decimals) if cv is not None else None

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
            "coefficient_of_variation": cv_rounded,
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
        "coefficient_of_variation": cv_rounded,
        "estimated_total_cost": estimated_cost,
    }


def _parse_timestamp(ts: str | datetime) -> datetime:
    """Parse an ISO timestamp string or pass through a datetime object."""
    if isinstance(ts, datetime):
        return ts
    return datetime.fromisoformat(ts)
