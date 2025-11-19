"""Pure utility functions for coordinator module."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import date

    from homeassistant.core import HomeAssistant

    from .time_service import TimeService

from custom_components.tibber_prices.const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def get_configured_home_ids(hass: HomeAssistant) -> set[str]:
    """Get all home_ids that have active config entries (main + subentries)."""
    home_ids = set()

    # Collect home_ids from all config entries for this domain
    for entry in hass.config_entries.async_entries(DOMAIN):
        if home_id := entry.data.get("home_id"):
            home_ids.add(home_id)

    return home_ids


def needs_tomorrow_data(
    cached_price_data: dict[str, Any] | None,
    tomorrow_date: date,
) -> bool:
    """Check if tomorrow data is missing or invalid."""
    if not cached_price_data or "homes" not in cached_price_data:
        return False

    # Use provided TimeService or create new one

    for home_data in cached_price_data["homes"].values():
        price_info = home_data.get("price_info", {})
        tomorrow_prices = price_info.get("tomorrow", [])

        # Check if tomorrow data is missing
        if not tomorrow_prices:
            return True

        # Check if tomorrow data is actually for tomorrow (validate date)
        first_price = tomorrow_prices[0]
        if starts_at := first_price.get("startsAt"):  # Already datetime in local timezone
            price_date = starts_at.date()
            if price_date != tomorrow_date:
                return True

    return False


def perform_midnight_turnover(price_info: dict[str, Any], *, time: TimeService) -> dict[str, Any]:
    """
    Perform midnight turnover on price data.

    Moves: today → yesterday, tomorrow → today, clears tomorrow.

    This handles cases where:
    - Server was running through midnight
    - Cache is being refreshed and needs proper day rotation

    Args:
        price_info: The price info dict with 'today', 'tomorrow', 'yesterday' keys
        time: TimeService instance (required)

    Returns:
        Updated price_info with rotated day data

    """
    # Use provided TimeService or create new one

    current_local_date = time.now().date()

    # Extract current data
    today_prices = price_info.get("today", [])
    tomorrow_prices = price_info.get("tomorrow", [])

    # Check if any of today's prices are from the previous day
    prices_need_rotation = False
    if today_prices:
        first_today_price = today_prices[0].get("startsAt")  # Already datetime in local timezone
        if first_today_price:
            first_today_price_date = first_today_price.date()
            prices_need_rotation = first_today_price_date < current_local_date

    if prices_need_rotation:
        return {
            "yesterday": today_prices,
            "today": tomorrow_prices,
            "tomorrow": [],
            "currency": price_info.get("currency", "EUR"),
        }

    # No rotation needed, return original
    return price_info


def parse_all_timestamps(price_data: dict[str, Any], *, time: TimeService) -> dict[str, Any]:
    """
    Parse all API timestamp strings to datetime objects.

    This is the SINGLE place where we convert API strings to datetime objects.
    After this, all code works with datetime objects, not strings.

    Performance: ~200 timestamps parsed ONCE instead of multiple times per update cycle.

    Args:
        price_data: Raw API data with string timestamps
        time: TimeService for parsing

    Returns:
        Same structure but with datetime objects instead of strings

    """
    if not price_data or "homes" not in price_data:
        return price_data

    # Process each home
    for home_data in price_data["homes"].values():
        price_info = home_data.get("price_info", {})

        # Process each day's intervals
        for day_key in ["yesterday", "today", "tomorrow"]:
            intervals = price_info.get(day_key, [])
            for interval in intervals:
                if (starts_at_str := interval.get("startsAt")) and isinstance(starts_at_str, str):
                    # Parse once, convert to local timezone, store as datetime object
                    interval["startsAt"] = time.parse_and_localize(starts_at_str)
                    # If already datetime (e.g., from cache), skip parsing

    return price_data

    return price_info
