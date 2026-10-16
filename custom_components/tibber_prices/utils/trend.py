"""
Price trend along a trend line, and its confirmed timeline.

The price trend answers "in which direction are prices moving right now?". Unlike the
price outlook, which compares the current price with the average of the next hours, it
fits a robust trend line (Theil-Sen) through the prices around now: 1.5 hours back and
1.5 hours ahead. A fitted line estimates the slope at the middle of its window, so the
window is centered on now; a window starting at now would report the direction 1.5 hours
later (e.g. "rising" while prices still fall toward a minimum).

The same raw trends feed one timeline of direction groups (rising / stable / falling).
State, trend start and next trend change are all read from that timeline, so they always
agree with each other.
"""

from __future__ import annotations

from bisect import bisect_right
from functools import lru_cache
from itertools import combinations
import statistics
from typing import TYPE_CHECKING, NamedTuple

from custom_components.tibber_prices.const import (
    DEFAULT_PRICE_TREND_CHANGE_CONFIRMATION,
    DEFAULT_PRICE_TREND_MIN_PRICE_CHANGE,
    DEFAULT_PRICE_TREND_MIN_PRICE_CHANGE_STRONGLY,
    DEFAULT_PRICE_TREND_THRESHOLD_FALLING,
    DEFAULT_PRICE_TREND_THRESHOLD_RISING,
    DEFAULT_PRICE_TREND_THRESHOLD_STRONGLY_FALLING,
    DEFAULT_PRICE_TREND_THRESHOLD_STRONGLY_RISING,
    DEFAULT_VOLATILITY_THRESHOLD_HIGH,
    DEFAULT_VOLATILITY_THRESHOLD_MODERATE,
    PRICE_TREND_FALLING,
    PRICE_TREND_RISING,
    PRICE_TREND_STABLE,
    PRICE_TREND_STRONGLY_FALLING,
    PRICE_TREND_STRONGLY_RISING,
)
from custom_components.tibber_prices.utils.price import calculate_volatility_factor, classify_price_trend

if TYPE_CHECKING:
    from collections.abc import Sequence

MIN_TREND_POINTS = 5
TREND_HALF_WINDOW = 6  # The line runs 1.5h back and 1.5h ahead, centered on the interval
TREND_MIN_AHEAD = 4  # With less than 1h of known prices ahead, the trend counts as stable
TREND_LOOKBACK_INTERVALS = 96  # The timeline starts 24h back, to find when the current trend began

# rising/strongly_rising are one direction group, so are falling/strongly_falling:
# a change between the two strengths is not a trend change
TREND_DIRECTION_GROUPS = {
    PRICE_TREND_STRONGLY_RISING: PRICE_TREND_RISING,
    PRICE_TREND_RISING: PRICE_TREND_RISING,
    PRICE_TREND_STABLE: PRICE_TREND_STABLE,
    PRICE_TREND_FALLING: PRICE_TREND_FALLING,
    PRICE_TREND_STRONGLY_FALLING: PRICE_TREND_FALLING,
}


