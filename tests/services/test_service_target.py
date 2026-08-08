"""
Tests for resolving what a service call operates on.

A call targets either a home or one of its time-travel views. A view runs its own
coordinator on a clock trailing real time and keeps its own interval pool, so the
target decides three things at once: which clock defines "now", which pool the prices
come from, and which coordinator data the periods were built from. Getting any of them
from the live entry while the others come from the view would silently mix timelines.

Views are addressed by device, because that is what a user picks; subentry IDs are
internal.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from custom_components.tibber_prices.services.helpers import ServiceTarget, resolve_search_range, resolve_service_target
from homeassistant.exceptions import ServiceValidationError

BERLIN = ZoneInfo("Europe/Berlin")

LIVE_NOW = datetime(2026, 7, 27, 14, 47, 0, 167996, tzinfo=BERLIN)
VIEW_OFFSET = timedelta(days=7)


def _coordinator(now: datetime, *, headless: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        time=SimpleNamespace(now=lambda: now),
        data={"priceInfo": [{"marker": "from-this-coordinator"}]},
        headless=headless,
    )


def _entry(views: dict[str, Any] | None = None) -> SimpleNamespace:
    live = _coordinator(LIVE_NOW)
    return SimpleNamespace(
        entry_id="entry_1",
        title="My House",
        runtime_data=SimpleNamespace(
            coordinator=live,
            interval_pool="live-pool",
            subentries=views or {},
        ),
    )


def _view(subentry_id: str = "sub_1", *, headless: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        subentry=SimpleNamespace(subentry_id=subentry_id, title="7 days ago"),
        coordinator=_coordinator(LIVE_NOW - VIEW_OFFSET, headless=headless),
        interval_pool="view-pool",
    )


def _hass(entry: SimpleNamespace) -> MagicMock:
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = [entry]
    return hass


def _device(entry_id: str | None = "entry_1", subentry_id: str | None = "sub_1") -> SimpleNamespace | None:
    if entry_id is None:
        return None
    return SimpleNamespace(config_entry_id=entry_id, config_subentry_id=subentry_id)


def _resolve(hass: MagicMock, entry_id: str = "", view: str = "", device: Any = ...) -> ServiceTarget:
    """Resolve a target with the device registry stubbed to return `device`."""
    registry = MagicMock()
    registry.async_get.return_value = _device() if device is ... else device
    with patch(
        "custom_components.tibber_prices.services.helpers.dr.async_get",
        return_value=registry,
    ):
        return resolve_service_target(hass, entry_id, view)


class TestTargetingTheHome:
    """Without a view, a call resolves to the home's own live data."""

    def test_no_view_resolves_to_live(self) -> None:
        """The live coordinator, pool and data are used."""
        entry = _entry()
        target = _resolve(_hass(entry), device=None)

        assert target.is_view is False
        assert target.subentry is None
        assert target.interval_pool == "live-pool"
        assert target.coordinator is entry.runtime_data.coordinator

    def test_home_device_also_means_live(self) -> None:
        """Picking the home's own device is not an error - it is the live data.

        The device picker offers it alongside the views, and a user selecting it
        plainly means "not a view".
        """
        entry = _entry({"sub_1": _view()})
        target = _resolve(_hass(entry), view="device_home", device=_device(subentry_id=None))

        assert target.is_view is False
        assert target.interval_pool == "live-pool"


class TestTargetingAView:
    """A view swaps the clock, the pool and the coordinator data together."""

    def test_view_device_resolves_to_the_view(self) -> None:
        """All three inputs come from the view, none from the live entry."""
        view = _view()
        entry = _entry({"sub_1": view})

        target = _resolve(_hass(entry), view="device_view")

        assert target.is_view is True
        assert target.subentry is view.subentry
        assert target.interval_pool == "view-pool"
        assert target.coordinator is view.coordinator
        assert target.entry is entry, "the entry stays the home, only the data source shifts"

    def test_view_clock_trails_real_time(self) -> None:
        """ "Now" for a view is its own shifted clock."""
        entry = _entry({"sub_1": _view()})

        target = _resolve(_hass(entry), view="device_view")

        assert target.now(BERLIN) == LIVE_NOW - VIEW_OFFSET

    def test_entry_id_may_be_omitted_when_a_view_is_given(self) -> None:
        """The view's device identifies the entry, so passing it again is optional."""
        entry = _entry({"sub_1": _view()})

        target = _resolve(_hass(entry), view="device_view")

        assert target.entry is entry

    def test_label_names_both_home_and_view(self) -> None:
        """Logs and errors identify which view answered."""
        entry = _entry({"sub_1": _view()})

        assert _resolve(_hass(entry), view="device_view").label == "My House / 7 days ago"
        assert _resolve(_hass(entry), device=None).label == "My House"


