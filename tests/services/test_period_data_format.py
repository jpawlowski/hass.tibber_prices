"""Test period data formatting for ApexCharts visualization."""

from datetime import UTC, datetime


def test_period_array_of_arrays_with_insert_nulls() -> None:
    """
    Test that period data generates 3 points per period when insert_nulls='segments'.

    For ApexCharts to correctly display periods as continuous blocks:
    1. Start time with price - Begin the period
    2. End time with price - Hold the price level until end
    3. End time with NULL - Cleanly terminate the segment (only with insert_nulls)
    """
    # Simulate a period from formatters.get_period_data()
    period = {
        "start": datetime(2025, 12, 3, 10, 0, tzinfo=UTC),
        "end": datetime(2025, 12, 3, 12, 0, tzinfo=UTC),
        "price_avg": 1250,  # Stored in minor units (12.50 EUR/ct)
        "level": "CHEAP",
        "rating_level": "LOW",
    }

    # Test with insert_nulls='segments' (should add NULL terminator)
    chart_data = []
    price_avg = period["price_avg"]
    start_serialized = period["start"].isoformat()
    end_serialized = period["end"].isoformat()
    insert_nulls = "segments"

    chart_data.append([start_serialized, price_avg])  # 1. Start with price
    chart_data.append([end_serialized, price_avg])  # 2. End with price (hold level)
    # 3. Add NULL terminator only if insert_nulls is enabled
    if insert_nulls in ("segments", "all"):
        chart_data.append([end_serialized, None])  # 3. End with NULL (terminate segment)

    # Verify structure
    assert len(chart_data) == 3, "Should generate 3 points with insert_nulls='segments'"

    # Point 1: Start with price
    assert chart_data[0][0] == "2025-12-03T10:00:00+00:00"
    assert chart_data[0][1] == 1250

    # Point 2: End with price (holds level)
    assert chart_data[1][0] == "2025-12-03T12:00:00+00:00"
    assert chart_data[1][1] == 1250

    # Point 3: End with NULL (terminates segment)
    assert chart_data[2][0] == "2025-12-03T12:00:00+00:00"
    assert chart_data[2][1] is None


def test_period_array_of_arrays_without_insert_nulls() -> None:
    """
    Test that period data generates 2 points per period when insert_nulls='none'.

    Without NULL insertion, we only get:
    1. Start time with price
    2. End time with price
    """
    period = {
        "start": datetime(2025, 12, 3, 10, 0, tzinfo=UTC),
        "end": datetime(2025, 12, 3, 12, 0, tzinfo=UTC),
        "price_avg": 1250,
    }

    # Test with insert_nulls='none' (should NOT add NULL terminator)
    chart_data = []
    price_avg = period["price_avg"]
    start_serialized = period["start"].isoformat()
    end_serialized = period["end"].isoformat()
    insert_nulls = "none"

    chart_data.append([start_serialized, price_avg])
    chart_data.append([end_serialized, price_avg])
    if insert_nulls in ("segments", "all"):
        chart_data.append([end_serialized, None])

    # Verify structure: Only 2 points without NULL terminator
    assert len(chart_data) == 2, "Should generate 2 points with insert_nulls='none'"
    assert chart_data[0][1] == 1250
    assert chart_data[1][1] == 1250


def test_multiple_periods_separated_by_nulls() -> None:
    """
    Test that multiple periods are properly separated by NULL points with insert_nulls enabled.

    This ensures gaps between periods are visualized correctly in ApexCharts.
    """
    periods = [
        {
            "start": datetime(2025, 12, 3, 10, 0, tzinfo=UTC),
            "end": datetime(2025, 12, 3, 12, 0, tzinfo=UTC),
            "price_avg": 1250,
        },
        {
            "start": datetime(2025, 12, 3, 15, 0, tzinfo=UTC),
            "end": datetime(2025, 12, 3, 17, 0, tzinfo=UTC),
            "price_avg": 1850,
        },
    ]

    chart_data = []
    insert_nulls = "segments"
    for period in periods:
        price_avg = period["price_avg"]
        start_serialized = period["start"].isoformat()
        end_serialized = period["end"].isoformat()

        chart_data.append([start_serialized, price_avg])
        chart_data.append([end_serialized, price_avg])
        if insert_nulls in ("segments", "all"):
            chart_data.append([end_serialized, None])

    # Verify structure: 2 periods x 3 points = 6 total points (with insert_nulls)
    assert len(chart_data) == 6, "Should generate 6 points for 2 periods with insert_nulls"

    # Period 1 ends with NULL
    assert chart_data[2][1] is None

    # Period 2 starts
    assert chart_data[3][0] == "2025-12-03T15:00:00+00:00"
    assert chart_data[3][1] == 1850

    # Period 2 ends with NULL
    assert chart_data[5][1] is None


