"""Interval attribute builders for Tibber Prices sensors."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from weakref import WeakKeyDictionary

from custom_components.tibber_prices.const import (
    CHEAP_PRICE_LEVELS,
    CONF_AVERAGE_SENSOR_DISPLAY,
    DEFAULT_AVERAGE_SENSOR_DISPLAY,
    EXPENSIVE_PRICE_LEVELS,
    PRICE_LEVEL_MAPPING,
    PRICE_RATING_MAPPING,
    format_price_unit_base,
    format_price_unit_subunit,
    get_display_precision,
    get_display_unit_factor,
)
from custom_components.tibber_prices.coordinator.helpers import get_intervals_for_day_offsets
from custom_components.tibber_prices.entity_utils import add_icon_color_attribute, get_rolling_hour_window
from custom_components.tibber_prices.sensor.definitions import ROLLING_HOUR_SENSOR_WINDOWS
from custom_components.tibber_prices.sensor.helpers import aggregate_average_data, aggregate_level_data
from custom_components.tibber_prices.utils.average import clock_hour_bounds, clock_hour_key
from custom_components.tibber_prices.utils.day_outlook import (
    DAY_PART_HOURS,
    TibberPricesOutlookBlock,
    build_day_outlook,
    build_day_part_outlook,
    build_hour_outlook,
    known_starts,
)
from custom_components.tibber_prices.utils.price import (
    calculate_volatility_with_cv,
    find_level_run_times,
    find_price_data_for_interval,
    get_volatility_thresholds,
)

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator.core import TibberPricesDataUpdateCoordinator
    from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService
    from custom_components.tibber_prices.data import TibberPricesConfigEntry

from .helpers import add_alternate_average_attribute
from .metadata import get_current_interval_data

QUARTER = timedelta(minutes=15)
# The quarter-hour series starts at the latest at yesterday's midnight: a night still running
# (from 22:00) shows whole in its details, and the chart card's two days without tomorrow's
# prices are yesterday and today
OUTLOOK_QUARTERS_DAYS_BACK = timedelta(days=1)


def _get_interval_data_for_attributes(
    key: str,
    coordinator: TibberPricesDataUpdateCoordinator,
    attributes: dict,
    *,
    time: TibberPricesTimeService,
) -> dict | None:
    """
    Get interval data and set timestamp based on sensor type.

    Refactored to reduce branch complexity in main function.

    Args:
        key: The sensor entity key
        coordinator: The data update coordinator
        attributes: Attributes dict to update with timestamp if needed
        time: TibberPricesTimeService instance

    Returns:
        Interval data if found, None otherwise

    """
    now = time.now()

    # Current/next price sensors - override timestamp with interval's startsAt
    next_sensors = ["next_interval_price", "next_interval_price_level", "next_interval_price_rating"]
    prev_sensors = ["previous_interval_price", "previous_interval_price_level", "previous_interval_price_rating"]
    next_hour = ["next_hour_average_price", "next_hour_price_level", "next_hour_price_rating"]
    curr_interval = ["current_interval_price", "current_interval_price_base"]
    curr_hour = ["current_hour_average_price", "current_hour_price_level", "current_hour_price_rating"]

    if key in next_sensors:
        target_time = time.get_next_interval_start()
        interval_data = find_price_data_for_interval(coordinator.data, target_time, time=time)
        if interval_data:
            attributes["timestamp"] = interval_data["startsAt"]
        return interval_data

    if key in prev_sensors:
        target_time = time.get_interval_offset_time(-1)
        interval_data = find_price_data_for_interval(coordinator.data, target_time, time=time)
        if interval_data:
            attributes["timestamp"] = interval_data["startsAt"]
        return interval_data

    if key in next_hour:
        target_time = now + timedelta(hours=1)
        interval_data = find_price_data_for_interval(coordinator.data, target_time, time=time)
        if interval_data:
            attributes["timestamp"] = interval_data["startsAt"]
        return interval_data

    # Current interval sensors (both variants)
    if key in curr_interval:
        interval_data = get_current_interval_data(coordinator, time=time)
        if interval_data and "startsAt" in interval_data:
            attributes["timestamp"] = interval_data["startsAt"]
        return interval_data

    # Current hour sensors - keep default timestamp
    if key in curr_hour:
        return get_current_interval_data(coordinator, time=time)

    return None


ROLLING_HOUR_OFFSETS = {key: hour_offset for key, (hour_offset, _) in ROLLING_HOUR_SENSOR_WINDOWS.items()}


def _add_rolling_window_attributes(
    attributes: dict,
    all_prices: list[dict],
    hour_offset: int,
    *,
    time: TibberPricesTimeService,
) -> None:
    """
    Add window_start/window_end: the span a rolling hour value is calculated from.

    The rolling hour is centered on the current interval (2 before + current + 2 after),
    not the clock hour, so users need to see which 75 minutes it covers.

    Args:
        attributes: Dictionary to add attributes to
        all_prices: Price intervals in chronological order (yesterday, today, tomorrow)
        hour_offset: 0 (current hour), 1 (next hour)
        time: TibberPricesTimeService instance (required)

    """
    window = get_rolling_hour_window(all_prices, time.now(), hour_offset, time=time)
    if not window:
        return
    first, last = time.get_interval_time(window[0]), time.get_interval_time(window[-1])
    if first is None or last is None:
        return
    attributes["window_start"] = first.isoformat()
    attributes["window_end"] = (last + time.get_interval_duration()).isoformat()


def _add_clock_hour_attributes(
    attributes: dict,
    all_prices: list[dict],
    hour_offset: int,
    *,
    time: TibberPricesTimeService,
    config_entry: TibberPricesConfigEntry,
) -> None:
    """
    Add the average of the clock hour (:00-:59), like the Tibber app shows it.

    The sensor state stays the rolling hour (smoother, no jump at the full hour); these
    attributes give automations the clock hour value without an extra entity.

    Args:
        attributes: Dictionary to add attributes to
        all_prices: Price intervals (yesterday, today, tomorrow)
        hour_offset: 0 (clock hour containing now), 1 (next clock hour)
        time: TibberPricesTimeService instance (required)
        config_entry: Config entry for display unit and precision

    """
    hour_start, hour_end = clock_hour_bounds(time.get_current_interval_start(), hour_offset)
    target = clock_hour_key(hour_start)
    hour_intervals = [
        interval
        for interval in all_prices
        if (starts_at := time.get_interval_time(interval)) is not None and clock_hour_key(starts_at) == target
    ]
    mean, median = aggregate_average_data(hour_intervals, config_entry)
    if mean is None:
        return
    attributes["clock_hour_start"] = hour_start.isoformat()
    attributes["clock_hour_end"] = hour_end.isoformat()
    attributes["clock_hour_price_mean"] = mean
    attributes["clock_hour_price_median"] = median


# The last outlook built per coordinator, with what it was built from: the attributes are
# read on every state write of the current price sensor, while their inputs change only with
# new data, new options or the next quarter hour
_OUTLOOK_CACHE: WeakKeyDictionary[Any, tuple[tuple, dict[str, Any]]] = WeakKeyDictionary()


def _add_outlook_attributes(
    attributes: dict,
    coordinator: TibberPricesDataUpdateCoordinator,
    *,
    time: TibberPricesTimeService,
    config_entry: TibberPricesConfigEntry,
) -> None:
    """Add the price outlook (see _build_outlook_attributes), built again only when its inputs change."""
    data = coordinator.data or {}
    # The objects themselves, compared by identity (never by content: they're large): new data
    # and new options are new objects, and a list replaced inside the data (a debug action)
    # counts as new too. Then the quarter hour, by value
    objects = (data, data.get("priceInfo"), data.get("pricePeriods"), config_entry.options)
    now = time.get_current_interval_start()
    cached = _OUTLOOK_CACHE.get(coordinator)
    if cached is not None:
        (cached_objects, cached_now), outlook = cached
        if cached_now == now and all(a is b for a, b in zip(cached_objects, objects, strict=True)):
            attributes.update(outlook)
            return
    outlook = _build_outlook_attributes(coordinator, time=time, config_entry=config_entry)
    _OUTLOOK_CACHE[coordinator] = ((objects, now), outlook)
    attributes.update(outlook)


def _build_outlook_attributes(
    coordinator: TibberPricesDataUpdateCoordinator,
    *,
    time: TibberPricesTimeService,
    config_entry: TibberPricesConfigEntry,
) -> dict[str, Any]:
    """
    Return the price outlook shaped like a weather forecast: clock hours and parts of the day.

    `outlook_hours` runs from one hour back to the end of the known prices, `outlook_day_parts` from the part
    of the day running now (morning, day, evening, night) as far as prices are known,
    `outlook_days` covers today and tomorrow (once complete) with their volatility, when the
    day's lowest and highest price occur, and the day's reference price (median or mean, as
    set for the average sensors).
    Each entry has its span, average, lowest and highest price (display unit) and the
    aggregated level.
    """
    # From the day before yesterday: the strips reach back into yesterday, and the night that
    # began the day before yesterday at 22:00 is shown whole (the coordinator keeps that day)
    all_prices = get_intervals_for_day_offsets(coordinator.data, [-2, -1, 0, 1])
    now = time.get_current_interval_start()

    factor = get_display_unit_factor(config_entry)
    precision = get_display_precision(config_entry)
    options = config_entry.options
    # Same thresholds as the volatility sensors, so a day here never disagrees with them
    volatility_thresholds = get_volatility_thresholds(options)

    # The day's reference price follows the average sensors' setting (median or mean), so a
    # dashboard's "above or below the day" matches the ⌀ Price Today sensor
    reference = options.get(CONF_AVERAGE_SENSOR_DISPLAY, DEFAULT_AVERAGE_SENSOR_DISPLAY)

    def reference_of(mean: float | None, median: float | None) -> float | None:
        return median if reference == "median" else mean

    def day_entry(block: TibberPricesOutlookBlock) -> dict[str, Any]:
        item = entry(block)
        priced = [interval for interval in block.intervals if "total" in interval]
        volatility, _ = calculate_volatility_with_cv([float(i["total"]) for i in priced], **volatility_thresholds)
        # When the day's lowest and highest price occur (first quarter hour on a tie)
        lowest = min(priced, key=lambda interval: float(interval["total"]))
        highest = max(priced, key=lambda interval: float(interval["total"]))
        return {
            "date": block.start.date().isoformat(),
            **item,
            "price_min_at": _interval_start_iso(lowest, time),
            "price_max_at": _interval_start_iso(highest, time),
            "price_reference": reference_of(item["price_mean"], item["price_median"]),
            "reference": reference,
            "volatility": volatility.lower(),
        }

    def entry(block: TibberPricesOutlookBlock) -> dict[str, Any]:
        """Return a block's entry."""
        mean, median = aggregate_average_data(block.intervals, config_entry)
        prices = [float(interval["total"]) for interval in block.intervals if "total" in interval]
        item: dict[str, Any] = {"start": block.start.isoformat(), "end": block.end.isoformat()}
        if block.part:
            item["part"] = block.part
            item["complete"] = block.complete
        item["price_mean"] = mean
        # Markers in cards always use the median: it shows where prices lean within the spread
        item["price_median"] = median
        # The spread inside the block, like low and high of a weather forecast day
        item["price_min"] = round(min(prices) * factor, precision) if prices else None
        item["price_max"] = round(max(prices) * factor, precision) if prices else None
        item["level"] = aggregate_level_data(block.intervals)
        return item

    attributes: dict[str, Any] = {}
    # Both units, so a card can show base or subunit currency whatever the sensors use
    currency = (coordinator.data or {}).get("currency")
    attributes["outlook_units"] = {
        "display": "subunit" if factor > 1 else "base",
        "base": format_price_unit_base(currency),
        "subunit": format_price_unit_subunit(currency),
    }
    # When each part of the day begins and ends, so cards needn't hard-code it
    attributes["outlook_day_part_hours"] = DAY_PART_HOURS
    # The priced intervals in order, worked out once for the days, the parts and the quarters
    known = known_starts(all_prices, time.get_interval_time)
    hour_blocks = build_hour_outlook(all_prices, now, time.get_interval_time)
    attributes["outlook_hours"] = [entry(b) for b in hour_blocks]
    days = build_day_outlook(all_prices, now, time.get_interval_time, known=known)
    attributes["outlook_days"] = [day_entry(b) for b in days]
    # The parts of the day cover what the hours do: cards scroll both back as far
    part_blocks = build_day_part_outlook(
        all_prices, now, time.get_interval_time, since=hour_blocks[0].start if hour_blocks else None, known=known
    )
    attributes["outlook_day_parts"] = [entry(b) for b in part_blocks]
    # Yesterday's averages and extremes: after midnight the hour strip still shows the last hour
    # of yesterday, and its dashed line is yesterday's (the part of the day strip starts with a
    # night that began yesterday, too); a chart reaching back into it marks yesterday's lowest
    # and highest price where they fall in view, of the whole day, not of the piece shown
    yesterday = (now - timedelta(days=1)).date()
    yesterday_intervals = get_intervals_for_day_offsets(coordinator.data, [-1])
    mean, median = aggregate_average_data(yesterday_intervals, config_entry)
    priced = [interval for interval in yesterday_intervals if "total" in interval]
    lowest = min(priced, key=lambda interval: float(interval["total"])) if priced else None
    highest = max(priced, key=lambda interval: float(interval["total"])) if priced else None
    attributes["outlook_yesterday"] = (
        {
            "date": yesterday.isoformat(),
            "price_mean": mean,
            "price_median": median,
            "price_reference": reference_of(mean, median),
            "price_min": round(float(lowest["total"]) * factor, precision) if lowest else None,
            "price_max": round(float(highest["total"]) * factor, precision) if highest else None,
            "price_min_at": _interval_start_iso(lowest, time) if lowest else None,
            "price_max_at": _interval_start_iso(highest, time) if highest else None,
        }
        if mean is not None
        else None
    )
    # Every quarter hour from where the strips begin (at the latest yesterday's midnight), for
    # zooming into an hour, a part of the day or a day, and for the chart card: compact (start, then one price and level
    # per quarter hour, None where unknown), so it costs little next to the other attributes
    # (The first part of the day may begin before the first hour: a night from 22:00)
    starts = [blocks[0].start.astimezone(UTC) for blocks in (hour_blocks, part_blocks) if blocks]
    starts.append((time.start_of_local_day(now) - OUTLOOK_QUARTERS_DAYS_BACK).astimezone(UTC))
    since = min(starts)
    attributes["outlook_quarters"] = _quarter_series(known, now, time, factor, precision, since=since)
    # The best and peak price periods that ended before today, as far back as the quarters reach:
    # the period sensors list only today's and tomorrow's, so cards can mark yesterday's too
    attributes["outlook_past_periods"] = _past_periods(coordinator.data, time, since=since)
    return attributes


