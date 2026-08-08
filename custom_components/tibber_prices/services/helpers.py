"""
Shared utilities for service handlers.

This module provides common helper functions used across multiple service handlers,
such as entry validation, data extraction, timezone resolution, and search range handling.

Functions:
    resolve_service_target: Resolve what a call operates on - a home or one of its
        time-travel views - bundling its clock, interval pool and coordinator data
    get_entry_and_data: Validate config entry and extract coordinator data
    has_tomorrow_data: Check if tomorrow's price data is available
    resolve_home_timezone: Extract home timezone from coordinator
    localize_to_home_tz: Localize datetime to Tibber home timezone
    calculate_end_of_tomorrow: Calculate end of tomorrow in home timezone
    floor_to_quarter_hour: Floor datetime to quarter-hour boundary
    apply_must_finish_by: Convert must_finish_by deadline to search_end
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

from dataclasses import dataclass
from datetime import datetime, time as dt_time, timedelta
import logging
from typing import TYPE_CHECKING, Any

from custom_components.tibber_prices.api.exceptions import (
    TibberPricesApiClientAuthenticationError,
    TibberPricesApiClientError,
)
from custom_components.tibber_prices.const import DOMAIN
from custom_components.tibber_prices.coordinator.helpers import get_intervals_for_day_offsets
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from zoneinfo import ZoneInfo

    from custom_components.tibber_prices.coordinator import TibberPricesDataUpdateCoordinator
    from custom_components.tibber_prices.interval_pool import TibberPricesIntervalPool
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Interval duration in minutes (quarter-hourly resolution)
INTERVAL_MINUTES = 15

# Default flexibility percentage for outlier smoothing in services
# Matches the period system default (15%) for consistency
DEFAULT_SERVICE_SMOOTHING_FLEX = 15.0

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
        "must_finish_by",
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

    # must_finish_by conflicts with all end-boundary parameters
    if "must_finish_by" in call_data:
        end_conflicts = {"search_end", "search_end_time", "search_end_offset_minutes"}
        conflicting_end = [p for p in end_conflicts if p in call_data]
        if conflicting_end:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="must_finish_by_conflicts_with_end",
                translation_placeholders={"params": ", ".join(sorted(conflicting_end))},
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


def apply_must_finish_by(
    call_data: dict[str, Any],
    home_tz: ZoneInfo,
) -> tuple[dict[str, Any], datetime | None]:
    """Convert must_finish_by deadline to search_end.

    When must_finish_by is set, search_end is set to must_finish_by directly.
    The interval pool uses exclusive end_time (intervals with startsAt < end_time),
    so the latest found window/schedule naturally ends at search_end.

    The deadline is floored onto the quarter-hour grid first. This is what makes it
    a genuine upper bound: an off-grid deadline such as 07:05 would otherwise admit
    the 07:00 interval, whose window runs to 07:15 and overshoots by 10 minutes.
    Flooring is applied here rather than to search_end in general, because a plain
    search_end is a range bound (partial overlap is fine) while must_finish_by is a
    promise the result must not break.

    Args:
        call_data: Service call data dict.
        home_tz: Home timezone for datetime localization.

    Returns:
        Tuple of (possibly modified call_data, localized must_finish_by datetime or None).
        If must_finish_by is absent, returns the original call_data unchanged.

    """
    if "must_finish_by" not in call_data:
        return call_data, None

    must_finish_by = localize_to_home_tz(call_data["must_finish_by"], home_tz)

    modified = dict(call_data)
    modified["search_end"] = floor_to_quarter_hour(must_finish_by)
    del modified["must_finish_by"]
    return modified, must_finish_by


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


@dataclass(frozen=True)
class ServiceTarget:
    """What a service call operates on: a home, or one time-travel view of it.

    A time-travel view runs its own coordinator on a shifted clock and keeps its own
    interval pool (see data.TibberPricesSubentryData). Everything a service needs to
    answer against a view rather than live differs: the clock that defines "now", the
    pool the prices come from, and the coordinator data the periods were built from.
    Bundling them means a service reads its inputs from one place and cannot
    accidentally mix a view's clock with the live pool.
    """

    entry: Any
    """The config entry. Always the home's entry, never the view."""

    subentry: Any | None
    """The targeted view's subentry, or None when targeting the home itself."""

    coordinator: Any
    interval_pool: TibberPricesIntervalPool
    data: dict

    @property
    def is_view(self) -> bool:
        """Return True when this call targets a time-travel view."""
        return self.subentry is not None

    @property
    def time(self) -> Any:
        """Return the TimeService defining "now" for this target.

        For a view this trails real time by the view's offset, which is what makes a
        relative search range ("next 24h") mean the view's next 24 hours.
        """
        return self.coordinator.time

    def now(self, home_tz: ZoneInfo) -> datetime:
        """Return the current moment for this target, in the home timezone."""
        return self.time.now().astimezone(home_tz)

    @property
    def label(self) -> str:
        """Return a short human-readable name for logs and error messages."""
        if self.subentry is None:
            return self.entry.title
        return f"{self.entry.title} / {self.subentry.title}"


