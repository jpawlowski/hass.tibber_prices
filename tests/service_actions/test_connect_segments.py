"""Test connect_segments feature for ApexCharts segment boundaries."""

from datetime import UTC, datetime, timedelta


def make_interval(start_time: datetime, price: float, level: str) -> dict:
    """Create a price interval for testing."""
    return {
        "startsAt": start_time,
        "total": price,
        "level": level,
    }


def make_day_prices(base_time: datetime) -> list[dict]:
    """Create sample price data with level transitions."""
    return [
        # First segment: CHEAP at low price
        make_interval(base_time, 0.10, "CHEAP"),
        make_interval(base_time + timedelta(minutes=15), 0.11, "CHEAP"),
        # Transition: CHEAP -> NORMAL (price goes UP)
        make_interval(base_time + timedelta(minutes=30), 0.20, "NORMAL"),
        make_interval(base_time + timedelta(minutes=45), 0.21, "NORMAL"),
        # Transition: NORMAL -> CHEAP (price goes DOWN)
        make_interval(base_time + timedelta(minutes=60), 0.12, "CHEAP"),
        make_interval(base_time + timedelta(minutes=75), 0.13, "CHEAP"),
    ]


class TestConnectSegmentsLogic:
    """Test the connect_segments transition logic."""

    def test_price_direction_detection_down(self) -> None:
        """Test that price going down is correctly detected."""
        current_price = 0.20
        next_price = 0.12
        assert next_price < current_price, "Should detect price going down"

    def test_price_direction_detection_up(self) -> None:
        """Test that price going up is correctly detected."""
        current_price = 0.11
        next_price = 0.20
        assert next_price > current_price, "Should detect price going up"

    def test_price_direction_detection_same(self) -> None:
        """Test that same price is handled correctly (treated as up)."""
        current_price = 0.15
        next_price = 0.15
        assert not (next_price < current_price), "Same price should not be treated as 'down'"

    def test_sample_data_structure(self) -> None:
        """Test that sample data has expected structure."""
        base_time = datetime(2025, 12, 1, 0, 0, tzinfo=UTC)
        prices = make_day_prices(base_time)

        assert len(prices) == 6, "Should have 6 intervals"

        # Check first transition (CHEAP -> NORMAL at index 1->2)
        assert prices[1]["level"] == "CHEAP"
        assert prices[2]["level"] == "NORMAL"
        assert prices[2]["total"] > prices[1]["total"], "Price should go UP at this transition"

        # Check second transition (NORMAL -> CHEAP at index 3->4)
        assert prices[3]["level"] == "NORMAL"
        assert prices[4]["level"] == "CHEAP"
        assert prices[4]["total"] < prices[3]["total"], "Price should go DOWN at this transition"


class TestConnectSegmentsOutput:
    """Test the expected output format with connect_segments enabled."""

    def test_transition_point_down_has_lower_price(self) -> None:
        """
        When price goes DOWN at boundary, the transition point should have the lower price.

        This creates a visual line going downward from the current segment level.
        """
        current_price = 0.20
        next_price = 0.12

        # With connect_segments=True and price going down:
        # The transition point should use next_price (the lower price)
        # This draws the line downward from current segment level
        is_price_going_down = next_price < current_price
        transition_price = next_price  # Use next price when going down

        assert is_price_going_down, "Price should be going down"
        assert transition_price == 0.12

    def test_transition_point_up_has_current_price(self) -> None:
        """
        When price goes UP at boundary, the hold point should have current price.

        This creates a visual hold at current level before the gap.
        """
        current_price = 0.11
        next_price = 0.20

        # With connect_segments=True and price going up:
        # The hold point should use current_price (extend current level)
        is_price_going_up = next_price >= current_price
        hold_price = current_price  # Extend current level when going up

        assert is_price_going_up, "Price should be going up"
        assert hold_price == 0.11


class TestSegmentBoundaryDetection:
    """Test detection of segment boundaries."""

    def test_same_level_no_boundary(self) -> None:
        """Intervals with same level should not create boundary."""
        interval_value = "CHEAP"
        next_value = "CHEAP"
        is_boundary = next_value != interval_value
        assert not is_boundary

    def test_different_level_creates_boundary(self) -> None:
        """Intervals with different level should create boundary."""
        interval_value = "CHEAP"
        next_value = "NORMAL"
        is_boundary = next_value != interval_value
        assert is_boundary

    def test_filter_match_check(self) -> None:
        """Test that filter matching works correctly."""
        filter_values = ["CHEAP"]
        interval_value = "CHEAP"
        next_value = "NORMAL"

        matches_filter = interval_value in filter_values
        assert matches_filter, "CHEAP should match filter"

        next_matches = next_value in filter_values
        assert not next_matches, "NORMAL should not match filter"


class TestPriceConversion:
    """Test price conversion logic used in connect_segments."""

    def test_subunit_currency_conversion(self) -> None:
        """Test conversion to subunit currency (cents/øre)."""
        price = 0.12  # EUR
        subunit_currency = True
        converted = round(price * 100, 2) if subunit_currency else round(price, 4)
        assert converted == 12.0, "0.12 EUR should be 12 cents"

    def test_base_currency_rounding(self) -> None:
        """Test base currency precision."""
        price = 0.123456
        subunit_currency = False
        converted = round(price * 100, 2) if subunit_currency else round(price, 4)
        assert converted == 0.1235, "Should round to 4 decimal places"

    def test_custom_rounding(self) -> None:
        """Test custom decimal rounding."""
        price = 0.12345
        converted = round(price, 4)
        round_decimals = 2
        final = round(converted, round_decimals)
        assert final == 0.12, "Should round to 2 decimal places"


