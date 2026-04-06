"""Interval pool manager - main coordinator for interval caching."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from custom_components.tibber_prices.api.exceptions import TibberPricesApiClientError
from homeassistant.util import dt as dt_utils

from .cache import TibberPricesIntervalPoolFetchGroupCache
from .fetcher import TibberPricesIntervalPoolFetcher
from .garbage_collector import MAX_CACHE_SIZE, TibberPricesIntervalPoolGarbageCollector
from .index import TibberPricesIntervalPoolTimestampIndex
from .storage import async_save_pool_state

if TYPE_CHECKING:
    from custom_components.tibber_prices.api.client import TibberPricesApiClient
    from custom_components.tibber_prices.coordinator.time_service import (
        TibberPricesTimeService,
    )

_LOGGER = logging.getLogger(__name__)
_LOGGER_DETAILS = logging.getLogger(__name__ + ".details")

# Interval lengths in minutes
INTERVAL_HOURLY = 60
INTERVAL_QUARTER_HOURLY = 15

# Debounce delay for auto-save (seconds)
DEBOUNCE_DELAY_SECONDS = 3.0

# Maximum UTC difference (seconds) between two intervals that share the same naive
# local timestamp to still be considered a true duplicate (not a DST fall-back pair).
# True duplicates differ by 0 s; DST fall-back pairs differ by ~3600 s.
_DST_COLLISION_MAX_SAME_UTC_S = 60


def _normalize_starts_at(starts_at: datetime | str) -> str:
    """Normalize startsAt to consistent format (YYYY-MM-DDTHH:MM:SS)."""
    if isinstance(starts_at, datetime):
        return starts_at.strftime("%Y-%m-%dT%H:%M:%S")
    return starts_at[:19]


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
        time_service: TibberPricesTimeService | None = None,
    ) -> None:
        """
        Initialize interval pool manager.

        Args:
            home_id: Tibber home ID (required, immutable).
            api: API client for fetching intervals.
            hass: HomeAssistant instance for auto-save (optional).
            entry_id: Config entry ID for auto-save (optional).
            time_service: TimeService for time-travel support (optional).
                         If None, uses real time (dt_utils.now()).

        """
        self._home_id = home_id
        self._time_service = time_service

        # Initialize components with dependency injection
        self._cache = TibberPricesIntervalPoolFetchGroupCache(time_service=time_service)
        self._index = TibberPricesIntervalPoolTimestampIndex()
        self._gc = TibberPricesIntervalPoolGarbageCollector(self._cache, self._index, home_id)
        self._fetcher = TibberPricesIntervalPoolFetcher(api, self._cache, self._index, home_id)

        # Auto-save support
        self._hass = hass
        self._entry_id = entry_id
        self._background_tasks: set[asyncio.Task] = set()
        self._save_debounce_task: asyncio.Task | None = None
        self._save_lock = asyncio.Lock()

        # DST fall-back extra intervals.
        # On DST fall-back nights (e.g. last Sunday October in EU), wall-clock
        # 02:00-02:45 occurs twice: once in CEST (+02:00) and once in CET (+01:00).
        # The main index uses naive 19-char keys, so the second batch collides.
        # To avoid discarding the CET hour's price data, we store the colliding
        # entries here keyed by their normalized timestamp.
        # Structure: {"2026-10-25T02:00:00": [{"startsAt": "...+01:00", ...}], ...}
        self._dst_extras: dict[str, list[dict[str, Any]]] = {}

    async def get_intervals(
        self,
        api_client: TibberPricesApiClient,
        user_data: dict[str, Any],
        start_time: datetime,
        end_time: datetime,
    ) -> tuple[list[dict[str, Any]], bool]:
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
            Tuple of (intervals, api_called):
            - intervals: List of price interval dicts, sorted by startsAt.
                        Contains ALL intervals in requested range (cached + fetched).
            - api_called: True if API was called to fetch missing data, False if all from cache.

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

        # Check coverage - find ranges not in cache
        missing_ranges = self._fetcher.check_coverage(cached_intervals, start_time_iso, end_time_iso)

        if missing_ranges:
            _LOGGER_DETAILS.debug(
                "Coverage check for home %s: %d range(s) missing - will fetch from API",
                self._home_id,
                len(missing_ranges),
            )
        else:
            _LOGGER_DETAILS.debug(
                "Coverage check for home %s: full coverage in cache - no API calls needed",
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

        # Track if API was called (True if any missing ranges were fetched)
        api_called = len(missing_ranges) > 0

        _LOGGER_DETAILS.debug(
            "Pool returning %d intervals for home %s (from cache: %d, fetched from API: %d ranges, api_called=%s)",
            len(final_result),
            self._home_id,
            len(cached_intervals),
            len(missing_ranges),
            api_called,
        )

        return final_result, api_called

    async def get_sensor_data(
        self,
        api_client: TibberPricesApiClient,
        user_data: dict[str, Any],
        home_timezone: str | None = None,
        *,
        include_tomorrow: bool = True,
    ) -> tuple[list[dict[str, Any]], bool]:
        """
        Get price intervals for sensor data (day-before-yesterday to end-of-tomorrow).

        Convenience method for coordinator/sensors that need the standard 4-day window:
        - Day before yesterday (for trailing 24h averages at midnight)
        - Yesterday (for trailing 24h averages)
        - Today (current prices)
        - Tomorrow (if available in cache)

        IMPORTANT - Two distinct behaviors:
        1. API FETCH: Controlled by include_tomorrow flag
           - include_tomorrow=False → Only fetch up to end of today (prevents API spam before 13:00)
           - include_tomorrow=True → Fetch including tomorrow data
        2. RETURN DATA: Always returns full protected range (including tomorrow if cached)
           - This ensures cached tomorrow data is used even if include_tomorrow=False

        The separation prevents the following bug:
        - If include_tomorrow affected both fetch AND return, cached tomorrow data
          would be lost when include_tomorrow=False, causing infinite refresh loops.

        Args:
            api_client: TibberPricesApiClient instance for API calls.
            user_data: User data dict containing home metadata.
            home_timezone: Optional timezone string (e.g., "Europe/Berlin").
            include_tomorrow: If True, fetch tomorrow's data from API. If False,
                             only fetch up to end of today. Default True.
                             DOES NOT affect returned data - always returns full range.

        Returns:
            Tuple of (intervals, api_called):
            - intervals: List of price interval dicts for the 4-day window (including any cached
                        tomorrow data), sorted by startsAt.
            - api_called: True if API was called to fetch missing data, False if all from cache.

        """
        # Determine timezone
        tz_str = home_timezone
        if not tz_str:
            tz_str = self._extract_timezone_from_user_data(user_data)

        # Calculate range in home's timezone
        tz = ZoneInfo(tz_str) if tz_str else None
        now = self._time_service.now() if self._time_service else dt_utils.now()
        now_local = now.astimezone(tz) if tz else now

        # Day before yesterday 00:00 (start) - same for both fetch and return
        day_before_yesterday = (now_local - timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)

        # End of tomorrow (full protected range) - used for RETURN data
        end_of_tomorrow = (now_local + timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)

        # API fetch range depends on include_tomorrow flag
        if include_tomorrow:
            fetch_end_time = end_of_tomorrow
            fetch_desc = "end-of-tomorrow"
        else:
            # Only fetch up to end of today (prevents API spam before 13:00)
            fetch_end_time = (now_local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            fetch_desc = "end-of-today"

        _LOGGER.debug(
            "Sensor data request for home %s: fetch %s to %s (%s), return up to %s",
            self._home_id,
            day_before_yesterday.isoformat(),
            fetch_end_time.isoformat(),
            fetch_desc,
            end_of_tomorrow.isoformat(),
        )

        # Fetch data (may be partial if include_tomorrow=False)
        _intervals, api_called = await self.get_intervals(
            api_client=api_client,
            user_data=user_data,
            start_time=day_before_yesterday,
            end_time=fetch_end_time,
        )

        # Return FULL protected range (including any cached tomorrow data)
        # This ensures cached tomorrow data is available even when include_tomorrow=False
        final_intervals = self._get_cached_intervals(
            day_before_yesterday.isoformat(),
            end_of_tomorrow.isoformat(),
        )

        return final_intervals, api_called

    def get_pool_stats(self) -> dict[str, Any]:
        """
        Get statistics about the interval pool.

        Returns comprehensive statistics for diagnostic sensors, separated into:
        - Sensor intervals (protected range: day-before-yesterday to tomorrow)
        - Cache statistics (entire pool including service-requested data)

        Protected Range:
            The protected range covers 4 days at 15-min resolution = 384 intervals.
            These intervals are never evicted by garbage collection.

        Cache Fill Level:
            Shows how full the cache is relative to MAX_CACHE_SIZE (960).
            100% is not bad - just means we're using the available space.
            GC will evict oldest non-protected intervals when limit is reached.

        Returns:
            Dict with sensor intervals, cache stats, and timestamps.

        """
        fetch_groups = self._cache.get_fetch_groups()

        # === Sensor Intervals (Protected Range) ===
        sensor_stats = self._get_sensor_interval_stats()

        # === Cache Statistics (Entire Pool) ===
        cache_total = self._index.count()
        cache_limit = MAX_CACHE_SIZE
        cache_fill_percent = round((cache_total / cache_limit) * 100, 1) if cache_limit > 0 else 0
        cache_extra = max(0, cache_total - sensor_stats["count"])  # Intervals outside protected range

        # === Timestamps ===
        # Last sensor fetch (for protected range data)
        last_sensor_fetch: str | None = None
        oldest_interval: str | None = None
        newest_interval: str | None = None

        if fetch_groups:
            # Find newest fetch group (most recent API call)
            newest_group = max(fetch_groups, key=lambda g: g["fetched_at"])
            last_sensor_fetch = newest_group["fetched_at"].isoformat()

            # Find oldest and newest intervals across all fetch groups
            all_timestamps = list(self._index.get_raw_index().keys())
            if all_timestamps:
                oldest_interval = min(all_timestamps)
                newest_interval = max(all_timestamps)

        return {
            # Sensor intervals (protected range)
            "sensor_intervals_count": sensor_stats["count"],
            "sensor_intervals_expected": sensor_stats["expected"],
            "sensor_intervals_has_gaps": sensor_stats["has_gaps"],
            # Cache statistics
            "cache_intervals_total": cache_total,
            "cache_intervals_limit": cache_limit,
            "cache_fill_percent": cache_fill_percent,
            "cache_intervals_extra": cache_extra,
            # Timestamps
            "last_sensor_fetch": last_sensor_fetch,
            "cache_oldest_interval": oldest_interval,
            "cache_newest_interval": newest_interval,
            # Fetch groups (API calls)
            "fetch_groups_count": len(fetch_groups),
        }

    def _get_sensor_interval_stats(self) -> dict[str, Any]:
        """
        Get statistics for sensor intervals (protected range).

        Protected range: day-before-yesterday 00:00 to day-after-tomorrow 00:00.
        Expected: ~480 intervals (5 days x 96 quarter-hourly slots).

        Returns:
            Dict with count, expected, and has_gaps.

        Note on DST:
            expected_count is derived from UTC-duration arithmetic and will be
            off by ±4 on spring-forward/fall-back days.  has_gaps uses a
            separate UTC-aware consecutive-interval check that is immune to this.

        """
        start_iso, end_iso = self._cache.get_protected_range()
        start_dt = datetime.fromisoformat(start_iso)
        end_dt = datetime.fromisoformat(end_iso)

        # Nominal expected count for diagnostics. On spring-forward days this
        # over-estimates by 4 (the 4 non-existent 02:xx local slots); on
        # fall-back days it under-estimates by 4. The has_gaps flag is
        # determined independently via UTC-aware logic below.
        expected_count = int((end_dt - start_dt).total_seconds() / (15 * 60))

        # Count actual intervals by naive-key iteration (matches index format)
        actual_count = 0
        current_dt = start_dt

        while current_dt < end_dt:
            current_key = current_dt.isoformat()[:19]
            if self._index.contains(current_key):
                actual_count += 1
            current_dt += timedelta(minutes=15)

        return {
            "count": actual_count,
            "expected": expected_count,
            "has_gaps": self._has_real_gaps_in_range(start_iso, end_iso),
        }

    def _has_real_gaps_in_range(self, start_iso: str, end_iso: str) -> bool:
        """
        Check for coverage gaps using UTC-aware consecutive-interval comparison.

        The naive key-counting approach in _get_sensor_interval_stats() visits
        'phantom' timestamps that don't exist on DST spring-forward days
        (e.g. 02:00-02:45 when clocks jump 02:00→03:00).  Those slots are
        permanently absent from the index, producing a false positive every
        spring-forward day until the next HA restart.

        This method avoids the problem by comparing consecutive cached intervals
        via their UTC times: the jump from 01:45+01:00 (CET) to 03:00+02:00
        (CEST) is exactly 15 minutes in UTC, so no gap is reported.

        Boundary comparisons (first/last interval vs start/end of protected
        range) use the naive 19-char local time representation to stay
        consistent with the fixed-offset arithmetic used by get_protected_range().

        Args:
            start_iso: ISO start of the protected range (inclusive).
            end_iso: ISO end of the protected range (exclusive).

        Returns:
            True if a real gap exists, False if the range is fully covered.

        """
        from datetime import UTC  # noqa: PLC0415 - UTC constant needed here only

        cached_intervals = self._get_cached_intervals(start_iso, end_iso)

        if not cached_intervals:
            return True

        resolution_change_utc = datetime(2025, 10, 1, tzinfo=UTC)
        # 1-minute tolerance for scheduling jitter / minor timestamp variations
        tolerance_s = 60

        # Sort by actual UTC time so ordering is correct across DST boundaries
        sorted_intervals = sorted(
            cached_intervals,
            key=lambda x: datetime.fromisoformat(x["startsAt"]),
        )

        # --- Boundary check: gap before first interval ---
        # Compare naive local times so we don't confuse a legitimate +01:00/+02:00
        # offset mismatch (caused by fixed-offset arithmetic in get_protected_range)
        # with a real missing hour.
        first_naive_str = sorted_intervals[0]["startsAt"][:19]
        start_naive_str = start_iso[:19]
        # datetime.fromisoformat on a naive string → naive datetime (intentional)
        first_naive_dt = datetime.fromisoformat(first_naive_str)
        start_naive_dt = datetime.fromisoformat(start_naive_str)
        if (first_naive_dt - start_naive_dt).total_seconds() > 15 * 60 + tolerance_s:
            return True

        # --- Interior check: gap between consecutive intervals (UTC-based) ---
        for i in range(len(sorted_intervals) - 1):
            current_dt = datetime.fromisoformat(sorted_intervals[i]["startsAt"])
            next_dt = datetime.fromisoformat(sorted_intervals[i + 1]["startsAt"])
            diff_s = (next_dt - current_dt).total_seconds()
            expected_s = 900 if current_dt.astimezone(UTC) >= resolution_change_utc else 3600
            if diff_s > expected_s + tolerance_s:
                return True  # Real gap between consecutive intervals

        # --- Boundary check: gap after last interval ---
        # Same naive-time logic as the start boundary.
        last_naive_str = sorted_intervals[-1]["startsAt"][:19]
        end_naive_str = end_iso[:19]
        last_naive_dt = datetime.fromisoformat(last_naive_str)
        end_naive_dt = datetime.fromisoformat(end_naive_str)
        last_dt_utc = datetime.fromisoformat(sorted_intervals[-1]["startsAt"])
        expected_last_s = 900 if last_dt_utc.astimezone(UTC) >= resolution_change_utc else 3600
        last_end_naive_dt = last_naive_dt + timedelta(seconds=expected_last_s)
        return (end_naive_dt - last_end_naive_dt).total_seconds() >= expected_last_s

    def _has_gaps_in_protected_range(self) -> bool:
        """
        Check if there are gaps in the protected date range.

        Delegates to _get_sensor_interval_stats() for consistency.

        Returns:
            True if any gaps exist, False if protected range is complete.

        """
        return self._get_sensor_interval_stats()["has_gaps"]

    def _extract_timezone_from_user_data(self, user_data: dict[str, Any]) -> str | None:
        """Extract timezone for this home from user_data."""
        if not user_data:
            return None

        viewer = user_data.get("viewer", {})
        homes = viewer.get("homes", [])

        for home in homes:
            if home.get("id") == self._home_id:
                return home.get("timeZone")

        return None

    def _get_cached_intervals(
        self,
        start_time_iso: str,
        end_time_iso: str,
    ) -> list[dict[str, Any]]:
        """
        Get cached intervals for time range using timestamp index.

        Uses timestamp_index for O(1) lookups per timestamp.

        IMPORTANT: Returns shallow copies of interval dicts to prevent external
        mutations (e.g., by parse_all_timestamps()) from affecting cached data.
        The Pool cache must remain immutable to ensure consistent behavior.

        Args:
            start_time_iso: ISO timestamp string (inclusive).
            end_time_iso: ISO timestamp string (exclusive).

        Returns:
            List of cached interval dicts in time range (may be empty or incomplete).
            Sorted by startsAt timestamp. Each dict is a shallow copy.

        """
        # Parse query range once
        start_time_dt = datetime.fromisoformat(start_time_iso)
        end_time_dt = datetime.fromisoformat(end_time_iso)

        # CRITICAL: Use NAIVE local timestamps for iteration.
        #
        # Index keys are naive local timestamps (timezone stripped via [:19]).
        # When start and end span a DST transition, they have different UTC offsets
        # (e.g., start=+01:00 CET, end=+02:00 CEST). Using fixed-offset datetimes
        # from fromisoformat() causes the loop to compare UTC values for the end
        # boundary, ending 1 hour early on spring-forward days (or 1 hour late on
        # fall-back days).
        #
        # By iterating in naive local time, we match the index key format exactly
        # and the end boundary comparison works correctly regardless of DST.
        current_naive = start_time_dt.replace(tzinfo=None)
        end_naive = end_time_dt.replace(tzinfo=None)

        # Use index to find intervals: iterate through expected timestamps
        result = []

        # Determine interval step (15 min post-2025-10-01, 60 min pre)
        resolution_change_naive = datetime(2025, 10, 1)  # noqa: DTZ001
        interval_minutes = INTERVAL_QUARTER_HOURLY if current_naive >= resolution_change_naive else INTERVAL_HOURLY

        while current_naive < end_naive:
            # Check if this timestamp exists in index (O(1) lookup)
            current_dt_key = current_naive.isoformat()[:19]
            location = self._index.get(current_dt_key)

            if location is not None:
                # Get interval from fetch group
                fetch_groups = self._cache.get_fetch_groups()
                fetch_group = fetch_groups[location["fetch_group_index"]]
                interval = fetch_group["intervals"][location["interval_index"]]
                # CRITICAL: Return shallow copy to prevent external mutations
                # (e.g., parse_all_timestamps() converts startsAt to datetime in-place)
                result.append(dict(interval))

                # Also yield DST fall-back extras for this naive timestamp.
                # On fall-back day, 02:xx occurs in both CEST and CET; the CET
                # version was stored in _dst_extras instead of being discarded.
                if current_dt_key in self._dst_extras:
                    result.extend(dict(extra) for extra in self._dst_extras[current_dt_key])

            # Move to next expected interval
            current_naive += timedelta(minutes=interval_minutes)

            # Handle resolution change boundary
            if interval_minutes == INTERVAL_HOURLY and current_naive >= resolution_change_naive:
                interval_minutes = INTERVAL_QUARTER_HOURLY

        _LOGGER_DETAILS.debug(
            "Retrieved %d intervals from cache for home %s (range %s to %s)",
            len(result),
            self._home_id,
            start_time_iso,
            end_time_iso,
        )

        return result

    def _handle_index_collision(
        self,
        starts_at_normalized: str,
        interval: dict[str, Any],
    ) -> bool:
        """
        Handle a key collision when adding an interval.

        A collision occurs when a new interval shares the same naive local key as one
        already in the index.  Two cases:

        * **True duplicate**: the UTC times are ≤ ``_DST_COLLISION_MAX_SAME_UTC_S``
          apart → normal re-fetch; caller should *touch* the existing entry.
        * **DST fall-back collision**: the UTC times differ by ~3600 s → the same
          local clock time occurs twice (CEST then CET).  Store the new interval in
          ``_dst_extras`` so both are preserved.

        Returns:
            ``True`` if this was a DST fall-back collision (extra stored internally).
            ``False`` if this was a true duplicate (caller should touch existing entry).

        """
        location = self._index.get(starts_at_normalized)
        if location is None:
            return False
        fetch_groups = self._cache.get_fetch_groups()
        existing_interval = fetch_groups[location["fetch_group_index"]]["intervals"][location["interval_index"]]
        existing_dt = datetime.fromisoformat(existing_interval["startsAt"])
        new_dt = datetime.fromisoformat(interval["startsAt"])
        if abs((new_dt - existing_dt).total_seconds()) > _DST_COLLISION_MAX_SAME_UTC_S:
            # Different UTC time → DST fall-back collision: preserve both
            self._dst_extras.setdefault(starts_at_normalized, []).append(dict(interval))
            _LOGGER.debug(
                "DST fall-back: stored extra interval %s alongside %s for home %s",
                interval["startsAt"],
                existing_interval["startsAt"],
                self._home_id,
            )
            return True
        return False

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
            starts_at_normalized = _normalize_starts_at(interval["startsAt"])
            if not self._index.contains(starts_at_normalized):
                new_intervals.append(interval)
            elif self._handle_index_collision(starts_at_normalized, interval):
                # DST fall-back: extra stored inside _handle_index_collision, skip touch
                pass
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
            starts_at_normalized = _normalize_starts_at(interval["startsAt"])
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

        # After GC, prune DST extras whose main index entry was evicted.
        # (Extras are only meaningful while their CEST counterpart is still indexed.)
        if gc_changed_data and self._dst_extras:
            self._dst_extras = {key: extras for key, extras in self._dst_extras.items() if self._index.contains(key)}

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

        # Update index to point to new fetch group using batch operation
        # This is more efficient than individual remove+add calls
        index_updates = [
            (starts_at_normalized, touch_group_index, interval_index)
            for interval_index, (starts_at_normalized, _) in enumerate(intervals_to_touch)
        ]
        self._index.update_batch(index_updates)

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

    async def async_shutdown(self) -> None:
        """
        Clean shutdown - cancel pending background tasks.

        Should be called when the config entry is unloaded to prevent
        orphaned tasks and ensure clean resource cleanup.

        """
        _LOGGER.debug("Shutting down interval pool for home %s", self._home_id)

        # Cancel debounce task if running
        if self._save_debounce_task is not None and not self._save_debounce_task.done():
            self._save_debounce_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._save_debounce_task
            _LOGGER.debug("Cancelled pending auto-save task")

        # Cancel any other background tasks
        if self._background_tasks:
            for task in list(self._background_tasks):
                if not task.done():
                    task.cancel()
            # Wait for all tasks to complete cancellation
            if self._background_tasks:
                await asyncio.gather(*self._background_tasks, return_exceptions=True)
            _LOGGER.debug("Cancelled %d background tasks", len(self._background_tasks))
            self._background_tasks.clear()

        _LOGGER.debug("Interval pool shutdown complete for home %s", self._home_id)

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
                starts_at_normalized = _normalize_starts_at(interval["startsAt"])

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
            # DST fall-back extras: CET duplicates of fall-back 02:xx intervals.
            # Only non-empty on/after fall-back nights; typically {} all year.
            "dst_extras": self._dst_extras,
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        *,
        api: TibberPricesApiClient,
        hass: Any | None = None,
        entry_id: str | None = None,
        time_service: TibberPricesTimeService | None = None,
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
            time_service: TimeService for time-travel support (optional).

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
        manager = cls(home_id=home_id, api=api, hass=hass, entry_id=entry_id, time_service=time_service)

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

        # Restore DST fall-back extras (CET duplicates of fall-back 02:xx intervals).
        # Typically empty ({}) except in the days following a fall-back night.
        manager._dst_extras = data.get("dst_extras", {})

        return manager
