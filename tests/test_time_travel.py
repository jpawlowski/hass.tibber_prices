"""
Unit tests for time-travel subentries.

A time-travel view shifts the clock into the past while time keeps advancing
normally. These tests cover the pieces that make that work: the shift model
(days and yearly, with its leap-day and data-coverage gaps), day-offset
filtering against the shifted reference, tomorrow realism, the diagnostic
sensors, and the ID scoping that keeps a view separate from its parent entry.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest

from custom_components.tibber_prices.const import (
    CONF_HEADLESS,
    CONF_REALISTIC_TOMORROW,
    CONF_TOMORROW_ARRIVAL_HOUR,
    CONF_VIRTUAL_TIME_OFFSET_DAYS,
    CONF_VIRTUAL_TIME_OFFSET_HOURS,
    CONF_VIRTUAL_TIME_OFFSET_MINUTES,
    CONF_VIRTUAL_TIME_OFFSET_MODE,
    CONF_VIRTUAL_TIME_OFFSET_YEARS,
)
from custom_components.tibber_prices.coordinator.helpers import get_intervals_for_day_offsets, needs_tomorrow_data
from custom_components.tibber_prices.coordinator.time_service import TibberPricesTimeService
from custom_components.tibber_prices.device import entity_unique_id
from custom_components.tibber_prices.time_travel import (
    MODE_DAYS,
    MODE_YEARLY,
    QUARTER_HOURLY_SINCE,
    SUBENTRY_TYPE_TIME_TRAVEL,
    TimeShift,
    build_time_shift,
    get_time_shift,
    is_headless,
    is_time_travel_subentry,
    iter_time_travel_subentries,
    max_selectable_days,
    max_selectable_years,
    subentry_storage_id,
    tomorrow_arrival_hour,
    uses_realistic_tomorrow,
)

TZ = ZoneInfo("Europe/Berlin")


def _make_subentry(
    subentry_id: str = "01JSUBENTRY",
    *,
    mode: str = MODE_DAYS,
    days: int = -7,
    years: int = 0,
    hours: int = 0,
    minutes: int = 0,
    headless: bool = False,
    realistic_tomorrow: bool = True,
    arrival_hour: int = 13,
    subentry_type: str = SUBENTRY_TYPE_TIME_TRAVEL,
) -> Mock:
    """Build a config subentry mock carrying a time-travel configuration."""
    subentry = Mock()
    subentry.subentry_id = subentry_id
    subentry.subentry_type = subentry_type
    subentry.title = "My House (7 days ago)"
    subentry.data = {
        CONF_VIRTUAL_TIME_OFFSET_MODE: mode,
        CONF_VIRTUAL_TIME_OFFSET_DAYS: days,
        CONF_VIRTUAL_TIME_OFFSET_YEARS: years,
        CONF_VIRTUAL_TIME_OFFSET_HOURS: hours,
        CONF_VIRTUAL_TIME_OFFSET_MINUTES: minutes,
        CONF_HEADLESS: headless,
        CONF_REALISTIC_TOMORROW: realistic_tomorrow,
        CONF_TOMORROW_ARRIVAL_HOUR: arrival_hour,
    }
    return subentry


def _interval(start: datetime, total: float = 0.25) -> dict[str, Any]:
    """Build a minimal price interval."""
    return {"startsAt": start, "total": total}


# ---------------------------------------------------------------------------
# Shift model
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_offset_is_never_positive() -> None:
    """
    Test offsets always point into the past.

    Scenario: A subentry carries positive offset values (hand-edited storage).
    Expected: Every component comes back negative - there is no price data in
        the future to travel to.
    """
    shift = get_time_shift(_make_subentry(days=7, hours=2, minutes=30))

    assert (shift.days, shift.hours, shift.minutes) == (-7, -2, -30)


@pytest.mark.unit
def test_live_entry_has_no_shift() -> None:
    """
    Test the live config entry is not shifted.

    Scenario: No subentry (the live coordinator).
    Expected: A live shift that resolves to real time unchanged.
    """
    shift = get_time_shift(None)
    real_now = datetime(2026, 8, 7, 14, 30, tzinfo=TZ)

    assert shift.is_live is True
    assert shift.resolve(real_now) == real_now
    assert shift.describe() == "live"


@pytest.mark.unit
def test_days_mode_shifts_by_a_fixed_number_of_days() -> None:
    """
    Test days mode subtracts whole days and keeps the wall-clock time.

    Scenario: A -7 day shift with an extra -2h30m fine-tuning.
    Expected: Same wall clock seven days earlier, minus the fine-tuning.
    """
    shift = TimeShift(mode=MODE_DAYS, days=-7, hours=-2, minutes=-30)

    resolved = shift.resolve(datetime(2026, 8, 7, 14, 30, tzinfo=TZ))

    assert resolved == datetime(2026, 7, 31, 12, 0, tzinfo=TZ)
    assert shift.describe() == "time_travel_days"


@pytest.mark.unit
def test_yearly_mode_lands_on_the_same_calendar_date() -> None:
    """
    Test yearly mode keeps month and day and only changes the year.

    Scenario: A -1 year shift on 7 August.
    Expected: 7 August of the previous year at the same wall-clock time - not a
        fixed 365-day subtraction, which would drift across leap years.
    """
    shift = TimeShift(mode=MODE_YEARLY, years=-1)

    resolved = shift.resolve(datetime(2027, 8, 7, 14, 30, tzinfo=TZ))

    assert resolved == datetime(2026, 8, 7, 14, 30, tzinfo=TZ)
    assert shift.describe() == "time_travel_yearly"


@pytest.mark.unit
def test_yearly_mode_is_unavailable_on_a_leap_day() -> None:
    """
    Test 29 February has no substitute in a non-leap target year.

    Scenario: Yearly view of -1 year, real date 29 February 2028.
    Expected: None (unavailable). Sliding to 1 March would silently compare the
        wrong day, and 2027 has no 29 February at all.
    """
    shift = TimeShift(mode=MODE_YEARLY, years=-1)

    assert shift.resolve(datetime(2028, 2, 29, 12, 0, tzinfo=TZ)) is None
    assert shift.has_data_coverage(datetime(2028, 2, 29, 12, 0, tzinfo=TZ)) is False
    # The day before resolves fine - the view is only out for that one day.
    assert shift.resolve(datetime(2028, 2, 28, 12, 0, tzinfo=TZ)) is not None


@pytest.mark.unit
def test_dates_before_the_resolution_change_have_no_coverage() -> None:
    """
    Test the view refuses dates without quarter-hourly prices.

    Scenario: An offset that lands just before and just after Tibber's switch to
        quarter-hourly prices, allowing for the two trailing days a view needs.
    Expected: Only the later one reports coverage - hourly data cannot be
        interpreted by 15-minute logic, so the view must go unavailable.
    """
    real_now = datetime(2026, 8, 7, 12, 0, tzinfo=TZ)
    days_to_floor = (real_now.date() - QUARTER_HOURLY_SINCE).days

    just_inside = TimeShift(days=-(days_to_floor - 2))
    just_outside = TimeShift(days=-(days_to_floor - 1))

    assert just_inside.has_data_coverage(real_now) is True
    assert just_outside.has_data_coverage(real_now) is False


@pytest.mark.unit
def test_selectable_ranges_track_available_data() -> None:
    """
    Test the config flow sliders shrink to what Tibber actually has.

    Scenario: A date shortly after the resolution change, and one much later.
    Expected: The day range grows with time and yearly mode stays unavailable
        until a full year of quarter-hourly data exists.
    """
    early = date(2025, 11, 18)
    later = date(2027, 6, 1)

    assert max_selectable_days(early) == (early - QUARTER_HOURLY_SINCE).days - 2
    assert max_selectable_years(early) == 0
    assert max_selectable_days(later) == 374
    assert max_selectable_years(later) >= 1


@pytest.mark.unit
def test_mode_switch_ignores_the_other_mode_offset() -> None:
    """
    Test a yearly view ignores a leftover day offset.

    Scenario: Storage holds both a day and a year offset (e.g. after a mode
        change wrote only part of the data).
    Expected: Yearly mode uses the year offset only, so the view cannot end up
        shifted twice.
    """
    shift = build_time_shift(
        {
            CONF_VIRTUAL_TIME_OFFSET_MODE: MODE_YEARLY,
            CONF_VIRTUAL_TIME_OFFSET_DAYS: -30,
            CONF_VIRTUAL_TIME_OFFSET_YEARS: -1,
        }
    )

    resolved = shift.resolve(datetime(2027, 8, 7, 14, 30, tzinfo=TZ))

    assert resolved == datetime(2026, 8, 7, 14, 30, tzinfo=TZ)


# ---------------------------------------------------------------------------
# Clock plumbing
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_time_service_advances_between_cycles() -> None:
    """
    Test a shifted clock still moves forward.

    Scenario: Two update cycles half an hour apart, both resolved from the same
        shift.
    Expected: The shifted times differ by the same half hour - the view is not
        frozen at a fixed instant, it trails real time.
    """
    shift = TimeShift(days=-2)
    first = TibberPricesTimeService(reference_time=shift.resolve(datetime(2026, 8, 7, 14, 0, tzinfo=TZ)))
    second = TibberPricesTimeService(reference_time=shift.resolve(datetime(2026, 8, 7, 14, 30, tzinfo=TZ)))

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
    assert [i["startsAt"].date() for i in tomorrow] == [date(2026, 8, 1)]


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

    assert [i["startsAt"].date() for i in today] == [date(2026, 8, 1)]


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

    shifted = TibberPricesTimeService(reference_time=datetime(2026, 7, 31, 12, 0, tzinfo=TZ))
    TibberPricesDataUpdateCoordinator._propagate_time_service(coordinator, shifted)  # noqa: SLF001

    assert coordinator.api.time == "real-time-service"
    coordinator.interval_pool.set_time_service.assert_called_once_with(shifted)


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

    shift = TimeShift(days=-7)
    cache.set_time_service(TibberPricesTimeService(reference_time=shift.resolve(reference)))
    shifted_start, shifted_end = cache.get_protected_range()

    assert shifted_start < live_start
    assert shifted_end < live_end
    assert datetime.fromisoformat(live_start) - datetime.fromisoformat(shifted_start) == timedelta(days=7)


# ---------------------------------------------------------------------------
# View behaviour
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_realistic_tomorrow_withholds_and_then_releases() -> None:
    """
    Test tomorrow's prices stay hidden until the view's own arrival hour.

    Scenario: A view holding two days of data, asked before and after 13:00 on
        its shifted clock.
    Expected: Before the arrival hour only today's intervals survive; after it
        the full range is returned. This is what lets an automation that waits
        for tomorrow's prices be rehearsed against a past day.
    """
    from custom_components.tibber_prices.coordinator.core import TibberPricesDataUpdateCoordinator  # noqa: PLC0415

    # The arrival hour is evaluated in Home Assistant's local timezone, which is
    # UTC in tests - so build the fixture there to keep the hours meaningful.
    price_info = [
        _interval(datetime(2026, 7, 31, 8, 0, tzinfo=UTC)),
        _interval(datetime(2026, 8, 1, 8, 0, tzinfo=UTC)),
    ]

    def _coordinator_at(hour: int) -> Mock:
        coordinator = Mock(spec=TibberPricesDataUpdateCoordinator)
        coordinator._withhold_tomorrow = True  # noqa: SLF001
        coordinator._tomorrow_arrival_hour = 13  # noqa: SLF001
        coordinator.time = TibberPricesTimeService(reference_time=datetime(2026, 7, 31, hour, 0, tzinfo=UTC))
        coordinator._log = Mock()  # noqa: SLF001
        coordinator._starts_at_or_after = TibberPricesDataUpdateCoordinator._starts_at_or_after.__get__(  # noqa: SLF001
            coordinator
        )
        return coordinator

    apply = TibberPricesDataUpdateCoordinator._apply_tomorrow_realism  # noqa: SLF001
    before = apply(_coordinator_at(9), {"price_info": price_info})
    after = apply(_coordinator_at(14), {"price_info": price_info})

    assert [i["startsAt"].date() for i in before["price_info"]] == [date(2026, 7, 31)]
    assert len(after["price_info"]) == 2


@pytest.mark.unit
def test_view_options_have_sensible_defaults() -> None:
    """
    Test the behaviour flags fall back safely.

    Scenario: A subentry whose data predates these options, and the live entry.
    Expected: Realism on, arrival hour 13, not headless - and the live entry
        never withholds anything.
    """
    bare = Mock()
    bare.data = {}

    assert uses_realistic_tomorrow(bare) is True
    assert tomorrow_arrival_hour(bare) == 13
    assert is_headless(bare) is False
    assert uses_realistic_tomorrow(None) is False
    assert is_headless(None) is False


@pytest.mark.unit
def test_arrival_hour_is_clamped() -> None:
    """
    Test a nonsensical arrival hour cannot break the comparison.

    Scenario: Storage holds an out-of-range or non-numeric hour.
    Expected: Clamped into 0..23, falling back to the default when unparsable.
    """
    assert tomorrow_arrival_hour(Mock(data={CONF_TOMORROW_ARRIVAL_HOUR: 99})) == 23
    assert tomorrow_arrival_hour(Mock(data={CONF_TOMORROW_ARRIVAL_HOUR: -5})) == 0
    assert tomorrow_arrival_hour(Mock(data={CONF_TOMORROW_ARRIVAL_HOUR: "nonsense"})) == 13


# ---------------------------------------------------------------------------
# Diagnostic sensors
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_diagnostic_sensors_describe_a_view() -> None:
    """
    Test the time-travel sensors report the view's configuration.

    Scenario: A yearly view with a fine-tuning offset, in headless mode.
    Expected: Mode and year offset are reported, the day offset is None (wrong
        mode), and the fine-tuning shows as a signed clock string.
    """
    from custom_components.tibber_prices.sensor.calculators.time_travel import (  # noqa: PLC0415
        TibberPricesTimeTravelCalculator,
    )

    coordinator = Mock()
    coordinator.time_shift = TimeShift(mode=MODE_YEARLY, years=-1, hours=-2, minutes=-30)
    coordinator.headless = True
    coordinator.is_time_travel = True
    coordinator.last_update_success = True
    coordinator.time = TibberPricesTimeService(reference_time=datetime(2026, 8, 7, 12, 0, tzinfo=TZ))

    calc = TibberPricesTimeTravelCalculator(coordinator)

    assert calc.get_entry_mode() == "time_travel_yearly"
    assert calc.get_years_offset() == -1
    assert calc.get_days_offset() is None
    assert calc.get_time_offset() == "-02:30"
    assert calc.get_headless_mode() == "on"
    assert calc.get_reference_time() == datetime(2026, 8, 7, 12, 0, tzinfo=TZ)


@pytest.mark.unit
def test_diagnostic_sensors_on_a_live_device() -> None:
    """
    Test the sensors answer meaningfully on the live device too.

    Scenario: The live coordinator.
    Expected: "live" with no offsets - someone comparing two devices in a chart
        needs that answer, not an empty entity.
    """
    from custom_components.tibber_prices.sensor.calculators.time_travel import (  # noqa: PLC0415
        TibberPricesTimeTravelCalculator,
    )

    coordinator = Mock()
    coordinator.time_shift = TimeShift()
    coordinator.headless = False
    coordinator.is_time_travel = False
    coordinator.last_update_success = True
    coordinator.time = TibberPricesTimeService(reference_time=datetime(2026, 8, 7, 12, 0, tzinfo=TZ))

    calc = TibberPricesTimeTravelCalculator(coordinator)

    assert calc.get_entry_mode() == "live"
    assert calc.get_days_offset() is None
    assert calc.get_years_offset() is None
    assert calc.get_time_offset() is None
    assert calc.get_headless_mode() == "off"


# ---------------------------------------------------------------------------
# Scoping
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_unique_ids_are_scoped_per_view() -> None:
    """
    Test entity unique IDs of a view cannot collide with the live entry's.

    Scenario: Same entity key for the live entry and for two views.
    Expected: Three distinct IDs, and the live one is unchanged from the plain
        "<entry_id>_<key>" form that existing installations already have.
    """
    live = entity_unique_id("entry123", "current_interval_price")
    view_a = entity_unique_id("entry123", "current_interval_price", _make_subentry("01JVIEWAAA"))
    view_b = entity_unique_id("entry123", "current_interval_price", _make_subentry("01JVIEWBBB"))

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
    assert subentry_storage_id("entry123", None) == "entry123"
    assert subentry_storage_id("entry123", _make_subentry()) == "entry123_01JSUBENTRY"


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


# ---------------------------------------------------------------------------
# Config flow validation
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_flow_rejects_useless_offsets() -> None:
    """
    Test the flow refuses offsets that cannot produce a working view.

    Scenario: A zero offset, and one reaching back past Tibber's switch to
        quarter-hourly prices.
    Expected: Distinct errors for both, so the user is corrected in the form
        rather than ending up with a permanently unavailable view.
    """
    from custom_components.tibber_prices.config_flow_handlers.subentry_flow import (  # noqa: PLC0415
        TibberPricesSubentryFlowHandler,
        _normalize_offset,
    )

    handler = TibberPricesSubentryFlowHandler()

    nothing = handler._validate(_normalize_offset({CONF_VIRTUAL_TIME_OFFSET_DAYS: 0}, MODE_DAYS))  # noqa: SLF001
    too_far = handler._validate(_normalize_offset({CONF_VIRTUAL_TIME_OFFSET_DAYS: -3650}, MODE_DAYS))  # noqa: SLF001
    fine = handler._validate(_normalize_offset({CONF_VIRTUAL_TIME_OFFSET_DAYS: -7}, MODE_DAYS))  # noqa: SLF001

    assert nothing == {"base": "no_time_offset"}
    assert too_far == {"base": "before_quarter_hourly"}
    assert fine == {}


@pytest.mark.unit
@pytest.mark.parametrize(
    ("label", "user_input", "mode"),
    [
        ("no duration field at all", {CONF_VIRTUAL_TIME_OFFSET_DAYS: 0}, MODE_DAYS),
        (
            "duration filled with zeros",
            {CONF_VIRTUAL_TIME_OFFSET_DAYS: 0, "time_offset": {"hours": 0, "minutes": 0}},
            MODE_DAYS,
        ),
        (
            "zeros including seconds",
            {CONF_VIRTUAL_TIME_OFFSET_DAYS: 0, "time_offset": {"hours": 0, "minutes": 0, "seconds": 0}},
            MODE_DAYS,
        ),
        # Seconds are dropped - the integration works in 15-minute intervals - so a
        # sub-minute offset leaves the clock exactly where it was.
        ("seconds only", {CONF_VIRTUAL_TIME_OFFSET_DAYS: 0, "time_offset": {"seconds": 30}}, MODE_DAYS),
        ("yearly with no year offset", {CONF_VIRTUAL_TIME_OFFSET_YEARS: 0}, MODE_YEARLY),
    ],
)
def test_flow_rejects_every_shape_of_zero_offset(label: str, user_input: dict, mode: str) -> None:
    """
    Test a view that would duplicate the live device is refused however it is expressed.

    Scenario: The several ways a form can come back describing no shift at all.
    Expected: All rejected. Such a view would carry its own device, entities and
        interval pool while showing exactly what the live device shows.
    """
    from custom_components.tibber_prices.config_flow_handlers.subentry_flow import (  # noqa: PLC0415
        TibberPricesSubentryFlowHandler,
        _normalize_offset,
    )

    handler = TibberPricesSubentryFlowHandler()

    assert handler._validate(_normalize_offset(user_input, mode)) == {"base": "no_time_offset"}, label  # noqa: SLF001


@pytest.mark.unit
@pytest.mark.parametrize(
    ("label", "user_input", "mode"),
    [
        # A same-day view shifted by hours is a real view, not a live duplicate.
        ("today, two hours back", {CONF_VIRTUAL_TIME_OFFSET_DAYS: 0, "time_offset": {"hours": 2}}, MODE_DAYS),
        ("today, 30 minutes back", {CONF_VIRTUAL_TIME_OFFSET_DAYS: 0, "time_offset": {"minutes": 30}}, MODE_DAYS),
        ("a week back", {CONF_VIRTUAL_TIME_OFFSET_DAYS: -7}, MODE_DAYS),
    ],
)
def test_flow_accepts_offsets_that_move_the_clock(label: str, user_input: dict, mode: str) -> None:
    """
    Test the zero-offset guard does not swallow legitimate small offsets.

    Scenario: Offsets that shift the clock without moving the date.
    Expected: Accepted - only a shift of exactly nothing is refused.
    """
    from custom_components.tibber_prices.config_flow_handlers.subentry_flow import (  # noqa: PLC0415
        TibberPricesSubentryFlowHandler,
        _normalize_offset,
    )

    handler = TibberPricesSubentryFlowHandler()

    assert handler._validate(_normalize_offset(user_input, mode)) == {}, label  # noqa: SLF001


@pytest.mark.unit
def test_flow_normalizes_offset_input() -> None:
    """
    Test the subentry form input is stored as negative components.

    Scenario: The form returns a positive day count and a duration dict with
        seconds (the DurationSelector cannot express negative values).
    Expected: Days, hours and minutes come back negative; seconds are dropped
        because the integration works on 15-minute intervals.
    """
    from custom_components.tibber_prices.config_flow_handlers.subentry_flow import _normalize_offset  # noqa: PLC0415

    offsets = _normalize_offset(
        {
            CONF_VIRTUAL_TIME_OFFSET_DAYS: -7,
            "time_offset": {"hours": 2, "minutes": 30, "seconds": 45},
        },
        MODE_DAYS,
    )

    assert (offsets.days, offsets.years, offsets.hours, offsets.minutes) == (-7, 0, -2, -30)


@pytest.mark.unit
def test_flow_clears_the_inactive_mode_offset() -> None:
    """
    Test switching mode cannot leave a stale offset behind.

    Scenario: A yearly view submitted with a day offset still in the form.
    Expected: Only the year offset is kept, so the stored data can never shift
        the clock twice.
    """
    from custom_components.tibber_prices.config_flow_handlers.subentry_flow import _normalize_offset  # noqa: PLC0415

    offsets = _normalize_offset(
        {CONF_VIRTUAL_TIME_OFFSET_DAYS: -30, CONF_VIRTUAL_TIME_OFFSET_YEARS: -1},
        MODE_YEARLY,
    )

    assert (offsets.days, offsets.years) == (0, -1)


# ---------------------------------------------------------------------------
# View naming
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_view_title_is_built_on_the_home_device_name() -> None:
    """
    Test a view is named after the home as its device shows it, not after the entry.

    Scenario: A home with an app nickname. Home Assistant titles the config entry by
        address, while the home's device carries the nickname.
    Expected: The view's title starts with the nickname, so it reads as the same home
        as the device sitting next to it in the integration page - it used to start
        with the address and looked like a different home.
    """
    from unittest.mock import MagicMock  # noqa: PLC0415

    from custom_components.tibber_prices.config_flow_handlers.subentry_flow import (  # noqa: PLC0415
        TibberPricesSubentryFlowHandler,
    )
    from custom_components.tibber_prices.device import build_device_info  # noqa: PLC0415

    entry_data = {
        "home_id": "home-1",
        "home_data": {
            "appNickname": "Pählstraße",
            "address": {"address1": "Pählstraße 6B", "city": "München"},
            "type": "APARTMENT",
        },
    }
    parent_entry = MagicMock()
    parent_entry.title = "Pählstraße 6B, München"
    parent_entry.data = entry_data

    coordinator = Mock()
    coordinator.config_entry.data = entry_data
    coordinator.config_entry.unique_id = "home-1"
    coordinator.hass.config.language = "en"

    handler = TibberPricesSubentryFlowHandler()
    handler.hass = MagicMock()
    handler.hass.config.language = "en"
    handler.hass.data = {}

    title = handler._build_title(  # noqa: SLF001
        parent_entry,
        {
            CONF_VIRTUAL_TIME_OFFSET_MODE: MODE_DAYS,
            CONF_VIRTUAL_TIME_OFFSET_DAYS: -6,
            CONF_HEADLESS: True,
        },
    )
    home_device_name = build_device_info(coordinator).get("name")

    assert home_device_name == "Pählstraße"
    assert title.startswith("Pählstraße ("), title
    assert not title.startswith("Pählstraße 6B"), "view still named after the entry title"
    assert title.endswith("[headless]")


@pytest.mark.unit
def test_view_title_keeps_a_parenthesis_in_the_home_name() -> None:
    """
    Test an app nickname containing "(...)" survives into the view title.

    Scenario: A home nicknamed "Haus (Ferien)".
    Expected: The whole nickname is kept. The old builder stripped everything from
        the first " (" onwards to trim a suffix off the entry title, which cut such
        a nickname down to "Haus".
    """
    from custom_components.tibber_prices.device import home_display_name  # noqa: PLC0415

    parent_entry = Mock()
    parent_entry.data = {"home_id": "home-1", "home_data": {"appNickname": "Haus (Ferien)"}}

    assert home_display_name(parent_entry) == "Haus (Ferien)"
