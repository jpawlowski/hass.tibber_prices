"""
Attribute builders for lifecycle diagnostic sensor.

This sensor uses event-based updates with state-change filtering to minimize
recorder entries. Only attributes that are relevant to the lifecycle STATE
are included here - attributes that change independently of state belong
in a separate sensor or diagnostics.

Included attributes (update only on state change):
- tomorrow_available: Whether tomorrow's price data is available
- next_api_poll: When the next API poll will occur (builds user trust)
- updates_today: Number of API calls made today
- last_turnover: When the last midnight turnover occurred
- last_error: Details of the last error (if any)

Pool statistics (sensor_intervals_count, cache_fill_percent, etc.) are
intentionally NOT included here because they change independently of
the lifecycle state. With state-change filtering, these would become
stale. Pool statistics are available via diagnostics or could be
exposed as a separate sensor if needed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from custom_components.tibber_prices.coordinator.core import (
        TibberPricesDataUpdateCoordinator,
    )
    from custom_components.tibber_prices.sensor.calculators.lifecycle import (
        TibberPricesLifecycleCalculator,
    )


def build_lifecycle_attributes(
    coordinator: TibberPricesDataUpdateCoordinator,
    lifecycle_calculator: TibberPricesLifecycleCalculator,
) -> dict[str, Any]:
    """
    Build attributes for data_lifecycle_status sensor.

    Event-based updates with state-change filtering - attributes only update
    when the lifecycle STATE changes (fresh→cached, cached→turnover_pending, etc.).

    Only includes attributes that are directly relevant to the lifecycle state.
    Pool statistics are intentionally excluded to avoid stale data.

    Returns:
        Dict with lifecycle attributes

    """
    attributes: dict[str, Any] = {}

    # === Tomorrow Data Status ===
    # Critical for understanding lifecycle state transitions
    attributes["tomorrow_available"] = lifecycle_calculator.has_tomorrow_data()

    # === Next API Poll Time ===
    # Builds user trust: shows when the integration will check for tomorrow data
    # - Before 13:00: Shows today 13:00 (when tomorrow-search begins)
    # - After 13:00 without tomorrow data: Shows next Timer #1 execution (active polling)
    # - After 13:00 with tomorrow data: Shows tomorrow 13:00 (predictive)
    next_poll = lifecycle_calculator.get_next_api_poll_time()
    if next_poll:
        attributes["next_api_poll"] = next_poll.isoformat()

    # === Update Statistics ===
    # Shows API activity - resets at midnight with turnover
    api_calls = lifecycle_calculator.get_api_calls_today()
    attributes["updates_today"] = api_calls

    # === Midnight Turnover Info ===
    # When was the last successful data rotation
    if coordinator._midnight_handler.last_turnover_time:  # noqa: SLF001
        attributes["last_turnover"] = coordinator._midnight_handler.last_turnover_time.isoformat()  # noqa: SLF001

    # === Error Status ===
    # Present only when there's an active error
    if coordinator.last_exception:
        attributes["last_error"] = str(coordinator.last_exception)

    return attributes
