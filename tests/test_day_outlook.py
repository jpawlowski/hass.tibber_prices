"""Forecast-style price outlook: clock hours around now and parts of the day."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from custom_components.tibber_prices.utils.day_outlook import (
    build_day_outlook,
    build_day_part_outlook,
    build_hour_outlook,
)


def _intervals(first: datetime, last: datetime) -> list[dict[str, Any]]:
    """Quarter-hour intervals from `first` to `last` (inclusive), stepping in UTC like the API."""
    result = []
    moment = first.astimezone(UTC)
    while moment <= last.astimezone(UTC):
        result.append({"startsAt": moment, "total": 0.1})
        moment += timedelta(minutes=15)
    return result


def _start(zone: ZoneInfo):
    return lambda interval: interval["startsAt"].astimezone(zone)


def _parts(blocks: list) -> list[tuple[str, str, str]]:
    return [(b.part, b.start.strftime("%d %H:%M"), b.end.strftime("%d %H:%M")) for b in blocks]


@pytest.mark.unit
def test_hours_are_48_with_tomorrow_today_and_tomorrow(berlin: ZoneInfo) -> None:
    """With tomorrow's prices: today from midnight and all of tomorrow, 48 hours."""
    intervals = _intervals(datetime(2026, 10, 15, 0, tzinfo=berlin), datetime(2026, 10, 17, 23, 45, tzinfo=berlin))
    now = datetime(2026, 10, 16, 13, 30, tzinfo=berlin)

    blocks = build_hour_outlook(intervals, now, _start(berlin))

    # To tomorrow 23:00, so a low at 23:45 tomorrow is in the strip; the past fills up the rest
    assert [(b.start.day, b.start.hour) for b in blocks] == [(16, h) for h in range(24)] + [(17, h) for h in range(24)]
    assert all(len(b.intervals) == 4 for b in blocks)


@pytest.mark.unit
def test_hours_reach_back_into_yesterday_until_tomorrows_prices_are_out(berlin: ZoneInfo) -> None:
    """Without tomorrow's prices: yesterday and today, 48 hours, ending where the prices end."""
    intervals = _intervals(datetime(2026, 10, 15, 0, tzinfo=berlin), datetime(2026, 10, 16, 23, 45, tzinfo=berlin))

    blocks = build_hour_outlook(intervals, datetime(2026, 10, 16, 21, 0, tzinfo=berlin), _start(berlin))

    assert [(b.start.day, b.start.hour) for b in blocks] == [(15, h) for h in range(24)] + [(16, h) for h in range(24)]


@pytest.mark.unit
def test_hours_keep_one_back_when_the_future_fills_the_window(berlin: ZoneInfo) -> None:
    """Shortly after midnight with two days ahead: still the hour before now, even past 48."""
    intervals = _intervals(datetime(2026, 10, 15, 0, tzinfo=berlin), datetime(2026, 10, 17, 23, 45, tzinfo=berlin))

    blocks = build_hour_outlook(intervals, datetime(2026, 10, 16, 0, 15, tzinfo=berlin), _start(berlin))

    assert (blocks[0].start.day, blocks[0].start.hour) == (15, 23)
    assert (blocks[1].start.day, blocks[1].start.hour) == (16, 0)
    assert (blocks[-1].start.day, blocks[-1].start.hour) == (17, 23)  # tomorrow's last hour too


@pytest.mark.unit
def test_day_parts_start_one_before_the_running_part_and_cross_midnight(berlin: ZoneInfo) -> None:
    """At 13:30 the day part runs, after the morning; the night goes from 22:00 to 06:00 as one block."""
    intervals = _intervals(datetime(2026, 10, 16, 0, tzinfo=berlin), datetime(2026, 10, 17, 23, 45, tzinfo=berlin))

    blocks = build_day_part_outlook(intervals, datetime(2026, 10, 16, 13, 30, tzinfo=berlin), _start(berlin))

    assert _parts(blocks) == [
        ("morning", "16 06:00", "16 09:00"),  # A little look back, like the hours
        ("day", "16 09:00", "16 17:00"),
        ("evening", "16 17:00", "16 22:00"),
        ("night", "16 22:00", "17 06:00"),
        ("morning", "17 06:00", "17 09:00"),
        ("day", "17 09:00", "17 17:00"),
        ("evening", "17 17:00", "17 22:00"),
        ("night", "17 22:00", "18 00:00"),  # as far as known, marked incomplete
    ]
    assert blocks[-1].complete is False
    assert len(blocks[3].intervals) == 32  # 8 hours