class TibberPricesTrendThresholds(NamedTuple):
    """Trend settings from the options flow; defaults are the integration defaults."""

    rising: float = DEFAULT_PRICE_TREND_THRESHOLD_RISING
    falling: float = DEFAULT_PRICE_TREND_THRESHOLD_FALLING
    strongly_rising: float = DEFAULT_PRICE_TREND_THRESHOLD_STRONGLY_RISING
    strongly_falling: float = DEFAULT_PRICE_TREND_THRESHOLD_STRONGLY_FALLING
    min_abs_diff: float = DEFAULT_PRICE_TREND_MIN_PRICE_CHANGE  # base currency
    min_abs_diff_strongly: float = DEFAULT_PRICE_TREND_MIN_PRICE_CHANGE_STRONGLY
    volatility_moderate: float = DEFAULT_VOLATILITY_THRESHOLD_MODERATE
    volatility_high: float = DEFAULT_VOLATILITY_THRESHOLD_HIGH
    confirmation: int = DEFAULT_PRICE_TREND_CHANGE_CONFIRMATION

    def classify(self, diff_pct: float, abs_diff: float, volatility_factor: float) -> str:
        """Classify a price change into the 5-level trend scale."""
        return classify_price_trend(
            diff_pct,
            abs_diff,
            volatility_factor=volatility_factor,
            threshold_rising=self.rising,
            threshold_falling=self.falling,
            threshold_strongly_rising=self.strongly_rising,
            threshold_strongly_falling=self.strongly_falling,
            min_abs_diff=self.min_abs_diff,
            min_abs_diff_strongly=self.min_abs_diff_strongly,
        )

    def effective(self, volatility_factor: float) -> dict[str, float]:
        """Percentage thresholds after the volatility adjustment, as shown in attributes."""
        return {
            "threshold_rising_%": round(self.rising * volatility_factor, 1),
            "threshold_rising_strongly_%": round(self.strongly_rising * volatility_factor, 1),
            "threshold_falling_%": round(self.falling * volatility_factor, 1),
            "threshold_falling_strongly_%": round(self.strongly_falling * volatility_factor, 1),
        }


class TrendLineChange(NamedTuple):
    """How much the trend line changes over its horizon."""

    diff_abs: float  # change along the line over the horizon, base currency
    diff_pct: float  # relative to the mean absolute price in the window


class RawTrend(NamedTuple):
    """The classified trend line at one interval, before confirmation."""

    trend: str
    change: TrendLineChange | None  # None: too little data, counted as stable
    volatility_factor: float


STABLE_RAW_TREND = RawTrend(PRICE_TREND_STABLE, None, 1.0)


class TrendSegment(NamedTuple):
    """A stretch of the timeline with one confirmed direction group."""

    start: int  # position in the raw trend list
    group: str  # PRICE_TREND_RISING | PRICE_TREND_STABLE | PRICE_TREND_FALLING


class TibberPricesTrendTimeline(NamedTuple):
    """State, start and next change of the price trend, as interval indices."""

    trend: str  # 5-level trend at the current interval
    start_index: int | None  # where the current direction began; None at the lookback edge
    previous_group: str | None  # direction group before the current one
    change_index: int | None  # where the next direction begins; None if none is confirmed
    change: RawTrend | None  # raw trend at change_index


def calculate_trend_line_change(prices: Sequence[float | None], horizon: int) -> TrendLineChange | None:
    """
    Fit a Theil-Sen trend line through `prices` (one per interval, oldest first).

    The slope is the median of the slopes between all pairs of prices. Unlike a
    least-squares fit, where the first and last price weigh most, up to about a quarter
    of the prices can be outliers without moving it; a straight ramp gives its exact slope.

    The change is the line's rise over `horizon` intervals. With a horizon of half the
    window, a straight ramp gives about "average of the next window half minus the price
    now", so the trend thresholds keep their usual meaning.

    Args:
        prices: Prices in time order, one per interval; None for a missing price, which
            is left out without shifting the time positions of the others
        horizon: Number of intervals to measure the change over

    Returns:
        The change, or None with fewer than MIN_TREND_POINTS known prices.

    """
    points = [(x, y) for x, y in enumerate(prices) if y is not None]
    if len(points) < MIN_TREND_POINTS:
        return None
    slope = statistics.median((y2 - y1) / (x2 - x1) for (x1, y1), (x2, y2) in combinations(points, 2))
    diff_abs = slope * horizon
    # Mean absolute level: stays meaningful when prices are near zero or negative
    level = sum(abs(y) for _, y in points) / len(points)
    return TrendLineChange(diff_abs, diff_abs / level * 100 if level else 0.0)


