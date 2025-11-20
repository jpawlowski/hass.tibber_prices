"""
Period calculation utilities (sub-package for modular organization).

This package splits period calculation logic into focused modules:
- types: Type definitions and constants
- level_filtering: Interval-level filtering logic
- period_building: Period construction from intervals
- period_statistics: Statistics calculation
- period_overlap: Overlap resolution logic
- relaxation: Per-day relaxation strategy
- core: Main API orchestration
- outlier_filtering: Price spike detection and smoothing

All public APIs are re-exported for backwards compatibility.
"""

from __future__ import annotations

# Re-export main API functions
from .core import calculate_periods

# Re-export outlier filtering
from .outlier_filtering import filter_price_outliers

# Re-export relaxation
from .relaxation import calculate_periods_with_relaxation

# Re-export constants and types
from .types import (
    INDENT_L0,
    INDENT_L1,
    INDENT_L2,
    INDENT_L3,
    INDENT_L4,
    INDENT_L5,
    TibberPricesIntervalCriteria,
    TibberPricesPeriodConfig,
    TibberPricesPeriodData,
    TibberPricesPeriodStatistics,
    TibberPricesThresholdConfig,
)

__all__ = [
    "INDENT_L0",
    "INDENT_L1",
    "INDENT_L2",
    "INDENT_L3",
    "INDENT_L4",
    "INDENT_L5",
    "TibberPricesIntervalCriteria",
    "TibberPricesPeriodConfig",
    "TibberPricesPeriodData",
    "TibberPricesPeriodStatistics",
    "TibberPricesThresholdConfig",
    "calculate_periods",
    "calculate_periods_with_relaxation",
    "filter_price_outliers",
]
