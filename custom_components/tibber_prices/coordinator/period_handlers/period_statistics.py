"""Period statistics calculation and summary building."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

    from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService

    from .types import (
        TibberPricesPeriodData,
        TibberPricesPeriodStatistics,
        TibberPricesThresholdConfig,
    )

from custom_components.tibber_prices.utils.average import calculate_median
from custom_components.tibber_prices.utils.price import (
    aggregate_period_levels,
    aggregate_period_ratings,
    calculate_coefficient_of_variation,
    calculate_volatility_level,
)


def calculate_period_price_diff(
    price_mean: float,
    start_time: datetime,
    price_context: dict[str, Any],
) -> tuple[float | None, float | None]:
    """
    Calculate period price difference from daily reference (min or max).

    Uses reference price from start day of the period for consistency.

    Args:
        price_mean: Mean price of the period (in base currency).
        start_time: Start time of the period.
        price_context: Dictionary with ref_prices per day.

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

    # Both prices are in base currency, no conversion needed
    ref_price_display = round(ref_price, 4)
    period_price_diff = round(price_mean - ref_price_display, 4)
    period_price_diff_pct = None
    if ref_price_display != 0:
        # CRITICAL: Use abs() for negative prices (same logic as calculate_difference_percentage)
        # Example: avg=-10, ref=-20 → diff=10, pct=10/abs(-20)*100=+50% (correctly shows more expensive)
        period_price_diff_pct = round((period_price_diff / abs(ref_price_display)) * 100, 2)

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


def calculate_period_price_statistics(
    period_price_data: list[dict],
) -> dict[str, float]:
    """
    Calculate price statistics for a period.

    Args:
        period_price_data: List of price data dictionaries with "total" field.

    Returns:
        Dictionary with price_mean, price_median, price_min, price_max, price_spread (all in base currency).
        Note: price_spread is calculated based on price_mean (max - min range as percentage of mean).

    """
    # Keep prices in base currency (Euro/NOK/SEK) for internal storage
    # Conversion to display units (ct/øre) happens in services/formatting layer
    factor = 1  # Always use base currency for storage
    prices_display = [round(float(p["total"]) * factor, 4) for p in period_price_data]

    if not prices_display:
        return {
            "price_mean": 0.0,
            "price_median": 0.0,
            "price_min": 0.0,
            "price_max": 0.0,
            "price_spread": 0.0,
        }

    price_mean = round(sum(prices_display) / len(prices_display), 4)
    median_value = calculate_median(prices_display)
    price_median = round(median_value, 4) if median_value is not None else 0.0
    price_min = round(min(prices_display), 4)
    price_max = round(max(prices_display), 4)
    price_spread = round(price_max - price_min, 4)

    return {
        "price_mean": price_mean,
        "price_median": price_median,
        "price_min": price_min,
        "price_max": price_max,
        "price_spread": price_spread,
    }


