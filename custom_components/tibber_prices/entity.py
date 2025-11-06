"""TibberPricesEntity class."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, get_home_type_translation
from .coordinator import TibberPricesDataUpdateCoordinator


class TibberPricesEntity(CoordinatorEntity[TibberPricesDataUpdateCoordinator]):
    """TibberPricesEntity class."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(self, coordinator: TibberPricesDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)

        # Get device information
        home_name, home_id, home_type = self._get_device_info()

        # Get translated home type using the configured language
        language = coordinator.hass.config.language or "en"
        translated_model = get_home_type_translation(home_type, language) if home_type else "Unknown"

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={
                (
                    DOMAIN,
                    coordinator.config_entry.unique_id or coordinator.config_entry.entry_id,
                )
            },
            name=home_name,
            manufacturer="Tibber",
            model=translated_model,
            model_id=home_type if home_type else None,
            serial_number=home_id if home_id else None,
            configuration_url="https://developer.tibber.com/explorer",
        )

    def _get_device_info(self) -> tuple[str, str | None, str | None]:
        """Get device name, ID and type."""
        user_profile = self.coordinator.get_user_profile()
        is_subentry = bool(self.coordinator.config_entry.data.get("home_id"))
        home_id = self.coordinator.config_entry.unique_id
        home_type = None

        if is_subentry:
            home_name, home_id, home_type = self._get_subentry_device_info()
            # Add user information if available
            if user_profile and user_profile.get("name"):
                home_name = f"{home_name} ({user_profile['name']})"
        elif user_profile:
            home_name = self._get_main_entry_device_info(user_profile)
        else:
            home_name, home_type = self._get_fallback_device_info()

        return home_name, home_id, home_type

    def _get_subentry_device_info(self) -> tuple[str, str | None, str | None]:
        """Get device info for subentry."""
        home_data = self.coordinator.config_entry.data.get("home_data", {})
        home_id = self.coordinator.config_entry.data.get("home_id")

        # Get home details
        address = home_data.get("address", {})
        address1 = address.get("address1", "")
        city = address.get("city", "")
        app_nickname = home_data.get("appNickname", "")
        home_type = home_data.get("type", "")

        # Compose home name
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
            home_name = f"Tibber Home {home_id}"

        return home_name, home_id, home_type

    def _get_main_entry_device_info(self, user_profile: dict) -> str:
        """Get device info for main entry."""
        user_name = user_profile.get("name", "Tibber User")
        user_email = user_profile.get("email", "")
        home_name = f"Tibber - {user_name}"
        if user_email:
            home_name = f"{home_name} ({user_email})"
        return home_name

    def _get_fallback_device_info(self) -> tuple[str, str | None]:
        """Get fallback device info if user data not available yet."""
        if not self.coordinator.data:
            return "Tibber Home", None

        try:
            address1 = str(self.coordinator.data.get("address", {}).get("address1", ""))
            city = str(self.coordinator.data.get("address", {}).get("city", ""))
            app_nickname = str(self.coordinator.data.get("appNickname", ""))
            home_type = str(self.coordinator.data.get("type", ""))

            # Compose a nice name
            if app_nickname and app_nickname.strip():
                home_name = f"Tibber {app_nickname.strip()}"
            elif address1:
                home_name = f"Tibber {address1}"
                if city:
                    home_name = f"{home_name}, {city}"
            else:
                home_name = "Tibber Home"
        except (KeyError, IndexError, TypeError):
            return "Tibber Home", None
        else:
            return home_name, home_type