def _resolve_entry(hass: HomeAssistant, entry_id: str) -> Any:
    """Resolve a config entry by ID, auto-selecting when there is exactly one."""
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
    return entry


def _entry_title(hass: HomeAssistant, entry_id: str) -> str:
    """Return an entry's display title, falling back to its raw ID.

    Used for error messages only, so an ID that resolves to nothing must not raise -
    naming it verbatim is still more useful to the reader than omitting it.
    """
    entry = next((e for e in hass.config_entries.async_entries(DOMAIN) if e.entry_id == entry_id), None)
    return entry.title if entry is not None else entry_id


def _resolve_view_device(hass: HomeAssistant, device_id: str) -> tuple[str, str | None]:
    """
    Map a device ID to the (entry_id, subentry_id) it stands for.

    Views are addressed by their device because that is what a user sees and picks;
    subentry IDs are internal. Home Assistant 2026.8 scopes a device to exactly one
    config entry and at most one subentry, so the device carries both directly.

    The picker in services.yaml is filtered to view devices, so a home device only
    arrives here from hand-written YAML. It has no subentry and resolves to a None
    subentry, i.e. that entry's live data - the sensible reading of naming the home,
    and not worth rejecting.

    Raises:
        ServiceValidationError: If the device is unknown to Home Assistant.

    """
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="invalid_view_device")
    return device.config_entry_id, device.config_subentry_id


def resolve_service_target(
    hass: HomeAssistant,
    entry_id: str,
    view_device_id: str = "",
) -> ServiceTarget:
    """
    Resolve what a service call operates on.

    Without view_device_id this is the home itself, selected by entry_id (or the only
    entry, when there is just one). With it, the call is answered against that
    time-travel view: its clock, its interval pool, its coordinator data.

    The view's device determines the entry as well, so a caller that picks a view does
    not have to also pass the matching entry_id. Passing a mismatched pair is rejected
    rather than silently resolved in favour of one of them.

    Args:
        hass: Home Assistant instance.
        entry_id: Config entry ID (empty string to auto-select the single entry).
        view_device_id: Device ID of a time-travel view, or empty for the home.

    Returns:
        The resolved ServiceTarget.

    Raises:
        ServiceValidationError: If the entry or view cannot be resolved, if the two
            disagree, or if the view is not currently set up.

    """
    if not view_device_id:
        entry = _resolve_entry(hass, entry_id)
        coordinator = entry.runtime_data.coordinator
        return ServiceTarget(
            entry=entry,
            subentry=None,
            coordinator=coordinator,
            interval_pool=entry.runtime_data.interval_pool,
            data=coordinator.data or {},
        )

    view_entry_id, subentry_id = _resolve_view_device(hass, view_device_id)
    if entry_id and entry_id != view_entry_id:
        # Reachable straight from the UI, not just hand-written YAML: a device selector
        # can only be filtered by integration and model, never by the config entry
        # picked in another field, so with several homes the view picker lists every
        # home's views. Name both sides - "they disagree" alone leaves the caller
        # guessing which of the two fields they got wrong.
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="view_entry_mismatch",
            translation_placeholders={
                "entry_home": _entry_title(hass, entry_id),
                "view_home": _entry_title(hass, view_entry_id),
            },
        )

    entry = _resolve_entry(hass, view_entry_id)
    if subentry_id is None:
        # The home's own device - the live data of that entry.
        coordinator = entry.runtime_data.coordinator
        return ServiceTarget(
            entry=entry,
            subentry=None,
            coordinator=coordinator,
            interval_pool=entry.runtime_data.interval_pool,
            data=coordinator.data or {},
        )

    view = entry.runtime_data.subentries.get(subentry_id)
    if view is None:
        # The device exists but the view is not running - it was removed, or the
        # entry has not finished setting its views up.
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="view_not_loaded")

    return ServiceTarget(
        entry=entry,
        subentry=view.subentry,
        coordinator=view.coordinator,
        interval_pool=view.interval_pool,
        data=view.coordinator.data or {},
    )


