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

from custom_components.tibber_prices.coordinator.period_handlers.level_filtering import check_interval_criteria
from custom_components.tibber_prices.coordinator.period_handlers.types import TibberPricesIntervalCriteria


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

    @pytest.mark.parametrize(
        ("price", "expected"),
        [
            (50.0, True),  # At the daily maximum
            (47.0, True),  # Within the band
            (46.0, True),  # Exactly at the threshold
            (45.99, False),  # One cent below the threshold
            (38.0, False),  # Far below, still above the mean
        ],
    )
    def test_flex_threshold(self, price: float, *, expected: bool) -> None:
        """Max 50, avg 30, flex 20% of the 20 ct span → accepts down to 46 ct."""
        # Regression (Nov 2025): flex arrives POSITIVE (user-facing -20% → 0.20, direction
        # from reverse_sort). Negative flex or an extra "price <= ref_price" condition once
        # blocked every peak interval.
        criteria = TibberPricesIntervalCriteria(
            ref_price=50.0,
            avg_price=30.0,
            flex=0.20,
            min_distance_from_avg=0.0,
            reverse_sort=True,
        )
        in_flex, _ = check_interval_criteria(price, criteria)
        assert in_flex is expected

    def test_regression_issue_259_threshold_stays_above_mean(self) -> None:
        """
        Regression (#259): peak flex is a share of max - avg, not of max.

        2026-11-13: max 46.19, mean 37.89, flex 20% → threshold 44.53 ct. The old
        base (max) gave 36.95 ct, below the mean, so min distance alone cut the period.
        """
        criteria = TibberPricesIntervalCriteria(
            ref_price=46.19,
            avg_price=37.89,
            flex=0.20,
            min_distance_from_avg=5.0,
            reverse_sort=True,
        )
        assert check_interval_criteria(44.6, criteria)[0] is True
        assert check_interval_criteria(44.4, criteria)[0] is False
        in_flex, meets_distance = check_interval_criteria(39.97, criteria)
        assert in_flex is False, "Flex must cut the period before min distance does"
        assert meets_distance is True


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
class TestConflictScaling:
    """min_distance is cut only where high flex passes it, just far enough for both to meet."""

    def test_no_scaling_on_normal_day(self) -> None:
        """Min 10, avg 20, flex 50%: flex ≤ 15 ct stays inside distance ≤ 19 ct → full 5%."""
        criteria = TibberPricesIntervalCriteria(
            ref_price=10.0,
            avg_price=20.0,
            flex=0.50,
            min_distance_from_avg=5.0,
            reverse_sort=False,
        )
        assert check_interval_criteria(19.0, criteria)[1] is True
        assert check_interval_criteria(19.1, criteria)[1] is False

    def test_flat_day_cut_to_meet_flex(self) -> None:
        """Min 30, avg 33, flex 50%: flex ≤ 31.5 ct passes distance ≤ 31.35 ct → both meet at 31.5 ct."""
        criteria = TibberPricesIntervalCriteria(
            ref_price=30.0,
            avg_price=33.0,
            flex=0.50,
            min_distance_from_avg=5.0,
            reverse_sort=False,
        )
        assert check_interval_criteria(31.5, criteria) == (True, True)
        assert check_interval_criteria(31.6, criteria) == (False, False)

    def test_flat_day_peak_cut_to_meet_flex(self) -> None:
        """Max 36, avg 33, flex 50%: flex ≥ 34.5 ct passes distance ≥ 34.65 ct → both meet at 34.5 ct."""
        criteria = TibberPricesIntervalCriteria(
            ref_price=36.0,
            avg_price=33.0,
            flex=0.50,
            min_distance_from_avg=5.0,
            reverse_sort=True,
        )
        assert check_interval_criteria(34.5, criteria) == (True, True)
        assert check_interval_criteria(34.4, criteria) == (False, False)

    def test_no_scaling_at_or_below_threshold_flex(self) -> None:
        """Very flat day at flex 20%: the conflict exists, but min_distance stays whole."""
        criteria = TibberPricesIntervalCriteria(
            ref_price=30.0,
            avg_price=31.0,
            flex=0.20,  # flex ≤ 30.2 ct, distance ≤ 29.45 ct
            min_distance_from_avg=5.0,
            reverse_sort=False,
        )
        assert check_interval_criteria(30.1, criteria) == (True, False)

    def test_never_below_25_percent(self) -> None:
        """Min 30, avg 30.2, flex 50%: meeting would need 0.33%, floor keeps 1.25% (≤ 29.82 ct)."""
        criteria = TibberPricesIntervalCriteria(
            ref_price=30.0,
            avg_price=30.2,
            flex=0.50,
            min_distance_from_avg=5.0,
            reverse_sort=False,
        )
        assert check_interval_criteria(30.0, criteria) == (True, False)
        assert check_interval_criteria(29.8, criteria)[1] is True


