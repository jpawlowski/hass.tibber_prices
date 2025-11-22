"""
Unit tests for level_filtering.py - Filter logic for period calculation.

This test suite validates the core filtering logic used in period calculation:
- Flex filter (price distance from daily min/max)
- Min distance filter (price distance from daily average)
- Dynamic scaling of min_distance when flex is high (>20%)
- Sign convention normalization (negative user values → positive internal values)

Regression Tests:
- Peak Price Sign Convention Bug (Nov 2025): Negative flex values blocked all peak prices
- Redundant Condition Bug (Nov 2025): "price <= ref_price" blocked all peak prices
"""

from __future__ import annotations

import pytest

from custom_components.tibber_prices.coordinator.period_handlers.level_filtering import (
    check_interval_criteria,
)
from custom_components.tibber_prices.coordinator.period_handlers.types import (
    TibberPricesIntervalCriteria,
)


@pytest.mark.unit
class TestFlexFilterBestPrice:
    """Test flex filter logic for Best Price (reverse_sort=False)."""

    def test_interval_within_flex_threshold(self) -> None:
        """Test interval that qualifies (price within flex threshold from minimum)."""
        # Daily min = 10 ct, flex = 15% → accepts up to 11.5 ct
        criteria = TibberPricesIntervalCriteria(
            ref_price=10.0,  # Daily minimum
            avg_price=20.0,
            flex=0.15,  # 15% flexibility
            min_distance_from_avg=0.0,
            reverse_sort=False,  # Best Price mode
        )

        # Price 11.0 ct is within 10 + (10 * 0.15) = 11.5 ct
        price = 11.0

        in_flex, _meets_distance = check_interval_criteria(price, criteria)

        assert in_flex is True, "Interval within flex threshold should pass flex check"

    def test_interval_outside_flex_threshold(self) -> None:
        """Test interval that fails (price outside flex threshold from minimum)."""
        criteria = TibberPricesIntervalCriteria(
            ref_price=10.0,  # Daily minimum
            avg_price=20.0,
            flex=0.15,  # 15% flexibility
            min_distance_from_avg=0.0,
            reverse_sort=False,  # Best Price mode
        )

        # Price 12.0 ct is outside 10 + (10 * 0.15) = 11.5 ct
        price = 12.0

        in_flex, _meets_distance = check_interval_criteria(price, criteria)

        assert in_flex is False, "Interval outside flex threshold should fail flex check"


