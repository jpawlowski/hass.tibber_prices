"""Services for Tibber Prices integration."""

from __future__ import annotations

from dataclasses import dataclass
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
        vol.Optional(ATTR_DAY): vol.In(["yesterday", "today", "tomorrow"]),
        vol.Optional(ATTR_TIME): vol.Match(r"^(\d{2}:\d{2}(:\d{2})?)$"),  # HH:mm or HH:mm:ss
    }
)


def _merge_priceinfo_and_pricerating(price_info: list[dict], price_rating: list[dict]) -> list[dict]:
    """
    Merge priceInfo and priceRating intervals by timestamp, prefixing rating fields.

    Also rename startsAt to start_time. Preserves item order.
    Adds 'start_dt' (datetime) to each merged interval for reliable sorting/comparison.
    """
    rating_by_time = {(r.get("time") or r.get("startsAt")): r for r in price_rating or []}
    merged = []
    for interval in price_info or []:
        ts = interval.get("startsAt")
        start_dt = dt_util.parse_datetime(ts) if ts else None
        merged_interval = {"start_time": ts, "start_dt": start_dt} if ts is not None else {"start_dt": None}
        for k, v in interval.items():
            if k == "startsAt":
                continue
            if k == "total":
                merged_interval["price"] = v
                merged_interval["price_minor"] = round(v * 100, 2)
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
    # Always sort by start_dt (datetime), None values last
    merged.sort(key=lambda x: (x.get("start_dt") is None, x.get("start_dt")))
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


@dataclass
class IntervalContext:
    """
    Context for selecting price intervals.

    Attributes:
        merged: List of merged price and rating intervals for the selected day.
        all_ratings: All rating intervals for the selected day.
        coordinator: Data update coordinator for the integration.
        day: The day being queried ('yesterday', 'today', or 'tomorrow').
        now: The datetime used for interval selection.
        is_simulated: Whether the time is simulated (from user input) or real.

    """

    merged: list[dict]
    all_ratings: list[dict]
    coordinator: Any
    day: str
    now: datetime
    is_simulated: bool


def _select_intervals(ctx: IntervalContext) -> tuple[Any, Any, Any]:
    """
    Select previous, current, and next intervals for the given day and time.

    If is_simulated is True, always calculate previous/current/next for all days, but:
    - For 'yesterday', never fetch previous from the day before yesterday.
    - For 'tomorrow', never fetch next from the day after tomorrow.
    If is_simulated is False, previous/current/next are None for 'yesterday' and 'tomorrow'.
    """
    merged = ctx.merged
    all_ratings = ctx.all_ratings
    coordinator = ctx.coordinator
    day = ctx.day
    now = ctx.now
    is_simulated = ctx.is_simulated

    if not merged or (not is_simulated and day in ("yesterday", "tomorrow")):
        return None, None, None

    idx = None
    cmp_now = dt_util.as_local(now) if now.tzinfo is None else now
    for i, interval in enumerate(merged):
        start_dt = interval.get("start_dt")
        if not start_dt:
            continue
        if start_dt.tzinfo is None:
            start_dt = dt_util.as_local(start_dt)
        if start_dt <= cmp_now:
            idx = i
        elif start_dt > cmp_now:
            break

    previous_interval = merged[idx - 1] if idx is not None and idx > 0 else None
    current_interval = merged[idx] if idx is not None else None
    next_interval = (
        merged[idx + 1] if idx is not None and idx + 1 < len(merged) else (merged[0] if idx is None else None)
    )

    if day == "today":
        if idx == 0:
            previous_interval = _find_previous_interval(merged, all_ratings, coordinator, day)
        if idx == len(merged) - 1:
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


def _get_price_stats(merged: list[dict]) -> PriceStats:
    """Calculate average, min, and max price and their intervals from merged data."""
    if merged:
        price_sum = sum(float(interval.get("price", 0)) for interval in merged if "price" in interval)
        price_avg = round(price_sum / len(merged), 4)
    else:
        price_avg = 0
    price_min, price_min_start_time, price_min_end_time = get_price_stat(merged, "min")
    price_max, price_max_start_time, price_max_end_time = get_price_stat(merged, "max")
    return PriceStats(
        price_avg=price_avg,
        price_min=price_min,
        price_min_start_time=price_min_start_time,
        price_min_end_time=price_min_end_time,
        price_max=price_max,
        price_max_start_time=price_max_start_time,
        price_max_end_time=price_max_end_time,
        stats_merged=merged,
    )


