"""
Attribute declarations of the sensors, by family (see utils/attribute_specs.py).

Entities that expose the same attributes share a set; hour-bound ones are functions of the hour count.
Only what an attribute builder adds on top of the common attributes (timestamp, description, usage tips)
is listed. `history=True` marks what the recorder keeps; everything else stays out of the database.
"""

from __future__ import annotations

from custom_components.tibber_prices.utils.attribute_specs import TibberPricesAttribute, attribute

# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------
ICON_COLOR = (attribute("icon_color"),)

# Mean and median next to the state; energy and tax shares when the price is split
PRICE_AVERAGES = (attribute("price_mean", history=True), attribute("price_median", history=True))
SPLIT_AVERAGES = (
    attribute("energy_price_mean"),
    attribute("energy_price_median"),
    attribute("tax_mean"),
    attribute("tax_median"),
)
PRICE_SPLIT = (attribute("energy_price"), attribute("tax"))

# The time span a rolling hour value covers
ROLLING_WINDOW = (attribute("window_start"), attribute("window_end"))

TREND_THRESHOLDS = (
    attribute("threshold_rising_percent"),
    attribute("threshold_rising_strongly_percent"),
    attribute("threshold_falling_percent"),
    attribute("threshold_falling_strongly_percent"),
)

# ---------------------------------------------------------------------------
# Interval and hour prices, levels and ratings
# ---------------------------------------------------------------------------
INTERVAL_PRICE = (*PRICE_SPLIT, *ICON_COLOR)

# The price of the current interval also carries the outlook lists
CURRENT_INTERVAL_PRICE = (
    *INTERVAL_PRICE,
    attribute("outlook_units"),
    attribute("outlook_day_part_hours"),
    attribute("outlook_hours"),
    attribute("outlook_days"),
    attribute("outlook_day_parts"),
    attribute("outlook_yesterday"),
    attribute("outlook_quarters"),
    attribute("outlook_past_periods"),
)

HOUR_AVERAGE_PRICE = (
    *ROLLING_WINDOW,
    attribute("clock_hour_start"),
    attribute("clock_hour_end"),
    attribute("clock_hour_price_mean"),
    attribute("clock_hour_price_median"),
    *PRICE_AVERAGES,
    *ICON_COLOR,
)

PRICE_LEVEL = (attribute("level_id"), attribute("level_value"), *ICON_COLOR)
HOUR_PRICE_LEVEL = (*ROLLING_WINDOW, *PRICE_LEVEL)
# How long the current level lasts and when the next cheap or expensive stretch starts
CURRENT_PRICE_LEVEL = (
    *PRICE_LEVEL,
    attribute("cheap_until"),
    attribute("next_cheap_start"),
    attribute("expensive_until"),
    attribute("next_expensive_start"),
)

PRICE_RATING = (
    attribute("rating_id"),
    attribute("rating_value"),
    attribute("diff_percent"),
    *PRICE_LEVEL,
)
HOUR_PRICE_RATING = (*ROLLING_WINDOW, *PRICE_RATING)

# ---------------------------------------------------------------------------
# Statistics over a day, a window or the next hours
# ---------------------------------------------------------------------------
DAILY_STATISTICS = (*PRICE_SPLIT, *SPLIT_AVERAGES, *PRICE_AVERAGES)
WINDOW_STATISTICS = (attribute("interval_count"), *SPLIT_AVERAGES, *PRICE_AVERAGES)
NEXT_AVERAGE = (attribute("interval_count"), attribute("hours"), *SPLIT_AVERAGES, *PRICE_AVERAGES)

# ---------------------------------------------------------------------------
# Volatility and price rank
# ---------------------------------------------------------------------------
VOLATILITY = (
    attribute("price_volatility"),
    attribute("price_coefficient_variation_percent", history=True),
    attribute("price_spread"),
    attribute("price_min", history=True),
    attribute("price_max", history=True),
    *PRICE_AVERAGES,
    attribute("price_q25"),
    attribute("price_q75"),
    attribute("price_typical_spread"),
    attribute("price_typical_spread_percent"),
    attribute("price_spike_count"),
    attribute("interval_count"),
    *ICON_COLOR,
)
# Today and tomorrow together also say how each day compares
TODAY_TOMORROW_VOLATILITY = (
    *VOLATILITY,
    attribute("today_volatility"),
    attribute("tomorrow_volatility"),
    attribute("interval_count_today"),
    attribute("interval_count_tomorrow"),
)


def rank_attributes(price: str) -> tuple[TibberPricesAttribute, ...]:
    """Return the attributes of a price rank sensor; `price` names the price it ranks (`current_price`)."""
    return (
        attribute("prices_below_count"),
        attribute("interval_count"),
        attribute("reference_min"),
        attribute("reference_max"),
        attribute("reference_mean"),
        attribute(price),
    )


# ---------------------------------------------------------------------------
# Trend, outlook and trajectory
# ---------------------------------------------------------------------------
# The trend calculator writes the second half of the window for windows longer than its MIN_HOURS_FOR_LATER_HALF (1)
SECOND_HALF_FROM_HOURS = 2


def outlook_attributes(hours: int) -> tuple[TibberPricesAttribute, ...]:
    """Return the attributes of the price outlook sensor of `hours` hours (the second half from 2 hours on)."""
    attributes = (
        attribute("trend_value"),
        attribute("interval_count"),
        attribute("volatility_factor"),
        *ICON_COLOR,
        attribute("trend_{h}h_percent", hours=hours),
        attribute("next_{h}h_avg", hours=hours),
        *TREND_THRESHOLDS,
    )
    if hours < SECOND_HALF_FROM_HOURS:
        return attributes
    return (
        *attributes,
        attribute("second_half_{h}h_avg", hours=hours),
        attribute("second_half_{h}h_diff_from_current_percent", hours=hours),
    )


def trajectory_attributes(hours: int) -> tuple[TibberPricesAttribute, ...]:
    """Return the attributes of the price trajectory sensor of `hours` hours."""
    return (
        attribute("trend_value"),
        attribute("volatility_factor"),
        *ICON_COLOR,
        attribute("trajectory_{h}h_percent", hours=hours),
        attribute("first_half_{h}h_avg", hours=hours),
        attribute("second_half_{h}h_avg", hours=hours),
        attribute("first_half_{h}h_diff_from_current_percent", hours=hours),
        attribute("second_half_{h}h_diff_from_current_percent", hours=hours),
        attribute("first_half_interval_count"),
        attribute("second_half_interval_count"),
    )


CURRENT_PRICE_TREND = (
    attribute("previous_direction", history=True),
    attribute("price_direction_duration_minutes"),
    attribute("price_direction_since"),
    *ICON_COLOR,
)
# The next change of the trend: the state is its time (or the minutes until it)
TREND_CHANGE = (
    attribute("direction", history=True),
    attribute("from_direction", history=True),
    attribute("minutes_until_change"),
    attribute("price_now"),
    attribute("price_at_change"),
    attribute("price_avg_after_change"),
    attribute("trend_diff_percent"),
    attribute("volatility_factor"),
    *TREND_THRESHOLDS,
)

# ---------------------------------------------------------------------------
# Day pattern, price phases and timing
# ---------------------------------------------------------------------------
DAY_PATTERN = (
    attribute("confidence"),
    attribute("day_cv_percent"),
    attribute("extreme_time"),
    attribute("valley_start"),
    attribute("valley_end"),
    attribute("peak_start"),
    attribute("peak_end"),
    attribute("segments"),
)
PRICE_PHASE = (
    attribute("start"),
    attribute("end"),
    attribute("price_min", history=True),
    attribute("price_max", history=True),
    attribute("price_mean", history=True),
    attribute("segment_index"),
    attribute("segment_count"),
    attribute("all_segments"),
    attribute("is_tomorrow"),
)
# The state of the timing sensors already is the number of minutes: the attributes only repeat it
PERIOD_TIMING = (
    *ICON_COLOR,
    attribute("period_duration_minutes"),
    attribute("remaining_minutes"),
    attribute("next_in_minutes"),
)
PHASE_TIMING = (
    *ICON_COLOR,
    attribute("phase_duration_minutes"),
    attribute("remaining_minutes"),
    attribute("next_in_minutes"),
)

# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------
DATA_LIFECYCLE = (
    attribute("tomorrow_available", history=True),
    attribute("next_api_poll"),
    attribute("updates_today", history=True),
    attribute("last_turnover"),
    attribute("last_error"),
)
CHART_METADATA = (
    attribute("yaxis_min"),
    attribute("yaxis_max"),
    attribute("yaxis_min_energy"),
    attribute("yaxis_max_energy"),
    attribute("yaxis_min_tax"),
    attribute("yaxis_max_tax"),
    attribute("currency"),
    attribute("resolution"),
    attribute("error"),
)
# The chart data export also exposes the service's result as attributes (open_attributes); `data` is the large one
CHART_DATA_EXPORT = (attribute("data"), attribute("currency"), attribute("error"))
