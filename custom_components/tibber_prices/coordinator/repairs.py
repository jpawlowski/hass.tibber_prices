"""
Repair issue management for Tibber Prices integration.

This module handles creation and cleanup of repair issues that notify users
about problems requiring attention in the Home Assistant UI.

Repair Types:
1. Tomorrow Data Missing - Warns when tomorrow's price data is unavailable after 18:00
2. Persistent Rate Limits - Warns when API rate limiting persists after multiple errors
3. Home Not Found - Warns when a home no longer exists in the Tibber account
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from custom_components.tibber_prices.const import DOMAIN
from homeassistant.helpers import issue_registry as ir

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Repair issue tracking thresholds
TOMORROW_DATA_WARNING_HOUR = 18  # Warn after 18:00 if tomorrow data missing
RATE_LIMIT_WARNING_THRESHOLD = 3  # Warn after 3 consecutive rate limit errors


class TibberPricesRepairManager:
    """Manage repair issues for Tibber Prices integration."""

    def __init__(self, hass: HomeAssistant, entry_id: str, home_name: str) -> None:
        """
        Initialize repair manager.

        Args:
            hass: Home Assistant instance
            entry_id: Config entry ID for this home
            home_name: Display name of the home (for user-friendly messages)

        """
        self._hass = hass
        self._entry_id = entry_id
        self._home_name = home_name

        # Track consecutive rate limit errors
        self._rate_limit_error_count = 0

        # Track if repairs are currently active
        self._tomorrow_data_repair_active = False
        self._rate_limit_repair_active = False
        self._home_not_found_repair_active = False

    async def check_tomorrow_data_availability(
        self,
        has_tomorrow_data: bool,  # noqa: FBT001 - Clear meaning in context
        current_time: datetime,
    ) -> None:
        """
        Check if tomorrow data is available and create/clear repair as needed.

        Creates repair if:
        - Current hour >= 18:00 (after expected data availability)
        - Tomorrow's data is missing

        Clears repair if:
        - Tomorrow's data is now available

        Args:
            has_tomorrow_data: Whether tomorrow's data is available
            current_time: Current local datetime for hour check

        """
        should_warn = current_time.hour >= TOMORROW_DATA_WARNING_HOUR and not has_tomorrow_data

        if should_warn and not self._tomorrow_data_repair_active:
            await self._create_tomorrow_data_repair()
        elif not should_warn and self._tomorrow_data_repair_active:
            await self._clear_tomorrow_data_repair()

    async def track_rate_limit_error(self) -> None:
        """
        Track rate limit error and create repair if threshold exceeded.

        Increments rate limit error counter and creates repair issue
        if threshold (3 consecutive errors) is reached.
        """
        self._rate_limit_error_count += 1

        if self._rate_limit_error_count >= RATE_LIMIT_WARNING_THRESHOLD and not self._rate_limit_repair_active:
            await self._create_rate_limit_repair()

    async def clear_rate_limit_tracking(self) -> None:
        """
        Clear rate limit error tracking after successful API call.

        Resets counter and clears any active repair issue.
        """
        self._rate_limit_error_count = min(self._rate_limit_error_count, 0)

        if self._rate_limit_repair_active:
            await self._clear_rate_limit_repair()

    async def create_home_not_found_repair(self) -> None:
        """
        Create repair for home no longer found in Tibber account.

        This indicates the home was deleted from the user's Tibber account
        but the config entry still exists in Home Assistant.
        """
        if self._home_not_found_repair_active:
            return

        _LOGGER.warning(
            "Home '%s' not found in Tibber account - creating repair issue",
            self._home_name,
        )

        ir.async_create_issue(
            self._hass,
            DOMAIN,
            f"home_not_found_{self._entry_id}",
            is_fixable=True,
            severity=ir.IssueSeverity.ERROR,
            translation_key="home_not_found",
            translation_placeholders={
                "home_name": self._home_name,
                "entry_id": self._entry_id,
            },
        )
        self._home_not_found_repair_active = True

    async def clear_home_not_found_repair(self) -> None:
        """Clear home not found repair (home is available again or entry removed)."""
        if not self._home_not_found_repair_active:
            return

        _LOGGER.debug("Clearing home not found repair for '%s'", self._home_name)

        ir.async_delete_issue(
            self._hass,
            DOMAIN,
            f"home_not_found_{self._entry_id}",
        )
        self._home_not_found_repair_active = False

    async def clear_all_repairs(self) -> None:
        """
        Clear all active repair issues.

        Called during coordinator shutdown or entry removal.
        """
        if self._tomorrow_data_repair_active:
            await self._clear_tomorrow_data_repair()
        if self._rate_limit_repair_active:
            await self._clear_rate_limit_repair()
        if self._home_not_found_repair_active:
            await self.clear_home_not_found_repair()

    async def _create_tomorrow_data_repair(self) -> None:
        """Create repair issue for missing tomorrow data."""
        _LOGGER.warning(
            "Tomorrow's price data missing after %d:00 for home '%s' - creating repair issue",
            TOMORROW_DATA_WARNING_HOUR,
            self._home_name,
        )

        ir.async_create_issue(
            self._hass,
            DOMAIN,
            f"tomorrow_data_missing_{self._entry_id}",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="tomorrow_data_missing",
            translation_placeholders={
                "home_name": self._home_name,
                "warning_hour": str(TOMORROW_DATA_WARNING_HOUR),
            },
        )
        self._tomorrow_data_repair_active = True

    async def _clear_tomorrow_data_repair(self) -> None:
        """Clear tomorrow data repair issue."""
        _LOGGER.debug("Tomorrow's data now available for '%s' - clearing repair issue", self._home_name)

        ir.async_delete_issue(
            self._hass,
            DOMAIN,
            f"tomorrow_data_missing_{self._entry_id}",
        )
        self._tomorrow_data_repair_active = False

    async def _create_rate_limit_repair(self) -> None:
        """Create repair issue for persistent rate limiting."""
        _LOGGER.warning(
            "Persistent API rate limiting detected for home '%s' (%d consecutive errors) - creating repair issue",
            self._home_name,
            self._rate_limit_error_count,
        )

        ir.async_create_issue(
            self._hass,
            DOMAIN,
            f"rate_limit_exceeded_{self._entry_id}",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="rate_limit_exceeded",
            translation_placeholders={
                "home_name": self._home_name,
                "error_count": str(self._rate_limit_error_count),
            },
        )
        self._rate_limit_repair_active = True

    async def _clear_rate_limit_repair(self) -> None:
        """Clear rate limit repair issue."""
        _LOGGER.debug("Rate limiting resolved for '%s' - clearing repair issue", self._home_name)

        ir.async_delete_issue(
            self._hass,
            DOMAIN,
            f"rate_limit_exceeded_{self._entry_id}",
        )
        self._rate_limit_repair_active = False