def _quarter_series(
    sorted_known: tuple[list[tuple[datetime, dict[str, Any]]], datetime] | None,
    now: datetime,
    time: TibberPricesTimeService,
    factor: float,
    precision: int,
    *,
    since: datetime | None = None,
) -> dict[str, Any] | None:
    """
    Return the quarter-hour prices from `since` on.

    `since` is where the strips begin (they reach back into yesterday), at the latest
    yesterday's midnight: each hour and part of the day they show can be zoomed into, and the
    chart card can draw yesterday.

    {"start": ISO time, "minutes": 15, "prices": [...], "levels": [...]}; position i is
    start + i * 15 minutes (counted in real time, so clock changes need no special case).
    `sorted_known` is known_starts() of the prices: sorted in UTC like the parts of the day (the
    repeated hour when clocks go back would collide in local time).
    """
    if since is None:
        since = time.start_of_local_day(now) - OUTLOOK_QUARTERS_DAYS_BACK
    known = [(start, interval) for start, interval in (sorted_known[0] if sorted_known else []) if start >= since]
    if not known:
        return None
    first = known[0][0]
    count = int((known[-1][0] - first) / QUARTER) + 1
    prices: list[float | None] = [None] * count
    levels: list[str | None] = [None] * count
    for start, interval in known:
        position, rest = divmod(start - first, QUARTER)
        if rest:
            continue  # Not on the quarter-hour grid (never for Tibber's prices)
        prices[position] = round(float(interval["total"]) * factor, precision)
        level = interval.get("level")
        levels[position] = level.lower() if isinstance(level, str) else None
    return {"start": first.astimezone(now.tzinfo).isoformat(), "minutes": 15, "prices": prices, "levels": levels}


