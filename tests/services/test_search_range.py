"""
Tests for resolve_search_range helper and negative offset support.

Verifies that services can search into the past using:
- Negative search_start_day_offset / search_end_day_offset
- Negative search_start_offset_minutes / search_end_offset_minutes
- Explicit past search_start / search_end datetimes

Also validates schema boundaries for all 4 services.
"""

from __future__ import annotations

from datetime import datetime, time as dt_time, timedelta
from typing import Any, cast
from zoneinfo import ZoneInfo

import pytest
import voluptuous as vol

from custom_components.tibber_prices.services.find_cheapest_block import _COMMON_BLOCK_SCHEMA
from custom_components.tibber_prices.services.find_cheapest_hours import _COMMON_HOURS_SCHEMA
from custom_components.tibber_prices.services.helpers import (
    apply_must_finish_by,
    ceil_to_quarter_hour,
    resolve_search_range,
)
from homeassistant.exceptions import ServiceValidationError

BERLIN = ZoneInfo("Europe/Berlin")


# =============================================================================
# resolve_search_range: Negative day offsets
# =============================================================================


class TestResolveSearchRangeNegativeDayOffset:
    """Test that negative day offsets correctly resolve to past dates."""

    def test_negative_start_day_offset(self) -> None:
        """Start yesterday at 06:00."""
        now = datetime(2026, 4, 11, 14, 30, tzinfo=BERLIN)
        call_data = {
            "search_start_time": dt_time(6, 0, 0),
            "search_start_day_offset": -1,
        }
        start, _end = resolve_search_range(call_data, now, BERLIN)
        # Should be yesterday 06:00
        assert start.day == 10
        assert start.hour == 6
        assert start.minute == 0

    def test_negative_both_day_offsets(self) -> None:
        """Full day in the past: yesterday 00:00 to yesterday 23:59."""
        now = datetime(2026, 4, 11, 14, 30, tzinfo=BERLIN)
        call_data = {
            "search_start_time": dt_time(0, 0, 0),
            "search_start_day_offset": -1,
            "search_end_time": dt_time(23, 59, 0),
            "search_end_day_offset": -1,
        }
        start, end = resolve_search_range(call_data, now, BERLIN)
        assert start.day == 10
        assert start.hour == 0
        # 23:59 ceils onto the grid; the exclusive end still covers exactly the
        # 23:45 interval of the 10th and nothing of the 11th.
        assert end == datetime(2026, 4, 11, 0, 0, tzinfo=BERLIN)

    def test_negative_7_day_offset(self) -> None:
        """Start 7 days ago."""
        now = datetime(2026, 4, 11, 14, 30, tzinfo=BERLIN)
        call_data = {
            "search_start_time": dt_time(0, 0, 0),
            "search_start_day_offset": -7,
            "search_end_time": dt_time(23, 59, 0),
            "search_end_day_offset": -7,
        }
        start, end = resolve_search_range(call_data, now, BERLIN)
        assert start.day == 4
        # Exclusive end ceiled onto midnight, still covering only the 4th
        assert end == datetime(2026, 4, 5, 0, 0, tzinfo=BERLIN)

    def test_cross_day_range_past_to_today(self) -> None:
        """Start yesterday, end today."""
        now = datetime(2026, 4, 11, 14, 30, tzinfo=BERLIN)
        call_data = {
            "search_start_time": dt_time(18, 0, 0),
            "search_start_day_offset": -1,
            "search_end_time": dt_time(6, 0, 0),
            "search_end_day_offset": 0,
        }
        start, end = resolve_search_range(call_data, now, BERLIN)
        assert start.day == 10
        assert start.hour == 18
        assert end.day == 11
        assert end.hour == 6


# =============================================================================
# resolve_search_range: Negative offset minutes
# =============================================================================