@pytest.mark.unit
class TestBoundaryConditions:
    """Test boundary and edge cases."""

    @pytest.mark.parametrize(
        ("price", "expected"),
        [
            (10.0, True),  # At the daily minimum
            (11.5, True),  # Exactly at the threshold: 10 + (10 * 0.15)
            (11.51, False),  # One cent over the threshold
        ],
    )
    def test_best_price_flex_boundaries(self, price: float, *, expected: bool) -> None:
        """Min 10, avg 20, flex 15% of the 10 ct span → accepts up to 11.5 ct."""
        criteria = TibberPricesIntervalCriteria(
            ref_price=10.0,
            avg_price=20.0,
            flex=0.15,
            min_distance_from_avg=0.0,
            reverse_sort=False,
        )
        in_flex, _ = check_interval_criteria(price, criteria)
        assert in_flex is expected

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
            avg_price=11.0,  # Close average: distance threshold lands below the flex threshold
            flex=0.20,  # Flex threshold: 10 + (1 * 0.20) = 10.2 ct
            min_distance_from_avg=10.0,  # Distance threshold: 11 * (1 - 10/100) = 9.9 ct
            reverse_sort=False,
        )

        # Price 10.1 ct: passes flex (10.1 <= 10.2) but fails distance (10.1 > 9.9)
        price = 10.1

        in_flex, meets_distance = check_interval_criteria(price, criteria)

        assert in_flex is True, "Should pass flex (within 10.2 ct threshold)"
        assert meets_distance is False, "Should fail distance (above 9.9 ct threshold)"

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
        # Flex threshold: 0.17 + ((8.26 - 0.17) * 0.15) = 0.17 + 1.2135 = 1.3835 ct
        # Distance threshold: 8.26 * (1 - 5/100) = 8.26 * 0.95 = 7.847 ct

        # Price scenarios
        price_at_min = 0.17  # Should pass both (at minimum)
        price_within_flex = 1.3  # Should pass flex (< 1.3835)
        price_too_high = 5.0  # Should fail flex (> 1.3835), but pass distance (< 7.847)

        in_flex_min, meets_dist_min = check_interval_criteria(price_at_min, criteria)
        in_flex_within, meets_dist_within = check_interval_criteria(price_within_flex, criteria)
        in_flex_high, meets_dist_high = check_interval_criteria(price_too_high, criteria)

        assert in_flex_min is True, "Minimum price should pass flex"
        assert meets_dist_min is True, "Minimum price should pass distance"

        assert in_flex_within is True, "1.3 ct should pass flex (< 1.3835)"
        assert meets_dist_within is True, "1.3 ct should pass distance (< 7.847)"

        assert in_flex_high is False, "5 ct should fail flex (way above 1.3835 threshold)"
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
        # Flex threshold: 17.24 - ((17.24 - 8.26) * 0.20) = 17.24 - 1.796 = 15.444 ct
        # Distance threshold: 8.26 * (1 + 5/100) = 8.26 * 1.05 = 8.673 ct

        # Price scenarios
        price_at_max = 17.24  # Should pass both (at maximum)
        price_within_flex = 16.0  # Should pass flex (> 15.444)
        price_too_low = 14.0  # Should fail flex (< 15.444)

        in_flex_max, meets_dist_max = check_interval_criteria(price_at_max, criteria)
        in_flex_within, meets_dist_within = check_interval_criteria(price_within_flex, criteria)
        in_flex_low, meets_dist_low = check_interval_criteria(price_too_low, criteria)

        assert in_flex_max is True, "Maximum price should pass flex"
        assert meets_dist_max is True, "Maximum price should pass distance"

        assert in_flex_within is True, "16 ct should pass flex (> 15.444)"
        assert meets_dist_within is True, "16 ct should pass distance (> 8.673)"

        assert in_flex_low is False, "14 ct should fail flex (< 15.444 threshold)"
        # 14 ct is still above average (8.26), so should pass distance
        assert meets_dist_low is True, "14 ct should pass distance (> 8.673)"

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


