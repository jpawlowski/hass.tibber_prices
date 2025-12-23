"""Interval fetcher - coverage check and API coordination for interval pool."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.util import dt as dt_utils

if TYPE_CHECKING:
    from collections.abc import Callable

    from custom_components.tibber_prices.api import TibberPricesApiClient

    from .cache import TibberPricesIntervalPoolFetchGroupCache
    from .index import TibberPricesIntervalPoolTimestampIndex

_LOGGER = logging.getLogger(__name__)
_LOGGER_DETAILS = logging.getLogger(__name__ + ".details")

# Resolution change date (hourly before, quarter-hourly after)
# Use UTC for constant - timezone adjusted at runtime when comparing
RESOLUTION_CHANGE_DATETIME = datetime(2025, 10, 1, tzinfo=UTC)
RESOLUTION_CHANGE_ISO = "2025-10-01T00:00:00"

# Interval lengths in minutes
INTERVAL_HOURLY = 60
INTERVAL_QUARTER_HOURLY = 15

# Minimum gap sizes in seconds
MIN_GAP_HOURLY = 3600  # 1 hour
MIN_GAP_QUARTER_HOURLY = 900  # 15 minutes

# Tolerance for time comparisons (±1 second for floating point/timezone issues)
TIME_TOLERANCE_SECONDS = 1
TIME_TOLERANCE_MINUTES = 1


class TibberPricesIntervalPoolFetcher:
    """Fetch missing intervals from API based on coverage check."""

    def __init__(
        self,
        api: TibberPricesApiClient,
        cache: TibberPricesIntervalPoolFetchGroupCache,
        index: TibberPricesIntervalPoolTimestampIndex,
        home_id: str,
    ) -> None:
        """
        Initialize fetcher.

        Args:
            api: API client for Tibber GraphQL queries.
            cache: Fetch group cache for storage operations.
            index: Timestamp index for gap detection.
            home_id: Tibber home ID for API calls.

        """
        self._api = api
        self._cache = cache
        self._index = index
        self._home_id = home_id

    def check_coverage(
        self,
        cached_intervals: list[dict[str, Any]],
        start_time_iso: str,
        end_time_iso: str,
    ) -> list[tuple[str, str]]:
        """
        Check cache coverage and find missing time ranges.

        This method minimizes API calls by:
        1. Finding all gaps in cached intervals
        2. Treating each cached interval as a discrete timestamp
        3. Gaps are time ranges between consecutive cached timestamps

        Handles both resolutions:
        - Pre-2025-10-01: Hourly intervals (:00:00 only)
        - Post-2025-10-01: Quarter-hourly intervals (:00:00, :15:00, :30:00, :45:00)
        - DST transitions (23h/25h days)

        The API requires an interval count (first: X parameter).
        For historical data (pre-2025-10-01), Tibber only stored hourly prices.
        The API returns whatever intervals exist for the requested period.

        Args:
            cached_intervals: List of cached intervals (may be empty).
            start_time_iso: ISO timestamp string (inclusive).
            end_time_iso: ISO timestamp string (exclusive).

        Returns:
            List of (start_iso, end_iso) tuples representing missing ranges.
            Each tuple represents a continuous time span that needs fetching.
            Ranges are automatically split at resolution change boundary.

        Example:
            Requested: 2025-11-13T00:00:00 to 2025-11-13T02:00:00
            Cached: [00:00, 00:15, 01:30, 01:45]
            Gaps: [(00:15, 01:30)] - missing intervals between groups

        """
        if not cached_intervals:
            # No cache → fetch entire range
            return [(start_time_iso, end_time_iso)]

        # Filter and sort cached intervals within requested range
        in_range_intervals = [
            interval for interval in cached_intervals if start_time_iso <= interval["startsAt"] < end_time_iso
        ]
        sorted_intervals = sorted(in_range_intervals, key=lambda x: x["startsAt"])

        if not sorted_intervals:
            # All cached intervals are outside requested range
            return [(start_time_iso, end_time_iso)]

        missing_ranges = []

        # Parse start/end times once
        start_time_dt = datetime.fromisoformat(start_time_iso)
        end_time_dt = datetime.fromisoformat(end_time_iso)

        # Get first cached interval datetime for resolution logic
        first_cached_dt = datetime.fromisoformat(sorted_intervals[0]["startsAt"])
        resolution_change_dt = RESOLUTION_CHANGE_DATETIME.replace(tzinfo=first_cached_dt.tzinfo)

        # Check gap before first cached interval
        time_diff_before_first = (first_cached_dt - start_time_dt).total_seconds()
        if time_diff_before_first > TIME_TOLERANCE_SECONDS:
            missing_ranges.append((start_time_iso, sorted_intervals[0]["startsAt"]))
            _LOGGER_DETAILS.debug(
                "Missing range before first cached interval: %s to %s (%.1f seconds)",
                start_time_iso,
                sorted_intervals[0]["startsAt"],
                time_diff_before_first,
            )

        # Check gaps between consecutive cached intervals
        for i in range(len(sorted_intervals) - 1):
            current_interval = sorted_intervals[i]
            next_interval = sorted_intervals[i + 1]

            current_start = current_interval["startsAt"]
            next_start = next_interval["startsAt"]

            # Parse to datetime for accurate time difference
            current_dt = datetime.fromisoformat(current_start)
            next_dt = datetime.fromisoformat(next_start)

            # Calculate time difference in minutes
            time_diff_minutes = (next_dt - current_dt).total_seconds() / 60

            # Determine expected interval length based on date
            expected_interval_minutes = (
                INTERVAL_HOURLY if current_dt < resolution_change_dt else INTERVAL_QUARTER_HOURLY
            )

            # Only create gap if intervals are NOT consecutive
            if time_diff_minutes > expected_interval_minutes + TIME_TOLERANCE_MINUTES:
                # Gap exists - missing intervals between them
                # Missing range starts AFTER current interval ends
                current_interval_end = current_dt + timedelta(minutes=expected_interval_minutes)
                missing_ranges.append((current_interval_end.isoformat(), next_start))
                _LOGGER_DETAILS.debug(
                    "Missing range between cached intervals: %s (ends at %s) to %s (%.1f min, expected %d min)",
                    current_start,
                    current_interval_end.isoformat(),
                    next_start,
                    time_diff_minutes,
                    expected_interval_minutes,
                )

        # Check gap after last cached interval
        # An interval's startsAt time represents the START of that interval.
        # The interval covers [startsAt, startsAt + interval_length).
        # So the last interval ENDS at (startsAt + interval_length), not at startsAt!
        last_cached_dt = datetime.fromisoformat(sorted_intervals[-1]["startsAt"])

        # Calculate when the last interval ENDS
        interval_minutes = INTERVAL_QUARTER_HOURLY if last_cached_dt >= resolution_change_dt else INTERVAL_HOURLY
        last_interval_end_dt = last_cached_dt + timedelta(minutes=interval_minutes)

        # Only create gap if there's uncovered time AFTER the last interval ends
        time_diff_after_last = (end_time_dt - last_interval_end_dt).total_seconds()

        # Need at least one full interval of gap
        min_gap_seconds = MIN_GAP_QUARTER_HOURLY if last_cached_dt >= resolution_change_dt else MIN_GAP_HOURLY
        if time_diff_after_last >= min_gap_seconds:
            # Missing range starts AFTER the last cached interval ends
            missing_ranges.append((last_interval_end_dt.isoformat(), end_time_iso))
            _LOGGER_DETAILS.debug(
                "Missing range after last cached interval: %s (ends at %s) to %s (%.1f seconds, need >= %d)",
                sorted_intervals[-1]["startsAt"],
                last_interval_end_dt.isoformat(),
                end_time_iso,
                time_diff_after_last,
                min_gap_seconds,
            )

        if not missing_ranges:
            _LOGGER.debug(
                "Full coverage - all intervals cached for range %s to %s",
                start_time_iso,
                end_time_iso,
            )
            return missing_ranges

        # Split ranges at resolution change boundary (2025-10-01 00:00:00)
        # This simplifies interval count calculation in API calls:
        # - Pre-2025-10-01: Always hourly (1 interval/hour)
        # - Post-2025-10-01: Always quarter-hourly (4 intervals/hour)
        return self._split_at_resolution_boundary(missing_ranges)

    def _split_at_resolution_boundary(self, ranges: list[tuple[str, str]]) -> list[tuple[str, str]]:
        """
        Split time ranges at resolution change boundary.

        Args:
            ranges: List of (start_iso, end_iso) tuples.

        Returns:
            List of ranges split at 2025-10-01T00:00:00 boundary.

        """
        split_ranges = []

        for start_iso, end_iso in ranges:
            # Check if range crosses the boundary
            if start_iso < RESOLUTION_CHANGE_ISO < end_iso:
                # Split into two ranges: before and after boundary
                split_ranges.append((start_iso, RESOLUTION_CHANGE_ISO))
                split_ranges.append((RESOLUTION_CHANGE_ISO, end_iso))
                _LOGGER_DETAILS.debug(
                    "Split range at resolution boundary: (%s, %s) → (%s, %s) + (%s, %s)",
                    start_iso,
                    end_iso,
                    start_iso,
                    RESOLUTION_CHANGE_ISO,
                    RESOLUTION_CHANGE_ISO,
                    end_iso,
                )
            else:
                # Range doesn't cross boundary - keep as is
                split_ranges.append((start_iso, end_iso))

        return split_ranges

    async def fetch_missing_ranges(
        self,
        api_client: TibberPricesApiClient,
        user_data: dict[str, Any],
        missing_ranges: list[tuple[str, str]],
        *,
        on_intervals_fetched: Callable[[list[dict[str, Any]], str], None] | None = None,
    ) -> list[list[dict[str, Any]]]:
        """
        Fetch missing intervals from API.

        Makes one API call per missing range. Uses routing logic to select
        the optimal endpoint (PRICE_INFO vs PRICE_INFO_RANGE).

        Args:
            api_client: TibberPricesApiClient instance for API calls.
            user_data: User data dict containing home metadata.
            missing_ranges: List of (start_iso, end_iso) tuples to fetch.
            on_intervals_fetched: Optional callback for each fetch result.
                                Receives (intervals, fetch_time_iso).

        Returns:
            List of interval lists (one per missing range).
            Each sublist contains intervals from one API call.

        Raises:
            TibberPricesApiClientError: If API calls fail.

        """
        # Import here to avoid circular dependency
        from custom_components.tibber_prices.interval_pool.routing import (  # noqa: PLC0415
            get_price_intervals_for_range,
        )

        fetch_time_iso = dt_utils.now().isoformat()
        all_fetched_intervals = []

        for idx, (missing_start_iso, missing_end_iso) in enumerate(missing_ranges, start=1):
            _LOGGER_DETAILS.debug(
                "Fetching from Tibber API (%d/%d) for home %s: range %s to %s",
                idx,
                len(missing_ranges),
                self._home_id,
                missing_start_iso,
                missing_end_iso,
            )

            # Parse ISO strings back to datetime for API call
            missing_start_dt = datetime.fromisoformat(missing_start_iso)
            missing_end_dt = datetime.fromisoformat(missing_end_iso)

            # Fetch intervals from API - routing returns ALL intervals (unfiltered)
            fetched_intervals = await get_price_intervals_for_range(
                api_client=api_client,
                home_id=self._home_id,
                user_data=user_data,
                start_time=missing_start_dt,
                end_time=missing_end_dt,
            )

            all_fetched_intervals.append(fetched_intervals)

            _LOGGER_DETAILS.debug(
                "Received %d intervals from Tibber API for home %s",
                len(fetched_intervals),
                self._home_id,
            )

            # Notify callback if provided (for immediate caching)
            if on_intervals_fetched:
                on_intervals_fetched(fetched_intervals, fetch_time_iso)

        return all_fetched_intervals
