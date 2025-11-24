"""Pure utility functions for coordinator module."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from custom_components.tibber_prices.const import DOMAIN
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from datetime import date

    from homeassistant.core import HomeAssistant

    from .time_service import TibberPricesTimeService

_LOGGER = logging.getLogger(__name__)


def get_configured_home_ids(hass: HomeAssistant) -> set[str]:
    """Get all home_ids that have active config entries (main + subentries)."""
    home_ids = set()

    # Collect home_ids from all config entries for this domain
    for entry in hass.config_entries.async_entries(DOMAIN):
        if home_id := entry.data.get("home_id"):
            home_ids.add(home_id)

    return home_ids


def get_intervals_for_day_offsets(
    coordinator_data: dict[str, Any] | None,
    offsets: list[int],
) -> list[dict[str, Any]]:
    """
    Get intervals for specific day offsets from coordinator data.

    This is the core function for filtering intervals by date offset.
    Abstracts the data structure - callers don't need to know where intervals are stored.

    Performance optimized:
    - Date comparison using .date() on datetime objects (fast)
    - Single pass through intervals with date caching
    - Only processes requested offsets

    Args:
        coordinator_data: Coordinator data dict (typically coordinator.data).
        offsets: List of day offsets relative to today (e.g., [0, 1] for today and tomorrow).
                 Range: -374 to +1 (allows historical comparisons up to one year + one week).
                 0 = today, -1 = yesterday, +1 = tomorrow, -7 = one week ago, etc.

    Returns:
        List of intervals matching the requested day offsets, in chronological order.

    Example:
        # Get only today's intervals
        today_intervals = get_intervals_for_day_offsets(coordinator.data, [0])

        # Get today and tomorrow
        future_intervals = get_intervals_for_day_offsets(coordinator.data, [0, 1])

        # Get all available intervals
        all = get_intervals_for_day_offsets(coordinator.data, [-1, 0, 1])

        # Compare last week with same week one year ago
        comparison = get_intervals_for_day_offsets(coordinator.data, [-7, -371])

    """
    if not coordinator_data:
        return []

    # Validate offsets are within acceptable range
    min_offset = -374  # One year + one week for comparisons
    max_offset = 1  # Tomorrow (we don't have data further in the future)

    # Extract intervals from coordinator data structure (priceInfo is now a list)
    all_intervals = coordinator_data.get("priceInfo", [])

    if not all_intervals:
        return []

    # Get current local date for comparison (no TimeService needed - use dt_util directly)
    now_local = dt_util.now()
    today_date = now_local.date()

    # Build set of target dates based on requested offsets
    target_dates = set()
    for offset in offsets:
        # Silently clamp offsets to valid range (don't fail on invalid input)
        if offset < min_offset or offset > max_offset:
            continue
        target_date = today_date + timedelta(days=offset)
        target_dates.add(target_date)

    if not target_dates:
        return []

    # Filter intervals matching target dates
    # Optimized: single pass, date() called once per interval
    result = []
    for interval in all_intervals:
        starts_at = interval.get("startsAt")
        if not starts_at:
            continue

        # Handle both datetime objects and strings (for flexibility)
        if isinstance(starts_at, str):
            # Parse if string (should be rare after parse_all_timestamps)
            starts_at = dt_util.parse_datetime(starts_at)
            if not starts_at:
                continue
            starts_at = dt_util.as_local(starts_at)

        # Fast date comparison using datetime.date()
        interval_date = starts_at.date()
        if interval_date in target_dates:
            result.append(interval)

    return result


def needs_tomorrow_data(
    cached_price_data: dict[str, Any] | None,
    tomorrow_date: date,
) -> bool:
    """Check if tomorrow data is missing or invalid in flat interval list."""
    if not cached_price_data or "homes" not in cached_price_data:
        return False

    # Check each home's intervals for tomorrow's date
    for home_data in cached_price_data["homes"].values():
        all_intervals = home_data.get("price_info", [])

        # Check if any interval exists for tomorrow's date
        has_tomorrow = False
        for interval in all_intervals:
            if starts_at := interval.get("startsAt"):  # Already datetime in local timezone
                interval_date = starts_at.date()
                if interval_date == tomorrow_date:
                    has_tomorrow = True
                    break

        # If no interval for tomorrow found, we need tomorrow data
        if not has_tomorrow:
            return True

    return False


def parse_all_timestamps(price_data: dict[str, Any], *, time: TibberPricesTimeService) -> dict[str, Any]:
    """
    Parse all API timestamp strings to datetime objects.

    This is the SINGLE place where we convert API strings to datetime objects.
    After this, all code works with datetime objects, not strings.

    Performance: ~200 timestamps parsed ONCE instead of multiple times per update cycle.

    Args:
        price_data: Raw API data with string timestamps (flat interval list)
        time: TibberPricesTimeService for parsing

    Returns:
        Same structure but with datetime objects instead of strings

    """
    if not price_data or "homes" not in price_data:
        return price_data

    # Process each home
    for home_data in price_data["homes"].values():
        # price_info is now a flat list of intervals
        price_info = home_data.get("price_info", [])

        # Skip if price_info is not a list (empty or invalid)
        if not isinstance(price_info, list):
            continue

        # Parse timestamps in flat interval list
        for interval in price_info:
            if (starts_at_str := interval.get("startsAt")) and isinstance(starts_at_str, str):
                # Parse once, convert to local timezone, store as datetime object
                interval["startsAt"] = time.parse_and_localize(starts_at_str)
                # If already datetime (e.g., from cache), skip parsing

    return price_data