def _past_periods(
    coordinator_data: dict | None, time: TibberPricesTimeService, *, since: datetime | None
) -> dict[str, list[dict[str, str]]]:
    """
    Return the best and peak price periods that ended before today and after `since`.

    {"best_price": [{"start": ISO, "end": ISO}, ...], "peak_price": [...]}: just their times,
    for marking them in the strips (the period sensors carry the details of today's and
    tomorrow's).
    """
    today_start = time.start_of_local_day(time.now())
    all_periods = (coordinator_data or {}).get("pricePeriods") or {}
    result: dict[str, list[dict[str, str]]] = {}
    for kind in ("best_price", "peak_price"):
        periods = all_periods.get(kind) or {}
        result[kind] = [
            {"start": period["start"].isoformat(), "end": period["end"].isoformat()}
            for period in periods.get("periods", [])
            if isinstance(period.get("start"), datetime)
            and isinstance(period.get("end"), datetime)
            and period["end"] < today_start
            and (since is None or period["end"] > since)
        ]
    return result


def _interval_start_iso(interval: dict, time: TibberPricesTimeService) -> str | None:
    """Start of an interval as ISO string (local time), or None if unknown."""
    start = time.get_interval_time(interval)
    return start.isoformat() if start else None


def _add_energy_tax_attributes(
    attributes: dict,
    interval_data: dict | None,
    *,
    config_entry: TibberPricesConfigEntry,
) -> None:
    """
    Add energy_price and tax attributes from interval data.

    The API provides `energy` (raw spot price) and `tax` (tax component) in base
    currency. These are converted to display units using the same factor as `total`.

    Args:
        attributes: Dictionary to add attributes to
        interval_data: Price interval data dict (may contain energy/tax fields)
        config_entry: Config entry for display unit preference

    """
    if not interval_data:
        return

    factor = get_display_unit_factor(config_entry)
    precision = get_display_precision(config_entry)

    energy = interval_data.get("energy")
    if energy is not None:
        attributes["energy_price"] = round(float(energy) * factor, precision)

    tax = interval_data.get("tax")
    if tax is not None:
        attributes["tax"] = round(float(tax) * factor, precision)


