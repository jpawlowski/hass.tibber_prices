"""
Calculator classes for Tibber Prices sensor value calculations.

This package contains specialized calculator classes that handle different types
of sensor value calculations. Each calculator focuses on one calculation pattern
(interval-based, rolling hour, daily statistics, etc.).

All calculators inherit from BaseCalculator and have access to coordinator data.
"""

from __future__ import annotations

from .base import BaseCalculator
from .daily_stat import DailyStatCalculator
from .interval import IntervalCalculator
from .metadata import MetadataCalculator
from .rolling_hour import RollingHourCalculator
from .timing import TimingCalculator
from .trend import TrendCalculator
from .volatility import VolatilityCalculator
from .window_24h import Window24hCalculator

__all__ = [
    "BaseCalculator",
    "DailyStatCalculator",
    "IntervalCalculator",
    "MetadataCalculator",
    "RollingHourCalculator",
    "TimingCalculator",
    "TrendCalculator",
    "VolatilityCalculator",
    "Window24hCalculator",
]
