"""Chart metadata export functionality for Tibber Prices sensors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.tibber_prices.const import (
    CONF_CURRENCY_DISPLAY_MODE,
    DATA_CHART_METADATA_CONFIG,
    DISPLAY_MODE_SUBUNIT,
    DOMAIN,
)

if TYPE_CHECKING:
    from datetime import datetime

    from custom_components.tibber_prices.coordinator import TibberPricesDataUpdateCoordinator
    from custom_components.tibber_prices.data import TibberPricesConfigEntry
    from homeassistant.core import HomeAssistant


async def call_chartdata_service_for_metadata_async(
    hass: HomeAssistant,
    coordinator: TibberPricesDataUpdateCoordinator,
    config_entry: TibberPricesConfigEntry,
) -> tuple[dict | None, str | None]:
    """
    Call get_chartdata service with configuration from configuration.yaml for metadata (async).

    Returns:
        Tuple of (response, error_message).
        If successful: (response_dict, None)
        If failed: (None, error_string)

    """
    # Get configuration from hass.data (loaded from configuration.yaml)
    domain_data = hass.data.get(DOMAIN, {})
    chart_metadata_config = domain_data.get(DATA_CHART_METADATA_CONFIG, {})

    # Use chart_metadata_config directly (already a dict from async_setup)
    service_params = dict(chart_metadata_config) if chart_metadata_config else {}

    # Add required entry_id parameter
    service_params["entry_id"] = config_entry.entry_id

    # Force metadata to "only" - this sensor ONLY provides metadata
    service_params["metadata"] = "only"

    # Use user's display unit preference from config_entry
    # This ensures chart_metadata yaxis values match the user's configured currency display mode
    if "subunit_currency" not in service_params:
        display_mode = config_entry.options.get(CONF_CURRENCY_DISPLAY_MODE, DISPLAY_MODE_SUBUNIT)
        service_params["subunit_currency"] = display_mode == DISPLAY_MODE_SUBUNIT

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
        coordinator.logger.exception("Chart metadata service call failed")
        return None, str(ex)
    else:
        return response, None


def get_chart_metadata_state(
    chart_metadata_response: dict | None,
    chart_metadata_error: str | None,
) -> str | None:
    """
    Return state for chart_metadata sensor.

    Args:
        chart_metadata_response: Last service response (or None)
        chart_metadata_error: Last error message (or None)

    Returns:
        "error" if error occurred
        "ready" if metadata available
        "pending" if no data yet

    """
    if chart_metadata_error:
        return "error"
    if chart_metadata_response:
        return "ready"
    return "pending"


def build_chart_metadata_attributes(
    chart_metadata_response: dict | None,
    chart_metadata_last_update: datetime | None,
    chart_metadata_error: str | None,
) -> dict[str, object] | None:
    """
    Return chart metadata from last service call as attributes.

    Attribute order: timestamp, error (if any), metadata fields (at the end).

    Args:
        chart_metadata_response: Last service response (should contain "metadata" key)
        chart_metadata_last_update: Timestamp of last update
        chart_metadata_error: Error message if service call failed

    Returns:
        Dict with timestamp, optional error, and metadata fields.

    """
    # Build base attributes with timestamp FIRST
    attributes: dict[str, object] = {
        "timestamp": chart_metadata_last_update,
    }

    # Add error message if service call failed
    if chart_metadata_error:
        attributes["error"] = chart_metadata_error

    if not chart_metadata_response:
        # No data - only timestamp (and error if present)
        return attributes

    # Extract metadata from response (get_chartdata returns {"metadata": {...}})
    metadata = chart_metadata_response.get("metadata", {})

    # Extract the fields we care about for charts
    # These are the universal chart metadata fields useful for any chart card
    if metadata:
        yaxis_suggested = metadata.get("yaxis_suggested", {})

        # Add yaxis bounds (useful for all chart cards)
        if "min" in yaxis_suggested:
            attributes["yaxis_min"] = yaxis_suggested["min"]
        if "max" in yaxis_suggested:
            attributes["yaxis_max"] = yaxis_suggested["max"]

        # Add currency info (useful for labeling)
        if "currency" in metadata:
            attributes["currency"] = metadata["currency"]

        # Add resolution info (interval duration in minutes)
        if "resolution" in metadata:
            attributes["resolution"] = metadata["resolution"]

    return attributes
