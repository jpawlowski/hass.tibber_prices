"""
Unit tests for cache age calculation.

Tests the get_cache_age_minutes() method which calculates how old
the cached data is in minutes.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest

from custom_components.tibber_prices.sensor.calculators.lifecycle import (
    TibberPricesLifecycleCalculator,
)


@pytest.mark.unit
def test_cache_age_no_update() -> None:
    """
    Test cache age is None when no updates have occurred.

    Scenario: Integration just started, no data fetched yet
    Expected: Cache age is None
    """
    coordinator = Mock()
    coordinator.time = Mock()

    current_time = datetime(2025, 11, 22, 14, 30, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    coordinator.time.now.return_value = current_time
    coordinator._last_price_update = None  # noqa: SLF001 - No update yet!

    calculator = TibberPricesLifecycleCalculator(coordinator)
    age = calculator.get_cache_age_minutes()

    assert age is None


@pytest.mark.unit
def test_cache_age_recent() -> None:
    """
    Test cache age for recent data.

    Scenario: Last update was 5 minutes ago
    Expected: Cache age is 5 minutes
    """
    coordinator = Mock()
    coordinator.time = Mock()

    current_time = datetime(2025, 11, 22, 14, 30, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    last_update = current_time - timedelta(minutes=5)

    coordinator.time.now.return_value = current_time
    coordinator._last_price_update = last_update  # noqa: SLF001

    calculator = TibberPricesLifecycleCalculator(coordinator)
    age = calculator.get_cache_age_minutes()

    assert age == 5


@pytest.mark.unit
def test_cache_age_old() -> None:
    """
    Test cache age for older data.

    Scenario: Last update was 90 minutes ago (6 update cycles missed)
    Expected: Cache age is 90 minutes
    """
    coordinator = Mock()
    coordinator.time = Mock()

    current_time = datetime(2025, 11, 22, 14, 30, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    last_update = current_time - timedelta(minutes=90)

    coordinator.time.now.return_value = current_time
    coordinator._last_price_update = last_update  # noqa: SLF001

    calculator = TibberPricesLifecycleCalculator(coordinator)
    age = calculator.get_cache_age_minutes()

    assert age == 90


@pytest.mark.unit
def test_cache_age_exact_minute() -> None:
    """
    Test cache age calculation rounds down to minutes.

    Scenario: Last update was 5 minutes and 45 seconds ago
    Expected: Cache age is 5 minutes (int conversion truncates)
    """
    coordinator = Mock()
    coordinator.time = Mock()

    current_time = datetime(2025, 11, 22, 14, 30, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    last_update = current_time - timedelta(minutes=5, seconds=45)

    coordinator.time.now.return_value = current_time
    coordinator._last_price_update = last_update  # noqa: SLF001

    calculator = TibberPricesLifecycleCalculator(coordinator)
    age = calculator.get_cache_age_minutes()

    # int() truncates: 5.75 minutes → 5
    assert age == 5


@pytest.mark.unit
def test_cache_age_zero_fresh_data() -> None:
    """
    Test cache age is 0 for brand new data.

    Scenario: Last update was just now (< 60 seconds ago)
    Expected: Cache age is 0 minutes
    """
    coordinator = Mock()
    coordinator.time = Mock()

    current_time = datetime(2025, 11, 22, 14, 30, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    last_update = current_time - timedelta(seconds=30)

    coordinator.time.now.return_value = current_time
    coordinator._last_price_update = last_update  # noqa: SLF001

    calculator = TibberPricesLifecycleCalculator(coordinator)
    age = calculator.get_cache_age_minutes()

    assert age == 0


@pytest.mark.unit
def test_cache_age_multiple_hours() -> None:
    """
    Test cache age for very old data (multiple hours).

    Scenario: Last update was 3 hours ago (180 minutes)
    Expected: Cache age is 180 minutes

    This could happen if API was down or integration was stopped.
    """
    coordinator = Mock()
    coordinator.time = Mock()

    current_time = datetime(2025, 11, 22, 14, 30, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    last_update = current_time - timedelta(hours=3)

    coordinator.time.now.return_value = current_time
    coordinator._last_price_update = last_update  # noqa: SLF001

    calculator = TibberPricesLifecycleCalculator(coordinator)
    age = calculator.get_cache_age_minutes()

    assert age == 180


@pytest.mark.unit
def test_cache_age_boundary_60_seconds() -> None:
    """
    Test cache age exactly at 60 seconds (1 minute boundary).

    Scenario: Last update was exactly 60 seconds ago
    Expected: Cache age is 1 minute
    """
    coordinator = Mock()
    coordinator.time = Mock()

    current_time = datetime(2025, 11, 22, 14, 30, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    last_update = current_time - timedelta(seconds=60)

    coordinator.time.now.return_value = current_time
    coordinator._last_price_update = last_update  # noqa: SLF001

    calculator = TibberPricesLifecycleCalculator(coordinator)
    age = calculator.get_cache_age_minutes()

    assert age == 1
