"""
Tests for memory leak prevention in interval pool.

This test module verifies that touch operations don't cause memory leaks by:
1. Reusing existing interval dicts (Python references, not copies)
2. Dead intervals being cleaned up by GC
3. Serialization filtering out dead intervals from storage
4. Empty fetch groups being removed after cleanup

Architecture:
    The interval pool uses a modular architecture:
    - TibberPricesIntervalPool (manager.py): Main coordinator
    - TibberPricesIntervalPoolFetchGroupCache (cache.py): Fetch group storage
    - TibberPricesIntervalPoolTimestampIndex (index.py): O(1) timestamp lookup
    - TibberPricesIntervalPoolGarbageCollector (garbage_collector.py): Eviction/cleanup
    - TibberPricesIntervalPoolFetcher (fetcher.py): Gap detection and API calls

    Tests access internal components directly for fine-grained verification.
"""

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from custom_components.tibber_prices.interval_pool.cache import (
    TibberPricesIntervalPoolFetchGroupCache,
)
from custom_components.tibber_prices.interval_pool.garbage_collector import (
    TibberPricesIntervalPoolGarbageCollector,
)
from custom_components.tibber_prices.interval_pool.index import (
    TibberPricesIntervalPoolTimestampIndex,
)
from custom_components.tibber_prices.interval_pool.manager import (
    TibberPricesIntervalPool,
)


@pytest.fixture
def mock_api() -> MagicMock:
    """Create a mock API client."""
    return MagicMock()


@pytest.fixture
def pool(mock_api: MagicMock) -> TibberPricesIntervalPool:
    """Create an interval pool for testing (single-home architecture)."""
    return TibberPricesIntervalPool(home_id="test_home_id", api=mock_api)


@pytest.fixture
def sample_intervals() -> list[dict]:
    """Create 24 sample intervals (1 day, hourly)."""
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


@pytest.fixture
def cache() -> TibberPricesIntervalPoolFetchGroupCache:
    """Create a fresh cache instance for testing."""
    return TibberPricesIntervalPoolFetchGroupCache()


@pytest.fixture
def index() -> TibberPricesIntervalPoolTimestampIndex:
    """Create a fresh index instance for testing."""
    return TibberPricesIntervalPoolTimestampIndex()


class TestTouchOperations:
    """Test touch operations (re-fetching same intervals)."""

    def test_touch_operation_reuses_existing_intervals(
        self,
        pool: TibberPricesIntervalPool,
    ) -> None:
        """Test that touch operations reuse existing interval dicts (references, not copies)."""
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

        # First fetch: Add intervals
        pool._add_intervals(sample_intervals, fetch_time_1)  # noqa: SLF001

        # Access internal cache
        fetch_groups = pool._cache.get_fetch_groups()  # noqa: SLF001

        # Verify: 1 fetch group with 24 intervals
        assert len(fetch_groups) == 1
        assert len(fetch_groups[0]["intervals"]) == 24

        # Get reference to first interval
        first_interval_original = fetch_groups[0]["intervals"][0]
        original_id = id(first_interval_original)

        # Second fetch: Touch same intervals
        pool._add_intervals(sample_intervals, fetch_time_2)  # noqa: SLF001

        # Re-fetch groups (list may have changed)
        fetch_groups = pool._cache.get_fetch_groups()  # noqa: SLF001

        # Verify: Now we have 2 fetch groups
        assert len(fetch_groups) == 2

        # Get reference to first interval from TOUCH group
        first_interval_touched = fetch_groups[1]["intervals"][0]
        touched_id = id(first_interval_touched)

        # CRITICAL: Should be SAME object (same memory address)
        assert original_id == touched_id, f"Memory addresses differ: {original_id} != {touched_id}"
        assert first_interval_original is first_interval_touched, "Touch should reuse existing dict, not create copy"

    def test_touch_operation_updates_index(
        self,
        pool: TibberPricesIntervalPool,
    ) -> None:
        """Test that touch operations update the index to point to new fetch group."""
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

        # Verify index points to group 0
        first_key = sample_intervals[0]["startsAt"][:19]
        index_entry = pool._index.get(first_key)  # noqa: SLF001
        assert index_entry is not None
        assert index_entry["fetch_group_index"] == 0

        # Second fetch (touch)
        pool._add_intervals(sample_intervals, fetch_time_2)  # noqa: SLF001

        # Verify index now points to group 1 (touch group)
        index_entry = pool._index.get(first_key)  # noqa: SLF001
        assert index_entry is not None
        assert index_entry["fetch_group_index"] == 1, "Index should point to touch group"