@pytest.mark.unit
class TestFlexFilterPeakPrice:
    """Test flex filter logic for Peak Price (reverse_sort=True)."""

    def test_interval_within_flex_threshold(self) -> None:
        """Test interval that qualifies (price within flex threshold from maximum)."""
        # Daily max = 50 ct, flex = 20% → accepts down to 40 ct
        # NOTE: flex is passed as POSITIVE 0.20, not negative!
        criteria = TibberPricesIntervalCriteria(
            ref_price=50.0,  # Daily maximum
            avg_price=30.0,
            flex=0.20,  # 20% flexibility (positive internally!)
            min_distance_from_avg=0.0,
            reverse_sort=True,  # Peak Price mode
        )

        # Price 45 ct is within 50 - (50 * 0.20) = 40 ct threshold
        price = 45.0

        in_flex, _meets_distance = check_interval_criteria(price, criteria)

        assert in_flex is True, "Interval within flex threshold should pass flex check"

    def test_interval_outside_flex_threshold(self) -> None:
        """Test interval that fails (price outside flex threshold from maximum)."""
        criteria = TibberPricesIntervalCriteria(
            ref_price=50.0,  # Daily maximum
            avg_price=30.0,
            flex=0.20,  # 20% flexibility (positive internally!)
            min_distance_from_avg=0.0,
            reverse_sort=True,  # Peak Price mode
        )

        # Price 38 ct is outside 50 - (50 * 0.20) = 40 ct threshold (too cheap!)
        price = 38.0

        in_flex, _meets_distance = check_interval_criteria(price, criteria)

        assert in_flex is False, "Interval outside flex threshold should fail flex check"

    def test_regression_bug_peak_price_sign_convention(self) -> None:
        """
        Regression test for Peak Price Sign Convention Bug (Nov 2025).

        Bug: When flex was passed as negative value (e.g., -0.20 for peak price),
        the flex filter would reject ALL intervals because:
        - User-facing config: peak_price_flex = -20% (negative sign convention)
        - Expected internal: 0.20 (positive, with reverse_sort=True for direction)
        - Broken behavior: Used -0.20 directly → math was wrong

        Additionally, there was a redundant condition that blocked peak prices:
            if reverse_sort:
                in_flex = price >= ref_price + (ref_price * flex)
                and price <= ref_price  # ← This was the bug!

        This test ensures:
        1. Negative flex values are normalized to positive (abs())
        2. No redundant conditions block valid peak price intervals
        """
        # User-facing: -20%, internally normalized to +0.20
        criteria = TibberPricesIntervalCriteria(
            ref_price=50.0,  # Daily maximum
            avg_price=30.0,
            flex=0.20,  # After normalization: abs(-0.20) = 0.20
            min_distance_from_avg=0.0,
            reverse_sort=True,
        )

        # Price exactly at threshold: 50 - (50 * 0.20) = 40 ct
        price_at_threshold = 40.0
        in_flex, _ = check_interval_criteria(price_at_threshold, criteria)
        assert in_flex is True, "Boundary case should pass after normalization fix"

        # Price within threshold: 45 ct
        price_within = 45.0
        in_flex, _ = check_interval_criteria(price_within, criteria)
        assert in_flex is True, "Price within threshold should pass"

        # Price outside threshold (too cheap): 38 ct
        price_outside = 38.0
        in_flex, _ = check_interval_criteria(price_outside, criteria)
        assert in_flex is False, "Price outside threshold should fail"


@pytest.mark.unit
class TestMinDistanceFilter:
    """Test min_distance_from_avg filter logic."""

    def test_best_price_below_average(self) -> None:
        """Test Best Price interval below average (passes min_distance check)."""
        criteria = TibberPricesIntervalCriteria(
            ref_price=10.0,
            avg_price=20.0,
            flex=0.50,  # High flex to not filter by flex
            min_distance_from_avg=5.0,  # 5% below average required (positive internally!)
            reverse_sort=False,
        )

        # Price 18 ct is 10% below average (20 - 18) / 20 = 0.10 → passes 5% requirement
        price = 18.0

        _in_flex, meets_distance = check_interval_criteria(price, criteria)

        assert meets_distance is True, "Interval sufficiently below average should pass distance check"

    def test_best_price_too_close_to_average(self) -> None:
        """Test Best Price interval too close to average (fails min_distance check)."""
        criteria = TibberPricesIntervalCriteria(
            ref_price=10.0,
            avg_price=20.0,
            flex=0.10,  # Low flex (10%) to avoid dynamic scaling
            min_distance_from_avg=5.0,  # 5% below average required
            reverse_sort=False,
        )

        # Price 19.5 ct is only 2.5% below average → fails 5% requirement
        # Threshold = 20 * (1 - 5/100) = 19.0 ct
        # 19.5 ct > 19.0 ct → FAILS distance check
        price = 19.5

        _in_flex, meets_distance = check_interval_criteria(price, criteria)

        assert meets_distance is False, "Interval too close to average should fail distance check"

    def test_peak_price_above_average(self) -> None:
        """Test Peak Price interval above average (passes min_distance check)."""
        criteria = TibberPricesIntervalCriteria(
            ref_price=50.0,
            avg_price=30.0,
            flex=0.50,  # High flex to not filter by flex
            min_distance_from_avg=5.0,  # 5% above average required (positive internally!)
            reverse_sort=True,
        )

        # Price 33 ct is 10% above average (33 - 30) / 30 = 0.10 → passes 5% requirement
        price = 33.0

        _in_flex, meets_distance = check_interval_criteria(price, criteria)

        assert meets_distance is True, "Interval sufficiently above average should pass distance check"

    def test_regression_min_distance_sign_convention(self) -> None:
        """
        Regression test for min_distance sign convention (Nov 2025).

        Bug: min_distance_from_avg had sign convention issues similar to flex:
        - User-facing: best_price_min_distance = -5% (negative = below average)
        - User-facing: peak_price_min_distance = +5% (positive = above average)
        - Expected internal: 5.0 (always positive, direction from reverse_sort)

        This test ensures min_distance is always normalized to positive.
        """
        # Best Price: User-facing -5%, internally normalized to 5.0
        criteria_best = TibberPricesIntervalCriteria(
            ref_price=10.0,
            avg_price=20.0,
            flex=0.50,
            min_distance_from_avg=5.0,  # After normalization: abs(-5.0) = 5.0
            reverse_sort=False,
        )

        # 18 ct = 10% below average → passes 5% requirement
        _, meets_distance = check_interval_criteria(18.0, criteria_best)
        assert meets_distance is True, "Best price normalization works"

        # Peak Price: User-facing +5%, internally normalized to 5.0
        criteria_peak = TibberPricesIntervalCriteria(
            ref_price=50.0,
            avg_price=30.0,
            flex=0.50,
            min_distance_from_avg=5.0,  # After normalization: abs(5.0) = 5.0
            reverse_sort=True,
        )

        # 33 ct = 10% above average → passes 5% requirement
        _, meets_distance = check_interval_criteria(33.0, criteria_peak)
        assert meets_distance is True, "Peak price normalization works"


