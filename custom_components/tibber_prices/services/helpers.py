"""
Shared utilities for service handlers.

This module provides common helper functions used across multiple service handlers,
such as entry validation, data extraction, timezone resolution, and search range handling.

Functions:
    get_entry_and_data: Validate config entry and extract coordinator data
    has_tomorrow_data: Check if tomorrow's price data is available
    resolve_home_timezone: Extract home timezone from coordinator
    localize_to_home_tz: Localize datetime to Tibber home timezone
    calculate_end_of_tomorrow: Calculate end of tomorrow in home timezone
    floor_to_quarter_hour: Floor datetime to quarter-hour boundary
    resolve_search_range: Resolve search start/end from various input formats
    filter_intervals_by_price_level: Filter intervals by Tibber price level
    VALID_SEARCH_SCOPES: Set of valid search_scope shorthand values
    PRICE_LEVEL_ORDER: Ordered tuple of price levels (lowest to highest)

Used by:
    - services/chartdata.py: Chart data export service
    - services/apexcharts.py: ApexCharts YAML generation
    - services/refresh_user_data.py: User data refresh
    - services/find_cheapest_block.py: Block service (cheapest + most expensive)
    - services/find_cheapest_hours.py: Hours service (cheapest + most expensive)
    - services/find_most_expensive_block.py: Most expensive block wrapper
    - services/find_most_expensive_hours.py: Most expensive hours wrapper

"""

from __future__ import annotations

from datetime import datetime, time as dt_time, timedelta
from typing import TYPE_CHECKING, Any

from custom_components.tibber_prices.const import DOMAIN
from custom_components.tibber_prices.coordinator.helpers import get_intervals_for_day_offsets
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from zoneinfo import ZoneInfo

    from custom_components.tibber_prices.coordinator import TibberPricesDataUpdateCoordinator
    from homeassistant.core import HomeAssistant

# Interval duration in minutes (quarter-hourly resolution)
INTERVAL_MINUTES = 15

# Valid scopes for the search_scope shorthand parameter
VALID_SEARCH_SCOPES = frozenset({"today", "tomorrow", "remaining_today", "next_24h", "next_48h"})

# Price level hierarchy (lowest to highest)
PRICE_LEVEL_ORDER = ("VERY_CHEAP", "CHEAP", "NORMAL", "EXPENSIVE", "VERY_EXPENSIVE")
_PRICE_LEVEL_RANK: dict[str, int] = {lvl: i for i, lvl in enumerate(PRICE_LEVEL_ORDER)}


# Parameters that define explicit search range boundaries
_EXPLICIT_RANGE_PARAMS = frozenset(
    {
        "search_start",
        "search_end",
        "search_start_time",
        "search_end_time",
        "search_start_offset_minutes",
        "search_end_offset_minutes",
        "search_start_day_offset",
        "search_end_day_offset",
    }
)


def validate_search_params(call_data: dict[str, Any]) -> None:
    """
    Validate search range parameter combinations.

    Checks for mutually exclusive parameters and required co-dependencies.
    Must be called before resolve_search_range().

    Raises:
        ServiceValidationError: If parameter combinations are invalid

    """
    has_scope = "search_scope" in call_data

    # search_scope conflicts with all explicit range parameters
    if has_scope:
        # day_offset params always appear (voluptuous defaults to 0), exclude from conflict check
        conflicts = _EXPLICIT_RANGE_PARAMS - {"search_start_day_offset", "search_end_day_offset"}
        conflicting = [p for p in conflicts if p in call_data]
        if conflicting:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="scope_conflicts_with_range",
                translation_placeholders={"params": ", ".join(sorted(conflicting))},
            )

    # search_start and search_start_time are mutually exclusive start-time specifications
    if "search_start" in call_data and "search_start_time" in call_data:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="start_time_conflict",
        )
    if "search_end" in call_data and "search_end_time" in call_data:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="end_time_conflict",
        )

    # day_offset without matching time parameter is meaningless
    # Schema defaults provide 0, but user explicitly setting non-zero without time is an error.
    # We detect explicit usage by checking for non-default values when time is absent.
    if "search_start_time" not in call_data and call_data.get("search_start_day_offset", 0) != 0:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="day_offset_requires_time",
            translation_placeholders={"offset_param": "search_start_day_offset", "time_param": "search_start_time"},
        )
    if "search_end_time" not in call_data and call_data.get("search_end_day_offset", 0) != 0:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="day_offset_requires_time",
            translation_placeholders={"offset_param": "search_end_day_offset", "time_param": "search_end_time"},
        )