def get_entry_and_data(hass: HomeAssistant, entry_id: str) -> tuple[Any, Any, dict]:
    """
    Validate entry and extract coordinator and data.

    Kept for callers that are inherently entry-level (refreshing account data,
    clearing a cache) and can never address a view. Anything that reads prices
    should use resolve_service_target() so it can answer for a view too.

    Args:
        hass: Home Assistant instance
        entry_id: Config entry ID to validate (empty string to auto-select)

    Returns:
        Tuple of (entry, coordinator, data)

    Raises:
        ServiceValidationError: If entry cannot be resolved

    """
    entry = _resolve_entry(hass, entry_id)
    coordinator = entry.runtime_data.coordinator
    return entry, coordinator, coordinator.data or {}


async def async_fetch_service_intervals(
    pool: TibberPricesIntervalPool,
    *,
    api_client: Any,
    user_data: dict[str, Any] | None,
    start_time: datetime,
    end_time: datetime,
    service_label: str,
) -> tuple[list[dict[str, Any]], bool]:
    """
    Fetch price intervals for a service request resiliently.

    Shared, resilient wrapper around the interval pool used by every price-query
    service. It guarantees two things the raw pool call does not:

    1. Sensor isolation: passes track_degraded=False so a service request can never
       flip the pool's degraded-state flags (which govern sensor availability). A
       failing or succeeding service fetch therefore has zero effect on sensor health.
    2. Graceful failure: on a transient API/data error the helper returns
       ([], False) instead of raising, so the service can still return a well-formed
       response (possibly with empty contents) for automations to consume.

    Authentication errors are re-raised unchanged so the coordinator can trigger the
    reauth flow.

    Args:
        pool: The config entry's interval pool.
        api_client: TibberPricesApiClient instance.
        user_data: Cached user data dict (may be None during early setup).
        start_time: Start of range (inclusive, timezone-aware).
        end_time: End of range (exclusive, timezone-aware).
        service_label: Human-readable service name for logging.

    Returns:
        Tuple of (intervals, fetch_ok):
        - intervals: Price intervals for the range. Empty list on failure.
        - fetch_ok: True if the data was available, False if an API error
          prevented fetching the requested (uncached) range.

    Raises:
        TibberPricesApiClientAuthenticationError: If authentication failed.

    """
    if start_time >= end_time:
        # Degenerate (empty) range - e.g. "remaining_today" with
        # include_current_interval=False during the final interval of the day, where
        # the search start is advanced onto tomorrow's midnight boundary. The pool
        # rejects such ranges outright; report it as "no data" rather than letting it
        # surface as a (false) API outage.
        _LOGGER.debug(
            "%s: empty search range (%s >= %s) - no intervals to fetch",
            service_label,
            start_time,
            end_time,
        )
        return [], True

    try:
        intervals, _api_called = await pool.get_intervals(
            api_client=api_client,
            user_data=user_data or {},
            start_time=start_time,
            end_time=end_time,
            track_degraded=False,
        )
    except TibberPricesApiClientAuthenticationError:
        raise
    except TibberPricesApiClientError as err:
        _LOGGER.warning(
            "%s: price data unavailable (%s) - returning empty result so sensors stay unaffected",
            service_label,
            err,
        )
        return [], False
    return intervals, True


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


def calculate_end_of_tomorrow(home_tz: ZoneInfo, now: datetime | None = None) -> datetime:
    """Calculate end of tomorrow in home timezone.

    Args:
        home_tz: Home timezone.
        now: The moment to count "tomorrow" from. Pass a time-travel view's clock to
            get the view's tomorrow; defaults to real time for entry-level callers.

    """
    now_home = (now or dt_util.now()).astimezone(home_tz)
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


def ceil_to_quarter_hour(dt_value: datetime) -> datetime:
    """Round dt_value up to a quarter-hour boundary, leaving boundaries untouched.

    Use for a point in time the caller named explicitly (an absolute datetime, a
    time-of-day, or an offset from now). A named point that already sits on a
    boundary starts an interval rather than interrupting one, so it is kept as-is;
    anything in between advances to the next boundary.
    """
    floored = floor_to_quarter_hour(dt_value)
    return floored if floored == dt_value else floored + timedelta(minutes=INTERVAL_MINUTES)