class TestResolveSearchRangeNegativeOffsetMinutes:
    """Test that negative offset minutes correctly resolve to past times."""

    def test_negative_start_offset(self) -> None:
        """Start 2 hours ago."""
        now = datetime(2026, 4, 11, 14, 30, tzinfo=BERLIN)
        call_data = {
            "search_start_offset_minutes": -120,
            "include_current_interval": True,
        }
        start, _end = resolve_search_range(call_data, now, BERLIN)
        # -120 min from 14:30 = 12:30, floored to 12:30
        assert start.hour == 12
        assert start.minute == 30

    def test_negative_start_offset_floors_to_quarter(self) -> None:
        """Negative offset gets floored to quarter-hour boundary."""
        now = datetime(2026, 4, 11, 14, 37, tzinfo=BERLIN)
        call_data = {
            "search_start_offset_minutes": -60,
            "include_current_interval": True,
        }
        start, _end = resolve_search_range(call_data, now, BERLIN)
        # -60 min from 14:37 = 13:37, floored to 13:30
        assert start.hour == 13
        assert start.minute == 30

    def test_negative_end_offset(self) -> None:
        """End 1 hour ago (fully historical range)."""
        now = datetime(2026, 4, 11, 14, 30, tzinfo=BERLIN)
        call_data = {
            "search_start_offset_minutes": -180,
            "search_end_offset_minutes": -60,
            "include_current_interval": True,
        }
        start, end = resolve_search_range(call_data, now, BERLIN)
        # Start: -180 min → 11:30, End: -60 min → 13:30
        assert start.hour == 11
        assert start.minute == 30
        assert end.hour == 13
        assert end.minute == 30

    def test_large_negative_offset_crosses_day(self) -> None:
        """Large negative offset crosses day boundary."""
        now = datetime(2026, 4, 11, 2, 0, tzinfo=BERLIN)
        call_data = {
            "search_start_offset_minutes": -180,
            "include_current_interval": True,
        }
        start, _end = resolve_search_range(call_data, now, BERLIN)
        # -180 min from 02:00 = 23:00 yesterday
        assert start.day == 10
        assert start.hour == 23

    def test_search_scope_excludes_current_interval_when_disabled(self) -> None:
        """Relative search scopes ceil to next quarter boundary when include_current_interval=False."""
        now = datetime(2026, 4, 11, 14, 37, tzinfo=BERLIN)
        call_data = {
            "search_scope": "next_24h",
            "include_current_interval": False,
        }
        start, end = resolve_search_range(call_data, now, BERLIN)
        # 14:37 is not on a quarter boundary → should ceil to 14:45
        assert start.hour == 14
        assert start.minute == 45
        assert start.second == 0
        # The rolling horizon is ceiled onto the grid (same intervals as before)
        assert end == ceil_to_quarter_hour(now + timedelta(hours=24))

    def test_search_scope_includes_current_interval_when_enabled(self) -> None:
        """Relative search scopes include the current quarter when enabled."""
        now = datetime(2026, 4, 11, 14, 37, tzinfo=BERLIN)
        call_data = {
            "search_scope": "next_24h",
            "include_current_interval": True,
        }
        start, end = resolve_search_range(call_data, now, BERLIN)
        assert start.hour == 14
        assert start.minute == 30
        assert end == ceil_to_quarter_hour(now + timedelta(hours=24))

    def test_exclude_current_interval_with_sub_second_now(self) -> None:
        """Regression: microseconds in now caused no intervals to be returned.

        When include_current_interval=False and now has sub-second precision
        (e.g. 14:47:00.167996), the search_start must be ceiled to the next
        quarter boundary (15:00) so it aligns with actual interval timestamps
        in the pool index. Previously, raw now was used, which matched no
        cached interval and returned no data.
        """
        # Reproduce the exact scenario from the bug report: 14:47:00.167996+02:00
        now = datetime(2026, 7, 27, 14, 47, 0, 167996, tzinfo=ZoneInfo("Europe/Berlin"))
        call_data = {
            "search_scope": "next_24h",
            "include_current_interval": False,
        }
        start, _end = resolve_search_range(call_data, now, ZoneInfo("Europe/Berlin"))
        # 14:47:00.167996 → floor → 14:45 + 15min → 15:00
        assert start.hour == 15
        assert start.minute == 0
        assert start.second == 0
        assert start.microsecond == 0

    def test_exclude_current_interval_already_on_boundary(self) -> None:
        """When now is exactly on a quarter boundary and include_current_interval=False,
        the start is advanced to the NEXT boundary (the interval that hasn't started yet).
        """
        # 14:45:00 exactly → the 14:45 interval is currently in progress
        # → exclude it → ceil to 15:00
        now = datetime(2026, 4, 11, 14, 45, 0, tzinfo=BERLIN)
        call_data = {
            "search_scope": "next_24h",
            "include_current_interval": False,
        }
        start, _end = resolve_search_range(call_data, now, BERLIN)
        # 14:45:00 is exactly on a boundary → but the 14:45 interval is "current"
        # The correct behaviour: include_current=False should start at 15:00
        assert start.hour == 15
        assert start.minute == 0

    def test_exclude_current_default_no_scope_ceils_to_next_quarter(self) -> None:
        """Default path (no scope) with include_current_interval=False also ceils."""
        now = datetime(2026, 4, 11, 14, 47, 30, tzinfo=BERLIN)
        call_data = {"include_current_interval": False}
        start, _end = resolve_search_range(call_data, now, BERLIN)
        assert start.hour == 15
        assert start.minute == 0
        assert start.second == 0

    def test_exclude_current_offset_minutes_ceils_to_next_quarter(self) -> None:
        """search_start_offset_minutes with include_current_interval=False also aligns."""
        now = datetime(2026, 4, 11, 14, 47, 30, tzinfo=BERLIN)
        call_data = {
            "search_start_offset_minutes": 20,
            "include_current_interval": False,
        }
        start, _end = resolve_search_range(call_data, now, BERLIN)
        # 14:47:30 + 20min = 15:07:30 → floor 15:00 → +15min → 15:15
        assert start.hour == 15
        assert start.minute == 15
        assert start.second == 0

    def test_remaining_today_in_last_interval_yields_empty_range(self) -> None:
        """During the final interval of the day, remaining_today has nothing left.

        Excluding the current interval advances the start onto tomorrow's midnight
        boundary, which equals the scope's end. The resulting empty range must be
        returned as-is (services report it as "no data"), not raise.
        """
        now = datetime(2026, 4, 11, 23, 50, tzinfo=BERLIN)
        call_data = {
            "search_scope": "remaining_today",
            "include_current_interval": False,
        }
        start, end = resolve_search_range(call_data, now, BERLIN)
        assert start == end
        assert start == datetime(2026, 4, 12, 0, 0, tzinfo=BERLIN)


