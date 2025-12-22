"""Utility functions for price data calculations."""

from __future__ import annotations

import logging
import statistics
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService

from custom_components.tibber_prices.const import (
    DEFAULT_PRICE_LEVEL_GAP_TOLERANCE,
    DEFAULT_PRICE_RATING_GAP_TOLERANCE,
    DEFAULT_PRICE_RATING_HYSTERESIS,
    DEFAULT_VOLATILITY_THRESHOLD_HIGH,
    DEFAULT_VOLATILITY_THRESHOLD_MODERATE,
    DEFAULT_VOLATILITY_THRESHOLD_VERY_HIGH,
    PRICE_LEVEL_MAPPING,
    PRICE_LEVEL_NORMAL,
    PRICE_RATING_NORMAL,
    VOLATILITY_HIGH,
    VOLATILITY_LOW,
    VOLATILITY_MODERATE,
    VOLATILITY_VERY_HIGH,
)
from custom_components.tibber_prices.coordinator.helpers import get_intervals_for_day_offsets

_LOGGER = logging.getLogger(__name__)

MIN_PRICES_FOR_VOLATILITY = 2  # Minimum number of price values needed for volatility calculation

# Volatility factors for adaptive trend thresholds
# These multipliers adjust the base trend thresholds based on price volatility.
# The volatility *ranges* are user-configurable (threshold_moderate, threshold_high),
# but the *reaction strength* (factors) is fixed for predictable behavior.
# This separation allows users to adjust volatility classification without
# unexpectedly changing trend sensitivity.
#
# Factor selection based on lookahead volatility:
# - Below moderate threshold (e.g., <15%): Use 0.6 → 40% more sensitive
# - Moderate to high (e.g., 15-30%): Use 1.0 → as configured by user
# - High and above (e.g., ≥30%): Use 1.4 → 40% less sensitive (filters noise)
VOLATILITY_FACTOR_SENSITIVE = 0.6  # Low volatility → more responsive
VOLATILITY_FACTOR_NORMAL = 1.0  # Moderate volatility → baseline
VOLATILITY_FACTOR_INSENSITIVE = 1.4  # High volatility → noise filtering


def calculate_volatility_level(
    prices: list[float],
    threshold_moderate: float | None = None,
    threshold_high: float | None = None,
    threshold_very_high: float | None = None,
) -> str:
    """
    Calculate volatility level from price list using coefficient of variation.

    Volatility indicates how much prices fluctuate during a period, which helps
    determine whether active load shifting is worthwhile. Uses the coefficient
    of variation (CV = std_dev / mean * 100%) for relative comparison that works
    across different price levels and period lengths.

    Args:
        prices: List of price values (in any unit, typically base currency units like EUR or NOK)
        threshold_moderate: Custom threshold for MODERATE level (default: use DEFAULT_VOLATILITY_THRESHOLD_MODERATE)
        threshold_high: Custom threshold for HIGH level (default: use DEFAULT_VOLATILITY_THRESHOLD_HIGH)
        threshold_very_high: Custom threshold for VERY_HIGH level (default: use DEFAULT_VOLATILITY_THRESHOLD_VERY_HIGH)

    Returns:
        Volatility level: "LOW", "MODERATE", "HIGH", or "VERY_HIGH" (uppercase)

    Examples:
        - CV < 15%: LOW → minimal optimization potential, prices relatively stable
        - 15% ≤ CV < 30%: MODERATE → some optimization worthwhile, noticeable variation
        - 30% ≤ CV < 50%: HIGH → strong optimization recommended, significant swings
        - CV ≥ 50%: VERY_HIGH → maximum optimization potential, extreme volatility

    Note:
        Requires at least 2 price values for calculation. Returns LOW if insufficient data.
        Works identically for short periods (2-3 intervals) and long periods (96 intervals/day).

    """
    # Need at least 2 values for standard deviation
    if len(prices) < MIN_PRICES_FOR_VOLATILITY:
        return VOLATILITY_LOW

    # Use provided thresholds or fall back to constants
    t_moderate = threshold_moderate if threshold_moderate is not None else DEFAULT_VOLATILITY_THRESHOLD_MODERATE
    t_high = threshold_high if threshold_high is not None else DEFAULT_VOLATILITY_THRESHOLD_HIGH
    t_very_high = threshold_very_high if threshold_very_high is not None else DEFAULT_VOLATILITY_THRESHOLD_VERY_HIGH

    # Calculate coefficient of variation
    # CRITICAL: Use absolute value of mean for negative prices (Norway/Germany)
    # Negative electricity prices are valid and should have measurable volatility
    mean = statistics.mean(prices)
    if mean == 0:
        # Division by zero case (all prices exactly zero)
        return VOLATILITY_LOW

    std_dev = statistics.stdev(prices)
    coefficient_of_variation = (std_dev / abs(mean)) * 100  # As percentage, use abs(mean)

    # Classify based on thresholds
    if coefficient_of_variation < t_moderate:
        return VOLATILITY_LOW
    if coefficient_of_variation < t_high:
        return VOLATILITY_MODERATE
    if coefficient_of_variation < t_very_high:
        return VOLATILITY_HIGH
    return VOLATILITY_VERY_HIGH