def add_current_interval_price_attributes(
    attributes: dict,
    key: str,
    coordinator: TibberPricesDataUpdateCoordinator,
    native_value: Any,
    cached_data: dict,
    *,
    time: TibberPricesTimeService,
    config_entry: TibberPricesConfigEntry,
) -> None:
    """
    Add attributes for current interval price sensors.

    Args:
        attributes: Dictionary to add attributes to
        key: The sensor entity key
        coordinator: The data update coordinator
        native_value: The current native value of the sensor
        cached_data: Dictionary containing cached sensor data
        time: TibberPricesTimeService instance (required)
        config_entry: Config entry for user preferences

    """
    # Get interval data and handle timestamp overrides
    interval_data = _get_interval_data_for_attributes(key, coordinator, attributes, time=time)

    # Rolling hour sensors: the exact time span their value covers
    hour_offset = ROLLING_HOUR_OFFSETS.get(key)
    if hour_offset is not None:
        all_prices = get_intervals_for_day_offsets(coordinator.data, [-1, 0, 1])
        _add_rolling_window_attributes(attributes, all_prices, hour_offset, time=time)
        if key in ("current_hour_average_price", "next_hour_average_price"):
            # The clock hour (:00-:59) alongside, for those who want both
            _add_clock_hour_attributes(attributes, all_prices, hour_offset, time=time, config_entry=config_entry)

    # Add icon_color for price sensors (based on their price level)
    if key in [
        "current_interval_price",
        "current_interval_price_base",
        "next_interval_price",
        "previous_interval_price",
    ]:
        # For interval-based price sensors, get level from interval_data
        if interval_data and "level" in interval_data:
            level = interval_data["level"]
            add_icon_color_attribute(attributes, key="price_level", state_value=level)

        # Add energy_price and tax attributes from raw API data
        _add_energy_tax_attributes(attributes, interval_data, config_entry=config_entry)

        if key == "current_interval_price":
            _add_outlook_attributes(attributes, coordinator, time=time, config_entry=config_entry)
    elif key in ["current_hour_average_price", "next_hour_average_price"]:
        # For hour-based price sensors, get level from cached_data
        level = cached_data.get("rolling_hour_level")
        if level:
            add_icon_color_attribute(attributes, key="price_level", state_value=level)

        # Add alternate average attribute for rolling hour average price sensors
        add_alternate_average_attribute(
            attributes,
            cached_data,
            f"rolling_hour_{ROLLING_HOUR_OFFSETS[key]}",
            config_entry=config_entry,
        )

    # Add price level attributes for all level sensors
    add_level_attributes_for_sensor(
        attributes=attributes,
        key=key,
        interval_data=interval_data,
        coordinator=coordinator,
        native_value=native_value,
        time=time,
    )

    # Add price rating attributes for all rating sensors
    add_rating_attributes_for_sensor(
        attributes=attributes,
        key=key,
        interval_data=interval_data,
        coordinator=coordinator,
        native_value=native_value,
        time=time,
    )


