"""
Service handler for find_most_expensive_block service.

Finds the most expensive contiguous window of a given duration within a search range.
Mirror of find_cheapest_block with reversed price selection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from .find_cheapest_block import _COMMON_BLOCK_SCHEMA, _handle_find_block

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall, ServiceResponse

FIND_MOST_EXPENSIVE_BLOCK_SERVICE_NAME = "find_most_expensive_block"

FIND_MOST_EXPENSIVE_BLOCK_SERVICE_SCHEMA = vol.Schema(_COMMON_BLOCK_SCHEMA)


async def handle_find_most_expensive_block(call: ServiceCall) -> ServiceResponse:
    """Handle find_most_expensive_block service call."""
    return await _handle_find_block(call, reverse=True)