def calculate_trailing_average_for_interval(
    interval_start: datetime,
    all_prices: list[dict[str, Any]],
) -> float | None:
    """
    Calculate the trailing 24-hour average price for a specific interval.

    Args:
        interval_start: The start time of the interval we're calculating for
        all_prices: List of all available price intervals (yesterday + today + tomorrow)

    Returns:
        The average price of all intervals in the 24 hours before interval_start,
        or None if insufficient data is available.

    """
    if not all_prices:
        return None

    # Calculate the lookback period: 24 hours before this interval
    lookback_start = interval_start - timedelta(hours=24)

    # Collect all prices that fall within the 24-hour lookback window
    matching_prices = []

    for price_data in all_prices:
        price_time = price_data.get("startsAt")  # Already datetime object in local timezone
        if not price_time:
            continue

        # Check if this price falls within our lookback window
        # Include prices that start >= lookback_start and start < interval_start
        if lookback_start <= price_time < interval_start:
            total_price = price_data.get("total")
            if total_price is not None:
                matching_prices.append(float(total_price))

    if not matching_prices:
        return None

    # CRITICAL: Warn if we have less than 24 hours of data (partial average)
    # 24 hours = 96 intervals (4 per hour)
    # Note: This is expected for intervals in the first 24h window

    # Calculate and return the average
    return sum(matching_prices) / len(matching_prices)


def calculate_difference_percentage(
    current_interval_price: float,
    trailing_average: float | None,
) -> float | None:
    """
    Calculate the difference percentage between current price and trailing average.

    This mimics the API's "difference" field from priceRating endpoint.

    CRITICAL: For negative averages, use absolute value to get meaningful percentage.
    Example: current=10 ct, average=-10 ct
    - Wrong: (10-(-10))/-10 = -200% (would rate as "cheap" despite being expensive)
    - Right: (10-(-10))/abs(-10) = +200% (correctly rates as "expensive")

    Args:
        current_interval_price: The current interval's price
        trailing_average: The 24-hour trailing average price

    Returns:
        The percentage difference: ((current - average) / abs(average)) * 100
        or None if trailing_average is None or zero.

    """
    if trailing_average is None or trailing_average == 0:
        return None

    # Use absolute value of average to handle negative prices correctly
    return ((current_interval_price - trailing_average) / abs(trailing_average)) * 100


def calculate_rating_level(  # noqa: PLR0911 - Multiple returns justified by clear hysteresis state machine
    difference: float | None,
    threshold_low: float,
    threshold_high: float,
    *,
    previous_rating: str | None = None,
    hysteresis: float = 0.0,
) -> str | None:
    """
    Calculate the rating level based on difference percentage and thresholds.

    This mimics the API's "level" field from priceRating endpoint.

    Supports hysteresis to prevent flickering at threshold boundaries. When a previous
    rating is provided, the threshold for leaving that state is adjusted by the
    hysteresis value, requiring a more significant change to switch states.

    Args:
        difference: The difference percentage (from calculate_difference_percentage)
        threshold_low: The low threshold percentage (typically -100 to 0)
        threshold_high: The high threshold percentage (typically 0 to 100)
        previous_rating: The rating level of the previous interval (for hysteresis)
        hysteresis: The hysteresis percentage (default 0.0 = no hysteresis)

    Returns:
        "LOW" if difference <= threshold_low (adjusted by hysteresis)
        "HIGH" if difference >= threshold_high (adjusted by hysteresis)
        "NORMAL" otherwise
        None if difference is None

    Example with hysteresis=2.0 and threshold_low=-10:
        - To enter LOW from NORMAL: difference must be <= -10% (threshold_low)
        - To leave LOW back to NORMAL: difference must be > -8% (threshold_low + hysteresis)
        This creates a "dead zone" that prevents rapid switching at boundaries.

    """
    if difference is None:
        return None

    # CRITICAL: Validate threshold configuration
    # threshold_low must be less than threshold_high for meaningful classification
    if threshold_low >= threshold_high:
        _LOGGER.warning(
            "Invalid rating thresholds: threshold_low (%.2f) >= threshold_high (%.2f). "
            "Using NORMAL as fallback. Please check configuration.",
            threshold_low,
            threshold_high,
        )
        return PRICE_RATING_NORMAL

    # Apply hysteresis based on previous state
    # The idea: make it "harder" to leave the current state than to enter it
    if previous_rating == "LOW":
        # Currently LOW: need to exceed threshold_low + hysteresis to leave
        exit_threshold_low = threshold_low + hysteresis
        if difference <= exit_threshold_low:
            return "LOW"
        # Check if we should go to HIGH (rare, but possible with large price swings)
        if difference >= threshold_high:
            return "HIGH"
        return PRICE_RATING_NORMAL

    if previous_rating == "HIGH":
        # Currently HIGH: need to drop below threshold_high - hysteresis to leave
        exit_threshold_high = threshold_high - hysteresis
        if difference >= exit_threshold_high:
            return "HIGH"
        # Check if we should go to LOW (rare, but possible with large price swings)
        if difference <= threshold_low:
            return "LOW"
        return PRICE_RATING_NORMAL

    # No previous state or previous was NORMAL: use standard thresholds
    if difference <= threshold_low:
        return "LOW"

    if difference >= threshold_high:
        return "HIGH"

    return PRICE_RATING_NORMAL


