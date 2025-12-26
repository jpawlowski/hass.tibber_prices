"""Constants for coordinator module."""

from datetime import timedelta

# Storage version for storing data
STORAGE_VERSION = 1

# Update interval for DataUpdateCoordinator timer
# This determines how often Timer #1 runs to check if updates are needed.
# Actual API calls only happen when:
# - Cache is invalid (different day, corrupted)
# - Tomorrow data missing after 13:00
# - No cached data exists
UPDATE_INTERVAL = timedelta(minutes=15)

# Quarter-hour boundaries for entity state updates (minutes: 00, 15, 30, 45)
QUARTER_HOUR_BOUNDARIES = (0, 15, 30, 45)

# Hour after which tomorrow's price data is expected (13:00 local time)
TOMORROW_DATA_CHECK_HOUR = 13

# Random delay range for tomorrow data checks (spread API load)
# When tomorrow data is missing after 13:00, wait 0-30 seconds before fetching
# This prevents all HA instances from requesting simultaneously
TOMORROW_DATA_RANDOM_DELAY_MAX = 30  # seconds

# Entity keys that require quarter-hour updates (time-sensitive entities)
# These entities calculate values based on current time and need updates every 15 minutes
# All other entities only update when new API data arrives
TIME_SENSITIVE_ENTITY_KEYS = frozenset(
    {
        # Current/next/previous price sensors
        "current_interval_price",
        "next_interval_price",
        "previous_interval_price",
        # Current/next/previous price levels
        "current_interval_price_level",
        "next_interval_price_level",
        "previous_interval_price_level",
        # Rolling hour calculations (5-interval windows)
        "current_hour_average_price",
        "next_hour_average_price",
        "current_hour_price_level",
        "next_hour_price_level",
        # Current/next/previous price ratings
        "current_interval_price_rating",
        "next_interval_price_rating",
        "previous_interval_price_rating",
        "current_hour_price_rating",
        "next_hour_price_rating",
        # Future average sensors (rolling N-hour windows from next interval)
        "next_avg_1h",
        "next_avg_2h",
        "next_avg_3h",
        "next_avg_4h",
        "next_avg_5h",
        "next_avg_6h",
        "next_avg_8h",
        "next_avg_12h",
        # Current/future price trend sensors (time-sensitive, update at interval boundaries)
        "current_price_trend",
        "next_price_trend_change",
        # Price trend sensors
        "price_trend_1h",
        "price_trend_2h",
        "price_trend_3h",
        "price_trend_4h",
        "price_trend_5h",
        "price_trend_6h",
        "price_trend_8h",
        "price_trend_12h",
        # Trailing/leading 24h calculations (based on current interval)
        "trailing_price_average",
        "leading_price_average",
        "trailing_price_min",
        "trailing_price_max",
        "leading_price_min",
        "leading_price_max",
        # Binary sensors that check if current time is in a period
        "peak_price_period",
        "best_price_period",
        # Best/Peak price timestamp sensors (periods only change at interval boundaries)
        "best_price_end_time",
        "best_price_next_start_time",
        "peak_price_end_time",
        "peak_price_next_start_time",
        # Lifecycle sensor needs quarter-hour precision for state transitions:
        # - 23:45: turnover_pending (last interval before midnight)
        # - 00:00: turnover complete (after midnight API update)
        # - 13:00: searching_tomorrow (when tomorrow data search begins)
        # Uses state-change filter in _handle_time_sensitive_update() to prevent recorder spam
        "data_lifecycle_status",
    }
)

# Entities that require minute-by-minute updates (separate from quarter-hour updates)
# These are timing sensors that track countdown/progress within best/peak price periods
# Timestamp sensors (end_time, next_start_time) only need quarter-hour updates since periods
# can only change at interval boundaries
MINUTE_UPDATE_ENTITY_KEYS = frozenset(
    {
        # Best Price countdown/progress sensors (need minute updates)
        "best_price_remaining_minutes",
        "best_price_progress",
        "best_price_next_in_minutes",
        # Peak Price countdown/progress sensors (need minute updates)
        "peak_price_remaining_minutes",
        "peak_price_progress",
        "peak_price_next_in_minutes",
    }
)
