"""
Day price pattern detection for Tibber Prices.

Analyses quarter-hourly price intervals for a calendar day and classifies them
into a small set of patterns that are meaningful for switching decisions:

    VALLEY        - Single price minimum (U/V-shape, cheap middle)
    PEAK          - Single price maximum (Lambda-shape, expensive middle)
    DOUBLE_VALLEY - Two minima separated by a peak   (W-shape)
    DOUBLE_PEAK   - Two peaks separated by a valley  (M-shape)
    FLAT          - No significant variation (CV <= 10 %)
    RISING        - Monotonically / persistently rising
    FALLING       - Monotonically / persistently falling
    MIXED         - Multiple extrema that do not neatly fit above patterns

For VALLEY and PEAK the module also locates the *knee points* (left and right
inflection points of the flanks) using a simplified Kneedle algorithm so that
Phases 3+ can extend period boundaries geometrically.

Intra-day segments are surfaced as a list of consecutive region dicts, allowing
automations to query "is the current hour in a rising segment?".

All functions are pure (no side effects) and operate on already-enriched
interval dicts produced by utils/price.py.
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import date, datetime

    from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService

_LOGGER = logging.getLogger(__name__)
_LOGGER_DETAILS = logging.getLogger(__name__ + ".details")

# ─── constants ────────────────────────────────────────────────────────────────

# A day is considered "flat" if its coefficient of variation is below this value.
# Reuses the same threshold as relaxation.py (LOW_CV_FLAT_DAY_THRESHOLD = 10.0).
FLAT_CV_THRESHOLD = 10.0  # %

# Minimum amplitude an extremum must have to count as "significant".
# Defined as a fraction of the day's price span.  0.20 = 20 % of span.
MIN_EXTREMUM_AMPLITUDE_RATIO = 0.20

# Smoothing window (in 15-min intervals) for the rolling-average pre-filter.
SMOOTH_WINDOW = 4  # 4 x 15 min = 1 h

# Minimum intervals in a day to attempt pattern detection.
MIN_DAY_INTERVALS = 4

# Minimum intervals in a series to search for extrema.
MIN_EXTREMA_INTERVALS = 3

# Edge zone: relative position threshold for RISING / FALLING detection.
_EDGE_ZONE = 0.25

# Pattern string constants
DAY_PATTERN_VALLEY = "valley"
DAY_PATTERN_PEAK = "peak"
DAY_PATTERN_DOUBLE_VALLEY = "double_valley"
DAY_PATTERN_DOUBLE_PEAK = "double_peak"
DAY_PATTERN_FLAT = "flat"
DAY_PATTERN_RISING = "rising"
DAY_PATTERN_FALLING = "falling"
DAY_PATTERN_MIXED = "mixed"

# Segment type constants
SEGMENT_TYPE_RISING = "rising"
SEGMENT_TYPE_FALLING = "falling"
SEGMENT_TYPE_FLAT = "flat"


# ─── public API ───────────────────────────────────────────────────────────────


def detect_day_patterns(
    all_prices: list[dict[str, Any]],
    *,
    time: TibberPricesTimeService,
) -> dict[str, dict[str, Any]]:
    """
    Detect price patterns for yesterday, today, and tomorrow.

    Groups enriched price intervals by calendar day and runs pattern detection
    on each.  Always returns all three keys; ``tomorrow`` may be ``None`` if
    data is not yet available.

    Args:
        all_prices: Flat list of enriched price interval dicts (the same list
                    that ``coordinator.data["priceInfo"]`` holds).
        time:       TibberPricesTimeService (needed for timezone-aware date boundaries).

    Returns:
        ``{"yesterday": <dict|None>, "today": <dict|None>, "tomorrow": <dict|None>}``
        where each value is a ``DayPatternDict`` (see _detect_single_day_pattern).

    """
    # ── group intervals by calendar day ────────────────────────────────────────
    from .period_building import split_intervals_by_day  # avoid circular at import time  # noqa: PLC0415

    intervals_by_day, _ = split_intervals_by_day(all_prices, time=time)

    now = time.now()
    today_date: date = now.date()

    import datetime as _dt  # noqa: PLC0415

    yesterday_date = today_date - _dt.timedelta(days=1)
    tomorrow_date = today_date + _dt.timedelta(days=1)

    result: dict[str, dict[str, Any] | None] = {
        "yesterday": None,
        "today": None,
        "tomorrow": None,
    }

    day_map: dict[str, date] = {
        "yesterday": yesterday_date,
        "today": today_date,
        "tomorrow": tomorrow_date,
    }

    for label, date_key in day_map.items():
        intervals = intervals_by_day.get(date_key)
        if intervals and len(intervals) >= MIN_DAY_INTERVALS:
            try:
                result[label] = _detect_single_day_pattern(intervals, time=time)
            except Exception:
                _LOGGER.exception("Day pattern detection failed for %s (%s)", label, date_key)
                result[label] = None
        else:
            result[label] = None

    return result  # type: ignore[return-value]


# ─── single-day detection ─────────────────────────────────────────────────────


def _detect_single_day_pattern(
    intervals: list[dict[str, Any]],
    *,
    time: TibberPricesTimeService,
) -> dict[str, Any]:
    """
    Analyse a single day's intervals and return a DayPatternDict.

    The returned dict has the shape described in AGENTS.md (DayPatternDict).
    """
    # Extract prices and datetimes (already tz-aware from enrichment)
    prices_raw: list[float] = [float(iv["total"]) for iv in intervals]
    times: list[datetime] = [time.get_interval_time(iv) for iv in intervals]  # type: ignore[misc]

    # ── coefficient of variation ────────────────────────────────────────────────
    n = len(prices_raw)
    mean_price = sum(prices_raw) / n
    variance = sum((p - mean_price) ** 2 for p in prices_raw) / n
    std_dev = math.sqrt(variance)
    cv_pct = round((std_dev / abs(mean_price)) * 100, 1) if mean_price != 0 else 0.0

    # ── smooth prices (1-h rolling average) ────────────────────────────────────
    smoothed = _smooth_prices(prices_raw, window=SMOOTH_WINDOW)

    # ── find significant extrema ────────────────────────────────────────────────
    price_span = max(prices_raw) - min(prices_raw) if prices_raw else 0.0
    extrema = _find_significant_extrema(smoothed, min_amplitude=price_span * MIN_EXTREMUM_AMPLITUDE_RATIO)

    # ── classify pattern ────────────────────────────────────────────────────────
    pattern, confidence = _classify_pattern(
        extrema,
        cv_pct,
        times,
        start_price=smoothed[0],
        end_price=smoothed[-1],
    )

    # ── knee points + primary extreme time ─────────────────────────────────────
    extreme_time: datetime | None = None
    valley_start: datetime | None = None
    valley_end: datetime | None = None
    peak_start: datetime | None = None
    peak_end: datetime | None = None

    if pattern == DAY_PATTERN_VALLEY:
        # Primary extreme = global minimum
        min_idx = prices_raw.index(min(prices_raw))
        extreme_time = times[min_idx] if min_idx < len(times) else None
        lk, rk = _find_knee_points(smoothed, min_idx)
        valley_start = times[lk] if lk is not None and lk < len(times) else None
        valley_end = times[rk] if rk is not None and rk < len(times) else None

    elif pattern == DAY_PATTERN_PEAK:
        max_idx = prices_raw.index(max(prices_raw))
        extreme_time = times[max_idx] if max_idx < len(times) else None
        lk, rk = _find_knee_points(smoothed, max_idx)
        peak_start = times[lk] if lk is not None and lk < len(times) else None
        peak_end = times[rk] if rk is not None and rk < len(times) else None

    elif pattern == DAY_PATTERN_DOUBLE_VALLEY and extrema:
        # Primary extreme = deeper of the two minima
        min_extrema = [e for e in extrema if e["type"] == "min"]
        if min_extrema:
            primary = min(min_extrema, key=lambda e: e["price"])
            extreme_time = times[primary["idx"]] if primary["idx"] < len(times) else None

    elif pattern == DAY_PATTERN_DOUBLE_PEAK and extrema:
        max_extrema = [e for e in extrema if e["type"] == "max"]
        if max_extrema:
            primary = max(max_extrema, key=lambda e: e["price"])
            extreme_time = times[primary["idx"]] if primary["idx"] < len(times) else None
        # The valley between the two peaks is the cheap zone for best-price periods.
        # Compute knee points around the deepest minimum so that compute_geometric_flex_bonus
        # can apply extra flex to intervals in this zone (same mechanism as VALLEY).
        min_extrema_dp = [e for e in extrema if e["type"] == "min"]
        if min_extrema_dp:
            valley_extreme = min(min_extrema_dp, key=lambda e: e["price"])
            lk, rk = _find_knee_points(smoothed, valley_extreme["idx"])
            valley_start = times[lk] if lk is not None and lk < len(times) else None
            valley_end = times[rk] if rk is not None and rk < len(times) else None
        # The valley between the two peaks is the cheap zone for best-price periods.
        # Compute knee points around the deepest minimum so that compute_geometric_flex_bonus
        # can apply extra flex to intervals inside this zone (same mechanism as VALLEY).
        min_extrema_dp = [e for e in extrema if e["type"] == "min"]
        if min_extrema_dp:
            valley_extreme = min(min_extrema_dp, key=lambda e: e["price"])
            lk, rk = _find_knee_points(smoothed, valley_extreme["idx"])
            valley_start = times[lk] if lk is not None and lk < len(times) else None
            valley_end = times[rk] if rk is not None and rk < len(times) else None

    # ── intra-day segments ──────────────────────────────────────────────────────
    segments = _detect_segments(extrema, prices_raw, times)

    result: dict[str, Any] = {
        "pattern": pattern,
        "confidence": round(confidence, 3),
        "day_cv_percent": cv_pct,
        "segments": segments,
        "extreme_time": extreme_time,
        "valley_start": valley_start,
        "valley_end": valley_end,
        "peak_start": peak_start,
        "peak_end": peak_end,
    }

    _LOGGER_DETAILS.debug(
        "  Day pattern: %s (confidence=%.2f, cv=%.1f%%, extrema=%d, segments=%d)",
        pattern,
        confidence,
        cv_pct,
        len(extrema),
        len(segments),
    )

    return result


# ─── smoothing ────────────────────────────────────────────────────────────────


def _smooth_prices(prices: list[float], window: int = SMOOTH_WINDOW) -> list[float]:
    """
    Apply a centred rolling-average with the given window width.

    Edge intervals use a narrower window (no zero-padding) so that pattern
    detection at the start/end of the day is not distorted.
    """
    n = len(prices)
    half = window // 2
    smoothed: list[float] = []
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        smoothed.append(sum(prices[lo:hi]) / (hi - lo))
    return smoothed


# ─── extrema detection ────────────────────────────────────────────────────────


def _find_significant_extrema(
    smoothed: list[float],
    *,
    min_amplitude: float,
) -> list[dict[str, Any]]:
    """
    Find local minima and maxima in the smoothed price series.

    A local extremum is retained only if it exceeds *min_amplitude* above/below
    both of its closest neighbours of the opposite polarity (prominence filter).

    Returns a list of ``{"idx": int, "type": "min"|"max", "price": float}``
    entries sorted by index.
    """
    n = len(smoothed)
    if n < MIN_EXTREMA_INTERVALS:
        return []

    # ── raw local extrema (strict local min/max) ────────────────────────────────
    # NOTE: We intentionally do NOT require the extremum to be below/above the
    # day's start and end prices. That check was too restrictive for solar-
    # influenced days (spring/summer) where overnight prices are as cheap as the
    # midday valley, causing the midday dip to go undetected. The amplitude/
    # prominence filter below is sufficient to suppress noise.
    candidates: list[dict[str, Any]] = []
    for i in range(1, n - 1):
        prev_p = smoothed[i - 1]
        cur_p = smoothed[i]
        next_p = smoothed[i + 1]
        if cur_p <= prev_p and cur_p <= next_p:
            candidates.append({"idx": i, "type": "min", "price": cur_p})
        elif cur_p >= prev_p and cur_p >= next_p:
            candidates.append({"idx": i, "type": "max", "price": cur_p})

    if not candidates:
        return []

    # ── amplitude filter ────────────────────────────────────────────────────────
    # For each candidate, measure prominence against the most representative
    # reference price available.
    #
    # Problem with pure local-neighbourhood mean: a broad, flat-bottomed valley
    # (e.g. a 5-hour cheap midday zone) pulls the neighbourhood mean down toward
    # the valley price itself, making the prominence appear near-zero even though
    # the valley is clearly significant on the full day.
    #
    # Solution: use max(local_mean, day_mean) for minima and min(local_mean,
    # day_mean) for maxima.  This picks the reference that gives the LARGEST
    # separation for genuine extrema:
    #   - Deep/broad valley: local_mean ≈ valley price → day_mean wins (higher).
    #   - Overnight plateau max: local_mean ≈ plateau price → day_mean wins (lower).
    #   - Sharp isolated spike: local_mean already high → day_mean may be lower,
    #     but the spike still has large prominence either way.
    day_mean = sum(smoothed) / len(smoothed)
    significant: list[dict[str, Any]] = []
    for cand in candidates:
        idx = cand["idx"]
        hw = max(4, n // 8)  # neighbourhood half-width: ≥4 intervals, up to 1/8 of day
        lo = max(0, idx - hw)
        hi = min(n, idx + hw + 1)
        neighbourhood = smoothed[lo:hi]
        local_mean = sum(neighbourhood) / len(neighbourhood)
        if cand["type"] == "min":
            reference = max(local_mean, day_mean)  # broad valley: day_mean dominates
            prominence = reference - cand["price"]
        else:
            reference = min(local_mean, day_mean)  # plateau max: day_mean dominates
            prominence = cand["price"] - reference
        if prominence >= min_amplitude * 0.8:  # slight tolerance on the threshold
            significant.append(cand)

    # ── deduplicate: keep only the most extreme value between alternating types ──
    return _deduplicate_extrema(significant)


def _deduplicate_extrema(extrema: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Ensure extrema alternate between min and max.

    Between two consecutive minima (or two consecutive maxima), keep only the
    more extreme one.  This mirrors the classical definition of alternating
    local extrema.
    """
    if not extrema:
        return []
    result: list[dict[str, Any]] = [extrema[0]]
    for e in extrema[1:]:
        last = result[-1]
        if e["type"] == last["type"]:
            # Same type - keep the more extreme one
            if e["type"] == "min":
                if e["price"] < last["price"]:
                    result[-1] = e
            elif e["price"] > last["price"]:
                result[-1] = e
        else:
            result.append(e)
    return result