# =============================================================================
# Quarter-hour grid alignment of explicitly requested boundaries
# =============================================================================


class TestExplicitBoundaryGridAlignment:
    """Explicitly requested start/end datetimes must land on the interval grid.

    The pool indexes intervals by :00/:15/:30/:45 keys and looks each stepped
    timestamp up verbatim, so an off-grid boundary silently matches nothing.
    """

    def test_explicit_start_floors_onto_grid(self) -> None:
        """An off-grid search_start includes the interval it falls inside."""
        now = datetime(2026, 4, 11, 8, 0, tzinfo=BERLIN)
        call_data = {
            "search_start": datetime(2026, 4, 11, 14, 47, tzinfo=BERLIN),
            "search_end": datetime(2026, 4, 11, 20, 0, tzinfo=BERLIN),
        }
        start, _end = resolve_search_range(call_data, now, BERLIN)
        assert start == datetime(2026, 4, 11, 14, 45, tzinfo=BERLIN)

    def test_explicit_start_ceils_when_current_excluded(self) -> None:
        """include_current_interval=False skips the partially elapsed interval."""
        now = datetime(2026, 4, 11, 8, 0, tzinfo=BERLIN)
        call_data = {
            "search_start": datetime(2026, 4, 11, 14, 47, tzinfo=BERLIN),
            "search_end": datetime(2026, 4, 11, 20, 0, tzinfo=BERLIN),
            "include_current_interval": False,
        }
        start, _end = resolve_search_range(call_data, now, BERLIN)
        assert start == datetime(2026, 4, 11, 15, 0, tzinfo=BERLIN)

    def test_explicit_start_on_boundary_is_kept_when_current_excluded(self) -> None:
        """A named start already on the grid begins an interval, so it is not skipped.

        This is where an explicit boundary differs from `now`: nothing is mid-flight
        at a point the caller chose, so there is no current interval to exclude.
        """
        now = datetime(2026, 4, 11, 8, 0, tzinfo=BERLIN)
        call_data = {
            "search_start": datetime(2026, 4, 11, 15, 0, tzinfo=BERLIN),
            "search_end": datetime(2026, 4, 11, 20, 0, tzinfo=BERLIN),
            "include_current_interval": False,
        }
        start, _end = resolve_search_range(call_data, now, BERLIN)
        assert start == datetime(2026, 4, 11, 15, 0, tzinfo=BERLIN)

    def test_start_time_of_day_floors_onto_grid(self) -> None:
        """search_start_time with off-grid minutes aligns the same way."""
        now = datetime(2026, 4, 11, 8, 0, tzinfo=BERLIN)
        call_data = {
            "search_start_time": dt_time(14, 47),
            "search_end_time": dt_time(20, 0),
        }
        start, _end = resolve_search_range(call_data, now, BERLIN)
        assert start == datetime(2026, 4, 11, 14, 45, tzinfo=BERLIN)

    def test_explicit_end_ceils_without_changing_what_is_searched(self) -> None:
        """An off-grid range end is ceiled, reporting the interval it already covered.

        The pool takes startsAt < end, so 14:47 always admitted the 14:45 interval.
        Ceiling makes the reported range say so instead of implying a 14:47 cutoff.
        """
        now = datetime(2026, 4, 11, 8, 0, tzinfo=BERLIN)
        call_data = {
            "search_start": datetime(2026, 4, 11, 10, 0, tzinfo=BERLIN),
            "search_end": datetime(2026, 4, 11, 14, 47, tzinfo=BERLIN),
        }
        _start, end = resolve_search_range(call_data, now, BERLIN)
        assert end == datetime(2026, 4, 11, 15, 0, tzinfo=BERLIN)

    def test_end_of_day_idiom_keeps_the_final_interval(self) -> None:
        """The common `23:59` end must still cover the 23:45 interval."""
        now = datetime(2026, 4, 11, 8, 0, tzinfo=BERLIN)
        call_data = {
            "search_start_time": dt_time(10, 0),
            "search_end_time": dt_time(23, 59),
        }
        _start, end = resolve_search_range(call_data, now, BERLIN)
        # Ceiling to midnight keeps startsAt < end true for the 23:45 interval
        assert end == datetime(2026, 4, 12, 0, 0, tzinfo=BERLIN)

    def test_must_finish_by_deadline_is_never_overshot(self) -> None:
        """An off-grid must_finish_by deadline must bound the result, not leak past it.

        Regression: 07:05 used to become search_end=07:05, and since the pool takes
        startsAt < end that admitted the 07:00 interval, whose window runs to 07:15 -
        ten minutes past a deadline the caller stated as hard.
        """
        now = datetime(2026, 4, 11, 4, 0, tzinfo=BERLIN)
        call_data = {
            "search_start": datetime(2026, 4, 11, 5, 0, tzinfo=BERLIN),
            "must_finish_by": datetime(2026, 4, 11, 7, 5, tzinfo=BERLIN),
        }
        effective, deadline = apply_must_finish_by(call_data, BERLIN)
        _start, end = resolve_search_range(effective, now, BERLIN)
        assert deadline == datetime(2026, 4, 11, 7, 5, tzinfo=BERLIN)
        # Last admitted interval starts 06:45 and ends 07:00, inside the deadline
        assert end == datetime(2026, 4, 11, 7, 0, tzinfo=BERLIN)
        assert end <= deadline

    def test_must_finish_by_on_boundary_is_unchanged(self) -> None:
        """A deadline already on the grid keeps its full final interval."""
        now = datetime(2026, 4, 11, 4, 0, tzinfo=BERLIN)
        call_data = {
            "search_start": datetime(2026, 4, 11, 5, 0, tzinfo=BERLIN),
            "must_finish_by": datetime(2026, 4, 11, 7, 0, tzinfo=BERLIN),
        }
        effective, deadline = apply_must_finish_by(call_data, BERLIN)
        _start, end = resolve_search_range(effective, now, BERLIN)
        assert end == deadline == datetime(2026, 4, 11, 7, 0, tzinfo=BERLIN)

    def test_aligned_boundaries_are_left_untouched(self) -> None:
        """A request already on the grid passes through unchanged."""
        now = datetime(2026, 4, 11, 8, 0, tzinfo=BERLIN)
        call_data = {
            "search_start": datetime(2026, 4, 11, 10, 15, tzinfo=BERLIN),
            "search_end": datetime(2026, 4, 11, 14, 30, tzinfo=BERLIN),
        }
        start, end = resolve_search_range(call_data, now, BERLIN)
        assert start == datetime(2026, 4, 11, 10, 15, tzinfo=BERLIN)
        assert end == datetime(2026, 4, 11, 14, 30, tzinfo=BERLIN)

    def test_range_collapsing_to_nothing_does_not_raise(self) -> None:
        """A range that snaps shut is "no window fits", not an invalid request.

        Validation runs on the requested values, so 14:47-14:50 is accepted; excluding
        the current interval then pushes the start onto the end, leaving an empty
        range that services report as no data.
        """
        now = datetime(2026, 4, 11, 8, 0, tzinfo=BERLIN)
        call_data = {
            "search_start": datetime(2026, 4, 11, 14, 47, tzinfo=BERLIN),
            "search_end": datetime(2026, 4, 11, 14, 50, tzinfo=BERLIN),
            "include_current_interval": False,
        }
        start, end = resolve_search_range(call_data, now, BERLIN)
        assert start == end == datetime(2026, 4, 11, 15, 0, tzinfo=BERLIN)

    def test_inverted_range_still_raises(self) -> None:
        """A genuinely backwards request remains a validation error."""
        now = datetime(2026, 4, 11, 8, 0, tzinfo=BERLIN)
        call_data = {
            "search_start": datetime(2026, 4, 11, 16, 0, tzinfo=BERLIN),
            "search_end": datetime(2026, 4, 11, 14, 0, tzinfo=BERLIN),
        }
        with pytest.raises(ServiceValidationError):
            resolve_search_range(call_data, now, BERLIN)


