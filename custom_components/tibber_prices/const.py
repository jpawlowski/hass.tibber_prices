"""Constants for the Tibber Price Analytics integration."""

import json
import logging
from pathlib import Path

import aiofiles

from homeassistant.core import HomeAssistant

# Version should match manifest.json
VERSION = "0.1.0"

DOMAIN = "tibber_prices"
CONF_ACCESS_TOKEN = "access_token"  # noqa: S105
CONF_EXTENDED_DESCRIPTIONS = "extended_descriptions"

ATTRIBUTION = "Data provided by Tibber"

# Update interval in seconds
SCAN_INTERVAL = 60 * 5  # 5 minutes

# Integration name should match manifest.json
DEFAULT_NAME = "Tibber Price Information & Ratings"
DEFAULT_EXTENDED_DESCRIPTIONS = False

# Price level constants
PRICE_LEVEL_NORMAL = "NORMAL"
PRICE_LEVEL_CHEAP = "CHEAP"
PRICE_LEVEL_VERY_CHEAP = "VERY_CHEAP"
PRICE_LEVEL_EXPENSIVE = "EXPENSIVE"
PRICE_LEVEL_VERY_EXPENSIVE = "VERY_EXPENSIVE"

# Mapping for comparing price levels (used for sorting)
PRICE_LEVEL_MAPPING = {
    PRICE_LEVEL_VERY_CHEAP: -2,
    PRICE_LEVEL_CHEAP: -1,
    PRICE_LEVEL_NORMAL: 0,
    PRICE_LEVEL_EXPENSIVE: 1,
    PRICE_LEVEL_VERY_EXPENSIVE: 2,
}

# Sensor type constants
SENSOR_TYPE_PRICE_LEVEL = "price_level"

LOGGER = logging.getLogger(__package__)

# Path to custom translations directory
CUSTOM_TRANSLATIONS_DIR = Path(__file__).parent / "custom_translations"

# Cache for translations to avoid repeated file reads
_TRANSLATIONS_CACHE: dict[str, dict] = {}


async def async_load_translations(hass: HomeAssistant, language: str) -> dict:
    """
    Load translations from file asynchronously.

    Args:
        hass: HomeAssistant instance
        language: The language code to load

    Returns:
        The loaded translations as a dictionary

    """
    # Use a key that includes the language parameter
    cache_key = f"{DOMAIN}_translations_{language}"

    # Check if we have an instance in hass.data
    if cache_key in hass.data:
        return hass.data[cache_key]

    # Check the module-level cache
    if language in _TRANSLATIONS_CACHE:
        return _TRANSLATIONS_CACHE[language]

    # Determine the file path
    file_path = CUSTOM_TRANSLATIONS_DIR / f"{language}.json"
    if not file_path.exists():
        # Fall back to English if requested language not found
        file_path = CUSTOM_TRANSLATIONS_DIR / "en.json"
        if not file_path.exists():
            LOGGER.debug("No custom translations found at %s", file_path)
            empty_cache = {}
            _TRANSLATIONS_CACHE[language] = empty_cache
            hass.data[cache_key] = empty_cache
            return empty_cache

    try:
        # Read the file asynchronously
        async with aiofiles.open(file_path, encoding="utf-8") as f:
            content = await f.read()
            translations = json.loads(content)

            # Store in both caches for future calls
            _TRANSLATIONS_CACHE[language] = translations
            hass.data[cache_key] = translations

            return translations

    except (OSError, json.JSONDecodeError) as err:
        LOGGER.warning("Error loading custom translations file: %s", err)
        empty_cache = {}
        _TRANSLATIONS_CACHE[language] = empty_cache
        hass.data[cache_key] = empty_cache
        return empty_cache

    except Exception:  # pylint: disable=broad-except
        LOGGER.exception("Unexpected error loading custom translations")
        empty_cache = {}
        _TRANSLATIONS_CACHE[language] = empty_cache
        hass.data[cache_key] = empty_cache
        return empty_cache


async def async_get_entity_description(
    hass: HomeAssistant,
    entity_type: str,
    entity_key: str,
    language: str = "en",
    field: str = "description",
) -> str | None:
    """
    Get a specific field from the entity's custom translations asynchronously.

    Args:
        hass: HomeAssistant instance
        entity_type: The type of entity (sensor, binary_sensor, etc.)
        entity_key: The key of the entity
        language: The language code (defaults to English)
        field: The field to retrieve (description, long_description, usage_tips)

    Returns:
        The requested field's value if found, None otherwise

    """
    translations = await async_load_translations(hass, language)

    # Check if entity exists in translations
    if entity_type in translations and entity_key in translations[entity_type]:
        # Get the entity data
        entity_data = translations[entity_type][entity_key]

        # If entity_data is a string, return it only for description field
        if isinstance(entity_data, str) and field == "description":
            return entity_data

        # If entity_data is a dict, look for the requested field
        if isinstance(entity_data, dict) and field in entity_data:
            return entity_data[field]

    return None


def get_entity_description(
    entity_type: str, entity_key: str, language: str = "en", field: str = "description"
) -> str | None:
    """
    Get entity description synchronously from the cache.

    This function only accesses the cached translations to avoid blocking I/O.

    Args:
        entity_type: The type of entity
        entity_key: The key of the entity
        language: The language code
        field: The field to retrieve

    Returns:
        The requested field's value if found in cache, None otherwise

    """
    # Only return from cache to avoid blocking I/O
    if language in _TRANSLATIONS_CACHE:
        translations = _TRANSLATIONS_CACHE[language]
        if entity_type in translations and entity_key in translations[entity_type]:
            entity_data = translations[entity_type][entity_key]

            if isinstance(entity_data, str) and field == "description":
                return entity_data

            if isinstance(entity_data, dict) and field in entity_data:
                return entity_data[field]

    return None
