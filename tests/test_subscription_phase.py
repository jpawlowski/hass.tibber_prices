"""
Tests for subscriptions that have not started yet or have ended (issue #230).

While the status is "awaiting market" Tibber sends no prices (``priceInfo.current``
is null, the day lists are empty). The integration must still set up, create only the
entities that need no prices, and start fetching when the contract starts. A contract
already "running" before ``validFrom`` has prices and works as usual (issue #237).
After ``validTo`` the entities stay on the last day of the contract.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch
from zoneinfo import ZoneInfo

import pytest

from custom_components.tibber_prices.const import get_default_currency_for_country
from custom_components.tibber_prices.coordinator.core import TibberPricesDataUpdateCoordinator
from custom_components.tibber_prices.coordinator.price_data_manager import TibberPricesPriceDataManager
from custom_components.tibber_prices.sensor.calculators.lifecycle import TibberPricesLifecycleCalculator
from custom_components.tibber_prices.time_travel import TimeShift
from custom_components.tibber_prices.utils.subscription import (
    PHASE_ACTIVE,
    PHASE_ENDED,
    PHASE_PENDING,
    get_subscription_last_interval_start,
    get_subscription_phase,
)

BERLIN = ZoneInfo("Europe/Berlin")
HOME_ID = "home-123"
NOW = datetime(2026, 11, 20, 12, 0, tzinfo=BERLIN)


def _subscription(
    valid_from: str | None,
    valid_to: str | None = None,
    *,
    current: bool = False,
    status: str | None = "awaiting market",
) -> dict:
    """Build a currentSubscription as the viewer query returns it."""
    return {
        "status": status,
        "validFrom": valid_from,
        "validTo": valid_to,
        "priceInfo": {"current": {"currency": "EUR"} if current else None},
    }


def _user_data(subscription: dict | None) -> dict:
    return {
        "viewer": {
            "homes": [
                {
                    "id": HOME_ID,
                    "timeZone": "Europe/Berlin",
                    "address": {"country": "NL"},
                    "currentSubscription": subscription,
                }
            ]
        }
    }


def _manager(user_data: dict | None = None) -> TibberPricesPriceDataManager:
    manager = TibberPricesPriceDataManager(
        api=Mock(),
        store=Mock(),
        log_prefix="[Test]",
        user_update_interval=timedelta(days=1),
        time=Mock(),
        home_id=HOME_ID,
        interval_pool=Mock(),
    )
    manager._cached_user_data = user_data  # noqa: SLF001
    return manager


# --- phase helper ---------------------------------------------------------------


@pytest.mark.unit
def test_phase_pending_before_valid_from() -> None:
    """A contract whose validFrom lies ahead is pending (the exact case of the issue)."""
    subscription = _subscription("2026-12-06T23:00:00+00:00")
    assert get_subscription_phase(subscription, NOW) == PHASE_PENDING


@pytest.mark.unit
def test_phase_active_before_valid_from_once_running_with_prices() -> None:
    """Issue #237: a confirmed switch is "running" with prices weeks before validFrom."""
    subscription = _subscription("2026-12-31T23:00:00+00:00", status="running", current=True)
    assert get_subscription_phase(subscription, NOW) == PHASE_ACTIVE


@pytest.mark.unit
@pytest.mark.parametrize(
    ("status", "current"),
    [("awaiting market", True), ("Awaiting Market", True), (None, False), ("pending", False), ("ended", False)],
)
def test_phase_pending_before_valid_from_unless_running(status: str | None, current: bool) -> None:
    """Before validFrom, any status but "running" (or none) keeps the contract pending."""
    subscription = _subscription("2026-12-31T23:00:00+00:00", status=status, current=current)
    assert get_subscription_phase(subscription, NOW) == PHASE_PENDING


@pytest.mark.unit
def test_running_contract_stays_active_when_the_current_price_is_missing() -> None:
    """A null current price during Tibber's maintenance must not turn a running contract pending."""
    subscription = _subscription("2026-12-31T23:00:00+00:00", status="running")
    assert get_subscription_phase(subscription, NOW) == PHASE_ACTIVE
    assert _manager()._validate_user_data(_user_data(subscription), HOME_ID) is False  # noqa: SLF001


