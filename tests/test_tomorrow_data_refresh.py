"""
Tests for tomorrow data arrival and cache invalidation.

Regression test for the bug where lifecycle sensor attributes (data_completeness,
tomorrow_available) didn't update after tomorrow data was successfully fetched
due to cached transformation data.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest

from custom_components.tibber_prices.coordinator.data_transformation import (
    TibberPricesDataTransformer,
)
from custom_components.tibber_prices.coordinator.time_service import (
    TibberPricesTimeService,
)
from homeassistant.util import dt as dt_util


def create_price_intervals(day_offset: int = 0) -> list[dict]:
    """Create 96 mock price intervals (quarter-hourly for one day)."""
    # Use CURRENT date so tests work regardless of when they run
    now_local = dt_util.now()
    base_date = now_local.replace(hour=0, minute=0, second=0, microsecond=0)

    intervals = []
    for i in range(96):
        interval_time = base_date.replace(day=base_date.day + day_offset, hour=i // 4, minute=(i % 4) * 15)
        intervals.append(
            {
                "startsAt": interval_time,
                "total": 20.0 + (i % 10),
                "energy": 18.0 + (i % 10),
                "tax": 2.0,
                "level": "NORMAL",
            }
        )
    return intervals


@pytest.mark.unit
def test_transformation_cache_invalidation_on_new_timestamp() -> None:
    """
    Test that DataTransformer cache is invalidated when source data timestamp changes.

    This is the core regression test for the bug:
    - Tomorrow data arrives with NEW timestamp
    - Transformation cache MUST be invalidated
    - Lifecycle attributes MUST be recalculated with new data
    """
    config_entry = Mock()
    config_entry.entry_id = "test_entry"
    config_entry.data = {"home_id": "home_123"}
    config_entry.options = {
        "price_rating_threshold_low": 75.0,
        "price_rating_threshold_high": 90.0,
    }

    time_service = TibberPricesTimeService()
    current_time = datetime(2025, 11, 22, 13, 15, 0, tzinfo=ZoneInfo("Europe/Oslo"))

    # Mock period calculator
    mock_period_calc = Mock()
    mock_period_calc.calculate_periods_for_price_info.return_value = {
        "best_price": [],
        "peak_price": [],
    }

    # Create transformer
    transformer = TibberPricesDataTransformer(
        config_entry=config_entry,
        log_prefix="[Test]",
        calculate_periods_fn=mock_period_calc.calculate_periods_for_price_info,
        time=time_service,
    )

    # STEP 1: First transformation with only today data (timestamp T1)
    # ================================================================
    data_t1 = {
        "timestamp": current_time,
        "home_id": "home_123",
        "price_info": create_price_intervals(0),  # Today only
        "currency": "EUR",
    }

    result_t1 = transformer.transform_data(data_t1)
    assert result_t1 is not None
    # In new flat structure, priceInfo is a list with only today's intervals (96)
    assert len(result_t1["priceInfo"]) == 96

    # STEP 2: Second call with SAME timestamp should use cache
    # =========================================================
    result_t1_cached = transformer.transform_data(data_t1)
    assert result_t1_cached is result_t1  # SAME object (cached)

    # STEP 3: Third call with DIFFERENT timestamp should NOT use cache
    # =================================================================
    new_time = current_time + timedelta(minutes=1)
    data_t2 = {
        "timestamp": new_time,  # DIFFERENT timestamp
        "home_id": "home_123",
        "price_info": create_price_intervals(0) + create_price_intervals(1),  # Today + Tomorrow
        "currency": "EUR",
    }

    result_t2 = transformer.transform_data(data_t2)

    # CRITICAL ASSERTIONS: Cache must be invalidated
    assert result_t2 is not result_t1  # DIFFERENT object (re-transformed)
    assert len(result_t2["priceInfo"]) == 192  # Today (96) + Tomorrow (96)
    assert "pricePeriods" in result_t2  # Periods recalculated


@pytest.mark.unit
def test_cache_behavior_on_config_change() -> None:
    """
    Document current cache behavior when config changes.

    NOTE: Currently, config changes with same timestamp DO NOT invalidate cache.
    This is acceptable because:
    1. Config changes trigger full coordinator reload (new instance)
    2. The critical bug was about NEW API DATA not updating (timestamp change)
    3. Options changes are handled at coordinator level via invalidate_config_cache()
    """
    config_entry = Mock()
    config_entry.entry_id = "test_entry"
    config_entry.data = {"home_id": "home_123"}
    config_entry.options = {
        "price_rating_threshold_low": 75.0,
        "price_rating_threshold_high": 90.0,
    }

    time_service = TibberPricesTimeService()
    current_time = datetime(2025, 11, 22, 13, 15, 0, tzinfo=ZoneInfo("Europe/Oslo"))

    mock_period_calc = Mock()
    mock_period_calc.calculate_periods_for_price_info.return_value = {
        "best_price": [],
        "peak_price": [],
    }

    transformer = TibberPricesDataTransformer(
        config_entry=config_entry,
        log_prefix="[Test]",
        calculate_periods_fn=mock_period_calc.calculate_periods_for_price_info,
        time=time_service,
    )

    data = {
        "timestamp": current_time,
        "home_id": "home_123",
        "price_info": create_price_intervals(0) + create_price_intervals(1),  # Today + Tomorrow
        "currency": "EUR",
    }

    # First transformation
    result_1 = transformer.transform_data(data)
    assert result_1 is not None

    # Second call with SAME config and timestamp should use cache
    result_1_cached = transformer.transform_data(data)
    assert result_1_cached is result_1  # SAME object

    # Change config (note: in real system, config change triggers coordinator reload)
    config_entry.options = {
        "price_rating_threshold_low": 80.0,  # Changed
        "price_rating_threshold_high": 95.0,  # Changed
    }

    # Call with SAME timestamp but DIFFERENT config
    # Current behavior: Still uses cache (acceptable, see docstring)
    result_2 = transformer.transform_data(data)
    assert result_2 is result_1  # SAME object (cache preserved)


@pytest.mark.unit
def test_cache_preserved_when_neither_timestamp_nor_config_changed() -> None:
    """
    Test that cache is PRESERVED when both timestamp and config stay the same.

    This ensures we're not invalidating cache unnecessarily.
    """
    config_entry = Mock()
    config_entry.entry_id = "test_entry"
    config_entry.data = {"home_id": "home_123"}
    config_entry.options = {
        "price_rating_threshold_low": 75.0,
        "price_rating_threshold_high": 90.0,
    }

    time_service = TibberPricesTimeService()
    current_time = datetime(2025, 11, 22, 13, 15, 0, tzinfo=ZoneInfo("Europe/Oslo"))

    mock_period_calc = Mock()
    mock_period_calc.calculate_periods_for_price_info.return_value = {
        "best_price": [],
        "peak_price": [],
    }

    transformer = TibberPricesDataTransformer(
        config_entry=config_entry,
        log_prefix="[Test]",
        calculate_periods_fn=mock_period_calc.calculate_periods_for_price_info,
        time=time_service,
    )

    data = {
        "timestamp": current_time,
        "home_id": "home_123",
        "price_info": create_price_intervals(0) + create_price_intervals(1),  # Today + Tomorrow
        "currency": "EUR",
    }

    # Multiple calls with unchanged data/config should all use cache
    result_1 = transformer.transform_data(data)
    result_2 = transformer.transform_data(data)
    result_3 = transformer.transform_data(data)

    assert result_1 is result_2 is result_3  # ALL same object (cached)

    # Verify period calculation was only called ONCE (during first transform)
    assert mock_period_calc.calculate_periods_for_price_info.call_count == 1
