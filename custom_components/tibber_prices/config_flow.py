"""
Config flow for Tibber Prices integration.

This module serves as the entry point for Home Assistant's config flow discovery.
The actual implementation is in the config_flow_handlers package.
"""

from __future__ import annotations

from .config_flow_handlers.options_flow import (
    TibberPricesOptionsFlowHandler as OptionsFlowHandler,
)
from .config_flow_handlers.schemas import (
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
from .config_flow_handlers.subentry_flow import (
    TibberPricesSubentryFlowHandler as SubentryFlowHandler,
)
from .config_flow_handlers.user_flow import TibberPricesFlowHandler as ConfigFlow
from .config_flow_handlers.validators import (
    TibberPricesCannotConnectError,
    TibberPricesInvalidAuthError,
    validate_api_token,
)

__all__ = [
    "ConfigFlow",
    "OptionsFlowHandler",
    "SubentryFlowHandler",
    "TibberPricesCannotConnectError",
    "TibberPricesInvalidAuthError",
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
