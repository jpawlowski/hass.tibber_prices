"""
Shape-based period extension: extend periods into adjacent cheap/expensive intervals.

After periods are identified by the core algorithm, this module optionally extends
each period's boundaries to include any directly-adjacent intervals that carry a
favourable price level relevant to the period type:

- Best price periods  → extend into VERY_CHEAP neighbours; fall back to CHEAP
                        on each side where no VERY_CHEAP neighbour exists.
- Peak price periods  → extend into VERY_EXPENSIVE neighbours; fall back to
                        EXPENSIVE on each side where no VERY_EXPENSIVE exists.

The fallback is evaluated **per side independently**: one side may extend via
VERY_CHEAP while the other side falls back to CHEAP.

Extension is purely additive and opt-in (disabled by default).  It does not affect
the core period-finding logic; periods that would not normally be found are not
created by this step.
"""

from __future__ import annotations

from datetime import timedelta
import statistics
from typing import TYPE_CHECKING, Any

from custom_components.tibber_prices.const import (
    PRICE_LEVEL_CHEAP,
    PRICE_LEVEL_EXPENSIVE,
    PRICE_LEVEL_MAPPING,
    PRICE_LEVEL_VERY_CHEAP,
    PRICE_LEVEL_VERY_EXPENSIVE,
)
from custom_components.tibber_prices.utils.price import aggregate_period_levels, aggregate_period_ratings

from .period_statistics import (
    calculate_aggregated_rating_difference,
    calculate_period_price_diff,
    calculate_period_price_statistics,
)

if TYPE_CHECKING:
    from datetime import datetime

    from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService

    from .types import TibberPricesThresholdConfig

_INTERVAL_DURATION = timedelta(minutes=15)


def extend_periods_for_shape(
    periods: list[dict[str, Any]],
    all_prices: list[dict[str, Any]],
    price_context: dict[str, Any],
    *,
    reverse_sort: bool,
    max_extension_intervals: int,
    thresholds: TibberPricesThresholdConfig,
    time: TibberPricesTimeService,
) -> list[dict[str, Any]]:
    """
    Extend each period into adjacent cheap/expensive intervals.

    For best price periods (reverse_sort=False):
        Primary: extend into VERY_CHEAP neighbours.
        Fallback: extend into CHEAP neighbours (per side, only if no VERY_CHEAP found).
    For peak price periods (reverse_sort=True):
        Primary: extend into VERY_EXPENSIVE neighbours.
        Fallback: extend into EXPENSIVE neighbours (per side, only if no VERY_EXPENSIVE found).

    Only intervals that are directly contiguous with the period and carry the
    required level are added.  At most *max_extension_intervals* are consumed on
    each side independently.  Period statistics are fully recalculated after
    any extension.

    Args:
        periods: Period summary dicts from ``extract_period_summaries``.
        all_prices: All enriched price intervals (yesterday + today + tomorrow).
        price_context: Dict with ``ref_prices`` and ``avg_prices`` per calendar day.
        reverse_sort: ``True`` for peak price, ``False`` for best price.
        max_extension_intervals: Maximum extra intervals that may be added per side.
        thresholds: Threshold configuration for level / rating aggregation.
        time: Time-service instance used to resolve ``startsAt`` timestamps.

    Returns:
        Updated list of period dicts, potentially with extended boundaries and
        recalculated statistics.  Unmodified periods are returned as-is.

    """
    if not periods or max_extension_intervals <= 0:
        return periods

    if reverse_sort:
        primary_level = PRICE_LEVEL_VERY_EXPENSIVE
        fallback_level = PRICE_LEVEL_EXPENSIVE
    else:
        primary_level = PRICE_LEVEL_VERY_CHEAP
        fallback_level = PRICE_LEVEL_CHEAP

    # Build a lookup dict: local datetime → full interval dict
    interval_index: dict[datetime, dict[str, Any]] = {}
    for iv in all_prices:
        t = time.get_interval_time(iv)
        if t is not None:
            interval_index[t] = iv

    return [
        _extend_period_edges(
            period,
            interval_index,
            primary_level=primary_level,
            fallback_level=fallback_level,
            max_intervals=max_extension_intervals,
            thresholds=thresholds,
            price_context=price_context,
        )
        for period in periods
    ]


# ── private helpers ────────────────────────────────────────────────────────────


def _walk_contiguous(
    interval_index: dict[datetime, dict[str, Any]],
    start_cursor: datetime,
    step: timedelta,
    target_level: str,
    max_intervals: int,
) -> list[dict[str, Any]]:
    """
    Walk contiguously from *start_cursor* in direction *step*, collecting intervals.

    Stops when the next interval is missing from the index, does not carry
    *target_level*, or the *max_intervals* cap is reached.

    Args:
        interval_index: Lookup map of ``{starts_at_datetime: interval_dict}``.
        start_cursor: First position to check (already offset from the period edge).
        step: ``+_INTERVAL_DURATION`` for rightward, ``-_INTERVAL_DURATION`` for leftward.
        target_level: Required ``level`` value (e.g. ``"VERY_CHEAP"``).
        max_intervals: Maximum intervals to collect.

    Returns:
        Collected intervals in chronological order (reversed for leftward walks).

    """
    additions: list[dict[str, Any]] = []
    cursor = start_cursor
    for _ in range(max_intervals):
        iv = interval_index.get(cursor)
        if iv is None or iv.get("level") != target_level:
            break
        additions.append(iv)
        cursor += step

    # For leftward walks the list was built newest-first; reverse to chronological
    if step < timedelta(0):
        additions.reverse()

    return additions