def ceil_to_next_quarter_hour(dt_value: datetime) -> datetime:
    """Return the start of the next quarter-hour interval after dt_value.

    Always advances past the interval that contains dt_value, even when
    dt_value falls exactly on a boundary. Use for ``now`` itself: the interval
    containing the present moment is running, and one that starts exactly now is
    the current interval too - both are skipped by include_current_interval=False.

    Aligning matters beyond semantics. The pool resolves a range by stepping from
    the start in quarter-hour increments and looking each timestamp up verbatim in
    an index keyed on :00/:15/:30/:45, so a raw ``now`` like ``14:47:00.167996``
    matches nothing at all and yields no intervals.
    """
    return floor_to_quarter_hour(dt_value) + timedelta(minutes=INTERVAL_MINUTES)


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


def _resolve_scope(
    scope: str,
    now: datetime,
    _home_tz: ZoneInfo,
    *,
    include_current: bool,
) -> tuple[datetime, datetime]:
    """
    Convert a search_scope shorthand into explicit start/end datetimes.

    Args:
        scope: One of "today", "tomorrow", "remaining_today", "next_24h", "next_48h"
        now: Current datetime in home timezone
        home_tz: Home timezone for date calculations

    Returns:
        Tuple of (start, end) datetimes in home timezone, both on the quarter-hour
        grid. Day boundaries are aligned already; the rolling next_24h/next_48h ends
        are ceiled to cover the whole interval the horizon falls inside.

    """
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start = today_start + timedelta(days=1)
    day_after_start = today_start + timedelta(days=2)

    rolling_start = floor_to_quarter_hour(now) if include_current else ceil_to_next_quarter_hour(now)

    if scope == "today":
        return today_start, tomorrow_start
    if scope == "tomorrow":
        return tomorrow_start, day_after_start
    if scope == "remaining_today":
        return rolling_start, tomorrow_start
    if scope == "next_24h":
        return rolling_start, ceil_to_quarter_hour(now + timedelta(hours=24))
    if scope == "next_48h":
        return rolling_start, ceil_to_quarter_hour(now + timedelta(hours=48))

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

    Whichever branch applies, both boundaries are snapped onto the quarter-hour grid
    the interval pool is indexed by. The start must be aligned for correctness - the
    pool steps from it in quarter-hour increments and looks each timestamp up
    verbatim, so an off-grid start matches nothing and yields no data at all. It
    rounds in the direction include_current_interval asks for. The end rounds up,
    which is a no-op in terms of intervals searched and merely reports the range that
    was really covered.

    Calls validate_search_params() first to check for conflicting combinations.
    """
    validate_search_params(call_data)
    include_current = call_data.get("include_current_interval", True)

    # Priority 0: search_scope shorthand
    if "search_scope" in call_data:
        return _resolve_scope(call_data["search_scope"], now, home_tz, include_current=include_current)

    # --- Resolve start ---
    # Every branch snaps to the grid. The `now` default is the only one that must
    # also skip an interval starting exactly at the reference point, so it is the
    # only user of ceil_to_next_quarter_hour; a start the caller named is not
    # "current" just because it happens to sit on a boundary.
    if "search_start" in call_data:
        raw_start = localize_to_home_tz(call_data["search_start"], home_tz)
        search_start = floor_to_quarter_hour(raw_start) if include_current else ceil_to_quarter_hour(raw_start)
    elif "search_start_time" in call_data:
        day_offset = call_data.get("search_start_day_offset", 0)
        raw_start = _resolve_time_with_day_offset(call_data["search_start_time"], day_offset, home_tz, now)
        search_start = floor_to_quarter_hour(raw_start) if include_current else ceil_to_quarter_hour(raw_start)
    elif "search_start_offset_minutes" in call_data:
        raw_start = now + timedelta(minutes=call_data["search_start_offset_minutes"])
        search_start = floor_to_quarter_hour(raw_start) if include_current else ceil_to_quarter_hour(raw_start)
    else:
        raw_start = now
        search_start = floor_to_quarter_hour(now) if include_current else ceil_to_next_quarter_hour(now)

    # --- Resolve end ---
    if "search_end" in call_data:
        raw_end = localize_to_home_tz(call_data["search_end"], home_tz)
    elif "search_end_time" in call_data:
        day_offset = call_data.get("search_end_day_offset", 0)
        raw_end = _resolve_time_with_day_offset(call_data["search_end_time"], day_offset, home_tz, now)
    elif "search_end_offset_minutes" in call_data:
        raw_end = now + timedelta(minutes=call_data["search_end_offset_minutes"])
    else:
        raw_end = calculate_end_of_tomorrow(home_tz, now)

    # Validate on the values the caller actually asked for. Snapping can still shrink
    # a range below one interval, and that is "no window fits", not a bad request.
    if raw_end <= raw_start:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="end_before_start",
            translation_placeholders={
                "search_start": raw_start.strftime("%Y-%m-%d %H:%M %z"),
                "search_end": raw_end.strftime("%Y-%m-%d %H:%M %z"),
            },
        )

    # The end rounds up: the pool takes startsAt < end, so an off-grid end already
    # admits the interval it falls inside. Ceiling changes nothing about which
    # intervals are searched, it just reports the range that was actually covered.
    # Deadlines are the exception and are floored in apply_must_finish_by().
    return search_start, ceil_to_quarter_hour(raw_end)


def smooth_service_intervals(
    intervals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Apply outlier smoothing to price intervals for service window finding.

    Reuses the period system's outlier filtering with a fixed flexibility
    percentage. Smoothed intervals are used for window FINDING only —
    original prices should be restored for response reporting.

    Args:
        intervals: Price intervals to smooth.

    Returns:
        New list of intervals with spike prices smoothed.
        Smoothed intervals have '_original_total' preserving the real price.

    """
    from custom_components.tibber_prices.coordinator.period_handlers.outlier_filtering import (  # noqa: PLC0415
        filter_price_outliers,
    )

    return filter_price_outliers(intervals, DEFAULT_SERVICE_SMOOTHING_FLEX, 0)


def restore_original_prices(intervals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Restore original prices on intervals that were smoothed.

    After using smoothed intervals for window finding, call this to get
    intervals with true prices for response reporting.

    Args:
        intervals: Intervals possibly containing '_original_total' from smoothing.

    Returns:
        New list of intervals with original prices restored and smoothing
        metadata removed.

    """
    result = []
    for iv in intervals:
        if "_original_total" in iv:
            restored = {k: v for k, v in iv.items() if k not in ("_smoothed", "_original_total")}
            restored["total"] = iv["_original_total"]
            result.append(restored)
        else:
            result.append(iv)
    return result


def calculate_search_range_avg(intervals: list[dict[str, Any]]) -> float | None:
    """
    Calculate average price across all intervals in the search range.

    Used as reference for min_distance_from_avg validation.

    Args:
        intervals: All price intervals in the search range (unfiltered).

    Returns:
        Average price in base currency unit, or None if no intervals.

    """
    if not intervals:
        return None
    return sum(iv["total"] for iv in intervals) / len(intervals)


def check_min_distance_from_avg(
    window_mean_base: float,
    range_avg: float,
    min_distance_pct: float,
    *,
    reverse: bool,
) -> bool:
    """
    Check if window mean price meets the minimum distance from range average.

    For cheapest searches: window mean must be at least X% BELOW range average.
    For most expensive searches: window mean must be at least X% ABOVE range average.

    CRITICAL: Uses abs(range_avg) to scale the distance so the direction of the
    threshold shift is always correct, even when range_avg is negative (Tibber
    prices can go negative during grid oversupply). Multiplying a negative
    range_avg directly by (1 ± ratio) flips the intended direction (e.g. avg *
    1.05 makes a negative average MORE negative, i.e. cheaper, which is the
    wrong direction for a "most expensive" threshold). This mirrors the
    abs()-based normalization already used for the period system's
    min_distance_from_avg handling (see coordinator/period_handlers/level_filtering.py).

    Args:
        window_mean_base: Window mean price in BASE currency (not display unit).
        range_avg: Search range average price in BASE currency.
        min_distance_pct: Required distance as percentage (e.g. 5.0 = 5%).
        reverse: True for most-expensive searches.

    Returns:
        True if the window passes the distance check.

    """
    if range_avg == 0:
        return True  # Cannot calculate percentage difference from zero

    distance_ratio = min_distance_pct / 100
    distance_amount = abs(range_avg) * distance_ratio
    if reverse:
        # Most expensive: window mean must be >= avg + distance
        threshold = range_avg + distance_amount
        return window_mean_base >= threshold
    # Cheapest: window mean must be <= avg - distance
    threshold = range_avg - distance_amount
    return window_mean_base <= threshold