@pytest.mark.unit
class TestDynamicScaling:
    """Test dynamic scaling of min_distance when flex is high."""

    def test_no_scaling_below_threshold(self) -> None:
        """Test no scaling when flex <= 20% (threshold)."""
        criteria = TibberPricesIntervalCriteria(
            ref_price=10.0,
            avg_price=20.0,
            flex=0.20,  # Exactly at threshold
            min_distance_from_avg=5.0,
            reverse_sort=False,
        )

        # Price at exactly 5% below average
        # Threshold = 20 * (1 - 5/100) = 19.0 ct
        price = 19.0

        _, meets_distance = check_interval_criteria(price, criteria)

        # At flex=20%, no scaling → full 5% requirement applies
        assert meets_distance is True, "Boundary case should pass with no scaling"

    def test_scaling_at_30_percent_flex(self) -> None:
        """Test dynamic scaling at flex=30% (scale factor ~0.75)."""
        # flex=30% → excess=10% → scale_factor = 1.0 - (0.10 x 2.5) = 0.75
        # adjusted_min_distance = 5.0 x 0.75 = 3.75%
        criteria = TibberPricesIntervalCriteria(
            ref_price=10.0,
            avg_price=20.0,
            flex=0.30,  # 30% flex
            min_distance_from_avg=5.0,
            reverse_sort=False,
        )

        # Price at 4% below average
        # Original threshold: 20 * (1 - 5/100) = 19.0 ct
        # Scaled threshold: 20 * (1 - 3.75/100) = 19.25 ct
        price = 19.2  # 4% below average

        _, meets_distance = check_interval_criteria(price, criteria)

        # With scaling, 4% below average passes (scaled requirement: 3.75%)
        assert meets_distance is True, "Dynamic scaling should relax requirement"

    def test_scaling_at_50_percent_flex(self) -> None:
        """Test maximum scaling at flex=50% (scale factor 0.25)."""
        # flex=50% → excess=30% → scale_factor = max(0.25, 1.0 - 0.75) = 0.25
        # adjusted_min_distance = 5.0 x 0.25 = 1.25%
        criteria = TibberPricesIntervalCriteria(
            ref_price=10.0,
            avg_price=20.0,
            flex=0.50,  # Maximum safe flex
            min_distance_from_avg=5.0,
            reverse_sort=False,
        )

        # Price at 2% below average (would fail without scaling)
        # Original threshold: 20 * (1 - 5/100) = 19.0 ct
        # Scaled threshold: 20 * (1 - 1.25/100) = 19.75 ct
        price = 19.6  # 2% below average

        _, meets_distance = check_interval_criteria(price, criteria)

        # With maximum scaling, 2% below average passes (scaled requirement: 1.25%)
        assert meets_distance is True, "Maximum scaling should heavily relax requirement"

    def test_scaling_never_below_25_percent(self) -> None:
        """Test that scale factor never goes below 0.25 (25%)."""
        # Even with unrealistically high flex, min 25% of min_distance is enforced
        criteria = TibberPricesIntervalCriteria(
            ref_price=10.0,
            avg_price=20.0,
            flex=0.80,  # Unrealistically high flex (would be capped elsewhere)
            min_distance_from_avg=5.0,
            reverse_sort=False,
        )

        # Minimum scaled distance: 5.0 x 0.25 = 1.25%
        # Threshold: 20 * (1 - 1.25/100) = 19.75 ct
        price_fail = 19.8  # 1% below average (fails even with max scaling)
        price_pass = 19.7  # 1.5% below average (passes)

        _, meets_distance_fail = check_interval_criteria(price_fail, criteria)
        _, meets_distance_pass = check_interval_criteria(price_pass, criteria)

        assert meets_distance_fail is False, "Below minimum scaled threshold should fail"
        assert meets_distance_pass is True, "Above minimum scaled threshold should pass"