def add_level_attributes_for_sensor(
    attributes: dict,
    key: str,
    interval_data: dict | None,
    coordinator: TibberPricesDataUpdateCoordinator,
    native_value: Any,
    *,
    time: TibberPricesTimeService,
) -> None:
    """
    Add price level attributes based on sensor type.

    Args:
        attributes: Dictionary to add attributes to
        key: The sensor entity key
        interval_data: Interval data for next/previous sensors
        coordinator: The data update coordinator
        native_value: The current native value of the sensor
        time: TibberPricesTimeService instance (required)

    """
    # For interval-based level sensors (next/previous), use interval data
    if key in ["next_interval_price_level", "previous_interval_price_level"]:
        if interval_data and "level" in interval_data:
            add_price_level_attributes(attributes, interval_data["level"])
    # For hour-aggregated level sensors, use native_value
    elif key in ["current_hour_price_level", "next_hour_price_level"]:
        level_value = native_value
        if level_value and isinstance(level_value, str):
            add_price_level_attributes(attributes, level_value.upper())
    # For current price level sensor
    elif key == "current_interval_price_level":
        current_interval_data = get_current_interval_data(coordinator, time=time)
        if current_interval_data and "level" in current_interval_data:
            add_price_level_attributes(attributes, current_interval_data["level"])
            _add_level_run_attributes(attributes, coordinator, current_interval_data, time=time)


