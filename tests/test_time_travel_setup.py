"""
Unit tests for the time-travel setup wiring in __init__.py.

Covers the control flow that decides how many coordinators exist and when the
config entry has to be reloaded - the parts that a pure data-level test would
miss.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.tibber_prices import _async_handle_subentry_change, _async_setup_subentries
from custom_components.tibber_prices.const import (
    CONF_HEADLESS,
    CONF_VIRTUAL_TIME_OFFSET_DAYS,
    CONF_VIRTUAL_TIME_OFFSET_HOURS,
    CONF_VIRTUAL_TIME_OFFSET_MINUTES,
)
from custom_components.tibber_prices.data import TibberPricesSubentryData
from custom_components.tibber_prices.time_travel import SUBENTRY_TYPE_TIME_TRAVEL

if TYPE_CHECKING:
    from collections.abc import Iterator

MODULE = "custom_components.tibber_prices"


def _make_subentry(
    subentry_id: str,
    days: int,
    subentry_type: str = SUBENTRY_TYPE_TIME_TRAVEL,
    *,
    headless: bool = False,
) -> Mock:
    """Build a config subentry mock."""
    subentry = Mock()
    subentry.subentry_id = subentry_id
    subentry.subentry_type = subentry_type
    subentry.title = f"View {subentry_id}"
    subentry.data = {
        CONF_VIRTUAL_TIME_OFFSET_DAYS: days,
        CONF_VIRTUAL_TIME_OFFSET_HOURS: 0,
        CONF_VIRTUAL_TIME_OFFSET_MINUTES: 0,
        CONF_HEADLESS: headless,
    }
    return subentry


def _make_entry(subentries: dict[str, Mock]) -> Mock:
    """Build a config entry mock holding the given subentries."""
    entry = Mock()
    entry.entry_id = "entry123"
    entry.title = "My House"
    entry.subentries = subentries
    entry.runtime_data = None
    return entry


@pytest.fixture
def stub_setup() -> Iterator[tuple[Mock, Mock]]:
    """Patch away pool creation and the coordinator so only the wiring is tested."""
    with (
        patch(f"{MODULE}._async_create_interval_pool", new_callable=AsyncMock) as pool_factory,
        patch(f"{MODULE}.TibberPricesDataUpdateCoordinator") as coordinator_cls,
    ):
        coordinator_cls.side_effect = lambda **kwargs: Mock(
            load_cache=AsyncMock(),
            time_offset="offset",
            subentry=kwargs.get("subentry"),
        )
        yield pool_factory, coordinator_cls


@pytest.mark.unit
async def test_one_coordinator_per_view(stub_setup: tuple[Mock, Mock]) -> None:
    """
    Test every time-travel subentry gets its own coordinator and pool.

    Scenario: An entry with two views and one unrelated subentry type.
    Expected: Two runtime entries, each built with its own subentry and its own
        pool - sharing a pool would make the views fight over the GC-protected
        range.
    """
    pool_factory, coordinator_cls = stub_setup
    pool_factory.side_effect = [Mock(name="pool_a"), Mock(name="pool_b")]

    entry = _make_entry(
        {
            "01JAAA": _make_subentry("01JAAA", -7),
            "01JBBB": _make_subentry("01JBBB", -14),
            "01JCCC": _make_subentry("01JCCC", -1, subentry_type="something_else"),
        }
    )

    views = await _async_setup_subentries(Mock(), entry, Mock(), "home-1")

    assert set(views) == {"01JAAA", "01JBBB"}
    assert pool_factory.await_count == 2
    assert views["01JAAA"].interval_pool is not views["01JBBB"].interval_pool
    assert coordinator_cls.call_args_list[0].kwargs["subentry"].subentry_id == "01JAAA"


@pytest.mark.unit
async def test_no_views_means_no_extra_coordinators(stub_setup: tuple[Mock, Mock]) -> None:
    """
    Test an entry without views stays exactly as before.

    Scenario: No subentries at all.
    Expected: No pools, no coordinators - the live setup path is untouched.
    """
    pool_factory, coordinator_cls = stub_setup

    views = await _async_setup_subentries(Mock(), _make_entry({}), Mock(), "home-1")

    assert views == {}
    assert pool_factory.await_count == 0
    assert coordinator_cls.call_count == 0


def _entry_with_runtime(subentries: dict[str, Mock]) -> Mock:
    """Build an entry whose runtime data matches its current subentries."""
    entry = _make_entry(subentries)
    entry.runtime_data = Mock(
        subentries={
            subentry_id: TibberPricesSubentryData(
                subentry=subentry,
                coordinator=Mock(),
                interval_pool=Mock(),
            )
            for subentry_id, subentry in subentries.items()
        }
    )
    return entry


@pytest.mark.unit
async def test_options_update_does_not_reload() -> None:
    """
    Test a plain options change does not trigger a reload.

    Scenario: The update listener fires but the subentry configuration is
        unchanged (an options update).
    Expected: No reload - the coordinator handles options in place, reloading
        would drop and rebuild every entity for nothing.
    """
    entry = _entry_with_runtime({"01JAAA": _make_subentry("01JAAA", -7)})
    hass = Mock()

    await _async_handle_subentry_change(hass, entry)

    hass.config_entries.async_schedule_reload.assert_not_called()


@pytest.mark.unit
async def test_added_view_triggers_reload() -> None:
    """
    Test adding a view reloads the entry.

    Scenario: A subentry exists that has no runtime coordinator yet.
    Expected: Reload, because coordinators and entities are wired up in setup.
    """
    entry = _entry_with_runtime({"01JAAA": _make_subentry("01JAAA", -7)})
    entry.subentries = dict(entry.subentries) | {"01JBBB": _make_subentry("01JBBB", -14)}
    hass = Mock()

    await _async_handle_subentry_change(hass, entry)

    hass.config_entries.async_schedule_reload.assert_called_once_with("entry123")


@pytest.mark.unit
async def test_changed_offset_reloads_and_drops_the_cache() -> None:
    """
    Test moving a view's offset reloads it and throws its cached window away.

    Scenario: Same subentry ID, different day offset than what was set up.
    Expected: Reload plus a storage purge - the view now points at a different
        stretch of history, so the old window is dead weight.
    """
    entry = _entry_with_runtime({"01JAAA": _make_subentry("01JAAA", -7)})
    entry.subentries = {"01JAAA": _make_subentry("01JAAA", -21)}
    hass = Mock()

    store = Mock(async_remove=AsyncMock())
    with (
        patch(f"{MODULE}.Store", return_value=store),
        patch(f"{MODULE}.async_remove_pool_storage", new_callable=AsyncMock) as remove_pool,
    ):
        await _async_handle_subentry_change(hass, entry)

    store.async_remove.assert_awaited_once()
    remove_pool.assert_awaited_once_with(hass, "entry123_01JAAA")
    hass.config_entries.async_schedule_reload.assert_called_once_with("entry123")


@pytest.mark.unit
async def test_presentation_change_keeps_the_cache() -> None:
    """
    Test toggling headless reloads without discarding data.

    Scenario: Same offset, headless flipped on.
    Expected: A reload (the entity set changes) but no purge - the view still
        needs exactly the same intervals, and refetching them would be waste.
    """
    entry = _entry_with_runtime({"01JAAA": _make_subentry("01JAAA", -7)})
    entry.subentries = {"01JAAA": _make_subentry("01JAAA", -7, headless=True)}
    hass = Mock()

    store = Mock(async_remove=AsyncMock())
    with (
        patch(f"{MODULE}.Store", return_value=store),
        patch(f"{MODULE}.async_remove_pool_storage", new_callable=AsyncMock) as remove_pool,
    ):
        await _async_handle_subentry_change(hass, entry)

    store.async_remove.assert_not_awaited()
    remove_pool.assert_not_awaited()
    hass.config_entries.async_schedule_reload.assert_called_once_with("entry123")


@pytest.mark.unit
async def test_removed_view_purges_its_storage() -> None:
    """
    Test deleting a view removes its cache and interval pool storage.

    Scenario: A configured view disappears from the entry.
    Expected: Its store is removed and the entry reloads - otherwise the
        storage would linger until the whole config entry is deleted.
    """
    entry = _entry_with_runtime({"01JAAA": _make_subentry("01JAAA", -7)})
    entry.subentries = {}
    hass = Mock()

    store = Mock(async_remove=AsyncMock())
    with (
        patch(f"{MODULE}.Store", return_value=store) as store_cls,
        patch(f"{MODULE}.async_remove_pool_storage", new_callable=AsyncMock) as remove_pool,
    ):
        await _async_handle_subentry_change(hass, entry)

    assert store_cls.call_args.args[2] == "tibber_prices.entry123.01JAAA"
    store.async_remove.assert_awaited_once()
    remove_pool.assert_awaited_once_with(hass, "entry123_01JAAA")
    hass.config_entries.async_schedule_reload.assert_called_once_with("entry123")


@pytest.mark.unit
async def test_headless_view_gets_diagnostic_sensors_only() -> None:
    """
    Test a headless view creates no price entities.

    Scenario: One normal and one headless view, both set up on the sensor
        platform.
    Expected: The headless view only receives diagnostic sensors. Its data is
        still fetched - the point is to avoid dozens of price entities per
        comparison view, not to stop collecting.
    """
    from custom_components.tibber_prices.sensor import async_setup_entry  # noqa: PLC0415
    from homeassistant.const import EntityCategory  # noqa: PLC0415

    entry = Mock()
    entry.options = {}
    entry.runtime_data = Mock(
        coordinator=Mock(headless=False),
        subentries={
            "01JNORMAL": Mock(subentry=Mock(), coordinator=Mock(headless=False)),
            "01JHEADLESS": Mock(subentry=Mock(), coordinator=Mock(headless=True)),
        },
    )

    added: dict[str | None, list] = {}

    def _add(entities, **kwargs) -> None:
        added.setdefault(kwargs.get("config_subentry_id"), []).extend(entities)

    await async_setup_entry(Mock(), entry, _add)

    headless = added["01JHEADLESS"]
    normal = added["01JNORMAL"]

    assert headless, "a headless view must still expose its diagnostic sensors"
    assert len(headless) < len(normal)
    assert all(e.entity_description.entity_category == EntityCategory.DIAGNOSTIC for e in headless)


@pytest.mark.unit
async def test_headless_view_gets_no_binary_sensors() -> None:
    """
    Test headless views are skipped entirely on the non-sensor platforms.

    Scenario: A headless view set up on the binary sensor platform.
    Expected: Nothing is added for it - binary sensors carry no diagnostics that
        would justify the clutter.
    """
    from custom_components.tibber_prices.binary_sensor import async_setup_entry  # noqa: PLC0415

    entry = Mock()
    entry.runtime_data = Mock(
        coordinator=Mock(headless=False),
        subentries={"01JHEADLESS": Mock(subentry=Mock(), coordinator=Mock(headless=True))},
    )

    added: dict[str | None, list] = {}

    def _add(entities, **kwargs) -> None:
        added.setdefault(kwargs.get("config_subentry_id"), []).extend(entities)

    await async_setup_entry(Mock(), entry, _add)

    assert "01JHEADLESS" not in added
    assert added[None], "the live entry still gets its binary sensors"


@pytest.mark.unit
async def test_disabling_the_entry_drops_caches() -> None:
    """
    Test disabling an entry throws its cached data away.

    Scenario: Home Assistant unloads the entry with disabled_by set.
    Expected: Pool storage removed and every coordinator's cache cleared. A
        disabled entry may stay off for weeks; whatever is cached now would be
        stale on the way back in.
    """
    from custom_components.tibber_prices import async_unload_entry  # noqa: PLC0415

    entry = _make_entry({})
    entry.disabled_by = "user"
    view_coordinator = Mock(async_shutdown=AsyncMock(), clear_cache=AsyncMock())
    entry.runtime_data = Mock(
        coordinator=Mock(async_shutdown=AsyncMock(), clear_cache=AsyncMock()),
        interval_pool=Mock(async_shutdown=AsyncMock()),
        subentries={
            "01JAAA": TibberPricesSubentryData(
                subentry=_make_subentry("01JAAA", -7),
                coordinator=view_coordinator,
                interval_pool=Mock(async_shutdown=AsyncMock()),
            )
        },
    )

    hass = Mock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass.config_entries.async_entries = Mock(return_value=[entry])

    with (
        patch(f"{MODULE}.async_remove_pool_storage", new_callable=AsyncMock) as remove_pool,
        patch(f"{MODULE}.async_save_pool_state", new_callable=AsyncMock) as save_pool,
    ):
        assert await async_unload_entry(hass, entry) is True

    assert save_pool.await_count == 0
    assert {call.args[1] for call in remove_pool.await_args_list} == {"entry123", "entry123_01JAAA"}
    entry.runtime_data.coordinator.clear_cache.assert_awaited_once()
    view_coordinator.clear_cache.assert_awaited_once()


@pytest.mark.unit
async def test_reload_keeps_caches() -> None:
    """
    Test a plain reload preserves the cached data.

    Scenario: The entry is unloaded without being disabled (reload, restart).
    Expected: Pool state saved, nothing cleared - surviving restarts is the
        whole point of the persistent store.
    """
    from custom_components.tibber_prices import async_unload_entry  # noqa: PLC0415

    entry = _make_entry({})
    entry.disabled_by = None
    entry.runtime_data = Mock(
        coordinator=Mock(async_shutdown=AsyncMock(), clear_cache=AsyncMock()),
        interval_pool=Mock(async_shutdown=AsyncMock()),
        subentries={},
    )

    hass = Mock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass.config_entries.async_entries = Mock(return_value=[entry])

    with (
        patch(f"{MODULE}.async_remove_pool_storage", new_callable=AsyncMock) as remove_pool,
        patch(f"{MODULE}.async_save_pool_state", new_callable=AsyncMock) as save_pool,
    ):
        assert await async_unload_entry(hass, entry) is True

    save_pool.assert_awaited_once()
    remove_pool.assert_not_awaited()
    entry.runtime_data.coordinator.clear_cache.assert_not_awaited()
