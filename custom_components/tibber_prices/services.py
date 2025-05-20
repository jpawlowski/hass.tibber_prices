"""Services for Tibber Prices integration."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Final

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

from .const import DOMAIN

PRICE_SERVICE_NAME = "get_price"
ATTR_DAY: Final = "day"
ATTR_ENTRY_ID: Final = "entry_id"
ATTR_TIME: Final = "time"

SERVICE_SCHEMA: Final = vol.Schema(
    {
        vol.Required(ATTR_ENTRY_ID): str,
        vol.Optional(ATTR_DAY, default="today"): vol.In(["yesterday", "today", "tomorrow"]),
        vol.Optional(ATTR_TIME): vol.Match(r"^(\d{2}:\d{2}(:\d{2})?)$"),  # HH:mm or HH:mm:ss
    }
)


def _merge_priceinfo_and_pricerating(price_info: list[dict], price_rating: list[dict]) -> list[dict]:
    """
    Merge priceInfo and priceRating intervals by timestamp, prefixing rating fields.

    Also rename startsAt to start_time. Preserves item order.
    """
    rating_by_time = {(r.get("time") or r.get("startsAt")): r for r in price_rating or []}
    merged = []
    for interval in price_info or []:
        ts = interval.get("startsAt")
        merged_interval = {"start_time": ts} if ts is not None else {}
        for k, v in interval.items():
            if k == "startsAt":
                continue
            if k == "total":
                merged_interval["price"] = v
                merged_interval["price_ct"] = round(v * 100, 2)
            elif k not in ("energy", "tax"):
                merged_interval[k] = v
        rating = rating_by_time.get(ts)
        if rating:
            for k, v in rating.items():
                if k in ("time", "startsAt", "total", "tax", "energy"):
                    continue
                if k == "difference":
                    merged_interval["rating_difference_%"] = v
                else:
                    merged_interval[f"rating_{k}"] = v
        merged.append(merged_interval)
    return merged


def _find_previous_interval(
    merged: list[dict],
    all_ratings: list[dict],
    coordinator: Any,
    day: str,
) -> Any:
    """Find previous interval from previous day if needed."""
    if merged and day == "today":
        yday_info = coordinator.data["priceInfo"].get("yesterday") or []
        if yday_info:
            yday_ratings = [
                r
                for r in all_ratings
                if r.get("time", r.get("startsAt", "")).startswith(_get_day_prefixes(yday_info)[0])
            ]
            yday_merged = _merge_priceinfo_and_pricerating(yday_info, yday_ratings)
            if yday_merged:
                return yday_merged[-1]
    return None


def _find_next_interval(
    merged: list[dict],
    all_ratings: list[dict],
    coordinator: Any,
    day: str,
) -> Any:
    """Find next interval from next day if needed."""
    if merged and day == "today":
        tmrw_info = coordinator.data["priceInfo"].get("tomorrow") or []
        if tmrw_info:
            tmrw_ratings = [
                r
                for r in all_ratings
                if r.get("time", r.get("startsAt", "")).startswith(_get_day_prefixes(tmrw_info)[0])
            ]
            tmrw_merged = _merge_priceinfo_and_pricerating(tmrw_info, tmrw_ratings)
            if tmrw_merged:
                return tmrw_merged[0]
    return None


def _select_intervals(
    merged: list[dict], all_ratings: list[dict], coordinator: Any, day: str, now: datetime, *, is_simulated: bool
) -> tuple[Any, Any, Any]:
    """
    Select previous, current, and next intervals for the given day and time.

    If is_simulated is True, always calculate previous/current/next for all days, but:
    - For 'yesterday', never fetch previous from the day before yesterday.
    - For 'tomorrow', never fetch next from the day after tomorrow.
    If is_simulated is False, previous/current/next are None for 'yesterday' and 'tomorrow'.
    """
    if not merged:
        return None, None, None

    if not is_simulated and day in ("yesterday", "tomorrow"):
        return None, None, None

    idx = None
    for i, interval in enumerate(merged):
        start_time = interval.get("start_time")
        if not start_time:
            continue
        start_dt = dt_util.parse_datetime(start_time)
        if start_dt is None:
            try:
                start_dt = datetime.fromisoformat(start_time)
            except ValueError:
                continue
        if start_dt.tzinfo is None:
            start_dt = dt_util.as_local(start_dt)
        cmp_now = now
        if cmp_now.tzinfo is None:
            cmp_now = dt_util.as_local(cmp_now)
        if start_dt <= cmp_now:
            idx = i
        if start_dt > cmp_now:
            break

    previous_interval = None
    current_interval = None
    next_interval = None

    if idx is None:
        next_interval = merged[0]
    else:
        current_interval = merged[idx]
        previous_interval = merged[idx - 1] if idx > 0 else None
        if idx + 1 < len(merged):
            next_interval = merged[idx + 1]

    # For today, allow previous/next from adjacent days
    if day == "today":
        if idx is not None and idx == 0:
            previous_interval = _find_previous_interval(merged, all_ratings, coordinator, day)
        if idx is not None and idx == len(merged) - 1:
            next_interval = _find_next_interval(merged, all_ratings, coordinator, day)

    return previous_interval, current_interval, next_interval


def get_adjacent_start_time(price_info_by_day: dict, day_key: str, *, first: bool) -> str | None:
    """Get the start_time from the first/last interval of an adjacent day."""
    info = price_info_by_day.get(day_key) or []
    if not info:
        return None
    idx = 0 if first else -1
    return info[idx].get("startsAt")


def annotate_intervals_with_times(
    merged: list[dict],
    price_info_by_day: dict,
    day: str,
) -> None:
    """Annotate merged intervals with end_time and previous_end_time."""
    for idx, interval in enumerate(merged):
        # Default: next interval's start_time
        if idx + 1 < len(merged):
            interval["end_time"] = merged[idx + 1].get("start_time")
        # Last interval: look into tomorrow if today, or None otherwise
        elif day == "today":
            next_start = get_adjacent_start_time(price_info_by_day, "tomorrow", first=True)
            interval["end_time"] = next_start
        elif day == "yesterday":
            next_start = get_adjacent_start_time(price_info_by_day, "today", first=True)
            interval["end_time"] = next_start
        elif day == "tomorrow":
            interval["end_time"] = None
        else:
            interval["end_time"] = None
        # First interval: look into yesterday if today, or None otherwise
        if idx == 0:
            if day == "today":
                prev_end = get_adjacent_start_time(price_info_by_day, "yesterday", first=False)
                interval["previous_end_time"] = prev_end
            elif day == "tomorrow":
                prev_end = get_adjacent_start_time(price_info_by_day, "today", first=False)
                interval["previous_end_time"] = prev_end
            elif day == "yesterday":
                interval["previous_end_time"] = None
            else:
                interval["previous_end_time"] = None


def get_price_stat(merged: list[dict], stat: str) -> tuple[float, str | None, str | None]:
    """Return min or max price and its start and end time from merged intervals."""
    if not merged:
        return 0, None, None
    values = [float(interval.get("price", 0)) for interval in merged if "price" in interval]
    if not values:
        return 0, None, None
    val = min(values) if stat == "min" else max(values)
    start_time = next((interval.get("start_time") for interval in merged if interval.get("price") == val), None)
    end_time = next((interval.get("end_time") for interval in merged if interval.get("price") == val), None)
    return val, start_time, end_time


async def _get_price(call: ServiceCall) -> dict[str, Any]:
    """
    Return merged priceInfo and priceRating for the requested day and config entry.

    If 'time' is provided, it must be in HH:mm or HH:mm:ss format and is combined with the selected 'day'.
    This only affects 'previous', 'current', and 'next' fields, not the 'prices' list.
    If 'time' is not provided, the current time is used for all days.
    """
    hass = call.hass
    day = call.data.get(ATTR_DAY, "today")
    entry_id = call.data.get(ATTR_ENTRY_ID)
    time_value = call.data.get(ATTR_TIME)
    if not entry_id:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="missing_entry_id")
    entry = next((e for e in hass.config_entries.async_entries(DOMAIN) if e.entry_id == entry_id), None)
    if not entry or not hasattr(entry, "runtime_data") or not entry.runtime_data:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="invalid_entry_id")
    coordinator = entry.runtime_data.coordinator
    data = coordinator.data or {}
    price_info_data = data.get("priceInfo") or {}
    price_rating_data = data.get("priceRating") or {}
    hourly_ratings = price_rating_data.get("hourly") or []
    rating_threshold_percentages = price_rating_data.get("thresholdPercentages")
    currency = price_rating_data.get("currency")

    # Fetch all relevant day data once
    price_info_by_day = {d: price_info_data.get(d) or [] for d in ("yesterday", "today", "tomorrow")}
    day_prefixes = {d: _get_day_prefixes(price_info_by_day[d]) for d in ("yesterday", "today", "tomorrow")}
    ratings_by_day = {
        d: [
            r
            for r in hourly_ratings
            if day_prefixes[d] and r.get("time", r.get("startsAt", "")).startswith(day_prefixes[d][0])
        ]
        if price_info_by_day[d] and day_prefixes[d]
        else []
        for d in ("yesterday", "today", "tomorrow")
    }

    price_info = price_info_by_day[day]
    all_ratings = ratings_by_day[day]
    merged = _merge_priceinfo_and_pricerating(price_info, all_ratings)

    annotate_intervals_with_times(merged, price_info_by_day, day)

    price_avg = (
        round(sum(float(interval.get("price", 0)) for interval in merged if "price" in interval) / len(merged), 4)
        if merged
        else 0
    )
    price_min, price_min_start_time, price_min_end_time = get_price_stat(merged, "min")
    price_max, price_max_start_time, price_max_end_time = get_price_stat(merged, "max")

    if time_value:
        if not price_info or not price_info[0].get("startsAt"):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_data_for_day",
            )
        day_prefix = price_info[0]["startsAt"].split("T")[0]
        dt_str = f"{day_prefix}T{time_value}"
        try:
            now = datetime.fromisoformat(dt_str)
        except ValueError as exc:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_simulate_time",
                translation_placeholders={"error": str(exc)},
            ) from exc
        is_simulated = True
    else:
        if not price_info or not price_info[0].get("startsAt"):
            now = dt_util.now().replace(second=0, microsecond=0)
        else:
            day_prefix = price_info[0]["startsAt"].split("T")[0]
            current_time = dt_util.now().time().replace(second=0, microsecond=0)
            dt_str = f"{day_prefix}T{current_time.isoformat()}"
            try:
                now = datetime.fromisoformat(dt_str)
            except ValueError:
                now = dt_util.now().replace(second=0, microsecond=0)
        is_simulated = True

    previous_interval, current_interval, next_interval = _select_intervals(
        merged, ratings_by_day[day], coordinator, day, now, is_simulated=is_simulated
    )

    # Remove 'previous_end_time' from output intervals
    for interval in merged:
        if "previous_end_time" in interval:
            del interval["previous_end_time"]

    return {
        "average": {
            "start_time": merged[0].get("start_time") if merged else None,
            "end_time": merged[0].get("end_time") if merged else None,
            "price": price_avg,
            "price_ct": round(price_avg * 100, 2),
        },
        "minimum": {
            "start_time": price_min_start_time,
            "end_time": price_min_end_time,
            "price": price_min,
            "price_ct": round(price_min * 100, 2),
        },
        "maximum": {
            "start_time": price_max_start_time,
            "end_time": price_max_end_time,
            "price": price_max,
            "price_ct": round(price_max * 100, 2),
        },
        "previous": previous_interval,
        "current": current_interval,
        "next": next_interval,
        "currency": currency,
        "rating_threshold_%": rating_threshold_percentages,
        "prices": merged,
    }


def _get_day_prefixes(price_info: list[dict]) -> list[str]:
    """Get ISO date prefixes for the requested day from price_info intervals."""
    prefixes = set()
    for interval in price_info:
        ts = interval.get("startsAt")
        if ts and "T" in ts:
            prefixes.add(ts.split("T")[0])
    return list(prefixes)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Tibber Prices integration."""
    hass.services.async_register(
        DOMAIN,
        PRICE_SERVICE_NAME,
        _get_price,
        schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
