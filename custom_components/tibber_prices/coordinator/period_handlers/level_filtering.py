"""Interval-level filtering logic for period calculation."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .types import IntervalCriteria

from custom_components.tibber_prices.const import PRICE_LEVEL_MAPPING


def check_level_with_gap_tolerance(
    interval_level: int,
    level_order: int,
    consecutive_gaps: int,
    gap_count: int,
    *,
    reverse_sort: bool,
) -> tuple[bool, bool, int]:
    """
    Check if interval meets level requirement with gap tolerance.

    Args:
        interval_level: Level value of current interval (from PRICE_LEVEL_MAPPING)
        level_order: Required level value
        consecutive_gaps: Current count of consecutive gap intervals
        gap_count: Maximum allowed consecutive gap intervals
        reverse_sort: True for peak price, False for best price

    Returns:
        Tuple of (meets_level, is_gap, new_consecutive_gaps):
        - meets_level: True if interval qualifies (exact match or within gap tolerance)
        - is_gap: True if this is a gap interval (deviates by exactly 1 step)
        - new_consecutive_gaps: Updated gap counter

    """
    if reverse_sort:
        # Peak price: interval must be >= level_order (e.g., EXPENSIVE or higher)
        meets_level_exact = interval_level >= level_order
        # Gap: exactly 1 step below (e.g., NORMAL when expecting EXPENSIVE)
        is_gap = interval_level == level_order - 1
    else:
        # Best price: interval must be <= level_order (e.g., CHEAP or lower)
        meets_level_exact = interval_level <= level_order
        # Gap: exactly 1 step above (e.g., NORMAL when expecting CHEAP)
        is_gap = interval_level == level_order + 1

    # Apply gap tolerance
    if meets_level_exact:
        return True, False, 0  # Meets level, not a gap, reset counter
    if is_gap and consecutive_gaps < gap_count:
        return True, True, consecutive_gaps + 1  # Allowed gap, increment counter
    return False, False, 0  # Doesn't meet level, reset counter


def apply_level_filter(
    price_data: dict,
    level_order: int | None,
    consecutive_gaps: int,
    gap_count: int,
    *,
    reverse_sort: bool,
) -> tuple[bool, int, bool]:
    """
    Apply level filter to a single interval.

    Args:
        price_data: Price data dict with "level" key
        level_order: Required level value (from PRICE_LEVEL_MAPPING) or None if disabled
        consecutive_gaps: Current count of consecutive gap intervals
        gap_count: Maximum allowed consecutive gap intervals
        reverse_sort: True for peak price, False for best price

    Returns:
        Tuple of (meets_level, new_consecutive_gaps, is_gap)

    """
    if level_order is None:
        return True, consecutive_gaps, False

    interval_level = PRICE_LEVEL_MAPPING.get(price_data.get("level", "NORMAL"), 0)
    meets_level, is_gap, new_consecutive_gaps = check_level_with_gap_tolerance(
        interval_level, level_order, consecutive_gaps, gap_count, reverse_sort=reverse_sort
    )
    return meets_level, new_consecutive_gaps, is_gap


def check_interval_criteria(
    price: float,
    criteria: IntervalCriteria,
) -> tuple[bool, bool]:
    """
    Check if interval meets flex and minimum distance criteria.

    Args:
        price: Interval price
        criteria: Interval criteria (ref_price, avg_price, flex, etc.)

    Returns:
        Tuple of (in_flex, meets_min_distance)

    """
    # Calculate percentage difference from reference
    percent_diff = ((price - criteria.ref_price) / criteria.ref_price) * 100 if criteria.ref_price != 0 else 0.0

    # Check if interval qualifies for the period
    in_flex = percent_diff >= criteria.flex * 100 if criteria.reverse_sort else percent_diff <= criteria.flex * 100

    # Minimum distance from average
    if criteria.reverse_sort:
        # Peak price: must be at least min_distance_from_avg% above average
        min_distance_threshold = criteria.avg_price * (1 + criteria.min_distance_from_avg / 100)
        meets_min_distance = price >= min_distance_threshold
    else:
        # Best price: must be at least min_distance_from_avg% below average
        min_distance_threshold = criteria.avg_price * (1 - criteria.min_distance_from_avg / 100)
        meets_min_distance = price <= min_distance_threshold

    return in_flex, meets_min_distance