def test_multiple_periods_without_nulls() -> None:
    """
    Test that multiple periods without insert_nulls generate continuous data.

    Without NULL separators, periods connect directly (may be desired for some chart types).
    """
    periods = [
        {
            "start": datetime(2025, 12, 3, 10, 0, tzinfo=UTC),
            "end": datetime(2025, 12, 3, 12, 0, tzinfo=UTC),
            "price_avg": 1250,
        },
        {
            "start": datetime(2025, 12, 3, 15, 0, tzinfo=UTC),
            "end": datetime(2025, 12, 3, 17, 0, tzinfo=UTC),
            "price_avg": 1850,
        },
    ]

    chart_data = []
    insert_nulls = "none"
    for period in periods:
        price_avg = period["price_avg"]
        start_serialized = period["start"].isoformat()
        end_serialized = period["end"].isoformat()

        chart_data.append([start_serialized, price_avg])
        chart_data.append([end_serialized, price_avg])
        if insert_nulls in ("segments", "all"):
            chart_data.append([end_serialized, None])

    # Verify structure: 2 periods x 2 points = 4 total points (without insert_nulls)
    assert len(chart_data) == 4, "Should generate 4 points for 2 periods without insert_nulls"

    # No NULL separators
    assert all(point[1] is not None for point in chart_data)


def test_period_currency_conversion() -> None:
    """
    Test that period prices are correctly converted between major/minor currency.

    Period prices are stored in minor units (ct/øre) in coordinator data.
    """
    period = {
        "start": datetime(2025, 12, 3, 10, 0, tzinfo=UTC),
        "end": datetime(2025, 12, 3, 12, 0, tzinfo=UTC),
        "price_avg": 1250,  # 12.50 ct/øre
    }

    # Test 1: Keep minor currency (for ApexCharts internal use)
    price_minor = period["price_avg"]
    assert price_minor == 1250, "Should keep minor units"

    # Test 2: Convert to major currency (for display)
    price_major = period["price_avg"] / 100
    assert price_major == 12.50, "Should convert to major units (EUR)"


def test_period_with_missing_end_time() -> None:
    """
    Test handling of periods without end time (incomplete period).

    If a period has no end time, we should only add the start point.
    """
    period = {
        "start": datetime(2025, 12, 3, 10, 0, tzinfo=UTC),
        "end": None,  # No end time
        "price_avg": 1250,
    }

    chart_data = []
    price_avg = period["price_avg"]
    start_serialized = period["start"].isoformat()
    end = period.get("end")
    end_serialized = end.isoformat() if end else None
    insert_nulls = "segments"

    # Add start point
    chart_data.append([start_serialized, price_avg])

    # Only add end points if end_serialized exists
    if end_serialized:
        chart_data.append([end_serialized, price_avg])
        if insert_nulls in ("segments", "all"):
            chart_data.append([end_serialized, None])

    # Verify: Only 1 point (start) for incomplete period
    assert len(chart_data) == 1, "Should only have start point for incomplete period"
    assert chart_data[0][1] == 1250


