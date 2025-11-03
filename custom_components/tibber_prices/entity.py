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

        # Get user profile information from coordinator
        user_profile = self.coordinator.get_user_profile()

        # Check if this is a main entry or subentry
        is_subentry = bool(self.coordinator.config_entry.data.get("home_id"))

        # Initialize variables
        home_name = "Tibber Home"
        home_id = self.coordinator.config_entry.unique_id
        home_type = None

        if is_subentry:
            # For subentries, show specific home information
            home_data = self.coordinator.config_entry.data.get("home_data", {})
            home_id = self.coordinator.config_entry.data.get("home_id")

            # Get home details
            address = home_data.get("address", {})
            address1 = address.get("address1", "")
            city = address.get("city", "")
            app_nickname = home_data.get("appNickname", "")
            home_type = home_data.get("type", "")

            # Compose home name
            home_name = app_nickname or address1 or f"Tibber Home {home_id}"
            if city:
                home_name = f"{home_name}, {city}"

            # Add user information if available
            if user_profile and user_profile.get("name"):
                home_name = f"{home_name} ({user_profile['name']})"
        elif user_profile:
            # For main entry, show user profile information
            user_name = user_profile.get("name", "Tibber User")
            user_email = user_profile.get("email", "")
            home_name = f"Tibber - {user_name}"
            if user_email:
                home_name = f"{home_name} ({user_email})"
        elif coordinator.data:
            # Fallback to original logic if user data not available yet
            try:
                address1 = str(coordinator.data.get("address", {}).get("address1", ""))
                city = str(coordinator.data.get("address", {}).get("city", ""))
                app_nickname = str(coordinator.data.get("appNickname", ""))
                home_type = str(coordinator.data.get("type", ""))
                # Compose a nice name
                home_name = "Tibber " + (app_nickname or address1 or "Home")
                if city:
                    home_name = f"{home_name}, {city}"
            except (KeyError, IndexError, TypeError):
                home_name = "Tibber Home"

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
