"""Tests for find service response contracts: reason codes and schedule comparison details."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall

import pytest

from custom_components.tibber_prices.services import (
    find_cheapest_block as block_module,
    find_cheapest_hours as hours_module,
    find_cheapest_schedule as schedule_module,
)
from custom_components.tibber_prices.services.find_cheapest_block import (
    _determine_no_window_reason,
    handle_find_cheapest_block,
)
from custom_components.tibber_prices.services.find_cheapest_hours import (
    _determine_no_intervals_reason,
    handle_find_cheapest_hours,
)
from custom_components.tibber_prices.services.find_cheapest_schedule import (
    FIND_CHEAPEST_SCHEDULE_SERVICE_SCHEMA,
    _compute_task_price_comparison,
    _determine_schedule_reason,
)


def _make_intervals(prices: list[float], start: datetime | None = None) -> list[dict]:
    """Create quarter-hour intervals for tests."""
    base = start or datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    return [
        {
            "startsAt": (base + timedelta(minutes=15 * i)).isoformat(),
            "total": price,
            "level": "NORMAL",
        }
        for i, price in enumerate(prices)
    ]


class TestBlockNoResultReasons:
    """Reason classification for contiguous block service."""

    def test_reason_no_data(self) -> None:
        """Return no_data_in_range when no intervals exist."""
        reason = _determine_no_window_reason([], [], 4, level_filter_active=False)
        assert reason == "no_data_in_range"

    def test_reason_level_filter_eliminated_all(self) -> None:
        """Return level-filter reason when filters remove all intervals."""
        reason = _determine_no_window_reason(
            _make_intervals([10.0, 12.0]),
            [],
            4,
            level_filter_active=True,
        )
        assert reason == "no_intervals_matching_level_filter"

    def test_reason_not_enough_intervals_after_filter(self) -> None:
        """Return insufficient_intervals_after_filter for short filtered pool."""
        reason = _determine_no_window_reason(
            _make_intervals([10.0, 12.0, 13.0]),
            _make_intervals([10.0, 12.0]),
            4,
            level_filter_active=False,
        )
        assert reason == "insufficient_intervals_after_filter"


class TestHoursNoResultReasons:
    """Reason classification for cheapest/most-expensive hours service."""

    def test_reason_no_data(self) -> None:
        """Return no_data_in_range when interval pool is empty."""
        reason = _determine_no_intervals_reason([], [], 6, level_filter_active=False)
        assert reason == "no_data_in_range"

    def test_reason_level_filter_eliminated_all(self) -> None:
        """Return level-filter reason when all intervals are filtered out."""
        reason = _determine_no_intervals_reason(
            _make_intervals([10.0, 11.0]),
            [],
            4,
            level_filter_active=True,
        )
        assert reason == "no_intervals_matching_level_filter"

    def test_reason_not_enough_intervals_after_filter(self) -> None:
        """Return insufficient_intervals_after_filter when pool is too short."""
        reason = _determine_no_intervals_reason(
            _make_intervals([10.0, 11.0, 12.0]),
            _make_intervals([10.0, 11.0]),
            4,
            level_filter_active=False,
        )
        assert reason == "insufficient_intervals_after_filter"


class TestScheduleReasonAndComparison:
    """Schedule service reason codes and comparison details behavior."""

    def test_schedule_reason_no_data(self) -> None:
        """Return no_data_in_range when schedule has no source intervals."""
        reason = _determine_schedule_reason(
            all_tasks_scheduled=False,
            assignments_count=0,
            price_info=[],
            filtered_price_info=[],
            level_filter_active=False,
        )
        assert reason == "no_data_in_range"

    def test_schedule_reason_level_filter(self) -> None:
        """Return level-filter reason when filter removes all schedule candidates."""
        reason = _determine_schedule_reason(
            all_tasks_scheduled=False,
            assignments_count=0,
            price_info=_make_intervals([10.0, 20.0]),
            filtered_price_info=[],
            level_filter_active=True,
        )
        assert reason == "no_intervals_matching_level_filter"

    def test_schedule_reason_partial(self) -> None:
        """Return partial-schedule reason when some tasks remain unscheduled."""
        reason = _determine_schedule_reason(
            all_tasks_scheduled=False,
            assignments_count=1,
            price_info=_make_intervals([10.0, 20.0, 30.0]),
            filtered_price_info=_make_intervals([10.0, 20.0, 30.0]),
            level_filter_active=False,
        )
        assert reason == "insufficient_contiguous_window_for_some_tasks"

    def test_schedule_schema_accepts_include_comparison_details(self) -> None:
        """Schedule schema should accept include_comparison_details flag."""
        result = cast(
            "dict[str, Any]",
            FIND_CHEAPEST_SCHEDULE_SERVICE_SCHEMA(
                {
                    "tasks": [{"name": "dishwasher", "duration": timedelta(hours=2)}],
                    "include_comparison_details": True,
                }
            ),
        )
        assert result["include_comparison_details"] is True

    def test_task_comparison_includes_details(self) -> None:
        """Task comparison helper should emit detail fields when enabled."""
        full_intervals = _make_intervals([5.0, 10.0, 50.0, 60.0])
        task_intervals = full_intervals[:2]

        comparison = _compute_task_price_comparison(
            task_intervals,
            full_intervals,
            1,
            include_details=True,
        )

        assert comparison is not None
        assert "comparison_price_mean" in comparison
        assert "comparison_price_min" in comparison
        assert "comparison_price_max" in comparison
        assert "comparison_window_start" in comparison
        assert "comparison_window_end" in comparison


class _FakePool:
    """Minimal async interval pool for service handler tests."""

    def __init__(self, intervals: list[dict]) -> None:
        """Store static interval list returned by get_intervals."""
        self._intervals = intervals

    async def get_intervals(self, **_kwargs: object) -> tuple[list[dict], bool]:
        """Return predefined intervals and no API-call marker."""
        return self._intervals, False


def _build_fake_entry_and_coordinator(intervals: list[dict]) -> tuple[SimpleNamespace, SimpleNamespace, dict]:
    """Build a minimal entry/coordinator/data tuple used by service handlers."""
    pool = _FakePool(intervals)
    entry = SimpleNamespace(
        data={"home_id": "home_1", "currency": "EUR"},
        runtime_data=SimpleNamespace(interval_pool=pool),
    )
    coordinator = SimpleNamespace(
        api=object(),
        _cached_user_data={"viewer": {"homes": [{"id": "home_1", "timeZone": "UTC"}]}},
    )
    data = {"priceInfo": intervals}
    return entry, coordinator, data


@pytest.mark.asyncio
async def test_block_handler_returns_level_filter_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    """Block handler should return reason when level filter eliminates all intervals."""
    intervals = _make_intervals([10.0, 11.0, 12.0, 13.0])
    fake_tuple = _build_fake_entry_and_coordinator(intervals)

    monkeypatch.setattr(block_module, "get_entry_and_data", lambda _hass, _entry_id: fake_tuple)
    monkeypatch.setattr(block_module, "resolve_home_timezone", lambda _coord, _home_id: "UTC")
    monkeypatch.setattr(
        block_module,
        "resolve_search_range",
        lambda _call_data, _now, _home_tz: (
            datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
            datetime(2026, 1, 1, 2, 0, tzinfo=UTC),
        ),
    )

    call = SimpleNamespace(
        hass=object(),
        data={
            "duration": timedelta(hours=1),
            "max_price_level": "very_cheap",
            "use_base_unit": True,
        },
    )
    response = cast("dict[str, Any]", await handle_find_cheapest_block(cast("ServiceCall", call)))

    assert response["window_found"] is False
    assert response["reason"] == "no_intervals_matching_level_filter"


@pytest.mark.asyncio
async def test_hours_handler_returns_insufficient_intervals_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hours handler should return insufficient_intervals_after_filter when pool is too short."""
    intervals = _make_intervals([10.0, 11.0, 12.0])  # 3 intervals only
    fake_tuple = _build_fake_entry_and_coordinator(intervals)

    monkeypatch.setattr(hours_module, "get_entry_and_data", lambda _hass, _entry_id: fake_tuple)
    monkeypatch.setattr(hours_module, "resolve_home_timezone", lambda _coord, _home_id: "UTC")
    monkeypatch.setattr(
        hours_module,
        "resolve_search_range",
        lambda _call_data, _now, _home_tz: (
            datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
            datetime(2026, 1, 1, 2, 0, tzinfo=UTC),
        ),
    )

    call = SimpleNamespace(
        hass=object(),
        data={
            "duration": timedelta(hours=1),  # needs 4 intervals
            "use_base_unit": True,
        },
    )
    response = cast("dict[str, Any]", await handle_find_cheapest_hours(cast("ServiceCall", call)))

    assert response["intervals_found"] is False
    assert response["reason"] == "insufficient_intervals_after_filter"


