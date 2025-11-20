"""
Calculator classes for Tibber Prices sensor value calculations.

This package contains specialized calculator classes that handle different types
of sensor value calculations. Each calculator focuses on one calculation pattern
(interval-based, rolling hour, daily statistics, etc.).

All calculators inherit from BaseCalculator and have access to coordinator data.
"""

from __future__ import annotations

from .base import TibberPricesBaseCalculator
from .daily_stat import TibberPricesDailyStatCalculator
from .interval import TibberPricesIntervalCalculator
from .metadata import TibberPricesMetadataCalculator
from .rolling_hour import TibberPricesRollingHourCalculator
from .timing import TibberPricesTimingCalculator
from .trend import TibberPricesTrendCalculator
from .volatility import TibberPricesVolatilityCalculator
from .window_24h import TibberPricesWindow24hCalculator

__all__ = [
    "TibberPricesBaseCalculator",
    "TibberPricesDailyStatCalculator",
    "TibberPricesIntervalCalculator",
    "TibberPricesMetadataCalculator",
    "TibberPricesRollingHourCalculator",
    "TibberPricesTimingCalculator",
    "TibberPricesTrendCalculator",
    "TibberPricesVolatilityCalculator",
    "TibberPricesWindow24hCalculator",
]
