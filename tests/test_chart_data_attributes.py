"""Tests for the chart_data_export sensor attribute builder."""

from __future__ import annotations

from datetime import UTC, datetime

from custom_components.tibber_prices.sensor.chart_data import build_chart_data_attributes

_NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
_RESPONSE = {"data": [{"start_time": "2026-01-01T12:00:00+00:00", "price_per_kwh": 0.25}]}


def test_currency_is_exposed_between_timestamp_and_data() -> None:
    """Currency lets attribute-reading consumers (e.g. tibber-graph) skip guessing it."""
    attrs = build_chart_data_attributes(_RESPONSE, _NOW, None, currency="EUR")

    assert attrs is not None
    assert list(attrs) == ["timestamp", "currency", "data"]
    assert attrs["currency"] == "EUR"
    assert attrs["data"] == _RESPONSE["data"]


def test_currency_omitted_when_unknown() -> None:
    """No currency known yet -> attribute is absent, not None."""
    attrs = build_chart_data_attributes(_RESPONSE, _NOW, None)

    assert attrs is not None
    assert "currency" not in attrs


def test_currency_kept_when_service_failed() -> None:
    """Error state still carries timestamp, error and currency."""
    attrs = build_chart_data_attributes(None, _NOW, "boom", currency="NOK")

    assert attrs == {"timestamp": _NOW, "error": "boom", "currency": "NOK"}
