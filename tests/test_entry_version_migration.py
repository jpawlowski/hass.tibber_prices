"""Tests for the config entry version migration (1.0 -> 1.1: day_price_* in the display unit)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from custom_components.tibber_prices import migrations
from custom_components.tibber_prices.const import CONF_CURRENCY_DISPLAY_MODE, DISPLAY_MODE_BASE, DISPLAY_MODE_SUBUNIT


def _entry(minor: int, mode: str | None, version: int = 1) -> MagicMock:
    entry = MagicMock()
    entry.version = version
    entry.minor_version = minor
    entry.entry_id = "abc"
    entry.title = "Home"
    entry.options = {} if mode is None else {CONF_CURRENCY_DISPLAY_MODE: mode}
    return entry


@pytest.mark.unit
@pytest.mark.parametrize(
    ("mode", "notified"), [(DISPLAY_MODE_BASE, True), (DISPLAY_MODE_SUBUNIT, False), (None, False)]
)
def test_older_entry_is_migrated_and_base_currency_homes_are_told(mode: str | None, *, notified: bool) -> None:
    """Only homes showing the base currency see their day_price_* values change, and only they hear of it."""
    hass = MagicMock()
    with patch.object(migrations.ir, "async_create_issue") as create_issue:
        assert migrations.async_migrate_entry_version(hass, _entry(0, mode))

    assert create_issue.called is notified
    hass.config_entries.async_update_entry.assert_called_once()
    assert hass.config_entries.async_update_entry.call_args.kwargs == {"minor_version": 1}


@pytest.mark.unit
def test_current_entry_is_left_alone() -> None:
    """An entry already at 1.1 (or created there) gets neither a notice nor an update."""
    hass = MagicMock()
    with patch.object(migrations.ir, "async_create_issue") as create_issue:
        assert migrations.async_migrate_entry_version(hass, _entry(1, DISPLAY_MODE_BASE))

    create_issue.assert_not_called()
    hass.config_entries.async_update_entry.assert_not_called()


@pytest.mark.unit
def test_newer_major_version_cannot_be_migrated() -> None:
    """A config from a newer major version of the integration is refused."""
    assert not migrations.async_migrate_entry_version(MagicMock(), _entry(0, DISPLAY_MODE_BASE, version=2))


@pytest.mark.unit
def test_notices_can_be_confirmed() -> None:
    """A notice is fixable: HA offers to confirm it (and then deletes it) instead of only to ignore it."""
    with patch.object(migrations.ir, "async_create_issue") as create_issue:
        migrations.async_migrate_entry_version(MagicMock(), _entry(0, DISPLAY_MODE_BASE))

    assert create_issue.call_args.kwargs["is_fixable"] is True
    assert create_issue.call_args.kwargs["translation_key"] in migrations.NOTICES


@pytest.mark.unit
def test_ignored_notices_of_the_entry_are_cleared() -> None:
    """Notices ignored before they could be confirmed leave the registry; open ones and others stay."""

    def issue(key: str, *, dismissed: bool) -> MagicMock:
        return MagicMock(
            translation_key=key, dismissed_version="2026.10.0" if dismissed else None, active=True, is_fixable=True
        )

    registry = MagicMock()
    registry.issues = {
        ("tibber_prices", "entity_migration_abc"): issue("entity_migration", dismissed=True),
        ("tibber_prices", "period_day_price_unit_abc"): issue("period_day_price_unit", dismissed=False),
        ("tibber_prices", "entity_migration_other"): issue("entity_migration", dismissed=True),
        ("tibber_prices", "home_not_found_abc"): issue("home_not_found", dismissed=True),
    }
    with (
        patch.object(migrations.ir, "async_get", return_value=registry),
        patch.object(migrations.ir, "async_delete_issue") as delete_issue,
    ):
        migrations._tidy_notices(MagicMock(), _entry(1, None))  # noqa: SLF001

    assert [call.args[2] for call in delete_issue.call_args_list] == ["entity_migration_abc"]


@pytest.mark.unit
def test_open_notices_stored_as_not_fixable_become_fixable() -> None:
    """A notice an older version created as not fixable is made fixable, keeping what it says."""
    old = MagicMock(
        translation_key="entity_migration",
        dismissed_version=None,
        active=True,
        is_fixable=False,
        is_persistent=True,
        translation_placeholders={"home_name": "Home"},
        learn_more_url="https://example.org",
    )
    registry = MagicMock()
    registry.issues = {("tibber_prices", "entity_migration_abc"): old}
    with (
        patch.object(migrations.ir, "async_get", return_value=registry),
        patch.object(migrations.ir, "async_create_issue") as create_issue,
        patch.object(migrations.ir, "async_delete_issue") as delete_issue,
    ):
        migrations._tidy_notices(MagicMock(), _entry(1, None))  # noqa: SLF001

    delete_issue.assert_not_called()
    assert create_issue.call_args.args[2] == "entity_migration_abc"
    assert create_issue.call_args.kwargs["is_fixable"] is True
    assert create_issue.call_args.kwargs["translation_placeholders"] == {"home_name": "Home"}