# =============================================================================
# Schema validation: day_offset boundaries
# =============================================================================


class TestSchemaValidation:
    """Verify that schemas accept negative offsets within bounds."""

    def _validate_block_schema(self, data: dict) -> dict:
        """Validate data through block schema."""
        schema = vol.Schema(_COMMON_BLOCK_SCHEMA)
        return cast("dict[str, Any]", schema(data))

    def _validate_hours_schema(self, data: dict) -> dict:
        """Validate data through hours schema."""
        schema = vol.Schema(_COMMON_HOURS_SCHEMA)
        return cast("dict[str, Any]", schema(data))

    def test_block_schema_accepts_negative_day_offset(self) -> None:
        """Block schema allows negative day offsets."""
        result = self._validate_block_schema(
            {
                "entry_id": "test",
                "duration": timedelta(hours=1),
                "search_start_day_offset": -3,
                "search_end_day_offset": -1,
            }
        )
        assert result["search_start_day_offset"] == -3
        assert result["search_end_day_offset"] == -1

    def test_block_schema_accepts_negative_offset_minutes(self) -> None:
        """Block schema allows negative offset minutes."""
        result = self._validate_block_schema(
            {
                "entry_id": "test",
                "duration": timedelta(hours=1),
                "search_start_offset_minutes": -1440,
                "search_end_offset_minutes": -60,
            }
        )
        assert result["search_start_offset_minutes"] == -1440
        assert result["search_end_offset_minutes"] == -60

    def test_block_schema_rejects_out_of_bounds_day_offset(self) -> None:
        """Block schema rejects day offset < -7."""
        with pytest.raises(vol.Invalid):
            self._validate_block_schema(
                {
                    "entry_id": "test",
                    "duration": timedelta(hours=1),
                    "search_start_day_offset": -8,
                }
            )

    def test_block_schema_max_day_offset_still_2(self) -> None:
        """Block schema still limits forward to +2."""
        with pytest.raises(vol.Invalid):
            self._validate_block_schema(
                {
                    "entry_id": "test",
                    "duration": timedelta(hours=1),
                    "search_start_day_offset": 3,
                }
            )

    def test_hours_schema_accepts_negative_day_offset(self) -> None:
        """Hours schema allows negative day offsets."""
        result = self._validate_hours_schema(
            {
                "entry_id": "test",
                "duration": timedelta(hours=2),
                "search_start_day_offset": -7,
                "search_end_day_offset": -5,
            }
        )
        assert result["search_start_day_offset"] == -7

    def test_hours_schema_accepts_negative_offset_minutes(self) -> None:
        """Hours schema allows negative offset minutes."""
        result = self._validate_hours_schema(
            {
                "entry_id": "test",
                "duration": timedelta(hours=2),
                "search_start_offset_minutes": -10080,
                "search_end_offset_minutes": -60,
            }
        )
        assert result["search_start_offset_minutes"] == -10080

    def test_hours_schema_rejects_out_of_bounds_offset_minutes(self) -> None:
        """Hours schema rejects offset minutes outside ±10080."""
        with pytest.raises(vol.Invalid):
            self._validate_hours_schema(
                {
                    "entry_id": "test",
                    "duration": timedelta(hours=2),
                    "search_start_offset_minutes": -10081,
                }
            )
