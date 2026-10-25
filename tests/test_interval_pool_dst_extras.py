"""Regression for #233: DST fall-back extras must not grow with every re-add."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

from custom_components.tibber_prices.interval_pool.fetcher import TibberPricesIntervalPoolFetcher
from custom_components.tibber_prices.interval_pool.manager import TibberPricesIntervalPool

_TZ = ZoneInfo("Europe/Berlin")


def _fall_back_intervals() -> list[dict]:
    """Return 02:00-02:45 twice: first CEST (+02:00), then CET (+01:00)."""
    result = []
    for fold in (0, 1):
        for minute in (0, 15, 30, 45):
            start = datetime(2026, 10, 25, 2, minute, tzinfo=_TZ, fold=fold)
            result.append({"startsAt": start.isoformat(), "total": 0.2, "energy": 0.15, "tax": 0.05})
    return result


def test_re_adding_fall_back_intervals_keeps_one_extra_per_timestamp() -> None:
    """Every re-fetch used to append another CET copy; reads returned them all."""
    pool = TibberPricesIntervalPool(home_id="test_home_id", api=MagicMock())
    intervals = _fall_back_intervals()

    for run in range(5):
        pool._add_intervals(intervals, f"2026-10-25T10:0{run}:00+01:00")  # noqa: SLF001

    result = pool._get_cached_intervals("2026-10-25T02:00:00", "2026-10-25T03:00:00")  # noqa: SLF001

    assert len(result) == 8
    assert all(len(extras) == 1 for extras in pool._dst_extras.values())  # noqa: SLF001


def _fetcher() -> TibberPricesIntervalPoolFetcher:
    return TibberPricesIntervalPoolFetcher(api=MagicMock(), cache=MagicMock(), index=MagicMock(), home_id="h")


def _day(date: tuple[int, int, int]) -> list[dict]:
    """Return a full local day of quarter-hours in Europe/Berlin, as the API delivers it (absolute UTC steps)."""
    start = datetime(*date, tzinfo=_TZ)
    end = datetime(*date, tzinfo=_TZ) + timedelta(days=1)
    start_utc = start.astimezone(UTC)
    end_utc = end.astimezone(UTC)
    result = []
    while start_utc < end_utc:
        local = start_utc.astimezone(_TZ)
        result.append({"startsAt": local.isoformat(), "total": 0.2})
        start_utc += timedelta(minutes=15)
    return result


def test_check_coverage_reports_no_gap_on_fall_back_day() -> None:
    """02:xx exists twice (+02:00 and +01:00); sorting by string put CET before CEST and faked gaps."""
    intervals = _day((2026, 10, 25))
    assert len(intervals) == 100

    fetcher = _fetcher()
    missing = fetcher.check_coverage(intervals, "2026-10-25T00:00:00+02:00", "2026-10-26T00:00:00+01:00")

    assert missing == []


def test_check_coverage_reports_no_gap_on_spring_forward_day() -> None:
    """02:xx does not exist on the clock-forward day; the 15-minute UTC step must not read as a gap."""
    intervals = _day((2026, 3, 29))
    assert len(intervals) == 92

    fetcher = _fetcher()
    missing = fetcher.check_coverage(intervals, "2026-03-29T00:00:00+01:00", "2026-03-30T00:00:00+02:00")

    assert missing == []


def test_re_fetched_extra_carries_the_latest_price() -> None:
    """A revised price for the CET copy replaces the stored one instead of being dropped."""
    pool = TibberPricesIntervalPool(home_id="test_home_id", api=MagicMock())
    intervals = _fall_back_intervals()
    pool._add_intervals(intervals, "2026-10-25T10:00:00+01:00")  # noqa: SLF001

    revised = [{**interval, "total": 0.9} for interval in intervals]
    pool._add_intervals(revised, "2026-10-25T10:15:00+01:00")  # noqa: SLF001

    extras = [extra for entries in pool._dst_extras.values() for extra in entries]  # noqa: SLF001
    assert len(extras) == 4
    assert all(extra["total"] == 0.9 for extra in extras)


def _restore(extras: dict) -> TibberPricesIntervalPool:
    pool = TibberPricesIntervalPool(home_id="test_home_id", api=MagicMock())
    pool._add_intervals(_fall_back_intervals(), "2026-10-25T10:00:00+01:00")  # noqa: SLF001
    data = pool.to_dict()
    data["dst_extras"] = extras
    restored = TibberPricesIntervalPool.from_dict(data, api=MagicMock())
    assert restored is not None
    return restored


def test_restore_shrinks_a_bloated_stored_pool_to_one_extra_per_timestamp() -> None:
    """Pools stored by affected versions held hundreds of copies per key."""
    cet = _fall_back_intervals()[4]  # 02:00+01:00
    key = cet["startsAt"][:19]

    restored = _restore({key: [dict(cet, total=0.1 * n) for n in range(1, 400)]})

    assert len(restored._dst_extras[key]) == 1  # noqa: SLF001
    assert restored._dst_extras[key][0]["total"] == 0.1 * 399  # noqa: SLF001 - the latest copy wins


def test_restore_drops_extras_that_repeat_the_indexed_interval_or_cannot_be_read() -> None:
    """An extra equal to the primary would be returned twice; a malformed one must not break the restore."""
    intervals = _fall_back_intervals()
    cest, cet = intervals[0], intervals[4]
    key = cest["startsAt"][:19]

    restored = _restore({key: [dict(cest), {"total": 1.0}, {"startsAt": "garbage"}, dict(cet)]})

    assert [extra["startsAt"] for extra in restored._dst_extras[key]] == [cet["startsAt"]]  # noqa: SLF001


def test_check_coverage_reads_a_naive_bound_as_utc() -> None:
    """Naive bounds (as in the docstring example) must not raise against aware startsAt values."""
    start = datetime(2026, 11, 13, 0, 0, tzinfo=UTC)
    intervals = [{"startsAt": (start + timedelta(minutes=15 * n)).isoformat()} for n in range(8)]

    missing = _fetcher().check_coverage(intervals, "2026-11-13T00:00:00", "2026-11-13T02:00:00")

    assert missing == []
