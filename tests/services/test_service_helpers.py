"""Tests for small pure helper functions in services/helpers.py."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

from custom_components.tibber_prices.services.helpers import async_fetch_service_intervals, check_min_distance_from_avg


class TestCheckMinDistanceFromAvgPositiveAverage:
    """Regression coverage for the common case: positive range average."""

    def test_cheapest_passes_when_far_enough_below(self) -> None:
        """Window 10% below a positive average passes a 5% requirement."""
        assert check_min_distance_from_avg(18.0, 20.0, 5.0, reverse=False) is True

    def test_cheapest_fails_when_too_close(self) -> None:
        """Window only 2% below a positive average fails a 5% requirement."""
        assert check_min_distance_from_avg(19.6, 20.0, 5.0, reverse=False) is False

    def test_most_expensive_passes_when_far_enough_above(self) -> None:
        """Window 10% above a positive average passes a 5% requirement."""
        assert check_min_distance_from_avg(22.0, 20.0, 5.0, reverse=True) is True

    def test_most_expensive_fails_when_too_close(self) -> None:
        """Window only 2% above a positive average fails a 5% requirement."""
        assert check_min_distance_from_avg(20.4, 20.0, 5.0, reverse=True) is False


class TestCheckMinDistanceFromAvgNegativeAverage:
    """Regression coverage for GH-reported sign bug: negative range average.

    Tibber prices can go negative during grid oversupply. The threshold must
    be computed as `avg ± abs(avg) * ratio` (not `avg * (1 ± ratio)`), since
    multiplying a negative average directly flips the intended direction.
    """

    def test_cheapest_passes_when_more_negative_than_avg(self) -> None:
        """A window that is 10% cheaper (more negative) than a -5 avg passes 5% req."""
        # -5 - abs(-5)*0.05 = -5.25 → window must be <= -5.25
        assert check_min_distance_from_avg(-5.6, -5.0, 5.0, reverse=False) is True

    def test_cheapest_fails_when_less_negative_than_avg(self) -> None:
        """A window that is actually more expensive (less negative) than avg must fail.

        Regression: the old buggy formula (avg * (1 - ratio)) computed a
        threshold of -4.75 here, incorrectly letting -5.1 pass even though
        it is only ~2% below avg (needs 5%).
        """
        assert check_min_distance_from_avg(-5.1, -5.0, 5.0, reverse=False) is False

    def test_most_expensive_passes_when_less_negative_than_avg(self) -> None:
        """A window 10% above (less negative than) a -5 avg passes a 5% req."""
        # -5 + abs(-5)*0.05 = -4.75 → window must be >= -4.75
        assert check_min_distance_from_avg(-4.4, -5.0, 5.0, reverse=True) is True

    def test_most_expensive_fails_when_actually_cheaper_than_avg(self) -> None:
        """A window that is cheaper (more negative) than avg must fail the most-expensive check.

        Regression: the old buggy formula (avg * (1 + ratio)) computed a
        threshold of -5.25 here, incorrectly letting -5.1 pass even though
        it is actually cheaper than the average, not more expensive.
        """
        assert check_min_distance_from_avg(-5.1, -5.0, 5.0, reverse=True) is False


class TestCheckMinDistanceFromAvgEdgeCases:
    """Edge cases: zero average."""

    def test_zero_average_always_passes(self) -> None:
        """A zero average makes percentage distance undefined; always pass."""
        assert check_min_distance_from_avg(5.0, 0.0, 5.0, reverse=False) is True
        assert check_min_distance_from_avg(-5.0, 0.0, 5.0, reverse=True) is True


class TestAsyncFetchServiceIntervalsEmptyRange:
    """A degenerate (empty) search range must not reach the interval pool.

    The pool raises on start >= end, which services translate into
    "price_data_unavailable" - a misleading API-outage signal. An empty range is
    simply "no intervals", so it is short-circuited to a successful empty result.
    """

    async def test_empty_range_returns_success_with_no_intervals(self) -> None:
        """start == end short-circuits to ([], True) without calling the pool."""
        pool = MagicMock()
        pool.get_intervals = AsyncMock()
        moment = datetime(2026, 4, 12, 0, 0, tzinfo=ZoneInfo("Europe/Berlin"))

        intervals, fetch_ok = await async_fetch_service_intervals(
            pool,
            api_client=MagicMock(),
            user_data={"homes": []},
            start_time=moment,
            end_time=moment,
            service_label="test",
        )

        assert intervals == []
        assert fetch_ok is True
        pool.get_intervals.assert_not_called()

    async def test_inverted_range_returns_success_with_no_intervals(self) -> None:
        """start > end is treated the same way as start == end."""
        pool = MagicMock()
        pool.get_intervals = AsyncMock()
        start = datetime(2026, 4, 12, 1, 0, tzinfo=ZoneInfo("Europe/Berlin"))

        intervals, fetch_ok = await async_fetch_service_intervals(
            pool,
            api_client=MagicMock(),
            user_data={"homes": []},
            start_time=start,
            end_time=start - timedelta(hours=1),
            service_label="test",
        )

        assert intervals == []
        assert fetch_ok is True
        pool.get_intervals.assert_not_called()
