"""
Device registry helpers for the Tibber Prices integration.

Single source of truth for the ``DeviceInfo`` of every Tibber Prices entity.
Sensors, binary sensors, numbers and switches all build their device through
:func:`build_device_info`, so all entities of an entry report exactly the same
device. Previously each platform carried its own copy of this logic and the
copies had drifted apart (different name composition, missing ``sw_version``).

Device model
------------
Home Assistant 2026.8 made a device belong to exactly one config entry and to
at most one config subentry, with identifiers scoped per config entry instead
of globally. See:
https://developers.home-assistant.io/blog/2026/07/21/device-registry-single-config-entry/

Mapped onto this integration:

* One service device per config entry - the Tibber account entry, or a single
  home entry.
* One additional service device per config subentry (a time-travel view). It
  carries its own identifier derived from the parent entry, so it can never
  merge with the parent device.

Registering subentry entities
-----------------------------
Building a subentry ``DeviceInfo`` is only half of it: the entity itself must
be handed to Home Assistant with the owning subentry, otherwise the device ends
up on the config entry and HA reports "devices that don't belong to a
sub-entry"::

    async_add_entities(entities, config_subentry_id=subentry.subentry_id)

That heading is not a fault report on its own: Home Assistant renders it for
every entry that owns devices *and* has subentries, so the parent entry's home
device belongs there and always will. Only a *view* device showing up under it
points at a missing ``config_subentry_id``.

Entity ``unique_id``s of subentry entities must likewise be scoped with
:func:`device_identifier`, or they collide with the parent entry's entities.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from .const import DOMAIN, INTEGRATION_VERSION, get_home_type_translation

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.config_entries import ConfigEntry, ConfigSubentry

    from .coordinator import TibberPricesDataUpdateCoordinator

MANUFACTURER = "Tibber"
CONFIGURATION_URL = "https://developer.tibber.com/explorer"
DEFAULT_HOME_NAME = "Tibber Home"
UNKNOWN_MODEL = "Unknown"

# Which timeline a device shows. `model` carries the home type and is the same for a
# home and its views, so this is what tells them apart - both on the device page and to
# the `view_id` device selector in services.yaml, which filters on it to offer views
# without also listing every home device.
#
# These are shown to the user on the device page, so they read as labels rather than as
# the slug a filter key invites. They must stay untranslated: a selector filter is
# static configuration and cannot follow the user's language. The Data Mode diagnostic
# sensor reports the same distinction in translated form.
LIVE_MODEL_ID = "Live"
VIEW_MODEL_ID = "Time-Travel View"


def device_identifier(
    coordinator: TibberPricesDataUpdateCoordinator,
    subentry: ConfigSubentry | None = None,
) -> str:
    """
    Return the identifier that scopes a device (and its entities) to an entry.

    Args:
        coordinator: Coordinator owning the config entry.
        subentry: Optional config subentry. When given, the identifier is
            scoped to that subentry so it never collides with the parent
            entry's device.

    Returns:
        Identifier string, used both as device identifier and as prefix for
        entity unique IDs.

    """
    config_entry = coordinator.config_entry
    base = config_entry.unique_id or config_entry.entry_id
    if subentry is None:
        return base
    return f"{base}_{subentry.subentry_id}"


def entity_unique_id(base: str, key: str, subentry: ConfigSubentry | None = None) -> str:
    """
    Compose an entity unique ID, scoped to a subentry when there is one.

    Platforms differ in what they use as base (entry ID vs. the entry's unique
    ID); this only inserts the subentry scope, so unique IDs of existing
    entities stay byte-identical as long as no subentry is involved.

    Args:
        base: Platform-specific prefix, usually the config entry ID.
        key: Entity description key.
        subentry: Time-travel subentry, or None for the live entry.

    Returns:
        Collision-free unique ID.

    """
    if subentry is not None:
        base = f"{base}_{subentry.subentry_id}"
    return f"{base}_{key}"


def build_device_info(
    coordinator: TibberPricesDataUpdateCoordinator,
    subentry: ConfigSubentry | None = None,
) -> DeviceInfo:
    """
    Build the ``DeviceInfo`` for an entity of this config entry or subentry.

    Args:
        coordinator: Coordinator owning the config entry.
        subentry: Optional config subentry the entity belongs to. Its device is
            separate from the parent entry's device and named after the
            subentry title.

    Returns:
        DeviceInfo for a service device.

    """
    home_name, home_id, home_type = resolve_home_identity(coordinator)

    language = coordinator.hass.config.language or "en"
    model = get_home_type_translation(home_type, language) if home_type else UNKNOWN_MODEL

    if subentry is not None:
        home_name = subentry.title or home_name

    return DeviceInfo(
        entry_type=DeviceEntryType.SERVICE,
        identifiers={(DOMAIN, device_identifier(coordinator, subentry))},
        name=home_name,
        manufacturer=MANUFACTURER,
        model=model,
        model_id=VIEW_MODEL_ID if subentry is not None else LIVE_MODEL_ID,
        serial_number=home_id or None,
        sw_version=INTEGRATION_VERSION,
        configuration_url=CONFIGURATION_URL,
    )


def home_display_name(config_entry: ConfigEntry) -> str:
    """
    Return the name a home's device carries, from the config entry alone.

    Same source as :func:`build_device_info`, reachable without a coordinator so the
    subentry config flow can name a view after the home rather than after the config
    entry title. Those two differ whenever the home has an app nickname: the entry
    title is the address, while the device shows the nickname. A view named from the
    entry title therefore did not match the home device it belongs to.

    Args:
        config_entry: The home's config entry.

    Returns:
        The home's display name. Falls back to the entry title for an entry that is
        not a home - which cannot own views, so this is defensive only.

    """
    if config_entry.data.get("home_id"):
        return _home_entry_identity(config_entry.data)[0]
    return config_entry.title


def resolve_home_identity(
    coordinator: TibberPricesDataUpdateCoordinator,
) -> tuple[str, str | None, str | None]:
    """
    Resolve the display name, home ID and home type behind a config entry.

    Three shapes of entry exist: a home entry (carries ``home_id`` in its
    data), an account entry (identified through the user profile) and an entry
    whose data has not been fetched yet (fallback).

    Args:
        coordinator: Coordinator owning the config entry.

    Returns:
        Tuple of (display name, home ID or None, home type or None).

    """
    config_entry = coordinator.config_entry
    home_id: str | None = config_entry.unique_id
    home_type: str | None = None

    if config_entry.data.get("home_id"):
        return _home_entry_identity(config_entry.data)

    user_profile = coordinator.get_user_profile()
    if user_profile:
        return _account_entry_name(user_profile), home_id, home_type

    home_name, home_type = _fallback_identity(coordinator)
    return home_name, home_id, home_type


def _home_entry_identity(entry_data: Mapping[str, Any]) -> tuple[str, str | None, str | None]:
    """Resolve identity for an entry that represents a single Tibber home."""
    home_data = entry_data.get("home_data", {})
    home_id = entry_data.get("home_id")

    address = home_data.get("address", {})
    address1 = address.get("address1", "")
    city = address.get("city", "")
    app_nickname = home_data.get("appNickname", "")
    home_type = home_data.get("type", "")

    if app_nickname and app_nickname.strip():
        # If appNickname is set, use it as-is (don't add city)
        home_name = app_nickname.strip()
    elif address1:
        # If no appNickname, use address and optionally add city
        home_name = address1
        if city:
            home_name = f"{home_name}, {city}"
    else:
        # Fallback to home ID
        home_name = f"{DEFAULT_HOME_NAME} {home_id}"

    return home_name, home_id, home_type


def _account_entry_name(user_profile: dict) -> str:
    """Resolve the display name for an entry that represents a Tibber account."""
    user_name = user_profile.get("name", "Tibber User")
    user_email = user_profile.get("email", "")
    home_name = f"Tibber - {user_name}"
    if user_email:
        home_name = f"{home_name} ({user_email})"
    return home_name


def _fallback_identity(
    coordinator: TibberPricesDataUpdateCoordinator,
) -> tuple[str, str | None]:
    """Resolve identity from coordinator data when user data is not available yet."""
    if not coordinator.data:
        return DEFAULT_HOME_NAME, None

    try:
        # Use 'or {}' to handle None values (API may return None during maintenance)
        address = coordinator.data.get("address") or {}
        address1 = str(address.get("address1", ""))
        city = str(address.get("city", ""))
        app_nickname = str(coordinator.data.get("appNickname", ""))
        home_type = str(coordinator.data.get("type", ""))

        # Compose a nice name
        if app_nickname and app_nickname.strip():
            home_name = f"Tibber {app_nickname.strip()}"
        elif address1:
            home_name = f"Tibber {address1}"
            if city:
                home_name = f"{home_name}, {city}"
        else:
            home_name = DEFAULT_HOME_NAME
    except KeyError, IndexError, TypeError:
        return DEFAULT_HOME_NAME, None
    else:
        return home_name, home_type