class TestTargetingErrors:
    """Ambiguous or unusable targets are rejected rather than guessed at."""

    def test_unknown_device_is_rejected(self) -> None:
        """A device Home Assistant does not know cannot be resolved."""
        with pytest.raises(ServiceValidationError):
            _resolve(_hass(_entry()), view="device_gone", device=None)

    def test_mismatched_entry_and_view_is_rejected(self) -> None:
        """A view belonging to another home must not silently win over entry_id.

        Resolving in favour of either one would answer for a home the caller did not
        ask about.
        """
        entry = _entry({"sub_1": _view()})

        with pytest.raises(ServiceValidationError):
            _resolve(_hass(entry), entry_id="entry_other", view="device_view")

    def test_view_that_is_not_set_up_is_rejected(self) -> None:
        """A device can outlive its view - the removed view has no data to answer with."""
        entry = _entry(views={})

        with pytest.raises(ServiceValidationError):
            _resolve(_hass(entry), view="device_view")


class TestViewClockDrivesSearchRanges:
    """The whole point of targeting a view: relative ranges follow its clock."""

    def test_relative_scope_is_relative_to_the_view(self) -> None:
        """ "Next 24h" on a view means the view's next 24 hours, a week ago."""
        entry = _entry({"sub_1": _view()})
        target = _resolve(_hass(entry), view="device_view")

        start, end = resolve_search_range({"search_scope": "next_24h"}, target.now(BERLIN), BERLIN)

        # 14:47:00.167996 a week back, floored onto the grid
        assert start == datetime(2026, 7, 20, 14, 45, tzinfo=BERLIN)
        assert end == datetime(2026, 7, 21, 15, 0, tzinfo=BERLIN)

    def test_default_range_ends_at_the_views_tomorrow(self) -> None:
        """With no range given, "end of tomorrow" is the view's tomorrow, not the real one."""
        entry = _entry({"sub_1": _view()})
        target = _resolve(_hass(entry), view="device_view")

        _start, end = resolve_search_range({}, target.now(BERLIN), BERLIN)

        assert end == datetime(2026, 7, 22, 0, 0, tzinfo=BERLIN)

    def test_live_and_view_ranges_differ_by_the_offset(self) -> None:
        """The same call against live and against a view differ by exactly the offset."""
        entry = _entry({"sub_1": _view()})
        live = _resolve(_hass(entry), device=None)
        view = _resolve(_hass(entry), view="device_view")

        live_start, _ = resolve_search_range({"search_scope": "next_24h"}, live.now(BERLIN), BERLIN)
        view_start, _ = resolve_search_range({"search_scope": "next_24h"}, view.now(BERLIN), BERLIN)

        assert live_start - view_start == VIEW_OFFSET


class TestHeadlessViews:
    """A headless view has data but no entities."""

    def test_headless_view_is_a_valid_target(self) -> None:
        """Data-returning actions must work on it - that is what it is for."""
        entry = _entry({"sub_1": _view(headless=True)})

        target = _resolve(_hass(entry), view="device_view")

        assert target.is_view is True
        assert target.interval_pool == "view-pool"
        assert target.coordinator.headless is True


def test_service_target_time_is_the_targets_coordinator_clock() -> None:
    """The clock is read from the target's coordinator, never from real time."""
    coordinator = _coordinator(datetime(2020, 1, 1, tzinfo=UTC))
    target = ServiceTarget(
        entry=SimpleNamespace(title="x"),
        subentry=None,
        coordinator=coordinator,
        interval_pool="pool",
        data={},
    )

    assert target.time is coordinator.time
    assert target.now(UTC) == datetime(2020, 1, 1, tzinfo=UTC)
