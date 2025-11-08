"""Constants for the Tibber Price Analytics integration."""

import json
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import aiofiles

from homeassistant.const import (
    CURRENCY_DOLLAR,
    CURRENCY_EURO,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant

DOMAIN = "tibber_prices"
CONF_EXTENDED_DESCRIPTIONS = "extended_descriptions"
CONF_BEST_PRICE_FLEX = "best_price_flex"
CONF_PEAK_PRICE_FLEX = "peak_price_flex"
CONF_BEST_PRICE_MIN_DISTANCE_FROM_AVG = "best_price_min_distance_from_avg"
CONF_PEAK_PRICE_MIN_DISTANCE_FROM_AVG = "peak_price_min_distance_from_avg"
CONF_BEST_PRICE_MIN_PERIOD_LENGTH = "best_price_min_period_length"
CONF_PEAK_PRICE_MIN_PERIOD_LENGTH = "peak_price_min_period_length"
CONF_PRICE_RATING_THRESHOLD_LOW = "price_rating_threshold_low"
CONF_PRICE_RATING_THRESHOLD_HIGH = "price_rating_threshold_high"
CONF_PRICE_TREND_THRESHOLD_RISING = "price_trend_threshold_rising"
CONF_PRICE_TREND_THRESHOLD_FALLING = "price_trend_threshold_falling"

ATTRIBUTION = "Data provided by Tibber"

# Integration name should match manifest.json
DEFAULT_NAME = "Tibber Price Information & Ratings"
DEFAULT_EXTENDED_DESCRIPTIONS = False
DEFAULT_BEST_PRICE_FLEX = 15  # 15% flexibility for best price (user-facing, percent)
DEFAULT_PEAK_PRICE_FLEX = -15  # 15% flexibility for peak price (user-facing, percent)
DEFAULT_BEST_PRICE_MIN_DISTANCE_FROM_AVG = 2  # 2% minimum distance from daily average for best price
DEFAULT_PEAK_PRICE_MIN_DISTANCE_FROM_AVG = 2  # 2% minimum distance from daily average for peak price
DEFAULT_BEST_PRICE_MIN_PERIOD_LENGTH = 60  # 60 minutes minimum period length for best price (user-facing, minutes)
DEFAULT_PEAK_PRICE_MIN_PERIOD_LENGTH = 60  # 60 minutes minimum period length for peak price (user-facing, minutes)
DEFAULT_PRICE_RATING_THRESHOLD_LOW = -10  # Default rating threshold low percentage
DEFAULT_PRICE_RATING_THRESHOLD_HIGH = 10  # Default rating threshold high percentage
DEFAULT_PRICE_TREND_THRESHOLD_RISING = 5  # Default trend threshold for rising prices (%)
DEFAULT_PRICE_TREND_THRESHOLD_FALLING = -5  # Default trend threshold for falling prices (%, negative value)

# Home types
HOME_TYPE_APARTMENT = "APARTMENT"
HOME_TYPE_ROWHOUSE = "ROWHOUSE"
HOME_TYPE_HOUSE = "HOUSE"
HOME_TYPE_COTTAGE = "COTTAGE"

# Mapping for home types to their localized names
HOME_TYPES = {
    HOME_TYPE_APARTMENT: "Apartment",
    HOME_TYPE_ROWHOUSE: "Rowhouse",
    HOME_TYPE_HOUSE: "House",
    HOME_TYPE_COTTAGE: "Cottage",
}

# Currency mapping: ISO code -> (major_symbol, minor_symbol, minor_name)
# For currencies with Home Assistant constants, use those; otherwise define custom ones
CURRENCY_INFO = {
    "EUR": (CURRENCY_EURO, "ct", "cents"),
    "NOK": ("kr", "øre", "øre"),
    "SEK": ("kr", "öre", "öre"),
    "DKK": ("kr", "øre", "øre"),
    "USD": (CURRENCY_DOLLAR, "¢", "cents"),
    "GBP": ("£", "p", "pence"),
}


def get_currency_info(currency_code: str | None) -> tuple[str, str, str]:
    """
    Get currency information for a given ISO currency code.

    Args:
        currency_code: ISO 4217 currency code (e.g., 'EUR', 'NOK', 'SEK')

    Returns:
        Tuple of (major_symbol, minor_symbol, minor_name)
        Defaults to EUR if currency is not recognized

    """
    if not currency_code:
        currency_code = "EUR"

    return CURRENCY_INFO.get(currency_code.upper(), CURRENCY_INFO["EUR"])


def format_price_unit_major(currency_code: str | None) -> str:
    """
    Format the price unit string with major currency unit (e.g., '€/kWh').

    Args:
        currency_code: ISO 4217 currency code (e.g., 'EUR', 'NOK', 'SEK')

    Returns:
        Formatted unit string like '€/kWh' or 'kr/kWh'

    """
    major_symbol, _, _ = get_currency_info(currency_code)
    return f"{major_symbol}/{UnitOfPower.KILO_WATT}{UnitOfTime.HOURS}"


def format_price_unit_minor(currency_code: str | None) -> str:
    """
    Format the price unit string with minor currency unit (e.g., 'ct/kWh').

    Args:
        currency_code: ISO 4217 currency code (e.g., 'EUR', 'NOK', 'SEK')

    Returns:
        Formatted unit string like 'ct/kWh' or 'øre/kWh'

    """
    _, minor_symbol, _ = get_currency_info(currency_code)
    return f"{minor_symbol}/{UnitOfPower.KILO_WATT}{UnitOfTime.HOURS}"


# Price level constants from Tibber API
PRICE_LEVEL_VERY_CHEAP = "VERY_CHEAP"
PRICE_LEVEL_CHEAP = "CHEAP"
PRICE_LEVEL_NORMAL = "NORMAL"
PRICE_LEVEL_EXPENSIVE = "EXPENSIVE"
PRICE_LEVEL_VERY_EXPENSIVE = "VERY_EXPENSIVE"

# Price rating constants (calculated values)
PRICE_RATING_LOW = "LOW"
PRICE_RATING_NORMAL = "NORMAL"
PRICE_RATING_HIGH = "HIGH"

# Sensor options (lowercase versions for ENUM device class)
# NOTE: These constants define the valid enum options, but they are not used directly
# in sensor.py due to import timing issues. Instead, the options are defined inline
# in the SensorEntityDescription objects. Keep these in sync with sensor.py!
PRICE_LEVEL_OPTIONS = [
    PRICE_LEVEL_VERY_CHEAP.lower(),
    PRICE_LEVEL_CHEAP.lower(),
    PRICE_LEVEL_NORMAL.lower(),
    PRICE_LEVEL_EXPENSIVE.lower(),
    PRICE_LEVEL_VERY_EXPENSIVE.lower(),
]

PRICE_RATING_OPTIONS = [
    PRICE_RATING_LOW.lower(),
    PRICE_RATING_NORMAL.lower(),
    PRICE_RATING_HIGH.lower(),
]

# Mapping for comparing price levels (used for sorting)
PRICE_LEVEL_MAPPING = {
    PRICE_LEVEL_VERY_CHEAP: -2,
    PRICE_LEVEL_CHEAP: -1,
    PRICE_LEVEL_NORMAL: 0,
    PRICE_LEVEL_EXPENSIVE: 1,
    PRICE_LEVEL_VERY_EXPENSIVE: 2,
}

# Mapping for comparing price ratings (used for sorting)
PRICE_RATING_MAPPING = {
    PRICE_RATING_LOW: -1,
    PRICE_RATING_NORMAL: 0,
    PRICE_RATING_HIGH: 1,
}

LOGGER = logging.getLogger(__package__)

# Path to custom translations directory
CUSTOM_TRANSLATIONS_DIR = Path(__file__).parent / "custom_translations"

# Path to standard translations directory
TRANSLATIONS_DIR = Path(__file__).parent / "translations"

# Cache for translations to avoid repeated file reads
_TRANSLATIONS_CACHE: dict[str, dict] = {}

# Cache for standard translations (config flow, home_types, etc.)
_STANDARD_TRANSLATIONS_CACHE: dict[str, dict] = {}


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


async def async_load_standard_translations(hass: HomeAssistant, language: str) -> dict:
    """
    Load standard translations from the translations directory asynchronously.

    These are the config flow and home_types translations used in the UI.

    Args:
        hass: HomeAssistant instance
        language: The language code to load

    Returns:
        The loaded translations as a dictionary

    """
    cache_key = f"{DOMAIN}_standard_translations_{language}"

    # Check if we have an instance in hass.data
    if cache_key in hass.data:
        return hass.data[cache_key]

    # Check the module-level cache
    if language in _STANDARD_TRANSLATIONS_CACHE:
        return _STANDARD_TRANSLATIONS_CACHE[language]

    # Determine the file path
    file_path = TRANSLATIONS_DIR / f"{language}.json"
    if not file_path.exists():
        # Fall back to English if requested language not found
        file_path = TRANSLATIONS_DIR / "en.json"
        if not file_path.exists():
            LOGGER.debug("No standard translations found at %s", file_path)
            empty_cache = {}
            _STANDARD_TRANSLATIONS_CACHE[language] = empty_cache
            hass.data[cache_key] = empty_cache
            return empty_cache

    try:
        # Read the file asynchronously
        async with aiofiles.open(file_path, encoding="utf-8") as f:
            content = await f.read()
            translations = json.loads(content)
            # Store in both caches for future calls
            _STANDARD_TRANSLATIONS_CACHE[language] = translations
            hass.data[cache_key] = translations
            return translations

    except (OSError, json.JSONDecodeError) as err:
        LOGGER.warning("Error loading standard translations file: %s", err)
        empty_cache = {}
        _STANDARD_TRANSLATIONS_CACHE[language] = empty_cache
        hass.data[cache_key] = empty_cache
        return empty_cache

    except Exception:  # pylint: disable=broad-except
        LOGGER.exception("Unexpected error loading standard translations")
        empty_cache = {}
        _STANDARD_TRANSLATIONS_CACHE[language] = empty_cache
        hass.data[cache_key] = empty_cache
        return empty_cache


async def async_get_translation(
    hass: HomeAssistant,
    path: Sequence[str],
    language: str = "en",
) -> Any:
    """
    Get a translation value by path asynchronously.

    Checks standard translations first, then custom translations.

    Args:
        hass: HomeAssistant instance
        path: A sequence of keys defining the path to the translation value
        language: The language code (defaults to English)

    Returns:
        The translation value if found, None otherwise

    """
    # Try standard translations first (config flow, home_types, etc.)
    translations = await async_load_standard_translations(hass, language)

    # Navigate to the requested path
    current = translations
    for key in path:
        if not isinstance(current, dict) or key not in current:
            break
        current = current.get(key)
    else:
        # If we successfully navigated to the end, return the value
        return current

    # Fall back to custom translations if not found in standard translations
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
    Checks standard translations first, then custom translations.

    Args:
        path: A sequence of keys defining the path to the translation value
        language: The language code (defaults to English)

    Returns:
        The translation value if found in cache, None otherwise

    """

    def _navigate_dict(d: dict, keys: Sequence[str]) -> Any:
        """Navigate through nested dict following the keys path."""
        current = d
        for key in keys:
            if not isinstance(current, dict) or key not in current:
                return None
            current = current[key]
        return current

    def _get_from_cache(cache: dict[str, dict], lang: str) -> Any:
        """Get translation from cache with fallback to English."""
        if lang in cache:
            result = _navigate_dict(cache[lang], path)
            if result is not None:
                return result
        # Fallback to English if not found in requested language
        if lang != "en" and "en" in cache:
            result = _navigate_dict(cache["en"], path)
            if result is not None:
                return result
        return None

    # Try standard translations first
    result = _get_from_cache(_STANDARD_TRANSLATIONS_CACHE, language)
    if result is not None:
        return result

    # Fall back to custom translations
    result = _get_from_cache(_TRANSLATIONS_CACHE, language)
    if result is not None:
        return result

    # Log the missing key for debugging
    LOGGER.debug("Translation key '%s' not found for language %s", path, language)
    return None


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


async def async_get_home_type_translation(
    hass: HomeAssistant,
    home_type: str,
    language: str = "en",
) -> str | None:
    """
    Get a localized translation for a home type asynchronously.

    Args:
        hass: HomeAssistant instance
        home_type: The home type (e.g., APARTMENT, HOUSE, etc.)
        language: The language code (defaults to English)

    Returns:
        The localized home type if found, None otherwise

    """
    return await async_get_translation(hass, ["home_types", home_type], language)


def get_home_type_translation(
    home_type: str,
    language: str = "en",
) -> str | None:
    """
    Get a localized translation for a home type synchronously from the cache.

    This function only accesses the cached translations to avoid blocking I/O.

    Args:
        home_type: The home type (e.g., APARTMENT, HOUSE, etc.)
        language: The language code (defaults to English)

    Returns:
        The localized home type if found in cache, fallback to HOME_TYPES dict, or None

    """
    translated = get_translation(["home_types", home_type], language)
    if translated:
        return translated
    fallback = HOME_TYPES.get(home_type)
    LOGGER.debug(
        "No translation found for home type '%s' in language '%s', using fallback: %s. "
        "Available caches: standard=%s, custom=%s",
        home_type,
        language,
        fallback,
        list(_STANDARD_TRANSLATIONS_CACHE.keys()),
        list(_TRANSLATIONS_CACHE.keys()),
    )
    return fallback
