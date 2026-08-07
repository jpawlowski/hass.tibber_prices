"""
Tests for range lookups in the interval pool that do not assume a grid.

The pool used to resolve a range by generating the timestamps it expected the range
to contain and looking each one up in the index. That only worked when the caller's
bounds happened to land on the interval grid, and failed silently otherwise: an
off-grid start produced timestamps matching no key, so the pool reported an empty
cache for a range it fully held. Services surfaced that as "no_data_in_range".

Coverage here pins the two properties that replaced the assumption:
1. Lookups select what is indexed, so bounds may sit anywhere.
2. A leading gap smaller than one interval is not reported as missing, because no
   fetch could ever fill it.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from custom_components.tibber_prices.interval_pool.fetcher import TibberPricesIntervalPoolFetcher
from custom_components.tibber_prices.interval_pool.index import TibberPricesIntervalPoolTimestampIndex
from custom_components.tibber_prices.interval_pool.manager import TibberPricesIntervalPool


@pytest.fixture
def pool() -> TibberPricesIntervalPool:
    """Create an interval pool holding one day of quarter-hourly intervals."""
    instance = TibberPricesIntervalPool(home_id="test_home_id", api=MagicMock())
    base = datetime(2026, 7, 27, 0, 0, tzinfo=UTC)
    intervals = [
        {
            "startsAt": (base + timedelta(minutes=15 * step)).isoformat(),
            "total": 0.20,
            "energy": 0.15,
            "tax": 0.05,
        }
        for step in range(96)
    ]
    instance._add_intervals(intervals, base.isoformat())  # noqa: SLF001
    return instance


class TestOffGridRangeLookup:
    """An off-grid boundary must not hide intervals the pool actually holds."""

    def test_off_grid_start_still_returns_intervals(self, pool: TibberPricesIntervalPool) -> None:
        """Regression for #190: a start with seconds and microseconds found nothing.

        14:47:00.167996 generated lookups at 14:47, 15:02, 15:17 ... none of which
        are indexed, so the pool returned an empty list for a fully cached day.
        """
        start = datetime(2026, 7, 27, 14, 47, 0, 167996, tzinfo=UTC)
        end = datetime(2026, 7, 27, 18, 0, tzinfo=UTC)

        result = pool._get_cached_intervals(start.isoformat(), end.isoformat())  # noqa: SLF001

        assert result, "off-grid start must not hide cached intervals"
        # Inclusive start: the first interval at or after 14:47 is 15:00
        assert result[0]["startsAt"].startswith("2026-07-27T15:00:00")
        assert result[-1]["startsAt"].startswith("2026-07-27T17:45:00")

    def test_off_grid_end_stops_at_last_interval_inside_range(self, pool: TibberPricesIntervalPool) -> None:
        """An off-grid end is exclusive on the interval start, as documented."""
        start = datetime(2026, 7, 27, 10, 0, tzinfo=UTC)
        end = datetime(2026, 7, 27, 14, 47, tzinfo=UTC)

        result = pool._get_cached_intervals(start.isoformat(), end.isoformat())  # noqa: SLF001

        assert result[0]["startsAt"].startswith("2026-07-27T10:00:00")
        assert result[-1]["startsAt"].startswith("2026-07-27T14:45:00")

    def test_aligned_range_is_exact(self, pool: TibberPricesIntervalPool) -> None:
        """An aligned range returns exactly the intervals it spans, in order."""
        start = datetime(2026, 7, 27, 8, 0, tzinfo=UTC)
        end = datetime(2026, 7, 27, 9, 0, tzinfo=UTC)

        result = pool._get_cached_intervals(start.isoformat(), end.isoformat())  # noqa: SLF001

        assert [interval["startsAt"][11:16] for interval in result] == ["08:00", "08:15", "08:30", "08:45"]

    def test_empty_range_returns_nothing(self, pool: TibberPricesIntervalPool) -> None:
        """A zero-width range holds no intervals."""
        moment = datetime(2026, 7, 27, 8, 0, tzinfo=UTC)

        assert pool._get_cached_intervals(moment.isoformat(), moment.isoformat()) == []  # noqa: SLF001


class TestIndexKeysInRange:
    """The index selects on its own keys, independent of interval length."""

    def test_selection_spans_a_resolution_change(self) -> None:
        """Hourly and quarter-hourly keys are both selected by one query.

        Generating expected timestamps needed to know where the 2025-10-01 switch
        from hourly to quarter-hourly fell; selecting indexed keys does not.
        """
        index = TibberPricesIntervalPoolTimestampIndex()
        hourly = ["2025-09-30T22:00:00+02:00", "2025-09-30T23:00:00+02:00"]
        quarter = ["2025-10-01T00:00:00+02:00", "2025-10-01T00:15:00+02:00"]
        for position, timestamp in enumerate(hourly + quarter):
            index.add({"startsAt": timestamp}, 0, position)

        keys = index.keys_in_range("2025-09-30T22:00:00+02:00", "2025-10-01T00:30:00+02:00")

        assert keys == [
            "2025-09-30T22:00:00",
            "2025-09-30T23:00:00",
            "2025-10-01T00:00:00",
            "2025-10-01T00:15:00",
        ]

    def test_selection_is_chronological_regardless_of_insertion_order(self) -> None:
        """Keys come back sorted even when added out of order."""
        index = TibberPricesIntervalPoolTimestampIndex()
        for position, timestamp in enumerate(["2026-07-27T09:00:00", "2026-07-27T08:00:00"]):
            index.add({"startsAt": timestamp}, 0, position)

        assert index.keys_in_range("2026-07-27T00:00:00", "2026-07-28T00:00:00") == [
            "2026-07-27T08:00:00",
            "2026-07-27T09:00:00",
        ]

    def test_bounds_are_inclusive_start_exclusive_end(self) -> None:
        """The range contract matches the pool's documented semantics."""
        index = TibberPricesIntervalPoolTimestampIndex()
        for position, timestamp in enumerate(["2026-07-27T08:00:00", "2026-07-27T09:00:00"]):
            index.add({"startsAt": timestamp}, 0, position)

        assert index.keys_in_range("2026-07-27T08:00:00", "2026-07-27T09:00:00") == ["2026-07-27T08:00:00"]


class TestLeadingGapDetection:
    """A gap shorter than one interval is unfillable and must not be reported."""

    def _fetcher(self) -> TibberPricesIntervalPoolFetcher:
        return TibberPricesIntervalPoolFetcher(
            api=MagicMock(),
            cache=MagicMock(),
            index=MagicMock(),
            home_id="test_home_id",
        )

    def test_sub_interval_leading_slack_is_not_a_gap(self) -> None:
        """An off-grid start sits partway into an interval, which is not missing data.

        Regression: this reported (14:47, 15:00) as missing on every call. The API
        cannot return an interval that starts in between, so the gap survived each
        fetch and the same range was requested again indefinitely.
        """
        cached = [{"startsAt": "2026-07-27T15:00:00+02:00"}]

        missing = self._fetcher().check_coverage(
            cached,
            "2026-07-27T14:47:00+02:00",
            "2026-07-27T15:15:00+02:00",
        )

        assert missing == []

    def test_whole_missing_interval_is_still_reported(self) -> None:
        """A genuine gap of one full interval must still trigger a fetch."""
        cached = [{"startsAt": "2026-07-27T15:00:00+02:00"}]

        missing = self._fetcher().check_coverage(
            cached,
            "2026-07-27T14:45:00+02:00",
            "2026-07-27T15:15:00+02:00",
        )

        assert missing == [("2026-07-27T14:45:00+02:00", "2026-07-27T15:00:00+02:00")]
