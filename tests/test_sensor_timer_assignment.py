"""
Test sensor-to-timer assignment correctness.

This tests the CRITICAL mapping between sensor entities and update timers:
- TIME_SENSITIVE sensors → Timer #2 (quarter-hour: :00, :15, :30, :45)
- MINUTE_UPDATE sensors → Timer #3 (minute: :00, :30)
- All other sensors → No timer (only update on API data arrival)

Ensures:
1. Each sensor is assigned to the correct timer
2. Timer constants match sensor definitions
3. No sensors are missing from or incorrectly added to timer groups
"""

from custom_components.tibber_prices.binary_sensor.definitions import (
    ENTITY_DESCRIPTIONS as BINARY_SENSOR_ENTITY_DESCRIPTIONS,
)
from custom_components.tibber_prices.coordinator.constants import (
    MINUTE_UPDATE_ENTITY_KEYS,
    TIME_SENSITIVE_ENTITY_KEYS,
)
from custom_components.tibber_prices.sensor.definitions import ENTITY_DESCRIPTIONS


def test_time_sensitive_sensors_are_valid() -> None:
    """
    Test that all TIME_SENSITIVE_ENTITY_KEYS correspond to actual sensors.

    Timer #2 (quarter-hour) should only trigger for sensors that exist.
    """
    all_sensor_keys = {desc.key for desc in ENTITY_DESCRIPTIONS}
    all_binary_sensor_keys = {desc.key for desc in BINARY_SENSOR_ENTITY_DESCRIPTIONS}
    all_entity_keys = all_sensor_keys | all_binary_sensor_keys

    for entity_key in TIME_SENSITIVE_ENTITY_KEYS:
        assert entity_key in all_entity_keys, (
            f"TIME_SENSITIVE key '{entity_key}' not found in sensor/binary_sensor definitions"
        )


def test_minute_update_sensors_are_valid() -> None:
    """
    Test that all MINUTE_UPDATE_ENTITY_KEYS correspond to actual sensors.

    Timer #3 (minute) should only trigger for sensors that exist.
    """
    all_sensor_keys = {desc.key for desc in ENTITY_DESCRIPTIONS}
    all_binary_sensor_keys = {desc.key for desc in BINARY_SENSOR_ENTITY_DESCRIPTIONS}
    all_entity_keys = all_sensor_keys | all_binary_sensor_keys

    for entity_key in MINUTE_UPDATE_ENTITY_KEYS:
        assert entity_key in all_entity_keys, (
            f"MINUTE_UPDATE key '{entity_key}' not found in sensor/binary_sensor definitions"
        )


def test_no_overlap_between_timer_groups() -> None:
    """
    Test that TIME_SENSITIVE and MINUTE_UPDATE groups are mutually exclusive.

    A sensor should never be in both timer groups simultaneously.
    This would cause duplicate updates and wasted resources.
    """
    overlap = TIME_SENSITIVE_ENTITY_KEYS & MINUTE_UPDATE_ENTITY_KEYS

    assert not overlap, (
        f"Sensors should not be in both TIME_SENSITIVE and MINUTE_UPDATE: {overlap}\n"
        "Each sensor should use only ONE timer for updates."
    )


def test_interval_sensors_use_quarter_hour_timer() -> None:
    """
    Test that interval-based sensors (current/next/previous) use Timer #2.

    These sensors need updates every 15 minutes because they reference
    specific 15-minute intervals that change at quarter-hour boundaries.
    """
    interval_sensors = [
        "current_interval_price",
        "next_interval_price",
        "previous_interval_price",
        "current_interval_price_level",
        "next_interval_price_level",
        "previous_interval_price_level",
        "current_interval_price_rating",
        "next_interval_price_rating",
        "previous_interval_price_rating",
    ]

    for sensor_key in interval_sensors:
        assert sensor_key in TIME_SENSITIVE_ENTITY_KEYS, (
            f"Interval sensor '{sensor_key}' should be TIME_SENSITIVE (Timer #2)"
        )