@pytest.mark.unit
def test_phase_active_from_valid_from_on() -> None:
    """From validFrom on the contract is active."""
    subscription = _subscription("2026-12-06T23:00:00+00:00")
    start = datetime.fromisoformat("2026-12-06T23:00:00+00:00")
    assert get_subscription_phase(subscription, start) == PHASE_ACTIVE


@pytest.mark.unit
def test_phase_ended_from_valid_to_on() -> None:
    """validTo is the first moment after the contract."""
    subscription = _subscription("2025-01-01T00:00:00+01:00", "2026-11-10T00:00:00+01:00")
    assert get_subscription_phase(subscription, NOW) == PHASE_ENDED
    assert get_subscription_phase(subscription, datetime(2026, 11, 9, 23, 59, tzinfo=BERLIN)) == PHASE_ACTIVE


@pytest.mark.unit
@pytest.mark.parametrize("subscription", [None, {}, {"validFrom": "garbage", "validTo": "not a date"}])
def test_phase_unknown_counts_as_active(subscription: dict | None) -> None:
    """Without usable dates nothing changes against the behaviour before phases existed."""
    assert get_subscription_phase(subscription, NOW) == PHASE_ACTIVE


@pytest.mark.unit
def test_phase_reads_dates_without_offset_as_utc() -> None:
    """A validTo without offset still ends the contract instead of being ignored."""
    subscription = _subscription("2025-01-01T00:00:00", "2026-11-10T00:00:00", current=True, status="running")
    assert get_subscription_phase(subscription, NOW) == PHASE_ENDED


@pytest.mark.unit
def test_last_interval_start_is_the_quarter_before_valid_to() -> None:
    """The clock of an ended contract stands on its last quarter hour, not a second before midnight."""
    subscription = _subscription("2025-01-01T00:00:00+01:00", "2026-11-10T00:00:00+01:00")
    assert get_subscription_last_interval_start(subscription) == datetime(2026, 11, 9, 23, 45, tzinfo=BERLIN)
    assert get_subscription_last_interval_start(_subscription("2025-01-01T00:00:00+01:00")) is None


# --- user data validation and currency --------------------------------------------


@pytest.mark.unit
def test_validation_accepts_pending_subscription_without_current_price() -> None:
    """The error of the issue: 'priceInfo has no current data' must not reject a pending contract."""
    manager = _manager()
    user_data = _user_data(_subscription("2099-01-01T00:00:00+01:00"))
    assert manager._validate_user_data(user_data, HOME_ID) is True  # noqa: SLF001


@pytest.mark.unit
def test_validation_still_rejects_active_subscription_without_current_price() -> None:
    """An active contract without a current price is an incomplete API answer (issue #60)."""
    manager = _manager()
    user_data = _user_data(_subscription("2020-01-01T00:00:00+01:00", status="running"))
    assert manager._validate_user_data(user_data, HOME_ID) is False  # noqa: SLF001


@pytest.mark.unit
def test_currency_of_pending_subscription_comes_from_the_country() -> None:
    """No current price means no currency from the API: the home's country decides."""
    manager = _manager(_user_data(_subscription("2099-01-01T00:00:00+01:00")))
    assert manager._get_currency_for_home(HOME_ID) == "EUR"  # noqa: SLF001
    assert get_default_currency_for_country("NO") == "NOK"
    assert get_default_currency_for_country("se") == "SEK"
    assert get_default_currency_for_country(None) == "EUR"


@pytest.mark.unit
def test_manager_phase_follows_cached_user_data() -> None:
    """The manager derives the phase from the cached subscription."""
    assert _manager().subscription_phase == PHASE_ACTIVE
    assert _manager(_user_data(_subscription("2099-01-01T00:00:00+01:00"))).subscription_phase == PHASE_PENDING
    ended = _subscription("2020-01-01T00:00:00+01:00", "2021-01-01T00:00:00+01:00", current=True)
    assert _manager(_user_data(ended)).subscription_phase == PHASE_ENDED