def validate_price_level_range(
    min_price_level: str | None,
    max_price_level: str | None,
) -> None:
    """
    Validate that min_price_level <= max_price_level in the level hierarchy.

    Raises:
        ServiceValidationError: If min level is higher than max level

    """
    if min_price_level is None or max_price_level is None:
        return

    min_rank = _PRICE_LEVEL_RANK.get(min_price_level.upper(), 0)
    max_rank = _PRICE_LEVEL_RANK.get(max_price_level.upper(), len(PRICE_LEVEL_ORDER) - 1)

    if min_rank > max_rank:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="min_level_exceeds_max",
            translation_placeholders={"min_level": min_price_level, "max_level": max_price_level},
        )


def validate_power_profile_length(
    power_profile: list[int] | None,
    duration_intervals: int,
) -> None:
    """
    Validate that power_profile length matches the number of intervals.

    Raises:
        ServiceValidationError: If lengths don't match

    """
    if power_profile is None:
        return

    if len(power_profile) != duration_intervals:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="power_profile_length_mismatch",
            translation_placeholders={
                "profile_length": str(len(power_profile)),
                "interval_count": str(duration_intervals),
                "duration_minutes": str(duration_intervals * INTERVAL_MINUTES),
            },
        )


def get_entry_and_data(hass: HomeAssistant, entry_id: str) -> tuple[Any, Any, dict]:
    """
    Validate entry and extract coordinator and data.

    If entry_id is empty, auto-selects the single config entry for this domain.
    Raises an error if there are zero or multiple entries and no entry_id is given.

    Args:
        hass: Home Assistant instance
        entry_id: Config entry ID to validate (empty string to auto-select)

    Returns:
        Tuple of (entry, coordinator, data)

    Raises:
        ServiceValidationError: If entry cannot be resolved

    """
    if not entry_id:
        entries = hass.config_entries.async_entries(DOMAIN)
        if len(entries) == 1:
            entry = entries[0]
        elif len(entries) == 0:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="no_entries_found")
        else:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="multiple_entries_no_entry_id")
    else:
        entry = next(
            (e for e in hass.config_entries.async_entries(DOMAIN) if e.entry_id == entry_id),
            None,
        )
    if not entry or not hasattr(entry, "runtime_data") or not entry.runtime_data:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="invalid_entry_id")
    coordinator = entry.runtime_data.coordinator
    data = coordinator.data or {}
    return entry, coordinator, data


def has_tomorrow_data(coordinator: TibberPricesDataUpdateCoordinator) -> bool:
    """
    Check if tomorrow's price data is available in coordinator.

    Uses get_intervals_for_day_offsets() to automatically determine tomorrow
    based on current date.

    Args:
        coordinator: TibberPricesDataUpdateCoordinator instance

    Returns:
        True if tomorrow's data exists (at least one interval), False otherwise

    """
    coordinator_data = coordinator.data or {}
    tomorrow_intervals = get_intervals_for_day_offsets(coordinator_data, [1])
    return len(tomorrow_intervals) > 0


def resolve_home_timezone(
    coordinator: Any,
    home_id: str,
) -> str:
    """Extract home timezone from coordinator's cached user data."""
    user_data = coordinator._cached_user_data  # noqa: SLF001
    if not user_data:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="user_data_not_available",
        )

    if "viewer" in user_data:
        for home in user_data["viewer"].get("homes", []):
            if home.get("id") == home_id:
                tz = home.get("timeZone")
                if tz:
                    return tz

    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="timezone_not_found",
    )


def localize_to_home_tz(dt_value: datetime, home_tz: ZoneInfo) -> datetime:
    """
    Localize a datetime to the Tibber home timezone.

    Handles the critical two-step process:
    1. GUI naive datetime → localize to HA server timezone
    2. Convert from HA timezone to home timezone
    """
    if dt_value.tzinfo is None:
        dt_value = dt_util.as_local(dt_value)
    return dt_value.astimezone(home_tz)


