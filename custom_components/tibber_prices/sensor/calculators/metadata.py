"""Calculator for home metadata, metering point, and subscription data."""

from __future__ import annotations

from .base import TibberPricesBaseCalculator


class TibberPricesMetadataCalculator(TibberPricesBaseCalculator):
    """
    Calculator for home metadata, metering point, and subscription data.

    Handles sensors that expose static or slowly-changing user data from the
    Tibber API, such as home characteristics, metering point information, and
    subscription details.
    """

    def get_home_metadata_value(self, field: str) -> str | int | None:
        """
        Get home metadata value from user data.

        String values are converted to lowercase for ENUM device_class compatibility.

        Args:
            field: The metadata field name (e.g., "type", "size", "mainFuseSize").

        Returns:
            The field value, or None if not available.

        """
        user_homes = self.coordinator.get_user_homes()
        if not user_homes:
            return None

        # Find the home matching this sensor's home_id
        home_id = self.config_entry.data.get("home_id")
        if not home_id:
            return None

        home_data = next((home for home in user_homes if home.get("id") == home_id), None)
        if not home_data:
            return None

        value = home_data.get(field)

        # Convert string to lowercase for ENUM device_class
        if isinstance(value, str):
            return value.lower()

        return value

    def get_metering_point_value(self, field: str) -> str | int | None:
        """
        Get metering point data value from user data.

        Args:
            field: The metering point field name (e.g., "gridCompany", "priceAreaCode").

        Returns:
            The field value, or None if not available.

        """
        user_homes = self.coordinator.get_user_homes()
        if not user_homes:
            return None

        home_id = self.config_entry.data.get("home_id")
        if not home_id:
            return None

        home_data = next((home for home in user_homes if home.get("id") == home_id), None)
        if not home_data:
            return None

        metering_point = home_data.get("meteringPointData")
        if not metering_point:
            return None

        return metering_point.get(field)

    def get_subscription_value(self, field: str) -> str | None:
        """
        Get subscription value from user data.

        String values are converted to lowercase for ENUM device_class compatibility.

        Args:
            field: The subscription field name (e.g., "status").

        Returns:
            The field value, or None if not available.

        """
        user_homes = self.coordinator.get_user_homes()
        if not user_homes:
            return None

        home_id = self.config_entry.data.get("home_id")
        if not home_id:
            return None

        home_data = next((home for home in user_homes if home.get("id") == home_id), None)
        if not home_data:
            return None

        subscription = home_data.get("currentSubscription")
        if not subscription:
            return None

        value = subscription.get(field)

        # Convert string to lowercase for ENUM device_class
        if isinstance(value, str):
            return value.lower()

        return value
