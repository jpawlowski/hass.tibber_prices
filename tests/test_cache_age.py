"""
Unit tests for sensor fetch age calculation.

Tests the get_sensor_fetch_age_minutes() method which calculates how old
the sensor data is in minutes (based on last API fetch for sensor intervals).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest

from custom_components.tibber_prices.sensor.calculators.lifecycle import (
    TibberPricesLifecycleCalculator,
)


def _create_mock_coordinator_with_pool(
    current_time: datetime,
    last_sensor_fetch: datetime | None,
) -> Mock:
    """Create a mock coordinator with pool stats configured."""
    coordinator = Mock()
    coordinator.time = Mock()
    coordinator.time.now.return_value = current_time

    # Mock the pool stats access path
    mock_pool = Mock()
    if last_sensor_fetch is not None:
        mock_pool.get_pool_stats.return_value = {
            # Sensor intervals (protected range)
            "sensor_intervals_count": 384,
            "sensor_intervals_expected": 384,
            "sensor_intervals_has_gaps": False,
            # Cache statistics
            "cache_intervals_total": 384,
            "cache_intervals_limit": 960,
            "cache_fill_percent": 40.0,
            "cache_intervals_extra": 0,
            # Timestamps
            "last_sensor_fetch": last_sensor_fetch.isoformat(),
            "cache_oldest_interval": "2025-11-20T00:00:00",
            "cache_newest_interval": "2025-11-23T23:45:00",
            # Metadata
            "fetch_groups_count": 1,
        }
    else:
        mock_pool.get_pool_stats.return_value = {
            # Sensor intervals (protected range)
            "sensor_intervals_count": 0,
            "sensor_intervals_expected": 384,
            "sensor_intervals_has_gaps": True,
            # Cache statistics
            "cache_intervals_total": 0,
            "cache_intervals_limit": 960,
            "cache_fill_percent": 0,
            "cache_intervals_extra": 0,
            # Timestamps
            "last_sensor_fetch": None,
            "cache_oldest_interval": None,
            "cache_newest_interval": None,
            # Metadata
            "fetch_groups_count": 0,
        }

    mock_price_data_manager = Mock()
    mock_price_data_manager._interval_pool = mock_pool  # noqa: SLF001

    coordinator._price_data_manager = mock_price_data_manager  # noqa: SLF001

    return coordinator


@pytest.mark.unit
def test_sensor_fetch_age_no_update() -> None:
    """
    Test sensor fetch age is None when no updates have occurred.

    Scenario: Integration just started, no data fetched yet
    Expected: Fetch age is None
    """
    current_time = datetime(2025, 11, 22, 14, 30, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    coordinator = _create_mock_coordinator_with_pool(current_time, None)

    calculator = TibberPricesLifecycleCalculator(coordinator)
    age = calculator.get_sensor_fetch_age_minutes()

    assert age is None


@pytest.mark.unit
def test_sensor_fetch_age_recent() -> None:
    """
    Test sensor fetch age for recent data.

    Scenario: Last update was 5 minutes ago
    Expected: Fetch age is 5 minutes
    """
    current_time = datetime(2025, 11, 22, 14, 30, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    last_fetch = current_time - timedelta(minutes=5)
    coordinator = _create_mock_coordinator_with_pool(current_time, last_fetch)

    calculator = TibberPricesLifecycleCalculator(coordinator)
    age = calculator.get_sensor_fetch_age_minutes()

    assert age == 5


@pytest.mark.unit
def test_sensor_fetch_age_old() -> None:
    """
    Test sensor fetch age for older data.

    Scenario: Last update was 90 minutes ago (6 update cycles missed)
    Expected: Fetch age is 90 minutes
    """
    current_time = datetime(2025, 11, 22, 14, 30, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    last_fetch = current_time - timedelta(minutes=90)
    coordinator = _create_mock_coordinator_with_pool(current_time, last_fetch)

    calculator = TibberPricesLifecycleCalculator(coordinator)
    age = calculator.get_sensor_fetch_age_minutes()

    assert age == 90


@pytest.mark.unit
def test_sensor_fetch_age_exact_minute() -> None:
    """
    Test sensor fetch age calculation rounds down to minutes.

    Scenario: Last update was 5 minutes and 45 seconds ago
    Expected: Fetch age is 5 minutes (int conversion truncates)
    """
    current_time = datetime(2025, 11, 22, 14, 30, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    last_fetch = current_time - timedelta(minutes=5, seconds=45)
    coordinator = _create_mock_coordinator_with_pool(current_time, last_fetch)

    calculator = TibberPricesLifecycleCalculator(coordinator)
    age = calculator.get_sensor_fetch_age_minutes()

    # int() truncates: 5.75 minutes → 5
    assert age == 5


@pytest.mark.unit
def test_sensor_fetch_age_zero_fresh_data() -> None:
    """
    Test sensor fetch age is 0 for brand new data.

    Scenario: Last update was just now (< 60 seconds ago)
    Expected: Fetch age is 0 minutes
    """
    current_time = datetime(2025, 11, 22, 14, 30, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    last_fetch = current_time - timedelta(seconds=30)
    coordinator = _create_mock_coordinator_with_pool(current_time, last_fetch)

    calculator = TibberPricesLifecycleCalculator(coordinator)
    age = calculator.get_sensor_fetch_age_minutes()

    assert age == 0


@pytest.mark.unit
def test_sensor_fetch_age_multiple_hours() -> None:
    """
    Test sensor fetch age for very old data (multiple hours).

    Scenario: Last update was 3 hours ago (180 minutes)
    Expected: Fetch age is 180 minutes

    This could happen if API was down or integration was stopped.
    """
    current_time = datetime(2025, 11, 22, 14, 30, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    last_fetch = current_time - timedelta(hours=3)
    coordinator = _create_mock_coordinator_with_pool(current_time, last_fetch)

    calculator = TibberPricesLifecycleCalculator(coordinator)
    age = calculator.get_sensor_fetch_age_minutes()

    assert age == 180


@pytest.mark.unit
def test_sensor_fetch_age_boundary_60_seconds() -> None:
    """
    Test sensor fetch age exactly at 60 seconds (1 minute boundary).

    Scenario: Last update was exactly 60 seconds ago
    Expected: Fetch age is 1 minute
    """
    current_time = datetime(2025, 11, 22, 14, 30, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    last_fetch = current_time - timedelta(seconds=60)
    coordinator = _create_mock_coordinator_with_pool(current_time, last_fetch)

    calculator = TibberPricesLifecycleCalculator(coordinator)
    age = calculator.get_sensor_fetch_age_minutes()

    assert age == 1
