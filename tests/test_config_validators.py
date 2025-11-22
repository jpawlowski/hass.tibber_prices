"""Tests for config flow validators."""

from __future__ import annotations

import pytest

from custom_components.tibber_prices.config_flow_handlers.validators import (
    validate_best_price_distance_percentage,
    validate_distance_percentage,
    validate_flex_percentage,
    validate_gap_count,
    validate_min_periods,
    validate_period_length,
    validate_price_rating_threshold_high,
    validate_price_rating_threshold_low,
    validate_price_rating_thresholds,
    validate_price_trend_falling,
    validate_price_trend_rising,
    validate_relaxation_attempts,
    validate_volatility_threshold_high,
    validate_volatility_threshold_moderate,
    validate_volatility_threshold_very_high,
    validate_volatility_thresholds,
)
from custom_components.tibber_prices.const import (
    MAX_DISTANCE_PERCENTAGE,
    MAX_FLEX_PERCENTAGE,
    MAX_GAP_COUNT,
    MAX_MIN_PERIODS,
    MAX_PRICE_RATING_THRESHOLD_HIGH,
    MAX_PRICE_RATING_THRESHOLD_LOW,
    MAX_PRICE_TREND_FALLING,
    MAX_PRICE_TREND_RISING,
    MAX_RELAXATION_ATTEMPTS,
    MAX_VOLATILITY_THRESHOLD_HIGH,
    MAX_VOLATILITY_THRESHOLD_MODERATE,
    MAX_VOLATILITY_THRESHOLD_VERY_HIGH,
    MIN_GAP_COUNT,
    MIN_PERIOD_LENGTH,
    MIN_PRICE_RATING_THRESHOLD_HIGH,
    MIN_PRICE_RATING_THRESHOLD_LOW,
    MIN_PRICE_TREND_FALLING,
    MIN_PRICE_TREND_RISING,
    MIN_RELAXATION_ATTEMPTS,
    MIN_VOLATILITY_THRESHOLD_HIGH,
    MIN_VOLATILITY_THRESHOLD_MODERATE,
    MIN_VOLATILITY_THRESHOLD_VERY_HIGH,
)


class TestPeriodLengthValidation:
    """Test period length validation."""

    def test_valid_period_lengths(self) -> None:
        """Test valid period lengths (multiples of 15)."""
        assert validate_period_length(15) is True  # Minimum
        assert validate_period_length(30) is True
        assert validate_period_length(45) is True
        assert validate_period_length(60) is True
        assert validate_period_length(120) is True
        assert validate_period_length(MIN_PERIOD_LENGTH) is True

    def test_invalid_period_lengths(self) -> None:
        """Test invalid period lengths (not multiples of 15)."""
        assert validate_period_length(0) is False
        assert validate_period_length(10) is False
        assert validate_period_length(20) is False
        assert validate_period_length(25) is False
        assert validate_period_length(40) is False
        assert validate_period_length(-15) is False  # Negative


class TestFlexPercentageValidation:
    """Test flex percentage validation."""

    def test_valid_positive_flex(self) -> None:
        """Test valid positive flex values (Best Price)."""
        assert validate_flex_percentage(0) is True
        assert validate_flex_percentage(10) is True
        assert validate_flex_percentage(15) is True
        assert validate_flex_percentage(25) is True
        assert validate_flex_percentage(MAX_FLEX_PERCENTAGE) is True

    def test_valid_negative_flex(self) -> None:
        """Test valid negative flex values (Peak Price)."""
        assert validate_flex_percentage(-10) is True
        assert validate_flex_percentage(-20) is True
        assert validate_flex_percentage(-30) is True
        assert validate_flex_percentage(-MAX_FLEX_PERCENTAGE) is True

    def test_invalid_flex(self) -> None:
        """Test invalid flex values (out of bounds)."""
        assert validate_flex_percentage(MAX_FLEX_PERCENTAGE + 1) is False
        assert validate_flex_percentage(-MAX_FLEX_PERCENTAGE - 1) is False
        assert validate_flex_percentage(100) is False
        assert validate_flex_percentage(-100) is False


class TestMinPeriodsValidation:
    """Test minimum periods count validation."""

    def test_valid_min_periods(self) -> None:
        """Test valid min periods values."""
        assert validate_min_periods(1) is True
        assert validate_min_periods(2) is True
        assert validate_min_periods(3) is True
        assert validate_min_periods(MAX_MIN_PERIODS) is True

    def test_invalid_min_periods(self) -> None:
        """Test invalid min periods values."""
        assert validate_min_periods(0) is False
        assert validate_min_periods(-1) is False
        assert validate_min_periods(MAX_MIN_PERIODS + 1) is False


