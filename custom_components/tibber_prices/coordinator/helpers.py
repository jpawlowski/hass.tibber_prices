"""Pure utility functions for coordinator module."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from datetime import date

    from homeassistant.core import HomeAssistant

from custom_components.tibber_prices.const import DOMAIN


def get_configured_home_ids(hass: HomeAssistant) -> set[str]:
    """Get all home_ids that have active config entries (main + subentries)."""
    home_ids = set()

    # Collect home_ids from all config entries for this domain
    for entry in hass.config_entries.async_entries(DOMAIN):
        if home_id := entry.data.get("home_id"):
            home_ids.add(home_id)

    return home_ids


def needs_tomorrow_data(cached_price_data: dict[str, Any] | None, tomorrow_date: date) -> bool:
    """Check if tomorrow data is missing or invalid."""
    if not cached_price_data or "homes" not in cached_price_data:
        return False

    for home_data in cached_price_data["homes"].values():
        price_info = home_data.get("price_info", {})
        tomorrow_prices = price_info.get("tomorrow", [])

        # Check if tomorrow data is missing
        if not tomorrow_prices:
            return True

        # Check if tomorrow data is actually for tomorrow (validate date)
        first_price = tomorrow_prices[0]
        if starts_at := first_price.get("startsAt"):
            price_time = dt_util.parse_datetime(starts_at)
            if price_time:
                price_date = dt_util.as_local(price_time).date()
                if price_date != tomorrow_date:
                    return True

    return False


def perform_midnight_turnover(price_info: dict[str, Any]) -> dict[str, Any]:
    """
    Perform midnight turnover on price data.

    Moves: today → yesterday, tomorrow → today, clears tomorrow.

    This handles cases where:
    - Server was running through midnight
    - Cache is being refreshed and needs proper day rotation

    Args:
        price_info: The price info dict with 'today', 'tomorrow', 'yesterday' keys

    Returns:
        Updated price_info with rotated day data

    """
    current_local_date = dt_util.as_local(dt_util.now()).date()

    # Extract current data
    today_prices = price_info.get("today", [])
    tomorrow_prices = price_info.get("tomorrow", [])

    # Check if any of today's prices are from the previous day
    prices_need_rotation = False
    if today_prices:
        first_today_price_str = today_prices[0].get("startsAt")
        if first_today_price_str:
            first_today_price_time = dt_util.parse_datetime(first_today_price_str)
            if first_today_price_time:
                first_today_price_date = dt_util.as_local(first_today_price_time).date()
                prices_need_rotation = first_today_price_date < current_local_date

    if prices_need_rotation:
        return {
            "yesterday": today_prices,
            "today": tomorrow_prices,
            "tomorrow": [],
            "currency": price_info.get("currency", "EUR"),
        }

    return price_info
