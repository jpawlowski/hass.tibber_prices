"""Test that min/max/average include enriched attributes."""

from datetime import UTC, datetime

import pytest

from custom_components.tibber_prices.services import _get_price_stat, _get_price_stats

# Constants for service enrichment tests
PRICE_MIN = 0.15
PRICE_MID = 0.25
PRICE_MAX = 0.35
PRICE_MINOR_MIN = 15
PRICE_MINOR_MID = 25
PRICE_MINOR_MAX = 35
DIFF_MIN = -10.5
DIFF_MID = 5.0
DIFF_MAX = 25.3
DIFF_MIN_LOW = -15.0
DIFF_MID_ZERO = 0.0
PRICE_LOW = 0.10
PRICE_HIGH = 0.20


def test_min_max_intervals_include_enriched_attributes() -> None:
    """Test that min/max intervals contain difference and rating_level."""
    merged = [
        {
            "start_time": "2025-11-01T00:00:00+01:00",
            "end_time": "2025-11-01T01:00:00+01:00",
            "start_dt": datetime(2025, 11, 1, 0, 0, tzinfo=UTC),
            "price": PRICE_MIN,
            "price_minor": PRICE_MINOR_MIN,
            "difference": DIFF_MIN,
            "rating_level": "LOW",
            "level": "VERY_CHEAP",
        },
        {
            "start_time": "2025-11-01T01:00:00+01:00",
            "end_time": "2025-11-01T02:00:00+01:00",
            "start_dt": datetime(2025, 11, 1, 1, 0, tzinfo=UTC),
            "price": PRICE_MID,
            "price_minor": PRICE_MINOR_MID,
            "difference": DIFF_MID,
            "rating_level": "NORMAL",
            "level": "NORMAL",
        },
        {
            "start_time": "2025-11-01T02:00:00+01:00",
            "end_time": "2025-11-01T03:00:00+01:00",
            "start_dt": datetime(2025, 11, 1, 2, 0, tzinfo=UTC),
            "price": PRICE_MAX,
            "price_minor": PRICE_MINOR_MAX,
            "difference": DIFF_MAX,
            "rating_level": "HIGH",
            "level": "EXPENSIVE",
        },
    ]

    stats = _get_price_stats(merged)

    # Verify min interval has all attributes
    assert stats.price_min == PRICE_MIN  # noqa: S101
    assert stats.price_min_interval is not None  # noqa: S101
    assert stats.price_min_interval["difference"] == DIFF_MIN  # noqa: S101
    assert stats.price_min_interval["rating_level"] == "LOW"  # noqa: S101
    assert stats.price_min_interval["level"] == "VERY_CHEAP"  # noqa: S101

    # Verify max interval has all attributes
    assert stats.price_max == PRICE_MAX  # noqa: S101
    assert stats.price_max_interval is not None  # noqa: S101
    assert stats.price_max_interval["difference"] == DIFF_MAX  # noqa: S101
    assert stats.price_max_interval["rating_level"] == "HIGH"  # noqa: S101
    assert stats.price_max_interval["level"] == "EXPENSIVE"  # noqa: S101

    # Verify average price is calculated
    assert stats.price_avg == pytest.approx(  # noqa: S101
        (PRICE_MIN + PRICE_MID + PRICE_MAX) / 3, rel=1e-4
    )


def test_get_price_stat_returns_full_interval() -> None:
    """Test that _get_price_stat returns the complete interval dict."""
    merged = [
        {
            "start_time": "2025-11-01T00:00:00+01:00",
            "price": PRICE_LOW,
            "difference": DIFF_MIN_LOW,
            "rating_level": "LOW",
        },
        {
            "start_time": "2025-11-01T01:00:00+01:00",
            "price": PRICE_HIGH,
            "difference": DIFF_MID_ZERO,
            "rating_level": "NORMAL",
        },
    ]

    min_price, min_interval = _get_price_stat(merged, "min")
    max_price, max_interval = _get_price_stat(merged, "max")

    # Min should be first interval
    assert min_price == PRICE_LOW  # noqa: S101
    assert min_interval is not None  # noqa: S101
    assert min_interval["difference"] == DIFF_MIN_LOW  # noqa: S101
    assert min_interval["rating_level"] == "LOW"  # noqa: S101

    # Max should be second interval
    assert max_price == PRICE_HIGH  # noqa: S101
    assert max_interval is not None  # noqa: S101
    assert max_interval["difference"] == DIFF_MID_ZERO  # noqa: S101
    assert max_interval["rating_level"] == "NORMAL"  # noqa: S101


def test_empty_merged_returns_none_intervals() -> None:
    """Test that empty merged list returns None for intervals."""
    stats = _get_price_stats([])

    assert stats.price_min == 0  # noqa: S101
    assert stats.price_min_interval is None  # noqa: S101
    assert stats.price_max == 0  # noqa: S101
    assert stats.price_max_interval is None  # noqa: S101
    assert stats.price_avg == 0  # noqa: S101
