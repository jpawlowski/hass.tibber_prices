"""Segment boundaries of the day pattern."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from custom_components.tibber_prices.coordinator.period_handlers.day_pattern import _detect_segments

DAY = datetime(2026, 10, 16, tzinfo=UTC)
TIMES = [DAY + timedelta(minutes=15 * i) for i in range(96)]
# Rising to 18:15, falling after it
PRICES = [float(i) if i <= 73 else float(146 - i) for i in range(96)]


@pytest.mark.unit
def test_last_segment_lasts_until_midnight() -> None:
    """Nothing takes over after 23:45, so the last segment ends at midnight, not at 23:45."""
    segments = _detect_segments([{"idx": 73}], PRICES, TIMES)

    assert [(s["type"], s["start"], s["end"]) for s in segments] == [
        ("rising", TIMES[0].isoformat(), TIMES[73].isoformat()),
        ("falling", TIMES[73].isoformat(), (DAY + timedelta(days=1)).isoformat()),
    ]