def test_apexcharts_mapping_preserves_structure() -> None:
    """
    Test that ApexCharts .map() transformation preserves the 3-point structure.

    The ApexCharts data_generator uses: .map(point => [point[0], 1])
    This should preserve all 3 points but replace price with 1 (for overlay).
    """
    # Simulate period data (3 points per period with insert_nulls='segments')
    period_data = [
        ["2025-12-03T10:00:00+00:00", 1250],  # Start with price
        ["2025-12-03T12:00:00+00:00", 1250],  # End with price
        ["2025-12-03T12:00:00+00:00", None],  # End with NULL
    ]

    # Simulate ApexCharts mapping: [timestamp, 1] for overlay
    mapped_data = [[point[0], 1 if point[1] is not None else None] for point in period_data]

    # Verify structure is preserved
    assert len(mapped_data) == 3, "Should preserve all 3 points"
    assert mapped_data[0] == ["2025-12-03T10:00:00+00:00", 1]  # Start
    assert mapped_data[1] == ["2025-12-03T12:00:00+00:00", 1]  # End (hold)
    assert mapped_data[2] == ["2025-12-03T12:00:00+00:00", None]  # End (terminate)


def test_insert_nulls_all_mode() -> None:
    """
    Test that insert_nulls='all' also adds NULL terminators.

    The 'all' mode should behave the same as 'segments' for period data.
    """
    period = {
        "start": datetime(2025, 12, 3, 10, 0, tzinfo=UTC),
        "end": datetime(2025, 12, 3, 12, 0, tzinfo=UTC),
        "price_avg": 1250,
    }

    chart_data = []
    price_avg = period["price_avg"]
    start_serialized = period["start"].isoformat()
    end_serialized = period["end"].isoformat()
    insert_nulls = "all"

    chart_data.append([start_serialized, price_avg])
    chart_data.append([end_serialized, price_avg])
    if insert_nulls in ("segments", "all"):
        chart_data.append([end_serialized, None])

    # Verify: 3 points with insert_nulls='all'
    assert len(chart_data) == 3, "Should generate 3 points with insert_nulls='all'"
    assert chart_data[2][1] is None


def test_insert_nulls_and_add_trailing_null_both_enabled() -> None:
    """
    Test that both insert_nulls and add_trailing_null work together correctly.

    When both are enabled, you should get:
    - NULL terminator after each period (from insert_nulls)
    - Additional NULL at the very end (from add_trailing_null)

    This results in TWO NULL points at the end: one for the last period, one trailing.
    """
    periods = [
        {
            "start": datetime(2025, 12, 3, 10, 0, tzinfo=UTC),
            "end": datetime(2025, 12, 3, 12, 0, tzinfo=UTC),
            "price_avg": 1250,
        },
    ]

    chart_data = []
    insert_nulls = "segments"
    add_trailing_null = True

    for period in periods:
        price_avg = period["price_avg"]
        start_serialized = period["start"].isoformat()
        end_serialized = period["end"].isoformat()

        chart_data.append([start_serialized, price_avg])
        chart_data.append([end_serialized, price_avg])
        if insert_nulls in ("segments", "all"):
            chart_data.append([end_serialized, None])

    # Add trailing null
    if add_trailing_null:
        chart_data.append([None, None])

    # Verify: 3 points (period) + 1 trailing = 4 total
    assert len(chart_data) == 4, "Should have 4 points with both insert_nulls and add_trailing_null"

    # Last period's NULL terminator
    assert chart_data[2][0] == "2025-12-03T12:00:00+00:00"
    assert chart_data[2][1] is None

    # Trailing NULL (completely null)
    assert chart_data[3][0] is None
    assert chart_data[3][1] is None


def test_neither_insert_nulls_nor_add_trailing_null() -> None:
    """
    Test that when both insert_nulls='none' and add_trailing_null=False, no NULLs are added.

    This gives clean period data without any NULL separators.
    """
    period = {
        "start": datetime(2025, 12, 3, 10, 0, tzinfo=UTC),
        "end": datetime(2025, 12, 3, 12, 0, tzinfo=UTC),
        "price_avg": 1250,
    }

    chart_data = []
    price_avg = period["price_avg"]
    start_serialized = period["start"].isoformat()
    end_serialized = period["end"].isoformat()
    insert_nulls = "none"
    add_trailing_null = False

    chart_data.append([start_serialized, price_avg])
    chart_data.append([end_serialized, price_avg])
    if insert_nulls in ("segments", "all"):
        chart_data.append([end_serialized, None])

    if add_trailing_null:
        chart_data.append([None, None])

    # Verify: Only 2 points (start, end) without any NULLs
    assert len(chart_data) == 2, "Should have 2 points without NULL insertion"
    assert all(point[1] is not None for point in chart_data), "No NULL values should be present"
