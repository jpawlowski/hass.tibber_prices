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
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_registry import (
    EntityRegistry,
)
from homeassistant.helpers.entity_registry import (
    async_get as async_get_entity_registry,
)

from .formatters import get_level_translation
from .helpers import get_entry_and_data

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall

# Service constants
APEXCHARTS_YAML_SERVICE_NAME: Final = "get_apexcharts_yaml"
ATTR_DAY: Final = "day"
ATTR_ENTRY_ID: Final = "entry_id"

# Service schema
APEXCHARTS_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTRY_ID): cv.string,
        vol.Optional("day"): vol.In(["yesterday", "today", "tomorrow"]),
        vol.Optional("level_type", default="rating_level"): vol.In(["rating_level", "level"]),
        vol.Optional("highlight_best_price", default=True): cv.boolean,
    }
)


def _build_entity_map(
    entity_registry: EntityRegistry,
    entry_id: str,
    level_type: str,
    day: str,
) -> dict[str, str]:
    """
    Build entity mapping for price levels based on day.

    Maps price levels to appropriate sensor entities (min/max/avg for the selected day).

    Args:
        entity_registry: Entity registry
        entry_id: Config entry ID
        level_type: "rating_level" or "level"
        day: "today", "tomorrow", or "yesterday"

    Returns:
        Dictionary mapping level keys to entity IDs

    """
    entity_map = {}

    # Define mapping patterns for each combination of level_type and day
    # Note: Match by entity key (in unique_id), not entity_id (user can rename)
    # Note: For "yesterday", we use "today" sensors as they show current state
    pattern_map = {
        ("rating_level", "today"): [
            ("lowest_price_today", [PRICE_RATING_LOW]),
            ("average_price_today", [PRICE_RATING_NORMAL]),
            ("highest_price_today", [PRICE_RATING_HIGH]),
        ],
        ("rating_level", "yesterday"): [
            ("lowest_price_today", [PRICE_RATING_LOW]),
            ("average_price_today", [PRICE_RATING_NORMAL]),
            ("highest_price_today", [PRICE_RATING_HIGH]),
        ],
        ("rating_level", "tomorrow"): [
            ("lowest_price_tomorrow", [PRICE_RATING_LOW]),
            ("average_price_tomorrow", [PRICE_RATING_NORMAL]),
            ("highest_price_tomorrow", [PRICE_RATING_HIGH]),
        ],
        ("level", "today"): [
            ("lowest_price_today", [PRICE_LEVEL_VERY_CHEAP, PRICE_LEVEL_CHEAP]),
            ("average_price_today", [PRICE_LEVEL_NORMAL]),
            ("highest_price_today", [PRICE_LEVEL_EXPENSIVE, PRICE_LEVEL_VERY_EXPENSIVE]),
        ],
        ("level", "yesterday"): [
            ("lowest_price_today", [PRICE_LEVEL_VERY_CHEAP, PRICE_LEVEL_CHEAP]),
            ("average_price_today", [PRICE_LEVEL_NORMAL]),
            ("highest_price_today", [PRICE_LEVEL_EXPENSIVE, PRICE_LEVEL_VERY_EXPENSIVE]),
        ],
        ("level", "tomorrow"): [
            ("lowest_price_tomorrow", [PRICE_LEVEL_VERY_CHEAP, PRICE_LEVEL_CHEAP]),
            ("average_price_tomorrow", [PRICE_LEVEL_NORMAL]),
            ("highest_price_tomorrow", [PRICE_LEVEL_EXPENSIVE, PRICE_LEVEL_VERY_EXPENSIVE]),
        ],
    }

    patterns = pattern_map.get((level_type, day), [])

    for entity in entity_registry.entities.values():
        if entity.config_entry_id != entry_id or entity.domain != "sensor":
            continue

        # Match entity against patterns using unique_id (contains entry_id_key)
        # Extract key from unique_id: format is "{entry_id}_{key}"
        if entity.unique_id and "_" in entity.unique_id:
            entity_key = entity.unique_id.split("_", 1)[1]  # Get everything after first underscore

            for pattern, levels in patterns:
                if pattern == entity_key:
                    for level in levels:
                        entity_map[level] = entity.entity_id
                    break

    return entity_map


