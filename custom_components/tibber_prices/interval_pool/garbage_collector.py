"""Garbage collector for interval cache eviction."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .cache import TibberPricesIntervalPoolFetchGroupCache
    from .index import TibberPricesIntervalPoolTimestampIndex

_LOGGER = logging.getLogger(__name__)
_LOGGER_DETAILS = logging.getLogger(__name__ + ".details")

# Maximum number of intervals to cache
# 1 days @ 15min resolution = 10 * 96 = 960 intervals
MAX_CACHE_SIZE = 960


class TibberPricesIntervalPoolGarbageCollector:
    """
    Manages cache eviction and dead interval cleanup.

    Eviction Strategy:
        - Evict oldest fetch groups first (by fetched_at timestamp)
        - Protected intervals (day-before-yesterday to tomorrow) are NEVER evicted
        - Evict complete fetch groups, not individual intervals

    Dead Interval Cleanup:
        When intervals are "touched" (re-fetched), they move to a new fetch group
        but remain in the old group. This creates "dead intervals" that occupy
        memory but are no longer referenced by the index.
    """

    def __init__(
        self,
        cache: TibberPricesIntervalPoolFetchGroupCache,
        index: TibberPricesIntervalPoolTimestampIndex,
        home_id: str,
    ) -> None:
        """
        Initialize garbage collector.

        Args:
            home_id: Home ID for logging purposes.
            cache: Fetch group cache to manage.
            index: Timestamp index for living interval detection.

        """
        self._home_id = home_id
        self._cache = cache
        self._index = index

    def run_gc(self) -> bool:
        """
        Run garbage collection if needed.

        Process:
            1. Clean up dead intervals from all fetch groups
            2. Count total intervals
            3. If > MAX_CACHE_SIZE, evict oldest fetch groups
            4. Rebuild index after eviction

        Returns:
            True if any cleanup or eviction happened, False otherwise.

        """
        fetch_groups = self._cache.get_fetch_groups()

        # Phase 1: Clean up dead intervals
        dead_count = self._cleanup_dead_intervals(fetch_groups)

        if dead_count > 0:
            _LOGGER_DETAILS.debug(
                "GC cleaned %d dead intervals (home %s)",
                dead_count,
                self._home_id,
            )

        # Phase 1.5: Remove empty fetch groups (after dead interval cleanup)
        empty_removed = self._remove_empty_groups(fetch_groups)
        if empty_removed > 0:
            _LOGGER_DETAILS.debug(
                "GC removed %d empty fetch groups (home %s)",
                empty_removed,
                self._home_id,
            )

        # Phase 2: Count total intervals after cleanup
        total_intervals = self._cache.count_total_intervals()

        if total_intervals <= MAX_CACHE_SIZE:
            _LOGGER_DETAILS.debug(
                "GC cleanup only for home %s: %d intervals <= %d limit (no eviction needed)",
                self._home_id,
                total_intervals,
                MAX_CACHE_SIZE,
            )
            return dead_count > 0

        # Phase 3: Evict old fetch groups
        evicted_indices = self._evict_old_groups(fetch_groups, total_intervals)

        if not evicted_indices:
            # All intervals are protected, cannot evict
            return dead_count > 0 or empty_removed > 0

        # Phase 4: Rebuild cache and index
        new_fetch_groups = [group for idx, group in enumerate(fetch_groups) if idx not in evicted_indices]
        self._cache.set_fetch_groups(new_fetch_groups)
        self._index.rebuild(new_fetch_groups)

        _LOGGER_DETAILS.debug(
            "GC evicted %d fetch groups (home %s): %d intervals remaining",
            len(evicted_indices),
            self._home_id,
            self._cache.count_total_intervals(),
        )

        return True

    def _remove_empty_groups(self, fetch_groups: list[dict[str, Any]]) -> int:
        """
        Remove fetch groups with no intervals.

        After dead interval cleanup, some groups may be completely empty.
        These should be removed to prevent memory accumulation.

        Note: This modifies the cache's internal list in-place and rebuilds
        the index to maintain consistency.

        Args:
            fetch_groups: List of fetch groups (will be modified).

        Returns:
            Number of empty groups removed.

        """
        # Find non-empty groups
        non_empty_groups = [group for group in fetch_groups if group["intervals"]]
        removed_count = len(fetch_groups) - len(non_empty_groups)

        if removed_count > 0:
            # Update cache with filtered list
            self._cache.set_fetch_groups(non_empty_groups)
            # Rebuild index since group indices changed
            self._index.rebuild(non_empty_groups)

        return removed_count

    def _cleanup_dead_intervals(self, fetch_groups: list[dict[str, Any]]) -> int:
        """
        Remove dead intervals from all fetch groups.

        Dead intervals are no longer referenced by the index (they were touched
        and moved to a newer fetch group).

        Args:
            fetch_groups: List of fetch groups to clean.

        Returns:
            Total number of dead intervals removed.

        """
        total_dead = 0

        for group_idx, group in enumerate(fetch_groups):
            old_intervals = group["intervals"]
            if not old_intervals:
                continue

            # Find living intervals (still in index at correct position)
            living_intervals = []

            for interval_idx, interval in enumerate(old_intervals):
                starts_at_normalized = interval["startsAt"][:19]
                index_entry = self._index.get(starts_at_normalized)

                if index_entry is not None:
                    # Check if index points to THIS position
                    if index_entry["fetch_group_index"] == group_idx and index_entry["interval_index"] == interval_idx:
                        living_intervals.append(interval)
                    else:
                        # Dead: index points elsewhere
                        total_dead += 1
                else:
                    # Dead: not in index
                    total_dead += 1

            # Replace with cleaned list if any dead intervals found
            if len(living_intervals) < len(old_intervals):
                group["intervals"] = living_intervals
                dead_count = len(old_intervals) - len(living_intervals)
                _LOGGER_DETAILS.debug(
                    "GC cleaned %d dead intervals from fetch group %d (home %s)",
                    dead_count,
                    group_idx,
                    self._home_id,
                )

        return total_dead

    def _evict_old_groups(
        self,
        fetch_groups: list[dict[str, Any]],
        total_intervals: int,
    ) -> set[int]:
        """
        Determine which fetch groups to evict to stay under MAX_CACHE_SIZE.

        Only evicts groups without protected intervals.
        Groups evicted oldest-first (by fetched_at).

        Args:
            fetch_groups: List of fetch groups.
            total_intervals: Total interval count.

        Returns:
            Set of fetch group indices to evict.

        """
        start_protected_iso, end_protected_iso = self._cache.get_protected_range()

        _LOGGER_DETAILS.debug(
            "Protected range: %s to %s",
            start_protected_iso[:10],
            end_protected_iso[:10],
        )

        # Classify: protected vs evictable
        evictable_groups = []

        for idx, group in enumerate(fetch_groups):
            has_protected = any(self._cache.is_interval_protected(interval) for interval in group["intervals"])

            if not has_protected:
                evictable_groups.append((idx, group))

        # Sort by fetched_at (oldest first)
        evictable_groups.sort(key=lambda x: x[1]["fetched_at"])

        _LOGGER_DETAILS.debug(
            "GC: %d protected groups, %d evictable groups",
            len(fetch_groups) - len(evictable_groups),
            len(evictable_groups),
        )

        # Evict until under limit
        evicted_indices = set()
        remaining = total_intervals

        for idx, group in evictable_groups:
            if remaining <= MAX_CACHE_SIZE:
                break

            group_count = len(group["intervals"])
            evicted_indices.add(idx)
            remaining -= group_count

            _LOGGER_DETAILS.debug(
                "GC evicting group %d (fetched %s): %d intervals, %d remaining",
                idx,
                group["fetched_at"].isoformat(),
                group_count,
                remaining,
            )

        if not evicted_indices:
            _LOGGER.warning(
                "GC cannot evict any groups (home %s): all %d intervals are protected",
                self._home_id,
                total_intervals,
            )

        return evicted_indices
