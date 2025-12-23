"""Fetch group cache for price intervals."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.util import dt as dt_utils

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator.time_service import (
        TibberPricesTimeService,
    )

_LOGGER = logging.getLogger(__name__)
_LOGGER_DETAILS = logging.getLogger(__name__ + ".details")

# Protected date range: day-before-yesterday to tomorrow (4 days total)
PROTECTED_DAYS_BEFORE = 2  # day-before-yesterday + yesterday
PROTECTED_DAYS_AFTER = 1  # tomorrow


class TibberPricesIntervalPoolFetchGroupCache:
    """
    Storage for fetch groups with protected range management.

    A fetch group is a collection of intervals fetched at the same time,
    stored together with their fetch timestamp for GC purposes.

    Structure:
        {
            "fetched_at": datetime,  # When this group was fetched
            "intervals": [dict, ...]  # List of interval dicts
        }

    Protected Range:
        Intervals within day-before-yesterday to tomorrow are protected
        and never evicted from cache. This range shifts daily automatically.

    Example (today = 2025-11-25):
        Protected: 2025-11-23 00:00 to 2025-11-27 00:00
    """

    def __init__(self, *, time_service: TibberPricesTimeService | None = None) -> None:
        """Initialize empty fetch group cache with optional TimeService."""
        self._fetch_groups: list[dict[str, Any]] = []
        self._time_service = time_service

        # Protected range cache (invalidated daily)
        self._protected_range_cache: tuple[str, str] | None = None
        self._protected_range_cache_date: str | None = None

    def add_fetch_group(
        self,
        intervals: list[dict[str, Any]],
        fetched_at: datetime,
    ) -> int:
        """
        Add new fetch group to cache.

        Args:
            intervals: List of interval dicts (sorted by startsAt).
            fetched_at: Timestamp when intervals were fetched.

        Returns:
            Index of the newly added fetch group.

        """
        fetch_group = {
            "fetched_at": fetched_at,
            "intervals": intervals,
        }

        fetch_group_index = len(self._fetch_groups)
        self._fetch_groups.append(fetch_group)

        _LOGGER_DETAILS.debug(
            "Added fetch group %d: %d intervals (fetched at %s)",
            fetch_group_index,
            len(intervals),
            fetched_at.isoformat(),
        )

        return fetch_group_index

    def get_fetch_groups(self) -> list[dict[str, Any]]:
        """Get all fetch groups (read-only access)."""
        return self._fetch_groups

    def set_fetch_groups(self, fetch_groups: list[dict[str, Any]]) -> None:
        """Replace all fetch groups (used during GC)."""
        self._fetch_groups = fetch_groups

    def get_protected_range(self) -> tuple[str, str]:
        """
        Get protected date range as ISO strings.

        Protected range: day-before-yesterday 00:00 to day-after-tomorrow 00:00.
        This range shifts daily automatically.

        Time Machine Support:
            If time_service was provided at init, uses time_service.now() for
            "today" calculation. This protects the correct date range when
            simulating a different date.

        Returns:
            Tuple of (start_iso, end_iso) for protected range.
            Start is inclusive, end is exclusive.

        Example (today = 2025-11-25):
            Returns: ("2025-11-23T00:00:00+01:00", "2025-11-27T00:00:00+01:00")
            Protected days: 2025-11-23, 2025-11-24, 2025-11-25, 2025-11-26

        """
        # Use TimeService if available (Time Machine support), else real time
        now = self._time_service.now() if self._time_service else dt_utils.now()
        today_date_str = now.date().isoformat()

        # Check cache validity (invalidate daily)
        if self._protected_range_cache_date == today_date_str and self._protected_range_cache:
            return self._protected_range_cache

        # Calculate new protected range
        today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Start: day-before-yesterday at 00:00
        start_dt = today_midnight - timedelta(days=PROTECTED_DAYS_BEFORE)

        # End: day after tomorrow at 00:00 (exclusive, so tomorrow is included)
        end_dt = today_midnight + timedelta(days=PROTECTED_DAYS_AFTER + 1)

        # Convert to ISO strings and cache
        start_iso = start_dt.isoformat()
        end_iso = end_dt.isoformat()

        self._protected_range_cache = (start_iso, end_iso)
        self._protected_range_cache_date = today_date_str

        return start_iso, end_iso

    def is_interval_protected(self, interval: dict[str, Any]) -> bool:
        """
        Check if interval is within protected date range.

        Protected intervals are never evicted from cache.

        Args:
            interval: Interval dict with "startsAt" ISO timestamp.

        Returns:
            True if interval is protected (within protected range).

        """
        starts_at_iso = interval["startsAt"]
        start_protected_iso, end_protected_iso = self.get_protected_range()

        # Fast string comparison (ISO timestamps are lexicographically sortable)
        return start_protected_iso <= starts_at_iso < end_protected_iso

    def count_total_intervals(self) -> int:
        """Count total intervals across all fetch groups."""
        return sum(len(group["intervals"]) for group in self._fetch_groups)

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize fetch groups for storage.

        Returns:
            Dict with serializable fetch groups.

        """
        return {
            "fetch_groups": [
                {
                    "fetched_at": group["fetched_at"].isoformat(),
                    "intervals": group["intervals"],
                }
                for group in self._fetch_groups
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TibberPricesIntervalPoolFetchGroupCache:
        """
        Restore fetch groups from storage.

        Args:
            data: Dict with "fetch_groups" list.

        Returns:
            TibberPricesIntervalPoolFetchGroupCache instance with restored data.

        """
        cache = cls()

        fetch_groups_data = data.get("fetch_groups", [])
        cache._fetch_groups = [
            {
                "fetched_at": datetime.fromisoformat(group["fetched_at"]),
                "intervals": group["intervals"],
            }
            for group in fetch_groups_data
        ]

        return cache