class TestDistancePercentageValidation:
    """Test distance from average percentage validation."""

    def test_valid_best_price_distance(self) -> None:
        """Test valid Best Price distance (negative values)."""
        assert validate_best_price_distance_percentage(0) is True
        assert validate_best_price_distance_percentage(-5) is True
        assert validate_best_price_distance_percentage(-10) is True
        assert validate_best_price_distance_percentage(-25) is True
        assert validate_best_price_distance_percentage(-MAX_DISTANCE_PERCENTAGE) is True

    def test_invalid_best_price_distance(self) -> None:
        """Test invalid Best Price distance (positive or out of bounds)."""
        assert validate_best_price_distance_percentage(5) is False  # Positive not allowed
        assert validate_best_price_distance_percentage(10) is False
        assert validate_best_price_distance_percentage(-MAX_DISTANCE_PERCENTAGE - 1) is False

    def test_valid_peak_price_distance(self) -> None:
        """Test valid Peak Price distance (positive values)."""
        assert validate_distance_percentage(0) is True
        assert validate_distance_percentage(5) is True
        assert validate_distance_percentage(10) is True
        assert validate_distance_percentage(25) is True
        assert validate_distance_percentage(MAX_DISTANCE_PERCENTAGE) is True

    def test_invalid_peak_price_distance(self) -> None:
        """Test invalid Peak Price distance (negative or out of bounds)."""
        assert validate_distance_percentage(-5) is False  # Negative not allowed
        assert validate_distance_percentage(-10) is False
        assert validate_distance_percentage(MAX_DISTANCE_PERCENTAGE + 1) is False


class TestGapCountValidation:
    """Test gap count validation."""

    def test_valid_gap_counts(self) -> None:
        """Test valid gap count values."""
        assert validate_gap_count(MIN_GAP_COUNT) is True
        assert validate_gap_count(0) is True
        assert validate_gap_count(1) is True
        assert validate_gap_count(4) is True
        assert validate_gap_count(MAX_GAP_COUNT) is True

    def test_invalid_gap_counts(self) -> None:
        """Test invalid gap count values."""
        assert validate_gap_count(MIN_GAP_COUNT - 1) is False
        assert validate_gap_count(MAX_GAP_COUNT + 1) is False
        assert validate_gap_count(-5) is False


class TestRelaxationAttemptsValidation:
    """Test relaxation attempts validation."""

    def test_valid_relaxation_attempts(self) -> None:
        """Test valid relaxation attempts values."""
        assert validate_relaxation_attempts(MIN_RELAXATION_ATTEMPTS) is True
        assert validate_relaxation_attempts(5) is True
        assert validate_relaxation_attempts(11) is True
        assert validate_relaxation_attempts(MAX_RELAXATION_ATTEMPTS) is True

    def test_invalid_relaxation_attempts(self) -> None:
        """Test invalid relaxation attempts values."""
        assert validate_relaxation_attempts(MIN_RELAXATION_ATTEMPTS - 1) is False
        assert validate_relaxation_attempts(0) is False
        assert validate_relaxation_attempts(MAX_RELAXATION_ATTEMPTS + 1) is False


class TestPriceRatingThresholdValidation:
    """Test price rating threshold validation."""

    def test_valid_threshold_low(self) -> None:
        """Test valid low threshold values (negative)."""
        assert validate_price_rating_threshold_low(MIN_PRICE_RATING_THRESHOLD_LOW) is True
        assert validate_price_rating_threshold_low(-20) is True
        assert validate_price_rating_threshold_low(-10) is True
        assert validate_price_rating_threshold_low(MAX_PRICE_RATING_THRESHOLD_LOW) is True

    def test_invalid_threshold_low(self) -> None:
        """Test invalid low threshold values."""
        assert validate_price_rating_threshold_low(MIN_PRICE_RATING_THRESHOLD_LOW - 1) is False
        assert validate_price_rating_threshold_low(MAX_PRICE_RATING_THRESHOLD_LOW + 1) is False
        assert validate_price_rating_threshold_low(0) is False  # Must be negative
        assert validate_price_rating_threshold_low(10) is False  # Must be negative

    def test_valid_threshold_high(self) -> None:
        """Test valid high threshold values (positive)."""
        assert validate_price_rating_threshold_high(MIN_PRICE_RATING_THRESHOLD_HIGH) is True
        assert validate_price_rating_threshold_high(10) is True
        assert validate_price_rating_threshold_high(20) is True
        assert validate_price_rating_threshold_high(MAX_PRICE_RATING_THRESHOLD_HIGH) is True

    def test_invalid_threshold_high(self) -> None:
        """Test invalid high threshold values."""
        assert validate_price_rating_threshold_high(MIN_PRICE_RATING_THRESHOLD_HIGH - 1) is False
        assert validate_price_rating_threshold_high(MAX_PRICE_RATING_THRESHOLD_HIGH + 1) is False
        assert validate_price_rating_threshold_high(0) is False  # Must be positive
        assert validate_price_rating_threshold_high(-10) is False  # Must be positive

    def test_valid_threshold_combinations(self) -> None:
        """Test valid combinations of low and high thresholds."""
        # Standard defaults
        assert validate_price_rating_thresholds(-20, 10) is True

        # Wide range
        assert validate_price_rating_thresholds(-50, 50) is True

        # Narrow range
        assert validate_price_rating_thresholds(-5, 5) is True

    def test_invalid_threshold_combinations(self) -> None:
        """Test invalid combinations of low and high thresholds."""
        # Low threshold out of range
        assert validate_price_rating_thresholds(-60, 10) is False

        # High threshold out of range
        assert validate_price_rating_thresholds(-20, 60) is False

        # Both out of range
        assert validate_price_rating_thresholds(-100, 100) is False

        # Low must be negative, high must be positive (crossing is OK)
        assert validate_price_rating_thresholds(-20, 10) is True


