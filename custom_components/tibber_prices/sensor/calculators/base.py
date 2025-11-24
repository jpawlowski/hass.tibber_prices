"""Base calculator class for all Tibber Prices sensor calculators."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from custom_components.tibber_prices.coordinator.helpers import (
    get_intervals_for_day_offsets,
)

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator import (
        TibberPricesDataUpdateCoordinator,
    )
    from custom_components.tibber_prices.data import TibberPricesConfigEntry
    from homeassistant.core import HomeAssistant


class TibberPricesBaseCalculator:
    """
    Base class for all sensor value calculators.

    Provides common access patterns to coordinator data and configuration.
    All specialized calculators should inherit from this class.
    """

    def __init__(self, coordinator: TibberPricesDataUpdateCoordinator) -> None:
        """
        Initialize the calculator.

        Args:
            coordinator: The data update coordinator providing price and user data.

        """
        self._coordinator = coordinator

    @property
    def coordinator(self) -> TibberPricesDataUpdateCoordinator:
        """Get the coordinator instance."""
        return self._coordinator

    @property
    def hass(self) -> HomeAssistant:
        """Get Home Assistant instance."""
        return self._coordinator.hass

    @property
    def config_entry(self) -> TibberPricesConfigEntry:
        """Get config entry."""
        return self._coordinator.config_entry

    @property
    def config(self) -> Any:
        """Get configuration options."""
        return self.config_entry.options

    @property
    def coordinator_data(self) -> dict[str, Any]:
        """Get full coordinator data."""
        return self._coordinator.data

    @property
    def price_info(self) -> list[dict[str, Any]]:
        """Get price info (intervals list) from coordinator data."""
        return self.coordinator_data.get("priceInfo", [])

    @property
    def user_data(self) -> dict[str, Any]:
        """Get user data from coordinator data."""
        return self.coordinator_data.get("user_data", {})

    @property
    def currency(self) -> str:
        """Get currency code from coordinator data."""
        return self.coordinator_data.get("currency", "EUR")

    # Smart data access methods with built-in None-safety

    def get_intervals(self, day_offset: int) -> list[dict]:
        """
        Get price intervals for a specific day with None-safety.

        Uses get_intervals_for_day_offsets() to abstract data structure access.

        Args:
            day_offset: Day offset (-1=yesterday, 0=today, 1=tomorrow).

        Returns:
            List of interval dictionaries, empty list if unavailable.

        """
        if not self.coordinator_data:
            return []
        return get_intervals_for_day_offsets(self.coordinator_data, [day_offset])

    @property
    def intervals_today(self) -> list[dict]:
        """Get today's intervals with None-safety."""
        return self.get_intervals(0)

    @property
    def intervals_tomorrow(self) -> list[dict]:
        """Get tomorrow's intervals with None-safety."""
        return self.get_intervals(1)

    @property
    def intervals_yesterday(self) -> list[dict]:
        """Get yesterday's intervals with None-safety."""
        return self.get_intervals(-1)

    def find_interval_at_offset(self, offset: int) -> dict | None:
        """
        Find interval at given offset from current time with bounds checking.

        Args:
            offset: Offset from current interval (0=current, 1=next, -1=previous).

        Returns:
            Interval dictionary or None if out of bounds or unavailable.

        """
        if not self.coordinator_data:
            return None

        from custom_components.tibber_prices.utils.price import (  # noqa: PLC0415 - avoid circular import
            find_price_data_for_interval,
        )

        time = self.coordinator.time
        target_time = time.get_interval_offset_time(offset)
        return find_price_data_for_interval(self.coordinator.data, target_time, time=time)

    def safe_get_from_interval(
        self,
        interval: dict[str, Any],
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Safely get a value from an interval dictionary.

        Args:
            interval: Interval dictionary.
            key: Key to retrieve.
            default: Default value if key not found.

        Returns:
            Value from interval or default.

        """
        return interval.get(key, default) if interval else default

    def has_data(self) -> bool:
        """
        Check if coordinator has any data available.

        Returns:
            True if data is available, False otherwise.

        """
        return bool(self.coordinator_data)

    def has_price_info(self) -> bool:
        """
        Check if price info is available in coordinator data.

        Returns:
            True if price info exists, False otherwise.

        """
        return bool(self.price_info)

    def get_day_intervals(self, day_offset: int) -> list[dict]:
        """
        Get intervals for a specific day from coordinator data.

        This is an alias for get_intervals() with consistent naming.

        Args:
            day_offset: Day offset (-1=yesterday, 0=today, 1=tomorrow).

        Returns:
            List of interval dictionaries, empty list if unavailable.

        """
        return self.get_intervals(day_offset)