def _process_price_interval(  # noqa: PLR0913 - Extra params needed for hysteresis
    price_interval: dict[str, Any],
    all_prices: list[dict[str, Any]],
    threshold_low: float,
    threshold_high: float,
    *,
    previous_rating: str | None = None,
    hysteresis: float = 0.0,
) -> str | None:
    """
    Process a single price interval and add difference and rating_level.

    Args:
        price_interval: The price interval to process (modified in place)
        all_prices: All available price intervals for lookback calculation
        threshold_low: Low threshold percentage
        threshold_high: High threshold percentage
        previous_rating: The rating level of the previous interval (for hysteresis)
        hysteresis: The hysteresis percentage to prevent flickering

    Returns:
        The calculated rating_level (for use as previous_rating in next call)

    """
    starts_at = price_interval.get("startsAt")  # Already datetime object in local timezone
    if not starts_at:
        return previous_rating
    current_interval_price = price_interval.get("total")

    if current_interval_price is None:
        return previous_rating

    # Calculate trailing average
    trailing_avg = calculate_trailing_average_for_interval(starts_at, all_prices)

    # Calculate and set the difference and rating_level
    if trailing_avg is not None:
        difference = calculate_difference_percentage(float(current_interval_price), trailing_avg)
        price_interval["difference"] = difference

        # Calculate rating_level based on difference with hysteresis
        rating_level = calculate_rating_level(
            difference,
            threshold_low,
            threshold_high,
            previous_rating=previous_rating,
            hysteresis=hysteresis,
        )
        price_interval["rating_level"] = rating_level
        return rating_level

    # Set to None if we couldn't calculate (expected for intervals in first 24h)
    price_interval["difference"] = None
    price_interval["rating_level"] = None
    return None


def _build_rating_blocks(
    rated_intervals: list[tuple[int, dict[str, Any], str]],
) -> list[tuple[int, int, str, int]]:
    """
    Build list of contiguous rating blocks from rated intervals.

    Args:
        rated_intervals: List of (original_idx, interval_dict, rating) tuples

    Returns:
        List of (start_idx, end_idx, rating, length) tuples where indices
        refer to positions in rated_intervals

    """
    blocks: list[tuple[int, int, str, int]] = []
    if not rated_intervals:
        return blocks

    block_start = 0
    current_rating = rated_intervals[0][2]

    for idx in range(1, len(rated_intervals)):
        if rated_intervals[idx][2] != current_rating:
            # End current block
            blocks.append((block_start, idx - 1, current_rating, idx - block_start))
            block_start = idx
            current_rating = rated_intervals[idx][2]

    # Don't forget the last block
    blocks.append((block_start, len(rated_intervals) - 1, current_rating, len(rated_intervals) - block_start))
    return blocks


def _build_level_blocks(
    level_intervals: list[tuple[int, dict[str, Any], str]],
) -> list[tuple[int, int, str, int]]:
    """
    Build list of contiguous price level blocks from intervals.

    Args:
        level_intervals: List of (original_idx, interval_dict, level) tuples

    Returns:
        List of (start_idx, end_idx, level, length) tuples where indices
        refer to positions in level_intervals

    """
    blocks: list[tuple[int, int, str, int]] = []
    if not level_intervals:
        return blocks

    block_start = 0
    current_level = level_intervals[0][2]

    for idx in range(1, len(level_intervals)):
        if level_intervals[idx][2] != current_level:
            # End current block
            blocks.append((block_start, idx - 1, current_level, idx - block_start))
            block_start = idx
            current_level = level_intervals[idx][2]

    # Don't forget the last block
    blocks.append((block_start, len(level_intervals) - 1, current_level, len(level_intervals) - block_start))
    return blocks


def _calculate_gravitational_pull(
    blocks: list[tuple[int, int, str, int]],
    block_idx: int,
    direction: str,
    gap_tolerance: int,
) -> tuple[int, str]:
    """
    Calculate "gravitational pull" from neighboring blocks in one direction.

    This finds the first LARGE block (> gap_tolerance) in the given direction
    and returns its size and rating. Small intervening blocks are "looked through".

    This approach ensures that small isolated blocks are always pulled toward
    the dominant large block, even if there are other small blocks in between.

    Args:
        blocks: List of (start_idx, end_idx, rating, length) tuples
        block_idx: Index of the current block being evaluated
        direction: "left" or "right"
        gap_tolerance: Maximum size of blocks considered "small"

    Returns:
        Tuple of (size, rating) of the first large block found,
        or (immediate_neighbor_size, immediate_neighbor_rating) if no large block exists

    """
    probe_range = range(block_idx - 1, -1, -1) if direction == "left" else range(block_idx + 1, len(blocks))
    total_small_accumulated = 0

    for probe_idx in probe_range:
        probe_rating = blocks[probe_idx][2]
        probe_size = blocks[probe_idx][3]

        if probe_size > gap_tolerance:
            # Found a large block - return its characteristics
            # Add any accumulated small blocks of the same rating
            if total_small_accumulated > 0:
                return (probe_size + total_small_accumulated, probe_rating)
            return (probe_size, probe_rating)

        # Small block - accumulate if same rating as what we've seen
        total_small_accumulated += probe_size

    # No large block found - return the immediate neighbor's info
    neighbor_idx = block_idx - 1 if direction == "left" else block_idx + 1
    return (blocks[neighbor_idx][3], blocks[neighbor_idx][2])