@dataclass
class PriceStats:
    """Encapsulates price statistics and their intervals for the Tibber Prices service."""

    price_avg: float
    price_min: float
    price_min_start_time: str | None
    price_min_end_time: str | None
    price_max: float
    price_max_start_time: str | None
    price_max_end_time: str | None
    stats_merged: list[dict]


@dataclass
class PriceResponseContext:
    """Context for building the price response."""

    price_stats: PriceStats
    previous_interval: dict | None
    current_interval: dict | None
    next_interval: dict | None
    currency: str | None
    rating_threshold_percentages: Any
    merged: list[dict]


def _build_price_response(ctx: PriceResponseContext) -> dict[str, Any]:
    """Build the response dictionary for the price service."""
    price_stats = ctx.price_stats
    return {
        "average": {
            "start_time": price_stats.stats_merged[0].get("start_time") if price_stats.stats_merged else None,
            "end_time": price_stats.stats_merged[0].get("end_time") if price_stats.stats_merged else None,
            "price": price_stats.price_avg,
            "price_minor": round(price_stats.price_avg * 100, 2),
        },
        "minimum": {
            "start_time": price_stats.price_min_start_time,
            "end_time": price_stats.price_min_end_time,
            "price": price_stats.price_min,
            "price_minor": round(price_stats.price_min * 100, 2),
        },
        "maximum": {
            "start_time": price_stats.price_max_start_time,
            "end_time": price_stats.price_max_end_time,
            "price": price_stats.price_max,
            "price_minor": round(price_stats.price_max * 100, 2),
        },
        "previous": ctx.previous_interval,
        "current": ctx.current_interval,
        "next": ctx.next_interval,
        "currency": ctx.currency,
        "rating_threshold_%": ctx.rating_threshold_percentages,
        "interval_count": len(ctx.merged),
        "intervals": ctx.merged,
    }


async def _get_price(call: ServiceCall) -> dict[str, Any]:
    """
    Return merged priceInfo and priceRating for the requested day and config entry.

    If 'time' is provided, it must be in HH:mm or HH:mm:ss format and is combined with the selected 'day'.
    This only affects 'previous', 'current', and 'next' fields, not the 'prices' list.
    If 'time' is not provided, the current time is used for all days.
    If 'day' is not provided, the prices list will include today and tomorrow, but stats and interval
    selection are only for today.
    """
    hass = call.hass
    entry_id_raw = call.data.get(ATTR_ENTRY_ID)
    if entry_id_raw is None:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="missing_entry_id")
    entry_id: str = str(entry_id_raw)
    time_value = call.data.get(ATTR_TIME)
    explicit_day = ATTR_DAY in call.data
    day = call.data.get(ATTR_DAY)

    entry, coordinator, data = _get_entry_and_data(hass, entry_id)
    price_info_data, price_rating_data, hourly_ratings, rating_threshold_percentages, currency = _extract_price_data(
        data
    )

    price_info_by_day, day_prefixes, ratings_by_day = _prepare_day_structures(price_info_data, hourly_ratings)

    (
        merged,
        stats_merged,
        interval_selection_merged,
        interval_selection_ratings,
        interval_selection_day,
    ) = _select_merge_strategy(
        explicit_day=explicit_day,
        day=day if day is not None else "today",
        price_info_by_day=price_info_by_day,
        ratings_by_day=ratings_by_day,
    )

    annotate_intervals_with_times(
        merged,
        price_info_by_day,
        interval_selection_day,
    )

    price_stats = _get_price_stats(stats_merged)

    now, is_simulated = _determine_now_and_simulation(time_value, interval_selection_merged)

    ctx = IntervalContext(
        merged=interval_selection_merged,
        all_ratings=interval_selection_ratings,
        coordinator=coordinator,
        day=interval_selection_day,
        now=now,
        is_simulated=is_simulated,
    )
    previous_interval, current_interval, next_interval = _select_intervals(ctx)

    for interval in merged:
        if "previous_end_time" in interval:
            del interval["previous_end_time"]

    response_ctx = PriceResponseContext(
        price_stats=price_stats,
        previous_interval=previous_interval,
        current_interval=current_interval,
        next_interval=next_interval,
        currency=currency,
        rating_threshold_percentages=rating_threshold_percentages,
        merged=merged,
    )

    return _build_price_response(response_ctx)


