"""Validation functions for Tibber Prices config flow."""

from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.tibber_prices.api import (
    TibberPricesApiClient,
    TibberPricesApiClientAuthenticationError,
    TibberPricesApiClientCommunicationError,
    TibberPricesApiClientError,
)
from custom_components.tibber_prices.const import (
    DOMAIN,
    MAX_DISTANCE_PERCENTAGE,
    MAX_FLEX_PERCENTAGE,
    MAX_GAP_COUNT,
    MAX_MIN_PERIODS,
    MAX_PRICE_RATING_THRESHOLD_HIGH,
    MAX_PRICE_RATING_THRESHOLD_LOW,
    MAX_PRICE_TREND_FALLING,
    MAX_PRICE_TREND_RISING,
    MAX_RELAXATION_ATTEMPTS,
    MAX_VOLATILITY_THRESHOLD,
    MIN_GAP_COUNT,
    MIN_PERIOD_LENGTH,
    MIN_PRICE_RATING_THRESHOLD_HIGH,
    MIN_PRICE_RATING_THRESHOLD_LOW,
    MIN_PRICE_TREND_FALLING,
    MIN_PRICE_TREND_RISING,
    MIN_RELAXATION_ATTEMPTS,
    MIN_VOLATILITY_THRESHOLD,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.loader import async_get_integration

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


class TibberPricesInvalidAuthError(HomeAssistantError):
    """Error to indicate invalid authentication."""


class TibberPricesCannotConnectError(HomeAssistantError):
    """Error to indicate we cannot connect."""


async def validate_api_token(hass: HomeAssistant, token: str) -> dict:
    """
    Validate Tibber API token.

    Args:
        hass: Home Assistant instance
        token: Tibber API access token

    Returns:
        dict with viewer data on success

    Raises:
        TibberPricesInvalidAuthError: Invalid token
        TibberPricesCannotConnectError: API connection failed

    """
    try:
        integration = await async_get_integration(hass, DOMAIN)
        client = TibberPricesApiClient(
            access_token=token,
            session=async_create_clientsession(hass),
            version=str(integration.version) if integration.version else "unknown",
        )
        result = await client.async_get_viewer_details()
        return result["viewer"]
    except TibberPricesApiClientAuthenticationError as exception:
        raise TibberPricesInvalidAuthError from exception
    except TibberPricesApiClientCommunicationError as exception:
        raise TibberPricesCannotConnectError from exception
    except TibberPricesApiClientError as exception:
        raise TibberPricesCannotConnectError from exception


def validate_period_length(minutes: int) -> bool:
    """
    Validate period length is a positive multiple of 15 minutes.

    Args:
        minutes: Period length in minutes

    Returns:
        True if length is valid (multiple of 15, at least MIN_PERIOD_LENGTH)

    """
    return minutes % 15 == 0 and minutes >= MIN_PERIOD_LENGTH


def validate_flex_percentage(flex: float) -> bool:
    """
    Validate flexibility percentage is within bounds.

    Args:
        flex: Flexibility percentage (can be negative for peak price)

    Returns:
        True if percentage is valid (-MAX_FLEX to +MAX_FLEX)

    """
    return -MAX_FLEX_PERCENTAGE <= flex <= MAX_FLEX_PERCENTAGE


def validate_min_periods(count: int) -> bool:
    """
    Validate minimum periods count is reasonable.

    Args:
        count: Number of minimum periods per day

    Returns:
        True if count is valid (1 to MAX_MIN_PERIODS)

    """
    return 1 <= count <= MAX_MIN_PERIODS


def validate_distance_percentage(distance: float) -> bool:
    """
    Validate distance from average percentage is reasonable.

    Args:
        distance: Distance percentage (0-50% is typical range)

    Returns:
        True if distance is valid (0-MAX_DISTANCE_PERCENTAGE)

    """
    return 0.0 <= distance <= MAX_DISTANCE_PERCENTAGE


def validate_gap_count(count: int) -> bool:
    """
    Validate gap count is within bounds.

    Args:
        count: Gap count (0-8)

    Returns:
        True if count is valid (MIN_GAP_COUNT to MAX_GAP_COUNT)

    """
    return MIN_GAP_COUNT <= count <= MAX_GAP_COUNT


def validate_relaxation_attempts(attempts: int) -> bool:
    """
    Validate relaxation attempts count is within bounds.

    Args:
        attempts: Number of relaxation attempts (1-12)

    Returns:
        True if attempts is valid (MIN_RELAXATION_ATTEMPTS to MAX_RELAXATION_ATTEMPTS)

    """
    return MIN_RELAXATION_ATTEMPTS <= attempts <= MAX_RELAXATION_ATTEMPTS


def validate_price_rating_threshold_low(threshold: int) -> bool:
    """
    Validate low price rating threshold.

    Args:
        threshold: Low rating threshold percentage (-50 to -5)

    Returns:
        True if threshold is valid (MIN_PRICE_RATING_THRESHOLD_LOW to MAX_PRICE_RATING_THRESHOLD_LOW)

    """
    return MIN_PRICE_RATING_THRESHOLD_LOW <= threshold <= MAX_PRICE_RATING_THRESHOLD_LOW


def validate_price_rating_threshold_high(threshold: int) -> bool:
    """
    Validate high price rating threshold.

    Args:
        threshold: High rating threshold percentage (5 to 50)

    Returns:
        True if threshold is valid (MIN_PRICE_RATING_THRESHOLD_HIGH to MAX_PRICE_RATING_THRESHOLD_HIGH)

    """
    return MIN_PRICE_RATING_THRESHOLD_HIGH <= threshold <= MAX_PRICE_RATING_THRESHOLD_HIGH


def validate_price_rating_thresholds(threshold_low: int, threshold_high: int) -> bool:
    """
    Cross-validate both price rating thresholds together.

    Ensures that LOW threshold < HIGH threshold with proper gap to avoid
    overlap at 0%. LOW should be negative (below average), HIGH should be
    positive (above average).

    Args:
        threshold_low: Low rating threshold percentage (-50 to -5)
        threshold_high: High rating threshold percentage (5 to 50)

    Returns:
        True if both thresholds are valid individually AND threshold_low < threshold_high

    """
    # Validate individual ranges first
    if not validate_price_rating_threshold_low(threshold_low):
        return False
    if not validate_price_rating_threshold_high(threshold_high):
        return False

    # Ensure LOW is always less than HIGH (should always be true given the ranges,
    # but explicit check for safety)
    return threshold_low < threshold_high


def validate_volatility_threshold(threshold: float) -> bool:
    """
    Validate volatility threshold percentage.

    Args:
        threshold: Volatility threshold percentage (0.0 to 100.0)

    Returns:
        True if threshold is valid (MIN_VOLATILITY_THRESHOLD to MAX_VOLATILITY_THRESHOLD)

    """
    return MIN_VOLATILITY_THRESHOLD <= threshold <= MAX_VOLATILITY_THRESHOLD


def validate_price_trend_rising(threshold: int) -> bool:
    """
    Validate rising price trend threshold.

    Args:
        threshold: Rising trend threshold percentage (1 to 50)

    Returns:
        True if threshold is valid (MIN_PRICE_TREND_RISING to MAX_PRICE_TREND_RISING)

    """
    return MIN_PRICE_TREND_RISING <= threshold <= MAX_PRICE_TREND_RISING


def validate_price_trend_falling(threshold: int) -> bool:
    """
    Validate falling price trend threshold.

    Args:
        threshold: Falling trend threshold percentage (-50 to -1)

    Returns:
        True if threshold is valid (MIN_PRICE_TREND_FALLING to MAX_PRICE_TREND_FALLING)

    """
    return MIN_PRICE_TREND_FALLING <= threshold <= MAX_PRICE_TREND_FALLING