def _apply_rating_gap_tolerance(
    all_intervals: list[dict[str, Any]],
    gap_tolerance: int,
) -> None:
    """
    Apply gap tolerance to smooth out isolated rating level changes.

    This is a post-processing step after hysteresis. It identifies short sequences
    of intervals (≤ gap_tolerance) and merges them into the larger neighboring block.
    The algorithm is bidirectional - it compares block sizes on both sides and
    assigns the small block to whichever neighbor is larger.

    This matches human intuition: a single "different" interval feels like it
    should belong to the larger surrounding group.

    Example with gap_tolerance=1:
        LOW LOW LOW NORMAL LOW LOW → LOW LOW LOW LOW LOW LOW
        (single NORMAL gets merged into larger LOW block)

    Example with gap_tolerance=1 (bidirectional):
        NORMAL NORMAL HIGH NORMAL HIGH HIGH HIGH → NORMAL NORMAL HIGH HIGH HIGH HIGH HIGH
        (single NORMAL at position 4 gets merged into larger HIGH block on the right)

    Args:
        all_intervals: List of price intervals with rating_level already set (modified in-place)
        gap_tolerance: Maximum number of consecutive "different" intervals to smooth out

    Note:
        - Compares block sizes on both sides and merges small blocks into larger neighbors
        - If both neighbors have equal size, prefers the LEFT neighbor (earlier in time)
        - Skips intervals without rating_level (None)
        - Intervals must be sorted chronologically for this to work correctly
        - Multiple passes may be needed as merging can create new small blocks

    """
    if gap_tolerance <= 0:
        return

    # Extract intervals with valid rating_level in chronological order
    rated_intervals: list[tuple[int, dict[str, Any], str]] = [
        (i, interval, interval["rating_level"])
        for i, interval in enumerate(all_intervals)
        if interval.get("rating_level") is not None
    ]

    if len(rated_intervals) < 3:  # noqa: PLR2004 - Minimum 3 for before/gap/after pattern
        return

    # Iteratively merge small blocks until no more changes
    max_iterations = 10
    total_corrections = 0

    for iteration in range(max_iterations):
        blocks = _build_rating_blocks(rated_intervals)
        corrections_this_pass = _merge_small_blocks(blocks, rated_intervals, gap_tolerance)
        total_corrections += corrections_this_pass

        if corrections_this_pass == 0:
            break

        _LOGGER.debug(
            "Gap tolerance pass %d: merged %d small blocks",
            iteration + 1,
            corrections_this_pass,
        )

    if total_corrections > 0:
        _LOGGER.debug("Gap tolerance: total %d block merges across all passes", total_corrections)


def _apply_level_gap_tolerance(
    all_intervals: list[dict[str, Any]],
    gap_tolerance: int,
) -> None:
    """
    Apply gap tolerance to smooth out isolated price level changes.

    Similar to rating gap tolerance, but operates on Tibber's "level" field
    (VERY_CHEAP, CHEAP, NORMAL, EXPENSIVE, VERY_EXPENSIVE). Identifies short
    sequences of intervals (≤ gap_tolerance) and merges them into the larger
    neighboring block.

    Example with gap_tolerance=1:
        CHEAP CHEAP CHEAP NORMAL CHEAP CHEAP → CHEAP CHEAP CHEAP CHEAP CHEAP CHEAP
        (single NORMAL gets merged into larger CHEAP block)

    Example with gap_tolerance=1 (bidirectional):
        NORMAL NORMAL EXPENSIVE NORMAL EXPENSIVE EXPENSIVE EXPENSIVE →
        NORMAL NORMAL EXPENSIVE EXPENSIVE EXPENSIVE EXPENSIVE EXPENSIVE
        (single NORMAL at position 4 gets merged into larger EXPENSIVE block on the right)

    Args:
        all_intervals: List of price intervals with level already set (modified in-place)
        gap_tolerance: Maximum number of consecutive "different" intervals to smooth out

    Note:
        - Uses same bidirectional algorithm as rating gap tolerance
        - Compares block sizes on both sides and merges small blocks into larger neighbors
        - If both neighbors have equal size, prefers the LEFT neighbor (earlier in time)
        - Skips intervals without level (None)
        - Intervals must be sorted chronologically for this to work correctly
        - Multiple passes may be needed as merging can create new small blocks

    """
    if gap_tolerance <= 0:
        return

    # Extract intervals with valid level in chronological order
    level_intervals: list[tuple[int, dict[str, Any], str]] = [
        (i, interval, interval["level"])
        for i, interval in enumerate(all_intervals)
        if interval.get("level") is not None
    ]

    if len(level_intervals) < 3:  # noqa: PLR2004 - Minimum 3 for before/gap/after pattern
        return

    # Iteratively merge small blocks until no more changes
    max_iterations = 10
    total_corrections = 0

    for iteration in range(max_iterations):
        blocks = _build_level_blocks(level_intervals)
        corrections_this_pass = _merge_small_level_blocks(blocks, level_intervals, gap_tolerance)
        total_corrections += corrections_this_pass

        if corrections_this_pass == 0:
            break

        _LOGGER.debug(
            "Level gap tolerance pass %d: merged %d small blocks",
            iteration + 1,
            corrections_this_pass,
        )

    if total_corrections > 0:
        _LOGGER.debug("Level gap tolerance: total %d block merges across all passes", total_corrections)