def _get_entry_and_data(hass: HomeAssistant, entry_id: str) -> tuple[Any, Any, dict]:
    """Validate entry and extract coordinator and data."""
    if not entry_id:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="missing_entry_id")
    entry = next((e for e in hass.config_entries.async_entries(DOMAIN) if e.entry_id == entry_id), None)
    if not entry or not hasattr(entry, "runtime_data") or not entry.runtime_data:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="invalid_entry_id")
    coordinator = entry.runtime_data.coordinator
    data = coordinator.data or {}
    return entry, coordinator, data


def _extract_price_data(data: dict) -> tuple[dict, dict, list, Any, Any]:
    """Extract price info and rating data from coordinator data."""
    price_info_data = data.get("priceInfo") or {}
    price_rating_data = data.get("priceRating") or {}
    hourly_ratings = price_rating_data.get("hourly") or []
    rating_threshold_percentages = price_rating_data.get("thresholdPercentages")
    currency = price_rating_data.get("currency")
    return price_info_data, price_rating_data, hourly_ratings, rating_threshold_percentages, currency


def _prepare_day_structures(price_info_data: dict, hourly_ratings: list) -> tuple[dict, dict, dict]:
    """Prepare price info, day prefixes, and ratings by day."""
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
    return price_info_by_day, day_prefixes, ratings_by_day


def _select_merge_strategy(
    *,
    explicit_day: bool,
    day: str,
    price_info_by_day: dict,
    ratings_by_day: dict,
) -> tuple[list, list, list, list, str]:
    """Select merging strategy for intervals and stats."""
    if not explicit_day:
        merged_today = _merge_priceinfo_and_pricerating(price_info_by_day["today"], ratings_by_day["today"])
        merged_tomorrow = _merge_priceinfo_and_pricerating(price_info_by_day["tomorrow"], ratings_by_day["tomorrow"])
        merged = merged_today + merged_tomorrow
        stats_merged = merged_today
        interval_selection_merged = merged_today
        interval_selection_ratings = ratings_by_day["today"]
        interval_selection_day = "today"
    else:
        day_key = day if day in ("yesterday", "today", "tomorrow") else "today"
        merged = _merge_priceinfo_and_pricerating(price_info_by_day[day_key], ratings_by_day[day_key])
        stats_merged = merged
        interval_selection_merged = merged
        interval_selection_ratings = ratings_by_day[day_key]
        interval_selection_day = day_key
    return (
        merged,
        stats_merged,
        interval_selection_merged,
        interval_selection_ratings,
        interval_selection_day,
    )


def _determine_now_and_simulation(
    time_value: str | None, interval_selection_merged: list[dict]
) -> tuple[datetime, bool]:
    """Determine the 'now' datetime and simulation flag."""
    is_simulated = False
    if time_value:
        if not interval_selection_merged or not interval_selection_merged[0].get("start_time"):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_data_for_day",
            )
        day_prefix = interval_selection_merged[0]["start_time"].split("T")[0]
        dt_str = f"{day_prefix}T{time_value}"
        try:
            now = datetime.fromisoformat(dt_str)
        except ValueError as exc:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_time",
                translation_placeholders={"error": str(exc)},
            ) from exc
        is_simulated = True
    elif not interval_selection_merged or not interval_selection_merged[0].get("start_time"):
        now = dt_util.now().replace(second=0, microsecond=0)
    else:
        day_prefix = interval_selection_merged[0]["start_time"].split("T")[0]
        current_time = dt_util.now().time().replace(second=0, microsecond=0)
        dt_str = f"{day_prefix}T{current_time.isoformat()}"
        try:
            now = datetime.fromisoformat(dt_str)
        except ValueError:
            now = dt_util.now().replace(second=0, microsecond=0)
    return now, is_simulated


DAY_PREFIX_LENGTH = 10


def _get_day_prefixes(day_info: list[dict]) -> list[str]:
    """Return a list of unique day prefixes from the intervals' start datetimes."""
    prefixes = set()
    for interval in day_info:
        dt_str = interval.get("time") or interval.get("startsAt")
        if not dt_str:
            continue
        start_dt = dt_util.parse_datetime(dt_str)
        if start_dt:
            prefixes.add(start_dt.date().isoformat())
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
