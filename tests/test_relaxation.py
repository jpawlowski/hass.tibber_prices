"""Focused regression tests for relaxation phase sequencing."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import Mock

import pytest

from custom_components.tibber_prices.coordinator.period_handlers import core as core_module
from custom_components.tibber_prices.coordinator.period_handlers.relaxation import relax_all_prices
from custom_components.tibber_prices.coordinator.period_handlers.types import TibberPricesPeriodConfig
from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService
from homeassistant.util import dt as dt_util


def _create_interval(base_time, offset: int, price: float, level: str) -> dict:
    """Create one quarter-hour interval for relaxation tests."""
    return {
        "startsAt": base_time + timedelta(minutes=offset * 15),
        "total": price,
        "level": level,
    }


@pytest.mark.unit
@pytest.mark.freeze_time("2025-11-22 12:00:00+01:00")
def test_relaxation_preserves_level_filter_before_trying_any(monkeypatch: pytest.MonkeyPatch) -> None:
    """Relaxation should try flex-only phases before dropping the configured level filter."""
    base_time = dt_util.parse_datetime("2025-11-22T12:00:00+01:00")
    assert base_time is not None

    mock_coordinator = Mock()
    mock_coordinator.config_entry = Mock()
    time_service = TibberPricesTimeService(mock_coordinator)
    time_service.now = Mock(return_value=base_time)

    all_prices = [
        _create_interval(base_time, 0, 0.18, "CHEAP"),
        _create_interval(base_time, 1, 0.19, "CHEAP"),
        _create_interval(base_time, 2, 0.22, "NORMAL"),
        _create_interval(base_time, 3, 0.31, "EXPENSIVE"),
    ]
    config = TibberPricesPeriodConfig(
        reverse_sort=False,
        flex=0.15,
        min_distance_from_avg=5.0,
        min_period_length=60,
        level_filter="cheap",
        gap_count=1,
    )

    calculate_periods_calls: list[tuple[float, str | None]] = []
    callback_args: list[str | None] = []

    def fake_calculate_periods(
        _all_prices: list[dict],
        *,
        config: TibberPricesPeriodConfig,
        time: TibberPricesTimeService,
        day_patterns_by_date: dict | None = None,
        time_range=None,
    ) -> dict:
        calculate_periods_calls.append((round(config.flex, 2), config.level_filter))
        return {"periods": [], "metadata": {}, "reference_data": {}}

    monkeypatch.setattr(core_module, "calculate_periods", fake_calculate_periods)

    relax_all_prices(
        all_prices=all_prices,
        config=config,
        min_periods=2,
        max_relaxation_attempts=2,
        should_show_callback=lambda level_override: callback_args.append(level_override) or True,
        baseline_periods=[],
        time=time_service,
        config_entry=mock_coordinator.config_entry,
    )

    assert callback_args == [None, "any", None, "any"]
    assert calculate_periods_calls == [
        (0.18, "cheap"),
        (0.18, "any"),
        (0.21, "cheap"),
        (0.21, "any"),
    ]
