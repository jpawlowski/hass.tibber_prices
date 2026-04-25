"""
Interval-level filtering logic for period calculation.

Key Concepts:
- Flex Filter: Limits price distance from daily min/max
- Min Distance Filter: Ensures prices are significantly different from average
- Dynamic Scaling: Min_Distance reduces at high Flex to prevent conflicts

See docs/development/period-calculation-theory.md for detailed explanation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

    from .types import TibberPricesIntervalCriteria

from custom_components.tibber_prices.const import PRICE_LEVEL_MAPPING

# Module-local log indentation (each module starts at level 0)
INDENT_L0 = ""  # Entry point / main function

# Flex threshold for min_distance scaling
FLEX_SCALING_THRESHOLD = 0.20  # 20% - start adjusting min_distance
SCALE_FACTOR_WARNING_THRESHOLD = 0.8  # Log when reduction > 20%

# Low absolute price threshold for min_distance scaling (in major currency unit, e.g. EUR/NOK)
# When the daily average price is below this, percentage-based min_distance becomes unreliable:
# even the daily minimum may not fall far enough below average in relative terms.
# Scale min_distance linearly to 0 as avg_price approaches 0.
# Value: 0.10 EUR/NOK = 10 ct/øre.
# At avg ≥ 0.10: full min_distance. At avg = 0.05: 50% min_distance. At avg = 0: 0%.
LOW_PRICE_AVG_THRESHOLD = 0.10  # EUR/NOK major unit (= 10 ct/øre in subunit)


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

    CRITICAL: This function works with NORMALIZED values (always positive):
    - criteria.flex: Always positive (e.g., 0.20 for 20%)
    - criteria.min_distance_from_avg: Always positive (e.g., 5.0 for 5%)
    - criteria.reverse_sort: Determines direction (True=Peak, False=Best)

    Args:
        price: Interval price
        criteria: Interval criteria (ref_price, avg_price, flex, etc.)

    Returns:
        Tuple of (in_flex, meets_min_distance)

    """
    # ============================================================
    # FAST PATH: Negative/zero prices always qualify as best price
    # ============================================================
    # When price ≤ 0 the consumer is paid or gets free electricity.
    # This is unconditionally the cheapest possible outcome regardless
    # of daily average, flex setting, or level filter.
    # Bypasses both flex AND min_distance: a negative price is always
    # maximally "far below average" in the economically meaningful sense.
    if not criteria.reverse_sort and price <= 0:
        return True, True

    # Normalize inputs to absolute values for consistent calculation
    flex_abs = abs(criteria.flex)
    min_distance_abs = abs(criteria.min_distance_from_avg)

    # ============================================================
    # FLEX FILTER: Check if price is within flex threshold of reference
    # ============================================================
    # Reference price is:
    # - Peak price (reverse_sort=True): daily MAXIMUM
    # - Best price (reverse_sort=False): daily MINIMUM
    #
    # Standard formula (positive daily minimum):
    # Flex base = max(price_span, abs(ref_price)):
    # - On V-shape days (tiny minimum, large span): span wins → meaningful flex band
    # - On flat days (large minimum, small span): ref_price wins → same as before
    #
    # Examples with flex=15% (positive minimum):
    # - V-shape: min=1 ct, avg=19 ct → span=18 ct → flex_base=18 → threshold=1+2.7=3.7 ct
    # - Flat:    min=30 ct, avg=33 ct → span=3 ct  → flex_base=30 → threshold=30+4.5=34.5 ct
    # - Normal:  min=10 ct, avg=20 ct → span=10 ct → flex_base=10 → threshold=10+1.5=11.5 ct

    # Positive shoulders around a short negative core are handled later in the
    # raw-period pipeline, where adjacency can be evaluated locally. Keeping the
    # interval filter day-agnostic avoids creating a global halo across the whole day.
    price_span = abs(criteria.avg_price - criteria.ref_price)
    flex_base = max(price_span, abs(criteria.ref_price))

    if flex_base == 0:
        # Degenerate case: all prices are zero → only exact zero qualifies
        in_flex = price == 0
    else:
        flex_amount = flex_base * flex_abs

        if criteria.reverse_sort:
            # Peak price: accept prices >= (ref_price - flex_amount)
            # Prices must be CLOSE TO or AT the maximum
            flex_threshold = criteria.ref_price - flex_amount
            in_flex = price >= flex_threshold
        else:
            # Best price: accept prices <= (ref_price + flex_amount)
            # Accept ALL low prices up to the flex threshold, not just those >= minimum
            # This ensures that if there are multiple low-price intervals, all that meet
            # the threshold are included, regardless of whether they're before or after
            # the daily minimum in the chronological sequence.
            flex_threshold = criteria.ref_price + flex_amount
            in_flex = price <= flex_threshold

    # ============================================================
    # MIN_DISTANCE FILTER: Check if price is far enough from average
    # ============================================================
    # CRITICAL: Adjust min_distance dynamically based on flex to prevent conflicts
    # Problem: High flex (e.g., 50%) can conflict with fixed min_distance (e.g., 5%)
    # Solution: When flex is high, reduce min_distance requirement proportionally

    adjusted_min_distance = min_distance_abs

    if flex_abs > FLEX_SCALING_THRESHOLD:
        # Scale down min_distance as flex increases
        # At 20% flex: multiplier = 1.0 (full min_distance)
        # At 40% flex: multiplier = 0.5 (half min_distance)
        # At 50% flex: multiplier = 0.25 (quarter min_distance)
        flex_excess = flex_abs - 0.20  # How much above 20%
        scale_factor = max(0.25, 1.0 - (flex_excess * 2.5))  # Linear reduction, min 25%
        adjusted_min_distance = min_distance_abs * scale_factor

        # Log adjustment at DEBUG level (only when significant reduction)
        if scale_factor < SCALE_FACTOR_WARNING_THRESHOLD:
            import logging  # noqa: PLC0415

            _LOGGER = logging.getLogger(f"{__name__}.details")
            _LOGGER.debug(
                "High flex %.1f%% detected: Reducing min_distance %.1f%% → %.1f%% (scale %.2f)",
                flex_abs * 100,
                min_distance_abs,
                adjusted_min_distance,
                scale_factor,
            )

    # ============================================================
    # ABSOLUTE LOW-PRICE SCALING: Reduce min_distance when avg is very low
    # ============================================================
    # Problem: On days where the entire price level is extremely low (e.g., avg=3 ct),
    # even the daily minimum might not fall 5% below the average in relative terms.
    # Example: avg=3 ct, min_distance=5% → threshold=2.85 ct.
    #          If min=2.9 ct, no interval qualifies despite being genuinely cheap.
    #
    # Solution: Scale min_distance linearly to 0 as avg_price approaches 0.
    # At avg=10 ct → full min_distance; at avg=5 ct → 50%; at avg=0 ct → 0%.
    #
    # This is currency-agnostic: 10 ct EUR and 10 øre NOK are both
    # "very low price territory" for their respective markets.
    if criteria.avg_price < LOW_PRICE_AVG_THRESHOLD and LOW_PRICE_AVG_THRESHOLD > 0:
        low_price_scale = max(0.0, criteria.avg_price / LOW_PRICE_AVG_THRESHOLD)
        adjusted_min_distance = adjusted_min_distance * low_price_scale

    # Calculate threshold from average (using normalized positive distance)
    # - Peak price: threshold = avg * (1 + distance/100) → prices must be ABOVE avg+distance
    # - Best price: threshold = avg * (1 - distance/100) → prices must be BELOW avg-distance
    if criteria.reverse_sort:
        # Peak: price must be >= avg * (1 + distance%)
        min_distance_threshold = criteria.avg_price * (1 + adjusted_min_distance / 100)
        meets_min_distance = price >= min_distance_threshold
    else:
        # Best: price must be <= avg * (1 - distance%)
        min_distance_threshold = criteria.avg_price * (1 - adjusted_min_distance / 100)
        meets_min_distance = price <= min_distance_threshold

    return in_flex, meets_min_distance