def _fallback_blocked_by_majority(
    intervals: list[dict[str, Any]],
    primary_level: str,
    fallback_level: str,
) -> bool:
    """Return ``True`` when fallback extension should be suppressed.

    If *primary_level* intervals strictly outnumber *fallback_level* intervals
    in the existing period, the period's character is predominantly primary.
    Extending with *fallback_level* would dilute that character; the geometric
    flex bonus of the core algorithm provides a better boundary in that case.

    Args:
        intervals: Existing period interval list.
        primary_level: Preferred level (``VERY_CHEAP`` / ``VERY_EXPENSIVE``).
        fallback_level: Extension candidate level (``CHEAP`` / ``EXPENSIVE``).

    Returns:
        ``True`` if fallback extension should be blocked.

    """
    primary_count = sum(1 for iv in intervals if iv.get("level") == primary_level)
    fallback_count = sum(1 for iv in intervals if iv.get("level") == fallback_level)
    return primary_count > fallback_count


def _is_spike_adjacent(
    beyond_iv: dict[str, Any] | None,
    fallback_level: str,
    reverse_sort: bool,
) -> bool:
    """Return ``True`` when the interval just outside the extension is a spike.

    If the interval immediately beyond the last collected fallback extension is
    "worse" than *fallback_level* (more expensive for best-price, cheaper for
    peak-price), the extension intervals form a ramp leading into a spike and
    should be discarded.

    Args:
        beyond_iv: Interval dict just outside the collected extension, or ``None``.
        fallback_level: The level used for the fallback extension.
        reverse_sort: ``True`` for peak-price, ``False`` for best-price.

    Returns:
        ``True`` if the extension should be dropped.

    """
    if beyond_iv is None:
        return False
    beyond_level = beyond_iv.get("level")
    if beyond_level is None:
        return False
    fallback_value = PRICE_LEVEL_MAPPING.get(fallback_level, 0)
    beyond_value = PRICE_LEVEL_MAPPING.get(beyond_level, 0)
    if reverse_sort:
        # Peak: "worse" means cheaper than the extension level
        return beyond_value < fallback_value
    # Best: "worse" means more expensive than the extension level
    return beyond_value > fallback_value


