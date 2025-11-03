"""Services for Tibber Prices integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from homeassistant.util import dt as dt_util

from .api import (
    TibberPricesApiClientAuthenticationError,
    TibberPricesApiClientCommunicationError,
    TibberPricesApiClientError,
)
from .const import (
    DOMAIN,
    PRICE_LEVEL_CHEAP,
    PRICE_LEVEL_EXPENSIVE,
    PRICE_LEVEL_NORMAL,
    PRICE_LEVEL_VERY_CHEAP,
    PRICE_LEVEL_VERY_EXPENSIVE,
    PRICE_RATING_HIGH,
    PRICE_RATING_LOW,
    PRICE_RATING_NORMAL,
    get_price_level_translation,
)

PRICE_SERVICE_NAME = "get_price"
APEXCHARTS_DATA_SERVICE_NAME = "get_apexcharts_data"
APEXCHARTS_YAML_SERVICE_NAME = "get_apexcharts_yaml"
REFRESH_USER_DATA_SERVICE_NAME = "refresh_user_data"
ATTR_DAY: Final = "day"
ATTR_ENTRY_ID: Final = "entry_id"
ATTR_TIME: Final = "time"

PRICE_SERVICE_SCHEMA: Final = vol.Schema(
    {
        vol.Required(ATTR_ENTRY_ID): str,
        vol.Optional(ATTR_DAY): vol.In(["yesterday", "today", "tomorrow"]),
        vol.Optional(ATTR_TIME): vol.Match(r"^(\d{2}:\d{2}(:\d{2})?)$"),  # HH:mm or HH:mm:ss
    }
)

APEXCHARTS_DATA_SERVICE_SCHEMA: Final = vol.Schema(
    {
        vol.Required("entity_id"): str,
        vol.Required("day"): vol.In(["yesterday", "today", "tomorrow"]),
        vol.Required("level_type"): vol.In(["level", "rating_level"]),
        vol.Required("level_key"): vol.In(
            [
                PRICE_LEVEL_CHEAP,
                PRICE_LEVEL_EXPENSIVE,
                PRICE_LEVEL_NORMAL,
                PRICE_LEVEL_VERY_CHEAP,
                PRICE_LEVEL_VERY_EXPENSIVE,
                PRICE_RATING_HIGH,
                PRICE_RATING_LOW,
                PRICE_RATING_NORMAL,
            ]
        ),
    }
)

APEXCHARTS_SERVICE_SCHEMA: Final = vol.Schema(
    {
        vol.Required("entity_id"): str,
        vol.Optional("day", default="today"): vol.In(["yesterday", "today", "tomorrow"]),
    }
)

REFRESH_USER_DATA_SERVICE_SCHEMA: Final = vol.Schema(
    {
        vol.Required(ATTR_ENTRY_ID): str,
    }
)

# --- Entry point: Service handler ---


async def _get_price(call: ServiceCall) -> dict[str, Any]:
    """Return price information for the requested day and config entry."""
    hass = call.hass
    entry_id_raw = call.data.get(ATTR_ENTRY_ID)
    if entry_id_raw is None:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="missing_entry_id")
    entry_id: str = str(entry_id_raw)
    time_value = call.data.get(ATTR_TIME)
    explicit_day = ATTR_DAY in call.data
    day = call.data.get(ATTR_DAY, "today")

    _, coordinator, _ = _get_entry_and_data(hass, entry_id)
    price_info_data, currency = _extract_price_data(coordinator.data)

    # Determine which days to include
    if explicit_day:
        day_key = day if day in ("yesterday", "today", "tomorrow") else "today"
        prices_raw = price_info_data.get(day_key, [])
        stats_raw = prices_raw
    else:
        # No explicit day: include today + tomorrow for prices, use today for stats
        today_raw = price_info_data.get("today", [])
        tomorrow_raw = price_info_data.get("tomorrow", [])
        prices_raw = today_raw + tomorrow_raw
        stats_raw = today_raw
        day_key = "today"

    # Transform to service format
    prices_transformed = _transform_price_intervals(prices_raw)
    stats_transformed = _transform_price_intervals(stats_raw)

    # Calculate stats
    price_stats = _get_price_stats(stats_transformed)

    # Determine now and simulation flag
    now, is_simulated = _determine_now_and_simulation(time_value, stats_transformed)

    # Select intervals
    previous_interval, current_interval, next_interval = _select_intervals(
        stats_transformed, coordinator, day_key, now, simulated=is_simulated
    )

    # Add end_time to intervals
    _annotate_end_times(prices_transformed, price_info_data, day_key)

    # Clean up temp fields from all intervals
    for interval in prices_transformed:
        if "start_dt" in interval:
            del interval["start_dt"]

    # Also clean up from selected intervals
    if previous_interval and "start_dt" in previous_interval:
        del previous_interval["start_dt"]
    if current_interval and "start_dt" in current_interval:
        del current_interval["start_dt"]
    if next_interval and "start_dt" in next_interval:
        del next_interval["start_dt"]

    response_ctx = PriceResponseContext(
        price_stats=price_stats,
        previous_interval=previous_interval,
        current_interval=current_interval,
        next_interval=next_interval,
        currency=currency,
        merged=prices_transformed,
    )

    return _build_price_response(response_ctx)


async def _get_entry_id_from_entity_id(hass: HomeAssistant, entity_id: str) -> str | None:
    """Return the config entry_id for a given entity_id."""
    entity_registry = async_get_entity_registry(hass)
    entry = entity_registry.async_get(entity_id)
    if entry is not None:
        return entry.config_entry_id
    return None


async def _get_apexcharts_data(call: ServiceCall) -> dict[str, Any]:
    """Return points for ApexCharts for a single level type (e.g., LOW, NORMAL, HIGH, etc)."""
    entity_id = call.data.get("entity_id", "sensor.tibber_price_today")
    day = call.data.get("day", "today")
    level_type = call.data.get("level_type", "rating_level")
    level_key = call.data.get("level_key")
    hass = call.hass

    # Get entry ID and verify it exists
    entry_id = await _get_entry_id_from_entity_id(hass, entity_id)
    if not entry_id:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="invalid_entity_id")

    _, coordinator, _ = _get_entry_and_data(hass, entry_id)

    # Get entries based on level_type
    entries = _get_apexcharts_entries(coordinator, day, level_type)
    if not entries:
        return {"points": []}

    # Ensure level_key is a string
    if level_key is None:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="missing_level_key")

    # Generate points for the chart
    points = _generate_apexcharts_points(entries, str(level_key))
    return {"points": points}


def _get_apexcharts_entries(coordinator: Any, day: str, _: str) -> list[dict]:
    """Get the appropriate entries for ApexCharts based on day."""
    # Price info is already enriched with difference and rating_level from coordinator
    price_info = coordinator.data.get("priceInfo", {})
    day_info = price_info.get(day, [])
    return day_info if day_info else []


def _generate_apexcharts_points(entries: list[dict], level_key: str) -> list:
    """Generate data points for ApexCharts based on the entries and level key."""
    points = []
    for i in range(len(entries) - 1):
        p = entries[i]
        if p.get("level") != level_key:
            continue
        points.append([p.get("time") or p.get("startsAt"), round((p.get("total") or 0) * 100, 2)])

    # Add a final point with null value if there are any points
    if points:
        points.append([points[-1][0], None])

    return points


async def _get_apexcharts_yaml(call: ServiceCall) -> dict[str, Any]:
    """Return a YAML snippet for an ApexCharts card using the get_apexcharts_data service for each level."""
    entity_id = call.data.get("entity_id", "sensor.tibber_price_today")
    day = call.data.get("day", "today")
    level_type = call.data.get("level_type", "rating_level")
    if level_type == "rating_level":
        series_levels = [
            (PRICE_RATING_LOW, "#2ecc71"),
            (PRICE_RATING_NORMAL, "#f1c40f"),
            (PRICE_RATING_HIGH, "#e74c3c"),
        ]
    else:
        series_levels = [
            (PRICE_LEVEL_VERY_CHEAP, "#2ecc71"),
            (PRICE_LEVEL_CHEAP, "#27ae60"),
            (PRICE_LEVEL_NORMAL, "#f1c40f"),
            (PRICE_LEVEL_EXPENSIVE, "#e67e22"),
            (PRICE_LEVEL_VERY_EXPENSIVE, "#e74c3c"),
        ]
    series = []
    for level_key, color in series_levels:
        name = get_price_level_translation(level_key, "en") or level_key
        data_generator = (
            f"const data = await hass.callService('tibber_prices', 'get_apexcharts_data', "
            f"{{ entity_id: '{entity_id}', day: '{day}', level_type: '{level_type}', level_key: '{level_key}' }});\n"
            f"return data.points;"
        )
        series.append(
            {
                "entity": entity_id,
                "name": name,
                "type": "area",
                "color": color,
                "yaxis_id": "price",
                "show": {"extremas": level_key != "NORMAL"},
                "data_generator": data_generator,
            }
        )
    title = "Preisphasen Tagesverlauf" if level_type == "rating" else "Preisniveau"
    return {
        "type": "custom:apexcharts-card",
        "update_interval": "5m",
        "span": {"start": "day"},
        "header": {
            "show": True,
            "title": title,
            "show_states": False,
        },
        "apex_config": {
            "stroke": {"curve": "stepline"},
            "fill": {"opacity": 0.4},
            "tooltip": {"x": {"format": "HH:mm"}},
            "legend": {"show": True},
        },
        "yaxis": [
            {"id": "price", "decimals": 0, "min": 0},
        ],
        "now": {"show": True, "color": "#8e24aa", "label": "🕒 LIVE"},
        "all_series_config": {"stroke_width": 1, "show": {"legend_value": False}},
        "series": series,
    }


async def _refresh_user_data(call: ServiceCall) -> dict[str, Any]:
    """Refresh user data for a specific config entry and return updated information."""
    entry_id = call.data.get(ATTR_ENTRY_ID)
    hass = call.hass

    if not entry_id:
        return {
            "success": False,
            "message": "Entry ID is required",
        }

    # Get the entry and coordinator
    try:
        _, coordinator, _ = _get_entry_and_data(hass, entry_id)
    except ServiceValidationError as ex:
        return {
            "success": False,
            "message": f"Invalid entry ID: {ex}",
        }

    # Force refresh user data using the public method
    try:
        updated = await coordinator.refresh_user_data()
    except (
        TibberPricesApiClientAuthenticationError,
        TibberPricesApiClientCommunicationError,
        TibberPricesApiClientError,
    ) as ex:
        return {
            "success": False,
            "message": f"API error refreshing user data: {ex!s}",
        }
    else:
        if updated:
            user_profile = coordinator.get_user_profile()
            homes = coordinator.get_user_homes()

            return {
                "success": True,
                "message": "User data refreshed successfully",
                "user_profile": user_profile,
                "homes_count": len(homes),
                "homes": homes,
                "last_updated": user_profile.get("last_updated"),
            }
        return {
            "success": False,
            "message": "User data was already up to date",
        }


# --- Helpers ---


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


def _extract_price_data(data: dict) -> tuple[dict, Any]:
    """Extract price info from enriched coordinator data."""
    price_info_data = data.get("priceInfo") or {}
    currency = price_info_data.get("currency")
    return price_info_data, currency


def _transform_price_intervals(price_info: list[dict]) -> list[dict]:
    """Transform priceInfo intervals to service output format."""
    result = []
    for interval in price_info or []:
        ts = interval.get("startsAt")
        start_dt = dt_util.parse_datetime(ts) if ts else None
        item = {"start_time": ts, "start_dt": start_dt} if ts else {"start_dt": None}

        for k, v in interval.items():
            if k == "startsAt":
                continue
            if k == "total":
                item["price"] = v
                item["price_minor"] = round(v * 100, 2)
            elif k not in ("energy", "tax"):
                item[k] = v

        result.append(item)

    # Sort by datetime
    result.sort(key=lambda x: (x.get("start_dt") is None, x.get("start_dt")))
    return result


def _annotate_end_times(merged: list[dict], price_info_by_day: dict, day: str) -> None:
    """Annotate merged intervals with end_time."""
    for idx, interval in enumerate(merged):
        # Default: next interval's start_time
        if idx + 1 < len(merged):
            interval["end_time"] = merged[idx + 1].get("start_time")
        # Last interval: look into next day's first interval
        else:
            next_day = "tomorrow" if day == "today" else (day if day == "tomorrow" else None)
            if next_day and price_info_by_day.get(next_day):
                first_of_next = price_info_by_day[next_day][0]
                interval["end_time"] = first_of_next.get("startsAt")
            else:
                interval["end_time"] = None


def _get_price_stats(merged: list[dict]) -> PriceStats:
    """Calculate average, min, and max price from merged data."""
    if merged:
        price_sum = sum(float(interval.get("price", 0)) for interval in merged if "price" in interval)
        price_avg = round(price_sum / len(merged), 4)
    else:
        price_avg = 0
    price_min, price_min_interval = _get_price_stat(merged, "min")
    price_max, price_max_interval = _get_price_stat(merged, "max")
    return PriceStats(
        price_avg=price_avg,
        price_min=price_min,
        price_min_start_time=price_min_interval.get("start_time") if price_min_interval else None,
        price_min_end_time=price_min_interval.get("end_time") if price_min_interval else None,
        price_max=price_max,
        price_max_start_time=price_max_interval.get("start_time") if price_max_interval else None,
        price_max_end_time=price_max_interval.get("end_time") if price_max_interval else None,
        price_min_interval=price_min_interval,
        price_max_interval=price_max_interval,
        stats_merged=merged,
    )


def _determine_now_and_simulation(
    time_value: str | None, interval_selection_merged: list[dict]
) -> tuple[datetime, bool]:
    """Determine the 'now' datetime and simulation flag."""
    is_simulated = False
    if time_value:
        if not interval_selection_merged or not interval_selection_merged[0].get("start_time"):
            now = dt_util.now().replace(second=0, microsecond=0)
            is_simulated = True
            return now, is_simulated
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
        is_simulated = True
    return now, is_simulated


def _select_intervals(  # noqa: PLR0912
    merged: list[dict], coordinator: Any, day: str, now: datetime, *, simulated: bool
) -> tuple[Any, Any, Any]:
    """Select previous, current, and next intervals for the given day and time."""
    if not merged or (not simulated and day in ("yesterday", "tomorrow")):
        return None, None, None

    # Find current interval by time
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

    # For today, try to fetch adjacent intervals from neighboring days
    if day == "today":
        if idx == 0 and previous_interval is None:
            yday_info = coordinator.data.get("priceInfo", {}).get("yesterday", [])
            if yday_info:
                yday_transformed = _transform_price_intervals(yday_info)
                if yday_transformed:
                    previous_interval = yday_transformed[-1]

        if idx == len(merged) - 1 and next_interval is None:
            tmrw_info = coordinator.data.get("priceInfo", {}).get("tomorrow", [])
            if tmrw_info:
                tmrw_transformed = _transform_price_intervals(tmrw_info)
                if tmrw_transformed:
                    next_interval = tmrw_transformed[0]

    return previous_interval, current_interval, next_interval


def _build_price_response(ctx: PriceResponseContext) -> dict[str, Any]:
    """Build the response dictionary for the price service."""
    price_stats = ctx.price_stats

    # Helper to clean internal fields from interval
    def clean_interval(interval: dict | None) -> dict | None:
        """Remove internal fields like start_dt from interval."""
        if not interval:
            return interval
        return {k: v for k, v in interval.items() if k != "start_dt"}

    # Build average interval (synthetic, using first interval as template)
    average_interval = {}
    if price_stats.stats_merged:
        first = price_stats.stats_merged[0]
        # Copy all attributes from first interval (excluding internal fields)
        for k in first:
            if k not in ("start_time", "end_time", "start_dt", "price", "price_minor"):
                average_interval[k] = first[k]

    return {
        "average": {
            **average_interval,
            "start_time": price_stats.stats_merged[0].get("start_time") if price_stats.stats_merged else None,
            "end_time": price_stats.stats_merged[0].get("end_time") if price_stats.stats_merged else None,
            "price": price_stats.price_avg,
            "price_minor": round(price_stats.price_avg * 100, 2),
        },
        "minimum": clean_interval(
            {
                **price_stats.price_min_interval,
                "price": price_stats.price_min,
                "price_minor": round(price_stats.price_min * 100, 2),
            }
        )
        if price_stats.price_min_interval
        else {
            "start_time": price_stats.price_min_start_time,
            "end_time": price_stats.price_min_end_time,
            "price": price_stats.price_min,
            "price_minor": round(price_stats.price_min * 100, 2),
        },
        "maximum": clean_interval(
            {
                **price_stats.price_max_interval,
                "price": price_stats.price_max,
                "price_minor": round(price_stats.price_max * 100, 2),
            }
        )
        if price_stats.price_max_interval
        else {
            "start_time": price_stats.price_max_start_time,
            "end_time": price_stats.price_max_end_time,
            "price": price_stats.price_max,
            "price_minor": round(price_stats.price_max * 100, 2),
        },
        "previous": clean_interval(ctx.previous_interval),
        "current": clean_interval(ctx.current_interval),
        "next": clean_interval(ctx.next_interval),
        "currency": ctx.currency,
        "interval_count": len(ctx.merged),
        "intervals": ctx.merged,
    }


def _get_price_stat(merged: list[dict], stat: str) -> tuple[float, dict | None]:
    """Return min or max price and its full interval from merged intervals."""
    if not merged:
        return 0, None
    values = [float(interval.get("price", 0)) for interval in merged if "price" in interval]
    if not values:
        return 0, None
    val = min(values) if stat == "min" else max(values)
    interval = next((interval for interval in merged if interval.get("price") == val), None)
    return val, interval


# --- Dataclasses ---


@dataclass
class PriceStats:
    """Encapsulates price statistics and their intervals for the Tibber Prices service."""

    price_avg: float
    price_min: float
    price_min_start_time: str | None
    price_min_end_time: str | None
    price_min_interval: dict | None
    price_max: float
    price_max_start_time: str | None
    price_max_end_time: str | None
    price_max_interval: dict | None
    stats_merged: list[dict]


@dataclass
class PriceResponseContext:
    """Context for building the price response."""

    price_stats: PriceStats
    previous_interval: dict | None
    current_interval: dict | None
    next_interval: dict | None
    currency: str | None
    merged: list[dict]


# --- Service registration ---


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Tibber Prices integration."""
    hass.services.async_register(
        DOMAIN,
        PRICE_SERVICE_NAME,
        _get_price,
        schema=PRICE_SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        APEXCHARTS_DATA_SERVICE_NAME,
        _get_apexcharts_data,
        schema=APEXCHARTS_DATA_SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        APEXCHARTS_YAML_SERVICE_NAME,
        _get_apexcharts_yaml,
        schema=APEXCHARTS_SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        REFRESH_USER_DATA_SERVICE_NAME,
        _refresh_user_data,
        schema=REFRESH_USER_DATA_SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
