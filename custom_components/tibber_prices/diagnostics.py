"""
Diagnostics support for tibber_prices.

Learn more about diagnostics:
https://developers.home-assistant.io/docs/core/integration_diagnostics
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import TibberPricesConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,  # noqa: ARG001
    entry: TibberPricesConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data.coordinator

    return {
        "entry": {
            "entry_id": entry.entry_id,
            "version": entry.version,
            "minor_version": entry.minor_version,
            "domain": entry.domain,
            "title": entry.title,
            "state": str(entry.state),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval": str(coordinator.update_interval),
            "is_main_entry": coordinator.is_main_entry(),
            "data": coordinator.data,
            "update_timestamps": {
                "price": coordinator._last_price_update.isoformat() if coordinator._last_price_update else None,  # noqa: SLF001
                "user": coordinator._last_user_update.isoformat() if coordinator._last_user_update else None,  # noqa: SLF001
            },
        },
        "error": {
            "last_exception": str(coordinator.last_exception) if coordinator.last_exception else None,
        },
    }
