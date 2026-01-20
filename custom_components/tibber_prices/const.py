"""Constants for the Tibber Price Analytics integration."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiofiles

from homeassistant.const import (
    CURRENCY_DOLLAR,
    CURRENCY_EURO,
    UnitOfPower,
    UnitOfTime,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

DOMAIN = "tibber_prices"
LOGGER = logging.getLogger(__package__)

# Data storage keys
DATA_CHART_CONFIG = "chart_config"  # Key for chart export config in hass.data
DATA_CHART_METADATA_CONFIG = "chart_metadata_config"  # Key for chart metadata config in hass.data

# Configuration keys
CONF_EXTENDED_DESCRIPTIONS = "extended_descriptions"
CONF_VIRTUAL_TIME_OFFSET_DAYS = (
    "virtual_time_offset_days"  # Time-travel: days offset (negative only, e.g., -7 = 7 days ago)
)
CONF_VIRTUAL_TIME_OFFSET_HOURS = "virtual_time_offset_hours"  # Time-travel: hours offset (-23 to +23)
CONF_VIRTUAL_TIME_OFFSET_MINUTES = "virtual_time_offset_minutes"  # Time-travel: minutes offset (-59 to +59)
CONF_BEST_PRICE_FLEX = "best_price_flex"
CONF_PEAK_PRICE_FLEX = "peak_price_flex"
CONF_BEST_PRICE_MIN_DISTANCE_FROM_AVG = "best_price_min_distance_from_avg"
CONF_PEAK_PRICE_MIN_DISTANCE_FROM_AVG = "peak_price_min_distance_from_avg"
CONF_BEST_PRICE_MIN_PERIOD_LENGTH = "best_price_min_period_length"
CONF_PEAK_PRICE_MIN_PERIOD_LENGTH = "peak_price_min_period_length"
CONF_PRICE_RATING_THRESHOLD_LOW = "price_rating_threshold_low"
CONF_PRICE_RATING_THRESHOLD_HIGH = "price_rating_threshold_high"
CONF_PRICE_RATING_HYSTERESIS = "price_rating_hysteresis"
CONF_PRICE_RATING_GAP_TOLERANCE = "price_rating_gap_tolerance"
CONF_PRICE_LEVEL_GAP_TOLERANCE = "price_level_gap_tolerance"
CONF_AVERAGE_SENSOR_DISPLAY = "average_sensor_display"  # "median" or "mean"
CONF_PRICE_TREND_THRESHOLD_RISING = "price_trend_threshold_rising"
CONF_PRICE_TREND_THRESHOLD_FALLING = "price_trend_threshold_falling"
CONF_PRICE_TREND_THRESHOLD_STRONGLY_RISING = "price_trend_threshold_strongly_rising"
CONF_PRICE_TREND_THRESHOLD_STRONGLY_FALLING = "price_trend_threshold_strongly_falling"
CONF_VOLATILITY_THRESHOLD_MODERATE = "volatility_threshold_moderate"
CONF_VOLATILITY_THRESHOLD_HIGH = "volatility_threshold_high"
CONF_VOLATILITY_THRESHOLD_VERY_HIGH = "volatility_threshold_very_high"
CONF_BEST_PRICE_MAX_LEVEL = "best_price_max_level"
CONF_PEAK_PRICE_MIN_LEVEL = "peak_price_min_level"
CONF_BEST_PRICE_MAX_LEVEL_GAP_COUNT = "best_price_max_level_gap_count"
CONF_PEAK_PRICE_MAX_LEVEL_GAP_COUNT = "peak_price_max_level_gap_count"
CONF_ENABLE_MIN_PERIODS_BEST = "enable_min_periods_best"
CONF_MIN_PERIODS_BEST = "min_periods_best"
CONF_RELAXATION_ATTEMPTS_BEST = "relaxation_attempts_best"
CONF_ENABLE_MIN_PERIODS_PEAK = "enable_min_periods_peak"
CONF_MIN_PERIODS_PEAK = "min_periods_peak"
CONF_RELAXATION_ATTEMPTS_PEAK = "relaxation_attempts_peak"
CONF_CHART_DATA_CONFIG = "chart_data_config"  # YAML config for chart data export

ATTRIBUTION = "Data provided by Tibber"

# Integration name should match manifest.json
DEFAULT_NAME = "Tibber Price Information & Ratings"
DEFAULT_EXTENDED_DESCRIPTIONS = False
DEFAULT_VIRTUAL_TIME_OFFSET_DAYS = 0  # No time offset (live mode)
DEFAULT_VIRTUAL_TIME_OFFSET_HOURS = 0
DEFAULT_VIRTUAL_TIME_OFFSET_MINUTES = 0
DEFAULT_BEST_PRICE_FLEX = 15  # 15% base flexibility - optimal for relaxation mode (default enabled)
# Peak price flexibility is set to -20% (20% base flexibility - optimal for relaxation mode).
# This is intentionally more flexible than best price (15%) because peak price periods can be more variable,
# and users may benefit from earlier warnings about expensive periods, even if they are less sharply defined.
# The negative sign indicates that the threshold is set below the MAX price
# (e.g., -20% means MAX * 0.8), not above the average price.
# A higher percentage allows for more conservative detection, reducing false negatives for peak price warnings.
DEFAULT_PEAK_PRICE_FLEX = -20  # 20% base flexibility (user-facing, percent)
DEFAULT_BEST_PRICE_MIN_DISTANCE_FROM_AVG = (
    -5
)  # -5% minimum distance from daily average (below average, ensures significance)
DEFAULT_PEAK_PRICE_MIN_DISTANCE_FROM_AVG = (
    5  # 5% minimum distance from daily average (above average, ensures significance)
)
DEFAULT_BEST_PRICE_MIN_PERIOD_LENGTH = 60  # 60 minutes minimum period length for best price (user-facing, minutes)
# Note: Peak price warnings are allowed for shorter periods (30 min) than best price periods (60 min).
# This asymmetry is intentional: shorter peak periods are acceptable for alerting users to brief expensive spikes,
# while best price periods require longer duration to ensure meaningful savings and avoid recommending short,
# impractical windows.
DEFAULT_PEAK_PRICE_MIN_PERIOD_LENGTH = 30  # 30 minutes minimum period length for peak price (user-facing, minutes)
DEFAULT_PRICE_RATING_THRESHOLD_LOW = -10  # Default rating threshold low percentage
DEFAULT_PRICE_RATING_THRESHOLD_HIGH = 10  # Default rating threshold high percentage
DEFAULT_PRICE_RATING_HYSTERESIS = 2.0  # Hysteresis percentage to prevent flickering at threshold boundaries
DEFAULT_PRICE_RATING_GAP_TOLERANCE = 1  # Max consecutive intervals to smooth out (0 = disabled)
DEFAULT_PRICE_LEVEL_GAP_TOLERANCE = 1  # Max consecutive intervals to smooth out for price level (0 = disabled)
DEFAULT_AVERAGE_SENSOR_DISPLAY = "median"  # Default: show median in state, mean in attributes
DEFAULT_PRICE_TREND_THRESHOLD_RISING = 3  # Default trend threshold for rising prices (%)
DEFAULT_PRICE_TREND_THRESHOLD_FALLING = -3  # Default trend threshold for falling prices (%, negative value)
# Strong trend thresholds default to 2x the base threshold.
# These are independently configurable to allow fine-tuning of "strongly" detection.
DEFAULT_PRICE_TREND_THRESHOLD_STRONGLY_RISING = 6  # Default strong rising threshold (%)
DEFAULT_PRICE_TREND_THRESHOLD_STRONGLY_FALLING = -6  # Default strong falling threshold (%, negative value)
# Default volatility thresholds (relative values using coefficient of variation)
# Coefficient of variation = (standard_deviation / mean) * 100%
# These thresholds are unitless and work across different price levels
DEFAULT_VOLATILITY_THRESHOLD_MODERATE = 15.0  # 15% - moderate price fluctuation
DEFAULT_VOLATILITY_THRESHOLD_HIGH = 30.0  # 30% - high price fluctuation
DEFAULT_VOLATILITY_THRESHOLD_VERY_HIGH = 50.0  # 50% - very high price fluctuation
DEFAULT_BEST_PRICE_MAX_LEVEL = "cheap"  # Default: prefer genuinely cheap periods, relax to "any" if needed
DEFAULT_PEAK_PRICE_MIN_LEVEL = "expensive"  # Default: prefer genuinely expensive periods, relax to "any" if needed
DEFAULT_BEST_PRICE_MAX_LEVEL_GAP_COUNT = 1  # Default: allow 1 level gap (e.g., CHEAP→NORMAL→CHEAP stays together)
DEFAULT_PEAK_PRICE_MAX_LEVEL_GAP_COUNT = 1  # Default: allow 1 level gap for peak price periods
MIN_INTERVALS_FOR_GAP_TOLERANCE = 6  # Minimum period length (in 15-min intervals = 1.5h) required for gap tolerance
DEFAULT_ENABLE_MIN_PERIODS_BEST = True  # Default: minimum periods feature enabled for best price
DEFAULT_MIN_PERIODS_BEST = 2  # Default: require at least 2 best price periods (when enabled)
DEFAULT_RELAXATION_ATTEMPTS_BEST = 11  # Default: 11 steps allows escalation from 15% to 48% (3% increment per step)
DEFAULT_ENABLE_MIN_PERIODS_PEAK = True  # Default: minimum periods feature enabled for peak price
DEFAULT_MIN_PERIODS_PEAK = 2  # Default: require at least 2 peak price periods (when enabled)
DEFAULT_RELAXATION_ATTEMPTS_PEAK = 11  # Default: 11 steps allows escalation from 20% to 50% (3% increment per step)

# Validation limits (used in GUI schemas and server-side validation)
# These ensure consistency between frontend and backend validation
MAX_FLEX_PERCENTAGE = 50  # Maximum flexibility percentage (aligned with GUI slider and MAX_SAFE_FLEX)
MAX_DISTANCE_PERCENTAGE = 50  # Maximum distance from average percentage (GUI slider limit)
MAX_GAP_COUNT = 8  # Maximum gap count for level filtering (GUI slider limit)
MAX_MIN_PERIODS = 10  # Maximum number of minimum periods per day (GUI slider limit)
MAX_RELAXATION_ATTEMPTS = 12  # Maximum relaxation attempts (GUI slider limit)
MIN_PERIOD_LENGTH = 15  # Minimum period length in minutes (1 quarter hour)
MAX_MIN_PERIOD_LENGTH = 180  # Maximum for minimum period length setting (3 hours - realistic for required minimum)

# Price rating threshold limits
# LOW threshold: negative values (prices below average) - practical range -50% to -5%
# HIGH threshold: positive values (prices above average) - practical range +5% to +50%
# Ensure minimum 5% gap between thresholds to avoid overlap at 0%
MIN_PRICE_RATING_THRESHOLD_LOW = -50  # Minimum value for low rating threshold
MAX_PRICE_RATING_THRESHOLD_LOW = -5  # Maximum value for low rating threshold (must be < HIGH)
MIN_PRICE_RATING_THRESHOLD_HIGH = 5  # Minimum value for high rating threshold (must be > LOW)
MAX_PRICE_RATING_THRESHOLD_HIGH = 50  # Maximum value for high rating threshold
MIN_PRICE_RATING_HYSTERESIS = 0.0  # Minimum hysteresis (0 = disabled)
MAX_PRICE_RATING_HYSTERESIS = 5.0  # Maximum hysteresis (5% band)
MIN_PRICE_RATING_GAP_TOLERANCE = 0  # Minimum gap tolerance (0 = disabled)
MAX_PRICE_RATING_GAP_TOLERANCE = 4  # Maximum gap tolerance (4 intervals = 1 hour)
MIN_PRICE_LEVEL_GAP_TOLERANCE = 0  # Minimum gap tolerance for price level (0 = disabled)
MAX_PRICE_LEVEL_GAP_TOLERANCE = 4  # Maximum gap tolerance for price level (4 intervals = 1 hour)

# Volatility threshold limits
# MODERATE threshold: practical range 5% to 25% (entry point for noticeable fluctuation)
# HIGH threshold: practical range 20% to 40% (significant price swings)
# VERY_HIGH threshold: practical range 35% to 80% (extreme volatility)
# Ensure cascading: MODERATE < HIGH < VERY_HIGH with ~5% minimum gaps
MIN_VOLATILITY_THRESHOLD_MODERATE = 5.0  # Minimum for moderate volatility threshold
MAX_VOLATILITY_THRESHOLD_MODERATE = 25.0  # Maximum for moderate volatility threshold (must be < HIGH)
MIN_VOLATILITY_THRESHOLD_HIGH = 20.0  # Minimum for high volatility threshold (must be > MODERATE)
MAX_VOLATILITY_THRESHOLD_HIGH = 40.0  # Maximum for high volatility threshold (must be < VERY_HIGH)
MIN_VOLATILITY_THRESHOLD_VERY_HIGH = 35.0  # Minimum for very high volatility threshold (must be > HIGH)
MAX_VOLATILITY_THRESHOLD_VERY_HIGH = 80.0  # Maximum for very high volatility threshold

# Price trend threshold limits
MIN_PRICE_TREND_RISING = 1  # Minimum rising trend threshold
MAX_PRICE_TREND_RISING = 50  # Maximum rising trend threshold
MIN_PRICE_TREND_FALLING = -50  # Minimum falling trend threshold (negative)
MAX_PRICE_TREND_FALLING = -1  # Maximum falling trend threshold (negative)
# Strong trend thresholds have higher ranges to allow detection of significant moves
MIN_PRICE_TREND_STRONGLY_RISING = 2  # Minimum strongly rising threshold (must be > rising)
MAX_PRICE_TREND_STRONGLY_RISING = 100  # Maximum strongly rising threshold
MIN_PRICE_TREND_STRONGLY_FALLING = -100  # Minimum strongly falling threshold (negative)
MAX_PRICE_TREND_STRONGLY_FALLING = -2  # Maximum strongly falling threshold (must be < falling)

# Gap count and relaxation limits
MIN_GAP_COUNT = 0  # Minimum gap count
MIN_RELAXATION_ATTEMPTS = 1  # Minimum relaxation attempts

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
    "EUR": (CURRENCY_EURO, "ct", "Cents"),
    "NOK": ("kr", "øre", "Øre"),
    "SEK": ("kr", "öre", "Öre"),
    "DKK": ("kr", "øre", "Øre"),
    "USD": (CURRENCY_DOLLAR, "¢", "Cents"),
    "GBP": ("£", "p", "Pence"),
}

# Base currency names: ISO code -> full currency name (in local language)
CURRENCY_NAMES = {
    "EUR": "Euro",
    "NOK": "Norske kroner",
    "SEK": "Svenska kronor",
    "DKK": "Danske kroner",
    "USD": "US Dollar",
    "GBP": "British Pound",
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


def format_price_unit_base(currency_code: str | None) -> str:
    """
    Format the price unit string with base currency unit (e.g., '€/kWh').

    Args:
        currency_code: ISO 4217 currency code (e.g., 'EUR', 'NOK', 'SEK')

    Returns:
        Formatted unit string like '€/kWh' or 'kr/kWh'

    """
    base_symbol, _, _ = get_currency_info(currency_code)
    return f"{base_symbol}/{UnitOfPower.KILO_WATT}{UnitOfTime.HOURS}"


def format_price_unit_subunit(currency_code: str | None) -> str:
    """
    Format the price unit string with subunit currency unit (e.g., 'ct/kWh').

    Args:
        currency_code: ISO 4217 currency code (e.g., 'EUR', 'NOK', 'SEK')

    Returns:
        Formatted unit string like 'ct/kWh' or 'øre/kWh'

    """
    _, subunit_symbol, _ = get_currency_info(currency_code)
    return f"{subunit_symbol}/{UnitOfPower.KILO_WATT}{UnitOfTime.HOURS}"


def get_currency_name(currency_code: str | None) -> str:
    """
    Get the full name of the base currency.

    Args:
        currency_code: ISO 4217 currency code (e.g., 'EUR', 'NOK', 'SEK')

    Returns:
        Full currency name like 'Euro' or 'Norwegian Krone'
        Defaults to 'Euro' if currency is not recognized

    """
    if not currency_code:
        currency_code = "EUR"

    return CURRENCY_NAMES.get(currency_code.upper(), CURRENCY_NAMES["EUR"])


# ============================================================================
# Currency Display Mode Configuration
# ============================================================================

# Configuration key for currency display mode
CONF_CURRENCY_DISPLAY_MODE = "currency_display_mode"

# Display mode values
DISPLAY_MODE_BASE = "base"  # Display in base currency units (€, kr)
DISPLAY_MODE_SUBUNIT = "subunit"  # Display in subunit currency units (ct, øre)

# Intelligent per-currency defaults based on market analysis
# EUR: Subunit (cents) - established convention in Germany/Netherlands
# NOK/SEK/DKK: Base (kroner) - Scandinavian preference for whole units
# USD/GBP: Base - international standard
DEFAULT_CURRENCY_DISPLAY = {
    "EUR": DISPLAY_MODE_SUBUNIT,
    "NOK": DISPLAY_MODE_BASE,
    "SEK": DISPLAY_MODE_BASE,
    "DKK": DISPLAY_MODE_BASE,
    "USD": DISPLAY_MODE_BASE,
    "GBP": DISPLAY_MODE_BASE,
}


def get_default_currency_display(currency_code: str | None) -> str:
    """
    Get intelligent default display mode for a currency.

    Args:
        currency_code: ISO 4217 currency code (e.g., 'EUR', 'NOK')

    Returns:
        Default display mode ('base' or 'subunit')

    """
    if not currency_code:
        return DISPLAY_MODE_SUBUNIT  # Fallback default

    return DEFAULT_CURRENCY_DISPLAY.get(currency_code.upper(), DISPLAY_MODE_SUBUNIT)


def get_default_options(currency_code: str | None) -> dict[str, Any]:
    """
    Get complete default options for a new config entry.

    This ensures new config entries have explicitly set defaults based on their currency,
    distinguishing them from legacy config entries that need migration.

    Options structure has been flattened for single-section steps:
    - Flat values: extended_descriptions, average_sensor_display, currency_display_mode,
      price_rating_thresholds, volatility_thresholds, price_trend_thresholds, time offsets
    - Nested sections (multi-section steps only): period_settings, flexibility_settings,
      relaxation_and_target_periods

    Args:
        currency_code: ISO 4217 currency code (e.g., 'EUR', 'NOK')

    Returns:
        Dictionary with all default option values in nested section structure

    """
    return {
        # Flat configuration values
        CONF_EXTENDED_DESCRIPTIONS: DEFAULT_EXTENDED_DESCRIPTIONS,
        CONF_AVERAGE_SENSOR_DISPLAY: DEFAULT_AVERAGE_SENSOR_DISPLAY,
        CONF_CURRENCY_DISPLAY_MODE: get_default_currency_display(currency_code),
        CONF_VIRTUAL_TIME_OFFSET_DAYS: DEFAULT_VIRTUAL_TIME_OFFSET_DAYS,
        CONF_VIRTUAL_TIME_OFFSET_HOURS: DEFAULT_VIRTUAL_TIME_OFFSET_HOURS,
        CONF_VIRTUAL_TIME_OFFSET_MINUTES: DEFAULT_VIRTUAL_TIME_OFFSET_MINUTES,
        # Price rating settings (flat - single-section step)
        CONF_PRICE_RATING_THRESHOLD_LOW: DEFAULT_PRICE_RATING_THRESHOLD_LOW,
        CONF_PRICE_RATING_THRESHOLD_HIGH: DEFAULT_PRICE_RATING_THRESHOLD_HIGH,
        CONF_PRICE_RATING_HYSTERESIS: DEFAULT_PRICE_RATING_HYSTERESIS,
        CONF_PRICE_RATING_GAP_TOLERANCE: DEFAULT_PRICE_RATING_GAP_TOLERANCE,
        CONF_PRICE_LEVEL_GAP_TOLERANCE: DEFAULT_PRICE_LEVEL_GAP_TOLERANCE,
        # Volatility thresholds (flat - single-section step)
        CONF_VOLATILITY_THRESHOLD_MODERATE: DEFAULT_VOLATILITY_THRESHOLD_MODERATE,
        CONF_VOLATILITY_THRESHOLD_HIGH: DEFAULT_VOLATILITY_THRESHOLD_HIGH,
        CONF_VOLATILITY_THRESHOLD_VERY_HIGH: DEFAULT_VOLATILITY_THRESHOLD_VERY_HIGH,
        # Price trend thresholds (flat - single-section step)
        CONF_PRICE_TREND_THRESHOLD_RISING: DEFAULT_PRICE_TREND_THRESHOLD_RISING,
        CONF_PRICE_TREND_THRESHOLD_FALLING: DEFAULT_PRICE_TREND_THRESHOLD_FALLING,
        # Nested section: Period settings (shared by best/peak price)
        "period_settings": {
            CONF_BEST_PRICE_MIN_PERIOD_LENGTH: DEFAULT_BEST_PRICE_MIN_PERIOD_LENGTH,
            CONF_PEAK_PRICE_MIN_PERIOD_LENGTH: DEFAULT_PEAK_PRICE_MIN_PERIOD_LENGTH,
            CONF_BEST_PRICE_MAX_LEVEL_GAP_COUNT: DEFAULT_BEST_PRICE_MAX_LEVEL_GAP_COUNT,
            CONF_PEAK_PRICE_MAX_LEVEL_GAP_COUNT: DEFAULT_PEAK_PRICE_MAX_LEVEL_GAP_COUNT,
            CONF_BEST_PRICE_MAX_LEVEL: DEFAULT_BEST_PRICE_MAX_LEVEL,
            CONF_PEAK_PRICE_MIN_LEVEL: DEFAULT_PEAK_PRICE_MIN_LEVEL,
        },
        # Nested section: Flexibility settings (shared by best/peak price)
        "flexibility_settings": {
            CONF_BEST_PRICE_FLEX: DEFAULT_BEST_PRICE_FLEX,
            CONF_PEAK_PRICE_FLEX: DEFAULT_PEAK_PRICE_FLEX,
            CONF_BEST_PRICE_MIN_DISTANCE_FROM_AVG: DEFAULT_BEST_PRICE_MIN_DISTANCE_FROM_AVG,
            CONF_PEAK_PRICE_MIN_DISTANCE_FROM_AVG: DEFAULT_PEAK_PRICE_MIN_DISTANCE_FROM_AVG,
        },
        # Nested section: Relaxation and target periods (shared by best/peak price)
        "relaxation_and_target_periods": {
            CONF_ENABLE_MIN_PERIODS_BEST: DEFAULT_ENABLE_MIN_PERIODS_BEST,
            CONF_MIN_PERIODS_BEST: DEFAULT_MIN_PERIODS_BEST,
            CONF_RELAXATION_ATTEMPTS_BEST: DEFAULT_RELAXATION_ATTEMPTS_BEST,
            CONF_ENABLE_MIN_PERIODS_PEAK: DEFAULT_ENABLE_MIN_PERIODS_PEAK,
            CONF_MIN_PERIODS_PEAK: DEFAULT_MIN_PERIODS_PEAK,
            CONF_RELAXATION_ATTEMPTS_PEAK: DEFAULT_RELAXATION_ATTEMPTS_PEAK,
        },
    }


def get_display_unit_factor(config_entry: ConfigEntry) -> int:
    """
    Get multiplication factor for converting base to display currency.

    Internal storage is ALWAYS in base currency (4 decimals precision).
    This function returns the conversion factor based on user configuration.

    Args:
        config_entry: ConfigEntry with currency_display_mode option

    Returns:
        100 for subunit currency display, 1 for base currency display

    Example:
        price_base = 0.2534  # Internal: 0.2534 €/kWh
        factor = get_display_unit_factor(config_entry)
        display_value = round(price_base * factor, 2)
        # → 25.34 ct/kWh (subunit) or 0.25 €/kWh (base)

    """
    display_mode = config_entry.options.get(CONF_CURRENCY_DISPLAY_MODE, DISPLAY_MODE_SUBUNIT)
    return 100 if display_mode == DISPLAY_MODE_SUBUNIT else 1


def get_display_unit_string(config_entry: ConfigEntry, currency_code: str | None) -> str:
    """
    Get unit string for display based on configuration.

    Args:
        config_entry: ConfigEntry with currency_display_mode option
        currency_code: ISO 4217 currency code

    Returns:
        Formatted unit string (e.g., 'ct/kWh' or '€/kWh')

    """
    display_mode = config_entry.options.get(CONF_CURRENCY_DISPLAY_MODE, DISPLAY_MODE_SUBUNIT)

    if display_mode == DISPLAY_MODE_SUBUNIT:
        return format_price_unit_subunit(currency_code)
    return format_price_unit_base(currency_code)


# ============================================================================
# Price Level, Rating, and Volatility Constants
# ============================================================================
# IMPORTANT: These string constants are the single source of truth for
# valid enum values. The Literal types in sensor/types.py and binary_sensor/types.py
# should be kept in sync with these values manually.

# Price level constants (from Tibber API)
PRICE_LEVEL_VERY_CHEAP = "VERY_CHEAP"
PRICE_LEVEL_CHEAP = "CHEAP"
PRICE_LEVEL_NORMAL = "NORMAL"
PRICE_LEVEL_EXPENSIVE = "EXPENSIVE"
PRICE_LEVEL_VERY_EXPENSIVE = "VERY_EXPENSIVE"

# Price rating constants (calculated values)
PRICE_RATING_LOW = "LOW"
PRICE_RATING_NORMAL = "NORMAL"
PRICE_RATING_HIGH = "HIGH"

# Price volatility level constants
VOLATILITY_LOW = "LOW"
VOLATILITY_MODERATE = "MODERATE"
VOLATILITY_HIGH = "HIGH"
VOLATILITY_VERY_HIGH = "VERY_HIGH"

# Price trend constants (calculated values with 5-level scale)
# Used by trend sensors: momentary, short-term, mid-term, long-term
PRICE_TREND_STRONGLY_FALLING = "strongly_falling"
PRICE_TREND_FALLING = "falling"
PRICE_TREND_STABLE = "stable"
PRICE_TREND_RISING = "rising"
PRICE_TREND_STRONGLY_RISING = "strongly_rising"

# Sensor options (lowercase versions for ENUM device class)
# NOTE: These constants define the valid enum options, but they are not used directly
# in sensor/definitions.py due to import timing issues. Instead, the options are defined inline
# in the SensorEntityDescription objects. Keep these in sync with sensor/definitions.py!
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

VOLATILITY_OPTIONS = [
    VOLATILITY_LOW.lower(),
    VOLATILITY_MODERATE.lower(),
    VOLATILITY_HIGH.lower(),
    VOLATILITY_VERY_HIGH.lower(),
]

# Trend options for enum sensors (lowercase versions for ENUM device class)
PRICE_TREND_OPTIONS = [
    PRICE_TREND_STRONGLY_FALLING,
    PRICE_TREND_FALLING,
    PRICE_TREND_STABLE,
    PRICE_TREND_RISING,
    PRICE_TREND_STRONGLY_RISING,
]

# Valid options for best price maximum level filter
# Sorted from cheap to expensive: user selects "up to how expensive"
BEST_PRICE_MAX_LEVEL_OPTIONS = [
    "any",  # No filter, allow all price levels
    PRICE_LEVEL_VERY_CHEAP.lower(),  # Only show if level ≤ VERY_CHEAP
    PRICE_LEVEL_CHEAP.lower(),  # Only show if level ≤ CHEAP
    PRICE_LEVEL_NORMAL.lower(),  # Only show if level ≤ NORMAL
    PRICE_LEVEL_EXPENSIVE.lower(),  # Only show if level ≤ EXPENSIVE
]

# Valid options for peak price minimum level filter
# Sorted from expensive to cheap: user selects "starting from how expensive"
PEAK_PRICE_MIN_LEVEL_OPTIONS = [
    "any",  # No filter, allow all price levels
    PRICE_LEVEL_EXPENSIVE.lower(),  # Only show if level ≥ EXPENSIVE
    PRICE_LEVEL_NORMAL.lower(),  # Only show if level ≥ NORMAL
    PRICE_LEVEL_CHEAP.lower(),  # Only show if level ≥ CHEAP
    PRICE_LEVEL_VERY_CHEAP.lower(),  # Only show if level ≥ VERY_CHEAP
]

# Relaxation level constants (for period filter relaxation)
# These describe which filter relaxation was applied to find a period
RELAXATION_NONE = "none"  # No relaxation, normal filters
RELAXATION_LEVEL_ANY = "level_any"  # Level filter disabled
RELAXATION_ALL_FILTERS_OFF = "all_filters_off"  # All filters disabled (deprecated, same as level_any)

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

# Mapping for comparing price trends (used for sorting and automation comparisons)
# Values range from -2 (strongly falling) to +2 (strongly rising), with 0 = stable
PRICE_TREND_MAPPING = {
    PRICE_TREND_STRONGLY_FALLING: -2,
    PRICE_TREND_FALLING: -1,
    PRICE_TREND_STABLE: 0,
    PRICE_TREND_RISING: 1,
    PRICE_TREND_STRONGLY_RISING: 2,
}

# Icon mapping for price levels (dynamic icons based on level)
PRICE_LEVEL_ICON_MAPPING = {
    PRICE_LEVEL_VERY_CHEAP: "mdi:gauge-empty",
    PRICE_LEVEL_CHEAP: "mdi:gauge-low",
    PRICE_LEVEL_NORMAL: "mdi:gauge",
    PRICE_LEVEL_EXPENSIVE: "mdi:gauge-full",
    PRICE_LEVEL_VERY_EXPENSIVE: "mdi:alert",
}

# Color mapping for price levels (CSS variables for theme compatibility)
PRICE_LEVEL_COLOR_MAPPING = {
    PRICE_LEVEL_VERY_CHEAP: "var(--success-color)",
    PRICE_LEVEL_CHEAP: "var(--success-color)",
    PRICE_LEVEL_NORMAL: "var(--state-icon-color)",
    PRICE_LEVEL_EXPENSIVE: "var(--warning-color)",
    PRICE_LEVEL_VERY_EXPENSIVE: "var(--error-color)",
}

# Icon mapping for current price sensors (dynamic icons based on price level)
# Used by current_interval_price and current_hour_average_price sensors
# Icon shows price level (cheap/normal/expensive), icon_color reinforces with color
PRICE_LEVEL_CASH_ICON_MAPPING = {
    PRICE_LEVEL_VERY_CHEAP: "mdi:cash-multiple",  # Many coins (save a lot!)
    PRICE_LEVEL_CHEAP: "mdi:cash-plus",  # Cash with plus (good price)
    PRICE_LEVEL_NORMAL: "mdi:cash",  # Standard cash icon
    PRICE_LEVEL_EXPENSIVE: "mdi:cash-minus",  # Cash with minus (expensive)
    PRICE_LEVEL_VERY_EXPENSIVE: "mdi:cash-remove",  # Cash crossed out (very expensive)
}

# Icon mapping for price ratings (dynamic icons based on rating)
PRICE_RATING_ICON_MAPPING = {
    PRICE_RATING_LOW: "mdi:thumb-up",
    PRICE_RATING_NORMAL: "mdi:thumbs-up-down",
    PRICE_RATING_HIGH: "mdi:thumb-down",
}

# Color mapping for price ratings (CSS variables for theme compatibility)
PRICE_RATING_COLOR_MAPPING = {
    PRICE_RATING_LOW: "var(--success-color)",
    PRICE_RATING_NORMAL: "var(--state-icon-color)",
    PRICE_RATING_HIGH: "var(--error-color)",
}

# Icon mapping for volatility levels (dynamic icons based on volatility)
VOLATILITY_ICON_MAPPING = {
    VOLATILITY_LOW: "mdi:chart-line-variant",
    VOLATILITY_MODERATE: "mdi:chart-timeline-variant",
    VOLATILITY_HIGH: "mdi:chart-bar",
    VOLATILITY_VERY_HIGH: "mdi:chart-scatter-plot",
}

# Color mapping for volatility levels (CSS variables for theme compatibility)
VOLATILITY_COLOR_MAPPING = {
    VOLATILITY_LOW: "var(--success-color)",
    VOLATILITY_MODERATE: "var(--info-color)",
    VOLATILITY_HIGH: "var(--warning-color)",
    VOLATILITY_VERY_HIGH: "var(--error-color)",
}

# Mapping for comparing volatility levels (used for sorting)
VOLATILITY_MAPPING = {
    VOLATILITY_LOW: 0,
    VOLATILITY_MODERATE: 1,
    VOLATILITY_HIGH: 2,
    VOLATILITY_VERY_HIGH: 3,
}

# Icon mapping for binary sensors (dynamic icons based on state)
# Note: OFF state icons can vary based on whether future periods exist
BINARY_SENSOR_ICON_MAPPING = {
    "best_price_period": {
        "on": "mdi:piggy-bank",
        "off": "mdi:timer-sand",  # Has future periods
        "off_no_future": "mdi:sleep",  # No future periods in next 6h
    },
    "peak_price_period": {
        "on": "mdi:alert-circle",
        "off": "mdi:shield-check",  # Has future periods
        "off_no_future": "mdi:sleep",  # No future periods in next 6h
    },
    "chart_data_export": {
        "on": "mdi:database-export",  # Data available
        "off": "mdi:database-alert",  # Service call failed or no config
    },
}

# Color mapping for binary sensors (CSS variables for theme compatibility)
BINARY_SENSOR_COLOR_MAPPING = {
    "best_price_period": {
        "on": "var(--success-color)",
        "off": "var(--state-icon-color)",
    },
    "peak_price_period": {
        "on": "var(--error-color)",
        "off": "var(--state-icon-color)",
    },
}

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
    return await async_get_translation(
        hass, ["sensor", "current_interval_price_level", "price_levels", level], language
    )


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
    return get_translation(["sensor", "current_interval_price_level", "price_levels", level], language)


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