def test_rolling_hour_sensors_use_quarter_hour_timer() -> None:
    """
    Test that rolling hour sensors (5-interval windows) use Timer #2.

    Rolling hour calculations depend on current interval position,
    which changes every 15 minutes.
    """
    rolling_hour_sensors = [
        "current_hour_average_price",
        "next_hour_average_price",
        "current_hour_price_level",
        "next_hour_price_level",
        "current_hour_price_rating",
        "next_hour_price_rating",
    ]

    for sensor_key in rolling_hour_sensors:
        assert sensor_key in TIME_SENSITIVE_ENTITY_KEYS, (
            f"Rolling hour sensor '{sensor_key}' should be TIME_SENSITIVE (Timer #2)"
        )


def test_future_avg_sensors_use_quarter_hour_timer() -> None:
    """
    Test that future N-hour average sensors use Timer #2.

    Future averages calculate rolling windows starting from "next interval",
    which changes every 15 minutes.
    """
    future_avg_sensors = [
        "next_avg_1h",
        "next_avg_2h",
        "next_avg_3h",
        "next_avg_4h",
        "next_avg_5h",
        "next_avg_6h",
        "next_avg_8h",
        "next_avg_12h",
    ]

    for sensor_key in future_avg_sensors:
        assert sensor_key in TIME_SENSITIVE_ENTITY_KEYS, (
            f"Future avg sensor '{sensor_key}' should be TIME_SENSITIVE (Timer #2)"
        )


def test_trend_sensors_use_quarter_hour_timer() -> None:
    """
    Test that price trend sensors use Timer #2.

    Trend analysis depends on current interval position and
    needs updates at quarter-hour boundaries.
    """
    trend_sensors = [
        "current_price_trend",
        "next_price_trend_change",
        "price_trend_1h",
        "price_trend_2h",
        "price_trend_3h",
        "price_trend_4h",
        "price_trend_5h",
        "price_trend_6h",
        "price_trend_8h",
        "price_trend_12h",
    ]

    for sensor_key in trend_sensors:
        assert sensor_key in TIME_SENSITIVE_ENTITY_KEYS, (
            f"Trend sensor '{sensor_key}' should be TIME_SENSITIVE (Timer #2)"
        )


def test_window_24h_sensors_use_quarter_hour_timer() -> None:
    """
    Test that trailing/leading 24h window sensors use Timer #2.

    24h windows are calculated relative to current interval,
    which changes every 15 minutes.
    """
    window_24h_sensors = [
        "trailing_price_average",
        "leading_price_average",
        "trailing_price_min",
        "trailing_price_max",
        "leading_price_min",
        "leading_price_max",
    ]

    for sensor_key in window_24h_sensors:
        assert sensor_key in TIME_SENSITIVE_ENTITY_KEYS, (
            f"24h window sensor '{sensor_key}' should be TIME_SENSITIVE (Timer #2)"
        )


def test_period_binary_sensors_use_quarter_hour_timer() -> None:
    """
    Test that best/peak price period binary sensors use Timer #2.

    Binary sensors check if current time is within a period.
    Periods can only change at quarter-hour interval boundaries.
    """
    period_binary_sensors = [
        "best_price_period",
        "peak_price_period",
    ]

    for sensor_key in period_binary_sensors:
        assert sensor_key in TIME_SENSITIVE_ENTITY_KEYS, (
            f"Period binary sensor '{sensor_key}' should be TIME_SENSITIVE (Timer #2)"
        )


def test_period_timestamp_sensors_use_quarter_hour_timer() -> None:
    """
    Test that period timestamp sensors (end_time, next_start_time) use Timer #2.

    Timestamp sensors report when periods end/start. Since periods can only
    change at quarter-hour boundaries (intervals), they only need quarter-hour updates.
    """
    timestamp_sensors = [
        "best_price_end_time",
        "best_price_next_start_time",
        "peak_price_end_time",
        "peak_price_next_start_time",
    ]

    for sensor_key in timestamp_sensors:
        assert sensor_key in TIME_SENSITIVE_ENTITY_KEYS, (
            f"Timestamp sensor '{sensor_key}' should be TIME_SENSITIVE (Timer #2)"
        )