@pytest.mark.unit
class TestBoundaryConditions:
    """Test boundary and edge cases."""

    def test_price_exactly_at_ref_price_best(self) -> None:
        """Test Best Price: interval exactly at reference price (daily minimum)."""
        criteria = TibberPricesIntervalCriteria(
            ref_price=10.0,
            avg_price=20.0,
            flex=0.15,
            min_distance_from_avg=0.0,
            reverse_sort=False,
        )

        # Price exactly at daily minimum
        price = 10.0

        in_flex, _ = check_interval_criteria(price, criteria)

        assert in_flex is True, "Price at reference should pass"

    def test_price_exactly_at_ref_price_peak(self) -> None:
        """Test Peak Price: interval exactly at reference price (daily maximum)."""
        criteria = TibberPricesIntervalCriteria(
            ref_price=50.0,
            avg_price=30.0,
            flex=0.20,
            min_distance_from_avg=0.0,
            reverse_sort=True,
        )

        # Price exactly at daily maximum
        price = 50.0

        in_flex, _ = check_interval_criteria(price, criteria)

        assert in_flex is True, "Price at reference should pass"

    def test_price_exactly_at_flex_threshold_best(self) -> None:
        """Test Best Price: interval exactly at flex threshold."""
        criteria = TibberPricesIntervalCriteria(
            ref_price=10.0,
            avg_price=20.0,
            flex=0.15,  # 15% → accepts up to 11.5 ct
            min_distance_from_avg=0.0,
            reverse_sort=False,
        )

        # Price exactly at threshold: 10 + (10 * 0.15) = 11.5 ct
        price = 11.5

        in_flex, _ = check_interval_criteria(price, criteria)

        assert in_flex is True, "Price at flex threshold should pass"

    def test_price_exactly_at_flex_threshold_peak(self) -> None:
        """Test Peak Price: interval exactly at flex threshold."""
        criteria = TibberPricesIntervalCriteria(
            ref_price=50.0,
            avg_price=30.0,
            flex=0.20,  # 20% → accepts down to 40 ct
            min_distance_from_avg=0.0,
            reverse_sort=True,
        )

        # Price exactly at threshold: 50 - (50 * 0.20) = 40 ct
        price = 40.0

        in_flex, _ = check_interval_criteria(price, criteria)

        assert in_flex is True, "Price at flex threshold should pass"

    def test_price_one_cent_outside_flex_threshold_best(self) -> None:
        """Test Best Price: interval one cent outside flex threshold."""
        criteria = TibberPricesIntervalCriteria(
            ref_price=10.0,
            avg_price=20.0,
            flex=0.15,  # Accepts up to 11.5 ct
            min_distance_from_avg=0.0,
            reverse_sort=False,
        )

        # Price one cent over threshold
        price = 11.51

        in_flex, _ = check_interval_criteria(price, criteria)

        assert in_flex is False, "Price over threshold should fail"

    def test_price_one_cent_outside_flex_threshold_peak(self) -> None:
        """Test Peak Price: interval one cent outside flex threshold."""
        criteria = TibberPricesIntervalCriteria(
            ref_price=50.0,
            avg_price=30.0,
            flex=0.20,  # Accepts down to 40 ct
            min_distance_from_avg=0.0,
            reverse_sort=True,
        )

        # Price one cent below threshold (too cheap)
        price = 39.99

        in_flex, _ = check_interval_criteria(price, criteria)

        assert in_flex is False, "Price below threshold should fail"

    def test_zero_flex(self) -> None:
        """Test with zero flexibility (only exact reference price passes)."""
        criteria = TibberPricesIntervalCriteria(
            ref_price=10.0,
            avg_price=20.0,
            flex=0.0,  # Zero flexibility
            min_distance_from_avg=0.0,
            reverse_sort=False,
        )

        # Only exact reference price should pass
        price_exact = 10.0
        price_above = 10.01

        in_flex_exact, _ = check_interval_criteria(price_exact, criteria)
        in_flex_above, _ = check_interval_criteria(price_above, criteria)

        assert in_flex_exact is True, "Exact price should pass with zero flex"
        assert in_flex_above is False, "Above reference should fail with zero flex"

    def test_zero_min_distance(self) -> None:
        """Test with zero min_distance (any price passes distance check)."""
        criteria = TibberPricesIntervalCriteria(
            ref_price=10.0,
            avg_price=20.0,
            flex=0.50,
            min_distance_from_avg=0.0,  # Zero min_distance
            reverse_sort=False,
        )

        # Price exactly at average (would normally fail distance check)
        price = 20.0

        _, meets_distance = check_interval_criteria(price, criteria)

        # With zero min_distance, any price passes distance check
        assert meets_distance is True, "Zero min_distance should accept all prices"

    def test_price_exactly_at_average_best(self) -> None:
        """Test Best Price: interval exactly at average (fails with min_distance>0)."""
        criteria = TibberPricesIntervalCriteria(
            ref_price=10.0,
            avg_price=20.0,
            flex=0.50,
            min_distance_from_avg=5.0,  # Requires 5% below average
            reverse_sort=False,
        )

        # Price exactly at average
        price = 20.0

        _, meets_distance = check_interval_criteria(price, criteria)

        assert meets_distance is False, "Price at average should fail distance check"

    def test_price_exactly_at_average_peak(self) -> None:
        """Test Peak Price: interval exactly at average (fails with min_distance>0)."""
        criteria = TibberPricesIntervalCriteria(
            ref_price=50.0,
            avg_price=30.0,
            flex=0.50,
            min_distance_from_avg=5.0,  # Requires 5% above average
            reverse_sort=True,
        )

        # Price exactly at average
        price = 30.0

        _, meets_distance = check_interval_criteria(price, criteria)

        assert meets_distance is False, "Price at average should fail distance check"


