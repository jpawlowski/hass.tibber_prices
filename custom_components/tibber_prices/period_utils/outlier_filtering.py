"""
Price outlier filtering for period calculation.

This module handles the detection and smoothing of single-interval price spikes
that would otherwise break up continuous periods. Outliers are only smoothed for
period formation - original prices are preserved for all statistics.

Uses statistical methods:
- Linear regression for trend-based spike detection
- Standard deviation for confidence thresholds
- Symmetry checking to avoid smoothing legitimate price shifts
- Zigzag detection with relative volatility for cluster rejection
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

_LOGGER = logging.getLogger(__name__)

# Outlier filtering constants
MIN_CONTEXT_SIZE = 3  # Minimum intervals needed before/after for analysis
CONFIDENCE_LEVEL = 2.0  # Standard deviations for 95% confidence interval
VOLATILITY_THRESHOLD = 0.05  # 5% max relative std dev for zigzag detection
SYMMETRY_THRESHOLD = 1.5  # Max std dev difference for symmetric spike
RELATIVE_VOLATILITY_THRESHOLD = 2.0  # Window volatility vs context (cluster detection)
ASYMMETRY_TAIL_WINDOW = 6  # Skip asymmetry check for last ~1.5h (6 intervals) of available data
ZIGZAG_TAIL_WINDOW = 6  # Skip zigzag/cluster detection for last ~1.5h (6 intervals)

# Module-local log indentation (each module starts at level 0)
INDENT_L0 = ""  # All logs in this module (no indentation needed)


@dataclass(slots=True)
class SpikeCandidateContext:
    """Container for spike validation parameters."""

    current: dict
    context_before: list[dict]
    context_after: list[dict]
    flexibility_ratio: float
    remaining_intervals: int
    stats: dict[str, float]
    analysis_window: list[dict]


def _should_skip_tail_check(
    remaining_intervals: int,
    tail_window: int,
    check_name: str,
    interval_label: str,
) -> bool:
    """Return True when remaining intervals fall inside tail window and log why."""
    if remaining_intervals < tail_window:
        _LOGGER.debug(
            "%sSpike at %s: Skipping %s check (only %d intervals remaining)",
            INDENT_L0,
            interval_label,
            check_name,
            remaining_intervals,
        )
        return True
    return False


def _calculate_statistics(prices: list[float]) -> dict[str, float]:
    """
    Calculate statistical measures for price context.

    Uses linear regression to detect trends, enabling accurate spike detection
    even when prices are gradually rising or falling.

    Args:
        prices: List of price values

    Returns:
        Dictionary with:
        - mean: Average price
        - std_dev: Standard deviation
        - trend_slope: Linear regression slope (price change per interval)

    """
    n = len(prices)
    mean = sum(prices) / n

    # Standard deviation
    variance = sum((p - mean) ** 2 for p in prices) / n
    std_dev = variance**0.5

    # Linear trend (least squares regression)
    # y = mx + b, we calculate m (slope)
    x_values = list(range(n))  # 0, 1, 2, ...
    x_mean = sum(x_values) / n

    numerator = sum((x - x_mean) * (y - mean) for x, y in zip(x_values, prices, strict=True))
    denominator = sum((x - x_mean) ** 2 for x in x_values)

    trend_slope = numerator / denominator if denominator != 0 else 0.0

    return {
        "mean": mean,
        "std_dev": std_dev,
        "trend_slope": trend_slope,
    }


def _check_symmetry(avg_before: float, avg_after: float, std_dev: float) -> bool:
    """
    Check if spike is symmetric (returns to baseline).

    A symmetric spike has similar average prices before and after the spike.
    Asymmetric spikes might indicate legitimate price level changes and should
    not be smoothed.

    Args:
        avg_before: Average price before spike
        avg_after: Average price after spike
        std_dev: Standard deviation of context prices

    Returns:
        True if symmetric (should smooth), False if asymmetric (should keep)

    """
    difference = abs(avg_after - avg_before)
    threshold = SYMMETRY_THRESHOLD * std_dev

    return difference <= threshold


def _detect_zigzag_pattern(window: list[dict], context_std_dev: float) -> bool:
    """
    Detect zigzag pattern or clustered spikes using multiple criteria.

    Enhanced detection with three checks:
    1. Absolute volatility: Is standard deviation too high?
    2. Direction changes: Too many up-down-up transitions?
    3. Relative volatility: Is window more volatile than context? (catches clusters!)

    The third check implicitly handles spike clusters without explicit multi-pass
    detection.

    Args:
        window: List of price intervals to analyze
        context_std_dev: Standard deviation of surrounding context

    Returns:
        True if zigzag/cluster detected (reject smoothing)

    """
    prices = [x["total"] for x in window]

    if len(prices) < MIN_CONTEXT_SIZE:
        return False

    avg_price = sum(prices) / len(prices)

    # Check 1: Absolute volatility
    variance = sum((p - avg_price) ** 2 for p in prices) / len(prices)
    std_dev = variance**0.5

    if std_dev / avg_price > VOLATILITY_THRESHOLD:
        return True  # Too volatile overall

    # Check 2: Direction changes
    direction_changes = 0
    for i in range(1, len(prices) - 1):
        prev_trend = prices[i] - prices[i - 1]
        next_trend = prices[i + 1] - prices[i]

        # Direction change when signs differ
        if prev_trend * next_trend < 0:
            direction_changes += 1

    max_allowed_changes = len(prices) / 3
    if direction_changes > max_allowed_changes:
        return True  # Too many direction changes

    # Check 3: Relative volatility (NEW - catches spike clusters!)
    # If this window is much more volatile than the surrounding context,
    # it's likely a cluster of spikes rather than one isolated spike
    return std_dev > RELATIVE_VOLATILITY_THRESHOLD * context_std_dev


def _validate_spike_candidate(
    candidate: SpikeCandidateContext,
) -> bool:
    """Run stability, symmetry, and zigzag checks before smoothing."""
    avg_before = sum(x["total"] for x in candidate.context_before) / len(candidate.context_before)
    avg_after = sum(x["total"] for x in candidate.context_after) / len(candidate.context_after)

    context_diff_pct = abs(avg_after - avg_before) / avg_before if avg_before > 0 else 0
    if context_diff_pct > candidate.flexibility_ratio:
        _LOGGER.debug(
            "%sInterval %s: Context unstable (%.1f%% change) - not a spike",
            INDENT_L0,
            candidate.current.get("startsAt", "unknown interval"),
            context_diff_pct * 100,
        )
        return False

    if not _should_skip_tail_check(
        candidate.remaining_intervals,
        ASYMMETRY_TAIL_WINDOW,
        "asymmetry",
        candidate.current.get("startsAt", "unknown interval"),
    ) and not _check_symmetry(avg_before, avg_after, candidate.stats["std_dev"]):
        _LOGGER.debug(
            "%sSpike at %s rejected: Asymmetric (before=%.2f, after=%.2f ct/kWh)",
            INDENT_L0,
            candidate.current.get("startsAt", "unknown interval"),
            avg_before * 100,
            avg_after * 100,
        )
        return False

    if _should_skip_tail_check(
        candidate.remaining_intervals,
        ZIGZAG_TAIL_WINDOW,
        "zigzag/cluster",
        candidate.current.get("startsAt", "unknown interval"),
    ):
        return True

    if _detect_zigzag_pattern(candidate.analysis_window, candidate.stats["std_dev"]):
        _LOGGER.debug(
            "%sSpike at %s rejected: Zigzag/cluster pattern detected",
            INDENT_L0,
            candidate.current.get("startsAt", "unknown interval"),
        )
        return False

    return True


def filter_price_outliers(
    intervals: list[dict],
    flexibility_pct: float,
    _min_duration: int,  # Unused, kept for API compatibility
) -> list[dict]:
    """
    Filter single-interval price spikes within stable sequences.

    Uses statistical methods to detect and smooth isolated spikes:
    - Linear regression to predict expected prices (handles trends)
    - Standard deviation for confidence intervals (adapts to volatility)
    - Symmetry checking (avoids smoothing legitimate price shifts)
    - Zigzag detection (rejects volatile areas and spike clusters)

    This runs BEFORE period formation to smooth out brief anomalies that would
    otherwise break continuous periods. Original prices are preserved for all
    statistics.

    Args:
        intervals: Price intervals to filter (typically 96 for yesterday/today/tomorrow)
        flexibility_pct: User's flexibility setting (derives tolerance)
        _min_duration: Minimum period duration (unused, kept for API compatibility)

    Returns:
        Intervals with smoothed prices (marked with _smoothed flag)

    """
    _LOGGER.info(
        "%sSmoothing price outliers: %d intervals, flex=%.1f%%",
        INDENT_L0,
        len(intervals),
        flexibility_pct,
    )

    # Convert percentage to ratio once for all comparisons (e.g., 15.0 → 0.15)
    flexibility_ratio = flexibility_pct / 100

    result = []
    smoothed_count = 0

    for i, current in enumerate(intervals):
        current_price = current["total"]

        # Get context windows (3 intervals before and after)
        context_before = intervals[max(0, i - MIN_CONTEXT_SIZE) : i]
        context_after = intervals[i + 1 : min(len(intervals), i + 1 + MIN_CONTEXT_SIZE)]

        # Need sufficient context on both sides
        if len(context_before) < MIN_CONTEXT_SIZE or len(context_after) < MIN_CONTEXT_SIZE:
            result.append(current)
            continue

        # Calculate statistics for combined context (excluding current interval)
        context_prices = [x["total"] for x in context_before + context_after]
        stats = _calculate_statistics(context_prices)

        # Predict expected price at current position using linear trend
        # Position offset: current is at index len(context_before) in the combined window
        offset_position = len(context_before)
        expected_price = stats["mean"] + (stats["trend_slope"] * offset_position)

        # Calculate how far current price deviates from expected
        residual = abs(current_price - expected_price)

        # Tolerance based on statistical confidence (2 std dev = 95% confidence)
        tolerance = stats["std_dev"] * CONFIDENCE_LEVEL

        # Not a spike if within tolerance
        if residual <= tolerance:
            result.append(current)
            continue

        # SPIKE CANDIDATE DETECTED - Now validate
        remaining_intervals = len(intervals) - (i + 1)
        analysis_window = [*context_before[-2:], current, *context_after[:2]]
        candidate_context = SpikeCandidateContext(
            current=current,
            context_before=context_before,
            context_after=context_after,
            flexibility_ratio=flexibility_ratio,
            remaining_intervals=remaining_intervals,
            stats=stats,
            analysis_window=analysis_window,
        )

        if not _validate_spike_candidate(candidate_context):
            result.append(current)
            continue

        # ALL CHECKS PASSED - Smooth the spike
        smoothed = current.copy()
        smoothed["total"] = expected_price  # Use trend-based prediction
        smoothed["_smoothed"] = True
        smoothed["_original_price"] = current_price

        result.append(smoothed)
        smoothed_count += 1

        _LOGGER.debug(
            "%sSmoothed spike at %s: %.2f → %.2f ct/kWh (residual: %.2f, tolerance: %.2f, trend_slope: %.4f)",
            INDENT_L0,
            current.get("startsAt", f"index {i}"),
            current_price * 100,
            expected_price * 100,
            residual * 100,
            tolerance * 100,
            stats["trend_slope"] * 100,
        )

    if smoothed_count > 0:
        _LOGGER.info(
            "%sPrice outlier smoothing complete: %d/%d intervals smoothed (%.1f%%)",
            INDENT_L0,
            smoothed_count,
            len(intervals),
            (smoothed_count / len(intervals)) * 100,
        )

    return result