def test_timing_sensors_use_minute_timer() -> None:
    """
    Test that countdown/progress timing sensors use Timer #3.

    These sensors track time remaining and progress percentage within periods.
    They need minute-by-minute updates for accurate countdown displays.

    IMPORTANT: Timestamp sensors (end_time, next_start_time) do NOT use Timer #3
    because periods can only change at quarter-hour boundaries.
    """
    timing_sensors = [
        "best_price_remaining_minutes",
        "best_price_progress",
        "best_price_next_in_minutes",  # Corrected from best_price_next_start_minutes
        "peak_price_remaining_minutes",
        "peak_price_progress",
        "peak_price_next_in_minutes",  # Corrected from peak_price_next_start_minutes
    ]

    for sensor_key in timing_sensors:
        assert sensor_key in MINUTE_UPDATE_ENTITY_KEYS, (
            f"Timing sensor '{sensor_key}' should be MINUTE_UPDATE (Timer #3)"
        )

        # Also verify it's NOT in TIME_SENSITIVE (no double updates)
        assert sensor_key not in TIME_SENSITIVE_ENTITY_KEYS, (
            f"Timing sensor '{sensor_key}' should NOT be in TIME_SENSITIVE\n"
            "Minute updates are sufficient for countdown/progress tracking."
        )


def test_lifecycle_sensor_uses_quarter_hour_timer() -> None:
    """
    Test that data lifecycle status sensor uses Timer #2.

    The lifecycle sensor needs quarter-hour updates to detect:
    - Turnover pending at 23:45 (quarter-hour boundary)
    - Turnover completed after midnight API update
    """
    assert "data_lifecycle_status" in TIME_SENSITIVE_ENTITY_KEYS, (
        "Lifecycle sensor needs quarter-hour updates to detect turnover_pending\n"
        "at 23:45 (last interval before midnight)"
    )


def test_daily_stat_sensors_not_in_timers() -> None:
    """
    Test that daily statistic sensors (min/max/avg) do NOT use timers.

    Daily stats don't depend on current time - they represent full-day aggregates.
    They only need updates when new API data arrives (not time-dependent).
    """
    daily_stat_sensors = [
        # Today/tomorrow min prices
        "daily_min_price_today",
        "daily_min_price_tomorrow",
        # Today/tomorrow max prices
        "daily_max_price_today",
        "daily_max_price_tomorrow",
        # Today/tomorrow averages
        "daily_average_price_today",
        "daily_average_price_tomorrow",
        # Daily price levels
        "daily_price_level_today",
        "daily_price_level_tomorrow",
        # Daily price ratings
        "daily_price_rating_today",
        "daily_price_rating_tomorrow",
    ]

    for sensor_key in daily_stat_sensors:
        assert sensor_key not in TIME_SENSITIVE_ENTITY_KEYS, (
            f"Daily stat sensor '{sensor_key}' should NOT use Timer #2\n"
            "Daily statistics don't depend on current time - only on API data arrival."
        )
        assert sensor_key not in MINUTE_UPDATE_ENTITY_KEYS, (
            f"Daily stat sensor '{sensor_key}' should NOT use Timer #3\n"
            "Daily statistics don't need minute-by-minute updates."
        )


def test_volatility_sensors_not_in_timers() -> None:
    """
    Test that volatility sensors do NOT use timers.

    Volatility analyzes price variation over fixed time windows.
    Values only change when new API data arrives (not time-dependent).
    """
    volatility_sensors = [
        "today_volatility_level",
        "tomorrow_volatility_level",
        "yesterday_volatility_level",
        "next_24h_volatility_level",
    ]

    for sensor_key in volatility_sensors:
        assert sensor_key not in TIME_SENSITIVE_ENTITY_KEYS, (
            f"Volatility sensor '{sensor_key}' should NOT use Timer #2\n"
            "Volatility calculates over fixed time windows - not time-dependent."
        )
        assert sensor_key not in MINUTE_UPDATE_ENTITY_KEYS, (
            f"Volatility sensor '{sensor_key}' should NOT use Timer #3\n"
            "Volatility doesn't need minute-by-minute updates."
        )


