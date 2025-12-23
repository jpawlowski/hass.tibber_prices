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


# Constants for fetch age formatting
MINUTES_PER_HOUR = 60
MINUTES_PER_DAY = 1440  # 24 * 60


def build_lifecycle_attributes(
    coordinator: TibberPricesDataUpdateCoordinator,
    lifecycle_calculator: TibberPricesLifecycleCalculator,
) -> dict[str, Any]:
    """
    Build attributes for data_lifecycle_status sensor.

    Shows comprehensive pool status, data availability, and update timing.
    Separates sensor-related stats from cache stats for clarity.

    Returns:
        Dict with lifecycle attributes

    """
    attributes: dict[str, Any] = {}

    # === Pool Statistics (source of truth for cached data) ===
    pool_stats = lifecycle_calculator.get_pool_stats()
    if pool_stats:
        # --- Sensor Intervals (Protected Range: gestern bis übermorgen) ---
        attributes["sensor_intervals_count"] = pool_stats.get("sensor_intervals_count", 0)
        attributes["sensor_intervals_expected"] = pool_stats.get("sensor_intervals_expected", 384)
        attributes["sensor_intervals_has_gaps"] = pool_stats.get("sensor_intervals_has_gaps", True)

        # --- Cache Statistics (Entire Pool) ---
        attributes["cache_intervals_total"] = pool_stats.get("cache_intervals_total", 0)
        attributes["cache_intervals_limit"] = pool_stats.get("cache_intervals_limit", 960)
        attributes["cache_fill_percent"] = pool_stats.get("cache_fill_percent", 0)
        attributes["cache_intervals_extra"] = pool_stats.get("cache_intervals_extra", 0)

        # --- Timestamps ---
        last_sensor_fetch = pool_stats.get("last_sensor_fetch")
        if last_sensor_fetch:
            attributes["last_sensor_fetch"] = last_sensor_fetch

        oldest_interval = pool_stats.get("cache_oldest_interval")
        if oldest_interval:
            attributes["cache_oldest_interval"] = oldest_interval

        newest_interval = pool_stats.get("cache_newest_interval")
        if newest_interval:
            attributes["cache_newest_interval"] = newest_interval

        # --- API Fetch Groups (internal tracking) ---
        attributes["fetch_groups_count"] = pool_stats.get("fetch_groups_count", 0)

    # === Sensor Fetch Age (human-readable) ===
    fetch_age = lifecycle_calculator.get_sensor_fetch_age_minutes()
    if fetch_age is not None:
        # Format fetch age with units for better readability
        if fetch_age < MINUTES_PER_HOUR:
            attributes["sensor_fetch_age"] = f"{fetch_age} min"
        elif fetch_age < MINUTES_PER_DAY:  # Less than 24 hours
            hours = fetch_age // MINUTES_PER_HOUR
            minutes = fetch_age % MINUTES_PER_HOUR
            attributes["sensor_fetch_age"] = f"{hours}h {minutes}min" if minutes > 0 else f"{hours}h"
        else:  # 24+ hours
            days = fetch_age // MINUTES_PER_DAY
            hours = (fetch_age % MINUTES_PER_DAY) // MINUTES_PER_HOUR
            attributes["sensor_fetch_age"] = f"{days}d {hours}h" if hours > 0 else f"{days}d"

        # Keep raw value for automations
        attributes["sensor_fetch_age_minutes"] = fetch_age

    # === Tomorrow Data Status ===
    attributes["tomorrow_available"] = lifecycle_calculator.has_tomorrow_data()
    attributes["tomorrow_expected_after"] = "13:00"

    # === Next Actions ===
    next_poll = lifecycle_calculator.get_next_api_poll_time()
    if next_poll:  # None means data is complete, no more polls needed
        attributes["next_api_poll"] = next_poll.isoformat()

    next_midnight = lifecycle_calculator.get_next_midnight_turnover_time()
    attributes["next_midnight_turnover"] = next_midnight.isoformat()

    # === Update Statistics ===
    api_calls = lifecycle_calculator.get_api_calls_today()
    attributes["updates_today"] = api_calls

    # === Midnight Turnover Info ===
    if coordinator._midnight_handler.last_turnover_time:  # noqa: SLF001 - Internal state access for diagnostic display
        attributes["last_turnover"] = coordinator._midnight_handler.last_turnover_time.isoformat()  # noqa: SLF001

    # === Error Status ===
    if coordinator.last_exception:
        attributes["last_error"] = str(coordinator.last_exception)

    return attributes