@pytest.mark.unit
def test_early_morning_belongs_to_last_night(berlin: ZoneInfo) -> None:
    """At 03:00 it's still the night that began yesterday at 22:00 (after yesterday evening)."""
    intervals = _intervals(datetime(2026, 10, 15, 0, tzinfo=berlin), datetime(2026, 10, 16, 23, 45, tzinfo=berlin))

    blocks = build_day_part_outlook(intervals, datetime(2026, 10, 16, 3, 0, tzinfo=berlin), _start(berlin))

    assert _parts(blocks)[:3] == [
        ("evening", "15 17:00", "15 22:00"),
        ("night", "15 22:00", "16 06:00"),
        ("morning", "16 06:00", "16 09:00"),
    ]


@pytest.mark.unit
def test_parts_since_start_where_the_known_prices_allow(berlin: ZoneInfo) -> None:
    """From yesterday 00:00 on: last-but-one night lacks its beginning, so yesterday morning comes first."""
    intervals = _intervals(datetime(2026, 10, 15, 0, tzinfo=berlin), datetime(2026, 10, 16, 23, 45, tzinfo=berlin))
    now = datetime(2026, 10, 16, 13, 30, tzinfo=berlin)

    blocks = build_day_part_outlook(intervals, now, _start(berlin), since=datetime(2026, 10, 15, 0, tzinfo=berlin))

    assert _parts(blocks)[0] == ("morning", "15 06:00", "15 09:00")
    assert [b.part for b in blocks][-3:] == ["day", "evening", "night"]  # today's, the night as far as known


@pytest.mark.unit
def test_part_before_without_prices_is_left_out(berlin: ZoneInfo) -> None:
    """Without prices for the morning, the list starts with the running part."""
    intervals = _intervals(datetime(2026, 10, 16, 9, tzinfo=berlin), datetime(2026, 10, 16, 23, 45, tzinfo=berlin))

    blocks = build_day_part_outlook(intervals, datetime(2026, 10, 16, 13, 30, tzinfo=berlin), _start(berlin))

    assert blocks[0].part == "day"


@pytest.mark.unit
def test_partly_known_part_ends_the_list_marked_incomplete(berlin: ZoneInfo) -> None:
    """Without tomorrow's prices, tonight is known until midnight: shown that far, marked incomplete."""
    intervals = _intervals(datetime(2026, 10, 16, 0, tzinfo=berlin), datetime(2026, 10, 16, 23, 45, tzinfo=berlin))

    blocks = build_day_part_outlook(intervals, datetime(2026, 10, 16, 13, 30, tzinfo=berlin), _start(berlin))

    assert [(b.part, b.complete) for b in blocks] == [
        ("morning", True),
        ("day", True),
        ("evening", True),
        ("night", False),
    ]
    assert (_parts(blocks)[-1][1:], len(blocks[-1].intervals)) == (("16 22:00", "17 00:00"), 8)


@pytest.mark.unit
def test_rest_of_a_part_under_an_hour_is_left_out(berlin: ZoneInfo) -> None:
    """A 45-minute rest of a day part says too little to show."""
    intervals = _intervals(datetime(2026, 10, 16, 0, tzinfo=berlin), datetime(2026, 10, 16, 22, 30, tzinfo=berlin))

    blocks = build_day_part_outlook(intervals, datetime(2026, 10, 16, 13, 30, tzinfo=berlin), _start(berlin))

    assert [b.part for b in blocks] == ["morning", "day", "evening"]


@pytest.mark.unit
def test_intervals_without_a_price_are_not_known(berlin: ZoneInfo) -> None:
    """A day whose intervals carry no price is no day yet: no block, nothing to take a low from."""
    today = _intervals(datetime(2026, 10, 16, 0, tzinfo=berlin), datetime(2026, 10, 16, 23, 45, tzinfo=berlin))
    tomorrow = [
        {"startsAt": interval["startsAt"]}
        for interval in _intervals(
            datetime(2026, 10, 17, 0, tzinfo=berlin), datetime(2026, 10, 17, 23, 45, tzinfo=berlin)
        )
    ]

    blocks = build_day_outlook(today + tomorrow, datetime(2026, 10, 16, 13, tzinfo=berlin), _start(berlin))

    assert [block.start.date().isoformat() for block in blocks] == ["2026-10-16"]


@pytest.mark.unit
def test_night_with_clock_change_has_nine_hours(berlin: ZoneInfo) -> None:
    """On the night clocks go back (25 October 2026), 22:00-06:00 lasts nine hours."""
    intervals = _intervals(datetime(2026, 10, 24, 0, tzinfo=berlin), datetime(2026, 10, 25, 23, 45, tzinfo=berlin))

    blocks = build_day_part_outlook(intervals, datetime(2026, 10, 24, 22, 30, tzinfo=berlin), _start(berlin))

    assert _parts(blocks)[1] == ("night", "24 22:00", "25 06:00")
    assert len(blocks[1].intervals) == 36


@pytest.mark.unit
def test_outlook_attributes_carry_mean_spread_and_level_in_display_unit(berlin: ZoneInfo) -> None:
    """The sensor attribute converts to the display unit and adds lowest/highest price per block."""
    from unittest.mock import MagicMock  # noqa: PLC0415

    from custom_components.tibber_prices.const import CONF_CURRENCY_DISPLAY_MODE, DISPLAY_MODE_SUBUNIT  # noqa: PLC0415
    from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService  # noqa: PLC0415
    from custom_components.tibber_prices.sensor.attributes.interval import _add_outlook_attributes  # noqa: PLC0415

    now = datetime(2026, 10, 16, 13, 30, tzinfo=berlin)
    intervals = [
        {**interval, "startsAt": interval["startsAt"].isoformat(), "total": 0.10 + 0.01 * (i % 4), "level": "CHEAP"}
        for i, interval in enumerate(
            _intervals(datetime(2026, 10, 15, 0, tzinfo=berlin), datetime(2026, 10, 17, 23, 45, tzinfo=berlin))
        )
    ]
    coordinator = MagicMock(data={"priceInfo": intervals, "referenceTime": now, "currency": "EUR"})
    attributes: dict[str, Any] = {}

    _add_outlook_attributes(
        attributes,
        coordinator,
        time=TibberPricesTimeService(reference_time=now),
        config_entry=MagicMock(options={CONF_CURRENCY_DISPLAY_MODE: DISPLAY_MODE_SUBUNIT}),
    )

    hour = next(h for h in attributes["outlook_hours"] if h["start"] == "2026-10-16T13:00:00+02:00")  # running now
    assert (hour["price_min"], hour["price_mean"], hour["price_max"], hour["level"]) == (10.0, 11.5, 13.0, "cheap")
    assert hour["price_median"] == 11.5  # Every block carries its median too, for markers in cards
    # The parts cover what the hours do (from today 00:00, tomorrow's prices being known): from
    # the night that began yesterday
    assert [(p["part"], p["start"][8:16]) for p in attributes["outlook_day_parts"][:3]] == [
        ("night", "15T22:00"),
        ("morning", "16T06:00"),
        ("day", "16T09:00"),
    ]
    today, tomorrow = attributes["outlook_days"]
    assert (today["date"], tomorrow["date"]) == ("2026-10-16", "2026-10-17")
    assert (today["price_min"], today["price_max"], today["level"]) == (10.0, 13.0, "cheap")
    assert today["volatility"] in ("low", "moderate", "high", "very_high")
    # Reference follows the average sensors' setting, median by default
    assert (today["reference"], today["price_median"], today["price_reference"]) == ("median", 11.5, 11.5)
    # Prices repeat 10, 11, 12, 13 per hour: the first low is 00:00, the first high 00:45
    assert (today["price_min_at"], today["price_max_at"]) == (
        "2026-10-16T00:00:00+02:00",
        "2026-10-16T00:45:00+02:00",
    )
    assert attributes["outlook_units"] == {"display": "subunit", "base": "€/kWh", "subunit": "ct/kWh"}
    # Yesterday's averages, for the dashed line over yesterday's last hour after midnight
    assert attributes["outlook_yesterday"] == {
        "date": "2026-10-15",
        "price_mean": 11.5,
        "price_median": 11.5,
        "price_reference": 11.5,
    }
    # Every quarter hour from 22:00 last night on, in the display unit, for zooming in
    quarters = attributes["outlook_quarters"]
    assert quarters["start"] == "2026-10-15T22:00:00+02:00"
    assert quarters["minutes"] == 15
    assert len(quarters["prices"]) == len(quarters["levels"]) == (2 + 48) * 4  # until tomorrow 23:45
    assert quarters["prices"][:4] == [10.0, 11.0, 12.0, 13.0]
    assert quarters["levels"][0] == "cheap"
    # Part boundaries for cards, wrapping around midnight for the night
    assert attributes["outlook_day_part_hours"] == {
        "morning": [6, 9],
        "day": [9, 17],
        "evening": [17, 22],
        "night": [22, 6],
    }


@pytest.mark.unit
def test_quarters_reach_back_as_far_as_the_strips(berlin: ZoneInfo) -> None:
    """Without tomorrow's prices the strips reach into yesterday's night: shown whole, its quarters too."""
    from unittest.mock import MagicMock  # noqa: PLC0415

    from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService  # noqa: PLC0415
    from custom_components.tibber_prices.sensor.attributes.interval import _add_outlook_attributes  # noqa: PLC0415

    now = datetime(2026, 10, 16, 10, 30, tzinfo=berlin)
    intervals = [
        {**interval, "startsAt": interval["startsAt"].isoformat(), "total": 0.10, "level": "NORMAL"}
        for interval in _intervals(
            datetime(2026, 10, 14, 0, tzinfo=berlin), datetime(2026, 10, 16, 23, 45, tzinfo=berlin)
        )
    ]
    coordinator = MagicMock(data={"priceInfo": intervals, "referenceTime": now, "currency": "EUR"})
    attributes: dict[str, Any] = {}

    _add_outlook_attributes(
        attributes, coordinator, time=TibberPricesTimeService(reference_time=now), config_entry=MagicMock(options={})
    )

    first_hour = attributes["outlook_hours"][0]["start"]
    assert first_hour < "2026-10-15T06:00:00+02:00"  # Into yesterday's night
    # That night is there whole, from 22:00 the day before yesterday, and so are its quarters
    night = attributes["outlook_day_parts"][0]
    assert (night["part"], night["start"], night["end"]) == (
        "night",
        "2026-10-14T22:00:00+02:00",
        "2026-10-15T06:00:00+02:00",
    )
    assert attributes["outlook_quarters"]["start"] == night["start"]


@pytest.mark.unit
def test_past_periods_cover_what_the_strips_show_before_today(berlin: ZoneInfo) -> None:
    """Yesterday's periods come along (the sensors list today's on): within the strips, not before."""
    from unittest.mock import MagicMock  # noqa: PLC0415

    from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService  # noqa: PLC0415
    from custom_components.tibber_prices.sensor.attributes.interval import _add_outlook_attributes  # noqa: PLC0415

    now = datetime(2026, 10, 16, 10, 30, tzinfo=berlin)
    intervals = [
        {**interval, "startsAt": interval["startsAt"].isoformat(), "total": 0.10, "level": "NORMAL"}
        for interval in _intervals(
            datetime(2026, 10, 14, 0, tzinfo=berlin), datetime(2026, 10, 16, 23, 45, tzinfo=berlin)
        )
    ]

    def period(day: int, start: int, end: int) -> dict[str, Any]:
        return {
            "start": datetime(2026, 10, day, start, tzinfo=berlin),
            "end": datetime(2026, 10, day, end, tzinfo=berlin),
        }

    periods = {
        "best_price": {"periods": [period(13, 3, 5), period(15, 2, 4), period(16, 1, 3)]},
        "peak_price": {"periods": [period(15, 18, 20)]},
    }
    coordinator = MagicMock(
        data={"priceInfo": intervals, "referenceTime": now, "currency": "EUR", "pricePeriods": periods}
    )
    attributes: dict[str, Any] = {}

    _add_outlook_attributes(
        attributes, coordinator, time=TibberPricesTimeService(reference_time=now), config_entry=MagicMock(options={})
    )

    assert attributes["outlook_past_periods"] == {
        "best_price": [{"start": "2026-10-15T02:00:00+02:00", "end": "2026-10-15T04:00:00+02:00"}],
        "peak_price": [{"start": "2026-10-15T18:00:00+02:00", "end": "2026-10-15T20:00:00+02:00"}],
    }