@pytest.mark.unit
async def test_pending_subscription_fetches_no_prices() -> None:
    """Before validFrom the pool is not asked for anything."""
    manager = _manager(_user_data(_subscription("2099-01-01T00:00:00+01:00")))
    manager._interval_pool.get_sensor_data = AsyncMock()  # noqa: SLF001

    data, api_called = await manager.fetch_home_data(HOME_ID, NOW)

    assert data["price_info"] == []
    assert data["currency"] == "EUR"
    assert api_called is False
    manager._interval_pool.get_sensor_data.assert_not_called()  # noqa: SLF001


@pytest.mark.unit
async def test_running_subscription_before_valid_from_fetches_prices() -> None:
    """Issue #237: the prices Tibber already sends before validFrom are fetched as usual."""
    running = _subscription("2099-01-01T00:00:00+01:00", status="running", current=True)
    manager = _manager(_user_data(running))
    fetched = [{"startsAt": "2026-11-20T12:00:00+01:00", "total": 0.3}]
    manager._fetch_via_pool = AsyncMock(return_value=(fetched, True))  # noqa: SLF001

    assert manager._validate_user_data(_user_data(running), HOME_ID) is True  # noqa: SLF001
    data, api_called = await manager.fetch_home_data(HOME_ID, NOW)

    assert manager.subscription_phase == PHASE_ACTIVE
    assert data["price_info"] == fetched
    assert api_called is True


@pytest.mark.unit
async def test_ended_subscription_serves_cache_only() -> None:
    """After validTo only what is cached is shown - no request that could only fail."""
    ended = _subscription("2020-01-01T00:00:00+01:00", "2021-01-01T00:00:00+01:00", current=True)
    manager = _manager(_user_data(ended))
    cached = [{"startsAt": "2020-12-31T23:45:00+01:00", "total": 0.3}]
    manager._interval_pool.get_cached_sensor_data = Mock(return_value=cached)  # noqa: SLF001
    manager._interval_pool.get_sensor_data = AsyncMock()  # noqa: SLF001

    data, api_called = await manager.fetch_home_data(HOME_ID, NOW)

    assert data["price_info"] == cached
    assert api_called is False
    manager._interval_pool.get_sensor_data.assert_not_called()  # noqa: SLF001


@pytest.mark.unit
async def test_stale_pending_copy_is_replaced_once_the_contract_started() -> None:
    """The cached copy from before validFrom has no currency source any more, so it is refetched."""
    started = _subscription("2020-01-01T00:00:00+01:00", status="running")  # cached while pending, now running
    manager = _manager(_user_data(started))
    fresh = _user_data(_subscription("2020-01-01T00:00:00+01:00", current=True))
    manager.api.async_get_viewer_details = AsyncMock(return_value=fresh)

    assert await manager._ensure_user_data(NOW) is True  # noqa: SLF001
    assert manager.cached_user_data == fresh


@pytest.mark.unit
async def test_ended_subscription_keeps_cache_when_api_has_nothing_new() -> None:
    """Tibber stops sending a subscription after the end: keep the cache, ask again tomorrow."""
    ended = _subscription("2020-01-01T00:00:00+01:00", "2021-01-01T00:00:00+01:00", current=True)
    cached = _user_data(ended)
    manager = _manager(cached)
    manager.api.async_get_viewer_details = AsyncMock(return_value=_user_data(None))

    assert await manager.update_user_data_if_needed(NOW) is False
    assert manager.cached_user_data == cached
    assert manager._last_user_update == NOW  # noqa: SLF001


@pytest.mark.unit
async def test_pending_subscription_looks_for_the_switch_hourly() -> None:
    """While pending, user data is checked hourly, and a confirmed switch with prices is taken."""
    manager = _manager(_user_data(_subscription("2099-01-01T00:00:00+01:00")))
    manager._last_user_update = NOW - timedelta(minutes=61)  # noqa: SLF001
    running = _user_data(_subscription("2099-01-01T00:00:00+01:00", status="running", current=True))
    manager.api.async_get_viewer_details = AsyncMock(return_value=running)

    assert await manager.update_user_data_if_needed(NOW) is True
    assert manager.cached_user_data == running
    assert manager.subscription_phase == PHASE_ACTIVE