class TestVolatilityThresholdValidation:
    """Test volatility threshold validation."""

    def test_valid_threshold_moderate(self) -> None:
        """Test valid moderate threshold values."""
        assert validate_volatility_threshold_moderate(MIN_VOLATILITY_THRESHOLD_MODERATE) is True
        assert validate_volatility_threshold_moderate(10.0) is True
        assert validate_volatility_threshold_moderate(15.0) is True
        assert validate_volatility_threshold_moderate(MAX_VOLATILITY_THRESHOLD_MODERATE) is True

    def test_invalid_threshold_moderate(self) -> None:
        """Test invalid moderate threshold values."""
        assert validate_volatility_threshold_moderate(MIN_VOLATILITY_THRESHOLD_MODERATE - 1) is False
        assert validate_volatility_threshold_moderate(MAX_VOLATILITY_THRESHOLD_MODERATE + 1) is False
        assert validate_volatility_threshold_moderate(0.0) is False

    def test_valid_threshold_high(self) -> None:
        """Test valid high threshold values."""
        assert validate_volatility_threshold_high(MIN_VOLATILITY_THRESHOLD_HIGH) is True
        assert validate_volatility_threshold_high(25.0) is True
        assert validate_volatility_threshold_high(30.0) is True
        assert validate_volatility_threshold_high(MAX_VOLATILITY_THRESHOLD_HIGH) is True

    def test_invalid_threshold_high(self) -> None:
        """Test invalid high threshold values."""
        assert validate_volatility_threshold_high(MIN_VOLATILITY_THRESHOLD_HIGH - 1) is False
        assert validate_volatility_threshold_high(MAX_VOLATILITY_THRESHOLD_HIGH + 1) is False

    def test_valid_threshold_very_high(self) -> None:
        """Test valid very high threshold values."""
        assert validate_volatility_threshold_very_high(MIN_VOLATILITY_THRESHOLD_VERY_HIGH) is True
        assert validate_volatility_threshold_very_high(50.0) is True
        assert validate_volatility_threshold_very_high(60.0) is True
        assert validate_volatility_threshold_very_high(MAX_VOLATILITY_THRESHOLD_VERY_HIGH) is True

    def test_invalid_threshold_very_high(self) -> None:
        """Test invalid very high threshold values."""
        assert validate_volatility_threshold_very_high(MIN_VOLATILITY_THRESHOLD_VERY_HIGH - 1) is False
        assert validate_volatility_threshold_very_high(MAX_VOLATILITY_THRESHOLD_VERY_HIGH + 1) is False

    def test_valid_threshold_combinations(self) -> None:
        """Test valid combinations of all three volatility thresholds."""
        # Standard defaults
        assert validate_volatility_thresholds(10.0, 25.0, 50.0) is True

        # Tight clustering
        assert validate_volatility_thresholds(20.0, 21.0, 36.0) is True

        # Wide spacing
        assert validate_volatility_thresholds(5.0, 30.0, 80.0) is True

    def test_invalid_threshold_combinations(self) -> None:
        """Test invalid combinations of volatility thresholds."""
        # Moderate out of range
        assert validate_volatility_thresholds(0.0, 25.0, 50.0) is False

        # High out of range
        assert validate_volatility_thresholds(10.0, 50.0, 50.0) is False

        # Very high out of range
        assert validate_volatility_thresholds(10.0, 25.0, 100.0) is False

        # Wrong order: moderate >= high
        assert validate_volatility_thresholds(25.0, 25.0, 50.0) is False
        assert validate_volatility_thresholds(30.0, 25.0, 50.0) is False

        # Wrong order: high >= very_high
        assert validate_volatility_thresholds(10.0, 50.0, 50.0) is False
        assert validate_volatility_thresholds(10.0, 60.0, 50.0) is False