def compute_geometric_flex_bonus(
    interval_time: datetime,
    day_pattern: dict[str, Any] | None,
    *,
    extra_flex: float,
    reverse_sort: bool,
) -> float:
    """
    Return extra flex if interval falls within the valley/peak geometric zone.

    For best price (reverse_sort=False): widens flex inside the VALLEY zone
    defined by [valley_start, valley_end] knee points.
    For peak price (reverse_sort=True): widens flex inside the PEAK zone
    defined by [peak_start, peak_end] knee points.

    Args:
        interval_time: Timezone-aware datetime of the interval's start.
        day_pattern: DayPatternDict for the interval's calendar day, or None.
        extra_flex: Additional flex to add (decimal, e.g. 0.10 for 10%).
        reverse_sort: True for peak price, False for best price.

    Returns:
        ``extra_flex`` if the interval is inside the geometric zone, else ``0.0``.

    """
    if not day_pattern or extra_flex <= 0:
        return 0.0

    pattern = day_pattern.get("pattern", "")

    if reverse_sort:
        # Peak price: expand inside PEAK (Λ-shape) zone
        if pattern != "peak":
            return 0.0
        zone_start = day_pattern.get("peak_start")
        zone_end = day_pattern.get("peak_end")
    else:
        # Best price: expand inside VALLEY zone.
        # Also handles DUCK_CURVE (solar duck-curve: expensive morning/evening, cheap midday)
        # where valley_start/valley_end mark the knee points around the midday minimum.
        if pattern not in ("valley", "duck_curve"):
            return 0.0
        zone_start = day_pattern.get("valley_start")
        zone_end = day_pattern.get("valley_end")

    if zone_start is None or zone_end is None:
        return 0.0

    if zone_start <= interval_time <= zone_end:
        return extra_flex
    return 0.0
