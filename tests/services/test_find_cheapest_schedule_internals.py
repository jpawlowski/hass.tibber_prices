"""Tests for pure internal helpers in find_cheapest_schedule.py."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from custom_components.tibber_prices.services.find_cheapest_schedule import _find_cheapest_window_in_pool


def _build_pool(minutes_and_prices: list[tuple[int, float]], base: datetime | None = None) -> list[dict]:
    """Build a pool of interval dicts from (minute_offset, price) tuples."""
    base = base or datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    return [
        {"startsAt": (base + timedelta(minutes=minute)).isoformat(), "total": price}
        for minute, price in minutes_and_prices
    ]


class TestFindCheapestWindowInPoolTemporalGap:
    """Regression coverage: a temporal gap must not hide the cheapest window.

    `_find_cheapest_window_in_pool` scans for contiguous available blocks. When
    a block-in-progress hits a time gap (e.g. because price-level filtering
    removed an interval from the middle of the range), the position where the
    gap was detected is itself a valid, untested candidate window start and
    must be retried — not skipped.
    """

    def test_cheapest_window_right_after_gap_is_found(self) -> None:
        """The cheapest 2-interval window sits right after a 30min time gap."""
        # Minutes: 0, 15, [gap - 30 missing], 45, 60, 75, 90
        # Cheapest contiguous pair by price sum is (45, 60) = 1 + 1 = 2.
        pool = _build_pool([(0, 10.0), (15, 10.0), (45, 1.0), (60, 1.0), (75, 10.0), (90, 10.0)])
        available = [True] * len(pool)

        result = _find_cheapest_window_in_pool(pool, 2, available)

        assert result is not None
        start, end = result
        assert (start, end) == (2, 4)
        chosen = pool[start:end]
        assert [iv["startsAt"] for iv in chosen] == [pool[2]["startsAt"], pool[3]["startsAt"]]
        assert sum(iv["total"] for iv in chosen) == 2.0

    def test_cheapest_window_immediately_before_gap_still_found(self) -> None:
        """A candidate window ending right before a gap must also still work."""
        # Minutes: 0, 15, 30 [gap], 60, 75
        # Cheapest contiguous pair is (0, 15) = 1 + 1 = 2, right before the gap.
        pool = _build_pool([(0, 1.0), (15, 1.0), (30, 10.0), (60, 10.0), (75, 10.0)])
        available = [True] * len(pool)

        result = _find_cheapest_window_in_pool(pool, 2, available)

        assert result == (0, 2)

    def test_multiple_gaps_all_candidate_starts_considered(self) -> None:
        """Multiple gaps in a row must not compound-skip valid starts."""
        # Minutes: 0, [gap], 30, [gap], 60, [gap], 90 — no 2 contiguous intervals
        # exist at all here, so no window should be found despite many gaps.
        pool = _build_pool([(0, 1.0), (30, 1.0), (60, 1.0), (90, 1.0)])
        available = [True] * len(pool)

        result = _find_cheapest_window_in_pool(pool, 2, available)

        assert result is None

    def test_unavailable_slot_is_still_correctly_skipped(self) -> None:
        """An unavailable (already-claimed) slot must still be skipped entirely."""
        pool = _build_pool([(0, 1.0), (15, 1.0), (30, 1.0), (45, 1.0)])
        # Claim index 1 (minute 15) as unavailable (e.g. assigned to another task).
        available = [True, False, True, True]

        result = _find_cheapest_window_in_pool(pool, 2, available)

        # Only (30, 45) is a valid contiguous available pair.
        assert result == (2, 4)