# ─── pattern classification ───────────────────────────────────────────────────


def _classify_pattern(
    extrema: list[dict[str, Any]],
    cv_pct: float,
    times: list[datetime],
    start_price: float = 0.0,
    end_price: float = 0.0,
) -> tuple[str, float]:
    """
    Classify the day into a pattern string and confidence score (0-1).

    Args:
        extrema:     List of significant extrema (already deduplicated).
        cv_pct:      Coefficient of variation for the day (%).
        times:       Timestamps of all intervals (for position calculations).
        start_price: Smoothed price of the first interval (day start).
        end_price:   Smoothed price of the last interval (day end).

    Returns:
        (pattern_string, confidence_float)

    """
    n_times = len(times)

    # ── flat day ────────────────────────────────────────────────────────────────
    if cv_pct <= FLAT_CV_THRESHOLD:
        # Confidence scales with how flat it is relative to threshold
        confidence = max(0.5, 1.0 - cv_pct / FLAT_CV_THRESHOLD)
        return DAY_PATTERN_FLAT, confidence

    # ── no significant extrema → monotone (rising or falling) ──────────────────
    if not extrema:
        # Cannot determine direction without access to underlying prices from here.
        # The caller (_detect_single_day_pattern) handles the RISING/FALLING case
        # before calling _classify_pattern when there are no extrema but prices exist.
        return DAY_PATTERN_MIXED, 0.4

    n_extrema = len(extrema)
    types = [e["type"] for e in extrema]

    # ── single extremum ─────────────────────────────────────────────────────────
    if n_extrema == 1:
        e = extrema[0]
        # Check position: central extrema → stronger pattern
        rel_pos = e["idx"] / max(1, n_times - 1)
        centrality = 1.0 - abs(rel_pos - 0.5) * 2  # 0 at edges, 1 at centre

        if e["type"] == "min":
            confidence = 0.6 + 0.4 * centrality
            return DAY_PATTERN_VALLEY, confidence
        # max
        # Check if it's edge-dominant: peak near start -> FALLING, near end -> RISING
        if rel_pos < _EDGE_ZONE:
            return DAY_PATTERN_FALLING, 0.6
        if rel_pos > 1.0 - _EDGE_ZONE:
            return DAY_PATTERN_RISING, 0.6
        confidence = 0.6 + 0.4 * centrality
        return DAY_PATTERN_PEAK, confidence

    # ── two extrema ─────────────────────────────────────────────────────────────
    if n_extrema == 2:
        if types == ["max", "min"]:
            # Check if max is above both endpoints → genuine interior peak
            max_price = extrema[0]["price"]
            if start_price > 0 and end_price > 0 and max_price > start_price and max_price > end_price:
                return DAY_PATTERN_PEAK, 0.65
            return DAY_PATTERN_FALLING, 0.7
        if types == ["min", "max"]:
            # Check if min is below both endpoints → genuine interior valley
            # (avoids misclassifying as RISING a day that starts/ends expensive
            # but has a cheap midday zone, e.g. spring solar duck-curve).
            min_price = extrema[0]["price"]
            if start_price > 0 and end_price > 0 and min_price < start_price and min_price < end_price:
                return DAY_PATTERN_VALLEY, 0.65
            return DAY_PATTERN_RISING, 0.7
        if types == ["min", "min"]:
            return DAY_PATTERN_DOUBLE_VALLEY, 0.65
        if types == ["max", "max"]:
            return DAY_PATTERN_DOUBLE_PEAK, 0.65

    # ── three extrema ────────────────────────────────────────────────────────────
    if n_extrema == 3:
        # min-max-min → W-shape
        if types == ["min", "max", "min"]:
            return DAY_PATTERN_DOUBLE_VALLEY, 0.75
        # max-min-max → M-shape
        if types == ["max", "min", "max"]:
            return DAY_PATTERN_DOUBLE_PEAK, 0.75
        # min-max or max-min with trailing → RISING/FALLING with extra bump
        if types[0] == "min" and types[-1] == "max":
            return DAY_PATTERN_RISING, 0.55
        if types[0] == "max" and types[-1] == "min":
            return DAY_PATTERN_FALLING, 0.55

    # ── four or more extrema ─────────────────────────────────────────────────────
    # Count dominating type
    n_min = types.count("min")
    n_max = types.count("max")
    if abs(n_min - n_max) <= 1:
        return DAY_PATTERN_MIXED, 0.5
    # More minima: day is mostly cheap → loosely valley-ish
    if n_min > n_max:
        return DAY_PATTERN_MIXED, 0.45
    return DAY_PATTERN_MIXED, 0.45