@pytest.mark.unit
async def test_pending_subscription_keeps_its_copy_until_the_first_price() -> None:
    """A "running" copy without a price yet is not usable: keep the pending one, look again in an hour."""
    cached = _user_data(_subscription("2099-01-01T00:00:00+01:00"))
    manager = _manager(cached)
    manager._last_user_update = NOW - timedelta(hours=2)  # noqa: SLF001
    manager.api.async_get_viewer_details = AsyncMock(
        return_value=_user_data(_subscription("2099-01-01T00:00:00+01:00", status="running"))
    )

    assert await manager.update_user_data_if_needed(NOW) is False
    assert manager.cached_user_data == cached
    assert manager._last_user_update == NOW  # noqa: SLF001
    assert await manager.update_user_data_if_needed(NOW + timedelta(minutes=30)) is False
    assert manager.api.async_get_viewer_details.await_count == 1


# --- coordinator: the clock of an ended contract -----------------------------------


def _coordinator_stub(subscription: dict | None) -> Mock:
    stub = Mock()
    stub._time_shift = TimeShift()  # noqa: SLF001
    stub._home_id = HOME_ID  # noqa: SLF001
    stub._cached_user_data = _user_data(subscription)  # noqa: SLF001
    stub._price_data_manager.subscription = subscription  # noqa: SLF001
    return stub


@pytest.mark.unit
def test_clock_stops_on_last_interval_of_ended_contract() -> None:
    """'Today' is the last day of the contract for good, 'tomorrow' does not exist."""
    stub = _coordinator_stub(_subscription("2020-01-01T00:00:00+01:00", "2026-11-10T00:00:00+01:00", current=True))
    with patch("custom_components.tibber_prices.coordinator.core.dt_util.now", return_value=NOW):
        time_service = TibberPricesDataUpdateCoordinator._create_time_service(stub)  # noqa: SLF001
    assert time_service.now() == datetime(2026, 11, 9, 23, 45, tzinfo=BERLIN)


@pytest.mark.unit
def test_clock_runs_normally_until_the_contract_ends() -> None:
    """A contract that ends in the future does not hold the clock yet."""
    stub = _coordinator_stub(_subscription("2020-01-01T00:00:00+01:00", "2026-12-31T00:00:00+01:00", current=True))
    with patch("custom_components.tibber_prices.coordinator.core.dt_util.now", return_value=NOW):
        time_service = TibberPricesDataUpdateCoordinator._create_time_service(stub)  # noqa: SLF001
    assert time_service.now() == NOW


@pytest.mark.unit
def test_intervals_after_the_end_are_dropped() -> None:
    """Market prices exist for days the contract does not cover; the home has none."""
    stub = _coordinator_stub(_subscription("2020-01-01T00:00:00+01:00", "2026-11-10T00:00:00+01:00", current=True))
    stub.time.now.return_value = NOW
    stub._starts_at_or_after = lambda starts_at, boundary: starts_at >= boundary  # noqa: SLF001
    last = datetime(2026, 11, 9, 23, 45, tzinfo=BERLIN)
    first_after = datetime(2026, 11, 10, 0, 0, tzinfo=BERLIN)
    raw = {"price_info": [{"startsAt": last}, {"startsAt": first_after}]}

    result = TibberPricesDataUpdateCoordinator._apply_subscription_window(stub, raw)  # noqa: SLF001

    assert result["price_info"] == [{"startsAt": last}]


@pytest.mark.unit
def test_phase_change_reloads_the_entry_once() -> None:
    """The price entities are created by a reload at the start of the contract - exactly one."""
    stub = Mock()
    stub.is_time_travel = False
    stub._reload_scheduled = False  # noqa: SLF001
    stub._created_pending = True  # noqa: SLF001
    stub.subscription_phase = PHASE_PENDING

    TibberPricesDataUpdateCoordinator._check_subscription_phase_change(stub)  # noqa: SLF001
    stub.hass.config_entries.async_schedule_reload.assert_not_called()

    stub.subscription_phase = PHASE_ACTIVE
    TibberPricesDataUpdateCoordinator._check_subscription_phase_change(stub)  # noqa: SLF001
    TibberPricesDataUpdateCoordinator._check_subscription_phase_change(stub)  # noqa: SLF001
    stub.hass.config_entries.async_schedule_reload.assert_called_once()


