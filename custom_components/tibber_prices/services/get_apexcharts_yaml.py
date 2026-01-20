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
    CONF_CURRENCY_DISPLAY_MODE,
    DISPLAY_MODE_SUBUNIT,
    DOMAIN,
    PRICE_LEVEL_CHEAP,
    PRICE_LEVEL_EXPENSIVE,
    PRICE_LEVEL_NORMAL,
    PRICE_LEVEL_VERY_CHEAP,
    PRICE_LEVEL_VERY_EXPENSIVE,
    PRICE_RATING_HIGH,
    PRICE_RATING_LOW,
    PRICE_RATING_NORMAL,
    get_display_unit_string,
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
        vol.Optional("day"): vol.In(["yesterday", "today", "tomorrow", "rolling_window", "rolling_window_autozoom"]),
        vol.Optional("level_type", default="rating_level"): vol.In(["rating_level", "level"]),
        vol.Optional("resolution", default="interval"): vol.In(["interval", "hourly"]),
        vol.Optional("highlight_best_price", default=True): cv.boolean,
        vol.Optional("highlight_peak_price", default=False): cv.boolean,
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
    # Note: For "yesterday_today_tomorrow" and "today_tomorrow", we use "today" sensors (dynamic windows)
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
        ("rating_level", "rolling_window"): [
            ("lowest_price_today", [PRICE_RATING_LOW]),
            ("average_price_today", [PRICE_RATING_NORMAL]),
            ("highest_price_today", [PRICE_RATING_HIGH]),
        ],
        ("rating_level", "rolling_window_autozoom"): [
            ("lowest_price_today", [PRICE_RATING_LOW]),
            ("average_price_today", [PRICE_RATING_NORMAL]),
            ("highest_price_today", [PRICE_RATING_HIGH]),
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
        ("level", "rolling_window"): [
            ("lowest_price_today", [PRICE_LEVEL_VERY_CHEAP, PRICE_LEVEL_CHEAP]),
            ("average_price_today", [PRICE_LEVEL_NORMAL]),
            ("highest_price_today", [PRICE_LEVEL_EXPENSIVE, PRICE_LEVEL_VERY_EXPENSIVE]),
        ],
        ("level", "rolling_window_autozoom"): [
            ("lowest_price_today", [PRICE_LEVEL_VERY_CHEAP, PRICE_LEVEL_CHEAP]),
            ("average_price_today", [PRICE_LEVEL_NORMAL]),
            ("highest_price_today", [PRICE_LEVEL_EXPENSIVE, PRICE_LEVEL_VERY_EXPENSIVE]),
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


def _check_custom_cards_installed(hass: Any) -> dict[str, bool]:
    """
    Check if required custom cards are installed via HACS/Lovelace resources.

    Args:
        hass: Home Assistant instance

    Returns:
        Dictionary with card names as keys and installation status as bool values

    """
    installed_cards = {"apexcharts-card": False, "config-template-card": False}

    # Access Lovelace resources via the new API (2026.2+)
    lovelace_data = hass.data.get("lovelace")
    if lovelace_data and hasattr(lovelace_data, "resources"):
        try:
            # ResourceStorageCollection has async_items() method
            resources = lovelace_data.resources
            if hasattr(resources, "async_items") and hasattr(resources, "data") and isinstance(resources.data, dict):
                # Can't use await here, so we check the internal storage
                for resource in resources.data.values():
                    url = resource.get("url", "") if isinstance(resource, dict) else ""
                    if "apexcharts-card" in url:
                        installed_cards["apexcharts-card"] = True
                    if "config-template-card" in url:
                        installed_cards["config-template-card"] = True
        except (AttributeError, TypeError):
            # Fallback: can't determine, assume not installed
            pass

    return installed_cards


def _get_sensor_disabled_notification(language: str) -> dict[str, str]:
    """Get notification texts for disabled chart metadata sensor."""
    title = get_translation(["apexcharts", "notification", "metadata_sensor_unavailable", "title"], language)
    message = get_translation(["apexcharts", "notification", "metadata_sensor_unavailable", "message"], language)

    if not title:
        title = get_translation(["apexcharts", "notification", "metadata_sensor_unavailable", "title"], "en")
    if not message:
        message = get_translation(["apexcharts", "notification", "metadata_sensor_unavailable", "message"], "en")

    if not title:
        title = "Tibber Prices: Chart Metadata Sensor Disabled"
    if not message:
        message = (
            "The Chart Metadata sensor is currently disabled. "
            "Enable it to get optimized chart scaling and gradient colors.\n\n"
            "[Open Tibber Prices Integration](https://my.home-assistant.io/redirect/integration/?domain=tibber_prices)\n\n"
            "After enabling the sensor, regenerate the ApexCharts YAML."
        )

    return {"title": title, "message": message}


def _get_missing_cards_notification(language: str, missing_cards: list[str]) -> dict[str, str]:
    """Get notification texts for missing custom cards."""
    title = get_translation(["apexcharts", "notification", "missing_cards", "title"], language)
    message = get_translation(["apexcharts", "notification", "missing_cards", "message"], language)

    if not title:
        title = get_translation(["apexcharts", "notification", "missing_cards", "title"], "en")
    if not message:
        message = get_translation(["apexcharts", "notification", "missing_cards", "message"], "en")

    if not title:
        title = "Tibber Prices: Missing Custom Cards"
    if not message:
        message = (
            "The following custom cards are required but not installed:\n"
            "{cards}\n\n"
            "Please click the links above to install them from HACS."
        )

    # Replace {cards} placeholder
    cards_list = "\n".join(missing_cards)
    message = message.replace("{cards}", cards_list)

    return {"title": title, "message": message}


async def handle_apexcharts_yaml(call: ServiceCall) -> dict[str, Any]:  # noqa: PLR0912, PLR0915, C901
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
    resolution = call.data.get("resolution", "interval")
    highlight_best_price = call.data.get("highlight_best_price", True)
    highlight_peak_price = call.data.get("highlight_peak_price", False)

    # Get user's language from hass config
    user_language = hass.config.language or "en"

    # Get coordinator to access price data (for currency) and config entry for display settings
    config_entry, coordinator, _ = get_entry_and_data(hass, entry_id)
    # Get currency from coordinator data
    currency = coordinator.data.get("currency", "EUR")

    # Get user's display unit preference (subunit or base currency)
    display_mode = config_entry.options.get(CONF_CURRENCY_DISPLAY_MODE, DISPLAY_MODE_SUBUNIT)
    use_subunit = display_mode == DISPLAY_MODE_SUBUNIT
    price_unit = get_display_unit_string(config_entry, currency)

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

    # Get translated names for overlays (best/peak)
    best_price_name = get_translation(["apexcharts", "best_price_period_name"], user_language) or "Best Price Period"
    peak_price_name = get_translation(["apexcharts", "peak_price_period_name"], user_language) or "Peak Price Period"

    # Track overlays added for tooltip index calculation later
    best_overlay_added = False
    peak_overlay_added = False

    # Add best price period highlight overlay FIRST (so it renders behind all other series)
    if highlight_best_price and entity_map:
        # Create vertical highlight bands using separate Y-axis (0-1 range)
        # This creates a semi-transparent overlay from bottom to top without affecting price scale
        # Conditionally include day parameter (omit for rolling window mode)
        # For rolling_window and rolling_window_autozoom, omit day parameter (dynamic selection)
        day_param = "" if day in ("rolling_window", "rolling_window_autozoom", None) else f"day: ['{day}'], "

        # Store original prices for tooltip, but map to 1 for full-height overlay
        # Use user's display unit preference for period data too
        subunit_param = "true" if use_subunit else "false"
        best_price_generator = (
            f"const response = await hass.callWS({{ "
            f"type: 'call_service', "
            f"domain: 'tibber_prices', "
            f"service: 'get_chartdata', "
            f"return_response: true, "
            f"service_data: {{ entry_id: '{entry_id}', {day_param}"
            f"period_filter: 'best_price', resolution: '{resolution}', "
            f"output_format: 'array_of_arrays', insert_nulls: 'segments', subunit_currency: {subunit_param} }} }}); "
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
                "color": "rgba(46, 204, 113, 0.05)",  # Ultra-subtle green overlay (barely visible)
                "yaxis_id": "highlight",  # Use separate Y-axis (0-1) for full-height overlay
                "show": {"legend_value": False, "in_header": False, "in_legend": False},
                "data_generator": best_price_generator,
                "stroke_width": 0,
            }
        )
        best_overlay_added = True

    # Add peak price period highlight overlay (renders behind series as well)
    if highlight_peak_price and entity_map:
        # Conditionally include day parameter (omit for rolling window mode)
        day_param = "" if day in ("rolling_window", "rolling_window_autozoom", None) else f"day: ['{day}'], "
        subunit_param = "true" if use_subunit else "false"
        peak_price_generator = (
            f"const response = await hass.callWS({{ "
            f"type: 'call_service', "
            f"domain: 'tibber_prices', "
            f"service: 'get_chartdata', "
            f"return_response: true, "
            f"service_data: {{ entry_id: '{entry_id}', {day_param}"
            f"period_filter: 'peak_price', resolution: '{resolution}', "
            f"output_format: 'array_of_arrays', insert_nulls: 'segments', subunit_currency: {subunit_param} }} }}); "
            f"const originalData = response.response.data; "
            f"return originalData.map((point, i) => {{ "
            f"const result = [point[0], point[1] === null ? null : 1]; "
            f"result.originalPrice = point[1]; "
            f"return result; "
            f"}});"
        )

        peak_price_entity = next(iter(entity_map.values()))

        series.append(
            {
                "entity": peak_price_entity,
                "name": peak_price_name,
                "type": "area",
                "color": "rgba(231, 76, 60, 0.06)",  # Subtle red overlay for peak price
                "yaxis_id": "highlight",
                "show": {"legend_value": False, "in_header": False, "in_legend": False},
                "data_generator": peak_price_generator,
                "stroke_width": 0,
            }
        )
        peak_overlay_added = True

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
        # For rolling_window and rolling_window_autozoom, omit day parameter (dynamic selection)
        day_param = "" if day in ("rolling_window", "rolling_window_autozoom", None) else f"day: ['{day}'], "

        # For rolling window modes, we'll capture metadata for dynamic config
        # For static day modes, just return data array
        # Use user's display unit preference for all data requests
        subunit_param = "true" if use_subunit else "false"
        if day in ("rolling_window", "rolling_window_autozoom", None):
            data_generator = (
                f"const response = await hass.callWS({{ "
                f"type: 'call_service', "
                f"domain: 'tibber_prices', "
                f"service: 'get_chartdata', "
                f"return_response: true, "
                f"service_data: {{ entry_id: '{entry_id}', {day_param}{filter_param}, resolution: '{resolution}', "
                f"output_format: 'array_of_arrays', insert_nulls: 'segments', subunit_currency: {subunit_param}, "
                f"connect_segments: true }} }}); "
                f"return response.response.data;"
            )
        else:
            # Static day modes: just return data (no metadata needed)
            data_generator = (
                f"const response = await hass.callWS({{ "
                f"type: 'call_service', "
                f"domain: 'tibber_prices', "
                f"service: 'get_chartdata', "
                f"return_response: true, "
                f"service_data: {{ entry_id: '{entry_id}', {day_param}{filter_param}, resolution: '{resolution}', "
                f"output_format: 'array_of_arrays', insert_nulls: 'segments', subunit_currency: {subunit_param}, "
                f"connect_segments: true }} }}); "
                f"return response.response.data;"
            )
        # Configure show options based on level_type and level_key
        # rating_level LOW/HIGH: Show raw state in header (entity state = min/max price of day)
        # rating_level NORMAL: Hide from header (not meaningful as extrema)
        # level (VERY_CHEAP/CHEAP/etc): Hide from header (entity state is aggregated value)
        if level_type == "rating_level" and level_key in (PRICE_RATING_LOW, PRICE_RATING_HIGH):
            show_config = {"legend_value": False, "in_header": "raw"}
        else:
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
                "stroke_width": 1.5,
            }
        )

    # Note: Extrema markers don't work with data_generator approach
    # ApexCharts card requires direct entity data for extremas feature, not dynamically generated data

    # Get translated title based on level_type
    title_key = "title_rating_level" if level_type == "rating_level" else "title_level"
    title = get_translation(["apexcharts", title_key], user_language) or (
        "Price Phases Daily Progress" if level_type == "rating_level" else "Price Level"
    )

    # Add translated day to title (only for fixed day views, not for dynamic modes)
    if day and day not in ("rolling_window", "rolling_window_autozoom"):
        day_translated = get_translation(["selector", "day", "options", day], user_language) or day.capitalize()
        title = f"{title} - {day_translated}"

    # Configure span based on selected day
    # For rolling window modes, use config-template-card for dynamic config
    if day == "yesterday":
        span_config = {"start": "day", "offset": "-1d"}
        graph_span_value = None
        use_template = False
    elif day == "tomorrow":
        span_config = {"start": "day", "offset": "+1d"}
        graph_span_value = None
        use_template = False
    elif day == "rolling_window":
        # Rolling 48h window: yesterday+today OR today+tomorrow (shifts at 13:00)
        span_config = None  # Will be set in template
        graph_span_value = "48h"
        use_template = True
    elif day == "rolling_window_autozoom":
        # Rolling 48h window with auto-zoom: yesterday+today OR today+tomorrow (shifts at 13:00)
        # Auto-zooms based on current time (2h lookback + remaining time)
        span_config = None  # Will be set in template
        graph_span_value = None  # Will be set in template
        use_template = True
    elif day:  # today (explicit)
        span_config = {"start": "day"}
        graph_span_value = None
        use_template = False
    else:  # Rolling window mode (None - same as rolling_window)
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
            "show_states": False,
        },
        "apex_config": {
            "chart": {
                "animations": {"enabled": False},
                "toolbar": {"show": True, "tools": {"zoom": True, "pan": True}},
                "zoom": {"enabled": True},
            },
            "stroke": {"curve": "stepline"},
            "fill": {
                "type": "gradient",
                "opacity": 0.45,
                "gradient": {
                    "shade": "light",
                    "type": "vertical",
                    "shadeIntensity": 0.2,
                    "opacityFrom": [0.5, 0.7, 0.7, 0.7, 0.7, 0.7],
                    "opacityTo": 0.25,
                    "stops": [50, 100],
                },
            },
            "dataLabels": {"enabled": False},
            "legend": {
                "show": False,
                "position": "bottom",
                "horizontalAlign": "center",
            },
            "grid": {
                "show": True,
                "borderColor": "rgba(144, 164, 174, 0.35)",
                "strokeDashArray": 0,
                "xaxis": {"lines": {"show": False}},
                "yaxis": {"lines": {"show": True}},
            },
            "markers": {
                "size": 0,  # No markers on data points
                "hover": {"size": 3},  # Show marker only on hover
                "colors": "#ff0000",
                "fillOpacity": 0.5,
                "strokeWidth": 5,
                "strokeColors": "#ff0000",
                "strokeOpacity": 0.15,
                "showNullDataPoints": False,
            },
            "tooltip": {
                "enabled": True,
                "shared": True,  # Combine tooltips from all series at same x-value
                # enabledOnSeries will be set dynamically below based on overlays
                "enabledOnSeries": [],
                "marker": {
                    "show": False,
                },
                "x": {
                    "show": False,
                },
            },
        },
        "yaxis": [
            {
                "id": "price",
                "apex_config": {"title": {"text": price_unit}},
            },
            {
                "id": "highlight",
                "min": 0,
                "max": 1,
                "show": False,  # Hide this axis (only for highlight overlay)
                "opposite": True,
                "apex_config": {
                    "forceNiceScale": True,
                    "tickAmount": 4,
                },
            },
        ],
        "now": (
            {"show": True, "color": "#8e24aa"}
            if day == "rolling_window_autozoom"
            else {"show": True, "color": "#8e24aa", "label": "🕒 LIVE"}
        ),
        "all_series_config": {
            "float_precision": 2,
        },
        "series": series,
    }

    # Dynamically set tooltip enabledOnSeries to exclude overlay indices
    overlay_count = (1 if best_overlay_added else 0) + (1 if peak_overlay_added else 0)
    result["apex_config"]["tooltip"]["enabledOnSeries"] = list(range(overlay_count, len(series)))

    # For rolling window mode and today_tomorrow, wrap in config-template-card for dynamic config
    if use_template:
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
            if day == "rolling_window_autozoom":
                # rolling_window_autozoom mode: Dynamic graph_span with auto-zoom
                # Shows last 120 min (8 intervals) + remaining minutes until end of time window
                # Auto-zooms every 15 minutes when current interval completes
                # When tomorrow data arrives after 13:00, extends to show tomorrow too
                #
                # Key principle: graph_span must always be divisible by 15 (full intervals)
                # The current (running) interval stays included until it completes
                #
                # Calculation:
                # 1. Round current time UP to next quarter-hour (include running interval)
                # 2. Calculate minutes from end of running interval to midnight
                # 3. Round to ensure full 15-minute intervals
                # 4. Add 120min lookback (always 8 intervals)
                # 5. If tomorrow data available: add 1440min (96 intervals)
                #
                # Example timeline (without tomorrow data):
                # 08:00 → next quarter: 08:15 → to midnight: 945min → span: 120+945 = 1065min (71 intervals)
                # 08:07 → next quarter: 08:15 → to midnight: 945min → span: 120+945 = 1065min (stays same)
                # 08:15 → next quarter: 08:30 → to midnight: 930min → span: 120+930 = 1050min (70 intervals)
                # 14:23 → next quarter: 14:30 → to midnight: 570min → span: 120+570 = 690min (46 intervals)
                #
                # After 13:00 with tomorrow data:
                # 14:00 → next quarter: 14:15 → to midnight: 585min → span: 120+585+1440 = 2145min (143 intervals)
                # 14:15 → next quarter: 14:30 → to midnight: 570min → span: 120+570+1440 = 2130min (142 intervals)
                template_graph_span = (
                    f"const now = new Date(); "
                    f"const currentMinute = now.getMinutes(); "
                    f"const nextQuarterMinute = Math.ceil(currentMinute / 15) * 15; "
                    f"const currentIntervalEnd = new Date(now); "
                    f"if (nextQuarterMinute === 60) {{ "
                    f"  currentIntervalEnd.setHours(now.getHours() + 1, 0, 0, 0); "
                    f"}} else {{ "
                    f"  currentIntervalEnd.setMinutes(nextQuarterMinute, 0, 0); "
                    f"}} "
                    f"const midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1, 0, 0, 0); "
                    f"const minutesFromIntervalEndToMidnight = Math.ceil((midnight - currentIntervalEnd) / 60000); "
                    f"const minutesRounded = Math.ceil(minutesFromIntervalEndToMidnight / 15) * 15; "
                    f"const lookback = 120; "
                    f"const hasTomorrowData = states['{tomorrow_data_sensor}'].state === 'on'; "
                    f"const totalMinutes = lookback + minutesRounded + (hasTomorrowData ? 1440 : 0); "
                    f"totalMinutes + 'min';"
                )

                # Find current_interval_price sensor for 15-minute update trigger
                current_price_sensor = next(
                    (
                        entity.entity_id
                        for entity in entity_registry.entities.values()
                        if entity.config_entry_id == entry_id
                        and entity.unique_id
                        and entity.unique_id.endswith("_current_interval_price")
                    ),
                    None,
                )

                trigger_entities = [tomorrow_data_sensor]
                if current_price_sensor:
                    trigger_entities.append(current_price_sensor)

                # Get metadata from chart_metadata sensor (preferred) or static fallback
                # The chart_metadata sensor provides yaxis_min and yaxis_max
                # as attributes, avoiding the need for async service calls in templates
                chart_metadata_sensor = next(
                    (
                        entity.entity_id
                        for entity in entity_registry.entities.values()
                        if entity.config_entry_id == entry_id
                        and entity.unique_id
                        and entity.unique_id.endswith("_chart_metadata")
                    ),
                    None,
                )

                # Track warning if sensor not available
                metadata_warning = None
                use_sensor_metadata = False

                # Check if sensor exists and is ready
                if chart_metadata_sensor:
                    metadata_state = hass.states.get(chart_metadata_sensor)
                    if metadata_state and metadata_state.state == "ready":
                        # Sensor ready - will use template variables
                        use_sensor_metadata = True
                    else:
                        # Sensor not ready - will show notification
                        metadata_warning = True
                else:
                    # Sensor not found - will show notification
                    metadata_warning = True

                # Set fallback values if sensor not used
                if not use_sensor_metadata:
                    # Build yaxis config (only include min/max if not None)
                    yaxis_price_config = {
                        "id": "price",
                        "apex_config": {
                            "title": {"text": price_unit},
                            "decimalsInFloat": 0 if use_subunit else 1,
                            "forceNiceScale": True,
                            "showAlways": True,
                            "tickAmount": 4,
                        },
                    }

                    entities_list = trigger_entities
                else:
                    # Use template variables to read sensor dynamically
                    # Add chart_metadata sensor to entities list
                    entities_list = [*trigger_entities, chart_metadata_sensor]

                    # Build yaxis config with template variables
                    yaxis_price_config = {
                        "id": "price",
                        "min": "${v_yaxis_min}",
                        "max": "${v_yaxis_max}",
                        "apex_config": {
                            "title": {"text": price_unit},
                            "decimalsInFloat": 0 if use_subunit else 1,
                            "forceNiceScale": True,
                            "showAlways": True,
                            "tickAmount": 4,
                        },
                    }

                # Build variables dict
                variables_dict = {"v_graph_span": template_graph_span}
                if use_sensor_metadata:
                    # Add dynamic metadata variables from sensor
                    variables_dict.update(
                        {
                            "v_yaxis_min": f"states['{chart_metadata_sensor}'].attributes.yaxis_min",
                            "v_yaxis_max": f"states['{chart_metadata_sensor}'].attributes.yaxis_max",
                        }
                    )

                result_dict = {
                    "type": "custom:config-template-card",
                    "variables": variables_dict,
                    "entities": entities_list,
                    "card": {
                        **result,
                        "span": {"start": "minute", "offset": "-120min"},
                        "graph_span": "${v_graph_span}",
                        "yaxis": [
                            yaxis_price_config,
                            {
                                "id": "highlight",
                                "min": 0,
                                "max": 1,
                                "show": False,
                                "opposite": True,
                                "apex_config": {
                                    "forceNiceScale": True,
                                    "tickAmount": 4,
                                },
                            },
                        ],
                        "apex_config": {
                            **result["apex_config"],
                            "fill": {
                                "type": "gradient",
                                "opacity": 0.45,
                                "gradient": {
                                    "shade": "light",
                                    "type": "vertical",
                                    "shadeIntensity": 0.2,
                                    "opacityFrom": [0.5, 0.7, 0.7, 0.7, 0.7, 0.7],
                                    "opacityTo": 0.25,
                                    "stops": [50, 100],
                                },
                            },
                        },
                    },
                }

                # Create separate notifications for different issues
                if metadata_warning:
                    # Notification 1: Chart Metadata Sensor disabled
                    notification_texts = _get_sensor_disabled_notification(user_language)
                    await hass.services.async_call(
                        "persistent_notification",
                        "create",
                        {
                            "message": notification_texts["message"],
                            "title": notification_texts["title"],
                            "notification_id": f"tibber_prices_chart_metadata_{entry_id}",
                        },
                    )

                # Check which custom cards are installed (always check, independent of sensor state)
                installed_cards = _check_custom_cards_installed(hass)
                missing_cards = [
                    "[apexcharts-card](https://my.home-assistant.io/redirect/hacs_repository/?owner=RomRider&repository=apexcharts-card)"
                    if not installed_cards["apexcharts-card"]
                    else None,
                    "[config-template-card](https://my.home-assistant.io/redirect/hacs_repository/?owner=iantrich&repository=config-template-card)"
                    if not installed_cards["config-template-card"]
                    else None,
                ]
                missing_cards = [card for card in missing_cards if card]  # Filter out None

                if missing_cards:
                    # Notification 2: Missing Custom Cards
                    notification_texts = _get_missing_cards_notification(user_language, missing_cards)
                    await hass.services.async_call(
                        "persistent_notification",
                        "create",
                        {
                            "message": notification_texts["message"],
                            "title": notification_texts["title"],
                            "notification_id": f"tibber_prices_missing_cards_{entry_id}",
                        },
                    )

                return result_dict
            # Rolling window modes (day is None or rolling_window): Dynamic offset
            # Add graph_span to base config (48h window)
            result["graph_span"] = graph_span_value
            # Wrap in config-template-card with dynamic offset calculation
            # Template checks if tomorrow data is available (binary sensor state)
            # If 'on' (tomorrow data available) → offset +1d (show today+tomorrow)
            # If 'off' (no tomorrow data) → offset +0d (show yesterday+today)
            template_value = f"states['{tomorrow_data_sensor}'].state === 'on' ? '+1d' : '+0d'"

            # Get metadata from chart_metadata sensor (preferred) or static fallback
            # The chart_metadata sensor provides yaxis_min and yaxis_max
            # as attributes, avoiding the need for async service calls in templates
            chart_metadata_sensor = next(
                (
                    entity.entity_id
                    for entity in entity_registry.entities.values()
                    if entity.config_entry_id == entry_id
                    and entity.unique_id
                    and entity.unique_id.endswith("_chart_metadata")
                ),
                None,
            )

            # Track warning if sensor not available
            metadata_warning = None
            use_sensor_metadata = False

            # Check if sensor exists and is ready
            if chart_metadata_sensor:
                metadata_state = hass.states.get(chart_metadata_sensor)
                if metadata_state and metadata_state.state == "ready":
                    # Sensor ready - will use template variables
                    use_sensor_metadata = True
                else:
                    # Sensor not ready - will show notification
                    metadata_warning = True
            else:
                # Sensor not found - will show notification
                metadata_warning = True

            # Set fallback values if sensor not used
            if not use_sensor_metadata:
                # Build yaxis config (only include min/max if not None)
                yaxis_price_config = {
                    "id": "price",
                    "apex_config": {
                        "title": {"text": price_unit},
                        "decimalsInFloat": 0 if use_subunit else 1,
                        "forceNiceScale": True,
                        "showAlways": True,
                        "tickAmount": 4,
                    },
                }

                entities_list = [tomorrow_data_sensor]
            else:
                # Use template variables to read sensor dynamically
                # Add chart_metadata sensor to entities list
                entities_list = [tomorrow_data_sensor, chart_metadata_sensor]

                # Build yaxis config with template variables
                yaxis_price_config = {
                    "id": "price",
                    "min": "${v_yaxis_min}",
                    "max": "${v_yaxis_max}",
                    "apex_config": {
                        "title": {"text": price_unit},
                        "decimalsInFloat": 0 if use_subunit else 1,
                        "forceNiceScale": True,
                        "showAlways": True,
                        "tickAmount": 4,
                    },
                }

            # Build variables dict
            variables_dict = {"v_offset": template_value}
            if use_sensor_metadata:
                # Add dynamic metadata variables from sensor
                variables_dict.update(
                    {
                        "v_yaxis_min": f"states['{chart_metadata_sensor}'].attributes.yaxis_min",
                        "v_yaxis_max": f"states['{chart_metadata_sensor}'].attributes.yaxis_max",
                    }
                )

            result_dict = {
                "type": "custom:config-template-card",
                "variables": variables_dict,
                "entities": entities_list,
                "card": {
                    **result,
                    "span": {
                        "end": "day",
                        "offset": "${v_offset}",
                    },
                    "yaxis": [
                        yaxis_price_config,
                        {
                            "id": "highlight",
                            "min": 0,
                            "max": 1,
                            "show": False,
                            "opposite": True,
                            "apex_config": {
                                "forceNiceScale": True,
                                "tickAmount": 4,
                            },
                        },
                    ],
                    "apex_config": {
                        **result["apex_config"],
                        "fill": {
                            "type": "gradient",
                            "opacity": 0.45,
                            "gradient": {
                                "shade": "light",
                                "type": "vertical",
                                "shadeIntensity": 0.2,
                                "opacityFrom": [0.5, 0.7, 0.7, 0.7, 0.7, 0.7],
                                "opacityTo": 0.25,
                                "stops": [50, 100],
                            },
                        },
                    },
                },
            }

            # Create separate notifications for different issues
            if metadata_warning:
                # Notification 1: Chart Metadata Sensor disabled
                notification_texts = _get_sensor_disabled_notification(user_language)
                await hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {
                        "message": notification_texts["message"],
                        "title": notification_texts["title"],
                        "notification_id": f"tibber_prices_chart_metadata_{entry_id}",
                    },
                )

            # Check which custom cards are installed (always check, independent of sensor state)
            installed_cards = _check_custom_cards_installed(hass)
            missing_cards = [
                "[apexcharts-card](https://my.home-assistant.io/redirect/hacs_repository/?owner=RomRider&repository=apexcharts-card)"
                if not installed_cards["apexcharts-card"]
                else None,
                "[config-template-card](https://my.home-assistant.io/redirect/hacs_repository/?owner=iantrich&repository=config-template-card)"
                if not installed_cards["config-template-card"]
                else None,
            ]
            missing_cards = [card for card in missing_cards if card]  # Filter out None

            if missing_cards:
                # Notification 2: Missing Custom Cards
                notification_texts = _get_missing_cards_notification(user_language, missing_cards)
                await hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {
                        "message": notification_texts["message"],
                        "title": notification_texts["title"],
                        "notification_id": f"tibber_prices_missing_cards_{entry_id}",
                    },
                )

            return result_dict

        # Fallback if sensor not found
        if day == "rolling_window_autozoom":
            # Fallback: show today with 24h span
            result["span"] = {"start": "day"}
            result["graph_span"] = "24h"
        else:
            # Rolling window fallback (rolling_window or None): just use +1d offset
            result["span"] = {"end": "day", "offset": "+1d"}
            result["graph_span"] = "48h"
        return result

    # Add span for fixed-day views
    if span_config:
        result["span"] = span_config

    # Add graph_span if needed
    if graph_span_value:
        result["graph_span"] = graph_span_value

    return result