def test_diagnostic_sensors_not_in_timers() -> None:
    """
    Test that diagnostic/metadata sensors do NOT use timers.

    Diagnostic sensors report static metadata or system state.
    They only update when configuration changes or new API data arrives.
    """
    diagnostic_sensors = [
        "data_last_updated",
        "home_id",
        "currency_code",
        "price_unit",
        "grid_company",
        "price_level",
        "address_line1",
        "address_line2",
        "address_line3",
        "zip_code",
        "city",
        "country",
        "latitude",
        "longitude",
        "time_zone",
        "estimated_annual_consumption",
        "subscription_status",
        "chart_data_export",
    ]

    for sensor_key in diagnostic_sensors:
        # Skip data_lifecycle_status - it needs quarter-hour updates
        if sensor_key == "data_lifecycle_status":
            continue

        assert sensor_key not in TIME_SENSITIVE_ENTITY_KEYS, (
            f"Diagnostic sensor '{sensor_key}' should NOT use Timer #2\nDiagnostic data doesn't depend on current time."
        )
        assert sensor_key not in MINUTE_UPDATE_ENTITY_KEYS, (
            f"Diagnostic sensor '{sensor_key}' should NOT use Timer #3\n"
            "Diagnostic data doesn't need minute-by-minute updates."
        )


def test_timer_constants_are_comprehensive() -> None:
    """
    Test that timer constants account for all time-dependent sensors.

    Verifies no time-dependent sensors are missing from timer groups.
    This is a safety check to catch sensors that need timers but don't have them.
    """
    all_sensor_keys = {desc.key for desc in ENTITY_DESCRIPTIONS}
    all_binary_sensor_keys = {desc.key for desc in BINARY_SENSOR_ENTITY_DESCRIPTIONS}
    all_entity_keys = all_sensor_keys | all_binary_sensor_keys
    sensors_with_timers = TIME_SENSITIVE_ENTITY_KEYS | MINUTE_UPDATE_ENTITY_KEYS

    # Expected time-dependent sensor patterns
    time_dependent_patterns = [
        "current_",
        "next_",
        "previous_",
        "trailing_",
        "leading_",
        "_remaining_",
        "_progress",
        "_next_in_",  # Corrected from _next_start_
        "_end_time",
        "_period",  # Binary sensors checking if NOW is in period
        "price_trend_",
        "next_avg_",
    ]

    # Known exceptions that look time-dependent but aren't
    known_exceptions = {
        "data_last_updated",  # Timestamp of last update, not time-dependent
        "next_24h_volatility",  # Uses fixed 24h window from current time, updated on API data
        "current_interval_price_major",  # Duplicate of current_interval_price (just different unit)
        "best_price_period_duration",  # Duration in minutes, doesn't change minute-by-minute
        "peak_price_period_duration",  # Duration in minutes, doesn't change minute-by-minute
    }

    potentially_missing = [
        sensor_key
        for sensor_key in all_entity_keys
        if (
            any(pattern in sensor_key for pattern in time_dependent_patterns)
            and sensor_key not in sensors_with_timers
            and sensor_key not in known_exceptions
        )
    ]

    assert not potentially_missing, (
        f"These sensors appear time-dependent but aren't in any timer group:\n"
        f"{potentially_missing}\n\n"
        "If they truly need time-based updates, add them to TIME_SENSITIVE_ENTITY_KEYS\n"
        "or MINUTE_UPDATE_ENTITY_KEYS in coordinator/constants.py"
    )


def test_timer_group_sizes() -> None:
    """
    Test timer group sizes as documentation/regression detection.

    This isn't a strict requirement, but significant changes in group sizes
    might indicate accidental additions/removals.
    """
    # As of Nov 2025
    expected_time_sensitive_min = 40  # At least 40 sensors
    expected_minute_update = 6  # Exactly 6 timing sensors

    assert len(TIME_SENSITIVE_ENTITY_KEYS) >= expected_time_sensitive_min, (
        f"Expected at least {expected_time_sensitive_min} TIME_SENSITIVE sensors, got {len(TIME_SENSITIVE_ENTITY_KEYS)}"
    )

    assert len(MINUTE_UPDATE_ENTITY_KEYS) == expected_minute_update, (
        f"Expected exactly {expected_minute_update} MINUTE_UPDATE sensors, got {len(MINUTE_UPDATE_ENTITY_KEYS)}"
    )