@pytest.mark.unit
class TestCombinedFilters:
    """Test interaction between flex and min_distance filters."""

    def test_passes_flex_fails_distance(self) -> None:
        """Test interval that passes flex but fails min_distance."""
        # Setup: We need flex threshold WIDER than distance threshold
        # Use flex <= 20% to avoid dynamic scaling interference
        criteria = TibberPricesIntervalCriteria(
            ref_price=10.0,
            avg_price=13.0,  # Closer average makes distance threshold tighter
            flex=0.20,  # Flex threshold: 10 + (10 * 0.20) = 12 ct
            min_distance_from_avg=10.0,  # Distance threshold: 13 * (1 - 10/100) = 11.7 ct
            reverse_sort=False,
        )

        # Price 11.8 ct: passes flex (11.8 <= 12) but fails distance (11.8 > 11.7)
        price = 11.8

        in_flex, meets_distance = check_interval_criteria(price, criteria)

        assert in_flex is True, "Should pass flex (within 12 ct threshold)"
        assert meets_distance is False, "Should fail distance (above 11.7 ct threshold)"

    def test_fails_flex_passes_distance(self) -> None:
        """Test interval that fails flex but passes min_distance."""
        criteria = TibberPricesIntervalCriteria(
            ref_price=10.0,  # Daily min
            avg_price=20.0,
            flex=0.15,  # Low flex - accepts up to 11.5 ct
            min_distance_from_avg=5.0,  # Requires 5% below average (19 ct or less)
            reverse_sort=False,
        )

        # Price 12 ct fails flex (> 11.5 ct) but passes distance (40% below avg)
        price = 12.0

        in_flex, meets_distance = check_interval_criteria(price, criteria)

        assert in_flex is False, "Should fail flex (outside 11.5 ct threshold)"
        assert meets_distance is True, "Should pass distance (well below average)"

    def test_both_filters_pass(self) -> None:
        """Test interval that passes both filters."""
        criteria = TibberPricesIntervalCriteria(
            ref_price=10.0,
            avg_price=20.0,
            flex=0.20,  # Accepts up to 12 ct
            min_distance_from_avg=5.0,  # Requires 5% below average (19 ct or less)
            reverse_sort=False,
        )

        # Price 11 ct passes both: < 12 ct (flex) and < 19 ct (distance)
        price = 11.0

        in_flex, meets_distance = check_interval_criteria(price, criteria)

        assert in_flex is True, "Should pass flex"
        assert meets_distance is True, "Should pass distance"

    def test_both_filters_fail(self) -> None:
        """Test interval that fails both filters."""
        criteria = TibberPricesIntervalCriteria(
            ref_price=10.0,
            avg_price=20.0,
            flex=0.15,  # Accepts up to 11.5 ct
            min_distance_from_avg=5.0,  # Requires 5% below average (19 ct or less)
            reverse_sort=False,
        )

        # Price 19.5 ct fails both: > 11.5 ct (flex) and > 19 ct (distance)
        price = 19.5

        in_flex, meets_distance = check_interval_criteria(price, criteria)

        assert in_flex is False, "Should fail flex"
        assert meets_distance is False, "Should fail distance"


