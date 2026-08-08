"""
Unit tests for the shared device info builder.

Covers the three entry shapes (home entry, account entry, fallback) and the
per-subentry device that the Home Assistant 2026.8 device registry model
requires: one device per config entry plus one device per config subentry, with
identifiers scoped per entry.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
import yaml

from custom_components.tibber_prices.const import DOMAIN, INTEGRATION_VERSION
from custom_components.tibber_prices.device import (
    VIEW_MODEL_ID,
    build_device_info,
    device_identifier,
    resolve_home_identity,
)

HOME_ID = "c70dcbe5-4485-4821-933d-a8a86452737b"


def _make_coordinator(
    *,
    entry_data: dict[str, Any] | None = None,
    unique_id: str | None = "user-123",
    entry_id: str = "01JENTRYID",
    user_profile: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    language: str = "en",
) -> Mock:
    """Build a coordinator mock with just enough surface for device.py."""
    coordinator = Mock()
    coordinator.config_entry = Mock()
    coordinator.config_entry.data = entry_data or {}
    coordinator.config_entry.unique_id = unique_id
    coordinator.config_entry.entry_id = entry_id
    coordinator.hass.config.language = language
    coordinator.get_user_profile.return_value = user_profile
    coordinator.data = data
    return coordinator


def _make_subentry(subentry_id: str = "01JSUBENTRY", title: str = "My House (7 days ago)") -> Mock:
    """Build a config subentry mock."""
    subentry = Mock()
    subentry.subentry_id = subentry_id
    subentry.title = title
    return subentry


@pytest.mark.unit
def test_home_entry_uses_app_nickname() -> None:
    """
    Test a home entry is named after its Tibber app nickname.

    Scenario: Entry data carries home_id and home_data with appNickname.
    Expected: Nickname is the device name, home_id becomes the serial number.
    """
    coordinator = _make_coordinator(
        entry_data={
            "home_id": HOME_ID,
            "home_data": {
                "appNickname": "  My House  ",
                "address": {"address1": "Kungsgatan 1", "city": "Stockholm"},
                "type": "HOUSE",
            },
        }
    )

    device_info = build_device_info(coordinator)

    assert device_info.get("name") == "My House"
    assert device_info.get("serial_number") == HOME_ID
    assert device_info.get("identifiers") == {(DOMAIN, "user-123")}
    assert device_info.get("sw_version") == INTEGRATION_VERSION


@pytest.mark.unit
def test_home_entry_falls_back_to_address() -> None:
    """
    Test a home entry without nickname is named after its address.

    Scenario: home_data has an address but no appNickname.
    Expected: Device name is "<address1>, <city>".
    """
    coordinator = _make_coordinator(
        entry_data={
            "home_id": HOME_ID,
            "home_data": {
                "address": {"address1": "Kungsgatan 1", "city": "Stockholm"},
                "type": "APARTMENT",
            },
        }
    )

    name, home_id, home_type = resolve_home_identity(coordinator)

    assert name == "Kungsgatan 1, Stockholm"
    assert home_id == HOME_ID
    assert home_type == "APARTMENT"


@pytest.mark.unit
def test_account_entry_uses_user_profile() -> None:
    """
    Test an account entry is named after the Tibber user profile.

    Scenario: Entry has no home_id, but the coordinator knows the user profile.
    Expected: Device name combines user name and email.
    """
    coordinator = _make_coordinator(
        user_profile={"name": "Arya Stark", "email": "arya@example.com"},
    )

    device_info = build_device_info(coordinator)

    assert device_info.get("name") == "Tibber - Arya Stark (arya@example.com)"
    assert device_info.get("serial_number") == "user-123"


@pytest.mark.unit
def test_fallback_without_any_data() -> None:
    """
    Test the fallback name when neither home data nor user profile exist.

    Scenario: Fresh entry, coordinator has not fetched anything yet.
    Expected: Generic name and "Unknown" model, never a crash.
    """
    coordinator = _make_coordinator(unique_id=None)

    device_info = build_device_info(coordinator)

    assert device_info.get("name") == "Tibber Home"
    assert device_info.get("model") == "Unknown"
    # No unique_id yet -> identifier falls back to the entry_id
    assert device_info.get("identifiers") == {(DOMAIN, "01JENTRYID")}


@pytest.mark.unit
def test_subentry_gets_its_own_device() -> None:
    """
    Test a config subentry produces a device separate from its parent entry.

    Scenario: Same coordinator, once without and once with a subentry.
    Expected: Different identifiers (HA 2026.8 scopes identifiers per entry)
        and the subentry device is named after the subentry title.
    """
    coordinator = _make_coordinator(
        entry_data={
            "home_id": HOME_ID,
            "home_data": {"appNickname": "My House", "type": "HOUSE"},
        }
    )
    subentry = _make_subentry()

    parent = build_device_info(coordinator)
    child = build_device_info(coordinator, subentry)

    assert parent.get("identifiers") != child.get("identifiers")
    assert child.get("identifiers") == {(DOMAIN, "user-123_01JSUBENTRY")}
    assert child.get("name") == "My House (7 days ago)"
    # Everything else stays inherited from the parent home
    assert child.get("serial_number") == parent.get("serial_number")
    assert child.get("model") == parent.get("model")


@pytest.mark.unit
def test_only_view_devices_carry_the_view_model_id() -> None:
    """Test model_id marks a device as a view, and only a view.

    Scenario: Same coordinator, once without and once with a subentry.
    Expected: The view carries VIEW_MODEL_ID, the home carries none.

    This is what the `view` device selector in services.yaml filters on - `model` is
    the home type and identical for both, so it cannot tell them apart. If the marker
    stopped being set, the picker would silently offer nothing to choose.
    """
    coordinator = _make_coordinator(
        entry_data={
            "home_id": HOME_ID,
            "home_data": {"appNickname": "My House", "type": "HOUSE"},
        }
    )

    home = build_device_info(coordinator)
    view = build_device_info(coordinator, _make_subentry())

    assert view.get("model_id") == VIEW_MODEL_ID
    assert home.get("model_id") is None


@pytest.mark.unit
def test_services_yaml_view_selector_filters_on_the_view_marker() -> None:
    """Test the shipped selector filters on exactly the marker the code sets.

    The two live in different files and different languages; a typo in either would
    only surface as an empty picker at runtime.
    """
    services = yaml.safe_load(
        (Path(__file__).parent.parent / "custom_components/tibber_prices/services.yaml").read_text(encoding="utf-8")
    )

    def view_fields(node: dict) -> list[dict]:
        found = []
        for key, value in (node.get("fields") or {}).items():
            if isinstance(value, dict) and "fields" in value:
                found.extend(view_fields(value))
            elif key == "view_id":
                found.append(value)
        return found

    selectors = [field["selector"]["device"] for service in services.values() for field in view_fields(service)]

    assert selectors, "no action offers a view selector"
    for selector in selectors:
        assert selector["filter"] == [{"integration": DOMAIN, "model_id": VIEW_MODEL_ID}]


@pytest.mark.unit
def test_device_identifier_scopes_unique_ids() -> None:
    """
    Test device_identifier() is usable as a unique_id prefix.

    Scenario: Parent entry and subentry ask for their identifier.
    Expected: The subentry identifier extends the parent's, so entity unique
        IDs built from it cannot collide.
    """
    coordinator = _make_coordinator()
    subentry = _make_subentry()

    parent_id = device_identifier(coordinator)
    child_id = device_identifier(coordinator, subentry)

    assert parent_id == "user-123"
    assert child_id.startswith(f"{parent_id}_")
    assert child_id != parent_id


@pytest.mark.unit
def test_all_platforms_share_one_device() -> None:
    """
    Test sensor, number and switch entities report the same device.

    Scenario: The three entity base classes build their device info for the
        same coordinator.
    Expected: Identical DeviceInfo - they must not create competing devices or
        overwrite each other's device name in the registry.
    """
    from custom_components.tibber_prices.entity import TibberPricesEntity  # noqa: PLC0415
    from custom_components.tibber_prices.number.core import TibberPricesConfigNumber  # noqa: PLC0415
    from custom_components.tibber_prices.switch.core import TibberPricesConfigSwitch  # noqa: PLC0415

    coordinator = _make_coordinator(
        entry_data={
            "home_id": HOME_ID,
            "home_data": {"appNickname": "My House", "type": "HOUSE"},
        }
    )

    number = TibberPricesConfigNumber.__new__(TibberPricesConfigNumber)
    switch = TibberPricesConfigSwitch.__new__(TibberPricesConfigSwitch)
    number.coordinator = coordinator
    switch.coordinator = coordinator
    number.subentry = None
    switch.subentry = None
    number._setup_device_info()  # noqa: SLF001
    switch._setup_device_info()  # noqa: SLF001

    entity = TibberPricesEntity(coordinator)

    assert entity.device_info == number._attr_device_info  # noqa: SLF001
    assert entity.device_info == switch._attr_device_info  # noqa: SLF001
    assert entity.device_info == build_device_info(coordinator)
