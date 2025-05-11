"""Diagnostics support for tibber_prices."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

TO_REDACT = {"access_token"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id].coordinator

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "coordinator_data": coordinator.data,
        "last_update_success": coordinator.last_update_success,
        "update_timestamps": {
            "price": coordinator.last_price_update.isoformat() if coordinator.last_price_update else None,
            "hourly_rating": coordinator.last_rating_update_hourly.isoformat()
            if coordinator.last_rating_update_hourly
            else None,
            "daily_rating": coordinator.last_rating_update_daily.isoformat()
            if coordinator.last_rating_update_daily
            else None,
            "monthly_rating": coordinator.last_rating_update_monthly.isoformat()
            if coordinator.last_rating_update_monthly
            else None,
        },
    }
