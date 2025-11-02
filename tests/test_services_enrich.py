"""Test that min/max/average include enriched attributes."""

from datetime import datetime

import pytest

from custom_components.tibber_prices.services import _get_price_stat, _get_price_stats


def test_min_max_intervals_include_enriched_attributes():
    """Test that min/max intervals contain difference and rating_level."""
    merged = [
        {
            "start_time": "2025-11-01T00:00:00+01:00",
            "end_time": "2025-11-01T01:00:00+01:00",
            "start_dt": datetime(2025, 11, 1, 0, 0),
            "price": 0.15,
            "price_minor": 15,
            "difference": -10.5,
            "rating_level": "LOW",
            "level": "VERY_CHEAP",
        },
        {
            "start_time": "2025-11-01T01:00:00+01:00",
            "end_time": "2025-11-01T02:00:00+01:00",
            "start_dt": datetime(2025, 11, 1, 1, 0),
            "price": 0.25,
            "price_minor": 25,
            "difference": 5.0,
            "rating_level": "NORMAL",
            "level": "NORMAL",
        },
        {
            "start_time": "2025-11-01T02:00:00+01:00",
            "end_time": "2025-11-01T03:00:00+01:00",
            "start_dt": datetime(2025, 11, 1, 2, 0),
            "price": 0.35,
            "price_minor": 35,
            "difference": 25.3,
            "rating_level": "HIGH",
            "level": "EXPENSIVE",
        },
    ]

    stats = _get_price_stats(merged)

    # Verify min interval has all attributes
    assert stats.price_min == 0.15
    assert stats.price_min_interval is not None
    assert stats.price_min_interval["difference"] == -10.5
    assert stats.price_min_interval["rating_level"] == "LOW"
    assert stats.price_min_interval["level"] == "VERY_CHEAP"

    # Verify max interval has all attributes
    assert stats.price_max == 0.35
    assert stats.price_max_interval is not None
    assert stats.price_max_interval["difference"] == 25.3
    assert stats.price_max_interval["rating_level"] == "HIGH"
    assert stats.price_max_interval["level"] == "EXPENSIVE"

    # Verify average price is calculated
    assert stats.price_avg == pytest.approx((0.15 + 0.25 + 0.35) / 3, rel=1e-4)


def test_get_price_stat_returns_full_interval():
    """Test that _get_price_stat returns the complete interval dict."""
    merged = [
        {
            "start_time": "2025-11-01T00:00:00+01:00",
            "price": 0.10,
            "difference": -15.0,
            "rating_level": "LOW",
        },
        {
            "start_time": "2025-11-01T01:00:00+01:00",
            "price": 0.20,
            "difference": 0.0,
            "rating_level": "NORMAL",
        },
    ]

    min_price, min_interval = _get_price_stat(merged, "min")
    max_price, max_interval = _get_price_stat(merged, "max")

    # Min should be first interval
    assert min_price == 0.10
    assert min_interval is not None
    assert min_interval["difference"] == -15.0
    assert min_interval["rating_level"] == "LOW"

    # Max should be second interval
    assert max_price == 0.20
    assert max_interval is not None
    assert max_interval["difference"] == 0.0
    assert max_interval["rating_level"] == "NORMAL"


def test_empty_merged_returns_none_intervals():
    """Test that empty merged list returns None for intervals."""
    stats = _get_price_stats([])

    assert stats.price_min == 0
    assert stats.price_min_interval is None
    assert stats.price_max == 0
    assert stats.price_max_interval is None
    assert stats.price_avg == 0