@pytest.mark.unit
class TestNegativePriceFastPath:
    """
    Tests for the negative/zero price fast path.

    Regression Tests:
    - Negative prices not fully included in best price (Apr 2026): Even with
      VERY_CHEAP extension and max flex (50%), the old formula excluded large
      parts of a negative-price day because the flex band was anchored at the
      negative daily minimum. Example: min=-38 ct, flex=50% → threshold=-19 ct,
      excluding -18 ct, -10 ct, 0 ct, etc.
    """

    def test_negative_price_always_qualifies_best_price(self) -> None:
        """Any negative price unconditionally qualifies as best price (fast path)."""
        # Simulate tomorrow: min=-38 ct, avg=-3 ct
        criteria = TibberPricesIntervalCriteria(
            ref_price=-38.0,
            avg_price=-3.0,
            flex=0.15,
            min_distance_from_avg=5.0,
            reverse_sort=False,
        )
        for price in [-38.0, -20.0, -5.0, -0.01]:
            in_flex, meets_distance = check_interval_criteria(price, criteria)
            assert in_flex is True, f"Negative price {price} ct should always pass flex"
            assert meets_distance is True, f"Negative price {price} ct should always pass distance"

    def test_zero_price_always_qualifies_best_price(self) -> None:
        """Zero price unconditionally qualifies as best price (fast path)."""
        criteria = TibberPricesIntervalCriteria(
            ref_price=-10.0,
            avg_price=5.0,
            flex=0.15,
            min_distance_from_avg=5.0,
            reverse_sort=False,
        )
        in_flex, meets_distance = check_interval_criteria(0.0, criteria)
        assert in_flex is True, "Zero price should always pass flex"
        assert meets_distance is True, "Zero price should always pass distance"

    def test_negative_price_does_not_qualify_peak_price(self) -> None:
        """Negative prices should NOT qualify as peak prices."""
        # Even with high average, a negative price is never a "peak"
        criteria = TibberPricesIntervalCriteria(
            ref_price=30.0,
            avg_price=20.0,
            flex=0.50,
            min_distance_from_avg=5.0,
            reverse_sort=True,
        )
        in_flex, _meets_distance = check_interval_criteria(-5.0, criteria)
        assert in_flex is False, "Negative price should fail peak price flex check"

    def test_positive_price_is_not_auto_qualified_on_negative_day(self) -> None:
        """Positive prices must still pass the normal interval criteria."""
        criteria = TibberPricesIntervalCriteria(
            ref_price=-38.0,
            avg_price=5.0,
            flex=0.15,
            min_distance_from_avg=5.0,
            reverse_sort=False,
        )
        in_flex, meets_distance = check_interval_criteria(2.0, criteria)
        assert in_flex is False, "Positive prices should not get a day-global negative halo"
        assert meets_distance is True, "Distance may still pass even when flex fails"

    def test_regression_old_formula_would_exclude_most_intervals(self) -> None:
        """
        Regression: the old flex formula (anchored at negative min) excluded
        almost all intervals on a day with extreme negative prices.

        Old formula (BROKEN):
          flex_base = max(|avg - min|, |min|) = max(35, 38) = 38
          threshold = -38 + 38 * 0.15 = -32.3 ct
          → only prices ≤ -32.3 ct qualify!

        New formula:
          Fast path: price ≤ 0 → always (True, True)
          Zero-anchored: threshold = abs(-3) * 0.15 = 0.45 ct above zero
          → ALL negative prices qualify, plus tiny halo near 0
        """
        criteria = TibberPricesIntervalCriteria(
            ref_price=-38.0,
            avg_price=-3.0,
            flex=0.15,
            min_distance_from_avg=5.0,
            reverse_sort=False,
        )
        # All these prices should pass with new logic but would have FAILED with old logic
        prices_that_now_pass = [-32.0, -20.0, -10.0, -5.0, -1.0, -0.01, 0.0]
        for price in prices_that_now_pass:
            in_flex, meets_distance = check_interval_criteria(price, criteria)
            assert in_flex is True, f"Price {price} ct should pass with new logic (regression)"
            assert meets_distance is True, f"Price {price} ct should pass distance (regression)"


