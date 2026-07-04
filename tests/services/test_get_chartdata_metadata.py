"""Tests for get_chartdata metadata statistics calculation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from custom_components.tibber_prices.services.get_chartdata import _calculate_metadata


def _make_chart_data(prices: list[float], start: datetime | None = None) -> list[dict]:
    """Build minimal chart_data entries (start_time + price) for metadata calc."""
    base = start or datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    return [
        {
            "start_time": (base + timedelta(minutes=15 * i)).isoformat(),
            "price_per_kwh": price,
        }
        for i, price in enumerate(prices)
    ]


class TestCalculateMetadataMedian:
    """Regression coverage: median must use proper statistics.median, not naive indexing.

    A naive `sorted(data)[len(data)//2]` returns the upper-middle value for
    even-length datasets instead of averaging the two middle values. Since a
    full day always has an even interval count (96 quarter-hours, 24 hours),
    this bug silently affected nearly every "combined"/per-day median in the
    chartdata metadata response.
    """

    def test_median_for_even_length_dataset_is_averaged(self) -> None:
        """4 known prices: naive impl would report 30.0, correct median is 25.0."""
        chart_data = _make_chart_data([10.0, 20.0, 30.0, 40.0])

        metadata = _calculate_metadata(
            chart_data=chart_data,
            price_field="price_per_kwh",
            start_time_field="start_time",
            currency="EUR",
            resolution="interval",
            subunit_currency=False,
        )

        assert metadata["price_stats"]["combined"]["median"] == 25.0

    def test_median_for_odd_length_dataset_is_middle_value(self) -> None:
        """3 known prices: median is simply the middle value."""
        chart_data = _make_chart_data([10.0, 20.0, 30.0])

        metadata = _calculate_metadata(
            chart_data=chart_data,
            price_field="price_per_kwh",
            start_time_field="start_time",
            currency="EUR",
            resolution="interval",
            subunit_currency=False,
        )

        assert metadata["price_stats"]["combined"]["median"] == 20.0

    def test_median_position_reflects_corrected_median(self) -> None:
        """median_position must be derived from the corrected median, not the naive one."""
        chart_data = _make_chart_data([10.0, 20.0, 30.0, 40.0])

        metadata = _calculate_metadata(
            chart_data=chart_data,
            price_field="price_per_kwh",
            start_time_field="start_time",
            currency="EUR",
            resolution="interval",
            subunit_currency=False,
        )

        combined = metadata["price_stats"]["combined"]
        # median=25.0, min=10.0, max=40.0 -> position = (25-10)/(40-10) = 0.5
        assert combined["median_position"] == 0.5