def build_period_summary_dict(
    period_data: TibberPricesPeriodData,
    stats: TibberPricesPeriodStatistics,
    *,
    reverse_sort: bool,
    price_context: dict[str, Any] | None = None,
) -> dict:
    """
    Build the complete period summary dictionary.

    Args:
        period_data: Period timing and position data
        stats: Calculated period statistics
        reverse_sort: True for peak price, False for best price (keyword-only)
        price_context: Optional dict with ref_prices, avg_prices, intervals_by_day for day statistics

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
        "price_mean": stats.price_mean,
        "price_median": stats.price_median,
        "price_min": stats.price_min,
        "price_max": stats.price_max,
        "price_spread": stats.price_spread,
        "price_coefficient_variation_%": stats.coefficient_of_variation,
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

    # Add day volatility and price statistics (for understanding midnight classification changes)
    if price_context:
        period_start_date = period_data.start_time.date()
        intervals_by_day = price_context.get("intervals_by_day", {})
        avg_prices = price_context.get("avg_prices", {})

        day_intervals = intervals_by_day.get(period_start_date, [])
        if day_intervals:
            # Calculate day price statistics (in EUR major units from API)
            day_prices = [float(p["total"]) for p in day_intervals]
            day_min = min(day_prices)
            day_max = max(day_prices)
            day_span = day_max - day_min
            day_avg = avg_prices.get(period_start_date, sum(day_prices) / len(day_prices))

            # Calculate volatility percentage (span / avg * 100)
            day_volatility_pct = round((day_span / day_avg * 100), 1) if day_avg > 0 else 0.0

            # Convert to minor units (ct/øre) for consistency with other price attributes
            summary["day_volatility_%"] = day_volatility_pct
            summary["day_price_min"] = round(day_min * 100, 2)
            summary["day_price_max"] = round(day_max * 100, 2)
            summary["day_price_span"] = round(day_span * 100, 2)

    return summary


def extract_period_summaries(
    periods: list[list[dict]],
    all_prices: list[dict],
    price_context: dict[str, Any],
    thresholds: TibberPricesThresholdConfig,
    *,
    time: TibberPricesTimeService,
) -> list[dict]:
    """
    Extract complete period summaries with all aggregated attributes.

    Returns sensor-ready period summaries with:
    - Timestamps and positioning (start, end, hour, minute, time)
    - Aggregated price statistics (price_mean, price_median, price_min, price_max, price_spread)
    - Volatility categorization (low/moderate/high/very_high based on coefficient of variation)
    - Rating difference percentage (aggregated from intervals)
    - Period price differences (period_price_diff_from_daily_min/max)
    - Aggregated level and rating_level
    - Interval count (number of 15-min intervals in period)

    All data is pre-calculated and ready for display - no further processing needed.

    Args:
        periods: List of periods, where each period is a list of interval dictionaries.
        all_prices: All price data from the API (enriched with level, difference, rating_level).
        price_context: Dictionary with ref_prices and avg_prices per day.
        thresholds: Threshold configuration for calculations.
        time: TibberPricesTimeService instance (required).

    """
    from .types import (  # noqa: PLC0415 - Avoid circular import
        TibberPricesPeriodData,
        TibberPricesPeriodStatistics,
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

        # Calculate price statistics (in base currency, conversion happens in presentation layer)
        price_stats = calculate_period_price_statistics(period_price_data)

        # Calculate period price difference from daily reference
        period_price_diff, period_price_diff_pct = calculate_period_price_diff(
            price_stats["price_mean"], start_time, price_context
        )

        # Extract prices for volatility calculation (coefficient of variation)
        prices_for_volatility = [float(p["total"]) for p in period_price_data if "total" in p]

        # Calculate CV (numeric) for quality gate checks
        period_cv = calculate_coefficient_of_variation(prices_for_volatility)

        # Calculate volatility (categorical) using thresholds
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
        period_data = TibberPricesPeriodData(
            start_time=start_time,
            end_time=end_time,
            period_length=len(period),
            period_idx=period_idx,
            total_periods=total_periods,
        )

        stats = TibberPricesPeriodStatistics(
            aggregated_level=aggregated_level,
            aggregated_rating=aggregated_rating,
            rating_difference_pct=rating_difference_pct,
            price_mean=price_stats["price_mean"],
            price_median=price_stats["price_median"],
            price_min=price_stats["price_min"],
            price_max=price_stats["price_max"],
            price_spread=price_stats["price_spread"],
            volatility=volatility,
            coefficient_of_variation=round(period_cv, 1) if period_cv is not None else None,
            period_price_diff=period_price_diff,
            period_price_diff_pct=period_price_diff_pct,
        )

        # Build complete period summary
        summary = build_period_summary_dict(
            period_data, stats, reverse_sort=thresholds.reverse_sort, price_context=price_context
        )

        # Add smoothing information if any intervals benefited from smoothing
        if smoothed_impactful_count > 0:
            summary["period_interval_smoothed_count"] = smoothed_impactful_count

        # Add level gap tolerance information if any intervals were kept as gaps
        if level_gap_count > 0:
            summary["period_interval_level_gap_count"] = level_gap_count

        summaries.append(summary)

    return summaries
