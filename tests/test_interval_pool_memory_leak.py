"""
Tests for memory leak prevention in interval pool.

This test module verifies that touch operations don't cause memory leaks by:
1. Reusing existing interval dicts (Python references, not copies)
2. Dead intervals being cleaned up by GC
3. Serialization filtering out dead intervals from storage
"""

import json
from datetime import UTC, datetime

import pytest

from custom_components.tibber_prices.interval_pool.pool import (
    TibberPricesIntervalPool,
)


@pytest.fixture
def pool() -> TibberPricesIntervalPool:
    """Create a shared interval pool for testing (single-home architecture)."""
    return TibberPricesIntervalPool(home_id="test_home_id")


@pytest.fixture
def sample_intervals() -> list[dict]:
    """Create 24 sample intervals (1 day)."""
    base_time = datetime(2025, 11, 25, 0, 0, 0, tzinfo=UTC)
    return [
        {
            "startsAt": (base_time.replace(hour=h)).isoformat(),
            "total": 10.0 + h,
            "energy": 8.0 + h,
            "tax": 2.0,
        }
        for h in range(24)
    ]


def test_touch_operation_reuses_existing_intervals(
    pool: TibberPricesIntervalPool,
) -> None:
    """Test that touch operations reuse existing interval dicts (references, not copies)."""
    # home_id not needed (single-home architecture)
    fetch_time_1 = "2025-11-25T10:00:00+01:00"
    fetch_time_2 = "2025-11-25T10:15:00+01:00"

    # Create sample intervals for this test
    sample_intervals = [
        {
            "startsAt": datetime(2025, 11, 25, h, 0, 0, tzinfo=UTC).isoformat(),
            "total": 10.0 + h,
        }
        for h in range(24)
    ]

    # First fetch: Add intervals
    pool._add_intervals(sample_intervals, fetch_time_1)  # noqa: SLF001

    # Direct property access (single-home architecture)
    fetch_groups = pool._fetch_groups  # noqa: SLF001

    # Verify: 1 fetch group with 24 intervals
    assert len(fetch_groups) == 1
    assert len(fetch_groups[0]["intervals"]) == 24

    # Get reference to first interval
    first_interval_original = fetch_groups[0]["intervals"][0]
    original_id = id(first_interval_original)

    # Second fetch: Touch same intervals
    pool._add_intervals(sample_intervals, fetch_time_2)  # noqa: SLF001

    # Verify: Now we have 2 fetch groups
    assert len(fetch_groups) == 2

    # Get reference to first interval from TOUCH group
    first_interval_touched = fetch_groups[1]["intervals"][0]
    touched_id = id(first_interval_touched)

    # CRITICAL: Should be SAME object (same memory address)
    assert original_id == touched_id, f"Memory addresses differ: {original_id} != {touched_id}"
    assert first_interval_original is first_interval_touched, "Touch should reuse existing dict, not create copy"


def test_touch_operation_leaves_dead_intervals_in_old_group(
    pool: TibberPricesIntervalPool,
) -> None:
    """Test that touch operations leave 'dead' intervals in old fetch groups."""
    # home_id not needed (single-home architecture)
    fetch_time_1 = "2025-11-25T10:00:00+01:00"
    fetch_time_2 = "2025-11-25T10:15:00+01:00"

    # Create sample intervals
    sample_intervals = [
        {
            "startsAt": datetime(2025, 11, 25, h, 0, 0, tzinfo=UTC).isoformat(),
            "total": 10.0 + h,
        }
        for h in range(24)
    ]

    # First fetch
    pool._add_intervals(sample_intervals, fetch_time_1)  # noqa: SLF001
    # Direct property access (single-home architecture)
    fetch_groups = pool._fetch_groups  # noqa: SLF001

    # Second fetch (touch all intervals)
    pool._add_intervals(sample_intervals, fetch_time_2)  # noqa: SLF001

    # BEFORE GC cleanup:
    # - Old group still has 24 intervals (but they're all "dead" - index points elsewhere)
    # - Touch group has 24 intervals (living - index points here)

    assert len(fetch_groups) == 2, "Should have 2 fetch groups"
    assert len(fetch_groups[0]["intervals"]) == 24, "Old group should still have intervals (dead)"
    assert len(fetch_groups[1]["intervals"]) == 24, "Touch group should have intervals (living)"

    # Verify index points to touch group (not old group)
    timestamp_index = pool._timestamp_index  # noqa: SLF001
    first_key = sample_intervals[0]["startsAt"][:19]
    index_entry = timestamp_index[first_key]

    assert index_entry["fetch_group_index"] == 1, "Index should point to touch group"


