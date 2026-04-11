"""
Service handler for find_most_expensive_hours service.

Finds the most expensive N minutes of intervals within a search range.
Mirror of find_cheapest_hours with reversed price selection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from .find_cheapest_hours import _COMMON_HOURS_SCHEMA, _handle_find_hours

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall, ServiceResponse

FIND_MOST_EXPENSIVE_HOURS_SERVICE_NAME = "find_most_expensive_hours"

FIND_MOST_EXPENSIVE_HOURS_SERVICE_SCHEMA = vol.Schema(_COMMON_HOURS_SCHEMA)


async def handle_find_most_expensive_hours(call: ServiceCall) -> ServiceResponse:
    """Handle find_most_expensive_hours service call."""
    return await _handle_find_hours(call, reverse=True)
