"""Timestamp index for O(1) interval lookups."""

from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)
_LOGGER_DETAILS = logging.getLogger(__name__ + ".details")


class TibberPricesIntervalPoolTimestampIndex:
    """
    Fast O(1) timestamp-based interval lookup.

    Maps normalized ISO timestamp strings to fetch group + interval indices.

    Structure:
        {
            "2025-11-25T00:00:00": {
                "fetch_group_index": 0,   # Index in fetch groups list
                "interval_index": 2       # Index within that group's intervals
            },
            ...
        }

    Normalization:
        Timestamps are normalized to 19 characters (YYYY-MM-DDTHH:MM:SS)
        by truncating microseconds and timezone info for fast string comparison.
    """

    def __init__(self) -> None:
        """Initialize empty timestamp index."""
        self._index: dict[str, dict[str, int]] = {}

    def add(
        self,
        interval: dict[str, Any],
        fetch_group_index: int,
        interval_index: int,
    ) -> None:
        """
        Add interval to index.

        Args:
            interval: Interval dict with "startsAt" ISO timestamp.
            fetch_group_index: Index of fetch group containing this interval.
            interval_index: Index within that fetch group's intervals list.

        """
        starts_at_normalized = self._normalize_timestamp(interval["startsAt"])
        self._index[starts_at_normalized] = {
            "fetch_group_index": fetch_group_index,
            "interval_index": interval_index,
        }

    def get(self, timestamp: str) -> dict[str, int] | None:
        """
        Look up interval location by timestamp.

        Args:
            timestamp: ISO timestamp string (will be normalized).

        Returns:
            Dict with fetch_group_index and interval_index, or None if not found.

        """
        starts_at_normalized = self._normalize_timestamp(timestamp)
        return self._index.get(starts_at_normalized)

    def contains(self, timestamp: str) -> bool:
        """
        Check if timestamp exists in index.

        Args:
            timestamp: ISO timestamp string (will be normalized).

        Returns:
            True if timestamp is in index.

        """
        starts_at_normalized = self._normalize_timestamp(timestamp)
        return starts_at_normalized in self._index

    def remove(self, timestamp: str) -> None:
        """
        Remove timestamp from index.

        Args:
            timestamp: ISO timestamp string (will be normalized).

        """
        starts_at_normalized = self._normalize_timestamp(timestamp)
        self._index.pop(starts_at_normalized, None)

    def clear(self) -> None:
        """Clear entire index."""
        self._index.clear()

    def rebuild(self, fetch_groups: list[dict[str, Any]]) -> None:
        """
        Rebuild index from fetch groups.

        Used after GC operations that modify fetch group structure.

        Args:
            fetch_groups: List of fetch group dicts.

        """
        self._index.clear()

        for fetch_group_idx, group in enumerate(fetch_groups):
            for interval_idx, interval in enumerate(group["intervals"]):
                starts_at_normalized = self._normalize_timestamp(interval["startsAt"])
                self._index[starts_at_normalized] = {
                    "fetch_group_index": fetch_group_idx,
                    "interval_index": interval_idx,
                }

        _LOGGER_DETAILS.debug(
            "Rebuilt index: %d timestamps indexed",
            len(self._index),
        )

    def get_raw_index(self) -> dict[str, dict[str, int]]:
        """Get raw index dict (for serialization)."""
        return self._index

    def count(self) -> int:
        """Count total indexed timestamps."""
        return len(self._index)

    @staticmethod
    def _normalize_timestamp(timestamp: str) -> str:
        """
        Normalize ISO timestamp for indexing.

        Truncates to 19 characters (YYYY-MM-DDTHH:MM:SS) to remove
        microseconds and timezone info for consistent string comparison.

        Args:
            timestamp: Full ISO timestamp string.

        Returns:
            Normalized timestamp (19 chars).

        Example:
            "2025-11-25T00:00:00.000+01:00" → "2025-11-25T00:00:00"

        """
        return timestamp[:19]
