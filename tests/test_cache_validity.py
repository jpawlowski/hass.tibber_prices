"""
Unit tests for cache validity checks.

Tests the is_cache_valid() function which determines if cached price data
is still current or needs to be refreshed.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest

from custom_components.tibber_prices.coordinator.cache import (
    TibberPricesCacheData,
    is_cache_valid,
)


@pytest.mark.unit
def test_cache_valid_same_day() -> None:
    """
    Test cache is valid when data is from the same calendar day.

    Scenario: Cache from 10:00, current time 15:00 (same day)
    Expected: Cache is valid
    """
    time_service = Mock()
    cache_time = datetime(2025, 11, 22, 10, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    current_time = datetime(2025, 11, 22, 15, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))

    time_service.now.return_value = current_time
    time_service.as_local.side_effect = lambda dt: dt

    cache_data = TibberPricesCacheData(
        price_data={"priceInfo": {"today": [1, 2, 3]}},
        user_data={"viewer": {"home": {"id": "test"}}},
        last_price_update=cache_time,
        last_user_update=cache_time,
        last_midnight_check=None,
    )

    result = is_cache_valid(cache_data, "[TEST]", time=time_service)

    assert result is True


@pytest.mark.unit
def test_cache_invalid_different_day() -> None:
    """
    Test cache is invalid when data is from a different calendar day.

    Scenario: Cache from yesterday, current time today
    Expected: Cache is invalid (date mismatch)
    """
    time_service = Mock()
    cache_time = datetime(2025, 11, 21, 23, 50, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    current_time = datetime(2025, 11, 22, 0, 10, 0, tzinfo=ZoneInfo("Europe/Oslo"))

    time_service.now.return_value = current_time
    time_service.as_local.side_effect = lambda dt: dt

    cache_data = TibberPricesCacheData(
        price_data={"priceInfo": {"today": [1, 2, 3]}},
        user_data={"viewer": {"home": {"id": "test"}}},
        last_price_update=cache_time,
        last_user_update=cache_time,
        last_midnight_check=None,
    )

    result = is_cache_valid(cache_data, "[TEST]", time=time_service)

    assert result is False


@pytest.mark.unit
def test_cache_invalid_no_price_data() -> None:
    """
    Test cache is invalid when no price data exists.

    Scenario: Cache exists but price_data is None
    Expected: Cache is invalid
    """
    time_service = Mock()
    current_time = datetime(2025, 11, 22, 15, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))

    time_service.now.return_value = current_time
    time_service.as_local.side_effect = lambda dt: dt

    cache_data = TibberPricesCacheData(
        price_data=None,  # No price data!
        user_data={"viewer": {"home": {"id": "test"}}},
        last_price_update=current_time,
        last_user_update=current_time,
        last_midnight_check=None,
    )

    result = is_cache_valid(cache_data, "[TEST]", time=time_service)

    assert result is False


@pytest.mark.unit
def test_cache_invalid_no_last_update() -> None:
    """
    Test cache is invalid when last_price_update is None.

    Scenario: Cache has data but no update timestamp
    Expected: Cache is invalid
    """
    time_service = Mock()
    current_time = datetime(2025, 11, 22, 15, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))

    time_service.now.return_value = current_time
    time_service.as_local.side_effect = lambda dt: dt

    cache_data = TibberPricesCacheData(
        price_data={"priceInfo": {"today": [1, 2, 3]}},
        user_data={"viewer": {"home": {"id": "test"}}},
        last_price_update=None,  # No timestamp!
        last_user_update=None,
        last_midnight_check=None,
    )

    result = is_cache_valid(cache_data, "[TEST]", time=time_service)

    assert result is False


@pytest.mark.unit
def test_cache_valid_after_midnight_turnover() -> None:
    """
    Test cache validity after midnight turnover with updated timestamp.

    Scenario: Midnight turnover occurred, _last_price_update was updated to new day
    Expected: Cache is valid (same date as current)

    This tests the fix for the "date_mismatch" bug where cache appeared invalid
    after midnight despite successful data rotation.
    """
    time_service = Mock()
    # After midnight turnover, _last_price_update should be set to current time
    turnover_time = datetime(2025, 11, 22, 0, 0, 5, tzinfo=ZoneInfo("Europe/Oslo"))
    current_time = datetime(2025, 11, 22, 0, 10, 0, tzinfo=ZoneInfo("Europe/Oslo"))

    time_service.now.return_value = current_time
    time_service.as_local.side_effect = lambda dt: dt

    cache_data = TibberPricesCacheData(
        price_data={"priceInfo": {"yesterday": [1], "today": [2], "tomorrow": []}},
        user_data={"viewer": {"home": {"id": "test"}}},
        last_price_update=turnover_time,  # Updated during turnover!
        last_user_update=turnover_time,
        last_midnight_check=turnover_time,
    )

    result = is_cache_valid(cache_data, "[TEST]", time=time_service)

    assert result is True


@pytest.mark.unit
def test_cache_invalid_midnight_crossing_without_update() -> None:
    """
    Test cache becomes invalid at midnight if timestamp not updated.

    Scenario: HA restarted after midnight, cache still has yesterday's timestamp
    Expected: Cache is invalid (would be caught and refreshed)
    """
    time_service = Mock()
    cache_time = datetime(2025, 11, 21, 23, 55, 0, tzinfo=ZoneInfo("Europe/Oslo"))
    current_time = datetime(2025, 11, 22, 0, 5, 0, tzinfo=ZoneInfo("Europe/Oslo"))

    time_service.now.return_value = current_time
    time_service.as_local.side_effect = lambda dt: dt

    cache_data = TibberPricesCacheData(
        price_data={"priceInfo": {"today": [1, 2, 3]}},
        user_data={"viewer": {"home": {"id": "test"}}},
        last_price_update=cache_time,  # Still yesterday!
        last_user_update=cache_time,
        last_midnight_check=None,
    )

    result = is_cache_valid(cache_data, "[TEST]", time=time_service)

    assert result is False


@pytest.mark.unit
def test_cache_validity_timezone_aware() -> None:
    """
    Test cache validity uses local timezone for date comparison.

    Scenario: UTC midnight vs local timezone midnight (different dates)
    Expected: Comparison done in local timezone, not UTC

    This ensures that midnight turnover happens at local midnight,
    not UTC midnight.
    """
    time_service = Mock()

    # 23:00 UTC on Nov 21 = 00:00 CET on Nov 22 (UTC+1)
    cache_time_utc = datetime(2025, 11, 21, 23, 0, 0, tzinfo=ZoneInfo("UTC"))
    current_time_utc = datetime(2025, 11, 21, 23, 30, 0, tzinfo=ZoneInfo("UTC"))

    # Convert to local timezone (CET = UTC+1)
    cache_time_local = cache_time_utc.astimezone(ZoneInfo("Europe/Oslo"))  # 00:00 Nov 22
    current_time_local = current_time_utc.astimezone(ZoneInfo("Europe/Oslo"))  # 00:30 Nov 22

    time_service.now.return_value = current_time_utc
    time_service.as_local.return_value = current_time_local

    cache_data = TibberPricesCacheData(
        price_data={"priceInfo": {"today": [1, 2, 3]}},
        user_data={"viewer": {"home": {"id": "test"}}},
        last_price_update=cache_time_utc,
        last_user_update=cache_time_utc,
        last_midnight_check=None,
    )

    # Mock as_local for cache_time
    def as_local_side_effect(dt: datetime) -> datetime:
        if dt == cache_time_utc:
            return cache_time_local
        return current_time_local

    time_service.as_local.side_effect = as_local_side_effect

    result = is_cache_valid(cache_data, "[TEST]", time=time_service)

    # Both times are Nov 22 in local timezone → same date → valid
    assert result is True


@pytest.mark.unit
def test_cache_validity_exact_midnight_boundary() -> None:
    """
    Test cache validity exactly at midnight boundary.

    Scenario: Cache from 23:59:59, current time 00:00:00
    Expected: Cache is invalid (different calendar days)
    """
    time_service = Mock()
    cache_time = datetime(2025, 11, 21, 23, 59, 59, tzinfo=ZoneInfo("Europe/Oslo"))
    current_time = datetime(2025, 11, 22, 0, 0, 0, tzinfo=ZoneInfo("Europe/Oslo"))

    time_service.now.return_value = current_time
    time_service.as_local.side_effect = lambda dt: dt

    cache_data = TibberPricesCacheData(
        price_data={"priceInfo": {"today": [1, 2, 3]}},
        user_data={"viewer": {"home": {"id": "test"}}},
        last_price_update=cache_time,
        last_user_update=cache_time,
        last_midnight_check=None,
    )

    result = is_cache_valid(cache_data, "[TEST]", time=time_service)

    assert result is False
