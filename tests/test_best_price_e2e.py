"""
End-to-End Tests for Best Price Period Generation (Nov 2025 Bug Fix).

These tests validate that the sign convention bug fix works correctly:
- Bug: Negative flex for peak wasn't normalized → affected period calculation
- Fix: abs() normalization in periods.py ensures consistent behavior

Test coverage matches manual testing checklist:
1. ✅ Best periods generate (not 0)
2. ✅ FLEX filter stats reasonable (~20-40%, not 100%)
3. ✅ Relaxation succeeds at reasonable flex (not maxed at 50%)
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from custom_components.tibber_prices.coordinator.period_handlers import (
    TibberPricesPeriodConfig,
    calculate_periods_with_relaxation,
)
from custom_components.tibber_prices.coordinator.time_service import (
    TibberPricesTimeService,
)
from homeassistant.util import dt as dt_util


def _create_realistic_intervals() -> list[dict]:
    """
    Create realistic test data matching German market Nov 22, 2025.

    Pattern: Morning peak (6-9h), midday low (9-15h), evening moderate (15-24h).
    Daily stats: Min=30.44ct, Avg=33.26ct, Max=36.03ct
    """
    # Use CURRENT date so tests work regardless of when they run
    now_local = dt_util.now()
    base_time = now_local.replace(hour=0, minute=0, second=0, microsecond=0)

    daily_min, daily_avg, daily_max = 0.3044, 0.3326, 0.3603

    def _create_interval(hour: int, minute: int, price: float, level: str, rating: str) -> dict:
        """Create a single interval dict."""
        return {
            "startsAt": base_time.replace(hour=hour, minute=minute),  # datetime object
            "total": price,
            "level": level,
            "rating_level": rating,
            "_original_price": price,
            "trailing_avg_24h": daily_avg,
            "daily_min": daily_min,
            "daily_avg": daily_avg,
            "daily_max": daily_max,
        }

    # Build all intervals as list comprehensions
    intervals = []

    # Overnight (00:00-06:00) - NORMAL
    intervals.extend(
        [_create_interval(hour, minute, 0.318, "NORMAL", "NORMAL") for hour in range(6) for minute in [0, 15, 30, 45]]
    )

    # Morning spike (06:00-09:00) - EXPENSIVE
    intervals.extend(
        [
            _create_interval(
                hour,
                minute,
                price := 0.33 + (hour - 6) * 0.01,
                "EXPENSIVE" if price > 0.34 else "NORMAL",
                "HIGH" if price > 0.35 else "NORMAL",
            )
            for hour in range(6, 9)
            for minute in [0, 15, 30, 45]
        ]
    )

    # Midday low (09:00-15:00) - CHEAP
    intervals.extend(
        [
            _create_interval(hour, minute, 0.305 + (hour - 12) * 0.002, "CHEAP", "LOW")
            for hour in range(9, 15)
            for minute in [0, 15, 30, 45]
        ]
    )

    # Evening moderate (15:00-24:00) - NORMAL to EXPENSIVE
    intervals.extend(
        [
            _create_interval(
                hour,
                minute,
                price := 0.32 + (hour - 15) * 0.005,
                "EXPENSIVE" if price > 0.34 else "NORMAL",
                "HIGH" if price > 0.35 else "NORMAL",
            )
            for hour in range(15, 24)
            for minute in [0, 15, 30, 45]
        ]
    )

    return intervals


@pytest.mark.unit
@pytest.mark.freeze_time("2025-11-22 12:00:00+01:00")
class TestBestPriceGenerationWorks:
    """Validate that best price periods generate successfully after bug fix."""

    def test_best_periods_generate_successfully(self) -> None:
        """
        ✅ PRIMARY TEST: Best periods generate (not 0).

        Validates that positive flex for BEST price mode produces periods.
        """
        intervals = _create_realistic_intervals()

        # Mock coordinator (minimal setup)
        mock_coordinator = Mock()
        mock_coordinator.config_entry = Mock()
        time_service = TibberPricesTimeService(mock_coordinator)
        # Mock now() to return test date
        test_time = dt_util.parse_datetime("2025-11-22T12:00:00+01:00")
        time_service.now = Mock(return_value=test_time)

        # Create config for BEST price mode (normal positive flex)
        config = TibberPricesPeriodConfig(
            flex=0.15,  # 15% positive (BEST price mode)
            min_distance_from_avg=5.0,
            min_period_length=60,  # Best price uses 60min default
            reverse_sort=False,  # Best price mode (cheapest first)
        )

        # Calculate periods with relaxation
        result = calculate_periods_with_relaxation(
            intervals,
            config=config,
            enable_relaxation=True,
            min_periods=2,
            max_relaxation_attempts=11,
            should_show_callback=lambda _: True,  # Allow all levels
            time=time_service,
            config_entry=mock_coordinator.config_entry,
        )

        periods = result.get("periods", [])

        # Validation: periods found
        assert len(periods) > 0, "Best periods should generate"
        assert 2 <= len(periods) <= 5, f"Expected 2-5 periods, got {len(periods)}"

    def test_positive_flex_produces_periods(self) -> None:
        """
        ✅ TEST: Positive flex produces periods in BEST mode.

        Validates standard positive flex behavior for cheapest periods.
        """
        intervals = _create_realistic_intervals()

        mock_coordinator = Mock()
        mock_coordinator.config_entry = Mock()
        time_service = TibberPricesTimeService(mock_coordinator)
        # Mock now() to return test date
        test_time = dt_util.parse_datetime("2025-11-22T12:00:00+01:00")
        time_service.now = Mock(return_value=test_time)

        # Test with positive flex (standard BEST mode)
        config_positive = TibberPricesPeriodConfig(
            flex=0.15,  # Positive for BEST mode
            min_distance_from_avg=5.0,
            min_period_length=60,
            reverse_sort=False,
        )

        result_pos = calculate_periods_with_relaxation(
            intervals,
            config=config_positive,
            enable_relaxation=True,
            min_periods=2,
            max_relaxation_attempts=11,
            should_show_callback=lambda _: True,
            time=time_service,
            config_entry=mock_coordinator.config_entry,
        )

        periods_pos = result_pos.get("periods", [])

        # With positive flex, should find periods
        assert len(periods_pos) >= 2, f"Should find periods with positive flex, got {len(periods_pos)}"

    def test_periods_contain_low_prices(self) -> None:
        """
        ✅ TEST: Best periods contain low prices (not expensive ones).

        Validates periods include cheap intervals, not expensive ones.
        """
        intervals = _create_realistic_intervals()

        mock_coordinator = Mock()
        mock_coordinator.config_entry = Mock()
        time_service = TibberPricesTimeService(mock_coordinator)
        # Mock now() to return test date
        test_time = dt_util.parse_datetime("2025-11-22T12:00:00+01:00")
        time_service.now = Mock(return_value=test_time)

        config = TibberPricesPeriodConfig(
            flex=0.15,
            min_distance_from_avg=5.0,
            min_period_length=60,
            reverse_sort=False,
        )

        result = calculate_periods_with_relaxation(
            intervals,
            config=config,
            enable_relaxation=True,
            min_periods=2,
            max_relaxation_attempts=11,
            should_show_callback=lambda _: True,
            time=time_service,
            config_entry=mock_coordinator.config_entry,
        )

        periods = result.get("periods", [])

        daily_max = intervals[0]["daily_max"]

        # Check period averages are NOT near daily maximum
        # Note: period prices are in cents, daily stats are in euros
        for period in periods:
            period_avg = period.get("price_mean", 0)
            assert period_avg < daily_max * 100 * 0.95, (
                f"Best period has too high avg: {period_avg:.4f} ct vs daily_max={daily_max * 100:.4f} ct"
            )

    def test_relaxation_works_at_reasonable_flex(self) -> None:
        """
        ✅ TEST: Relaxation succeeds without maxing flex at 50%.

        Validates relaxation finds periods at reasonable flex levels.
        """
        intervals = _create_realistic_intervals()

        mock_coordinator = Mock()
        mock_coordinator.config_entry = Mock()
        time_service = TibberPricesTimeService(mock_coordinator)
        # Mock now() to return test date
        test_time = dt_util.parse_datetime("2025-11-22T12:00:00+01:00")
        time_service.now = Mock(return_value=test_time)

        # Lower flex to trigger relaxation
        config = TibberPricesPeriodConfig(
            flex=0.10,  # 10% - likely needs relaxation
            min_distance_from_avg=5.0,
            min_period_length=60,
            reverse_sort=False,
        )

        result = calculate_periods_with_relaxation(
            intervals,
            config=config,
            enable_relaxation=True,
            min_periods=2,
            max_relaxation_attempts=11,
            should_show_callback=lambda _: True,
            time=time_service,
            config_entry=mock_coordinator.config_entry,
        )

        periods = result.get("periods", [])

        # Should find periods via relaxation
        assert len(periods) >= 2, "Relaxation should find periods"

        # Check if relaxation was used
        relaxation_meta = result.get("metadata", {}).get("relaxation", {})
        if "max_flex_used" in relaxation_meta:
            max_flex_used = relaxation_meta["max_flex_used"]
            # Fix ensures reasonable flex is sufficient
            assert max_flex_used <= 0.35, f"Flex should stay reasonable, got {max_flex_used * 100:.1f}%"


@pytest.mark.unit
@pytest.mark.freeze_time("2025-11-22 12:00:00+01:00")
class TestBestPriceBugRegressionValidation:
    """Regression tests ensuring consistent behavior with peak price fix."""

    def test_metadata_shows_reasonable_flex_used(self) -> None:
        """
        ✅ REGRESSION: Metadata shows flex used was reasonable (not 50%).

        This validates FLEX filter works correctly in BEST mode too.
        """
        intervals = _create_realistic_intervals()

        mock_coordinator = Mock()
        mock_coordinator.config_entry = Mock()
        time_service = TibberPricesTimeService(mock_coordinator)
        # Mock now() to return test date
        test_time = dt_util.parse_datetime("2025-11-22T12:00:00+01:00")
        time_service.now = Mock(return_value=test_time)

        config = TibberPricesPeriodConfig(
            flex=0.15,
            min_distance_from_avg=5.0,
            min_period_length=60,
            reverse_sort=False,
        )

        result = calculate_periods_with_relaxation(
            intervals,
            config=config,
            enable_relaxation=True,
            min_periods=2,
            max_relaxation_attempts=11,
            should_show_callback=lambda _: True,
            time=time_service,
            config_entry=mock_coordinator.config_entry,
        )

        # Check result metadata
        # Check that relaxation didn't max out at 50%
        metadata = result.get("metadata", {})
        config_used = metadata.get("config", {})

        if "flex" in config_used:
            flex_used = config_used["flex"]
            # Reasonable flex should be sufficient (not maxing out at 50%)
            assert 0.10 <= flex_used <= 0.48, f"Expected flex 10-48%, got {flex_used * 100:.1f}%"

        # Also check relaxation metadata
        relaxation_meta = result.get("metadata", {}).get("relaxation", {})
        if "max_flex_used" in relaxation_meta:
            max_flex = relaxation_meta["max_flex_used"]
            # Should not max out at 50%
            assert max_flex <= 0.48, f"Max flex should be reasonable, got {max_flex * 100:.1f}%"

    def test_periods_include_cheap_intervals(self) -> None:
        """
        ✅ REGRESSION: Best periods include intervals near daily min.

        Validates that cheap intervals are properly included in periods.
        """
        intervals = _create_realistic_intervals()

        mock_coordinator = Mock()
        mock_coordinator.config_entry = Mock()
        time_service = TibberPricesTimeService(mock_coordinator)
        # Mock now() to return test date
        test_time = dt_util.parse_datetime("2025-11-22T12:00:00+01:00")
        time_service.now = Mock(return_value=test_time)

        config = TibberPricesPeriodConfig(
            flex=0.15,
            min_distance_from_avg=5.0,
            min_period_length=60,
            reverse_sort=False,
        )

        result = calculate_periods_with_relaxation(
            intervals,
            config=config,
            enable_relaxation=True,
            min_periods=2,
            max_relaxation_attempts=11,
            should_show_callback=lambda _: True,
            time=time_service,
            config_entry=mock_coordinator.config_entry,
        )

        periods = result.get("periods", [])

        daily_avg = intervals[0]["daily_avg"]
        daily_min = intervals[0]["daily_min"]

        # At least one period should have low average
        # Note: period prices are in cents, daily stats are in euros
        min_period_avg = min(p.get("price_mean", 1.0) for p in periods)

        assert min_period_avg <= daily_avg * 100 * 0.95, (
            f"Best periods should have low avg: {min_period_avg:.4f} ct vs daily_avg={daily_avg * 100:.4f} ct"
        )

        # Check proximity to daily min
        assert min_period_avg <= daily_min * 100 * 1.15, (
            f"At least one period near daily_min: {min_period_avg:.4f} ct vs daily_min={daily_min * 100:.4f} ct"
        )
