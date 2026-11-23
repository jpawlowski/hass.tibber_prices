"""
Interval-level filtering logic for period calculation.

Key Concepts:
- Flex Filter: Limits price distance from daily min/max
- Min Distance Filter: Ensures prices are significantly different from average
- Conflict Scaling: Min_Distance is cut where high Flex passes it (flat days)

See docs/development/period-calculation-theory.md for detailed explanation.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

    from .types import TibberPricesIntervalCriteria

from custom_components.tibber_prices.const import PRICE_LEVEL_MAPPING

# Module-local log indentation (each module starts at level 0)
INDENT_L0 = ""  # Entry point / main function

# Flex threshold for min_distance scaling
FLEX_SCALING_THRESHOLD = 0.20  # 20% - above this, min_distance may be cut where flex passes it
MIN_DISTANCE_SCALE_FLOOR = 0.25  # conflict scaling never cuts min_distance below 25% of the setting

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


def calculate_flex_threshold(criteria: TibberPricesIntervalCriteria) -> float:
    """
    Return the flex threshold: the highest best price / lowest peak price that is in flex.

    Flex is a share of the band between the reference (daily min for best price, daily
    max for peak price) and the daily mean (span = |avg - ref|), so the threshold never
    crosses the mean (#259). Examples with flex=15%:
    - Best, normal:  min=10 ct, avg=20 ct → span=10 ct → threshold=10+1.5=11.5 ct
    - Best, flat:    min=30 ct, avg=33 ct → span=3 ct  → threshold=30+0.45=30.45 ct
    - Peak:          max=46 ct, avg=38 ct → span=8 ct  → threshold=46-1.2=44.8 ct

    The geometric bonus keeps its former base max(span, |ref|), so configured values
    widen the band as much as before.
    """
    price_span = abs(criteria.avg_price - criteria.ref_price)
    flex_amount = price_span * abs(criteria.flex) + max(price_span, abs(criteria.ref_price)) * criteria.geometric_flex
    return criteria.ref_price - flex_amount if criteria.reverse_sort else criteria.ref_price + flex_amount


def calculate_effective_min_distance(criteria: TibberPricesIntervalCriteria, flex_threshold: float) -> float:
    """
    Return min_distance (in %, positive) after low-price and conflict scaling.

    Low-price scaling: on days where the entire price level is extremely low (e.g., avg=3 ct),
    even the daily minimum might not fall 5% below the average in relative terms. min_distance
    scales linearly to 0 as avg_price approaches 0 (avg=10 ct → full, 5 ct → 50%, 0 ct → 0%).
    Currency-agnostic: 10 ct EUR and 10 øre NOK are both "very low price territory".

    Conflict scaling: at high flex, the flex threshold can pass the min_distance threshold, so
    min_distance alone would set the period edges. Since flex is a share of |avg - ref| (#259),
    that only happens when the span is small against the min_distance band (flat days). Then
    min_distance is cut just far enough for both thresholds to meet, never below
    MIN_DISTANCE_SCALE_FLOOR of the setting (and never raised). At or below
    FLEX_SCALING_THRESHOLD (flex plus geometric bonus), min_distance stays whole, so it keeps
    suppressing phantom periods on flat days at the configured flex.
    """
    min_distance_setting = abs(criteria.min_distance_from_avg)
    min_distance = min_distance_setting

    if criteria.avg_price < LOW_PRICE_AVG_THRESHOLD and LOW_PRICE_AVG_THRESHOLD > 0:
        min_distance *= max(0.0, criteria.avg_price / LOW_PRICE_AVG_THRESHOLD)

    if abs(criteria.flex) + criteria.geometric_flex > FLEX_SCALING_THRESHOLD and criteria.avg_price > 0:
        flex_threshold_ratio = flex_threshold / criteria.avg_price
        meeting_distance = (flex_threshold_ratio - 1 if criteria.reverse_sort else 1 - flex_threshold_ratio) * 100
        if meeting_distance < min_distance:
            floor = min(min_distance, min_distance_setting * MIN_DISTANCE_SCALE_FLOOR)
            min_distance = max(meeting_distance, floor)

    return min_distance


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
    # FAST PATH: Negative/zero prices always qualify as best price.
    # When price ≤ 0 the consumer is paid or gets free electricity: unconditionally the
    # cheapest possible outcome regardless of daily average, flex setting, or level filter.
    # Bypasses both flex AND min_distance. Positive shoulders around a short negative core
    # are handled later in the raw-period pipeline, where adjacency can be evaluated locally;
    # keeping this filter day-agnostic avoids a global halo across the whole day.
    if not criteria.reverse_sort and price <= 0:
        return True, True

    # FLEX FILTER: Peak accepts prices at or above the threshold (close to the maximum),
    # best accepts ALL prices at or below it, before or after the daily minimum
    flex_threshold = calculate_flex_threshold(criteria)
    in_flex = price >= flex_threshold if criteria.reverse_sort else price <= flex_threshold

    # MIN_DISTANCE FILTER: Peak must be min_distance% above the average, best below it
    min_distance = calculate_effective_min_distance(criteria, flex_threshold)
    if criteria.reverse_sort:
        meets_min_distance = price >= criteria.avg_price * (1 + min_distance / 100)
    else:
        meets_min_distance = price <= criteria.avg_price * (1 - min_distance / 100)

    return in_flex, meets_min_distance


def compute_geometric_flex_bonus(
    interval_time: datetime,
    day_pattern: dict[str, Any] | None,
    *,
    extra_flex: float,
    reverse_sort: bool,
) -> float:
    """
    Return the geometric flex bonus if interval falls within the valley/peak geometric zone.

    The bonus is not added to flex: it goes into ``TibberPricesIntervalCriteria.geometric_flex``,
    a share of max(|avg - ref|, |ref|), while flex is a share of |avg - ref|.

    For best price (reverse_sort=False): widens flex inside the VALLEY zone
    defined by [valley_start, valley_end] knee points.
    For peak price (reverse_sort=True): widens flex inside the PEAK zone
    defined by [peak_start, peak_end] knee points.

    Args:
        interval_time: Timezone-aware datetime of the interval's start.
        day_pattern: DayPatternDict for the interval's calendar day, or None.
        extra_flex: Geometric flex bonus (decimal, e.g. 0.10 for 10%).
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