def test_gc_cleanup_removes_dead_intervals(
    pool: TibberPricesIntervalPool,
) -> None:
    """Test that GC cleanup removes dead intervals from old fetch groups."""
    # home_id not needed (single-home architecture)
    fetch_time_1 = "2025-11-25T10:00:00+01:00"
    fetch_time_2 = "2025-11-25T10:15:00+01:00"

    # Create sample intervals
    sample_intervals = [
        {
            "startsAt": datetime(2025, 11, 25, h, 0, 0, tzinfo=UTC).isoformat(),
            "total": 10.0 + h,
        }
        for h in range(24)
    ]

    # First fetch
    pool._add_intervals(sample_intervals, fetch_time_1)  # noqa: SLF001

    # Second fetch (touch all intervals)
    pool._add_intervals(sample_intervals, fetch_time_2)  # noqa: SLF001

    # Direct property access (single-home architecture)
    fetch_groups = pool._fetch_groups  # noqa: SLF001
    timestamp_index = pool._timestamp_index  # noqa: SLF001

    # Before cleanup: old group has 24 intervals
    assert len(fetch_groups[0]["intervals"]) == 24, "Before cleanup"

    # Run GC cleanup explicitly
    dead_count = pool._gc_cleanup_dead_intervals(fetch_groups, timestamp_index)  # noqa: SLF001

    # Verify: 24 dead intervals were removed
    assert dead_count == 24, f"Expected 24 dead intervals, got {dead_count}"

    # After cleanup: old group should be empty
    assert len(fetch_groups[0]["intervals"]) == 0, "Old group should be empty after cleanup"

    # Touch group still has 24 living intervals
    assert len(fetch_groups[1]["intervals"]) == 24, "Touch group should still have intervals"


def test_serialization_excludes_dead_intervals(
    pool: TibberPricesIntervalPool,
) -> None:
    """Test that to_dict() excludes dead intervals from serialization."""
    # home_id not needed (single-home architecture)
    fetch_time_1 = "2025-11-25T10:00:00+01:00"
    fetch_time_2 = "2025-11-25T10:15:00+01:00"

    # Create sample intervals
    sample_intervals = [
        {
            "startsAt": datetime(2025, 11, 25, h, 0, 0, tzinfo=UTC).isoformat(),
            "total": 10.0 + h,
        }
        for h in range(24)
    ]

    # First fetch
    pool._add_intervals(sample_intervals, fetch_time_1)  # noqa: SLF001

    # Second fetch (touch all intervals)
    pool._add_intervals(sample_intervals, fetch_time_2)  # noqa: SLF001

    # Serialize WITHOUT running GC cleanup first
    serialized = pool.to_dict()

    # Verify serialization structure
    assert "fetch_groups" in serialized
    assert "home_id" in serialized
    fetch_groups = serialized["fetch_groups"]

    # CRITICAL: Should only serialize touch group (living intervals)
    # Old group with all dead intervals should NOT be serialized
    assert len(fetch_groups) == 1, "Should only serialize groups with living intervals"

    # Touch group should have all 24 intervals
    assert len(fetch_groups[0]["intervals"]) == 24, "Touch group should have all intervals"

    # Verify JSON size is reasonable (not 2x the size)
    json_str = json.dumps(serialized)
    json_size = len(json_str)
    # Each interval is ~100-150 bytes, 24 intervals = ~2.4-3.6 KB
    # With metadata + structure, expect < 5 KB
    assert json_size < 5000, f"JSON too large: {json_size} bytes (expected < 5000)"