def _merge_small_blocks(
    blocks: list[tuple[int, int, str, int]],
    rated_intervals: list[tuple[int, dict[str, Any], str]],
    gap_tolerance: int,
) -> int:
    """
    Merge small blocks into their larger neighbors.

    CRITICAL: This function collects ALL merge decisions FIRST, then applies them.
    This prevents the order of processing from affecting outcomes. Without this,
    earlier blocks could be merged incorrectly because the gravitational pull
    calculation would see already-modified neighbors instead of the original state.

    The merge decision is based on the FIRST LARGE BLOCK in each direction,
    looking through any small intervening blocks. This ensures consistent
    behavior when multiple small blocks are adjacent.

    Args:
        blocks: List of (start_idx, end_idx, rating, length) tuples
        rated_intervals: List of (original_idx, interval_dict, rating) tuples (modified in-place)
        gap_tolerance: Maximum size of blocks to merge

    Returns:
        Number of blocks merged in this pass

    """
    # Phase 1: Collect all merge decisions based on ORIGINAL block state
    merge_decisions: list[tuple[int, int, str]] = []  # (start_ri_idx, end_ri_idx, target_rating)

    for block_idx, (start, end, rating, length) in enumerate(blocks):
        if length > gap_tolerance:
            continue

        # Must have neighbors on BOTH sides (not an edge block)
        if block_idx == 0 or block_idx == len(blocks) - 1:
            continue

        # Calculate gravitational pull from each direction
        left_pull, left_rating = _calculate_gravitational_pull(blocks, block_idx, "left", gap_tolerance)
        right_pull, right_rating = _calculate_gravitational_pull(blocks, block_idx, "right", gap_tolerance)

        # Determine target rating (prefer left if equal)
        target_rating = left_rating if left_pull >= right_pull else right_rating

        if rating != target_rating:
            merge_decisions.append((start, end, target_rating))

    # Phase 2: Apply all merge decisions
    for start, end, target_rating in merge_decisions:
        for ri_idx in range(start, end + 1):
            original_idx, interval, _old_rating = rated_intervals[ri_idx]
            interval["rating_level"] = target_rating
            rated_intervals[ri_idx] = (original_idx, interval, target_rating)

    return len(merge_decisions)


def _merge_small_level_blocks(
    blocks: list[tuple[int, int, str, int]],
    level_intervals: list[tuple[int, dict[str, Any], str]],
    gap_tolerance: int,
) -> int:
    """
    Merge small price level blocks into their larger neighbors.

    CRITICAL: This function collects ALL merge decisions FIRST, then applies them.
    This prevents the order of processing from affecting outcomes. Without this,
    earlier blocks could be merged incorrectly because the gravitational pull
    calculation would see already-modified neighbors instead of the original state.

    The merge decision is based on the FIRST LARGE BLOCK in each direction,
    looking through any small intervening blocks. This ensures consistent
    behavior when multiple small blocks are adjacent.

    Args:
        blocks: List of (start_idx, end_idx, level, length) tuples
        level_intervals: List of (original_idx, interval_dict, level) tuples (modified in-place)
        gap_tolerance: Maximum size of blocks to merge

    Returns:
        Number of blocks merged in this pass

    """
    # Phase 1: Collect all merge decisions based on ORIGINAL block state
    merge_decisions: list[tuple[int, int, str]] = []  # (start_li_idx, end_li_idx, target_level)

    for block_idx, (start, end, level, length) in enumerate(blocks):
        if length > gap_tolerance:
            continue

        # Must have neighbors on BOTH sides (not an edge block)
        if block_idx == 0 or block_idx == len(blocks) - 1:
            continue

        # Calculate gravitational pull from each direction
        left_pull, left_level = _calculate_gravitational_pull(blocks, block_idx, "left", gap_tolerance)
        right_pull, right_level = _calculate_gravitational_pull(blocks, block_idx, "right", gap_tolerance)

        # Determine target level (prefer left if equal)
        target_level = left_level if left_pull >= right_pull else right_level

        if level != target_level:
            merge_decisions.append((start, end, target_level))

    # Phase 2: Apply all merge decisions
    for start, end, target_level in merge_decisions:
        for li_idx in range(start, end + 1):
            original_idx, interval, _old_level = level_intervals[li_idx]
            interval["level"] = target_level
            level_intervals[li_idx] = (original_idx, interval, target_level)

    return len(merge_decisions)