@pytest.mark.unit
class TestFlexBaseIsSpanToMean:
    """Flex is a share of |avg - ref| in both directions; the geometric bonus keeps max(span, |ref|)."""

    def test_best_price_flat_day_stays_below_mean(self) -> None:
        """Flat day: min 30, avg 33, flex 15% → threshold 30.45 ct (was 34.5, above the mean)."""
        criteria = TibberPricesIntervalCriteria(
            ref_price=30.0,
            avg_price=33.0,
            flex=0.15,
            min_distance_from_avg=0.0,
            reverse_sort=False,
        )
        assert check_interval_criteria(30.45, criteria)[0] is True
        assert check_interval_criteria(30.5, criteria)[0] is False

    @pytest.mark.parametrize(("reverse_sort", "ref"), [(False, 30.0), (True, 46.0)])
    def test_threshold_never_crosses_mean(self, *, reverse_sort: bool, ref: float) -> None:
        """At the 50% hard limit, a price at the mean fails flex in both directions."""
        criteria = TibberPricesIntervalCriteria(
            ref_price=ref,
            avg_price=38.0,
            flex=0.50,
            min_distance_from_avg=0.0,
            reverse_sort=reverse_sort,
        )
        assert check_interval_criteria(38.0, criteria)[0] is False

    def test_geometric_bonus_keeps_former_base_peak(self) -> None:
        """Peak bonus 10% widens by 10% of max (46 ct → 4.6 ct), not of the 8 ct span."""
        criteria = TibberPricesIntervalCriteria(
            ref_price=46.0,
            avg_price=38.0,
            flex=0.20,
            min_distance_from_avg=0.0,
            reverse_sort=True,
            geometric_flex=0.10,
        )
        # Threshold: 46 - (8 * 0.20) - (46 * 0.10) = 46 - 1.6 - 4.6 = 39.8 ct
        assert check_interval_criteria(39.8, criteria)[0] is True
        assert check_interval_criteria(39.7, criteria)[0] is False

    def test_geometric_bonus_keeps_former_base_best_v_shape(self) -> None:
        """Best on a V-shape day: the former base was the span, so the bonus uses it too."""
        criteria = TibberPricesIntervalCriteria(
            ref_price=1.0,
            avg_price=19.0,
            flex=0.15,
            min_distance_from_avg=0.0,
            reverse_sort=False,
            geometric_flex=0.10,
        )
        # Threshold: 1 + (18 * 0.15) + (18 * 0.10) = 1 + 2.7 + 1.8 = 5.5 ct
        assert check_interval_criteria(5.5, criteria)[0] is True
        assert check_interval_criteria(5.6, criteria)[0] is False
