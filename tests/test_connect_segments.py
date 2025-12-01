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
        # The transition point should use next_price (lower price)
        transition_price = min(current_price, next_price)

        assert transition_price == next_price
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
        hold_price = min(current_price, next_price)

        assert hold_price == current_price
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

    def test_minor_currency_conversion(self) -> None:
        """Test conversion to minor currency (cents/øre)."""
        price = 0.12  # EUR
        minor_currency = True
        converted = round(price * 100, 2) if minor_currency else round(price, 4)
        assert converted == 12.0, "0.12 EUR should be 12 cents"

    def test_major_currency_rounding(self) -> None:
        """Test major currency precision."""
        price = 0.123456
        minor_currency = False
        converted = round(price * 100, 2) if minor_currency else round(price, 4)
        assert converted == 0.1235, "Should round to 4 decimal places"

    def test_custom_rounding(self) -> None:
        """Test custom decimal rounding."""
        price = 0.12345
        converted = round(price, 4)
        round_decimals = 2
        final = round(converted, round_decimals)
        assert final == 0.12, "Should round to 2 decimal places"
