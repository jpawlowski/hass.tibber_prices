"""
Service handlers for Tibber Prices integration.

This package provides service endpoints for external integrations and data export:
- Chart data export (get_chartdata)
- ApexCharts YAML generation (get_apexcharts_yaml)
- User data refresh (refresh_user_data)
- Find best start time (find_best_start) - Planning for run-once devices
- Plan charging (plan_charging) - Charging plan for energy storage
- Debug: Clear tomorrow data (debug_clear_tomorrow) - DevContainer only

Architecture:
- helpers.py: Common utilities (get_entry_and_data)
- common.py: Shared planning utilities (window parsing, response envelope)
- formatters.py: Data transformation and formatting functions
- chartdata.py: Main data export service handler
- apexcharts.py: ApexCharts card YAML generator
- refresh_user_data.py: User data refresh handler
- find_best_start.py: Best start time finder for appliances
- plan_charging.py: Charging plan generator for batteries/EVs
- debug_clear_tomorrow.py: Debug tool for testing tomorrow refresh (dev only)

"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from custom_components.tibber_prices.const import DOMAIN
from homeassistant.core import SupportsResponse, callback

from .find_best_start import (
    FIND_BEST_START_SERVICE_NAME,
    FIND_BEST_START_SERVICE_SCHEMA,
    handle_find_best_start,
)
from .get_apexcharts_yaml import (
    APEXCHARTS_SERVICE_SCHEMA,
    APEXCHARTS_YAML_SERVICE_NAME,
    handle_apexcharts_yaml,
)
from .get_chartdata import CHARTDATA_SERVICE_NAME, CHARTDATA_SERVICE_SCHEMA, handle_chartdata
from .get_price import GET_PRICE_SERVICE_NAME, GET_PRICE_SERVICE_SCHEMA, handle_get_price
from .plan_charging import (
    PLAN_CHARGING_SERVICE_NAME,
    PLAN_CHARGING_SERVICE_SCHEMA,
    handle_plan_charging,
)
from .refresh_user_data import (
    REFRESH_USER_DATA_SERVICE_NAME,
    REFRESH_USER_DATA_SERVICE_SCHEMA,
    handle_refresh_user_data,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

__all__ = [
    "async_setup_services",
]

# Check if running in development mode (DevContainer)
_IS_DEV_MODE = os.environ.get("TIBBER_PRICES_DEV") == "1"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Tibber Prices integration."""
    hass.services.async_register(
        DOMAIN,
        APEXCHARTS_YAML_SERVICE_NAME,
        handle_apexcharts_yaml,
        schema=APEXCHARTS_SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        CHARTDATA_SERVICE_NAME,
        handle_chartdata,
        schema=CHARTDATA_SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        GET_PRICE_SERVICE_NAME,
        handle_get_price,
        schema=GET_PRICE_SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        REFRESH_USER_DATA_SERVICE_NAME,
        handle_refresh_user_data,
        schema=REFRESH_USER_DATA_SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        FIND_BEST_START_SERVICE_NAME,
        handle_find_best_start,
        schema=FIND_BEST_START_SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        PLAN_CHARGING_SERVICE_NAME,
        handle_plan_charging,
        schema=PLAN_CHARGING_SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    # Debug services - only available in DevContainer (TIBBER_PRICES_DEV=1)
    if _IS_DEV_MODE:
        from .debug_clear_tomorrow import (  # noqa: PLC0415 - Conditional import for dev-only service
            DEBUG_CLEAR_TOMORROW_SERVICE_NAME,
            DEBUG_CLEAR_TOMORROW_SERVICE_SCHEMA,
            handle_debug_clear_tomorrow,
        )

        hass.services.async_register(
            DOMAIN,
            DEBUG_CLEAR_TOMORROW_SERVICE_NAME,
            handle_debug_clear_tomorrow,
            schema=DEBUG_CLEAR_TOMORROW_SERVICE_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )
