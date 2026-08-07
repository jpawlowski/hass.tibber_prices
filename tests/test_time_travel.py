"""
Unit tests for time-travel subentries.

A time-travel view shifts the clock by a fixed negative offset while time keeps
advancing normally. These tests cover the pieces that make that work: offset
normalization, the shifted TimeService, day-offset filtering against the shifted
reference, and the ID scoping that keeps a view separate from its parent entry.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest

from custom_components.tibber_prices.const import (
    CONF_VIRTUAL_TIME_OFFSET_DAYS,
    CONF_VIRTUAL_TIME_OFFSET_HOURS,
    CONF_VIRTUAL_TIME_OFFSET_MINUTES,
)
from custom_components.tibber_prices.coordinator.helpers import get_intervals_for_day_offsets, needs_tomorrow_data
from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService
from custom_components.tibber_prices.device import entity_unique_id
from custom_components.tibber_prices.time_travel import (
    SUBENTRY_TYPE_TIME_TRAVEL,
    build_offset,
    get_time_travel_offset,
    is_time_travel_subentry,
    iter_time_travel_subentries,
    subentry_storage_id,
)

TZ = ZoneInfo("Europe/Berlin")


def _make_subentry(
    subentry_id: str = "01JSUBENTRY",
    *,
    days: int = -7,
    hours: int = 0,
    minutes: int = 0,
    subentry_type: str = SUBENTRY_TYPE_TIME_TRAVEL,
) -> Mock:
    """Build a config subentry mock carrying a time offset."""
    subentry = Mock()
    subentry.subentry_id = subentry_id
    subentry.subentry_type = subentry_type
    subentry.title = "My House (7 days ago)"
    subentry.data = {
        CONF_VIRTUAL_TIME_OFFSET_DAYS: days,
        CONF_VIRTUAL_TIME_OFFSET_HOURS: hours,
        CONF_VIRTUAL_TIME_OFFSET_MINUTES: minutes,
    }
    return subentry


def _interval(start: datetime, total: float = 0.25) -> dict[str, Any]:
    """Build a minimal price interval."""
    return {"startsAt": start, "total": total}


@pytest.mark.unit
def test_offset_is_never_positive() -> None:
    """
    Test offsets always point into the past.

    Scenario: A subentry carries positive offset values (hand-edited storage).
    Expected: The resulting timedelta is still negative - there is no price data
        in the future to travel to.
    """
    subentry = _make_subentry(days=7, hours=2, minutes=30)

    assert get_time_travel_offset(subentry) == timedelta(days=-7, hours=-2, minutes=-30)
    assert build_offset(days=-1, hours=0, minutes=0) == timedelta(days=-1)


@pytest.mark.unit
def test_live_entry_has_zero_offset() -> None:
    """
    Test the live config entry is not shifted.

    Scenario: No subentry (the live coordinator).
    Expected: Zero offset, so the TimeService behaves exactly as before.
    """
    assert get_time_travel_offset(None) == timedelta()


@pytest.mark.unit
def test_time_service_applies_offset() -> None:
    """
    Test the TimeService shifts "now" by the configured offset.

    Scenario: Two services built from the same reference, one with a -7d offset.
    Expected: The shifted one reports a "now" exactly 7 days earlier and flags
        itself as time-travel.
    """
    reference = datetime(2026, 8, 7, 14, 30, tzinfo=TZ)

    live = TibberPricesTimeService(reference_time=reference)
    shifted = TibberPricesTimeService(reference_time=reference, offset=timedelta(days=-7))

    assert live.now() == reference
    assert live.is_time_travel is False
    assert shifted.now() == datetime(2026, 7, 31, 14, 30, tzinfo=TZ)
    assert shifted.is_time_travel is True
    assert shifted.offset == timedelta(days=-7)


@pytest.mark.unit
def test_time_service_advances_between_cycles() -> None:
    """
    Test a shifted clock still moves forward.

    Scenario: Two update cycles half an hour apart, both with the same offset.
    Expected: The shifted times differ by the same half hour - the view is not
        frozen at a fixed instant, it trails real time.
    """
    offset = timedelta(days=-2)
    first = TibberPricesTimeService(reference_time=datetime(2026, 8, 7, 14, 0, tzinfo=TZ), offset=offset)
    second = TibberPricesTimeService(reference_time=datetime(2026, 8, 7, 14, 30, tzinfo=TZ), offset=offset)

    assert second.now() - first.now() == timedelta(minutes=30)


@pytest.mark.unit
def test_day_offsets_resolve_against_reference_time() -> None:
    """
    Test day-offset filtering follows the shifted clock.

    Scenario: Data spanning two days, queried with a referenceTime on the
        earlier day (as a time-travel coordinator would write it).
    Expected: Offset 0 returns that earlier day, not the real today.
    """
    shifted_today = datetime(2026, 7, 31, 12, 0, tzinfo=TZ)
    data = {
        "priceInfo": [
            _interval(datetime(2026, 7, 31, 8, 0, tzinfo=TZ)),
            _interval(datetime(2026, 8, 1, 8, 0, tzinfo=TZ)),
        ],
        "referenceTime": shifted_today,
    }

    today = get_intervals_for_day_offsets(data, [0])
    tomorrow = get_intervals_for_day_offsets(data, [1])

    assert [i["startsAt"].date() for i in today] == [shifted_today.date()]
    assert [i["startsAt"].date() for i in tomorrow] == [datetime(2026, 8, 1, tzinfo=TZ).date()]


@pytest.mark.unit
def test_explicit_reference_time_wins() -> None:
    """
    Test an explicit reference overrides the one carried in the data.

    Scenario: Data says "today is the 31st", caller passes the 1st.
    Expected: The caller's reference decides.
    """
    data = {
        "priceInfo": [
            _interval(datetime(2026, 7, 31, 8, 0, tzinfo=TZ)),
            _interval(datetime(2026, 8, 1, 8, 0, tzinfo=TZ)),
        ],
        "referenceTime": datetime(2026, 7, 31, 12, 0, tzinfo=TZ),
    }

    today = get_intervals_for_day_offsets(data, [0], reference_time=datetime(2026, 8, 1, 12, 0, tzinfo=TZ))

    assert [i["startsAt"].date() for i in today] == [datetime(2026, 8, 1, tzinfo=TZ).date()]


@pytest.mark.unit
def test_needs_tomorrow_data_uses_reference_time() -> None:
    """
    Test the tomorrow check follows the shifted clock.

    Scenario: Data covers the 31st and the 1st; the view sits on the 31st.
    Expected: Tomorrow (the 1st) is present, so no fetch is needed - while a
        reference on the 1st would find nothing for the 2nd.
    """
    price_info = [
        _interval(datetime(2026, 7, 31, 8, 0, tzinfo=TZ)),
        _interval(datetime(2026, 8, 1, 8, 0, tzinfo=TZ)),
    ]

    on_31st = needs_tomorrow_data(
        {"price_info": price_info},
        reference_time=datetime(2026, 7, 31, 12, 0, tzinfo=TZ),
    )
    on_1st = needs_tomorrow_data(
        {"price_info": price_info},
        reference_time=datetime(2026, 8, 1, 12, 0, tzinfo=TZ),
    )

    assert on_31st is False
    assert on_1st is True


@pytest.mark.unit
def test_unique_ids_are_scoped_per_view() -> None:
    """
    Test entity unique IDs of a view cannot collide with the live entry's.

    Scenario: Same entity key for the live entry and for two views.
    Expected: Three distinct IDs, and the live one is unchanged from the plain
        "<entry_id>_<key>" form that existing installations already have.
    """
    subentry_a = _make_subentry("01JVIEWAAA")
    subentry_b = _make_subentry("01JVIEWBBB")

    live = entity_unique_id("entry123", "current_interval_price")
    view_a = entity_unique_id("entry123", "current_interval_price", subentry_a)
    view_b = entity_unique_id("entry123", "current_interval_price", subentry_b)

    assert live == "entry123_current_interval_price"
    assert len({live, view_a, view_b}) == 3


@pytest.mark.unit
def test_storage_ids_are_scoped_per_view() -> None:
    """
    Test each view gets its own interval pool storage.

    Scenario: Live entry and a view ask for their storage ID.
    Expected: The live entry keeps the bare entry ID (existing storage stays
        valid), the view gets its own.
    """
    subentry = _make_subentry()

    assert subentry_storage_id("entry123", None) == "entry123"
    assert subentry_storage_id("entry123", subentry) == "entry123_01JSUBENTRY"


@pytest.mark.unit
def test_pool_protected_range_follows_shifted_clock() -> None:
    """
    Test the interval pool protects the view's window, not the live one.

    Scenario: A pool is handed a TimeService shifted 7 days back.
    Expected: Its GC-protected range moves with it. Without this the pool would
        evict the historical intervals it just fetched, because they fall
        outside the live day-before-yesterday..tomorrow window.
    """
    from custom_components.tibber_prices.interval_pool.cache import (  # noqa: PLC0415
        TibberPricesIntervalPoolFetchGroupCache,
    )

    reference = datetime(2026, 8, 7, 14, 30, tzinfo=TZ)
    cache = TibberPricesIntervalPoolFetchGroupCache(time_service=TibberPricesTimeService(reference_time=reference))
    live_start, live_end = cache.get_protected_range()

    cache.set_time_service(TibberPricesTimeService(reference_time=reference, offset=timedelta(days=-7)))
    shifted_start, shifted_end = cache.get_protected_range()

    assert shifted_start < live_start
    assert shifted_end < live_end
    assert datetime.fromisoformat(live_start) - datetime.fromisoformat(shifted_start) == timedelta(days=7)


@pytest.mark.unit
def test_shared_api_client_keeps_real_time() -> None:
    """
    Test a view never puts its shifted clock on the shared API client.

    Scenario: A time-travel coordinator propagates its TimeService.
    Expected: The API client is left alone. It is shared with the live entry and
        uses its clock only for request spacing - a clock days in the past would
        make "time since last request" negative and stall the client for days.
    """
    from custom_components.tibber_prices.coordinator.core import TibberPricesDataUpdateCoordinator  # noqa: PLC0415

    coordinator = Mock(spec=TibberPricesDataUpdateCoordinator)
    coordinator.api = Mock(time="real-time-service")
    coordinator._price_data_manager = Mock()  # noqa: SLF001
    coordinator._data_transformer = Mock()  # noqa: SLF001
    coordinator._period_calculator = Mock()  # noqa: SLF001
    coordinator.interval_pool = Mock()
    coordinator.is_time_travel = True

    shifted = TibberPricesTimeService(offset=timedelta(days=-7))
    TibberPricesDataUpdateCoordinator._propagate_time_service(coordinator, shifted)  # noqa: SLF001

    assert coordinator.api.time == "real-time-service"
    coordinator.interval_pool.set_time_service.assert_called_once_with(shifted)


@pytest.mark.unit
def test_flow_normalizes_offset_input() -> None:
    """
    Test the subentry form input is stored as negative components.

    Scenario: The form returns a positive day count and a duration dict with
        seconds (the DurationSelector cannot express negative values).
    Expected: Days, hours and minutes come back negative; seconds are dropped
        because the integration works on 15-minute intervals.
    """
    from custom_components.tibber_prices.config_flow_handlers.subentry_flow import (  # noqa: PLC0415
        _has_offset,
        _normalize_offset,
    )

    days, hours, minutes = _normalize_offset(
        {
            CONF_VIRTUAL_TIME_OFFSET_DAYS: -7,
            "time_offset": {"hours": 2, "minutes": 30, "seconds": 45},
        }
    )

    assert (days, hours, minutes) == (-7, -2, -30)
    assert _has_offset(days, hours, minutes) is True
    assert _has_offset(0, 0, 0) is False


@pytest.mark.unit
def test_only_time_travel_subentries_are_picked_up() -> None:
    """
    Test iteration ignores foreign subentry types.

    Scenario: An entry holding a time-travel subentry and an unrelated one.
    Expected: Only the time-travel subentry is yielded, so a future subentry
        type does not accidentally get a coordinator.
    """
    time_travel = _make_subentry("01JAAA")
    other = _make_subentry("01JBBB", subentry_type="something_else")
    entry = Mock()
    entry.subentries = {"01JAAA": time_travel, "01JBBB": other}

    found = list(iter_time_travel_subentries(entry))

    assert found == [time_travel]
    assert is_time_travel_subentry(time_travel) is True
    assert is_time_travel_subentry(other) is False
