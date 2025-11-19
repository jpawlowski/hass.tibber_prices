"""Period statistics calculation and summary building."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

    from custom_components.tibber_prices.coordinator.time_service import TimeService

    from .types import (
        PeriodData,
        PeriodStatistics,
        ThresholdConfig,
    )
from custom_components.tibber_prices.utils.price import (
    aggregate_period_levels,
    aggregate_period_ratings,
    calculate_volatility_level,
)


def calculate_period_price_diff(
    price_avg: float,
    start_time: datetime,
    price_context: dict[str, Any],
) -> tuple[float | None, float | None]:
    """
    Calculate period price difference from daily reference (min or max).

    Uses reference price from start day of the period for consistency.

    Returns:
        Tuple of (period_price_diff, period_price_diff_pct) or (None, None) if no reference available.

    """
    if not price_context or not start_time:
        return None, None

    ref_prices = price_context.get("ref_prices", {})
    date_key = start_time.date()
    ref_price = ref_prices.get(date_key)

    if ref_price is None:
        return None, None

    # Convert reference price to minor units (ct/øre)
    ref_price_minor = round(ref_price * 100, 2)
    period_price_diff = round(price_avg - ref_price_minor, 2)
    period_price_diff_pct = None
    if ref_price_minor != 0:
        period_price_diff_pct = round((period_price_diff / ref_price_minor) * 100, 2)

    return period_price_diff, period_price_diff_pct


def calculate_aggregated_rating_difference(period_price_data: list[dict]) -> float | None:
    """
    Calculate aggregated rating difference percentage for the period.

    Takes the average of all interval differences (from their respective thresholds).

    Args:
        period_price_data: List of price data dictionaries with "difference" field

    Returns:
        Average difference percentage, or None if no valid data

    """
    differences = []
    for price_data in period_price_data:
        diff = price_data.get("difference")
        if diff is not None:
            differences.append(float(diff))

    if not differences:
        return None

    return round(sum(differences) / len(differences), 2)


def calculate_period_price_statistics(period_price_data: list[dict]) -> dict[str, float]:
    """
    Calculate price statistics for a period.

    Args:
        period_price_data: List of price data dictionaries with "total" field

    Returns:
        Dictionary with price_avg, price_min, price_max, price_spread (all in minor units: ct/øre)

    """
    prices_minor = [round(float(p["total"]) * 100, 2) for p in period_price_data]

    if not prices_minor:
        return {
            "price_avg": 0.0,
            "price_min": 0.0,
            "price_max": 0.0,
            "price_spread": 0.0,
        }

    price_avg = round(sum(prices_minor) / len(prices_minor), 2)
    price_min = round(min(prices_minor), 2)
    price_max = round(max(prices_minor), 2)
    price_spread = round(price_max - price_min, 2)

    return {
        "price_avg": price_avg,
        "price_min": price_min,
        "price_max": price_max,
        "price_spread": price_spread,
    }


def build_period_summary_dict(
    period_data: PeriodData,
    stats: PeriodStatistics,
    *,
    reverse_sort: bool,
) -> dict:
    """
    Build the complete period summary dictionary.

    Args:
        period_data: Period timing and position data
        stats: Calculated period statistics
        reverse_sort: True for peak price, False for best price (keyword-only)

    Returns:
        Complete period summary dictionary following attribute ordering

    """
    # Build complete period summary (following attribute ordering from AGENTS.md)
    summary = {
        # 1. Time information (when does this apply?)
        "start": period_data.start_time,
        "end": period_data.end_time,
        "duration_minutes": period_data.period_length * 15,  # period_length is in intervals
        # 2. Core decision attributes (what should I do?)
        "level": stats.aggregated_level,
        "rating_level": stats.aggregated_rating,
        "rating_difference_%": stats.rating_difference_pct,
        # 3. Price statistics (how much does it cost?)
        "price_avg": stats.price_avg,
        "price_min": stats.price_min,
        "price_max": stats.price_max,
        "price_spread": stats.price_spread,
        "volatility": stats.volatility,
        # 4. Price differences will be added below if available
        # 5. Detail information (additional context)
        "period_interval_count": period_data.period_length,
        "period_position": period_data.period_idx,
        "periods_total": period_data.total_periods,
        "periods_remaining": period_data.total_periods - period_data.period_idx,
    }

    # Add period price difference attributes based on sensor type (step 4)
    if stats.period_price_diff is not None:
        if reverse_sort:
            # Peak price sensor: compare to daily maximum
            summary["period_price_diff_from_daily_max"] = stats.period_price_diff
            if stats.period_price_diff_pct is not None:
                summary["period_price_diff_from_daily_max_%"] = stats.period_price_diff_pct
        else:
            # Best price sensor: compare to daily minimum
            summary["period_price_diff_from_daily_min"] = stats.period_price_diff
            if stats.period_price_diff_pct is not None:
                summary["period_price_diff_from_daily_min_%"] = stats.period_price_diff_pct

    return summary


def extract_period_summaries(
    periods: list[list[dict]],
    all_prices: list[dict],
    price_context: dict[str, Any],
    thresholds: ThresholdConfig,
    *,
    time: TimeService,
) -> list[dict]:
    """
    Extract complete period summaries with all aggregated attributes.

    Returns sensor-ready period summaries with:
    - Timestamps and positioning (start, end, hour, minute, time)
    - Aggregated price statistics (price_avg, price_min, price_max, price_spread)
    - Volatility categorization (low/moderate/high/very_high based on coefficient of variation)
    - Rating difference percentage (aggregated from intervals)
    - Period price differences (period_price_diff_from_daily_min/max)
    - Aggregated level and rating_level
    - Interval count (number of 15-min intervals in period)

    All data is pre-calculated and ready for display - no further processing needed.

    Args:
        periods: List of periods, where each period is a list of interval dictionaries
        all_prices: All price data from the API (enriched with level, difference, rating_level)
        price_context: Dictionary with ref_prices and avg_prices per day
        thresholds: Threshold configuration for calculations
        time: TimeService instance (required)

    """
    from .types import (  # noqa: PLC0415 - Avoid circular import
        PeriodData,
        PeriodStatistics,
    )

    # Build lookup dictionary for full price data by timestamp
    price_lookup: dict[str, dict] = {}
    for price_data in all_prices:
        starts_at = time.get_interval_time(price_data)
        if starts_at:
            price_lookup[starts_at.isoformat()] = price_data

    summaries = []
    total_periods = len(periods)

    for period_idx, period in enumerate(periods, 1):
        if not period:
            continue

        first_interval = period[0]
        last_interval = period[-1]

        start_time = first_interval.get("interval_start")
        end_time = last_interval.get("interval_end")

        if not start_time or not end_time:
            continue

        # Look up full price data for each interval in the period
        period_price_data: list[dict] = []
        for interval in period:
            start = interval.get("interval_start")
            if not start:
                continue
            start_iso = start.isoformat()
            price_data = price_lookup.get(start_iso)
            if price_data:
                period_price_data.append(price_data)

        # Calculate aggregated level and rating_level
        aggregated_level = None
        aggregated_rating = None

        if period_price_data:
            # Aggregate level (from API's "level" field)
            aggregated_level = aggregate_period_levels(period_price_data)

            # Aggregate rating_level (from calculated "rating_level" and "difference" fields)
            if thresholds.threshold_low is not None and thresholds.threshold_high is not None:
                aggregated_rating, _ = aggregate_period_ratings(
                    period_price_data,
                    thresholds.threshold_low,
                    thresholds.threshold_high,
                )

        # Calculate price statistics (in minor units: ct/øre)
        price_stats = calculate_period_price_statistics(period_price_data)

        # Calculate period price difference from daily reference
        period_price_diff, period_price_diff_pct = calculate_period_price_diff(
            price_stats["price_avg"], start_time, price_context
        )

        # Extract prices for volatility calculation (coefficient of variation)
        prices_for_volatility = [float(p["total"]) for p in period_price_data if "total" in p]

        # Calculate volatility (categorical) and aggregated rating difference (numeric)
        volatility = calculate_volatility_level(
            prices_for_volatility,
            threshold_moderate=thresholds.threshold_volatility_moderate,
            threshold_high=thresholds.threshold_volatility_high,
            threshold_very_high=thresholds.threshold_volatility_very_high,
        ).lower()
        rating_difference_pct = calculate_aggregated_rating_difference(period_price_data)

        # Count how many intervals in this period benefited from smoothing (i.e., would have been excluded)
        smoothed_impactful_count = sum(1 for interval in period if interval.get("smoothing_was_impactful", False))

        # Count how many intervals were kept due to level filter gap tolerance
        level_gap_count = sum(1 for interval in period if interval.get("is_level_gap", False))

        # Build period data and statistics objects
        period_data = PeriodData(
            start_time=start_time,
            end_time=end_time,
            period_length=len(period),
            period_idx=period_idx,
            total_periods=total_periods,
        )

        stats = PeriodStatistics(
            aggregated_level=aggregated_level,
            aggregated_rating=aggregated_rating,
            rating_difference_pct=rating_difference_pct,
            price_avg=price_stats["price_avg"],
            price_min=price_stats["price_min"],
            price_max=price_stats["price_max"],
            price_spread=price_stats["price_spread"],
            volatility=volatility,
            period_price_diff=period_price_diff,
            period_price_diff_pct=period_price_diff_pct,
        )

        # Build complete period summary
        summary = build_period_summary_dict(period_data, stats, reverse_sort=thresholds.reverse_sort)

        # Add smoothing information if any intervals benefited from smoothing
        if smoothed_impactful_count > 0:
            summary["period_interval_smoothed_count"] = smoothed_impactful_count

        # Add level gap tolerance information if any intervals were kept as gaps
        if level_gap_count > 0:
            summary["period_interval_level_gap_count"] = level_gap_count

        summaries.append(summary)

    return summaries
