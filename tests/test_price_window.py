"""
Tests for price window algorithms.

Tests the pure algorithm functions in utils/price_window.py:
- find_cheapest_contiguous_window (sliding window)
- find_cheapest_n_intervals (cheapest N picks with optional min-segment)
- group_intervals_into_segments
- calculate_window_statistics
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from custom_components.tibber_prices.utils.price_window import (
    calculate_window_statistics,
    find_cheapest_contiguous_window,
    find_cheapest_n_intervals,
    group_intervals_into_segments,
)

# =============================================================================
# Test Helpers
# =============================================================================


def _make_intervals(
    prices: list[float],
    start: datetime | None = None,
    gap_after: set[int] | None = None,
) -> list[dict]:
    """
    Create interval dicts from a list of prices.

    Args:
        prices: List of price values (one per 15-min interval).
        start: Start datetime (defaults to 2026-04-11T00:00:00+02:00).
        gap_after: Set of indices after which to insert a 15-min gap
            (making non-contiguous intervals).

    """
    if start is None:
        start = datetime(2026, 4, 11, 0, 0, tzinfo=UTC)

    intervals = []
    current = start
    for i, price in enumerate(prices):
        intervals.append(
            {
                "startsAt": current.isoformat(),
                "total": price,
                "energy": price * 0.8,
                "tax": price * 0.2,
                "level": "NORMAL",
            }
        )
        skip = 2 if gap_after and i in gap_after else 1
        current += timedelta(minutes=15 * skip)

    return intervals


# =============================================================================
# find_cheapest_contiguous_window
# =============================================================================


class TestFindCheapestContiguousWindow:
    """Tests for the sliding window algorithm."""

    def test_empty_intervals(self) -> None:
        """Return None for empty input."""
        assert find_cheapest_contiguous_window([], 4) is None

    def test_duration_exceeds_available(self) -> None:
        """Return None when not enough intervals."""
        intervals = _make_intervals([10.0, 20.0, 15.0])
        assert find_cheapest_contiguous_window(intervals, 4) is None

    def test_zero_duration(self) -> None:
        """Return None for zero duration."""
        intervals = _make_intervals([10.0, 20.0])
        assert find_cheapest_contiguous_window(intervals, 0) is None

    def test_exact_fit(self) -> None:
        """Window equals all available intervals."""
        prices = [10.0, 20.0, 15.0, 12.0]
        intervals = _make_intervals(prices)
        result = find_cheapest_contiguous_window(intervals, 4)
        assert result is not None
        assert len(result["intervals"]) == 4

    def test_single_interval(self) -> None:
        """Window of 1 picks the cheapest single interval."""
        prices = [30.0, 10.0, 20.0, 40.0]
        intervals = _make_intervals(prices)
        result = find_cheapest_contiguous_window(intervals, 1)
        assert result is not None
        assert len(result["intervals"]) == 1
        assert result["intervals"][0]["total"] == 10.0

    def test_u_shaped_curve(self) -> None:
        """Finds cheap window in center of U-shaped price curve."""
        # U-shape: expensive morning, cheap midday, expensive evening
        prices = [30.0, 25.0, 15.0, 10.0, 8.0, 9.0, 12.0, 20.0, 28.0, 35.0]
        intervals = _make_intervals(prices)
        result = find_cheapest_contiguous_window(intervals, 4)
        assert result is not None
        # Should be intervals 3-6: [10.0, 8.0, 9.0, 12.0] = sum 39.0
        selected_prices = [iv["total"] for iv in result["intervals"]]
        assert selected_prices == [10.0, 8.0, 9.0, 12.0]

    def test_v_shaped_curve(self) -> None:
        """Finds cheapest block on V-shaped day (classic Issue #108 scenario)."""
        # V-shape: expensive → cheap minimum → expensive
        prices = [25.0, 20.0, 15.0, 10.0, 5.0, 10.0, 15.0, 20.0]
        intervals = _make_intervals(prices)
        # 4-interval window: cheapest is centered on minimum
        result = find_cheapest_contiguous_window(intervals, 4)
        assert result is not None
        selected_prices = [iv["total"] for iv in result["intervals"]]
        # [15.0, 10.0, 5.0, 10.0] = 40.0 or [10.0, 5.0, 10.0, 15.0] = 40.0
        assert sum(selected_prices) == 40.0

    def test_flat_prices(self) -> None:
        """All prices equal: picks first window."""
        prices = [10.0] * 8
        intervals = _make_intervals(prices)
        result = find_cheapest_contiguous_window(intervals, 4)
        assert result is not None
        # First window (index 0)
        assert result["intervals"][0]["startsAt"] == intervals[0]["startsAt"]

    def test_cheapest_at_end(self) -> None:
        """Cheapest window is the last N intervals."""
        prices = [30.0, 25.0, 20.0, 15.0, 10.0, 5.0, 3.0, 2.0]
        intervals = _make_intervals(prices)
        result = find_cheapest_contiguous_window(intervals, 4)
        assert result is not None
        selected_prices = [iv["total"] for iv in result["intervals"]]
        assert selected_prices == [10.0, 5.0, 3.0, 2.0]

    def test_cheapest_at_start(self) -> None:
        """Cheapest window is the first N intervals."""
        prices = [2.0, 3.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0]
        intervals = _make_intervals(prices)
        result = find_cheapest_contiguous_window(intervals, 4)
        assert result is not None
        selected_prices = [iv["total"] for iv in result["intervals"]]
        assert selected_prices == [2.0, 3.0, 5.0, 10.0]

    def test_negative_prices(self) -> None:
        """Handles negative prices (renewable surplus)."""
        prices = [5.0, 3.0, -1.0, -3.0, -2.0, 1.0, 4.0, 8.0]
        intervals = _make_intervals(prices)
        result = find_cheapest_contiguous_window(intervals, 3)
        assert result is not None
        selected_prices = [iv["total"] for iv in result["intervals"]]
        # [-1.0, -3.0, -2.0] = -6.0 is cheapest 3-block
        assert selected_prices == [-1.0, -3.0, -2.0]

    def test_midnight_crossing(self) -> None:
        """Window can span midnight."""
        # 8 intervals starting at 22:00 → crossing midnight
        start = datetime(2026, 4, 11, 22, 0, tzinfo=UTC)
        prices = [20.0, 15.0, 10.0, 5.0, 3.0, 2.0, 8.0, 12.0]
        intervals = _make_intervals(prices, start=start)
        result = find_cheapest_contiguous_window(intervals, 4)
        assert result is not None
        selected_prices = [iv["total"] for iv in result["intervals"]]
        assert selected_prices == [5.0, 3.0, 2.0, 8.0]

    def test_gap_breaks_contiguous_window(self) -> None:
        """A real time gap prevents windows from spanning across it."""
        intervals = _make_intervals([1.0, 2.0, 3.0, 4.0], gap_after={1})
        assert find_cheapest_contiguous_window(intervals, 3) is None


# =============================================================================
# find_cheapest_contiguous_window — power_profile weighted scoring
# =============================================================================


class TestFindCheapestContiguousWindowWithPowerProfile:
    """Tests for power-profile-weighted window selection."""

    def test_profile_changes_selection(self) -> None:
        """Front-loaded profile prefers placing cheap intervals at high-wattage positions."""
        # Prices: [10, 10, 5, 5, 10]
        # Without profile: windows 1 and 2 both sum to 20; first tie wins (index 1, prices [10,5,5])
        # Profile [3000, 500, 500] — first interval costs 6× more per unit:
        #   Window 0: 10*3000+10*500+5*500  = 37500
        #   Window 1: 10*3000+ 5*500+5*500  = 35000
        #   Window 2:  5*3000+ 5*500+10*500 = 22500  ← cheapest weighted
        prices = [10.0, 10.0, 5.0, 5.0, 10.0]
        intervals = _make_intervals(prices)

        result_no_profile = find_cheapest_contiguous_window(intervals, 3)
        assert result_no_profile is not None
        assert result_no_profile["intervals"][0]["total"] == 10.0  # index 1

        result_profile = find_cheapest_contiguous_window(intervals, 3, power_profile=[3000, 500, 500])
        assert result_profile is not None
        assert result_profile["intervals"][0]["total"] == 5.0  # index 2

    def test_profile_no_effect_with_uniform_weights(self) -> None:
        """A uniform profile produces the same selection as no profile."""
        prices = [20.0, 15.0, 5.0, 3.0, 4.0, 18.0, 25.0]
        intervals = _make_intervals(prices)

        result_no_profile = find_cheapest_contiguous_window(intervals, 3)
        result_uniform = find_cheapest_contiguous_window(intervals, 3, power_profile=[1000, 1000, 1000])

        assert result_no_profile is not None
        assert result_uniform is not None
        assert result_no_profile["intervals"][0]["startsAt"] == result_uniform["intervals"][0]["startsAt"]

    def test_profile_reverse_most_expensive(self) -> None:
        """Profile-weighted most-expensive selection places high-watt phases on peak prices."""
        # Prices: [5, 10, 20, 10, 5]
        # Profile [3000, 500]: front-load is 6× heavier
        #   Window 0: 5*3000+10*500 = 20000
        #   Window 1: 10*3000+20*500 = 40000
        #   Window 2: 20*3000+10*500 = 65000  ← most expensive weighted
        #   Window 3: 10*3000+ 5*500 = 32500
        prices = [5.0, 10.0, 20.0, 10.0, 5.0]
        intervals = _make_intervals(prices)

        result = find_cheapest_contiguous_window(intervals, 2, reverse=True, power_profile=[3000, 500])
        assert result is not None
        assert result["intervals"][0]["total"] == 20.0  # window starts at index 2

    def test_profile_longer_than_duration_uses_first_n(self) -> None:
        """A profile longer than duration only uses the first duration_intervals values."""
        # Profile [3000, 500, 500, 999, 999] — only first 3 used for a 3-interval window
        # Should be identical to profile [3000, 500, 500]
        prices = [10.0, 10.0, 5.0, 5.0, 10.0]
        intervals = _make_intervals(prices)

        result_exact = find_cheapest_contiguous_window(intervals, 3, power_profile=[3000, 500, 500])
        result_longer = find_cheapest_contiguous_window(intervals, 3, power_profile=[3000, 500, 500, 9999, 9999])

        assert result_exact is not None
        assert result_longer is not None
        assert result_exact["intervals"][0]["startsAt"] == result_longer["intervals"][0]["startsAt"]

    def test_profile_gap_still_prevents_spanning(self) -> None:
        """Profile weighting does not override the temporal-gap check."""
        # Very cheap interval at index 2 is separated by a gap — cannot be included
        intervals = _make_intervals([10.0, 10.0, 1.0, 10.0], gap_after={1})
        # Only two contiguous segments of 2 intervals each; 3-interval window impossible
        assert find_cheapest_contiguous_window(intervals, 3, power_profile=[3000, 500, 500]) is None


# =============================================================================
# find_cheapest_n_intervals
# =============================================================================


class TestFindCheapestNIntervals:
    """Tests for the cheapest-N-picks algorithm."""

    def test_empty_intervals(self) -> None:
        """Return None for empty input."""
        assert find_cheapest_n_intervals([], 4) is None

    def test_count_exceeds_available(self) -> None:
        """Return None when not enough intervals."""
        intervals = _make_intervals([10.0, 20.0, 15.0])
        assert find_cheapest_n_intervals(intervals, 4) is None

    def test_zero_count(self) -> None:
        """Return None for zero count."""
        intervals = _make_intervals([10.0])
        assert find_cheapest_n_intervals(intervals, 0) is None

    def test_picks_cheapest(self) -> None:
        """Picks the N cheapest intervals regardless of position."""
        prices = [30.0, 10.0, 25.0, 5.0, 20.0, 8.0, 35.0, 15.0]
        intervals = _make_intervals(prices)
        result = find_cheapest_n_intervals(intervals, 3)
        assert result is not None
        selected_prices = sorted(iv["total"] for iv in result["intervals"])
        assert selected_prices == [5.0, 8.0, 10.0]

    def test_chronological_order(self) -> None:
        """Result intervals are sorted chronologically."""
        prices = [30.0, 10.0, 25.0, 5.0, 20.0, 8.0]
        intervals = _make_intervals(prices)
        result = find_cheapest_n_intervals(intervals, 3)
        assert result is not None
        starts = [iv["startsAt"] for iv in result["intervals"]]
        assert starts == sorted(starts)

    def test_segments_grouped(self) -> None:
        """Result contains segments grouping contiguous intervals."""
        # Cheapest 4 from: 30, 10, 8, 5, 20, 3, 2, 35
        # Picks: 2(idx6), 3(idx5), 5(idx3), 8(idx2)
        prices = [30.0, 10.0, 8.0, 5.0, 20.0, 3.0, 2.0, 35.0]
        intervals = _make_intervals(prices)
        result = find_cheapest_n_intervals(intervals, 4)
        assert result is not None
        assert "segments" in result
        assert len(result["segments"]) >= 1

    def test_single_contiguous_segment(self) -> None:
        """All picked intervals form one segment."""
        # Cheapest 3: indices 2,3,4 → [5.0, 3.0, 4.0] all adjacent
        prices = [20.0, 15.0, 5.0, 3.0, 4.0, 25.0, 30.0]
        intervals = _make_intervals(prices)
        result = find_cheapest_n_intervals(intervals, 3)
        assert result is not None
        assert len(result["segments"]) == 1
        assert result["segments"][0]["interval_count"] == 3

    def test_min_segment_basic(self) -> None:
        """With min_segment=2, single-interval segments are excluded."""
        # Prices: 10, 20, 30, 5, 40, 8, 7, 35
        # Without constraint: picks 5(idx3), 7(idx6), 8(idx5) → 3 isolated singles
        # With min_segment=2: must form segments ≥2 intervals
        prices = [10.0, 20.0, 30.0, 5.0, 40.0, 8.0, 7.0, 35.0]
        intervals = _make_intervals(prices)
        result = find_cheapest_n_intervals(intervals, 3, min_segment_intervals=2)
        assert result is not None
        # All segments should be ≥ 2 intervals
        for seg in result["segments"]:
            assert seg["interval_count"] >= 2

    def test_min_segment_forces_different_selection(self) -> None:
        """Min segment constraint changes the selection vs. no constraint."""
        prices = [10.0, 50.0, 50.0, 5.0, 50.0, 50.0, 8.0, 50.0]
        intervals = _make_intervals(prices)

        # Without constraint: picks indices 0(10), 3(5), 6(8)
        result_no_constraint = find_cheapest_n_intervals(intervals, 3, min_segment_intervals=1)
        assert result_no_constraint is not None
        prices_no = sorted(iv["total"] for iv in result_no_constraint["intervals"])
        assert prices_no == [5.0, 8.0, 10.0]

        # With constraint (min 2): those are all isolated → must find alternatives
        result_constrained = find_cheapest_n_intervals(intervals, 3, min_segment_intervals=2)
        assert result_constrained is not None
        # Selection will be different
        prices_constrained = sorted(iv["total"] for iv in result_constrained["intervals"])
        assert prices_constrained != prices_no

    def test_negative_prices(self) -> None:
        """Handles negative prices correctly."""
        prices = [5.0, -3.0, 10.0, -5.0, 8.0, -1.0]
        intervals = _make_intervals(prices)
        result = find_cheapest_n_intervals(intervals, 3)
        assert result is not None
        selected_prices = sorted(iv["total"] for iv in result["intervals"])
        assert selected_prices == [-5.0, -3.0, -1.0]

    def test_exact_fit(self) -> None:
        """Count equals available intervals."""
        prices = [10.0, 20.0, 15.0]
        intervals = _make_intervals(prices)
        result = find_cheapest_n_intervals(intervals, 3)
        assert result is not None
        assert len(result["intervals"]) == 3

    def test_min_segment_impossible_returns_none(self) -> None:
        """Return None instead of partial results when min segment cannot be met."""
        intervals = _make_intervals([1.0, 2.0, 3.0, 4.0], gap_after={0, 1, 2})
        assert find_cheapest_n_intervals(intervals, 2, min_segment_intervals=2) is None


# =============================================================================
# group_intervals_into_segments
# =============================================================================


class TestGroupIntervalsIntoSegments:
    """Tests for segment grouping."""

    def test_empty(self) -> None:
        """Empty input returns empty list."""
        assert group_intervals_into_segments([]) == []

    def test_single_interval(self) -> None:
        """Single interval becomes one segment."""
        intervals = _make_intervals([10.0])
        segments = group_intervals_into_segments(intervals)
        assert len(segments) == 1
        assert segments[0]["interval_count"] == 1
        assert segments[0]["duration_minutes"] == 15

    def test_all_contiguous(self) -> None:
        """All contiguous intervals form one segment."""
        intervals = _make_intervals([10.0, 20.0, 15.0, 12.0])
        segments = group_intervals_into_segments(intervals)
        assert len(segments) == 1
        assert segments[0]["interval_count"] == 4
        assert segments[0]["duration_minutes"] == 60

    def test_gap_creates_segments(self) -> None:
        """A gap creates separate segments."""
        # Gap after index 1 (30-min gap instead of 15-min)
        intervals = _make_intervals([10.0, 20.0, 15.0, 12.0], gap_after={1})
        segments = group_intervals_into_segments(intervals)
        assert len(segments) == 2
        assert segments[0]["interval_count"] == 2
        assert segments[1]["interval_count"] == 2

    def test_multiple_gaps(self) -> None:
        """Multiple gaps create multiple segments."""
        intervals = _make_intervals(
            [10.0, 20.0, 15.0, 12.0, 8.0],
            gap_after={0, 2},
        )
        segments = group_intervals_into_segments(intervals)
        assert len(segments) == 3


# =============================================================================
# calculate_window_statistics
# =============================================================================


class TestCalculateWindowStatistics:
    """Tests for price statistics calculation."""

    def test_empty(self) -> None:
        """Empty input returns all None."""
        stats = calculate_window_statistics([])
        assert stats["price_mean"] is None
        assert stats["price_median"] is None
        assert stats["estimated_total_cost"] is None

    def test_basic_stats(self) -> None:
        """Correct mean, median, min, max, spread."""
        intervals = _make_intervals([10.0, 20.0, 30.0, 40.0])
        stats = calculate_window_statistics(intervals)
        assert stats["price_mean"] == 25.0
        assert stats["price_median"] == 25.0
        assert stats["price_min"] == 10.0
        assert stats["price_max"] == 40.0
        assert stats["price_spread"] == 30.0
        # 4 intervals x 15min = 1h, cost = sum(price x 0.25h) = (10+20+30+40) x 0.25 = 25.0
        assert stats["estimated_total_cost"] == 25.0

    def test_unit_factor(self) -> None:
        """Unit factor multiplies all values."""
        intervals = _make_intervals([0.10, 0.20, 0.30])
        stats = calculate_window_statistics(intervals, unit_factor=100)
        assert stats["price_mean"] == 20.0
        assert stats["price_min"] == 10.0
        assert stats["price_max"] == 30.0
        # 3 intervals x 15min, prices in subunit: (10+20+30) x 0.25 = 15.0
        assert stats["estimated_total_cost"] == 15.0

    def test_single_interval(self) -> None:
        """Single interval: mean=median=min=max, spread=0."""
        intervals = _make_intervals([15.0])
        stats = calculate_window_statistics(intervals)
        assert stats["price_mean"] == 15.0
        assert stats["price_median"] == 15.0
        assert stats["price_min"] == 15.0
        assert stats["price_max"] == 15.0
        assert stats["price_spread"] == 0.0
        # 1 interval x 0.25h x 15.0 = 3.75
        assert stats["estimated_total_cost"] == 3.75

    def test_negative_prices(self) -> None:
        """Handles negative prices."""
        intervals = _make_intervals([-10.0, -5.0, -20.0])
        stats = calculate_window_statistics(intervals)
        assert stats["price_min"] == -20.0
        assert stats["price_max"] == -5.0
        assert stats["price_spread"] == 15.0
        # 3 intervals x 0.25h: (-10+-5+-20) x 0.25 = -8.75
        assert stats["estimated_total_cost"] == -8.75

    def test_rounding(self) -> None:
        """Results are rounded to specified decimals."""
        intervals = _make_intervals([1.0 / 3.0, 2.0 / 3.0])
        stats = calculate_window_statistics(intervals, round_decimals=2)
        assert stats["price_mean"] == 0.5
        assert stats["price_min"] == 0.33
        assert stats["price_max"] == 0.67
        # (0.333...+0.666...) x 0.25 = 0.25
        assert stats["estimated_total_cost"] == 0.25


# =============================================================================
# Reverse mode (find most expensive)
# =============================================================================


class TestFindMostExpensiveContiguousWindow:
    """Tests for the sliding window algorithm with reverse=True."""

    def test_finds_most_expensive_block(self) -> None:
        """Reverse mode finds the most expensive contiguous window."""
        prices = [10.0, 20.0, 30.0, 40.0, 5.0, 3.0, 2.0, 1.0]
        intervals = _make_intervals(prices)
        result = find_cheapest_contiguous_window(intervals, 4, reverse=True)
        assert result is not None
        selected_prices = [iv["total"] for iv in result["intervals"]]
        assert selected_prices == [10.0, 20.0, 30.0, 40.0]

    def test_most_expensive_at_end(self) -> None:
        """Most expensive window at the end."""
        prices = [1.0, 2.0, 3.0, 4.0, 10.0, 20.0, 30.0, 40.0]
        intervals = _make_intervals(prices)
        result = find_cheapest_contiguous_window(intervals, 4, reverse=True)
        assert result is not None
        selected_prices = [iv["total"] for iv in result["intervals"]]
        assert selected_prices == [10.0, 20.0, 30.0, 40.0]

    def test_reverse_single_interval(self) -> None:
        """Reverse picks the most expensive single interval."""
        prices = [5.0, 40.0, 10.0, 30.0]
        intervals = _make_intervals(prices)
        result = find_cheapest_contiguous_window(intervals, 1, reverse=True)
        assert result is not None
        assert result["intervals"][0]["total"] == 40.0

    def test_reverse_empty_returns_none(self) -> None:
        """Edge case: empty input."""
        assert find_cheapest_contiguous_window([], 4, reverse=True) is None

    def test_reverse_vs_forward_different(self) -> None:
        """Reverse and forward give different results on asymmetric data."""
        prices = [5.0, 10.0, 30.0, 25.0, 3.0, 2.0]
        intervals = _make_intervals(prices)
        cheapest = find_cheapest_contiguous_window(intervals, 2)
        most_expensive = find_cheapest_contiguous_window(intervals, 2, reverse=True)
        assert cheapest is not None
        assert most_expensive is not None
        cheap_sum = sum(iv["total"] for iv in cheapest["intervals"])
        exp_sum = sum(iv["total"] for iv in most_expensive["intervals"])
        assert exp_sum > cheap_sum


class TestFindMostExpensiveNIntervals:
    """Tests for the cheapest-N-picks algorithm with reverse=True."""

    def test_picks_most_expensive(self) -> None:
        """Reverse picks the N most expensive intervals."""
        prices = [30.0, 10.0, 25.0, 5.0, 20.0, 8.0, 35.0, 15.0]
        intervals = _make_intervals(prices)
        result = find_cheapest_n_intervals(intervals, 3, reverse=True)
        assert result is not None
        selected_prices = sorted((iv["total"] for iv in result["intervals"]), reverse=True)
        assert selected_prices == [35.0, 30.0, 25.0]

    def test_reverse_chronological_order(self) -> None:
        """Reverse result intervals are still sorted chronologically."""
        prices = [30.0, 10.0, 25.0, 5.0, 20.0, 8.0, 35.0, 15.0]
        intervals = _make_intervals(prices)
        result = find_cheapest_n_intervals(intervals, 3, reverse=True)
        assert result is not None
        starts = [iv["startsAt"] for iv in result["intervals"]]
        assert starts == sorted(starts)

    def test_reverse_min_segment(self) -> None:
        """Reverse with min_segment constraint picks expensive segments."""
        prices = [5.0, 30.0, 35.0, 3.0, 2.0, 40.0, 38.0, 1.0]
        intervals = _make_intervals(prices)
        result = find_cheapest_n_intervals(intervals, 4, min_segment_intervals=2, reverse=True)
        assert result is not None
        for seg in result["segments"]:
            assert seg["interval_count"] >= 2

    def test_reverse_empty_returns_none(self) -> None:
        """Edge case: empty input."""
        assert find_cheapest_n_intervals([], 4, reverse=True) is None

    def test_reverse_vs_forward_different(self) -> None:
        """Reverse and forward produce different sets."""
        prices = [5.0, 10.0, 30.0, 25.0, 3.0, 2.0, 40.0, 15.0]
        intervals = _make_intervals(prices)
        cheapest = find_cheapest_n_intervals(intervals, 3)
        most_expensive = find_cheapest_n_intervals(intervals, 3, reverse=True)
        assert cheapest is not None
        assert most_expensive is not None
        cheap_prices = sorted(iv["total"] for iv in cheapest["intervals"])
        exp_prices = sorted(iv["total"] for iv in most_expensive["intervals"])
        assert cheap_prices != exp_prices


# =============================================================================
# Price Comparison (Cheapest vs Most Expensive)
# =============================================================================


class TestPriceComparison:
    """Tests for price comparison between cheapest and most expensive windows."""

    def test_contiguous_window_spread(self) -> None:
        """Price difference between cheapest and most expensive contiguous windows."""
        # Prices: clear cheap period (0.05) and clear expensive period (0.30)
        prices = [0.05, 0.05, 0.05, 0.05, 0.20, 0.20, 0.30, 0.30, 0.30, 0.30]
        intervals = _make_intervals(prices)

        cheapest = find_cheapest_contiguous_window(intervals, 4, reverse=False)
        most_expensive = find_cheapest_contiguous_window(intervals, 4, reverse=True)

        assert cheapest is not None
        assert most_expensive is not None

        cheap_stats = calculate_window_statistics(cheapest["intervals"])
        expensive_stats = calculate_window_statistics(most_expensive["intervals"])

        assert cheap_stats["price_mean"] is not None
        assert expensive_stats["price_mean"] is not None

        spread = round(expensive_stats["price_mean"] - cheap_stats["price_mean"], 4)
        # Mean of [0.30, 0.30, 0.30, 0.30] - mean of [0.05, 0.05, 0.05, 0.05] = 0.25
        assert spread > 0
        assert abs(spread - 0.25) < 0.001

    def test_spread_symmetric(self) -> None:
        """Price difference is the same regardless of which direction we compute from."""
        prices = [0.10, 0.10, 0.40, 0.40, 0.15, 0.15, 0.35, 0.35]
        intervals = _make_intervals(prices)

        cheapest = find_cheapest_contiguous_window(intervals, 2, reverse=False)
        most_expensive = find_cheapest_contiguous_window(intervals, 2, reverse=True)

        assert cheapest is not None
        assert most_expensive is not None

        cheap_stats = calculate_window_statistics(cheapest["intervals"])
        expensive_stats = calculate_window_statistics(most_expensive["intervals"])

        assert cheap_stats["price_mean"] is not None
        assert expensive_stats["price_mean"] is not None

        spread_cheap_to_exp = expensive_stats["price_mean"] - cheap_stats["price_mean"]
        spread_exp_to_cheap = cheap_stats["price_mean"] - expensive_stats["price_mean"]

        assert abs(spread_cheap_to_exp + spread_exp_to_cheap) < 0.0001

    def test_n_intervals_spread(self) -> None:
        """Price difference between cheapest and most expensive N picks."""
        prices = [0.02, 0.50, 0.03, 0.45, 0.01, 0.48, 0.04, 0.42]
        intervals = _make_intervals(prices)

        cheapest = find_cheapest_n_intervals(intervals, 3, reverse=False)
        most_expensive = find_cheapest_n_intervals(intervals, 3, reverse=True)

        assert cheapest is not None
        assert most_expensive is not None

        cheap_stats = calculate_window_statistics(cheapest["intervals"])
        expensive_stats = calculate_window_statistics(most_expensive["intervals"])

        assert cheap_stats["price_mean"] is not None
        assert expensive_stats["price_mean"] is not None

        # Cheapest 3: [0.01, 0.02, 0.03] → mean 0.02
        # Most expensive 3: [0.50, 0.48, 0.45] → mean ~0.4767
        spread = expensive_stats["price_mean"] - cheap_stats["price_mean"]
        assert spread > 0.4

    def test_flat_prices_zero_spread(self) -> None:
        """Flat prices produce zero price difference."""
        prices = [0.25, 0.25, 0.25, 0.25, 0.25, 0.25]
        intervals = _make_intervals(prices)

        cheapest = find_cheapest_contiguous_window(intervals, 3, reverse=False)
        most_expensive = find_cheapest_contiguous_window(intervals, 3, reverse=True)

        assert cheapest is not None
        assert most_expensive is not None

        cheap_stats = calculate_window_statistics(cheapest["intervals"])
        expensive_stats = calculate_window_statistics(most_expensive["intervals"])

        assert cheap_stats["price_mean"] is not None
        assert expensive_stats["price_mean"] is not None

        spread = expensive_stats["price_mean"] - cheap_stats["price_mean"]
        assert abs(spread) < 0.0001

    def test_single_interval_no_spread(self) -> None:
        """With only 1 interval and duration=1, cheapest==most expensive (no difference)."""
        intervals = _make_intervals([0.30])

        cheapest = find_cheapest_contiguous_window(intervals, 1, reverse=False)
        most_expensive = find_cheapest_contiguous_window(intervals, 1, reverse=True)

        assert cheapest is not None
        assert most_expensive is not None

        cheap_stats = calculate_window_statistics(cheapest["intervals"])
        expensive_stats = calculate_window_statistics(most_expensive["intervals"])

        assert cheap_stats["price_mean"] is not None
        assert expensive_stats["price_mean"] is not None

        spread = expensive_stats["price_mean"] - cheap_stats["price_mean"]
        assert abs(spread) < 0.0001
