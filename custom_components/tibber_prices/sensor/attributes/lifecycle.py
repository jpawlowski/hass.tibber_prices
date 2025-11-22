"""Attribute builders for lifecycle diagnostic sensor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator.core import (
        TibberPricesDataUpdateCoordinator,
    )
    from custom_components.tibber_prices.sensor.calculators.lifecycle import (
        TibberPricesLifecycleCalculator,
    )


# Constants for cache age formatting
MINUTES_PER_HOUR = 60
MINUTES_PER_DAY = 1440  # 24 * 60


def build_lifecycle_attributes(
    coordinator: TibberPricesDataUpdateCoordinator,
    lifecycle_calculator: TibberPricesLifecycleCalculator,
) -> dict[str, Any]:
    """
    Build attributes for data_lifecycle_status sensor.

    Shows comprehensive cache status, data availability, and update timing.

    Returns:
        Dict with lifecycle attributes

    """
    attributes: dict[str, Any] = {}

    # Cache Status (formatted for readability)
    cache_age = lifecycle_calculator.get_cache_age_minutes()
    if cache_age is not None:
        # Format cache age with units for better readability
        if cache_age < MINUTES_PER_HOUR:
            attributes["cache_age"] = f"{cache_age} min"
        elif cache_age < MINUTES_PER_DAY:  # Less than 24 hours
            hours = cache_age // MINUTES_PER_HOUR
            minutes = cache_age % MINUTES_PER_HOUR
            attributes["cache_age"] = f"{hours}h {minutes}min" if minutes > 0 else f"{hours}h"
        else:  # 24+ hours
            days = cache_age // MINUTES_PER_DAY
            hours = (cache_age % MINUTES_PER_DAY) // MINUTES_PER_HOUR
            attributes["cache_age"] = f"{days}d {hours}h" if hours > 0 else f"{days}d"

        # Keep raw value for automations
        attributes["cache_age_minutes"] = cache_age

    cache_validity = lifecycle_calculator.get_cache_validity_status()
    attributes["cache_validity"] = cache_validity

    if coordinator._last_price_update:  # noqa: SLF001 - Internal state access for diagnostic display
        attributes["last_api_fetch"] = coordinator._last_price_update.isoformat()  # noqa: SLF001
        attributes["last_cache_update"] = coordinator._last_price_update.isoformat()  # noqa: SLF001

    # Data Availability & Completeness
    data_completeness = lifecycle_calculator.get_data_completeness_status()
    attributes["data_completeness"] = data_completeness

    attributes["yesterday_available"] = lifecycle_calculator.is_data_available("yesterday")
    attributes["today_available"] = lifecycle_calculator.is_data_available("today")
    attributes["tomorrow_available"] = lifecycle_calculator.is_data_available("tomorrow")
    attributes["tomorrow_expected_after"] = "13:00"

    # Next Actions (only show if meaningful)
    next_poll = lifecycle_calculator.get_next_api_poll_time()
    if next_poll:  # None means data is complete, no more polls needed
        attributes["next_api_poll"] = next_poll.isoformat()

    next_midnight = lifecycle_calculator.get_next_midnight_turnover_time()
    attributes["next_midnight_turnover"] = next_midnight.isoformat()

    # Update Statistics
    api_calls = lifecycle_calculator.get_api_calls_today()
    attributes["updates_today"] = api_calls

    # Last Turnover Time (from midnight handler)
    if coordinator._midnight_handler.last_turnover_time:  # noqa: SLF001 - Internal state access for diagnostic display
        attributes["last_turnover"] = coordinator._midnight_handler.last_turnover_time.isoformat()  # noqa: SLF001

    # Last Error (if any)
    if coordinator.last_exception:
        attributes["last_error"] = str(coordinator.last_exception)

    return attributes