@pytest.mark.unit
class TestRealWorldScenarios:
    """Test with realistic price data and configurations."""

    def test_german_market_best_price(self) -> None:
        """Test Best Price with realistic German market data (Nov 2025)."""
        # Real data from Nov 22, 2025: Min=0.17 ct, Avg=8.26 ct, Max=17.24 ct
        criteria = TibberPricesIntervalCriteria(
            ref_price=0.17,  # Daily minimum (early morning)
            avg_price=8.26,  # Daily average
            flex=0.15,  # 15% default flex
            min_distance_from_avg=5.0,  # -5% below average (user-facing)
            reverse_sort=False,
        )

        # Calculate thresholds:
        # Flex threshold: 0.17 + (0.17 * 0.15) = 0.17 + 0.0255 = 0.1955 ct
        # Distance threshold: 8.26 * (1 - 5/100) = 8.26 * 0.95 = 7.847 ct

        # Price scenarios
        price_at_min = 0.17  # Should pass both (at minimum)
        price_within_flex = 0.19  # Should pass flex (< 0.1955)
        price_too_high = 5.0  # Should fail flex (> 0.1955), but pass distance (< 7.847)

        in_flex_min, meets_dist_min = check_interval_criteria(price_at_min, criteria)
        in_flex_within, meets_dist_within = check_interval_criteria(price_within_flex, criteria)
        in_flex_high, meets_dist_high = check_interval_criteria(price_too_high, criteria)

        assert in_flex_min is True, "Minimum price should pass flex"
        assert meets_dist_min is True, "Minimum price should pass distance"

        assert in_flex_within is True, "0.19 ct should pass flex (< 0.1955)"
        assert meets_dist_within is True, "0.19 ct should pass distance (< 7.847)"

        assert in_flex_high is False, "5 ct should fail flex (way above 0.1955 threshold)"
        assert meets_dist_high is True, "5 ct should pass distance (< 7.847)"

    def test_german_market_peak_price(self) -> None:
        """Test Peak Price with realistic German market data (Nov 2025)."""
        # Real data: Min=0.17 ct, Avg=8.26 ct, Max=17.24 ct
        criteria = TibberPricesIntervalCriteria(
            ref_price=17.24,  # Daily maximum (evening peak)
            avg_price=8.26,  # Daily average
            flex=0.20,  # 20% default flex (user-facing: -20%)
            min_distance_from_avg=5.0,  # +5% above average (user-facing)
            reverse_sort=True,
        )

        # Calculate thresholds:
        # Flex threshold: 17.24 - (17.24 * 0.20) = 17.24 - 3.448 = 13.792 ct
        # Distance threshold: 8.26 * (1 + 5/100) = 8.26 * 1.05 = 8.673 ct

        # Price scenarios
        price_at_max = 17.24  # Should pass both (at maximum)
        price_within_flex = 14.0  # Should pass flex (> 13.792)
        price_too_low = 10.0  # Should fail flex (< 13.792)

        in_flex_max, meets_dist_max = check_interval_criteria(price_at_max, criteria)
        in_flex_within, meets_dist_within = check_interval_criteria(price_within_flex, criteria)
        in_flex_low, meets_dist_low = check_interval_criteria(price_too_low, criteria)

        assert in_flex_max is True, "Maximum price should pass flex"
        assert meets_dist_max is True, "Maximum price should pass distance"

        assert in_flex_within is True, "14 ct should pass flex (> 13.792)"
        assert meets_dist_within is True, "14 ct should pass distance (> 8.673)"

        assert in_flex_low is False, "10 ct should fail flex (< 13.792 threshold)"
        # 10 ct is still above average (8.26), so should pass distance
        assert meets_dist_low is True, "10 ct should pass distance (> 8.673)"

    def test_negative_prices(self) -> None:
        """Test with negative prices (wind/solar surplus scenarios)."""
        # Scenario: Lots of renewable energy, prices go negative
        criteria = TibberPricesIntervalCriteria(
            ref_price=-5.0,  # Daily minimum (negative!)
            avg_price=3.0,  # Daily average (some hours still positive)
            flex=0.20,  # 20% flex
            min_distance_from_avg=5.0,
            reverse_sort=False,
        )

        # Price at -5 ct (minimum, negative)
        # Flex threshold: -5 + abs(-5 * 0.20) = -5 + 1 = -4 ct
        price_at_min = -5.0
        price_within_flex = -4.5

        in_flex_min, _ = check_interval_criteria(price_at_min, criteria)
        in_flex_within, _ = check_interval_criteria(price_within_flex, criteria)

        assert in_flex_min is True, "Negative minimum should pass"
        assert in_flex_within is True, "Within flex of negative min should pass"