def test_repeated_touch_operations_dont_grow_storage(
    pool: TibberPricesIntervalPool,
) -> None:
    """Test that repeated touch operations don't grow storage size unbounded."""
    # home_id not needed (single-home architecture)

    # Create sample intervals
    sample_intervals = [
        {
            "startsAt": datetime(2025, 11, 25, h, 0, 0, tzinfo=UTC).isoformat(),
            "total": 10.0 + h,
        }
        for h in range(24)
    ]

    # Simulate 10 re-fetches of the same intervals
    for i in range(10):
        fetch_time = f"2025-11-25T{10 + i}:00:00+01:00"
        pool._add_intervals(sample_intervals, fetch_time)  # noqa: SLF001

    # Memory state: 10 fetch groups (9 empty, 1 with all intervals)
    # Direct property access (single-home architecture)
    fetch_groups = pool._fetch_groups  # noqa: SLF001
    assert len(fetch_groups) == 10, "Should have 10 fetch groups in memory"

    # Total intervals in memory: 240 references (24 per group, mostly dead)
    total_refs = sum(len(g["intervals"]) for g in fetch_groups)
    assert total_refs == 24 * 10, "Memory should have 240 interval references"

    # Serialize (filters dead intervals)
    serialized = pool.to_dict()
    serialized_groups = serialized["fetch_groups"]

    # Storage should only have 1 group with 24 living intervals
    assert len(serialized_groups) == 1, "Should only serialize 1 group (with living intervals)"
    assert len(serialized_groups[0]["intervals"]) == 24, "Should only have 24 living intervals"

    # Verify storage size is bounded
    json_str = json.dumps(serialized)
    json_size = len(json_str)
    # Should still be < 10 KB even after 10 fetches
    assert json_size < 10000, f"Storage grew unbounded: {json_size} bytes (expected < 10000)"


def test_gc_cleanup_with_partial_touch(
    pool: TibberPricesIntervalPool,
    sample_intervals: list[dict],
) -> None:
    """Test GC cleanup when only some intervals are touched (partial overlap)."""
    # home_id not needed (single-home architecture)
    fetch_time_1 = "2025-11-25T10:00:00+01:00"
    fetch_time_2 = "2025-11-25T10:15:00+01:00"

    # First fetch: All 24 intervals
    pool._add_intervals(sample_intervals, fetch_time_1)  # noqa: SLF001

    # Second fetch: Only first 12 intervals (partial touch)
    partial_intervals = sample_intervals[:12]
    pool._add_intervals(partial_intervals, fetch_time_2)  # noqa: SLF001

    # Direct property access (single-home architecture)
    fetch_groups = pool._fetch_groups  # noqa: SLF001
    timestamp_index = pool._timestamp_index  # noqa: SLF001

    # Before cleanup:
    # - Old group: 24 intervals (12 dead, 12 living)
    # - Touch group: 12 intervals (all living)
    assert len(fetch_groups[0]["intervals"]) == 24, "Old group should have 24 intervals"
    assert len(fetch_groups[1]["intervals"]) == 12, "Touch group should have 12 intervals"

    # Run GC cleanup
    dead_count = pool._gc_cleanup_dead_intervals(fetch_groups, timestamp_index)  # noqa: SLF001

    # Should clean 12 dead intervals (the ones that were touched)
    assert dead_count == 12, f"Expected 12 dead intervals, got {dead_count}"

    # After cleanup:
    # - Old group: 12 intervals (the ones that were NOT touched)
    # - Touch group: 12 intervals (unchanged)
    assert len(fetch_groups[0]["intervals"]) == 12, "Old group should have 12 living intervals left"
    assert len(fetch_groups[1]["intervals"]) == 12, "Touch group should still have 12 intervals"


def test_memory_leak_prevention_integration(
    pool: TibberPricesIntervalPool,
) -> None:
    """Integration test: Verify no memory leak over multiple operations."""
    # home_id not needed (single-home architecture)

    # Create sample intervals
    sample_intervals = [
        {
            "startsAt": datetime(2025, 11, 25, h, 0, 0, tzinfo=UTC).isoformat(),
            "total": 10.0 + h,
        }
        for h in range(24)
    ]

    # Simulate typical usage pattern over time
    # Day 1: Fetch 24 intervals
    pool._add_intervals(sample_intervals, "2025-11-25T10:00:00+01:00")  # noqa: SLF001

    # Day 1: Re-fetch (touch) - updates fetch time
    pool._add_intervals(sample_intervals, "2025-11-25T14:00:00+01:00")  # noqa: SLF001

    # Day 1: Re-fetch (touch) again
    pool._add_intervals(sample_intervals, "2025-11-25T18:00:00+01:00")  # noqa: SLF001

    # Direct property access (single-home architecture)
    fetch_groups = pool._fetch_groups  # noqa: SLF001
    timestamp_index = pool._timestamp_index  # noqa: SLF001

    # Memory state BEFORE cleanup:
    # - 3 fetch groups
    # - Total: 72 interval references (24 per group)
    # - Dead: 48 (first 2 groups have all dead intervals)
    # - Living: 24 (last group has all living intervals)
    assert len(fetch_groups) == 3, "Should have 3 fetch groups"
    total_refs = sum(len(g["intervals"]) for g in fetch_groups)
    assert total_refs == 72, "Should have 72 interval references in memory"

    # Run GC cleanup
    dead_count = pool._gc_cleanup_dead_intervals(fetch_groups, timestamp_index)  # noqa: SLF001
    assert dead_count == 48, "Should clean 48 dead intervals"

    # Memory state AFTER cleanup:
    # - 3 fetch groups (2 empty, 1 with all intervals)
    # - Total: 24 interval references
    # - Dead: 0
    # - Living: 24
    total_refs_after = sum(len(g["intervals"]) for g in fetch_groups)
    assert total_refs_after == 24, "Should only have 24 interval references after cleanup"

    # Verify serialization excludes empty groups
    serialized = pool.to_dict()
    serialized_groups = serialized["fetch_groups"]

    # Should only serialize 1 group (the one with living intervals)
    assert len(serialized_groups) == 1, "Should only serialize groups with living intervals"
    assert len(serialized_groups[0]["intervals"]) == 24, "Should have 24 intervals"


def test_interval_identity_preserved_across_touch(
    pool: TibberPricesIntervalPool,
) -> None:
    """Test that interval dict identity (memory address) is preserved across touch."""
    # home_id not needed (single-home architecture)

    # Create sample intervals
    sample_intervals = [
        {
            "startsAt": datetime(2025, 11, 25, h, 0, 0, tzinfo=UTC).isoformat(),
            "total": 10.0 + h,
        }
        for h in range(24)
    ]

    # First fetch
    pool._add_intervals(sample_intervals, "2025-11-25T10:00:00+01:00")  # noqa: SLF001

    # Direct property access (single-home architecture)
    fetch_groups = pool._fetch_groups  # noqa: SLF001

    # Collect memory addresses of intervals in original group
    original_ids = [id(interval) for interval in fetch_groups[0]["intervals"]]

    # Second fetch (touch)
    pool._add_intervals(sample_intervals, "2025-11-25T10:15:00+01:00")  # noqa: SLF001

    # Collect memory addresses of intervals in touch group
    touched_ids = [id(interval) for interval in fetch_groups[1]["intervals"]]

    # CRITICAL: All memory addresses should be identical (same objects)
    assert original_ids == touched_ids, "Touch should preserve interval identity (memory addresses)"

    # Third fetch (touch again)
    pool._add_intervals(sample_intervals, "2025-11-25T10:30:00+01:00")  # noqa: SLF001

    # New touch group should also reference the SAME original objects
    touched_ids_2 = [id(interval) for interval in fetch_groups[2]["intervals"]]
    assert original_ids == touched_ids_2, "Multiple touches should preserve original identity"

    # Verify: All 3 groups have references to THE SAME interval dicts
    # Only the list entries differ (8 bytes each), not the interval dicts (600+ bytes each)
    for i in range(24):
        assert fetch_groups[0]["intervals"][i] is fetch_groups[1]["intervals"][i] is fetch_groups[2]["intervals"][i], (
            f"Interval {i} should be the same object across all groups"
        )
