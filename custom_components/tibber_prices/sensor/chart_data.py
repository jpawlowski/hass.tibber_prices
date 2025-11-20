"""Chart data export functionality for Tibber Prices sensors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.tibber_prices.const import DATA_CHART_CONFIG, DOMAIN

if TYPE_CHECKING:
    from datetime import datetime

    from custom_components.tibber_prices.coordinator import TibberPricesDataUpdateCoordinator
    from custom_components.tibber_prices.data import TibberPricesConfigEntry
    from homeassistant.core import HomeAssistant


async def call_chartdata_service_async(
    hass: HomeAssistant,
    coordinator: TibberPricesDataUpdateCoordinator,
    config_entry: TibberPricesConfigEntry,
) -> tuple[dict | None, str | None]:
    """
    Call get_chartdata service with configuration from configuration.yaml (async).

    Returns:
        Tuple of (response, error_message).
        If successful: (response_dict, None)
        If failed: (None, error_string)

    """
    # Get configuration from hass.data (loaded from configuration.yaml)
    domain_data = hass.data.get(DOMAIN, {})
    chart_config = domain_data.get(DATA_CHART_CONFIG, {})

    # Use chart_config directly (already a dict from async_setup)
    service_params = dict(chart_config) if chart_config else {}

    # Add required entry_id parameter
    service_params["entry_id"] = config_entry.entry_id

    # Call get_chartdata service using official HA service system
    try:
        response = await hass.services.async_call(
            DOMAIN,
            "get_chartdata",
            service_params,
            blocking=True,
            return_response=True,
        )
    except Exception as ex:
        coordinator.logger.exception("Chart data service call failed")
        return None, str(ex)
    else:
        return response, None


def get_chart_data_state(
    chart_data_response: dict | None,
    chart_data_error: str | None,
) -> str | None:
    """
    Return state for chart_data_export sensor.

    Args:
        chart_data_response: Last service response (or None)
        chart_data_error: Last error message (or None)

    Returns:
        "error" if error occurred
        "ready" if data available
        "pending" if no data yet

    """
    if chart_data_error:
        return "error"
    if chart_data_response:
        return "ready"
    return "pending"


def build_chart_data_attributes(
    chart_data_response: dict | None,
    chart_data_last_update: datetime | None,
    chart_data_error: str | None,
) -> dict[str, object] | None:
    """
    Return chart data from last service call as attributes with metadata.

    Attribute order: timestamp, error (if any), service data (at the end).

    Args:
        chart_data_response: Last service response
        chart_data_last_update: Timestamp of last update
        chart_data_error: Error message if service call failed

    Returns:
        Dict with timestamp, optional error, and service response data.

    """
    # Build base attributes with metadata FIRST
    attributes: dict[str, object] = {
        "timestamp": chart_data_last_update,
    }

    # Add error message if service call failed
    if chart_data_error:
        attributes["error"] = chart_data_error

    if not chart_data_response:
        # No data - only metadata (timestamp, error)
        return attributes

    # Service data goes LAST - after metadata
    if isinstance(chart_data_response, dict):
        if len(chart_data_response) > 1:
            # Multiple keys → wrap to prevent collision with metadata
            attributes["data"] = chart_data_response
        else:
            # Single key → safe to merge directly
            attributes.update(chart_data_response)
    else:
        # If response is array/list/primitive, wrap it in "data" key
        attributes["data"] = chart_data_response

    return attributes
