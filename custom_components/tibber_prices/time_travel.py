"""
Time-travel subentries - shared helpers.

A time-travel view is a `ConfigSubentry` of a home's config entry. It shows the
same home's prices as they were at a point in the past, with the clock still
advancing normally: only the reference time is shifted by a fixed negative
offset.

Everything downstream of the shifted clock follows automatically:

* The coordinator builds every `TibberPricesTimeService` with the offset, so
  "now", "today" and "tomorrow" all refer to the shifted date.
* The IntervalPool fetches and protects the shifted 4-day window instead of the
  live one, which is why each view needs its own pool (see
  `_async_create_interval_pool` in `__init__.py`).
* Entities, devices and storage keys are scoped with the subentry ID so a view
  never collides with its parent entry.

Data resolution is limited to 2025-10-01 onwards, when Tibber switched from
hourly to quarter-hourly prices. Older offsets return hourly data that this
integration's 15-minute logic cannot interpret; `MAX_OFFSET_DAYS` bounds the
configurable range but the practical floor is that date.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from .const import CONF_VIRTUAL_TIME_OFFSET_DAYS, CONF_VIRTUAL_TIME_OFFSET_HOURS, CONF_VIRTUAL_TIME_OFFSET_MINUTES

if TYPE_CHECKING:
    from collections.abc import Iterator

    from homeassistant.config_entries import ConfigEntry, ConfigSubentry

# Subentry type key. Must match the `config_subentries.<type>` key in the
# translation files and the key returned by async_get_supported_subentry_types().
SUBENTRY_TYPE_TIME_TRAVEL = "time_travel"

# Slider bounds for the day offset (one year + one week, matching the range
# get_intervals_for_day_offsets() accepts).
MAX_OFFSET_DAYS = 374


def get_time_travel_offset(subentry: ConfigSubentry | None) -> timedelta:
    """
    Return the clock offset configured for a subentry.

    Args:
        subentry: The time-travel subentry, or None for the live config entry.

    Returns:
        A non-positive timedelta. Zero means "live" - no shift at all.

    """
    if subentry is None:
        return timedelta()

    return build_offset(
        days=int(subentry.data.get(CONF_VIRTUAL_TIME_OFFSET_DAYS, 0) or 0),
        hours=int(subentry.data.get(CONF_VIRTUAL_TIME_OFFSET_HOURS, 0) or 0),
        minutes=int(subentry.data.get(CONF_VIRTUAL_TIME_OFFSET_MINUTES, 0) or 0),
    )


def build_offset(*, days: int, hours: int, minutes: int) -> timedelta:
    """
    Build a normalized (never positive) offset from its components.

    The config flow already stores negative values, but a hand-edited or
    partially migrated subentry must not be able to shift the clock into the
    future - there is no price data there to show.

    Args:
        days: Day component (sign is ignored).
        hours: Hour component (sign is ignored).
        minutes: Minute component (sign is ignored).

    Returns:
        Non-positive timedelta.

    """
    return -abs(timedelta(days=days, hours=hours, minutes=minutes))


def is_time_travel_subentry(subentry: ConfigSubentry) -> bool:
    """Return True if the subentry is a time-travel view of its parent entry."""
    return subentry.subentry_type == SUBENTRY_TYPE_TIME_TRAVEL


def iter_time_travel_subentries(entry: ConfigEntry) -> Iterator[ConfigSubentry]:
    """
    Yield the time-travel subentries of a config entry, in a stable order.

    Ordering by subentry ID keeps entity creation deterministic across restarts.
    """
    for subentry in sorted(entry.subentries.values(), key=lambda s: s.subentry_id):
        if is_time_travel_subentry(subentry):
            yield subentry


def subentry_storage_id(entry_id: str, subentry: ConfigSubentry | None) -> str:
    """
    Return the storage identifier for a coordinator's interval pool.

    The live coordinator keeps the plain entry ID so existing pool storage stays
    valid; each time-travel view gets its own suffixed store.
    """
    if subentry is None:
        return entry_id
    return f"{entry_id}_{subentry.subentry_id}"
