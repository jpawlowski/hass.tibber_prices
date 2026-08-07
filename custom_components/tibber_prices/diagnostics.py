"""
Diagnostics support for tibber_prices.

Learn more about diagnostics:
https://developers.home-assistant.io/docs/core/integration_diagnostics
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.util import dt as dt_util

from .time_travel import tomorrow_arrival_hour, uses_realistic_tomorrow

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import TibberPricesConfigEntry, TibberPricesSubentryData


def _view_diagnostics(subentry_id: str, view: TibberPricesSubentryData) -> dict[str, Any]:
    """
    Describe one time-travel view for the diagnostics download.

    Both clocks are included on purpose: a support report needs to show which
    real moment produced which shifted moment, otherwise "the prices are wrong"
    reports about views are impossible to interpret.
    """
    coordinator = view.coordinator
    shift = coordinator.time_shift
    real_now = dt_util.now()
    effective = shift.resolve(real_now)
    price_info = (coordinator.data or {}).get("priceInfo", [])

    return {
        "subentry_id": subentry_id,
        "title": view.subentry.title,
        "mode": shift.describe(),
        "offset": {
            "days": shift.days,
            "years": shift.years,
            "hours": shift.hours,
            "minutes": shift.minutes,
        },
        "headless": coordinator.headless,
        "realistic_tomorrow": uses_realistic_tomorrow(view.subentry),
        "tomorrow_arrival_hour": tomorrow_arrival_hour(view.subentry),
        "now_real": real_now.isoformat(),
        # None means the target date does not exist today (29 February in a
        # non-leap target year) - the view is deliberately unavailable.
        "now_effective": effective.isoformat() if effective else None,
        "has_data_coverage": shift.has_data_coverage(real_now),
        "interval_range": {
            "first": _interval_start(price_info[0]) if price_info else None,
            "last": _interval_start(price_info[-1]) if price_info else None,
        },
        "interval_count": len(price_info),
        "last_update_success": coordinator.last_update_success,
        "last_exception": str(coordinator.last_exception) if coordinator.last_exception else None,
    }


def _interval_start(interval: dict[str, Any]) -> str | None:
    """Return an interval's start as an ISO string, whatever type it carries."""
    starts_at = interval.get("startsAt")
    if starts_at is None:
        return None
    return starts_at.isoformat() if hasattr(starts_at, "isoformat") else str(starts_at)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
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
        "time_travel_views": [
            _view_diagnostics(subentry_id, view) for subentry_id, view in entry.runtime_data.subentries.items()
        ],
        "cache_status": {
            "user_data_cached": coordinator._cached_user_data is not None,  # noqa: SLF001
            "has_price_data": coordinator.data is not None and "priceInfo" in (coordinator.data or {}),
            "transformer_cache_valid": coordinator._data_transformer._cached_transformed_data is not None,  # noqa: SLF001
            "period_calculator_cache_valid": coordinator._period_calculator._cached_periods is not None,  # noqa: SLF001
        },
        "error": {
            "last_exception": str(coordinator.last_exception) if coordinator.last_exception else None,
        },
    }
