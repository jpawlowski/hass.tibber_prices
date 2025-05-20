"""Constants for the Tibber Price Analytics integration."""

import json
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import aiofiles

from homeassistant.core import HomeAssistant

# Version should match manifest.json
VERSION = "0.1.0"

DOMAIN = "tibber_prices"
CONF_ACCESS_TOKEN = "access_token"  # noqa: S105
CONF_EXTENDED_DESCRIPTIONS = "extended_descriptions"
CONF_BEST_PRICE_FLEX = "best_price_flex"
CONF_PEAK_PRICE_FLEX = "peak_price_flex"

ATTRIBUTION = "Data provided by Tibber"

# Integration name should match manifest.json
DEFAULT_NAME = "Tibber Price Information & Ratings"
DEFAULT_EXTENDED_DESCRIPTIONS = False
DEFAULT_BEST_PRICE_FLEX = 5  # 5% flexibility for best price (user-facing, percent)
DEFAULT_PEAK_PRICE_FLEX = 5  # 5% flexibility for peak price (user-facing, percent)

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

# Price rating constants
PRICE_RATING_NORMAL = "NORMAL"
PRICE_RATING_LOW = "LOW"
PRICE_RATING_HIGH = "HIGH"

# Mapping for comparing price ratings (used for sorting)
PRICE_RATING_MAPPING = {
    PRICE_RATING_LOW: -1,
    PRICE_RATING_NORMAL: 0,
    PRICE_RATING_HIGH: 1,
}

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


async def async_get_translation(
    hass: HomeAssistant,
    path: Sequence[str],
    language: str = "en",
) -> Any:
    """
    Get a translation value by path asynchronously.

    Args:
        hass: HomeAssistant instance
        path: A sequence of keys defining the path to the translation value
        language: The language code (defaults to English)

    Returns:
        The translation value if found, None otherwise

    """
    translations = await async_load_translations(hass, language)

    # Navigate to the requested path
    current = translations
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]

    return current


def get_translation(
    path: Sequence[str],
    language: str = "en",
) -> Any:
    """
    Get a translation value by path synchronously from the cache.

    This function only accesses the cached translations to avoid blocking I/O.

    Args:
        path: A sequence of keys defining the path to the translation value
        language: The language code (defaults to English)

    Returns:
        The translation value if found in cache, None otherwise

    """
    # Only return from cache to avoid blocking I/O
    if language not in _TRANSLATIONS_CACHE:
        # Fall back to English if the requested language is not available
        if language != "en" and "en" in _TRANSLATIONS_CACHE:
            language = "en"
        else:
            return None

    # Navigate to the requested path
    current = _TRANSLATIONS_CACHE[language]
    for key in path:
        if not isinstance(current, dict):
            return None
        if key not in current:
            # Log the missing key for debugging
            LOGGER.debug("Translation key '%s' not found in path %s for language %s", key, path, language)
            return None
        current = current[key]

    return current


# Convenience functions for backward compatibility and common usage patterns
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
    entity_data = await async_get_translation(hass, [entity_type, entity_key], language)

    # Handle the case where entity_data is a string (for description field)
    if isinstance(entity_data, str) and field == "description":
        return entity_data

    # Handle the case where entity_data is a dict
    if isinstance(entity_data, dict) and field in entity_data:
        return entity_data[field]

    return None


def get_entity_description(
    entity_type: str,
    entity_key: str,
    language: str = "en",
    field: str = "description",
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
    entity_data = get_translation([entity_type, entity_key], language)

    # Handle the case where entity_data is a string (for description field)
    if isinstance(entity_data, str) and field == "description":
        return entity_data

    # Handle the case where entity_data is a dict
    if isinstance(entity_data, dict) and field in entity_data:
        return entity_data[field]

    return None


async def async_get_price_level_translation(
    hass: HomeAssistant,
    level: str,
    language: str = "en",
) -> str | None:
    """
    Get a localized translation for a price level asynchronously.

    Args:
        hass: HomeAssistant instance
        level: The price level (e.g., VERY_CHEAP, NORMAL, etc.)
        language: The language code (defaults to English)

    Returns:
        The localized price level if found, None otherwise

    """
    return await async_get_translation(hass, ["sensor", "price_level", "price_levels", level], language)


def get_price_level_translation(
    level: str,
    language: str = "en",
) -> str | None:
    """
    Get a localized translation for a price level synchronously from the cache.

    This function only accesses the cached translations to avoid blocking I/O.

    Args:
        level: The price level (e.g., VERY_CHEAP, NORMAL, etc.)
        language: The language code (defaults to English)

    Returns:
        The localized price level if found in cache, None otherwise

    """
    return get_translation(["sensor", "price_level", "price_levels", level], language)
