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

    # Get period metadata from coordinator data
    price_periods = coordinator.data.get("pricePeriods", {}) if coordinator.data else {}

    return {
        "entry": {
            "entry_id": entry.entry_id,
            "version": entry.version,
            "minor_version": entry.minor_version,
            "domain": entry.domain,
            "title": entry.title,
            "state": str(entry.state),
            "home_id": entry.data.get("home_id", ""),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval": str(coordinator.update_interval),
            "data": coordinator.data,
            "update_timestamps": {
                "price": coordinator._last_price_update.isoformat() if coordinator._last_price_update else None,  # noqa: SLF001
                "user": coordinator._last_user_update.isoformat() if coordinator._last_user_update else None,  # noqa: SLF001
                "last_coordinator_update": coordinator._last_coordinator_update.isoformat()  # noqa: SLF001
                if coordinator._last_coordinator_update  # noqa: SLF001
                else None,
            },
            "lifecycle": {
                "state": coordinator._lifecycle_state,  # noqa: SLF001
                "is_fetching": coordinator._is_fetching,  # noqa: SLF001
                "api_calls_today": coordinator._api_calls_today,  # noqa: SLF001
                "last_api_call_date": coordinator._last_api_call_date.isoformat()  # noqa: SLF001
                if coordinator._last_api_call_date  # noqa: SLF001
                else None,
            },
        },
        "periods": {
            "best_price": {
                "count": len(price_periods.get("best_price", {}).get("periods", [])),
                "metadata": price_periods.get("best_price", {}).get("metadata", {}),
            },
            "peak_price": {
                "count": len(price_periods.get("peak_price", {}).get("periods", [])),
                "metadata": price_periods.get("peak_price", {}).get("metadata", {}),
            },
        },
        "config": {
            "options": dict(entry.options),
        },
        "cache_status": {
            "user_data_cached": coordinator._cached_user_data is not None,  # noqa: SLF001
            "price_data_cached": coordinator._cached_price_data is not None,  # noqa: SLF001
            "transformer_cache_valid": coordinator._data_transformer._cached_transformed_data is not None,  # noqa: SLF001
            "period_calculator_cache_valid": coordinator._period_calculator._cached_periods is not None,  # noqa: SLF001
        },
        "error": {
            "last_exception": str(coordinator.last_exception) if coordinator.last_exception else None,
        },
    }
