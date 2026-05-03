"""Tests for sequential scheduling feature in find_cheapest_schedule."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast

from custom_components.tibber_prices.services.find_cheapest_schedule import (
    FIND_CHEAPEST_SCHEDULE_SERVICE_SCHEMA,
    _attempt_schedule,
)


def _make_intervals(
    prices: list[float],
    start: datetime | None = None,
    *,
    level: str = "NORMAL",
) -> list[dict[str, Any]]:
    """Create contiguous quarter-hour intervals for tests."""
    base = start or datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    return [
        {
            "startsAt": (base + timedelta(minutes=15 * i)).isoformat(),
            "total": price,
            "level": level,
        }
        for i, price in enumerate(prices)
    ]


def _make_tasks(*specs: tuple[str, int]) -> list[dict[str, Any]]:
    """Create task dicts from (name, duration_intervals) tuples."""
    return [
        {
            "name": name,
            "duration_minutes_requested": dur * 15,
            "duration_minutes": dur * 15,
            "duration_intervals": dur,
            "power_profile": None,
        }
        for name, dur in specs
    ]


class TestSequentialSchema:
    """Schema accepts sequential parameter."""

    def test_schema_accepts_sequential_true(self) -> None:
        """Schema should accept sequential: true."""
        result = cast(
            "dict[str, Any]",
            FIND_CHEAPEST_SCHEDULE_SERVICE_SCHEMA(
                {
                    "tasks": [{"name": "dishwasher", "duration": timedelta(hours=1)}],
                    "sequential": True,
                }
            ),
        )
        assert result["sequential"] is True

    def test_schema_defaults_sequential_false(self) -> None:
        """Sequential should default to false when omitted."""
        result = cast(
            "dict[str, Any]",
            FIND_CHEAPEST_SCHEDULE_SERVICE_SCHEMA(
                {
                    "tasks": [{"name": "dishwasher", "duration": timedelta(hours=1)}],
                }
            ),
        )
        assert result["sequential"] is False

    def test_schema_defaults_include_current_interval_true(self) -> None:
        """Schedule schema should expose include_current_interval like other actions."""
        result = cast(
            "dict[str, Any]",
            FIND_CHEAPEST_SCHEDULE_SERVICE_SCHEMA(
                {
                    "tasks": [{"name": "dishwasher", "duration": timedelta(hours=1)}],
                }
            ),
        )
        assert result["include_current_interval"] is True


class TestSequentialOrdering:
    """Sequential mode preserves declaration order and chains search windows."""

    def test_non_sequential_sorts_by_duration(self) -> None:
        """Default (non-sequential) mode sorts tasks longest-first."""
        # 16 intervals = 4 hours of data
        # Prices: first 8 cheap, last 8 expensive
        prices = [5.0] * 8 + [20.0] * 8
        pool = _make_intervals(prices)

        # Task A is short (2 intervals), Task B is long (4 intervals)
        tasks = _make_tasks(("short_a", 2), ("long_b", 4))

        assignments, unscheduled, _ = _attempt_schedule(
            pool,
            max_price_level=None,
            min_price_level=None,
            tasks=tasks,
            gap_intervals=0,
            smooth_outliers=False,
            sequential=False,
        )

        assert not unscheduled
        assert len(assignments) == 2
        # Greedy longest-first: long_b gets placed first (cheapest window)
        # Assignments are returned in placement order (longest first)
        assert assignments[0]["name"] == "long_b"
        assert assignments[1]["name"] == "short_a"

    def test_sequential_preserves_declaration_order(self) -> None:
        """Sequential mode places tasks in the order they appear."""
        # 16 intervals, all same price
        prices = [10.0] * 16
        pool = _make_intervals(prices)

        # Declare short task first, long task second
        tasks = _make_tasks(("short_a", 2), ("long_b", 4))

        assignments, unscheduled, _ = _attempt_schedule(
            pool,
            max_price_level=None,
            min_price_level=None,
            tasks=tasks,
            gap_intervals=0,
            smooth_outliers=False,
            sequential=True,
        )

        assert not unscheduled
        assert len(assignments) == 2
        # Sequential: short_a placed first, long_b after
        assert assignments[0]["name"] == "short_a"
        assert assignments[1]["name"] == "long_b"

    def test_sequential_chains_search_windows(self) -> None:
        """Each sequential task starts after the previous task's end."""
        # 12 intervals: first 4 are cheap, next 4 medium, last 4 expensive
        prices = [5.0] * 4 + [10.0] * 4 + [20.0] * 4
        pool = _make_intervals(prices)

        # Two tasks of 3 intervals each
        tasks = _make_tasks(("task_a", 3), ("task_b", 3))

        assignments, unscheduled, _ = _attempt_schedule(
            pool,
            max_price_level=None,
            min_price_level=None,
            tasks=tasks,
            gap_intervals=0,
            smooth_outliers=False,
            sequential=True,
        )

        assert not unscheduled
        assert len(assignments) == 2

        # Task A should get the cheapest window (intervals 0-2)
        a_end_last = datetime.fromisoformat(assignments[0]["intervals"][-1]["startsAt"])

        # Task B must start at or after task A's end
        b_start = datetime.fromisoformat(assignments[1]["intervals"][0]["startsAt"])
        assert b_start >= a_end_last + timedelta(minutes=15)

    def test_sequential_respects_gap(self) -> None:
        """Sequential mode enforces gap between tasks."""
        # 16 intervals of uniform price
        prices = [10.0] * 16
        pool = _make_intervals(prices)

        # 2 tasks of 3 intervals each, with 2-interval (30 min) gap
        tasks = _make_tasks(("washer", 3), ("dryer", 3))

        assignments, unscheduled, _ = _attempt_schedule(
            pool,
            max_price_level=None,
            min_price_level=None,
            tasks=tasks,
            gap_intervals=2,
            smooth_outliers=False,
            sequential=True,
        )

        assert not unscheduled
        assert len(assignments) == 2

        washer_end = datetime.fromisoformat(assignments[0]["intervals"][-1]["startsAt"]) + timedelta(minutes=15)
        dryer_start = datetime.fromisoformat(assignments[1]["intervals"][0]["startsAt"])

        # Gap should be at least 30 minutes (2 intervals × 15 min)
        gap = dryer_start - washer_end
        assert gap >= timedelta(minutes=30)

    def test_sequential_chain_breaks_on_failure(self) -> None:
        """If a sequential task can't be placed, all later tasks are unscheduled."""
        # Only 6 intervals — not enough for 3 tasks of 3 intervals each
        prices = [10.0] * 6
        pool = _make_intervals(prices)

        tasks = _make_tasks(("task_a", 3), ("task_b", 3), ("task_c", 3))

        assignments, unscheduled, _ = _attempt_schedule(
            pool,
            max_price_level=None,
            min_price_level=None,
            tasks=tasks,
            gap_intervals=0,
            smooth_outliers=False,
            sequential=True,
        )

        # Task A and B fit (6 intervals total), task C doesn't
        assert len(assignments) == 2
        assert assignments[0]["name"] == "task_a"
        assert assignments[1]["name"] == "task_b"
        assert unscheduled == ["task_c"]

    def test_sequential_all_fail_after_first_failure(self) -> None:
        """If the first task fails in sequential mode, all are unscheduled."""
        # 2 intervals — not enough for any 3-interval task
        prices = [10.0] * 2
        pool = _make_intervals(prices)

        tasks = _make_tasks(("task_a", 3), ("task_b", 2))

        assignments, unscheduled, _ = _attempt_schedule(
            pool,
            max_price_level=None,
            min_price_level=None,
            tasks=tasks,
            gap_intervals=0,
            smooth_outliers=False,
            sequential=True,
        )

        # Task A can't fit (needs 3, only 2 available)
        # Task B should also be unscheduled because the chain is broken
        assert len(assignments) == 0
        assert unscheduled == ["task_a", "task_b"]

    def test_sequential_optimizes_within_window(self) -> None:
        """Sequential still finds cheapest window within each task's available range."""
        # 12 intervals: pattern cheap-expensive-cheap-expensive...
        # First 6 for task A, second 6 for task B
        # Within each half, there's a cheaper sub-window
        prices = [20.0, 5.0, 5.0, 20.0, 20.0, 20.0, 20.0, 20.0, 5.0, 5.0, 20.0, 20.0]
        pool = _make_intervals(prices)

        tasks = _make_tasks(("task_a", 2), ("task_b", 2))

        assignments, unscheduled, _ = _attempt_schedule(
            pool,
            max_price_level=None,
            min_price_level=None,
            tasks=tasks,
            gap_intervals=0,
            smooth_outliers=False,
            sequential=True,
        )

        assert not unscheduled
        assert len(assignments) == 2

        # Task A should pick the cheapest 2-interval window: indices 1-2 (price 5.0 each)
        a_prices = [iv["total"] for iv in assignments[0]["intervals"]]
        assert a_prices == [5.0, 5.0]

        # Task B searches from index 2 onward, cheapest is indices 8-9 (price 5.0 each)
        b_prices = [iv["total"] for iv in assignments[1]["intervals"]]
        assert b_prices == [5.0, 5.0]

    def test_sequential_single_task_same_as_non_sequential(self) -> None:
        """With a single task, sequential and non-sequential produce the same result."""
        prices = [20.0, 5.0, 5.0, 20.0, 10.0, 10.0]
        pool = _make_intervals(prices)
        tasks = _make_tasks(("only_task", 2))

        a_seq, u_seq, _ = _attempt_schedule(
            pool,
            max_price_level=None,
            min_price_level=None,
            tasks=tasks,
            gap_intervals=0,
            smooth_outliers=False,
            sequential=True,
        )
        a_non, u_non, _ = _attempt_schedule(
            pool,
            max_price_level=None,
            min_price_level=None,
            tasks=tasks,
            gap_intervals=0,
            smooth_outliers=False,
            sequential=False,
        )

        assert not u_seq
        assert not u_non
        assert len(a_seq) == len(a_non) == 1
        assert a_seq[0]["intervals"] == a_non[0]["intervals"]


