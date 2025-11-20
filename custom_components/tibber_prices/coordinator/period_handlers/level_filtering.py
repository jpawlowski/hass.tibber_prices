"""
Interval-level filtering logic for period calculation.

Key Concepts:
- Flex Filter: Limits price distance from daily min/max
- Min Distance Filter: Ensures prices are significantly different from average
- Dynamic Scaling: Min_Distance reduces at high Flex to prevent conflicts

See docs/development/period-calculation-theory.md for detailed explanation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .types import TibberPricesIntervalCriteria

from custom_components.tibber_prices.const import PRICE_LEVEL_MAPPING

# Module-local log indentation (each module starts at level 0)
INDENT_L0 = ""  # Entry point / main function

# Flex threshold for min_distance scaling
FLEX_SCALING_THRESHOLD = 0.20  # 20% - start adjusting min_distance
SCALE_FACTOR_WARNING_THRESHOLD = 0.8  # Log when reduction > 20%


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
    criteria: TibberPricesIntervalCriteria,
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

    # CRITICAL: Adjust min_distance dynamically based on flex to prevent conflicts
    # Problem: High flex (e.g., 50%) can conflict with fixed min_distance (e.g., 5%)
    # Solution: When flex is high, reduce min_distance requirement proportionally
    #
    # At low flex (≤20%), use full min_distance (e.g., 5%)
    # At high flex (≥40%), reduce min_distance to avoid over-filtering
    # Linear interpolation between 20-40% flex range

    adjusted_min_distance = criteria.min_distance_from_avg
    flex_abs = abs(criteria.flex)

    if flex_abs > FLEX_SCALING_THRESHOLD:
        # Scale down min_distance as flex increases
        # At 20% flex: multiplier = 1.0 (full min_distance)
        # At 40% flex: multiplier = 0.5 (half min_distance)
        # At 50% flex: multiplier = 0.25 (quarter min_distance)
        flex_excess = flex_abs - 0.20  # How much above 20%
        scale_factor = max(0.25, 1.0 - (flex_excess * 2.5))  # Linear reduction, min 25%
        adjusted_min_distance = criteria.min_distance_from_avg * scale_factor

        # Log adjustment at DEBUG level (only when significant reduction)
        if scale_factor < SCALE_FACTOR_WARNING_THRESHOLD:
            import logging  # noqa: PLC0415

            _LOGGER = logging.getLogger(__name__)  # noqa: N806
            _LOGGER.debug(
                "High flex %.1f%% detected: Reducing min_distance %.1f%% → %.1f%% (scale %.2f)",
                flex_abs * 100,
                criteria.min_distance_from_avg,
                adjusted_min_distance,
                scale_factor,
            )

    # Minimum distance from average (using adjusted value)
    if criteria.reverse_sort:
        # Peak price: must be at least adjusted_min_distance% above average
        min_distance_threshold = criteria.avg_price * (1 + adjusted_min_distance / 100)
        meets_min_distance = price >= min_distance_threshold
    else:
        # Best price: must be at least adjusted_min_distance% below average
        min_distance_threshold = criteria.avg_price * (1 - adjusted_min_distance / 100)
        meets_min_distance = price <= min_distance_threshold

    return in_flex, meets_min_distance
