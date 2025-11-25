"""
Tests for interval pool API call optimization.

These tests demonstrate how the interval pool minimizes API calls by:
1. Detecting all missing ranges (gaps in cache)
2. Making exactly ONE API call per continuous gap
3. Reusing cached intervals whenever possible

NOTE: These tests are currently skipped due to the single-home architecture refactoring.
The tests need to be rewritten to properly mock the TibberPricesApiClient with all
required methods (_extract_home_timezones, _calculate_day_before_yesterday_midnight,
async_get_price_info, async_get_price_info_range). The mocking strategy needs to be
updated to match the new API routing logic in interval_pool/routing.py.

TODO: Rewrite these tests with proper API client fixtures.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.tibber_prices.interval_pool.pool import TibberPricesIntervalPool
from homeassistant.util import dt as dt_utils

pytest_plugins = ("pytest_homeassistant_custom_component",)

# Skip all tests in this module until they are rewritten for single-home architecture
pytestmark = pytest.mark.skip(reason="Tests need rewrite for single-home architecture + API routing mocks")


def _create_test_interval(start_time: datetime) -> dict:
    """Create a test price interval dict."""
    return {
        "startsAt": start_time.isoformat(),
        "total": 25.5,
        "energy": 20.0,
        "tax": 5.5,
        "level": "NORMAL",
    }


def _create_intervals(start: datetime, count: int) -> list[dict]:
    """Create a list of test intervals (15min each)."""
    return [_create_test_interval(start + timedelta(minutes=15 * i)) for i in range(count)]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_no_cache_single_api_call() -> None:
    """Test: Empty cache → 1 API call for entire range."""
    pool = TibberPricesIntervalPool(home_id="home123")

    # Mock API client
    api_client = MagicMock(
        spec=[
            "async_get_price_info_for_range",
            "async_get_price_info",
            "async_get_price_info_range",
            "_extract_home_timezones",
            "_calculate_day_before_yesterday_midnight",
        ]
    )
    start = dt_utils.now().replace(hour=10, minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=2)  # 8 intervals

    # Create mock response
    mock_intervals = _create_intervals(start, 8)
    api_client.async_get_price_info_for_range = AsyncMock(return_value=mock_intervals)
    api_client._extract_home_timezones = MagicMock(return_value={"home123": "Europe/Berlin"})  # noqa: SLF001
    # Mock boundary calculation (returns day before yesterday midnight)
    dby_midnight = (dt_utils.now() - timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
    api_client._calculate_day_before_yesterday_midnight = MagicMock(return_value=dby_midnight)  # noqa: SLF001
    # Mock the actual price info fetching methods (they call async_get_price_info_for_range internally)
    api_client.async_get_price_info = AsyncMock(return_value={"priceInfo": mock_intervals})
    api_client.async_get_price_info_range = AsyncMock(return_value=mock_intervals)

    user_data = {"timeZone": "Europe/Berlin"}

    # Act
    result = await pool.get_intervals(api_client, user_data, start, end)

    # Assert: Exactly 1 API call
    assert api_client.async_get_price_info_for_range.call_count == 1
    assert len(result) == 8


@pytest.mark.asyncio
@pytest.mark.unit
async def test_full_cache_zero_api_calls() -> None:
    """Test: Fully cached range → 0 API calls."""
    pool = TibberPricesIntervalPool(home_id="home123")

    # Mock API client
    api_client = MagicMock(
        spec=[
            "async_get_price_info_for_range",
            "async_get_price_info",
            "async_get_price_info_range",
            "_extract_home_timezones",
            "_calculate_day_before_yesterday_midnight",
        ]
    )
    start = dt_utils.now().replace(hour=10, minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=2)  # 8 intervals

    # Pre-populate cache
    mock_intervals = _create_intervals(start, 8)
    api_client.async_get_price_info_for_range = AsyncMock(return_value=mock_intervals)
    api_client._extract_home_timezones = MagicMock(return_value={"home123": "Europe/Berlin"})  # noqa: SLF001
    # Mock boundary calculation (returns day before yesterday midnight)
    dby_midnight = (dt_utils.now() - timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
    api_client._calculate_day_before_yesterday_midnight = MagicMock(return_value=dby_midnight)  # noqa: SLF001
    # Mock the actual price info fetching methods (they call async_get_price_info_for_range internally)
    api_client.async_get_price_info = AsyncMock(return_value={"priceInfo": mock_intervals})
    api_client.async_get_price_info_range = AsyncMock(return_value=mock_intervals)
    user_data = {"timeZone": "Europe/Berlin"}

    # First call: populate cache
    await pool.get_intervals(api_client, user_data, start, end)
    assert api_client.async_get_price_info_for_range.call_count == 1

    # Second call: should use cache
    result = await pool.get_intervals(api_client, user_data, start, end)

    # Assert: Still only 1 API call (from first request)
    assert api_client.async_get_price_info_for_range.call_count == 1
    assert len(result) == 8


@pytest.mark.asyncio
@pytest.mark.unit
async def test_single_gap_single_api_call() -> None:
    """Test: One gap in cache → 1 API call for that gap only."""
    pool = TibberPricesIntervalPool(home_id="home123")

    # Mock API client
    api_client = MagicMock(
        spec=[
            "async_get_price_info_for_range",
            "async_get_price_info",
            "async_get_price_info_range",
            "_extract_home_timezones",
            "_calculate_day_before_yesterday_midnight",
        ]
    )
    start = dt_utils.now().replace(hour=10, minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=3)  # 12 intervals total

    user_data = {"timeZone": "Europe/Berlin"}

    # Pre-populate cache with first 4 and last 4 intervals (gap in middle)
    first_batch = _create_intervals(start, 4)
    last_batch = _create_intervals(start + timedelta(hours=2), 4)

    # First call: cache first batch
    api_client.async_get_price_info_for_range = AsyncMock(return_value=first_batch)
    await pool.get_intervals(api_client, user_data, start, start + timedelta(hours=1))

    # Second call: cache last batch
    api_client.async_get_price_info_for_range = AsyncMock(return_value=last_batch)
    await pool.get_intervals(
        api_client,
        user_data,
        start + timedelta(hours=2),
        start + timedelta(hours=3),
    )

    # Now we have: [10:00-11:00] <GAP> [12:00-13:00]
    call_count_before = api_client.async_get_price_info_for_range.call_count

    # Third call: request entire range (should only fetch the gap)
    gap_intervals = _create_intervals(start + timedelta(hours=1), 4)
    api_client.async_get_price_info_for_range = AsyncMock(return_value=gap_intervals)

    result = await pool.get_intervals(api_client, user_data, start, end)

    # Assert: Exactly 1 additional API call (for the gap)
    assert api_client.async_get_price_info_for_range.call_count == call_count_before + 1
    assert len(result) == 12  # All intervals now available


@pytest.mark.asyncio
@pytest.mark.unit
async def test_multiple_gaps_multiple_api_calls() -> None:
    """Test: Multiple gaps → one API call per continuous gap."""
    pool = TibberPricesIntervalPool(home_id="home123")

    # Mock API client
    api_client = MagicMock(
        spec=[
            "async_get_price_info_for_range",
            "async_get_price_info",
            "async_get_price_info_range",
            "_extract_home_timezones",
            "_calculate_day_before_yesterday_midnight",
        ]
    )
    start = dt_utils.now().replace(hour=10, minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=4)  # 16 intervals total

    user_data = {"timeZone": "Europe/Berlin"}

    # Pre-populate cache with scattered intervals
    # Cache: [10:00-10:30] <GAP1> [11:00-11:30] <GAP2> [12:00-12:30] <GAP3> [13:00-13:30]
    batch1 = _create_intervals(start, 2)  # 10:00-10:30
    batch2 = _create_intervals(start + timedelta(hours=1), 2)  # 11:00-11:30
    batch3 = _create_intervals(start + timedelta(hours=2), 2)  # 12:00-12:30
    batch4 = _create_intervals(start + timedelta(hours=3), 2)  # 13:00-13:30

    # Populate cache
    for batch, offset in [
        (batch1, 0),
        (batch2, 1),
        (batch3, 2),
        (batch4, 3),
    ]:
        api_client.async_get_price_info_for_range = AsyncMock(return_value=batch)
        await pool.get_intervals(
            api_client,
            user_data,
            start + timedelta(hours=offset),
            start + timedelta(hours=offset, minutes=30),
        )

    call_count_before = api_client.async_get_price_info_for_range.call_count

    # Now request entire range (should fetch 3 gaps)
    gap1 = _create_intervals(start + timedelta(minutes=30), 2)  # 10:30-11:00
    gap2 = _create_intervals(start + timedelta(hours=1, minutes=30), 2)  # 11:30-12:00
    gap3 = _create_intervals(start + timedelta(hours=2, minutes=30), 2)  # 12:30-13:00

    # Mock will be called 3 times, return appropriate gap data each time
    call_count = 0

    def mock_fetch(*_args: object, **_kwargs: object) -> list[dict]:
        """Mock fetch function that returns different data per call."""
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return gap1
        if call_count == 2:
            return gap2
        return gap3

    api_client.async_get_price_info_for_range = AsyncMock(side_effect=mock_fetch)

    result = await pool.get_intervals(api_client, user_data, start, end)

    # Assert: Exactly 3 additional API calls (one per gap)
    assert api_client.async_get_price_info_for_range.call_count == call_count_before + 3
    assert len(result) == 16  # All intervals now available


@pytest.mark.asyncio
@pytest.mark.unit
async def test_partial_overlap_minimal_fetch() -> None:
    """Test: Overlapping request → fetch only new intervals."""
    pool = TibberPricesIntervalPool(home_id="home123")

    # Mock API client
    api_client = MagicMock(
        spec=[
            "async_get_price_info_for_range",
            "async_get_price_info",
            "async_get_price_info_range",
            "_extract_home_timezones",
            "_calculate_day_before_yesterday_midnight",
        ]
    )
    start = dt_utils.now().replace(hour=10, minute=0, second=0, microsecond=0)

    user_data = {"timeZone": "Europe/Berlin"}

    # First request: 10:00-12:00 (8 intervals)
    batch1 = _create_intervals(start, 8)
    api_client.async_get_price_info_for_range = AsyncMock(return_value=batch1)
    await pool.get_intervals(api_client, user_data, start, start + timedelta(hours=2))

    assert api_client.async_get_price_info_for_range.call_count == 1

    # Second request: 11:00-13:00 (8 intervals, 4 cached, 4 new)
    batch2 = _create_intervals(start + timedelta(hours=2), 4)  # Only new ones
    api_client.async_get_price_info_for_range = AsyncMock(return_value=batch2)

    result = await pool.get_intervals(
        api_client,
        user_data,
        start + timedelta(hours=1),
        start + timedelta(hours=3),
    )

    # Assert: 1 additional API call (for 12:00-13:00 only)
    assert api_client.async_get_price_info_for_range.call_count == 2
    assert len(result) == 8  # 11:00-13:00


@pytest.mark.asyncio
@pytest.mark.unit
async def test_detect_missing_ranges_optimization() -> None:
    """Test: Gap detection returns minimal set of ranges (tested via API behavior)."""
    pool = TibberPricesIntervalPool(home_id="home123")

    # Mock API client that tracks calls
    api_client = MagicMock(
        spec=[
            "async_get_price_info_for_range",
            "async_get_price_info",
            "async_get_price_info_range",
            "_extract_home_timezones",
            "_calculate_day_before_yesterday_midnight",
        ]
    )

    start = dt_utils.now().replace(hour=10, minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=4)

    user_data = {"timeZone": "Europe/Berlin"}

    # Pre-populate cache with scattered intervals
    cached = [
        _create_test_interval(start),  # 10:00
        _create_test_interval(start + timedelta(minutes=15)),  # 10:15
        # GAP: 10:30-11:00
        _create_test_interval(start + timedelta(hours=1)),  # 11:00
        _create_test_interval(start + timedelta(hours=1, minutes=15)),  # 11:15
        # GAP: 11:30-12:00
        _create_test_interval(start + timedelta(hours=2)),  # 12:00
        # GAP: 12:15-14:00
    ]

    # Manually add to cache (simulate previous fetches)
    # Note: Accessing private _cache for test setup
    # Single-home architecture: directly populate internal structures
    pool._fetch_groups = [  # noqa: SLF001
        {
            "intervals": cached,
            "fetch_time": dt_utils.now().isoformat(),
        }
    ]
    pool._timestamp_index = {interval["startsAt"]: idx for idx, interval in enumerate(cached)}  # noqa: SLF001

    # Mock responses for the 3 expected gaps
    gap1 = _create_intervals(start + timedelta(minutes=30), 2)  # 10:30-11:00
    gap2 = _create_intervals(start + timedelta(hours=1, minutes=30), 2)  # 11:30-12:00
    gap3 = _create_intervals(start + timedelta(hours=2, minutes=15), 7)  # 12:15-14:00

    call_count = 0

    def mock_fetch(*_args: object, **_kwargs: object) -> list[dict]:
        """Mock fetch function that returns different data per call."""
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return gap1
        if call_count == 2:
            return gap2
        return gap3

    api_client.async_get_price_info_for_range = AsyncMock(side_effect=mock_fetch)

    # Request entire range - should detect exactly 3 gaps
    result = await pool.get_intervals(api_client, user_data, start, end)

    # Assert: Exactly 3 API calls (one per gap)
    assert api_client.async_get_price_info_for_range.call_count == 3

    # Verify all intervals are now available
    assert len(result) == 16  # 2 + 2 + 2 + 2 + 1 + 7 = 16 intervals