def enrich_price_info_with_differences(  # noqa: PLR0913 - Extra params for rating stabilization
    all_intervals: list[dict[str, Any]],
    *,
    threshold_low: float | None = None,
    threshold_high: float | None = None,
    hysteresis: float | None = None,
    gap_tolerance: int | None = None,
    level_gap_tolerance: int | None = None,
    time: TibberPricesTimeService | None = None,  # noqa: ARG001  # Used in production (via coordinator), kept for compatibility
) -> list[dict[str, Any]]:
    """
    Enrich price intervals with calculated 'difference' and 'rating_level' values.

    Computes the trailing 24-hour average, difference percentage, and rating level
    for intervals that have sufficient lookback data (in-place modification).

    Uses hysteresis to prevent flickering at threshold boundaries. When an interval's
    difference is near a threshold, hysteresis ensures that the rating only changes
    when there's a significant movement, not just minor fluctuations.

    After hysteresis, applies gap tolerance as post-processing to smooth out any
    remaining isolated rating changes (e.g., a single NORMAL interval surrounded
    by LOW intervals gets corrected to LOW).

    Similarly, applies level gap tolerance to smooth out isolated price level changes
    from Tibber's API (e.g., a single NORMAL interval surrounded by CHEAP intervals
    gets corrected to CHEAP).

    CRITICAL: Only enriches intervals that have at least 24 hours of prior data
    available. This is determined by checking if (interval_start - earliest_interval_start) >= 24h.
    Works independently of interval density (24 vs 96 intervals/day) and handles
    transition periods (e.g., Oct 1, 2025) correctly.

    CRITICAL: Intervals are processed in chronological order to properly apply
    hysteresis. The rating_level of each interval depends on the previous interval's
    rating to prevent rapid switching at threshold boundaries.

    Args:
        all_intervals: Flat list of all price intervals (day_before_yesterday + yesterday + today + tomorrow).
        threshold_low: Low threshold percentage for rating_level (defaults to -10)
        threshold_high: High threshold percentage for rating_level (defaults to 10)
        hysteresis: Hysteresis percentage to prevent flickering (defaults to 2.0)
        gap_tolerance: Max consecutive intervals to smooth out for rating_level (defaults to 1, 0 = disabled)
        level_gap_tolerance: Max consecutive intervals to smooth out for price level (defaults to 1, 0 = disabled)
        time: TibberPricesTimeService instance (kept for API compatibility, not used)

    Returns:
        Same list (modified in-place) with 'difference' and 'rating_level' added
        to intervals that have full 24h lookback data. Intervals within the first
        24 hours remain unenriched.

    Note:
        Interval density changed on Oct 1, 2025 from 24 to 96 intervals/day.
        This function works correctly across this transition by using time-based
        rather than count-based logic.

    """
    threshold_low = threshold_low if threshold_low is not None else -10
    threshold_high = threshold_high if threshold_high is not None else 10
    hysteresis = hysteresis if hysteresis is not None else DEFAULT_PRICE_RATING_HYSTERESIS
    gap_tolerance = gap_tolerance if gap_tolerance is not None else DEFAULT_PRICE_RATING_GAP_TOLERANCE
    level_gap_tolerance = level_gap_tolerance if level_gap_tolerance is not None else DEFAULT_PRICE_LEVEL_GAP_TOLERANCE

    if not all_intervals:
        return all_intervals

    # Find the earliest interval timestamp (start of available data)
    earliest_start: datetime | None = None
    for interval in all_intervals:
        starts_at = interval.get("startsAt")
        if starts_at and (earliest_start is None or starts_at < earliest_start):
            earliest_start = starts_at

    if earliest_start is None:
        # No valid intervals - return as-is
        return all_intervals

    # Calculate the 24-hour boundary from earliest data
    # Only intervals starting at or after this boundary have full 24h lookback
    enrichment_boundary = earliest_start + timedelta(hours=24)

    # CRITICAL: Sort intervals by time for proper hysteresis application
    # We need to process intervals in chronological order so each interval
    # can use the previous interval's rating_level for hysteresis
    intervals_with_time: list[tuple[dict[str, Any], datetime]] = [
        (interval, starts_at) for interval in all_intervals if (starts_at := interval.get("startsAt")) is not None
    ]
    intervals_with_time.sort(key=lambda x: x[1])

    # Process intervals in chronological order (modifies in-place)
    # CRITICAL: Only enrich intervals that start >= 24h after earliest data
    enriched_count = 0
    skipped_count = 0
    previous_rating: str | None = None

    for price_interval, starts_at in intervals_with_time:
        # Skip if interval doesn't have full 24h lookback
        if starts_at < enrichment_boundary:
            skipped_count += 1
            continue

        # Process interval and get its rating for use as previous_rating in next iteration
        previous_rating = _process_price_interval(
            price_interval,
            all_intervals,
            threshold_low,
            threshold_high,
            previous_rating=previous_rating,
            hysteresis=hysteresis,
        )
        enriched_count += 1

    # Apply gap tolerance as post-processing step
    # This smooths out isolated rating changes that slip through hysteresis
    if gap_tolerance > 0:
        _apply_rating_gap_tolerance(all_intervals, gap_tolerance)

    # Apply level gap tolerance as post-processing step
    # This smooths out isolated price level changes from Tibber's API
    if level_gap_tolerance > 0:
        _apply_level_gap_tolerance(all_intervals, level_gap_tolerance)

    return all_intervals


def find_price_data_for_interval(
    coordinator_data: dict,
    target_time: datetime,
    *,
    time: TibberPricesTimeService,
) -> dict | None:
    """
    Find the price data for a specific 15-minute interval timestamp.

    Args:
        coordinator_data: The coordinator data dict
        target_time: The target timestamp to find price data for
        time: TibberPricesTimeService instance (required)

    Returns:
        Price data dict if found, None otherwise

    """
    # Round to nearest quarter-hour to handle edge cases where we're called
    # slightly before the boundary (e.g., 14:59:59.999 → 15:00:00)
    rounded_time = time.round_to_nearest_quarter(target_time)
    rounded_date = rounded_time.date()

    # Get all intervals (yesterday, today, tomorrow) via helper
    all_intervals = get_intervals_for_day_offsets(coordinator_data, [-1, 0, 1])

    # Search for matching interval
    for price_data in all_intervals:
        starts_at = time.get_interval_time(price_data)
        if starts_at is None:
            continue

        # Exact match after rounding (both time and date must match)
        if starts_at == rounded_time and starts_at.date() == rounded_date:
            return price_data

    return None