class TestSequentialThreeTasks:
    """Sequential scheduling with three tasks (washer → dryer → fold reminder)."""

    def test_three_tasks_chained(self) -> None:
        """Three sequential tasks are placed in order with no overlap."""
        # 24 intervals (6 hours) with varying prices
        prices = [15.0, 10.0, 5.0, 5.0, 10.0, 15.0, 20.0, 25.0] * 3
        pool = _make_intervals(prices)

        tasks = _make_tasks(("washer", 4), ("dryer", 3), ("fold", 1))

        assignments, unscheduled, _ = _attempt_schedule(
            pool,
            max_price_level=None,
            min_price_level=None,
            tasks=tasks,
            gap_intervals=0,
            smooth_outliers=False,
            sequential=True,
        )

        assert not unscheduled
        assert len(assignments) == 3
        assert assignments[0]["name"] == "washer"
        assert assignments[1]["name"] == "dryer"
        assert assignments[2]["name"] == "fold"

        # Verify no overlap: each task starts after previous ends
        for i in range(1, len(assignments)):
            prev_end = datetime.fromisoformat(assignments[i - 1]["intervals"][-1]["startsAt"]) + timedelta(minutes=15)
            curr_start = datetime.fromisoformat(assignments[i]["intervals"][0]["startsAt"])
            assert curr_start >= prev_end

    def test_three_tasks_with_gap(self) -> None:
        """Three sequential tasks respect gap between each pair."""
        prices = [10.0] * 24
        pool = _make_intervals(prices)

        tasks = _make_tasks(("washer", 4), ("dryer", 3), ("fold", 1))

        assignments, unscheduled, _ = _attempt_schedule(
            pool,
            max_price_level=None,
            min_price_level=None,
            tasks=tasks,
            gap_intervals=1,  # 15 min gap
            smooth_outliers=False,
            sequential=True,
        )

        assert not unscheduled
        assert len(assignments) == 3

        # Verify gaps between each pair
        for i in range(1, len(assignments)):
            prev_end = datetime.fromisoformat(assignments[i - 1]["intervals"][-1]["startsAt"]) + timedelta(minutes=15)
            curr_start = datetime.fromisoformat(assignments[i]["intervals"][0]["startsAt"])
            gap = curr_start - prev_end
            assert gap >= timedelta(minutes=15)