# ─── knee point detection (simplified Kneedle) ───────────────────────────────


def _find_knee_points(
    smoothed: list[float],
    extreme_idx: int,
) -> tuple[int | None, int | None]:
    """
    Find the left and right knee points of a V-/Λ-shaped flank.

    Uses a simplified Kneedle algorithm:
    1. Normalise each flank to [0,1] on both axes.
    2. Compute the perpendicular distance of each point from the straight line
       connecting the flank start to the extreme point.
    3. The knee is the point of maximum perpendicular distance.

    Args:
        smoothed:    Smoothed price series for the full day.
        extreme_idx: Index of the valley minimum (VALLEY) or peak maximum (PEAK).
        is_minimum:  True for valley (prices falling then rising),
                     False for peak (prices rising then falling).

    Returns:
        ``(left_knee_idx, right_knee_idx)`` - indices into ``smoothed``.
        Either may be ``None`` if the flank is too short.

    """
    n = len(smoothed)

    left_idx = _find_knee_on_flank(smoothed, start=0, end=extreme_idx)
    right_idx = _find_knee_on_flank(smoothed, start=extreme_idx, end=n - 1)

    return left_idx, right_idx


def _find_knee_on_flank(
    prices: list[float],
    start: int,
    end: int,
) -> int | None:
    """
    Locate the knee on one flank using the simplified Kneedle method.

    Args:
        prices:     Full price series.
        start:      Index of flank start.
        end:        Index of flank end (the extreme point).
        descending: True if prices fall from start → end, False if they rise.

    Returns:
        Index of knee point, or ``None`` if flank is fewer than 4 intervals.

    """
    length = end - start
    if length < MIN_EXTREMA_INTERVALS:
        return None

    p_start = prices[start]
    p_end = prices[end]

    # Normalise so that start=(0,0) and end=(1,1)
    px_range = float(length)
    py_range = p_end - p_start
    if abs(py_range) < 1e-9:
        return None  # Flat flank - no knee

    max_dist = 0.0
    knee_idx: int | None = None
    for i in range(start + 1, end):
        # Normalised coordinates
        nx = (i - start) / px_range
        ny = (prices[i] - p_start) / py_range
        # For the line y=x: perpendicular distance = |ny - nx| / sqrt(2)
        dist = abs(ny - nx) / math.sqrt(2)
        if dist > max_dist:
            max_dist = dist
            knee_idx = i

    return knee_idx