def aggregate_price_levels(levels: list[str]) -> str:
    """
    Aggregate multiple price levels into a single representative level using median.

    Takes a list of price level strings (e.g., "VERY_CHEAP", "NORMAL", "EXPENSIVE")
    and returns the median level after sorting by numeric values. This naturally
    tends toward "NORMAL" when levels are mixed, which is the desired conservative
    behavior for period/window aggregations.

    Args:
        levels: List of price level strings from intervals

    Returns:
        The median price level string, or PRICE_LEVEL_NORMAL if input is empty

    Note:
        For even-length lists, uses upper-middle value (len // 2) to bias toward
        NORMAL rather than cheaper levels. This provides conservative recommendations
        when periods contain mixed price levels.

        Example: [-2, -1, 0, 1] → index 2 → value 0 (NORMAL)
        This is intentional: we prefer saying "NORMAL" over "CHEAP" when ambiguous.

    """
    if not levels:
        return PRICE_LEVEL_NORMAL

    # Convert levels to numeric values and sort
    numeric_values = [PRICE_LEVEL_MAPPING.get(level, 0) for level in levels]
    numeric_values.sort()

    # Get median: middle value for odd length, upper-middle for even length
    # Upper-middle (len // 2) intentionally biases toward NORMAL (0) for even counts
    median_idx = len(numeric_values) // 2
    median_value = numeric_values[median_idx]

    # Convert back to level string
    for level, value in PRICE_LEVEL_MAPPING.items():
        if value == median_value:
            return level

    return PRICE_LEVEL_NORMAL


def aggregate_price_rating(differences: list[float], threshold_low: float, threshold_high: float) -> tuple[str, float]:
    """
    Aggregate multiple price differences into a single rating level.

    Calculates the average difference percentage across multiple intervals
    and applies thresholds to determine the overall rating level.

    Args:
        differences: List of difference percentages from intervals
        threshold_low: The low threshold percentage for LOW rating
        threshold_high: The high threshold percentage for HIGH rating

    Returns:
        Tuple of (rating_level, average_difference)
        rating_level: "LOW", "NORMAL", or "HIGH"
        average_difference: The averaged difference percentage

    """
    if not differences:
        return PRICE_RATING_NORMAL, 0.0

    # Filter out None values
    valid_differences = [d for d in differences if d is not None]
    if not valid_differences:
        return PRICE_RATING_NORMAL, 0.0

    # Calculate average difference
    avg_difference = sum(valid_differences) / len(valid_differences)

    # Apply thresholds
    rating_level = calculate_rating_level(avg_difference, threshold_low, threshold_high)

    return rating_level or PRICE_RATING_NORMAL, avg_difference


def aggregate_period_levels(interval_data_list: list[dict[str, Any]]) -> str | None:
    """
    Aggregate price levels across multiple intervals in a period.

    Extracts "level" from each interval and uses the same logic as
    aggregate_price_levels() to determine the overall level for the period.

    Args:
        interval_data_list: List of price interval dictionaries with "level" keys

    Returns:
        The aggregated level string in lowercase (e.g., "very_cheap", "normal", "expensive"),
        or None if no valid levels found

    """
    levels: list[str] = []
    for interval in interval_data_list:
        level = interval.get("level")
        if level is not None and isinstance(level, str):
            levels.append(level)

    if not levels:
        return None

    aggregated = aggregate_price_levels(levels)
    # Convert to lowercase for consistency with other enum sensors
    return aggregated.lower() if aggregated else None


def aggregate_period_ratings(
    interval_data_list: list[dict[str, Any]],
    threshold_low: float,
    threshold_high: float,
) -> tuple[str | None, float | None]:
    """
    Aggregate price ratings across multiple intervals in a period.

    Extracts "difference" from each interval and uses the same logic as
    aggregate_price_rating() to determine the overall rating for the period.

    Args:
        interval_data_list: List of price interval dictionaries with "difference" keys
        threshold_low: The low threshold percentage for LOW rating
        threshold_high: The high threshold percentage for HIGH rating

    Returns:
        Tuple of (rating_level, average_difference)
        rating_level: "low", "normal", "high" (lowercase), or None if no valid data
        average_difference: The averaged difference percentage, or None if no valid data

    """
    differences: list[float] = []
    for interval in interval_data_list:
        diff = interval.get("difference")
        if diff is not None:
            differences.append(float(diff))

    if not differences:
        return None, None

    rating_level, avg_diff = aggregate_price_rating(differences, threshold_low, threshold_high)
    # Convert to lowercase for consistency with other enum sensors
    return rating_level.lower() if rating_level else None, avg_diff


