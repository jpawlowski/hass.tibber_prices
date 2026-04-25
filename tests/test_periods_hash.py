"""Regression tests for period calculation cache hashing."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from unittest.mock import Mock

import pytest

from custom_components.tibber_prices import const as _const
from custom_components.tibber_prices.coordinator import periods as periods_module
from custom_components.tibber_prices.coordinator.periods import TibberPricesPeriodCalculator
from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService
from homeassistant.util import dt as dt_util


def _create_hash_interval(starts_at: str, price: float, level: str, rating_level: str, difference: float) -> dict:
    """Create one interval for period hash tests."""
    parsed = dt_util.parse_datetime(starts_at)
    assert parsed is not None
    return {
        "startsAt": parsed,
        "total": price,
        "level": level,
        "rating_level": rating_level,
        "difference": difference,
    }


def _create_hash_price_info() -> list[dict]:
    """Create minimal today/tomorrow data for cache hash tests."""
    return [
        _create_hash_interval("2025-11-22T00:00:00+01:00", 0.11, "CHEAP", "LOW", -12.0),
        _create_hash_interval("2025-11-22T00:15:00+01:00", 0.12, "NORMAL", "NORMAL", -4.0),
        _create_hash_interval("2025-11-23T00:00:00+01:00", 0.13, "NORMAL", "NORMAL", 0.0),
        _create_hash_interval("2025-11-23T00:15:00+01:00", 0.14, "EXPENSIVE", "HIGH", 12.0),
    ]


def _compute_hash(calculator: TibberPricesPeriodCalculator, price_info: list[dict]) -> str:
    """Call the internal periods hash helper without tripping the private-access lint rule."""
    return calculator._compute_periods_hash(price_info)  # noqa: SLF001 - targeted cache-key regression check


def _create_calculator(options: dict[str, Any]) -> TibberPricesPeriodCalculator:
    """Create a period calculator with deterministic test time."""
    calculator = TibberPricesPeriodCalculator(Mock(options=options), "[test]")
    reference_time = dt_util.parse_datetime("2025-11-22T12:00:00+01:00")
    assert reference_time is not None
    calculator.time = TibberPricesTimeService(reference_time=reference_time)
    return calculator


@pytest.mark.unit
@pytest.mark.freeze_time("2025-11-22 12:00:00+01:00")
class TestPeriodsHash:
    """Validate that same-day value changes invalidate the period cache."""

    def test_hash_changes_when_same_day_price_changes(self) -> None:
        """Changing an interval price with identical timestamps must change the cache hash."""
        calculator = TibberPricesPeriodCalculator(Mock(options={}), "[test]")
        original = _create_hash_price_info()
        updated = deepcopy(original)
        updated[1]["total"] = 0.125

        assert _compute_hash(calculator, original) != _compute_hash(calculator, updated)

    def test_hash_changes_when_same_day_level_changes(self) -> None:
        """Changing level/rating metadata with identical timestamps must change the cache hash."""
        calculator = TibberPricesPeriodCalculator(Mock(options={}), "[test]")
        original = _create_hash_price_info()
        updated = deepcopy(original)
        updated[1]["level"] = "CHEAP"
        updated[1]["rating_level"] = "LOW"
        updated[1]["difference"] = -10.0

        assert _compute_hash(calculator, original) != _compute_hash(calculator, updated)


@pytest.mark.unit
@pytest.mark.freeze_time("2025-11-22 12:00:00+01:00")
class TestPeriodConfigNormalization:
    """Validate numeric period config values degrade cleanly to defaults."""

    def test_get_period_config_falls_back_for_invalid_numeric_options(self) -> None:
        """Malformed config values should fall back to defaults instead of raising."""
        calculator = _create_calculator(
            {
                "flexibility_settings": {
                    _const.CONF_BEST_PRICE_FLEX: "bad-flex",
                    _const.CONF_BEST_PRICE_MIN_DISTANCE_FROM_AVG: "bad-distance",
                },
                "period_settings": {
                    _const.CONF_BEST_PRICE_MIN_PERIOD_LENGTH: "bad-min-length",
                },
                "extension_settings": {
                    _const.CONF_BEST_PRICE_MAX_EXTENSION_INTERVALS: "bad-extension",
                    _const.CONF_BEST_PRICE_GEOMETRIC_FLEX: "bad-geometric",
                    _const.CONF_BEST_PRICE_SEGMENT_MIN_PERIODS: "bad-segments",
                },
            }
        )

        config = calculator.get_period_config(reverse_sort=False)

        assert config["flex"] == abs(_const.DEFAULT_BEST_PRICE_FLEX) / 100
        assert config["min_distance_from_avg"] == abs(_const.DEFAULT_BEST_PRICE_MIN_DISTANCE_FROM_AVG)
        assert config["min_period_length"] == _const.DEFAULT_BEST_PRICE_MIN_PERIOD_LENGTH
        assert config["max_extension_intervals"] == _const.DEFAULT_BEST_PRICE_MAX_EXTENSION_INTERVALS
        assert config["geometric_extra_flex"] == _const.DEFAULT_BEST_PRICE_GEOMETRIC_FLEX / 100
        assert config["segment_min_periods"] == _const.DEFAULT_BEST_PRICE_SEGMENT_MIN_PERIODS

    def test_should_show_periods_falls_back_for_invalid_gap_count(self) -> None:
        """Malformed gap_count should not break day-level filter checks."""
        calculator = _create_calculator(
            {
                "period_settings": {
                    _const.CONF_BEST_PRICE_MAX_LEVEL: "cheap",
                    _const.CONF_BEST_PRICE_MAX_LEVEL_GAP_COUNT: "bad-gap-count",
                }
            }
        )

        assert (
            calculator.should_show_periods(
                [
                    _create_hash_interval(
                        "2025-11-22T00:00:00+01:00", 0.11, level="CHEAP", rating_level="LOW", difference=-12.0
                    ),
                    _create_hash_interval(
                        "2025-11-22T00:15:00+01:00", 0.10, level="CHEAP", rating_level="LOW", difference=-14.0
                    ),
                    _create_hash_interval(
                        "2025-11-22T00:30:00+01:00", 0.09, level="CHEAP", rating_level="LOW", difference=-16.0
                    ),
                    _create_hash_interval(
                        "2025-11-22T00:45:00+01:00", 0.08, level="CHEAP", rating_level="LOW", difference=-18.0
                    ),
                ],
                reverse_sort=False,
            )
            is True
        )

    def test_calculate_periods_for_price_info_falls_back_for_invalid_runtime_numbers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Runtime period calculation should use defaults when numeric overrides are malformed."""
        captured_calls: list[dict[str, Any]] = []

        def _fake_calculate_periods_with_relaxation(
            all_prices: list[dict[str, Any]],
            *,
            config: Any,
            enable_relaxation: bool,
            min_periods: int,
            max_relaxation_attempts: int,
            should_show_callback: Any,
            time: Any,
            config_entry: Any,
            day_patterns_by_date: Any,
        ) -> dict[str, Any]:
            captured_calls.append(
                {
                    "reverse_sort": config.reverse_sort,
                    "min_periods": min_periods,
                    "max_relaxation_attempts": max_relaxation_attempts,
                    "gap_count": config.gap_count,
                    "threshold_low": config.threshold_low,
                    "threshold_high": config.threshold_high,
                    "threshold_volatility_moderate": config.threshold_volatility_moderate,
                    "threshold_volatility_high": config.threshold_volatility_high,
                    "threshold_volatility_very_high": config.threshold_volatility_very_high,
                }
            )
            return {
                "periods": [],
                "intervals": [],
                "metadata": {
                    "total_intervals": len(all_prices),
                    "total_periods": 0,
                    "config": {},
                    "relaxation": {"relaxation_active": enable_relaxation, "relaxation_attempted": enable_relaxation},
                },
            }

        monkeypatch.setattr(
            periods_module, "calculate_periods_with_relaxation", _fake_calculate_periods_with_relaxation
        )

        calculator = _create_calculator(
            {
                _const.CONF_PRICE_RATING_THRESHOLD_LOW: "bad-threshold-low",
                _const.CONF_PRICE_RATING_THRESHOLD_HIGH: "bad-threshold-high",
                _const.CONF_VOLATILITY_THRESHOLD_MODERATE: "bad-vol-moderate",
                _const.CONF_VOLATILITY_THRESHOLD_HIGH: "bad-vol-high",
                _const.CONF_VOLATILITY_THRESHOLD_VERY_HIGH: "bad-vol-very-high",
                "relaxation_and_target_periods": {
                    _const.CONF_ENABLE_MIN_PERIODS_BEST: True,
                    _const.CONF_ENABLE_MIN_PERIODS_PEAK: True,
                    _const.CONF_MIN_PERIODS_BEST: "bad-min-best",
                    _const.CONF_RELAXATION_ATTEMPTS_BEST: "bad-attempts-best",
                    _const.CONF_MIN_PERIODS_PEAK: "bad-min-peak",
                    _const.CONF_RELAXATION_ATTEMPTS_PEAK: "bad-attempts-peak",
                },
                "period_settings": {
                    _const.CONF_BEST_PRICE_MAX_LEVEL_GAP_COUNT: "bad-best-gap",
                    _const.CONF_PEAK_PRICE_MAX_LEVEL_GAP_COUNT: "bad-peak-gap",
                },
            }
        )

        result = calculator.calculate_periods_for_price_info(_create_hash_price_info())

        assert result["best_price"]["metadata"]["total_periods"] == 0
        assert result["peak_price"]["metadata"]["total_periods"] == 0
        assert len(captured_calls) == 2

        best_call = next(call for call in captured_calls if call["reverse_sort"] is False)
        peak_call = next(call for call in captured_calls if call["reverse_sort"] is True)

        assert best_call["min_periods"] == _const.DEFAULT_MIN_PERIODS_BEST
        assert best_call["max_relaxation_attempts"] == _const.DEFAULT_RELAXATION_ATTEMPTS_BEST
        assert best_call["gap_count"] == _const.DEFAULT_BEST_PRICE_MAX_LEVEL_GAP_COUNT
        assert peak_call["min_periods"] == _const.DEFAULT_MIN_PERIODS_PEAK
        assert peak_call["max_relaxation_attempts"] == _const.DEFAULT_RELAXATION_ATTEMPTS_PEAK
        assert peak_call["gap_count"] == _const.DEFAULT_PEAK_PRICE_MAX_LEVEL_GAP_COUNT
        assert best_call["threshold_low"] == _const.DEFAULT_PRICE_RATING_THRESHOLD_LOW
        assert best_call["threshold_high"] == _const.DEFAULT_PRICE_RATING_THRESHOLD_HIGH
        assert best_call["threshold_volatility_moderate"] == _const.DEFAULT_VOLATILITY_THRESHOLD_MODERATE
        assert best_call["threshold_volatility_high"] == _const.DEFAULT_VOLATILITY_THRESHOLD_HIGH
        assert best_call["threshold_volatility_very_high"] == _const.DEFAULT_VOLATILITY_THRESHOLD_VERY_HIGH
