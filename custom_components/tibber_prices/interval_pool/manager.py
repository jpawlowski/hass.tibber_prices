"""Interval pool manager - main coordinator for interval caching."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from custom_components.tibber_prices.api.exceptions import TibberPricesApiClientError
from homeassistant.util import dt as dt_utils

from .cache import TibberPricesIntervalPoolFetchGroupCache
from .fetcher import TibberPricesIntervalPoolFetcher
from .garbage_collector import TibberPricesIntervalPoolGarbageCollector
from .index import TibberPricesIntervalPoolTimestampIndex
from .storage import async_save_pool_state

if TYPE_CHECKING:
    from custom_components.tibber_prices.api.client import TibberPricesApiClient

_LOGGER = logging.getLogger(__name__)
_LOGGER_DETAILS = logging.getLogger(__name__ + ".details")

# Interval lengths in minutes
INTERVAL_HOURLY = 60
INTERVAL_QUARTER_HOURLY = 15

# Debounce delay for auto-save (seconds)
DEBOUNCE_DELAY_SECONDS = 3.0


class TibberPricesIntervalPool:
    """
    High-performance interval cache manager for a single Tibber home.

    Coordinates all interval pool components:
    - TibberPricesIntervalPoolFetchGroupCache: Stores fetch groups and manages protected ranges
    - TibberPricesIntervalPoolTimestampIndex: Provides O(1) timestamp lookups
    - TibberPricesIntervalPoolGarbageCollector: Evicts old fetch groups when cache exceeds limits
    - TibberPricesIntervalPoolFetcher: Detects gaps and fetches missing intervals from API

    Architecture:
    - Each manager handles exactly ONE home (1:1 with config entry)
    - home_id is immutable after initialization
    - All operations are thread-safe via asyncio locks

    Features:
    - Fetch-time based eviction (oldest fetch groups removed first)
    - Protected date range (day-before-yesterday to tomorrow never evicted)
    - Fast O(1) lookups by timestamp
    - Automatic gap detection and API fetching
    - Debounced auto-save to prevent excessive I/O

    Example:
        manager = TibberPricesIntervalPool(home_id="abc123", hass=hass, entry_id=entry.entry_id)
        intervals = await manager.get_intervals(
            api_client=client,
            user_data=data,
            start_time=datetime(...),
            end_time=datetime(...),
        )

    """

    def __init__(
        self,
        *,
        home_id: str,
        api: TibberPricesApiClient,
        hass: Any | None = None,
        entry_id: str | None = None,
    ) -> None:
        """
        Initialize interval pool manager.

        Args:
            home_id: Tibber home ID (required, immutable).
            api: API client for fetching intervals.
            hass: HomeAssistant instance for auto-save (optional).
            entry_id: Config entry ID for auto-save (optional).

        """
        self._home_id = home_id

        # Initialize components with dependency injection
        self._cache = TibberPricesIntervalPoolFetchGroupCache()
        self._index = TibberPricesIntervalPoolTimestampIndex()
        self._gc = TibberPricesIntervalPoolGarbageCollector(self._cache, self._index, home_id)
        self._fetcher = TibberPricesIntervalPoolFetcher(api, self._cache, self._index, home_id)

        # Auto-save support
        self._hass = hass
        self._entry_id = entry_id
        self._background_tasks: set[asyncio.Task] = set()
        self._save_debounce_task: asyncio.Task | None = None
        self._save_lock = asyncio.Lock()

    async def get_intervals(
        self,
        api_client: TibberPricesApiClient,
        user_data: dict[str, Any],
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict[str, Any]]:
        """
        Get price intervals for time range (cached + fetch missing).

        Main entry point for retrieving intervals. Coordinates:
        1. Check cache for existing intervals
        2. Detect missing time ranges
        3. Fetch missing ranges from API
        4. Add new intervals to cache (may trigger GC)
        5. Return complete interval list

        User receives ALL requested intervals even if cache exceeds limits.
        Cache only keeps the most recent intervals (FIFO eviction).

        Args:
            api_client: TibberPricesApiClient instance for API calls.
            user_data: User data dict containing home metadata.
            start_time: Start of range (inclusive, timezone-aware).
            end_time: End of range (exclusive, timezone-aware).

        Returns:
            List of price interval dicts, sorted by startsAt.
            Contains ALL intervals in requested range (cached + fetched).

        Raises:
            TibberPricesApiClientError: If API calls fail or validation errors.

        """
        # Validate inputs
        if not user_data:
            msg = "User data required for timezone-aware price fetching"
            raise TibberPricesApiClientError(msg)

        if start_time >= end_time:
            msg = f"Invalid time range: start_time ({start_time}) must be before end_time ({end_time})"
            raise TibberPricesApiClientError(msg)

        # Convert to ISO strings for cache operations
        start_time_iso = start_time.isoformat()
        end_time_iso = end_time.isoformat()

        _LOGGER_DETAILS.debug(
            "Interval pool request for home %s: range %s to %s",
            self._home_id,
            start_time_iso,
            end_time_iso,
        )

        # Get cached intervals using index
        cached_intervals = self._get_cached_intervals(start_time_iso, end_time_iso)

        # Detect missing ranges
        missing_ranges = self._fetcher.detect_gaps(cached_intervals, start_time_iso, end_time_iso)

        if missing_ranges:
            _LOGGER_DETAILS.debug(
                "Detected %d missing range(s) for home %s - will make %d API call(s)",
                len(missing_ranges),
                self._home_id,
                len(missing_ranges),
            )
        else:
            _LOGGER_DETAILS.debug(
                "All intervals available in cache for home %s - zero API calls needed",
                self._home_id,
            )

        # Fetch missing ranges from API
        if missing_ranges:
            fetch_time_iso = dt_utils.now().isoformat()

            # Fetch with callback for immediate caching
            await self._fetcher.fetch_missing_ranges(
                api_client=api_client,
                user_data=user_data,
                missing_ranges=missing_ranges,
                on_intervals_fetched=lambda intervals, _: self._add_intervals(intervals, fetch_time_iso),
            )

        # After caching all API responses, read from cache again to get final result
        # This ensures we return exactly what user requested, filtering out extra intervals
        final_result = self._get_cached_intervals(start_time_iso, end_time_iso)

        _LOGGER_DETAILS.debug(
            "Interval pool returning %d intervals for home %s "
            "(initially %d cached, %d API calls made, final %d after re-reading cache)",
            len(final_result),
            self._home_id,
            len(cached_intervals),
            len(missing_ranges),
            len(final_result),
        )

        return final_result

    def _get_cached_intervals(
        self,
        start_time_iso: str,
        end_time_iso: str,
    ) -> list[dict[str, Any]]:
        """
        Get cached intervals for time range using timestamp index.

        Uses timestamp_index for O(1) lookups per timestamp.

        Args:
            start_time_iso: ISO timestamp string (inclusive).
            end_time_iso: ISO timestamp string (exclusive).

        Returns:
            List of cached interval dicts in time range (may be empty or incomplete).
            Sorted by startsAt timestamp.

        """
        # Parse query range once
        start_time_dt = datetime.fromisoformat(start_time_iso)
        end_time_dt = datetime.fromisoformat(end_time_iso)

        # Use index to find intervals: iterate through expected timestamps
        result = []
        current_dt = start_time_dt

        # Determine interval step (15 min post-2025-10-01, 60 min pre)
        resolution_change_dt = datetime(2025, 10, 1, tzinfo=start_time_dt.tzinfo)
        interval_minutes = INTERVAL_QUARTER_HOURLY if current_dt >= resolution_change_dt else INTERVAL_HOURLY

        while current_dt < end_time_dt:
            # Check if this timestamp exists in index (O(1) lookup)
            current_dt_key = current_dt.isoformat()[:19]
            location = self._index.get(current_dt_key)

            if location is not None:
                # Get interval from fetch group
                fetch_groups = self._cache.get_fetch_groups()
                fetch_group = fetch_groups[location["fetch_group_index"]]
                interval = fetch_group["intervals"][location["interval_index"]]
                result.append(interval)

            # Move to next expected interval
            current_dt += timedelta(minutes=interval_minutes)

            # Handle resolution change boundary
            if interval_minutes == INTERVAL_HOURLY and current_dt >= resolution_change_dt:
                interval_minutes = INTERVAL_QUARTER_HOURLY

        _LOGGER_DETAILS.debug(
            "Cache lookup for home %s: found %d intervals in range %s to %s",
            self._home_id,
            len(result),
            start_time_iso,
            end_time_iso,
        )

        return result

    def _add_intervals(
        self,
        intervals: list[dict[str, Any]],
        fetch_time_iso: str,
    ) -> None:
        """
        Add intervals as new fetch group to cache with GC.

        Strategy:
        1. Filter out duplicates (intervals already in cache)
        2. Handle "touch" (move cached intervals to new fetch group)
        3. Add new fetch group to cache
        4. Update timestamp index
        5. Run GC if needed
        6. Schedule debounced auto-save

        Args:
            intervals: List of interval dicts from API.
            fetch_time_iso: ISO timestamp string when intervals were fetched.

        """
        if not intervals:
            return

        fetch_time_dt = datetime.fromisoformat(fetch_time_iso)

        # Classify intervals: new vs already cached
        new_intervals = []
        intervals_to_touch = []

        for interval in intervals:
            starts_at_normalized = interval["startsAt"][:19]
            if not self._index.contains(starts_at_normalized):
                new_intervals.append(interval)
            else:
                intervals_to_touch.append((starts_at_normalized, interval))
                _LOGGER_DETAILS.debug(
                    "Interval %s already cached for home %s, will touch (update fetch time)",
                    interval["startsAt"],
                    self._home_id,
                )

        # Handle touched intervals: move to new fetch group
        if intervals_to_touch:
            self._touch_intervals(intervals_to_touch, fetch_time_dt)

        if not new_intervals:
            if intervals_to_touch:
                _LOGGER_DETAILS.debug(
                    "All %d intervals already cached for home %s (touched only)",
                    len(intervals),
                    self._home_id,
                )
            return

        # Sort new intervals by startsAt
        new_intervals.sort(key=lambda x: x["startsAt"])

        # Add new fetch group to cache
        fetch_group_index = self._cache.add_fetch_group(new_intervals, fetch_time_dt)

        # Update timestamp index for all new intervals
        for interval_index, interval in enumerate(new_intervals):
            starts_at_normalized = interval["startsAt"][:19]
            self._index.add(interval, fetch_group_index, interval_index)

        _LOGGER_DETAILS.debug(
            "Added fetch group %d to home %s cache: %d new intervals (fetched at %s)",
            fetch_group_index,
            self._home_id,
            len(new_intervals),
            fetch_time_iso,
        )

        # Run GC to evict old fetch groups if needed
        gc_changed_data = self._gc.run_gc()

        # Schedule debounced auto-save if data changed
        data_changed = len(new_intervals) > 0 or len(intervals_to_touch) > 0 or gc_changed_data
        if data_changed and self._hass is not None and self._entry_id is not None:
            self._schedule_debounced_save()

    def _touch_intervals(
        self,
        intervals_to_touch: list[tuple[str, dict[str, Any]]],
        fetch_time_dt: datetime,
    ) -> None:
        """
        Move cached intervals to new fetch group (update fetch time).

        Creates a new fetch group containing references to existing intervals.
        Updates the index to point to the new fetch group.

        Args:
            intervals_to_touch: List of (normalized_timestamp, interval_dict) tuples.
            fetch_time_dt: Datetime when intervals were fetched.

        """
        fetch_groups = self._cache.get_fetch_groups()

        # Create touch fetch group with existing interval references
        touch_intervals = []
        for starts_at_normalized, _interval in intervals_to_touch:
            # Get existing interval from old fetch group
            location = self._index.get(starts_at_normalized)
            if location is None:
                continue  # Should not happen, but be defensive

            old_group = fetch_groups[location["fetch_group_index"]]
            existing_interval = old_group["intervals"][location["interval_index"]]
            touch_intervals.append(existing_interval)

        # Add touch group to cache
        touch_group_index = self._cache.add_fetch_group(touch_intervals, fetch_time_dt)

        # Update index to point to new fetch group
        for interval_index, (starts_at_normalized, _) in enumerate(intervals_to_touch):
            # Remove old index entry
            self._index.remove(starts_at_normalized)
            # Add new index entry pointing to touch group
            interval = touch_intervals[interval_index]
            self._index.add(interval, touch_group_index, interval_index)

        _LOGGER.debug(
            "Touched %d cached intervals for home %s (moved to fetch group %d, fetched at %s)",
            len(intervals_to_touch),
            self._home_id,
            touch_group_index,
            fetch_time_dt.isoformat(),
        )

    def _schedule_debounced_save(self) -> None:
        """
        Schedule debounced save with configurable delay.

        Cancels existing timer and starts new one if already scheduled.
        This prevents multiple saves during rapid successive changes.

        """
        # Cancel existing debounce timer if running
        if self._save_debounce_task is not None and not self._save_debounce_task.done():
            self._save_debounce_task.cancel()
            _LOGGER.debug("Cancelled pending auto-save (new changes detected, resetting timer)")

        # Schedule new debounced save
        task = asyncio.create_task(
            self._debounced_save_worker(),
            name=f"interval_pool_debounce_{self._entry_id}",
        )
        self._save_debounce_task = task
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def _debounced_save_worker(self) -> None:
        """Debounce worker: waits configured delay, then saves if not cancelled."""
        try:
            await asyncio.sleep(DEBOUNCE_DELAY_SECONDS)
            await self._auto_save_pool_state()
        except asyncio.CancelledError:
            _LOGGER.debug("Auto-save timer cancelled (expected - new changes arrived)")
            raise

    async def _auto_save_pool_state(self) -> None:
        """Auto-save pool state to storage with lock protection."""
        if self._hass is None or self._entry_id is None:
            return

        async with self._save_lock:
            try:
                pool_state = self.to_dict()
                await async_save_pool_state(self._hass, self._entry_id, pool_state)
                _LOGGER.debug("Auto-saved interval pool for entry %s", self._entry_id)
            except Exception:
                _LOGGER.exception("Failed to auto-save interval pool for entry %s", self._entry_id)

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize interval pool state for storage.

        Filters out dead intervals (no longer referenced by index).

        Returns:
            Dictionary containing serialized pool state (only living intervals).

        """
        fetch_groups = self._cache.get_fetch_groups()

        # Serialize fetch groups (only living intervals)
        serialized_fetch_groups = []

        for group_idx, fetch_group in enumerate(fetch_groups):
            living_intervals = []

            for interval_idx, interval in enumerate(fetch_group["intervals"]):
                starts_at_normalized = interval["startsAt"][:19]

                # Check if interval is still referenced in index
                location = self._index.get(starts_at_normalized)
                # Only keep if index points to THIS position in THIS group
                if (
                    location is not None
                    and location["fetch_group_index"] == group_idx
                    and location["interval_index"] == interval_idx
                ):
                    living_intervals.append(interval)

            # Only serialize groups with living intervals
            if living_intervals:
                serialized_fetch_groups.append(
                    {
                        "fetched_at": fetch_group["fetched_at"].isoformat(),
                        "intervals": living_intervals,
                    }
                )

        return {
            "version": 1,
            "home_id": self._home_id,
            "fetch_groups": serialized_fetch_groups,
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        *,
        api: TibberPricesApiClient,
        hass: Any | None = None,
        entry_id: str | None = None,
    ) -> TibberPricesIntervalPool | None:
        """
        Restore interval pool manager from storage.

        Expects single-home format: {"version": 1, "home_id": "...", "fetch_groups": [...]}
        Old multi-home format is treated as corrupted and returns None.

        Args:
            data: Dictionary containing serialized pool state.
            api: API client for fetching intervals.
            hass: HomeAssistant instance for auto-save (optional).
            entry_id: Config entry ID for auto-save (optional).

        Returns:
            Restored TibberPricesIntervalPool instance, or None if format unknown/corrupted.

        """
        # Validate format
        if not data or "home_id" not in data or "fetch_groups" not in data:
            if "homes" in data:
                _LOGGER.info(
                    "Interval pool storage uses old multi-home format (pre-2025-11-25). "
                    "Treating as corrupted. Pool will rebuild from API."
                )
            else:
                _LOGGER.warning("Interval pool storage format unknown or corrupted. Pool will rebuild from API.")
            return None

        home_id = data["home_id"]

        # Create manager with home_id from storage
        manager = cls(home_id=home_id, api=api, hass=hass, entry_id=entry_id)

        # Restore fetch groups to cache
        for serialized_group in data.get("fetch_groups", []):
            fetched_at_dt = datetime.fromisoformat(serialized_group["fetched_at"])
            intervals = serialized_group["intervals"]
            fetch_group_index = manager._cache.add_fetch_group(intervals, fetched_at_dt)

            # Rebuild index for this fetch group
            for interval_index, interval in enumerate(intervals):
                manager._index.add(interval, fetch_group_index, interval_index)

        total_intervals = sum(len(group["intervals"]) for group in manager._cache.get_fetch_groups())
        _LOGGER.debug(
            "Interval pool restored from storage (home %s, %d intervals)",
            home_id,
            total_intervals,
        )

        return manager
