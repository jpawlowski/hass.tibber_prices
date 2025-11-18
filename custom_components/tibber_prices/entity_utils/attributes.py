"""Common attribute utilities for Tibber Prices entities."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from ..data import TibberPricesConfigEntry  # noqa: TID252


def build_timestamp_attribute(interval_data: dict | None) -> str | None:
    """
    Build timestamp attribute from interval data.

    Extracts startsAt field consistently across all sensors.

    Args:
        interval_data: Interval data dictionary containing startsAt field

    Returns:
        ISO format timestamp string or None

    """
    if not interval_data:
        return None
    return interval_data.get("startsAt")


def build_period_attributes(period_data: dict) -> dict:
    """
    Build common period attributes (start, end, duration, timestamp).

    Used by binary sensors for period-based entities.

    Args:
        period_data: Period data dictionary

    Returns:
        Dictionary with common period attributes

    """
    return {
        "start": period_data.get("start"),
        "end": period_data.get("end"),
        "duration_minutes": period_data.get("duration_minutes"),
        "timestamp": period_data.get("start"),  # Timestamp = period start
    }


def add_description_attributes(  # noqa: PLR0913
    attributes: dict,
    platform: str,
    translation_key: str | None,
    hass: HomeAssistant,
    config_entry: TibberPricesConfigEntry,
    *,
    position: str = "end",
) -> None:
    """
    Add description attributes from custom translations to an existing attributes dict.

    Adds description (always), and optionally long_description and usage_tips if
    CONF_EXTENDED_DESCRIPTIONS is enabled in config.

    This function modifies the attributes dict in-place. By default, descriptions are
    added at the END of the dict (after all other attributes). For special cases like
    chart_data_export, use position="before_service_data" to add descriptions before
    service data attributes.

    Args:
        attributes: Existing attributes dict to modify (in-place)
        platform: Platform name ("sensor" or "binary_sensor")
        translation_key: Translation key for entity
        hass: Home Assistant instance
        config_entry: Config entry with options
        position: Where to add descriptions:
                 - "end" (default): Add at the very end
                 - "before_service_data": Add before service data (for chart_data_export)

    """
    if not translation_key or not hass:
        return

    # Import here to avoid circular dependency
    from ..const import (  # noqa: PLC0415, TID252
        CONF_EXTENDED_DESCRIPTIONS,
        DEFAULT_EXTENDED_DESCRIPTIONS,
        get_entity_description,
    )

    language = hass.config.language if hass.config.language else "en"

    # Build description dict
    desc_attrs: dict[str, str] = {}

    description = get_entity_description(platform, translation_key, language, "description")
    if description:
        desc_attrs["description"] = description

    extended_descriptions = config_entry.options.get(
        CONF_EXTENDED_DESCRIPTIONS,
        config_entry.data.get(CONF_EXTENDED_DESCRIPTIONS, DEFAULT_EXTENDED_DESCRIPTIONS),
    )

    if extended_descriptions:
        long_desc = get_entity_description(platform, translation_key, language, "long_description")
        if long_desc:
            desc_attrs["long_description"] = long_desc

        usage_tips = get_entity_description(platform, translation_key, language, "usage_tips")
        if usage_tips:
            desc_attrs["usage_tips"] = usage_tips

    # Add descriptions at appropriate position
    if position == "end":
        # Default: Add at the very end
        attributes.update(desc_attrs)
    elif position == "before_service_data":
        # Special case: Insert before service data
        # This is used by chart_data_export to keep our attributes before foreign data
        # We need to rebuild the dict to maintain order
        temp_attrs = dict(attributes)
        attributes.clear()

        # Add everything except service data
        for key, value in temp_attrs.items():
            if key not in ("timestamp", "error"):
                continue
            attributes[key] = value

        # Add descriptions here (before service data)
        attributes.update(desc_attrs)

        # Add service data last
        for key, value in temp_attrs.items():
            if key in ("timestamp", "error"):
                continue
            attributes[key] = value


async def async_add_description_attributes(  # noqa: PLR0913
    attributes: dict,
    platform: str,
    translation_key: str | None,
    hass: HomeAssistant,
    config_entry: TibberPricesConfigEntry,
    *,
    position: str = "end",
) -> None:
    """
    Async version of add_description_attributes.

    Adds description attributes from custom translations to an existing attributes dict.
    Uses async translation loading (calls async_get_entity_description).

    Args:
        attributes: Existing attributes dict to modify (in-place)
        platform: Platform name ("sensor" or "binary_sensor")
        translation_key: Translation key for entity
        hass: Home Assistant instance
        config_entry: Config entry with options
        position: Where to add descriptions ("end" or "before_service_data")

    """
    if not translation_key or not hass:
        return

    # Import here to avoid circular dependency
    from ..const import (  # noqa: PLC0415, TID252
        CONF_EXTENDED_DESCRIPTIONS,
        DEFAULT_EXTENDED_DESCRIPTIONS,
        async_get_entity_description,
    )

    language = hass.config.language if hass.config.language else "en"

    # Build description dict
    desc_attrs: dict[str, str] = {}

    description = await async_get_entity_description(
        hass,
        platform,
        translation_key,
        language,
        "description",
    )
    if description:
        desc_attrs["description"] = description

    extended_descriptions = config_entry.options.get(
        CONF_EXTENDED_DESCRIPTIONS,
        config_entry.data.get(CONF_EXTENDED_DESCRIPTIONS, DEFAULT_EXTENDED_DESCRIPTIONS),
    )

    if extended_descriptions:
        long_desc = await async_get_entity_description(
            hass,
            platform,
            translation_key,
            language,
            "long_description",
        )
        if long_desc:
            desc_attrs["long_description"] = long_desc

        usage_tips = await async_get_entity_description(
            hass,
            platform,
            translation_key,
            language,
            "usage_tips",
        )
        if usage_tips:
            desc_attrs["usage_tips"] = usage_tips

    # Add descriptions at appropriate position
    if position == "end":
        # Default: Add at the very end
        attributes.update(desc_attrs)
    elif position == "before_service_data":
        # Special case: Insert before service data (same logic as sync version)
        temp_attrs = dict(attributes)
        attributes.clear()

        for key, value in temp_attrs.items():
            if key not in ("timestamp", "error"):
                continue
            attributes[key] = value

        attributes.update(desc_attrs)

        for key, value in temp_attrs.items():
            if key in ("timestamp", "error"):
                continue
            attributes[key] = value
