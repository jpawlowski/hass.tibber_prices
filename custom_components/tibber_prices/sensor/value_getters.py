"""Value getter mapping for Tibber Prices sensors."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from custom_components.tibber_prices.utils.average import (
    calculate_current_leading_max,
    calculate_current_leading_mean,
    calculate_current_leading_min,
    calculate_current_trailing_max,
    calculate_current_trailing_mean,
    calculate_current_trailing_min,
    calculate_mean,
    calculate_median,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from custom_components.tibber_prices.sensor.calculators.daily_stat import TibberPricesDailyStatCalculator
    from custom_components.tibber_prices.sensor.calculators.interval import TibberPricesIntervalCalculator
    from custom_components.tibber_prices.sensor.calculators.lifecycle import TibberPricesLifecycleCalculator
    from custom_components.tibber_prices.sensor.calculators.metadata import TibberPricesMetadataCalculator
    from custom_components.tibber_prices.sensor.calculators.rolling_hour import TibberPricesRollingHourCalculator
    from custom_components.tibber_prices.sensor.calculators.timing import TibberPricesTimingCalculator
    from custom_components.tibber_prices.sensor.calculators.trend import TibberPricesTrendCalculator
    from custom_components.tibber_prices.sensor.calculators.volatility import TibberPricesVolatilityCalculator
    from custom_components.tibber_prices.sensor.calculators.window_24h import TibberPricesWindow24hCalculator


def get_value_getter_mapping(
    interval_calculator: TibberPricesIntervalCalculator,
    rolling_hour_calculator: TibberPricesRollingHourCalculator,
    daily_stat_calculator: TibberPricesDailyStatCalculator,
    window_24h_calculator: TibberPricesWindow24hCalculator,
    trend_calculator: TibberPricesTrendCalculator,
    timing_calculator: TibberPricesTimingCalculator,
    volatility_calculator: TibberPricesVolatilityCalculator,
    metadata_calculator: TibberPricesMetadataCalculator,
    lifecycle_calculator: TibberPricesLifecycleCalculator,
    get_next_avg_n_hours_value: Callable[[int], float | None],
    get_data_timestamp: Callable[[], datetime | None],
    get_chart_data_export_value: Callable[[], str | None],
    get_chart_metadata_value: Callable[[], str | None],
) -> dict[str, Callable]:
    """
    Build mapping from entity key to value getter callable.

    This function centralizes the handler mapping logic, making it easier to maintain
    and understand the relationship between sensor types and their calculation methods.

    Args:
        interval_calculator: Calculator for current/next/previous interval values
        rolling_hour_calculator: Calculator for 5-interval rolling windows
        daily_stat_calculator: Calculator for daily min/max/avg statistics
        window_24h_calculator: Calculator for trailing/leading 24h windows
        trend_calculator: Calculator for price trend analysis
        timing_calculator: Calculator for best/peak price period timing
        volatility_calculator: Calculator for price volatility analysis
        metadata_calculator: Calculator for home/metering metadata
        lifecycle_calculator: Calculator for data lifecycle tracking
        get_next_avg_n_hours_value: Method for next N-hour average forecasts
        get_data_timestamp: Method for data timestamp sensor
        get_chart_data_export_value: Method for chart data export sensor
        get_chart_metadata_value: Method for chart metadata sensor

    Returns:
        Dictionary mapping entity keys to their value getter callables.

    """
    return {
        # ================================================================
        # INTERVAL-BASED SENSORS - via IntervalCalculator
        # ================================================================
        # Price level sensors
        "current_interval_price_level": interval_calculator.get_price_level_value,
        "next_interval_price_level": lambda: interval_calculator.get_interval_value(
            interval_offset=1, value_type="level"
        ),
        "previous_interval_price_level": lambda: interval_calculator.get_interval_value(
            interval_offset=-1, value_type="level"
        ),
        # Price sensors (in cents)
        "current_interval_price": lambda: interval_calculator.get_interval_value(
            interval_offset=0, value_type="price", in_euro=False
        ),
        "current_interval_price_base": lambda: interval_calculator.get_interval_value(
            interval_offset=0, value_type="price", in_euro=True
        ),
        "next_interval_price": lambda: interval_calculator.get_interval_value(
            interval_offset=1, value_type="price", in_euro=False
        ),
        "previous_interval_price": lambda: interval_calculator.get_interval_value(
            interval_offset=-1, value_type="price", in_euro=False
        ),
        # Rating sensors
        "current_interval_price_rating": lambda: interval_calculator.get_rating_value(rating_type="current"),
        "next_interval_price_rating": lambda: interval_calculator.get_interval_value(
            interval_offset=1, value_type="rating"
        ),
        "previous_interval_price_rating": lambda: interval_calculator.get_interval_value(
            interval_offset=-1, value_type="rating"
        ),
        # ================================================================
        # ROLLING HOUR SENSORS (5-interval windows) - via RollingHourCalculator
        # ================================================================
        "current_hour_price_level": lambda: rolling_hour_calculator.get_rolling_hour_value(
            hour_offset=0, value_type="level"
        ),
        "next_hour_price_level": lambda: rolling_hour_calculator.get_rolling_hour_value(
            hour_offset=1, value_type="level"
        ),
        # Rolling hour average (5 intervals: 2 before + current + 2 after)
        "current_hour_average_price": lambda: rolling_hour_calculator.get_rolling_hour_value(
            hour_offset=0, value_type="price"
        ),
        "next_hour_average_price": lambda: rolling_hour_calculator.get_rolling_hour_value(
            hour_offset=1, value_type="price"
        ),
        "current_hour_price_rating": lambda: rolling_hour_calculator.get_rolling_hour_value(
            hour_offset=0, value_type="rating"
        ),
        "next_hour_price_rating": lambda: rolling_hour_calculator.get_rolling_hour_value(
            hour_offset=1, value_type="rating"
        ),
        # ================================================================
        # DAILY STATISTICS SENSORS - via DailyStatCalculator
        # ================================================================
        "lowest_price_today": lambda: daily_stat_calculator.get_daily_stat_value(day="today", stat_func=min),
        "highest_price_today": lambda: daily_stat_calculator.get_daily_stat_value(day="today", stat_func=max),
        "average_price_today": lambda: daily_stat_calculator.get_daily_stat_value(
            day="today",
            stat_func=lambda prices: (calculate_mean(prices), calculate_median(prices)),
        ),
        # Tomorrow statistics sensors
        "lowest_price_tomorrow": lambda: daily_stat_calculator.get_daily_stat_value(day="tomorrow", stat_func=min),
        "highest_price_tomorrow": lambda: daily_stat_calculator.get_daily_stat_value(day="tomorrow", stat_func=max),
        "average_price_tomorrow": lambda: daily_stat_calculator.get_daily_stat_value(
            day="tomorrow",
            stat_func=lambda prices: (calculate_mean(prices), calculate_median(prices)),
        ),
        # Daily aggregated level sensors
        "yesterday_price_level": lambda: daily_stat_calculator.get_daily_aggregated_value(
            day="yesterday", value_type="level"
        ),
        "today_price_level": lambda: daily_stat_calculator.get_daily_aggregated_value(day="today", value_type="level"),
        "tomorrow_price_level": lambda: daily_stat_calculator.get_daily_aggregated_value(
            day="tomorrow", value_type="level"
        ),
        # Daily aggregated rating sensors
        "yesterday_price_rating": lambda: daily_stat_calculator.get_daily_aggregated_value(
            day="yesterday", value_type="rating"
        ),
        "today_price_rating": lambda: daily_stat_calculator.get_daily_aggregated_value(
            day="today", value_type="rating"
        ),
        "tomorrow_price_rating": lambda: daily_stat_calculator.get_daily_aggregated_value(
            day="tomorrow", value_type="rating"
        ),
        # ================================================================
        # 24H WINDOW SENSORS (trailing/leading from current) - via TibberPricesWindow24hCalculator
        # ================================================================
        # Trailing and leading average sensors
        "trailing_price_average": lambda: window_24h_calculator.get_24h_window_value(
            stat_func=calculate_current_trailing_mean,
        ),
        "leading_price_average": lambda: window_24h_calculator.get_24h_window_value(
            stat_func=calculate_current_leading_mean,
        ),
        # Trailing and leading min/max sensors
        "trailing_price_min": lambda: window_24h_calculator.get_24h_window_value(
            stat_func=calculate_current_trailing_min,
        ),
        "trailing_price_max": lambda: window_24h_calculator.get_24h_window_value(
            stat_func=calculate_current_trailing_max,
        ),
        "leading_price_min": lambda: window_24h_calculator.get_24h_window_value(
            stat_func=calculate_current_leading_min,
        ),
        "leading_price_max": lambda: window_24h_calculator.get_24h_window_value(
            stat_func=calculate_current_leading_max,
        ),
        # ================================================================
        # FUTURE FORECAST SENSORS
        # ================================================================
        # Future average sensors (next N hours from next interval)
        "next_avg_1h": lambda: get_next_avg_n_hours_value(1),
        "next_avg_2h": lambda: get_next_avg_n_hours_value(2),
        "next_avg_3h": lambda: get_next_avg_n_hours_value(3),
        "next_avg_4h": lambda: get_next_avg_n_hours_value(4),
        "next_avg_5h": lambda: get_next_avg_n_hours_value(5),
        "next_avg_6h": lambda: get_next_avg_n_hours_value(6),
        "next_avg_8h": lambda: get_next_avg_n_hours_value(8),
        "next_avg_12h": lambda: get_next_avg_n_hours_value(12),
        # Current and next trend change sensors
        "current_price_trend": trend_calculator.get_current_trend_value,
        "next_price_trend_change": trend_calculator.get_next_trend_change_value,
        "next_price_trend_change_in": trend_calculator.get_trend_change_in_minutes_value,
        # Price outlook sensors (current price vs average of next Xh)
        "price_outlook_1h": lambda: trend_calculator.get_price_outlook_value(hours=1),
        "price_outlook_2h": lambda: trend_calculator.get_price_outlook_value(hours=2),
        "price_outlook_3h": lambda: trend_calculator.get_price_outlook_value(hours=3),
        "price_outlook_4h": lambda: trend_calculator.get_price_outlook_value(hours=4),
        "price_outlook_5h": lambda: trend_calculator.get_price_outlook_value(hours=5),
        "price_outlook_6h": lambda: trend_calculator.get_price_outlook_value(hours=6),
        "price_outlook_8h": lambda: trend_calculator.get_price_outlook_value(hours=8),
        "price_outlook_12h": lambda: trend_calculator.get_price_outlook_value(hours=12),
        # Price trajectory sensors (first-half vs second-half window, reveals turning points)
        "price_trajectory_2h": lambda: trend_calculator.get_price_trajectory_value(hours=2),
        "price_trajectory_3h": lambda: trend_calculator.get_price_trajectory_value(hours=3),
        "price_trajectory_4h": lambda: trend_calculator.get_price_trajectory_value(hours=4),
        "price_trajectory_5h": lambda: trend_calculator.get_price_trajectory_value(hours=5),
        "price_trajectory_6h": lambda: trend_calculator.get_price_trajectory_value(hours=6),
        "price_trajectory_8h": lambda: trend_calculator.get_price_trajectory_value(hours=8),
        "price_trajectory_12h": lambda: trend_calculator.get_price_trajectory_value(hours=12),
        # Diagnostic sensors
        "data_timestamp": get_data_timestamp,
        # Data lifecycle status sensor
        "data_lifecycle_status": lifecycle_calculator.get_lifecycle_state,
        # Home metadata sensors (via MetadataCalculator)
        "home_type": lambda: metadata_calculator.get_home_metadata_value("type"),
        "home_size": lambda: metadata_calculator.get_home_metadata_value("size"),
        "main_fuse_size": lambda: metadata_calculator.get_home_metadata_value("mainFuseSize"),
        "number_of_residents": lambda: metadata_calculator.get_home_metadata_value("numberOfResidents"),
        "primary_heating_source": lambda: metadata_calculator.get_home_metadata_value("primaryHeatingSource"),
        # Metering point sensors (via MetadataCalculator)
        "grid_company": lambda: metadata_calculator.get_metering_point_value("gridCompany"),
        "grid_area_code": lambda: metadata_calculator.get_metering_point_value("gridAreaCode"),
        "price_area_code": lambda: metadata_calculator.get_metering_point_value("priceAreaCode"),
        "consumption_ean": lambda: metadata_calculator.get_metering_point_value("consumptionEan"),
        "production_ean": lambda: metadata_calculator.get_metering_point_value("productionEan"),
        "energy_tax_type": lambda: metadata_calculator.get_metering_point_value("energyTaxType"),
        "vat_type": lambda: metadata_calculator.get_metering_point_value("vatType"),
        "estimated_annual_consumption": lambda: metadata_calculator.get_metering_point_value(
            "estimatedAnnualConsumption"
        ),
        # Subscription sensors (via MetadataCalculator)
        "subscription_status": lambda: metadata_calculator.get_subscription_value("status"),
        # Day pattern sensors (via MetadataCalculator)
        "day_pattern_yesterday": lambda: metadata_calculator.get_day_pattern_value("yesterday"),
        "day_pattern_today": lambda: metadata_calculator.get_day_pattern_value("today"),
        "day_pattern_tomorrow": lambda: metadata_calculator.get_day_pattern_value("tomorrow"),
        "current_price_phase": lambda: metadata_calculator.get_current_price_phase_value(),
        "next_price_phase": lambda: metadata_calculator.get_next_price_phase_value(),
        # Price phase timing sensors (current phase duration/progress + next-phase-by-type)
        "current_price_phase_end_time": lambda: metadata_calculator.get_price_phase_timing_value("end_time"),
        "current_price_phase_remaining_minutes": lambda: metadata_calculator.get_price_phase_timing_value(
            "remaining_minutes"
        ),
        "current_price_phase_duration": lambda: metadata_calculator.get_price_phase_timing_value("duration"),
        "current_price_phase_progress": lambda: metadata_calculator.get_price_phase_timing_value("progress"),
        "next_rising_phase_start_time": lambda: metadata_calculator.get_next_phase_of_type_value(
            "rising", "start_time"
        ),
        "next_falling_phase_start_time": lambda: metadata_calculator.get_next_phase_of_type_value(
            "falling", "start_time"
        ),
        "next_flat_phase_start_time": lambda: metadata_calculator.get_next_phase_of_type_value("flat", "start_time"),
        "next_rising_phase_in_minutes": lambda: metadata_calculator.get_next_phase_of_type_value(
            "rising", "in_minutes"
        ),
        "next_falling_phase_in_minutes": lambda: metadata_calculator.get_next_phase_of_type_value(
            "falling", "in_minutes"
        ),
        "next_flat_phase_in_minutes": lambda: metadata_calculator.get_next_phase_of_type_value("flat", "in_minutes"),
        # Volatility sensors (via VolatilityCalculator)
        "today_volatility": lambda: volatility_calculator.get_volatility_value(volatility_type="today"),
        "tomorrow_volatility": lambda: volatility_calculator.get_volatility_value(volatility_type="tomorrow"),
        "next_24h_volatility": lambda: volatility_calculator.get_volatility_value(volatility_type="next_24h"),
        "today_tomorrow_volatility": lambda: volatility_calculator.get_volatility_value(
            volatility_type="today_tomorrow"
        ),
        # Price rank sensors (via VolatilityCalculator - reuses same price extraction)
        # Current interval rank
        "current_interval_price_rank_today": lambda: volatility_calculator.get_percentile_rank_value(
            subject="current_interval", percentile_type="today"
        ),
        "current_interval_price_rank_tomorrow": lambda: volatility_calculator.get_percentile_rank_value(
            subject="current_interval", percentile_type="tomorrow"
        ),
        "current_interval_price_rank_today_tomorrow": lambda: volatility_calculator.get_percentile_rank_value(
            subject="current_interval", percentile_type="today_tomorrow"
        ),
        # Next interval rank
        "next_interval_price_rank_today": lambda: volatility_calculator.get_percentile_rank_value(
            subject="next_interval", percentile_type="today"
        ),
        "next_interval_price_rank_today_tomorrow": lambda: volatility_calculator.get_percentile_rank_value(
            subject="next_interval", percentile_type="today_tomorrow"
        ),
        # Previous interval rank
        "previous_interval_price_rank_today": lambda: volatility_calculator.get_percentile_rank_value(
            subject="previous_interval", percentile_type="today"
        ),
        "previous_interval_price_rank_today_tomorrow": lambda: volatility_calculator.get_percentile_rank_value(
            subject="previous_interval", percentile_type="today_tomorrow"
        ),
        # Rolling-hour rank (1h average)
        "current_hour_price_rank_today": lambda: volatility_calculator.get_percentile_rank_value(
            subject="current_hour", percentile_type="today"
        ),
        "current_hour_price_rank_today_tomorrow": lambda: volatility_calculator.get_percentile_rank_value(
            subject="current_hour", percentile_type="today_tomorrow"
        ),
        "next_hour_price_rank_today": lambda: volatility_calculator.get_percentile_rank_value(
            subject="next_hour", percentile_type="today"
        ),
        "next_hour_price_rank_today_tomorrow": lambda: volatility_calculator.get_percentile_rank_value(
            subject="next_hour", percentile_type="today_tomorrow"
        ),
        # ================================================================
        # BEST/PEAK PRICE TIMING SENSORS - via TimingCalculator
        # ================================================================
        # Best Price timing sensors
        "best_price_end_time": lambda: timing_calculator.get_period_timing_value(
            period_type="best_price", value_type="end_time"
        ),
        "best_price_period_duration": lambda: cast(
            "float | None",
            timing_calculator.get_period_timing_value(period_type="best_price", value_type="period_duration"),
        ),
        "best_price_remaining_minutes": lambda: cast(
            "float | None",
            timing_calculator.get_period_timing_value(period_type="best_price", value_type="remaining_minutes"),
        ),
        "best_price_progress": lambda: timing_calculator.get_period_timing_value(
            period_type="best_price", value_type="progress"
        ),
        "best_price_next_start_time": lambda: timing_calculator.get_period_timing_value(
            period_type="best_price", value_type="next_start_time"
        ),
        "best_price_next_in_minutes": lambda: cast(
            "float | None",
            timing_calculator.get_period_timing_value(period_type="best_price", value_type="next_in_minutes"),
        ),
        # Peak Price timing sensors
        "peak_price_end_time": lambda: timing_calculator.get_period_timing_value(
            period_type="peak_price", value_type="end_time"
        ),
        "peak_price_period_duration": lambda: cast(
            "float | None",
            timing_calculator.get_period_timing_value(period_type="peak_price", value_type="period_duration"),
        ),
        "peak_price_remaining_minutes": lambda: cast(
            "float | None",
            timing_calculator.get_period_timing_value(period_type="peak_price", value_type="remaining_minutes"),
        ),
        "peak_price_progress": lambda: timing_calculator.get_period_timing_value(
            period_type="peak_price", value_type="progress"
        ),
        "peak_price_next_start_time": lambda: timing_calculator.get_period_timing_value(
            period_type="peak_price", value_type="next_start_time"
        ),
        "peak_price_next_in_minutes": lambda: cast(
            "float | None",
            timing_calculator.get_period_timing_value(period_type="peak_price", value_type="next_in_minutes"),
        ),
        # Chart data export sensor
        "chart_data_export": get_chart_data_export_value,
        # Chart metadata sensor
        "chart_metadata": get_chart_metadata_value,
    }