# --- lifecycle sensor ---------------------------------------------------------------


def _lifecycle_coordinator(phase: str) -> Mock:
    coordinator = Mock()
    coordinator.time = Mock()
    coordinator.time.now.return_value = NOW
    coordinator.time.as_local.side_effect = lambda dt: dt
    coordinator._is_fetching = False  # noqa: SLF001
    coordinator.last_exception = None
    coordinator._last_price_update = None  # noqa: SLF001
    coordinator.subscription_phase = phase
    return coordinator


@pytest.mark.unit
def test_lifecycle_state_awaiting_subscription() -> None:
    """Before the contract starts the lifecycle sensor says so instead of searching for data."""
    calculator = TibberPricesLifecycleCalculator(_lifecycle_coordinator(PHASE_PENDING))
    assert calculator.get_lifecycle_state() == "awaiting_subscription"
    assert calculator.get_next_api_poll_time() is None


@pytest.mark.unit
def test_lifecycle_state_subscription_ended() -> None:
    """After the end the clock stands at 23:45 - that must not read as 'searching tomorrow'."""
    coordinator = _lifecycle_coordinator(PHASE_ENDED)
    coordinator.time.now.return_value = datetime(2026, 11, 9, 23, 45, tzinfo=BERLIN)
    calculator = TibberPricesLifecycleCalculator(coordinator)
    assert calculator.get_lifecycle_state() == "subscription_ended"
    assert calculator.get_next_api_poll_time() is None


@pytest.mark.unit
def test_lifecycle_error_outranks_subscription_phase() -> None:
    """A failing request stays visible."""
    coordinator = _lifecycle_coordinator(PHASE_PENDING)
    coordinator.last_exception = Exception("boom")
    assert TibberPricesLifecycleCalculator(coordinator).get_lifecycle_state() == "error"


# --- review follow-ups ------------------------------------------------------------


@pytest.mark.unit
def test_awaiting_market_after_start_still_has_no_price_yet() -> None:
    """Right at validFrom Tibber may still say "awaiting market": no current price, no error."""
    started = _subscription("2020-01-01T00:00:00+01:00")  # status "awaiting market", no current
    manager = _manager()
    assert manager._validate_user_data(_user_data(started), HOME_ID) is True  # noqa: SLF001
    assert _manager(_user_data(started))._get_currency_for_home(HOME_ID) == "EUR"  # noqa: SLF001


@pytest.mark.unit
async def test_outdated_cache_is_kept_when_the_refresh_fails() -> None:
    """A failing refresh must not turn a usable cached copy into an update failure."""
    from custom_components.tibber_prices.api.exceptions import TibberPricesApiClientError  # noqa: PLC0415

    cached = _user_data(_subscription("2020-01-01T00:00:00+01:00", current=True))
    manager = _manager(cached)
    manager._validate_user_data = Mock(return_value=False)  # noqa: SLF001
    manager.api.async_get_viewer_details = AsyncMock(side_effect=TibberPricesApiClientError("down"))

    assert await manager._ensure_user_data(NOW) is False  # noqa: SLF001
    assert manager.cached_user_data == cached


@pytest.mark.unit
def test_binary_sensor_pending_set_leaves_out_price_dependent_sensors() -> None:
    """tomorrow_data_available has nothing to report before the contract starts."""
    from custom_components.tibber_prices.binary_sensor.definitions import PRICE_DEPENDENT_DIAGNOSTIC_KEYS  # noqa: PLC0415

    assert "tomorrow_data_available" in PRICE_DEPENDENT_DIAGNOSTIC_KEYS


@pytest.mark.unit
def test_config_flow_accepts_future_subscription_without_status() -> None:
    """A contract with a start date but no status yet is still a contract."""
    from custom_components.tibber_prices.config_flow_handlers.user_flow import TibberPricesConfigFlowHandler  # noqa: PLC0415

    home = {"currentSubscription": {"status": None, "validFrom": "2099-01-01T00:00:00+01:00"}}
    assert TibberPricesConfigFlowHandler._get_subscription_status(home) == "future"  # noqa: SLF001
    assert TibberPricesConfigFlowHandler._get_subscription_status({"currentSubscription": {"status": None}}) == "none"  # noqa: SLF001