@pytest.mark.asyncio
async def test_schedule_handler_adds_per_task_comparison_details(monkeypatch: pytest.MonkeyPatch) -> None:
    """Schedule handler should include per-task comparison details when requested."""
    intervals = _make_intervals([5.0, 6.0, 50.0, 60.0])
    fake_tuple = _build_fake_entry_and_coordinator(intervals)

    monkeypatch.setattr(schedule_module, "get_entry_and_data", lambda _hass, _entry_id: fake_tuple)
    monkeypatch.setattr(schedule_module, "resolve_home_timezone", lambda _coord, _home_id: "UTC")
    monkeypatch.setattr(
        schedule_module,
        "resolve_search_range",
        lambda _call_data, _now, _home_tz: (
            datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
            datetime(2026, 1, 1, 2, 0, tzinfo=UTC),
        ),
    )

    call = SimpleNamespace(
        hass=object(),
        data={
            "tasks": [{"name": "dishwasher", "duration": timedelta(minutes=30)}],
            "include_comparison_details": True,
            "use_base_unit": True,
        },
    )
    response = cast("dict[str, Any]", await schedule_module.handle_find_cheapest_schedule(cast("ServiceCall", call)))

    assert response["all_tasks_scheduled"] is True
    assert response["reason"] is None
    tasks = cast("list[dict[str, Any]]", response["tasks"])
    assert len(tasks) == 1
    comparison = cast("dict[str, Any] | None", tasks[0]["price_comparison"])
    assert comparison is not None
    assert "comparison_price_min" in comparison
    assert "comparison_price_max" in comparison
    assert "comparison_window_end" in comparison