def _add_level_run_attributes(
    attributes: dict,
    coordinator: TibberPricesDataUpdateCoordinator,
    current_interval_data: dict,
    *,
    time: TibberPricesTimeService,
) -> None:
    """
    Add how long prices stay cheap/expensive and when the next such stretch starts.

    Complements the best/peak price periods: those can end while prices are still
    cheap, or start after prices already turned cheap.

    Args:
        attributes: Dictionary to add attributes to
        coordinator: The data update coordinator
        current_interval_data: Price data of the current interval
        time: TibberPricesTimeService instance (required)

    """
    current_start = time.get_interval_time(current_interval_data)
    if current_start is None:
        return
    intervals = get_intervals_for_day_offsets(coordinator.data, [-1, 0, 1])
    runs = find_level_run_times(
        intervals, current_start, {"cheap": CHEAP_PRICE_LEVELS, "expensive": EXPENSIVE_PRICE_LEVELS}, time=time
    )
    for prefix, (until, next_start) in runs.items():
        attributes[f"{prefix}_until"] = until.isoformat() if until else None
        attributes[f"next_{prefix}_start"] = next_start.isoformat() if next_start else None


def add_price_level_attributes(attributes: dict, level: str) -> None:
    """
    Add price level specific attributes.

    Args:
        attributes: Dictionary to add attributes to
        level: The price level value (e.g., VERY_CHEAP, NORMAL, etc.)

    """
    if level in PRICE_LEVEL_MAPPING:
        attributes["level_value"] = PRICE_LEVEL_MAPPING[level]
    attributes["level_id"] = level

    # Add icon_color for dynamic styling
    add_icon_color_attribute(attributes, key="price_level", state_value=level)


def add_rating_attributes_for_sensor(
    attributes: dict,
    key: str,
    interval_data: dict | None,
    coordinator: TibberPricesDataUpdateCoordinator,
    native_value: Any,
    *,
    time: TibberPricesTimeService,
) -> None:
    """
    Add price rating attributes based on sensor type.

    Args:
        attributes: Dictionary to add attributes to
        key: The sensor entity key
        interval_data: Interval data for next/previous sensors
        coordinator: The data update coordinator
        native_value: The current native value of the sensor
        time: TibberPricesTimeService instance (required)

    """
    # For interval-based rating sensors (next/previous), use interval data
    if key in ["next_interval_price_rating", "previous_interval_price_rating"]:
        if interval_data and "rating_level" in interval_data:
            add_price_rating_attributes(attributes, interval_data["rating_level"])
    # For hour-aggregated rating sensors, use native_value
    elif key in ["current_hour_price_rating", "next_hour_price_rating"]:
        rating_value = native_value
        if rating_value and isinstance(rating_value, str):
            add_price_rating_attributes(attributes, rating_value.upper())
    # For current price rating sensor
    elif key == "current_interval_price_rating":
        current_interval_data = get_current_interval_data(coordinator, time=time)
        if current_interval_data and "rating_level" in current_interval_data:
            add_price_rating_attributes(attributes, current_interval_data["rating_level"])


def add_price_rating_attributes(attributes: dict, rating: str) -> None:
    """
    Add price rating specific attributes.

    Args:
        attributes: Dictionary to add attributes to
        rating: The price rating value (e.g., LOW, NORMAL, HIGH)

    """
    if rating in PRICE_RATING_MAPPING:
        attributes["rating_value"] = PRICE_RATING_MAPPING[rating]
    attributes["rating_id"] = rating

    # Add icon_color for dynamic styling
    add_icon_color_attribute(attributes, key="price_rating", state_value=rating)
