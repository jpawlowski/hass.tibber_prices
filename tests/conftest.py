"""Shared test fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from zoneinfo import ZoneInfo

import pytest

from homeassistant.util import dt as dt_util


@pytest.fixture
def berlin() -> Iterator[ZoneInfo]:
    """Run a test in Europe/Berlin (DST), then restore the default time zone."""
    previous = dt_util.get_default_time_zone()
    zone = ZoneInfo("Europe/Berlin")
    dt_util.set_default_time_zone(zone)
    yield zone
    dt_util.set_default_time_zone(previous)