class TestPriceTrendThresholdValidation:
    """Test price trend threshold validation."""

    def test_valid_threshold_rising(self) -> None:
        """Test valid rising trend threshold values (positive)."""
        assert validate_price_trend_rising(MIN_PRICE_TREND_RISING) is True
        assert validate_price_trend_rising(10) is True
        assert validate_price_trend_rising(25) is True
        assert validate_price_trend_rising(MAX_PRICE_TREND_RISING) is True

    def test_invalid_threshold_rising(self) -> None:
        """Test invalid rising trend threshold values."""
        assert validate_price_trend_rising(MIN_PRICE_TREND_RISING - 1) is False
        assert validate_price_trend_rising(0) is False
        assert validate_price_trend_rising(MAX_PRICE_TREND_RISING + 1) is False
        assert validate_price_trend_rising(-10) is False  # Must be positive

    def test_valid_threshold_falling(self) -> None:
        """Test valid falling trend threshold values (negative)."""
        assert validate_price_trend_falling(MIN_PRICE_TREND_FALLING) is True
        assert validate_price_trend_falling(-25) is True
        assert validate_price_trend_falling(-10) is True
        assert validate_price_trend_falling(MAX_PRICE_TREND_FALLING) is True

    def test_invalid_threshold_falling(self) -> None:
        """Test invalid falling trend threshold values."""
        assert validate_price_trend_falling(MIN_PRICE_TREND_FALLING - 1) is False
        assert validate_price_trend_falling(0) is False
        assert validate_price_trend_falling(MAX_PRICE_TREND_FALLING + 1) is False
        assert validate_price_trend_falling(10) is False  # Must be negative


class TestBoundaryConditions:
    """Test boundary conditions for all validators."""

    def test_exact_boundaries(self) -> None:
        """Test that validators accept exact boundary values."""
        # Period length
        assert validate_period_length(MIN_PERIOD_LENGTH) is True

        # Flex
        assert validate_flex_percentage(MAX_FLEX_PERCENTAGE) is True
        assert validate_flex_percentage(-MAX_FLEX_PERCENTAGE) is True

        # Min periods
        assert validate_min_periods(1) is True
        assert validate_min_periods(MAX_MIN_PERIODS) is True

        # Distance (Best Price)
        assert validate_best_price_distance_percentage(0) is True
        assert validate_best_price_distance_percentage(-MAX_DISTANCE_PERCENTAGE) is True

        # Distance (Peak Price)
        assert validate_distance_percentage(0) is True
        assert validate_distance_percentage(MAX_DISTANCE_PERCENTAGE) is True

        # Gap count
        assert validate_gap_count(MIN_GAP_COUNT) is True
        assert validate_gap_count(MAX_GAP_COUNT) is True

        # Relaxation attempts
        assert validate_relaxation_attempts(MIN_RELAXATION_ATTEMPTS) is True
        assert validate_relaxation_attempts(MAX_RELAXATION_ATTEMPTS) is True

    def test_just_outside_boundaries(self) -> None:
        """Test that validators reject values just outside boundaries."""
        # Flex
        assert validate_flex_percentage(MAX_FLEX_PERCENTAGE + 1) is False
        assert validate_flex_percentage(-MAX_FLEX_PERCENTAGE - 1) is False

        # Min periods
        assert validate_min_periods(0) is False
        assert validate_min_periods(MAX_MIN_PERIODS + 1) is False

        # Distance (Best Price)
        assert validate_best_price_distance_percentage(1) is False  # Must be ≤0
        assert validate_best_price_distance_percentage(-MAX_DISTANCE_PERCENTAGE - 1) is False

        # Distance (Peak Price)
        assert validate_distance_percentage(-1) is False  # Must be ≥0
        assert validate_distance_percentage(MAX_DISTANCE_PERCENTAGE + 1) is False


class TestFloatPrecision:
    """Test handling of float precision in validators."""

    def test_float_precision_distance(self) -> None:
        """Test float precision for distance validators."""
        # Best Price
        assert validate_best_price_distance_percentage(-5.5) is True
        assert validate_best_price_distance_percentage(-0.1) is True
        assert validate_best_price_distance_percentage(-49.9) is True

        # Peak Price
        assert validate_distance_percentage(5.5) is True
        assert validate_distance_percentage(0.1) is True
        assert validate_distance_percentage(49.9) is True

    def test_float_precision_volatility(self) -> None:
        """Test float precision for volatility validators."""
        assert validate_volatility_threshold_moderate(10.5) is True
        assert validate_volatility_threshold_high(25.3) is True
        assert validate_volatility_threshold_very_high(50.7) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
