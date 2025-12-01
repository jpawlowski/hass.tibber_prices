"""
ApexCharts YAML generation service handler.

This module implements the `get_apexcharts_yaml` service, which generates
ready-to-use YAML configuration for ApexCharts cards with price level visualization.

Features:
- Automatic color-coded series per price level/rating
- Server-side NULL insertion for clean gaps
- Translated level names and titles
- Responsive to user language settings
- Configurable day selection (yesterday/today/tomorrow)

Service: tibber_prices.get_apexcharts_yaml
Response: YAML configuration dict for ApexCharts card

"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

import voluptuous as vol

from custom_components.tibber_prices.const import (
    DOMAIN,
    PRICE_LEVEL_CHEAP,
    PRICE_LEVEL_EXPENSIVE,
    PRICE_LEVEL_NORMAL,
    PRICE_LEVEL_VERY_CHEAP,
    PRICE_LEVEL_VERY_EXPENSIVE,
    PRICE_RATING_HIGH,
    PRICE_RATING_LOW,
    PRICE_RATING_NORMAL,
    format_price_unit_minor,
    get_translation,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry

from .formatters import get_level_translation
from .helpers import get_entry_and_data

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall

# Service constants
APEXCHARTS_YAML_SERVICE_NAME: Final = "get_apexcharts_yaml"
ATTR_DAY: Final = "day"
ATTR_ENTRY_ID: Final = "entry_id"

# Service schema
APEXCHARTS_SERVICE_SCHEMA: Final = vol.Schema(
    {
        vol.Required(ATTR_ENTRY_ID): str,
        vol.Optional("day", default="today"): vol.In(["yesterday", "today", "tomorrow"]),
        vol.Optional("level_type", default="rating_level"): vol.In(["rating_level", "level"]),
    }
)


async def handle_apexcharts_yaml(call: ServiceCall) -> dict[str, Any]:
    """
    Return YAML snippet for ApexCharts card.

    Generates a complete ApexCharts card configuration with:
    - Separate series for each price level/rating (color-coded)
    - Automatic data fetching via get_chartdata service
    - Translated labels and titles
    - Clean gap visualization with NULL insertion

    See services.yaml for detailed parameter documentation.

    Args:
        call: Service call with parameters

    Returns:
        Dictionary with ApexCharts card configuration

    Raises:
        ServiceValidationError: If entry_id is missing or invalid

    """
    hass = call.hass
    entry_id_raw = call.data.get(ATTR_ENTRY_ID)
    if entry_id_raw is None:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="missing_entry_id")
    entry_id: str = str(entry_id_raw)

    day = call.data.get("day", "today")
    level_type = call.data.get("level_type", "rating_level")

    # Get user's language from hass config
    user_language = hass.config.language or "en"

    # Get coordinator to access price data (for currency)
    _, coordinator, _ = get_entry_and_data(hass, entry_id)
    # Get currency from coordinator data
    currency = coordinator.data.get("currency", "EUR")
    price_unit = format_price_unit_minor(currency)

    # Get a sample entity_id for the series (first sensor from this entry)
    entity_registry = async_get_entity_registry(hass)
    sample_entity = None
    for entity in entity_registry.entities.values():
        if entity.config_entry_id == entry_id and entity.domain == "sensor":
            sample_entity = entity.entity_id
            break

    if level_type == "rating_level":
        series_levels = [
            (PRICE_RATING_LOW, "#2ecc71"),
            (PRICE_RATING_NORMAL, "#f1c40f"),
            (PRICE_RATING_HIGH, "#e74c3c"),
        ]
    else:
        series_levels = [
            (PRICE_LEVEL_VERY_CHEAP, "#2ecc71"),
            (PRICE_LEVEL_CHEAP, "#27ae60"),
            (PRICE_LEVEL_NORMAL, "#f1c40f"),
            (PRICE_LEVEL_EXPENSIVE, "#e67e22"),
            (PRICE_LEVEL_VERY_EXPENSIVE, "#e74c3c"),
        ]
    series = []
    for level_key, color in series_levels:
        # Get translated name for the level using helper function
        name = get_level_translation(level_key, level_type, user_language)
        # Use server-side insert_nulls='segments' for clean gaps
        if level_type == "rating_level":
            filter_param = f"rating_level_filter: ['{level_key}']"
        else:
            filter_param = f"level_filter: ['{level_key}']"

        # Data generator fetches chart data and removes trailing nulls for proper header display
        # (ApexCharts in_header shows last value, so trailing nulls cause "N/A")
        data_generator = (
            f"const response = await hass.callWS({{ "
            f"type: 'call_service', "
            f"domain: 'tibber_prices', "
            f"service: 'get_chartdata', "
            f"return_response: true, "
            f"service_data: {{ entry_id: '{entry_id}', day: ['{day}'], {filter_param}, "
            f"output_format: 'array_of_arrays', insert_nulls: 'segments', minor_currency: true }} }}); "
            f"const data = response.response.data; "
            f"while (data.length > 0 && data[data.length - 1][1] === null) data.pop(); "
            f"return data;"
        )
        # Only show extremas for HIGH and LOW levels (not NORMAL)
        show_extremas = level_key != "NORMAL"
        series.append(
            {
                "entity": sample_entity or "sensor.tibber_prices",
                "name": name,
                "type": "area",
                "color": color,
                "yaxis_id": "price",
                "show": {"extremas": show_extremas, "legend_value": False},
                "data_generator": data_generator,
                "stroke_width": 1,
            }
        )

    # Get translated title based on level_type
    title_key = "title_rating_level" if level_type == "rating_level" else "title_level"
    title = get_translation(["apexcharts", title_key], user_language) or (
        "Price Phases Daily Progress" if level_type == "rating_level" else "Price Level"
    )

    # Add translated day to title
    day_translated = get_translation(["selector", "day", "options", day], user_language) or day.capitalize()
    title = f"{title} - {day_translated}"

    # Configure span based on selected day
    if day == "yesterday":
        span_config = {"start": "day", "offset": "-1d"}
    elif day == "tomorrow":
        span_config = {"start": "day", "offset": "+1d"}
    else:  # today
        span_config = {"start": "day"}

    return {
        "type": "custom:apexcharts-card",
        "update_interval": "5m",
        "span": span_config,
        "header": {
            "show": True,
            "title": title,
            "show_states": False,
        },
        "apex_config": {
            "chart": {
                "animations": {"enabled": False},
                "toolbar": {"show": True, "tools": {"zoom": True, "pan": True}},
                "zoom": {"enabled": True},
            },
            "stroke": {"curve": "stepline", "width": 2},
            "fill": {
                "type": "gradient",
                "opacity": 0.4,
                "gradient": {
                    "shade": "dark",
                    "type": "vertical",
                    "shadeIntensity": 0.5,
                    "opacityFrom": 0.7,
                    "opacityTo": 0.2,
                },
            },
            "dataLabels": {"enabled": False},
            "tooltip": {
                "x": {"format": "HH:mm"},
                "y": {"title": {"formatter": f"function() {{ return '{price_unit}'; }}"}},
            },
            "legend": {
                "show": True,
                "position": "top",
                "horizontalAlign": "left",
                "markers": {"radius": 2},
            },
            "grid": {
                "show": True,
                "borderColor": "#40475D",
                "strokeDashArray": 4,
                "xaxis": {"lines": {"show": True}},
                "yaxis": {"lines": {"show": True}},
            },
            "markers": {"size": 0},
        },
        "yaxis": [
            {
                "id": "price",
                "decimals": 2,
                "min": 0,
                "apex_config": {"title": {"text": price_unit}},
            },
        ],
        "now": {"show": True, "color": "#8e24aa", "label": "🕒 LIVE"},
        "all_series_config": {
            "stroke_width": 1,
            "group_by": {"func": "raw", "duration": "15min"},
        },
        "series": series,
    }