def build_trend_segments(raw_trends: Sequence[str], confirmation: int) -> list[TrendSegment]:
    """
    Turn raw trends (one per interval, oldest first) into confirmed direction segments.

    A new segment starts once `confirmation` consecutive raw trends agree on another
    direction group; it starts at the first of them. Shorter deviations (an outlier, or a
    brief pass through stable between rising and falling) keep the current segment.

    The first segment starts at position 0, the edge of the data seen, so its real start
    is unknown. Its group is the first confirmed one, so an outlier right at the edge
    doesn't create a segment boundary of its own.

    Returns:
        Segments in order, the first starting at position 0. Empty for empty input.

    """
    if not raw_trends:
        return []
    groups = [TREND_DIRECTION_GROUPS.get(trend, PRICE_TREND_STABLE) for trend in raw_trends]
    run = max(confirmation, 1)
    first = next(
        (position for position in range(len(groups)) if groups[position : position + run] == [groups[position]] * run),
        0,
    )
    segments = [TrendSegment(0, groups[first])]
    for position in range(first + 1, len(groups)):
        group = groups[position]
        if group != segments[-1].group and groups[position : position + run] == [group] * run:
            segments.append(TrendSegment(position, group))
    return segments


def trend_for_group(raw_trend: str, group: str) -> str:
    """Return the raw 5-level trend if it belongs to `group`, else the group's mild level."""
    return raw_trend if TREND_DIRECTION_GROUPS.get(raw_trend) == group else group


def build_trend_timeline(
    prices: Sequence[float | None], current_index: int, thresholds: TibberPricesTrendThresholds
) -> TibberPricesTrendTimeline:
    """
    Read the price trend at `current_index` from the confirmed timeline around it.

    Raw trends run from 24h back to the end of the data. Ahead of now, only intervals
    with a full window count, so the end of the data doesn't fake a trend change.

    Args:
        prices: One price per interval in time order (None where unknown)
        current_index: Index of the current interval in `prices`
        thresholds: Trend settings

    Returns:
        Trend, start of the current direction and the next change, as indices.

    """
    raw_all = _raw_trends(tuple(prices), thresholds)
    start = max(0, current_index - TREND_LOOKBACK_INTERVALS)
    end = max(current_index + 1, len(prices) - TREND_HALF_WINDOW)
    raw = [raw_all[index] or STABLE_RAW_TREND for index in range(start, end)]

    segments = build_trend_segments([entry.trend for entry in raw], thresholds.confirmation)
    position = current_index - start
    current = bisect_right([segment.start for segment in segments], position) - 1
    segment = segments[current]
    following = segments[current + 1] if current + 1 < len(segments) else None

    return TibberPricesTrendTimeline(
        trend=trend_for_group(raw[position].trend, segment.group),
        start_index=start + segment.start if current > 0 else None,
        previous_group=segments[current - 1].group if current > 0 else None,
        change_index=start + following.start if following else None,
        change=raw[following.start] if following else None,
    )


@lru_cache(maxsize=8)
def _raw_trends(
    prices: tuple[float | None, ...], thresholds: TibberPricesTrendThresholds
) -> tuple[RawTrend | None, ...]:
    """
    Classify the trend line at every interval (None where it can't be computed).

    Depends only on prices and settings, not on the time, so all trend sensors of a home
    share one result until new prices arrive.
    """
    raw: list[RawTrend | None] = []
    for index in range(len(prices)):
        if index + TREND_MIN_AHEAD >= len(prices):
            raw.append(None)
            continue
        window = prices[max(0, index - TREND_HALF_WINDOW) : index + TREND_HALF_WINDOW + 1]
        change = calculate_trend_line_change(window, TREND_HALF_WINDOW)
        if change is None:
            raw.append(None)
            continue
        factor = calculate_volatility_factor(
            [price for price in window if price is not None], thresholds.volatility_moderate, thresholds.volatility_high
        )
        raw.append(RawTrend(thresholds.classify(change.diff_pct, abs(change.diff_abs), factor), change, factor))
    return tuple(raw)