@pytest.mark.unit
def test_quarter_series_counts_real_time_over_a_clock_change(berlin: ZoneInfo) -> None:
    """On 25 October 2026 the clocks go back: 100 quarter hours that day, with a gap left as None."""
    from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService  # noqa: PLC0415
    from custom_components.tibber_prices.sensor.attributes.interval import _quarter_series  # noqa: PLC0415
    from custom_components.tibber_prices.utils.day_outlook import known_starts  # noqa: PLC0415

    now = datetime(2026, 10, 25, 12, 0, tzinfo=berlin)
    intervals = [
        {**interval, "startsAt": interval["startsAt"].isoformat(), "total": 0.2, "level": "NORMAL"}
        for interval in _intervals(
            datetime(2026, 10, 24, 0, tzinfo=berlin), datetime(2026, 10, 25, 23, 45, tzinfo=berlin)
        )
    ]
    del intervals[-8]  # 21:45 unknown

    time = TibberPricesTimeService(reference_time=now)
    series = _quarter_series(known_starts(intervals, time.get_interval_time), now, time, 100, 1)

    assert series is not None
    assert series["start"] == "2026-10-24T22:00:00+02:00"
    assert len(series["prices"]) == 8 + 100  # 22:00-24:00, then a 25-hour day
    assert series["prices"][-8] is None
    assert series["levels"][-8] is None
    assert series["prices"][0] == 20.0
    assert series["levels"][0] == "normal"


@pytest.mark.unit
def test_days_are_today_and_tomorrow_once_complete(berlin: ZoneInfo) -> None:
    """Tomorrow joins only when its prices reach midnight; a clock change day has 23 or 25 hours."""
    now = datetime(2026, 10, 24, 15, 0, tzinfo=berlin)
    today_only = _intervals(datetime(2026, 10, 24, 0, tzinfo=berlin), datetime(2026, 10, 24, 23, 45, tzinfo=berlin))
    both = _intervals(datetime(2026, 10, 24, 0, tzinfo=berlin), datetime(2026, 10, 25, 23, 45, tzinfo=berlin))

    assert [b.start.day for b in build_day_outlook(today_only, now, _start(berlin))] == [24]
    days = build_day_outlook(both, now, _start(berlin))
    assert [(b.start.day, len(b.intervals)) for b in days] == [(24, 96), (25, 100)]  # 25 October: 25 hours


@pytest.mark.unit
def test_outlook_is_built_again_only_when_its_inputs_change(berlin: ZoneInfo) -> None:
    """Read on every state write, the outlook is rebuilt for new data or the next quarter hour only."""
    from unittest.mock import MagicMock, patch  # noqa: PLC0415

    from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService  # noqa: PLC0415
    from custom_components.tibber_prices.sensor.attributes.interval import (  # noqa: PLC0415
        _add_outlook_attributes,
        _build_outlook_attributes,
    )

    now = datetime(2026, 10, 16, 10, 30, tzinfo=berlin)
    intervals = [
        {**interval, "startsAt": interval["startsAt"].isoformat(), "level": "NORMAL"}
        for interval in _intervals(
            datetime(2026, 10, 15, 0, tzinfo=berlin), datetime(2026, 10, 16, 23, 45, tzinfo=berlin)
        )
    ]
    coordinator = MagicMock(data={"priceInfo": intervals, "referenceTime": now, "currency": "EUR"})
    config_entry = MagicMock(options={})
    build = MagicMock(side_effect=_build_outlook_attributes)

    def add(at: datetime) -> dict[str, Any]:
        attributes: dict[str, Any] = {}
        _add_outlook_attributes(
            attributes, coordinator, time=TibberPricesTimeService(reference_time=at), config_entry=config_entry
        )
        return attributes

    with patch("custom_components.tibber_prices.sensor.attributes.interval._build_outlook_attributes", build):
        first = add(now)
        assert add(now) == first  # Same data, same quarter hour: from the cache
        assert build.call_count == 1
        add(now + timedelta(minutes=15))  # The next quarter hour
        assert build.call_count == 2
        coordinator.data = {**coordinator.data}  # New data
        add(now + timedelta(minutes=15))
        assert build.call_count == 3


@pytest.mark.unit
def test_known_prices_end_one_quarter_hour_after_the_last_start(berlin: ZoneInfo) -> None:
    """A quarter hour missing near the end doesn't stretch the last one: the data ends 15 minutes after its start."""
    from custom_components.tibber_prices.utils.day_outlook import known_starts  # noqa: PLC0415

    intervals = _intervals(datetime(2026, 10, 17, 0, tzinfo=berlin), datetime(2026, 10, 17, 23, 45, tzinfo=berlin))
    del intervals[-2]  # 23:30 unknown: the last two starts are 30 minutes apart

    known = known_starts(intervals, lambda interval: interval["startsAt"])

    assert known is not None
    assert known[1] == datetime(2026, 10, 18, 0, tzinfo=berlin)