def _calculate_lookahead_volatility_factor(
    all_intervals: list[dict[str, Any]],
    lookahead_intervals: int,
    volatility_threshold_moderate: float,
    volatility_threshold_high: float,
) -> float:
    """
    Calculate volatility factor for adaptive thresholds based on lookahead period.

    Uses the same volatility calculation (coefficient of variation) as volatility sensors,
    ensuring consistent volatility interpretation across the integration.

    Args:
        all_intervals: List of price intervals (today + tomorrow)
        lookahead_intervals: Number of intervals to analyze for volatility
        volatility_threshold_moderate: Threshold for moderate volatility (%, e.g., 15)
        volatility_threshold_high: Threshold for high volatility (%, e.g., 30)

    Returns:
        Multiplier for base threshold:
        - 0.6 for low volatility (< moderate threshold)
        - 1.0 for moderate volatility (moderate to high threshold)
        - 1.4 for high volatility (>= high threshold)

    """
    if len(all_intervals) < lookahead_intervals:
        # Insufficient data - use default factor (no adjustment)
        return 1.0

    # Extract prices from next N intervals
    lookahead_prices = [
        float(interval["total"])
        for interval in all_intervals[:lookahead_intervals]
        if "total" in interval and interval["total"] is not None
    ]

    if not lookahead_prices:
        # No valid prices - use default factor
        return 1.0

    # Use the same volatility calculation as volatility sensors (coefficient of variation)
    # This ensures consistent interpretation of volatility across the integration
    volatility_level = calculate_volatility_level(
        prices=lookahead_prices,
        threshold_moderate=volatility_threshold_moderate,
        threshold_high=volatility_threshold_high,
        # Note: We don't use VERY_HIGH threshold here, only LOW/MODERATE/HIGH matter for factor
    )

    # Map volatility level to adjustment factor
    if volatility_level == VOLATILITY_LOW:
        factor = VOLATILITY_FACTOR_SENSITIVE  # 0.6 → More sensitive trend detection
    elif volatility_level in (VOLATILITY_MODERATE, VOLATILITY_HIGH):
        # Treat MODERATE and HIGH the same for trend detection
        # HIGH volatility means noisy data, so we need less sensitive thresholds
        factor = VOLATILITY_FACTOR_NORMAL if volatility_level == VOLATILITY_MODERATE else VOLATILITY_FACTOR_INSENSITIVE
    else:  # VOLATILITY_VERY_HIGH (should not occur with our thresholds, but handle it)
        factor = VOLATILITY_FACTOR_INSENSITIVE  # 1.4 → Less sensitive (filter noise)

    return factor


def calculate_price_trend(  # noqa: PLR0913 - All parameters are necessary for volatility-adaptive calculation
    current_interval_price: float,
    future_average: float,
    threshold_rising: float = 3.0,
    threshold_falling: float = -3.0,
    *,
    volatility_adjustment: bool = True,
    lookahead_intervals: int | None = None,
    all_intervals: list[dict[str, Any]] | None = None,
    volatility_threshold_moderate: float = DEFAULT_VOLATILITY_THRESHOLD_MODERATE,
    volatility_threshold_high: float = DEFAULT_VOLATILITY_THRESHOLD_HIGH,
) -> tuple[str, float]:
    """
    Calculate price trend by comparing current price with future average.

    Supports volatility-adaptive thresholds: when enabled, the effective threshold
    is adjusted based on price volatility in the lookahead period. This makes the
    trend detection more sensitive during stable periods and less noisy during
    volatile periods.

    Uses the same volatility thresholds as configured for volatility sensors,
    ensuring consistent volatility interpretation across the integration.

    Args:
        current_interval_price: Current interval price
        future_average: Average price of future intervals
        threshold_rising: Base threshold for rising trend (%, positive, default 3%)
        threshold_falling: Base threshold for falling trend (%, negative, default -3%)
        volatility_adjustment: Enable volatility-adaptive thresholds (default True)
        lookahead_intervals: Number of intervals in trend period for volatility calc
        all_intervals: Price intervals (today + tomorrow) for volatility calculation
        volatility_threshold_moderate: User-configured moderate volatility threshold (%)
        volatility_threshold_high: User-configured high volatility threshold (%)

    Returns:
        Tuple of (trend_state, difference_percentage)
        trend_state: "rising" | "falling" | "stable"
        difference_percentage: % change from current to future ((future - current) / current * 100)

    Note:
        Volatility adjustment factor:
        - Low volatility (<15%): factor 0.6 → more sensitive (e.g., 3% → 1.8%)
        - Moderate volatility (15-35%): factor 1.0 → as configured (3%)
        - High volatility (>35%): factor 1.4 → less sensitive (e.g., 3% → 4.2%)

    """
    if current_interval_price == 0:
        # Avoid division by zero - return stable trend
        return "stable", 0.0

    # Apply volatility adjustment if enabled and data available
    effective_rising = threshold_rising
    effective_falling = threshold_falling
    volatility_factor = 1.0

    if volatility_adjustment and lookahead_intervals and all_intervals:
        volatility_factor = _calculate_lookahead_volatility_factor(
            all_intervals, lookahead_intervals, volatility_threshold_moderate, volatility_threshold_high
        )
        effective_rising = threshold_rising * volatility_factor
        effective_falling = threshold_falling * volatility_factor

    # Calculate percentage difference from current to future
    # CRITICAL: Use abs() for negative prices to get correct percentage direction
    # Example: current=-10, future=-5 → diff=5, pct=5/abs(-10)*100=+50% (correctly shows rising)
    if current_interval_price == 0:
        # Edge case: avoid division by zero
        diff_pct = 0.0
    else:
        diff_pct = ((future_average - current_interval_price) / abs(current_interval_price)) * 100

    # Determine trend based on effective thresholds
    if diff_pct >= effective_rising:
        trend = "rising"
    elif diff_pct <= effective_falling:
        trend = "falling"
    else:
        trend = "stable"

    return trend, diff_pct