# ─── intra-day segment detection ─────────────────────────────────────────────


def _detect_segments(
    extrema: list[dict[str, Any]],
    prices: list[float],
    times: list[datetime],
) -> list[dict[str, Any]]:
    """
    Build a list of monotone segments separated by the detected extrema.

    Each segment is a dict with:
        type        - "rising" | "falling" | "flat"
        start       - tz-aware datetime of first interval
        end         - tz-aware datetime of last interval
        price_min   - min price in segment (EUR/NOK/SEK)
        price_max   - max price in segment
        price_mean  - mean price in segment

    """
    n = len(prices)
    if n == 0:
        return []

    # Build boundary indices: 0, all extremum indices, n-1
    boundaries = [0, *sorted(e["idx"] for e in extrema), n - 1]
    # Deduplicate consecutive boundaries
    boundaries = list(dict.fromkeys(boundaries))  # preserves order, removes dupes

    segments: list[dict[str, Any]] = []
    for seg_i in range(len(boundaries) - 1):
        lo = boundaries[seg_i]
        hi = boundaries[seg_i + 1]
        if hi <= lo:
            continue
        seg_prices = prices[lo : hi + 1]
        price_start = prices[lo]
        price_end = prices[hi]
        delta = price_end - price_start
        span = max(seg_prices) - min(seg_prices)

        if span < (max(prices) - min(prices)) * 0.05:
            seg_type = SEGMENT_TYPE_FLAT
        elif delta > 0:
            seg_type = SEGMENT_TYPE_RISING
        else:
            seg_type = SEGMENT_TYPE_FALLING

        seg: dict[str, Any] = {
            "type": seg_type,
            "start": times[lo].isoformat() if lo < len(times) and times[lo] is not None else None,
            "end": times[hi].isoformat() if hi < len(times) and times[hi] is not None else None,
            "price_min": round(min(seg_prices), 4),
            "price_max": round(max(seg_prices), 4),
            "price_mean": round(sum(seg_prices) / len(seg_prices), 4),
        }
        segments.append(seg)

    return segments