class TestGarbageCollection:
    """Test garbage collection and dead interval cleanup."""

    def test_gc_cleanup_removes_dead_intervals(
        self,
        cache: TibberPricesIntervalPoolFetchGroupCache,
        index: TibberPricesIntervalPoolTimestampIndex,
    ) -> None:
        """Test that GC cleanup removes dead intervals from old fetch groups."""
        gc = TibberPricesIntervalPoolGarbageCollector(cache, index, "test_home")

        # Create sample intervals
        sample_intervals = [
            {
                "startsAt": datetime(2025, 11, 25, h, 0, 0, tzinfo=UTC).isoformat(),
                "total": 10.0 + h,
            }
            for h in range(24)
        ]

        # First fetch: Add to cache and index
        fetch_time_1 = datetime(2025, 11, 25, 10, 0, 0, tzinfo=UTC)
        group_idx_1 = cache.add_fetch_group(sample_intervals, fetch_time_1)
        for i, interval in enumerate(sample_intervals):
            index.add(interval, group_idx_1, i)

        # Verify initial state
        assert cache.count_total_intervals() == 24
        assert index.count() == 24

        # Second fetch (touch): Create new fetch group
        fetch_time_2 = datetime(2025, 11, 25, 10, 15, 0, tzinfo=UTC)
        group_idx_2 = cache.add_fetch_group(sample_intervals, fetch_time_2)

        # Update index to point to new group (simulates touch)
        for i, interval in enumerate(sample_intervals):
            index.add(interval, group_idx_2, i)

        # Before GC: 48 intervals in cache (24 dead + 24 living), 24 in index
        assert cache.count_total_intervals() == 48
        assert index.count() == 24

        # Run GC
        gc_changed = gc.run_gc()

        # After GC: Dead intervals cleaned, empty group removed
        assert gc_changed is True
        assert cache.count_total_intervals() == 24, "Should only have living intervals"

    def test_gc_removes_empty_fetch_groups(
        self,
        cache: TibberPricesIntervalPoolFetchGroupCache,
        index: TibberPricesIntervalPoolTimestampIndex,
    ) -> None:
        """Test that GC removes empty fetch groups after dead interval cleanup."""
        gc = TibberPricesIntervalPoolGarbageCollector(cache, index, "test_home")

        # Create sample intervals
        sample_intervals = [
            {
                "startsAt": datetime(2025, 11, 25, h, 0, 0, tzinfo=UTC).isoformat(),
                "total": 10.0 + h,
            }
            for h in range(4)  # Small set
        ]

        # Add two fetch groups
        fetch_time_1 = datetime(2025, 11, 25, 10, 0, 0, tzinfo=UTC)
        fetch_time_2 = datetime(2025, 11, 25, 10, 15, 0, tzinfo=UTC)

        cache.add_fetch_group(sample_intervals, fetch_time_1)
        group_idx_2 = cache.add_fetch_group(sample_intervals, fetch_time_2)

        # Index points only to second group
        for i, interval in enumerate(sample_intervals):
            index.add(interval, group_idx_2, i)

        # Before GC: 2 groups
        assert len(cache.get_fetch_groups()) == 2

        # Run GC
        gc.run_gc()

        # After GC: Only 1 group (empty one removed)
        fetch_groups = cache.get_fetch_groups()
        assert len(fetch_groups) == 1, "Empty fetch group should be removed"
        assert len(fetch_groups[0]["intervals"]) == 4