def _extend_period_edges(
    period: dict[str, Any],
    interval_index: dict[datetime, dict[str, Any]],
    *,
    primary_level: str,
    fallback_level: str,
    max_intervals: int,
    thresholds: TibberPricesThresholdConfig,
    price_context: dict[str, Any],
) -> dict[str, Any]:
    """
    Consume adjacent intervals on both edges of a period.

    Each side is evaluated independently:
    1. Try extending into *primary_level* neighbours (VERY_CHEAP / VERY_EXPENSIVE).
    2. If no primary-level neighbours were found on that side, fall back to
       *fallback_level* neighbours (CHEAP / EXPENSIVE).

    The original period dict is never mutated; a new dict is returned.
    If no extension is possible on either side, the original dict is returned.

    Args:
        period: Period summary dict with ``start`` and ``end`` datetime keys.
        interval_index: Lookup map of ``{starts_at_datetime: interval_dict}``.
        primary_level: Preferred level (``"VERY_CHEAP"`` or ``"VERY_EXPENSIVE"``).
        fallback_level: Fallback level (``"CHEAP"`` or ``"EXPENSIVE"``).
        max_intervals: Maximum intervals that may be added on each side.
        thresholds: Threshold config for aggregation helpers.
        price_context: Reference prices / averages per calendar day.

    Returns:
        Extended (or original) period summary dict.

    """
    start: datetime = period["start"]
    end: datetime = period["end"]
    # ``end`` is the exclusive boundary: the last included interval starts at
    # ``end - _INTERVAL_DURATION``.

    reverse_sort = primary_level == PRICE_LEVEL_VERY_EXPENSIVE
    backward_step = -_INTERVAL_DURATION
    forward_step = _INTERVAL_DURATION

    # Collect original intervals early – needed for the majority gate below.
    original_intervals = _collect_original_intervals(start, end, interval_index)

    # ── walk LEFT (earlier than period start) ─────────────────────────────────
    left_cursor = start - _INTERVAL_DURATION
    left_additions = _walk_contiguous(interval_index, left_cursor, backward_step, primary_level, max_intervals)
    left_used_fallback = False
    if not left_additions:
        # Fallback: only if the period interior is not predominantly primary_level.
        # When primary_level (e.g. VERY_CHEAP) strictly outnumbers fallback_level
        # (e.g. CHEAP) inside the period, adding fallback edges dilutes the
        # period's character.  Rely on the geometric flex bonus instead.
        if not _fallback_blocked_by_majority(original_intervals, primary_level, fallback_level):
            left_additions = _walk_contiguous(interval_index, left_cursor, backward_step, fallback_level, max_intervals)
            left_used_fallback = bool(left_additions)

    # Look-beyond guard (fallback only): if the interval immediately outside the
    # collected extensions is worse than fallback_level (e.g. a price spike just
    # before a run of CHEAP intervals), those intervals form a ramp into the spike
    # and should not be included.
    if left_used_fallback:
        one_beyond_left = start - _INTERVAL_DURATION * (len(left_additions) + 1)
        if _is_spike_adjacent(interval_index.get(one_beyond_left), fallback_level, reverse_sort):
            left_additions = []

    # ── walk RIGHT (later than period end) ────────────────────────────────────
    right_additions = _walk_contiguous(interval_index, end, forward_step, primary_level, max_intervals)
    right_used_fallback = False
    if not right_additions:
        # Fallback: same majority gate as left side.
        if not _fallback_blocked_by_majority(original_intervals, primary_level, fallback_level):
            right_additions = _walk_contiguous(interval_index, end, forward_step, fallback_level, max_intervals)
            right_used_fallback = bool(right_additions)

    # Look-beyond guard (fallback only).
    if right_used_fallback:
        one_beyond_right = end + _INTERVAL_DURATION * len(right_additions)
        if _is_spike_adjacent(interval_index.get(one_beyond_right), fallback_level, reverse_sort):
            right_additions = []

    total_added = len(left_additions) + len(right_additions)
    if total_added == 0:
        return period

    # ── rebuild full interval list for the extended period ────────────────────
    all_period_intervals = left_additions + original_intervals + right_additions

    # ── recalculate boundaries ────────────────────────────────────────────────
    new_start = start - _INTERVAL_DURATION * len(left_additions)
    new_end = end + _INTERVAL_DURATION * len(right_additions)
    new_duration_minutes = int((new_end - new_start).total_seconds() // 60)
    new_interval_count = len(all_period_intervals)

    # ── recalculate price statistics ──────────────────────────────────────────
    price_stats = calculate_period_price_statistics(all_period_intervals)
    period_price_diff, period_price_diff_pct = calculate_period_price_diff(
        price_stats["price_mean"], new_start, price_context
    )
    rating_diff_pct = calculate_aggregated_rating_difference(all_period_intervals)

    # ── recalculate level / rating aggregates ─────────────────────────────────
    new_level = aggregate_period_levels(all_period_intervals)
    new_rating: str | None = None
    if thresholds.threshold_low is not None and thresholds.threshold_high is not None:
        new_rating, _ = aggregate_period_ratings(
            all_period_intervals,
            thresholds.threshold_low,
            thresholds.threshold_high,
        )

    # ── recalculate volatility (coefficient of variation) ────────────────────
    prices_for_vol = [float(p["total"]) for p in all_period_intervals if "total" in p]
    cv_pct: float | None = None
    if len(prices_for_vol) >= 2:
        mean_p = statistics.mean(prices_for_vol)
        if mean_p > 0:
            cv_pct = round(statistics.stdev(prices_for_vol) / mean_p * 100, 1)

    # ── assemble updated period dict (keep structural fields, update statistics) ─
    updated: dict[str, Any] = {
        **period,
        # Time fields
        "start": new_start,
        "end": new_end,
        "duration_minutes": new_duration_minutes,
        # Core decision attributes
        "level": new_level,
        "rating_level": new_rating,
        "rating_difference_%": rating_diff_pct,
        # Price statistics
        "price_mean": price_stats["price_mean"],
        "price_median": price_stats["price_median"],
        "price_min": price_stats["price_min"],
        "price_max": price_stats["price_max"],
        "price_spread": price_stats["price_spread"],
        "price_coefficient_variation_%": cv_pct,
        # Detail
        "period_interval_count": new_interval_count,
        # Extension metadata
        "extension_intervals_added": total_added,
    }

    # Refresh period price diff (replaces old value from base period)
    if reverse_sort:
        updated.pop("period_price_diff_from_daily_min", None)
        updated.pop("period_price_diff_from_daily_min_%", None)
        if period_price_diff is not None:
            updated["period_price_diff_from_daily_max"] = period_price_diff
            if period_price_diff_pct is not None:
                updated["period_price_diff_from_daily_max_%"] = period_price_diff_pct
    else:
        updated.pop("period_price_diff_from_daily_max", None)
        updated.pop("period_price_diff_from_daily_max_%", None)
        if period_price_diff is not None:
            updated["period_price_diff_from_daily_min"] = period_price_diff
            if period_price_diff_pct is not None:
                updated["period_price_diff_from_daily_min_%"] = period_price_diff_pct

    return updated


def _collect_original_intervals(
    start: datetime,
    end: datetime,
    interval_index: dict[datetime, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Reconstruct the ordered interval list for an existing period from the index."""
    result: list[dict[str, Any]] = []
    cursor = start
    while cursor < end:
        iv = interval_index.get(cursor)
        if iv is not None:
            result.append(iv)
        cursor += _INTERVAL_DURATION
    return result