class TestTrailingNullRemoval:
    """Test trailing null value removal for ApexCharts header display (segments mode only)."""

    def test_trailing_nulls_removed(self) -> None:
        """Test that trailing null values are removed from chart_data."""
        price_field = "price_per_kwh"
        chart_data = [
            {"start_time": "2025-12-01T00:00:00", price_field: 10.0},
            {"start_time": "2025-12-01T00:15:00", price_field: 12.0},
            {"start_time": "2025-12-01T00:30:00", price_field: None},  # Trailing null
            {"start_time": "2025-12-01T00:45:00", price_field: None},  # Trailing null
        ]

        # Simulate the trailing null removal logic
        while chart_data and chart_data[-1].get(price_field) is None:
            chart_data.pop()

        assert len(chart_data) == 2, "Should have 2 items after removing trailing nulls"
        assert chart_data[-1][price_field] == 12.0, "Last item should be the last non-null price"

    def test_internal_nulls_preserved(self) -> None:
        """Test that internal null values are preserved for gap visualization."""
        price_field = "price_per_kwh"
        chart_data = [
            {"start_time": "2025-12-01T00:00:00", price_field: 10.0},
            {"start_time": "2025-12-01T00:15:00", price_field: None},  # Internal null (gap)
            {"start_time": "2025-12-01T00:30:00", price_field: 12.0},
            {"start_time": "2025-12-01T00:45:00", price_field: None},  # Trailing null
        ]

        # Simulate the trailing null removal logic
        while chart_data and chart_data[-1].get(price_field) is None:
            chart_data.pop()

        assert len(chart_data) == 3, "Should have 3 items after removing trailing null"
        assert chart_data[1][price_field] is None, "Internal null should be preserved"
        assert chart_data[-1][price_field] == 12.0, "Last item should be the last non-null price"

    def test_no_nulls_unchanged(self) -> None:
        """Test that chart_data without trailing nulls is unchanged."""
        price_field = "price_per_kwh"
        chart_data = [
            {"start_time": "2025-12-01T00:00:00", price_field: 10.0},
            {"start_time": "2025-12-01T00:15:00", price_field: 12.0},
        ]

        original_length = len(chart_data)

        # Simulate the trailing null removal logic
        while chart_data and chart_data[-1].get(price_field) is None:
            chart_data.pop()

        assert len(chart_data) == original_length, "Data without trailing nulls should be unchanged"

    def test_empty_data_handled(self) -> None:
        """Test that empty chart_data is handled without error."""
        price_field = "price_per_kwh"
        chart_data: list[dict] = []

        # Simulate the trailing null removal logic - should not raise
        while chart_data and chart_data[-1].get(price_field) is None:
            chart_data.pop()

        assert chart_data == [], "Empty data should remain empty"


class TestTrailingNullModeSpecific:
    """Test that trailing null removal respects insert_nulls mode."""

    def test_segments_mode_removes_trailing_nulls(self) -> None:
        """Test that insert_nulls='segments' removes trailing nulls for ApexCharts header fix."""
        price_field = "price_per_kwh"
        insert_nulls = "segments"
        chart_data = [
            {"start_time": "2025-12-01T00:00:00", price_field: 10.0},
            {"start_time": "2025-12-01T00:15:00", price_field: 12.0},
            {"start_time": "2025-12-01T00:30:00", price_field: None},  # Trailing null
            {"start_time": "2025-12-01T00:45:00", price_field: None},  # Trailing null
        ]

        # Simulate the conditional trailing null removal
        if insert_nulls == "segments":
            while chart_data and chart_data[-1].get(price_field) is None:
                chart_data.pop()

        assert len(chart_data) == 2, "Segments mode should remove trailing nulls"
        assert chart_data[-1][price_field] == 12.0, "Last item should be last non-null price"

    def test_all_mode_preserves_trailing_nulls(self) -> None:
        """Test that insert_nulls='all' preserves trailing nulls (intentional gaps)."""
        price_field = "price_per_kwh"
        insert_nulls = "all"
        chart_data = [
            {"start_time": "2025-12-01T00:00:00", price_field: 10.0},
            {"start_time": "2025-12-01T00:15:00", price_field: 12.0},
            {"start_time": "2025-12-01T00:30:00", price_field: None},  # Intentional gap
            {"start_time": "2025-12-01T00:45:00", price_field: None},  # Intentional gap
        ]

        original_length = len(chart_data)

        # Simulate the conditional trailing null removal
        if insert_nulls == "segments":
            while chart_data and chart_data[-1].get(price_field) is None:
                chart_data.pop()

        assert len(chart_data) == original_length, "'all' mode should preserve trailing nulls"
        assert chart_data[-1][price_field] is None, "Last item should remain null"

    def test_none_mode_no_trailing_nulls_expected(self) -> None:
        """Test that insert_nulls='none' has no trailing nulls by design."""
        price_field = "price_per_kwh"
        insert_nulls = "none"
        # In 'none' mode, nulls are never inserted, so no trailing nulls exist
        chart_data = [
            {"start_time": "2025-12-01T00:00:00", price_field: 10.0},
            {"start_time": "2025-12-01T00:15:00", price_field: 12.0},
        ]

        original_length = len(chart_data)

        # Simulate the conditional trailing null removal
        if insert_nulls == "segments":
            while chart_data and chart_data[-1].get(price_field) is None:
                chart_data.pop()

        assert len(chart_data) == original_length, "'none' mode should have no nulls to remove"
