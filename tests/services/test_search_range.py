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
from custom_components.tibber_prices.services.helpers import resolve_search_range

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
        assert end.day == 10
        assert end.hour == 23

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
        assert end.day == 4

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
        """Relative search scopes honor include_current_interval=false."""
        now = datetime(2026, 4, 11, 14, 37, tzinfo=BERLIN)
        call_data = {
            "search_scope": "next_24h",
            "include_current_interval": False,
        }
        start, end = resolve_search_range(call_data, now, BERLIN)
        assert start == now
        assert end == now + timedelta(hours=24)

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
        assert end == now + timedelta(hours=24)


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
