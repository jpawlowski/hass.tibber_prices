"""
Configuration flow package for UI-based setup.

This package handles all user interaction for integration configuration:
- Initial setup: API token validation, home selection
- Subentry flow: Add additional Tibber homes
- Options flow: Multi-step configuration wizard
- Reauthentication: Token refresh when expired

Flow handlers:
- user_flow.py: Initial setup and reauth
- subentry_flow.py: Add additional homes
- options_flow.py: 6-step configuration wizard

Supporting modules:
- schemas.py: Form schema definitions (vol.Schema)
- validators.py: Input validation and API testing
"""

from __future__ import annotations

# Phase 3: Import flow handlers from their new modular structure
from custom_components.tibber_prices.config_flow_handlers.options_flow import (
    TibberPricesOptionsFlowHandler,
)
from custom_components.tibber_prices.config_flow_handlers.schemas import (
    get_best_price_schema,
    get_options_init_schema,
    get_peak_price_schema,
    get_price_rating_schema,
    get_price_trend_schema,
    get_reauth_confirm_schema,
    get_select_home_schema,
    get_subentry_init_schema,
    get_user_schema,
    get_volatility_schema,
)
from custom_components.tibber_prices.config_flow_handlers.subentry_flow import (
    TibberPricesSubentryFlowHandler,
)
from custom_components.tibber_prices.config_flow_handlers.user_flow import (
    TibberPricesFlowHandler,
)
from custom_components.tibber_prices.config_flow_handlers.validators import (
    TibberPricesCannotConnectError,
    TibberPricesInvalidAuthError,
    validate_api_token,
)

__all__ = [
    "TibberPricesCannotConnectError",
    "TibberPricesFlowHandler",
    "TibberPricesInvalidAuthError",
    "TibberPricesOptionsFlowHandler",
    "TibberPricesSubentryFlowHandler",
    "get_best_price_schema",
    "get_options_init_schema",
    "get_peak_price_schema",
    "get_price_rating_schema",
    "get_price_trend_schema",
    "get_reauth_confirm_schema",
    "get_select_home_schema",
    "get_subentry_init_schema",
    "get_user_schema",
    "get_volatility_schema",
    "validate_api_token",
]
