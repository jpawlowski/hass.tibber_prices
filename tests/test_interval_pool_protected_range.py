"""Tests for the interval pool's protected range: the days garbage collection never evicts."""

from datetime import datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService
from custom_components.tibber_prices.interval_pool.cache import TibberPricesIntervalPoolFetchGroupCache
from custom_components.tibber_prices.interval_pool.manager import TibberPricesIntervalPool


@pytest.mark.unit
def test_protected_range_counts_days_in_the_homes_time_zone() -> None:
    """GC protects the days the coordinator fetches: from day-before-yesterday 00:00 in the home's time."""
    # 01:30 in Oslo is still the previous day in New York, where Home Assistant might run
    now = datetime(2026, 10, 17, 1, 30, tzinfo=ZoneInfo("Europe/Oslo")).astimezone(ZoneInfo("America/New_York"))
    cache = TibberPricesIntervalPoolFetchGroupCache(time_service=TibberPricesTimeService(reference_time=now))
    cache.set_home_timezone(ZoneInfo("Europe/Oslo"))

    assert cache.get_protected_range() == ("2026-10-15T00:00:00+02:00", "2026-10-19T00:00:00+02:00")
    # The night that began the day before yesterday at 22:00 stays
    assert cache.is_interval_protected({"startsAt": "2026-10-15T22:00:00.000+02:00"})
    assert not cache.is_interval_protected({"startsAt": "2026-10-14T23:45:00.000+02:00"})


@pytest.mark.unit
def test_restored_pool_knows_the_homes_time_zone_before_its_first_fetch() -> None:
    """The home's time zone is stored with the pool: GC right after a restart protects the home's days."""
    now = datetime(2026, 10, 17, 1, 30, tzinfo=ZoneInfo("Europe/Oslo")).astimezone(ZoneInfo("America/New_York"))
    time = TibberPricesTimeService(reference_time=now)
    pool = TibberPricesIntervalPool(home_id="home", api=MagicMock(), time_service=time)
    pool.set_home_timezone("Europe/Oslo")

    restored = TibberPricesIntervalPool.from_dict(pool.to_dict(), api=MagicMock(), time_service=time)

    assert restored is not None
    assert restored._cache.get_protected_range()  # noqa: SLF001 == ("2026-10-15T00:00:00+02:00", "2026-10-19T00:00:00+02:00")