def _get_current_price_entity(entity_registry: EntityRegistry, entry_id: str) -> str | None:
    """Get current interval price entity for header display."""
    return next(
        (
            entity.entity_id
            for entity in entity_registry.entities.values()
            if entity.config_entry_id == entry_id
            and entity.unique_id
            and entity.unique_id.endswith("_current_interval_price")
        ),
        None,
    )


async def handle_apexcharts_yaml(call: ServiceCall) -> dict[str, Any]:  # noqa: PLR0912, PLR0915
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

    day = call.data.get("day")  # Can be None (rolling window mode)
    level_type = call.data.get("level_type", "rating_level")
    highlight_best_price = call.data.get("highlight_best_price", True)

    # Get user's language from hass config
    user_language = hass.config.language or "en"

    # Get coordinator to access price data (for currency)
    _, coordinator, _ = get_entry_and_data(hass, entry_id)
    # Get currency from coordinator data
    currency = coordinator.data.get("currency", "EUR")
    price_unit = format_price_unit_minor(currency)

    # Get entity registry for mapping
    entity_registry = async_get_entity_registry(hass)

    # Build entity mapping based on level_type and day for clickable states
    # When day is None, use "today" as fallback for entity mapping
    entity_map = _build_entity_map(entity_registry, entry_id, level_type, day or "today")

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
    # Only create series for levels that have a matching entity (filter out missing levels)
    for level_key, color in series_levels:
        # Skip levels that don't have a corresponding sensor
        if level_key not in entity_map:
            continue

        # Get translated name for the level using helper function
        name = get_level_translation(level_key, level_type, user_language)
        # Use server-side insert_nulls='segments' for clean gaps
        if level_type == "rating_level":
            filter_param = f"rating_level_filter: ['{level_key}']"
        else:
            filter_param = f"level_filter: ['{level_key}']"

        # Conditionally include day parameter (omit for rolling window mode)
        day_param = f"day: ['{day}'], " if day else ""

        data_generator = (
            f"const response = await hass.callWS({{ "
            f"type: 'call_service', "
            f"domain: 'tibber_prices', "
            f"service: 'get_chartdata', "
            f"return_response: true, "
            f"service_data: {{ entry_id: '{entry_id}', {day_param}{filter_param}, "
            f"output_format: 'array_of_arrays', insert_nulls: 'segments', minor_currency: true, "
            f"connect_segments: true }} }}); "
            f"return response.response.data;"
        )
        # All series use same configuration (no extremas on data_generator series)
        # Hide all levels in header since data_generator series don't show meaningful state values
        # (the entity state is the min/max/avg price, not the current price for this level)
        show_config = {"legend_value": False, "in_header": False}

        series.append(
            {
                "entity": entity_map[level_key],  # Use entity_map directly (no fallback needed)
                "name": name,
                "type": "area",
                "color": color,
                "yaxis_id": "price",
                "show": show_config,
                "data_generator": data_generator,
                "stroke_width": 1,
            }
        )

    # Note: Extrema markers don't work with data_generator approach
    # ApexCharts requires entity time-series data for extremas feature
    # Min/Max sensors are single values, not time-series

    # Get translated name for best price periods (needed for tooltip formatter)
    best_price_name = (
        get_translation(["binary_sensor", "best_price_period", "name"], user_language) or "Best Price Period"
    )

    # Add best price period highlight overlay (vertical bands from top to bottom)
    if highlight_best_price and entity_map:
        # Create vertical highlight bands using separate Y-axis (0-1 range)
        # This creates a semi-transparent overlay from bottom to top without affecting price scale
        # Conditionally include day parameter (omit for rolling window mode)
        day_param = f"day: ['{day}'], " if day else ""

        # Store original prices for tooltip, but map to 1 for full-height overlay
        # We use a custom tooltip formatter to show the real price
        best_price_generator = (
            f"const response = await hass.callWS({{ "
            f"type: 'call_service', "
            f"domain: 'tibber_prices', "
            f"service: 'get_chartdata', "
            f"return_response: true, "
            f"service_data: {{ entry_id: '{entry_id}', {day_param}"
            f"period_filter: 'best_price', "
            f"output_format: 'array_of_arrays', insert_nulls: 'segments', minor_currency: true }} }}); "
            f"const originalData = response.response.data; "
            f"return originalData.map((point, i) => {{ "
            f"const result = [point[0], point[1] === null ? null : 1]; "
            f"result.originalPrice = point[1]; "
            f"return result; "
            f"}});"
        )

        # Use first entity from entity_map (reuse existing entity to avoid extra header entries)
        best_price_entity = next(iter(entity_map.values()))

        series.append(
            {
                "entity": best_price_entity,
                "name": best_price_name,
                "type": "area",
                "color": "rgba(46, 204, 113, 0.2)",  # Semi-transparent green
                "yaxis_id": "highlight",  # Use separate Y-axis (0-1) for full-height overlay
                "show": {"legend_value": False, "in_header": False, "in_legend": False},
                "data_generator": best_price_generator,
                "stroke_width": 0,
                "curve": "stepline",
            }
        )

    # Get translated title based on level_type
    title_key = "title_rating_level" if level_type == "rating_level" else "title_level"
    title = get_translation(["apexcharts", title_key], user_language) or (
        "Price Phases Daily Progress" if level_type == "rating_level" else "Price Level"
    )

    # Add translated day to title (only if day parameter was provided)
    if day:
        day_translated = get_translation(["selector", "day", "options", day], user_language) or day.capitalize()
        title = f"{title} - {day_translated}"

    # Configure span based on selected day
    # For rolling window mode, use config-template-card for dynamic offset
    if day == "yesterday":
        span_config = {"start": "day", "offset": "-1d"}
        graph_span_value = None
        use_template = False
    elif day == "tomorrow":
        span_config = {"start": "day", "offset": "+1d"}
        graph_span_value = None
        use_template = False
    elif day:  # today (explicit)
        span_config = {"start": "day"}
        graph_span_value = None
        use_template = False
    else:  # Rolling window mode (None)
        # Use config-template-card to dynamically set offset based on data availability
        span_config = None  # Will be set in template
        graph_span_value = "48h"
        use_template = True

    result = {
        "type": "custom:apexcharts-card",
        "update_interval": "5m",
        "header": {
            "show": True,
            "title": title,
            "show_states": True,
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
                "show": False,
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
            {
                "id": "highlight",
                "min": 0,
                "max": 1,
                "show": False,  # Hide this axis (only for highlight overlay)
                "opposite": True,
            },
        ],
        "now": {"show": True, "color": "#8e24aa", "label": "🕒 LIVE"},
        "all_series_config": {
            "stroke_width": 1,
            "group_by": {"func": "raw", "duration": "15min"},
        },
        "series": series,
    }

    # For rolling window mode, wrap in config-template-card for dynamic offset
    if use_template:
        # Add graph_span to base config (48h window)
        result["graph_span"] = graph_span_value

        # Find tomorrow_data_available binary sensor
        tomorrow_data_sensor = next(
            (
                entity.entity_id
                for entity in entity_registry.entities.values()
                if entity.config_entry_id == entry_id
                and entity.unique_id
                and entity.unique_id.endswith("_tomorrow_data_available")
            ),
            None,
        )

        if tomorrow_data_sensor:
            # Wrap in config-template-card with dynamic offset calculation
            # Template checks if tomorrow data is available (binary sensor state)
            # If 'on' (tomorrow data available) → offset +1d (show today+tomorrow)
            # If 'off' (no tomorrow data) → offset +0d (show yesterday+today)
            template_value = f"states['{tomorrow_data_sensor}'].state === 'on' ? '+1d' : '+0d'"
            return {
                "type": "custom:config-template-card",
                "variables": {
                    "v_offset": template_value,
                },
                "entities": [tomorrow_data_sensor],
                "card": {
                    **result,
                    "span": {
                        "end": "day",
                        "offset": "${v_offset}",
                    },
                },
            }

        # Fallback if sensor not found: just use +1d offset
        result["span"] = {"end": "day", "offset": "+1d"}
        return result

    # Add span for fixed-day views
    if span_config:
        result["span"] = span_config

    # Add graph_span if needed
    if graph_span_value:
        result["graph_span"] = graph_span_value

    return result