class TestSerialization:
    """Test serialization excludes dead intervals."""

    def test_serialization_excludes_dead_intervals(
        self,
        pool: TibberPricesIntervalPool,
    ) -> None:
        """Test that to_dict() excludes dead intervals from serialization."""
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

        # Second fetch (touch)
        pool._add_intervals(sample_intervals, fetch_time_2)  # noqa: SLF001

        # Serialize WITHOUT running GC cleanup first
        serialized = pool.to_dict()

        # Verify serialization structure
        assert "fetch_groups" in serialized
        assert "home_id" in serialized
        fetch_groups = serialized["fetch_groups"]

        # CRITICAL: Should only serialize living intervals
        # Old group with dead intervals should NOT be serialized
        total_serialized_intervals = sum(len(g["intervals"]) for g in fetch_groups)
        assert total_serialized_intervals == 24, (
            f"Should only serialize 24 living intervals, got {total_serialized_intervals}"
        )

    def test_repeated_touch_operations_dont_grow_storage(
        self,
        pool: TibberPricesIntervalPool,
    ) -> None:
        """Test that repeated touch operations don't grow storage size unbounded."""
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

        # Serialize (filters dead intervals)
        serialized = pool.to_dict()
        serialized_groups = serialized["fetch_groups"]

        # Storage should only have 24 living intervals total
        total_intervals = sum(len(g["intervals"]) for g in serialized_groups)
        assert total_intervals == 24, f"Should only have 24 living intervals, got {total_intervals}"

        # Verify storage size is bounded
        json_str = json.dumps(serialized)
        json_size = len(json_str)
        # Should still be < 10 KB even after 10 fetches
        assert json_size < 10000, f"Storage grew unbounded: {json_size} bytes (expected < 10000)"


class TestIndexBatchUpdate:
    """Test batch index update functionality."""

    def test_batch_update_efficiency(
        self,
        index: TibberPricesIntervalPoolTimestampIndex,
    ) -> None:
        """Test that batch update correctly updates multiple entries."""
        # Create test intervals
        timestamps = [f"2025-11-25T{h:02d}:00:00" for h in range(24)]

        # Add intervals pointing to group 0
        for i, ts in enumerate(timestamps):
            index.add({"startsAt": ts}, 0, i)

        # Verify initial state
        assert index.count() == 24
        for ts in timestamps:
            entry = index.get(ts)
            assert entry is not None
            assert entry["fetch_group_index"] == 0

        # Batch update to point to group 1
        updates = [(ts, 1, i) for i, ts in enumerate(timestamps)]
        index.update_batch(updates)

        # Verify all entries now point to group 1
        for ts in timestamps:
            entry = index.get(ts)
            assert entry is not None
            assert entry["fetch_group_index"] == 1, f"Entry for {ts} should point to group 1"

    def test_batch_update_with_partial_overlap(
        self,
        index: TibberPricesIntervalPoolTimestampIndex,
    ) -> None:
        """Test batch update with only some existing entries."""
        # Add initial entries (0-11)
        for i in range(12):
            ts = f"2025-11-25T{i:02d}:00:00"
            index.add({"startsAt": ts}, 0, i)

        assert index.count() == 12

        # Batch update: update first 6, add 6 new (12-17)
        updates = [(f"2025-11-25T{i:02d}:00:00", 1, i) for i in range(18)]
        index.update_batch(updates)

        # Should now have 18 entries (12 existing + 6 new)
        assert index.count() == 18

        # All should point to group 1
        for i in range(18):
            ts = f"2025-11-25T{i:02d}:00:00"
            entry = index.get(ts)
            assert entry is not None
            assert entry["fetch_group_index"] == 1


class TestIntervalIdentityPreservation:
    """Test that interval dict identity is preserved across operations."""

    def test_interval_identity_preserved_across_touch(
        self,
        pool: TibberPricesIntervalPool,
    ) -> None:
        """Test that interval dict identity (memory address) is preserved across touch."""
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

        # Get fetch groups
        fetch_groups = pool._cache.get_fetch_groups()  # noqa: SLF001

        # Collect memory addresses of intervals in original group
        original_ids = [id(interval) for interval in fetch_groups[0]["intervals"]]

        # Second fetch (touch)
        pool._add_intervals(sample_intervals, "2025-11-25T10:15:00+01:00")  # noqa: SLF001

        # Re-fetch groups
        fetch_groups = pool._cache.get_fetch_groups()  # noqa: SLF001

        # Collect memory addresses of intervals in touch group
        touched_ids = [id(interval) for interval in fetch_groups[1]["intervals"]]

        # CRITICAL: All memory addresses should be identical (same objects)
        assert original_ids == touched_ids, "Touch should preserve interval identity (memory addresses)"

        # Third fetch (touch again)
        pool._add_intervals(sample_intervals, "2025-11-25T10:30:00+01:00")  # noqa: SLF001

        # Re-fetch groups
        fetch_groups = pool._cache.get_fetch_groups()  # noqa: SLF001

        # New touch group should also reference the SAME original objects
        touched_ids_2 = [id(interval) for interval in fetch_groups[2]["intervals"]]
        assert original_ids == touched_ids_2, "Multiple touches should preserve original identity"