def calculate_end_of_tomorrow(home_tz: ZoneInfo) -> datetime:
    """Calculate end of tomorrow in home timezone."""
    now_home = dt_util.now().astimezone(home_tz)
    tomorrow = (now_home + timedelta(days=1)).date()
    # End of tomorrow = midnight at start of day after tomorrow
    return now_home.replace(
        year=tomorrow.year,
        month=tomorrow.month,
        day=tomorrow.day,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    ) + timedelta(days=1)


def floor_to_quarter_hour(dt_value: datetime) -> datetime:
    """Floor a datetime to the current quarter-hour boundary."""
    return dt_value.replace(minute=(dt_value.minute // INTERVAL_MINUTES) * INTERVAL_MINUTES, second=0, microsecond=0)


def _resolve_time_with_day_offset(
    time_value: dt_time,
    day_offset: int,
    home_tz: ZoneInfo,
    now: datetime,
) -> datetime:
    """Resolve a time-of-day + day offset to a full datetime in home timezone."""
    now_home = now.astimezone(home_tz)
    target_date = (now_home + timedelta(days=day_offset)).date()
    return datetime(
        year=target_date.year,
        month=target_date.month,
        day=target_date.day,
        hour=time_value.hour,
        minute=time_value.minute,
        second=time_value.second,
        tzinfo=home_tz,
    )


def _resolve_scope(scope: str, now: datetime, _home_tz: ZoneInfo) -> tuple[datetime, datetime]:
    """
    Convert a search_scope shorthand into explicit start/end datetimes.

    Args:
        scope: One of "today", "tomorrow", "remaining_today", "next_24h", "next_48h"
        now: Current datetime in home timezone
        home_tz: Home timezone for date calculations

    Returns:
        Tuple of (start, end) datetimes in home timezone

    """
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start = today_start + timedelta(days=1)
    day_after_start = today_start + timedelta(days=2)

    if scope == "today":
        return today_start, tomorrow_start
    if scope == "tomorrow":
        return tomorrow_start, day_after_start
    if scope == "remaining_today":
        return floor_to_quarter_hour(now), tomorrow_start
    if scope == "next_24h":
        return floor_to_quarter_hour(now), now + timedelta(hours=24)
    if scope == "next_48h":
        return floor_to_quarter_hour(now), now + timedelta(hours=48)

    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="invalid_search_scope",
    )


def filter_intervals_by_price_level(
    intervals: list[dict[str, Any]],
    min_price_level: str | None,
    max_price_level: str | None,
) -> list[dict[str, Any]]:
    """
    Filter intervals by Tibber price level.

    Keeps only intervals whose 'level' field is within the requested range.
    If an interval has no 'level' field it is kept (avoids silently dropping data on API changes).

    Args:
        intervals: Price interval dicts with optional 'level' key
        min_price_level: Lower bound level (inclusive), e.g. "CHEAP"
        max_price_level: Upper bound level (inclusive), e.g. "NORMAL"

    Returns:
        Filtered list; same list reference if no filter is active

    """
    if min_price_level is None and max_price_level is None:
        return intervals

    min_rank = _PRICE_LEVEL_RANK.get(min_price_level.upper(), 0) if min_price_level else 0
    max_rank = (
        _PRICE_LEVEL_RANK.get(max_price_level.upper(), len(PRICE_LEVEL_ORDER) - 1)
        if max_price_level
        else len(PRICE_LEVEL_ORDER) - 1
    )

    result = []
    for iv in intervals:
        level = iv.get("level")
        if level is None:
            result.append(iv)
            continue
        rank = _PRICE_LEVEL_RANK.get(str(level).upper())
        if rank is None:
            result.append(iv)
            continue
        if min_rank <= rank <= max_rank:
            result.append(iv)
    return result


def build_rating_lookup(coordinator_data: dict[str, Any]) -> dict[str, str | None]:
    """
    Build a startsAt → rating_level lookup from enriched coordinator data.

    The coordinator's priceInfo contains rating_level (LOW/NORMAL/HIGH) computed
    from trailing 24h averages with hysteresis. Pool intervals lack this field,
    so this lookup allows annotating service responses with rating_level.

    Args:
        coordinator_data: coordinator.data dict with enriched priceInfo

    Returns:
        Dict mapping startsAt ISO string to lowercase rating_level (or None)

    """
    lookup: dict[str, str | None] = {}
    for iv in coordinator_data.get("priceInfo", []):
        starts_at = iv.get("startsAt")
        rating = iv.get("rating_level")
        if starts_at:
            lookup[starts_at] = rating.lower() if isinstance(rating, str) else None
    return lookup


def build_response_interval(
    iv: dict[str, Any],
    unit_factor: int,
    rating_lookup: dict[str, str | None],
) -> dict[str, Any]:
    """
    Build an enriched interval dict for service responses.

    Converts a raw pool interval into a companion-friendly format with
    ends_at, level, and rating_level fields.

    Args:
        iv: Raw interval dict from pool (startsAt, total, level, ...)
        unit_factor: Price unit multiplier (1 for base unit, 100 for cents, etc.)
        rating_lookup: startsAt → rating_level mapping from coordinator data

    Returns:
        Enriched interval dict for service response

    """
    starts_at = iv["startsAt"]
    if isinstance(starts_at, str):
        ends_at = (datetime.fromisoformat(starts_at) + timedelta(minutes=INTERVAL_MINUTES)).isoformat()
    else:
        ends_at = (starts_at + timedelta(minutes=INTERVAL_MINUTES)).isoformat()

    return {
        "starts_at": starts_at,
        "ends_at": ends_at,
        "price": round(iv["total"] * unit_factor, 4),
        "level": (iv.get("level") or "").lower() or None,
        "rating_level": rating_lookup.get(starts_at),
    }


def resolve_search_range(
    call_data: dict[str, Any],
    now: datetime,
    home_tz: ZoneInfo,
) -> tuple[datetime, datetime]:
    """
    Resolve search start/end from scope shorthand, explicit datetime, time+offset, or defaults.

    Priority (highest to lowest):
    0. search_scope shorthand (today, tomorrow, remaining_today, next_24h, next_48h)
    1. Explicit datetime (search_start / search_end)
    2. Time-of-day + day offset (search_start_time + search_start_day_offset)
    3. Minutes offset (search_start_offset_minutes / search_end_offset_minutes)
    4. Default (now for start, end of tomorrow for end)

    Calls validate_search_params() first to check for conflicting combinations.
    """
    validate_search_params(call_data)
    include_current = call_data.get("include_current_interval", True)

    # Priority 0: search_scope shorthand
    if "search_scope" in call_data:
        return _resolve_scope(call_data["search_scope"], now, home_tz)

    # --- Resolve start ---
    if "search_start" in call_data:
        search_start = localize_to_home_tz(call_data["search_start"], home_tz)
    elif "search_start_time" in call_data:
        day_offset = call_data.get("search_start_day_offset", 0)
        search_start = _resolve_time_with_day_offset(call_data["search_start_time"], day_offset, home_tz, now)
    elif "search_start_offset_minutes" in call_data:
        search_start = now + timedelta(minutes=call_data["search_start_offset_minutes"])
        if include_current:
            search_start = floor_to_quarter_hour(search_start)
    else:
        search_start = floor_to_quarter_hour(now) if include_current else now

    # --- Resolve end ---
    if "search_end" in call_data:
        search_end = localize_to_home_tz(call_data["search_end"], home_tz)
    elif "search_end_time" in call_data:
        day_offset = call_data.get("search_end_day_offset", 0)
        search_end = _resolve_time_with_day_offset(call_data["search_end_time"], day_offset, home_tz, now)
    elif "search_end_offset_minutes" in call_data:
        search_end = now + timedelta(minutes=call_data["search_end_offset_minutes"])
    else:
        search_end = calculate_end_of_tomorrow(home_tz)

    if search_end <= search_start:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="end_before_start",
            translation_placeholders={
                "search_start": search_start.strftime("%Y-%m-%d %H:%M %z"),
                "search_end": search_end.strftime("%Y-%m-%d %H:%M %z"),
            },
        )

    return search_start, search_end
