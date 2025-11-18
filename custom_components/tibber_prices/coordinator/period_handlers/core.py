"""Core period calculation API - main entry points."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .types import PeriodConfig

from .outlier_filtering import (
    filter_price_outliers,
)
from .period_building import (
    add_interval_ends,
    build_periods,
    calculate_reference_prices,
    filter_periods_by_end_date,
    filter_periods_by_min_length,
    split_intervals_by_day,
)
from .period_merging import (
    merge_adjacent_periods_at_midnight,
)
from .period_statistics import (
    extract_period_summaries,
)
from .types import ThresholdConfig


def calculate_periods(
    all_prices: list[dict],
    *,
    config: PeriodConfig,
) -> dict[str, Any]:
    """
    Calculate price periods (best or peak) from price data.

    This function identifies periods but does NOT store full interval data redundantly.
    It returns lightweight period summaries that reference the original price data.

    Steps:
    1. Split prices by day and calculate daily averages
    2. Calculate reference prices (min/max per day)
    3. Build periods based on criteria
    4. Filter by minimum length
    5. Merge adjacent periods at midnight
    6. Extract period summaries (start/end times, not full price data)

    Args:
        all_prices: All price data points from yesterday/today/tomorrow
        config: Period configuration containing reverse_sort, flex, min_distance_from_avg,
                min_period_length, threshold_low, and threshold_high

    Returns:
        Dict with:
        - periods: List of lightweight period summaries (start/end times only)
        - metadata: Config and statistics
        - reference_data: Daily min/max/avg for on-demand annotation

    """
    # Extract config values
    reverse_sort = config.reverse_sort
    flex = config.flex
    min_distance_from_avg = config.min_distance_from_avg
    min_period_length = config.min_period_length
    threshold_low = config.threshold_low
    threshold_high = config.threshold_high

    if not all_prices:
        return {
            "periods": [],
            "metadata": {
                "total_periods": 0,
                "config": {
                    "reverse_sort": reverse_sort,
                    "flex": flex,
                    "min_distance_from_avg": min_distance_from_avg,
                    "min_period_length": min_period_length,
                },
            },
            "reference_data": {
                "ref_prices": {},
                "avg_prices": {},
            },
        }

    # Ensure prices are sorted chronologically
    all_prices_sorted = sorted(all_prices, key=lambda p: p["startsAt"])

    # Step 1: Split by day and calculate averages
    intervals_by_day, avg_price_by_day = split_intervals_by_day(all_prices_sorted)

    # Step 2: Calculate reference prices (min or max per day)
    ref_prices = calculate_reference_prices(intervals_by_day, reverse_sort=reverse_sort)

    # Step 2.5: Filter price outliers (smoothing for period formation only)
    # This runs BEFORE period formation to prevent isolated price spikes
    # from breaking up otherwise continuous periods
    all_prices_smoothed = filter_price_outliers(
        all_prices_sorted,
        abs(flex) * 100,  # Convert to percentage (e.g., 0.15 → 15.0)
        min_period_length,
    )

    # Step 3: Build periods
    price_context = {
        "ref_prices": ref_prices,
        "avg_prices": avg_price_by_day,
        "flex": flex,
        "min_distance_from_avg": min_distance_from_avg,
    }
    raw_periods = build_periods(
        all_prices_smoothed,  # Use smoothed prices for period formation
        price_context,
        reverse_sort=reverse_sort,
        level_filter=config.level_filter,
        gap_count=config.gap_count,
    )

    # Step 4: Filter by minimum length
    raw_periods = filter_periods_by_min_length(raw_periods, min_period_length)

    # Step 5: Merge adjacent periods at midnight
    raw_periods = merge_adjacent_periods_at_midnight(raw_periods)

    # Step 6: Add interval ends
    add_interval_ends(raw_periods)

    # Step 7: Filter periods by end date (keep periods ending today or later)
    raw_periods = filter_periods_by_end_date(raw_periods)

    # Step 8: Extract lightweight period summaries (no full price data)
    # Note: Filtering for current/future is done here based on end date,
    # not start date. This preserves periods that started yesterday but end today.
    thresholds = ThresholdConfig(
        threshold_low=threshold_low,
        threshold_high=threshold_high,
        threshold_volatility_moderate=config.threshold_volatility_moderate,
        threshold_volatility_high=config.threshold_volatility_high,
        threshold_volatility_very_high=config.threshold_volatility_very_high,
        reverse_sort=reverse_sort,
    )
    period_summaries = extract_period_summaries(
        raw_periods,
        all_prices_sorted,
        price_context,
        thresholds,
    )

    return {
        "periods": period_summaries,  # Lightweight summaries only
        "metadata": {
            "total_periods": len(period_summaries),
            "config": {
                "reverse_sort": reverse_sort,
                "flex": flex,
                "min_distance_from_avg": min_distance_from_avg,
                "min_period_length": min_period_length,
            },
        },
        "reference_data": {
            "ref_prices": {k.isoformat(): v for k, v in ref_prices.items()},
            "avg_prices": {k.isoformat(): v for k, v in avg_price_by_day.items()},
        },
    }
