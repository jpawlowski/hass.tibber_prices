"""
Data update coordination package.

This package orchestrates data fetching, caching, and entity updates:
- API polling at 15-minute intervals
- Persistent storage via HA Store
- Quarter-hour entity refresh scheduling
- Price data enrichment pipeline
- Period calculation (best/peak price periods)

Main components:
- core.py: TibberPricesDataUpdateCoordinator (main coordinator class)
- cache.py: Persistent storage management
- data_transformation.py: Raw data → enriched data pipeline
- listeners.py: Entity refresh scheduling
- period_handlers/: Period calculation sub-package
"""

from .constants import (
    MINUTE_UPDATE_ENTITY_KEYS,
    STORAGE_VERSION,
    TIME_SENSITIVE_ENTITY_KEYS,
)
from .core import TibberPricesDataUpdateCoordinator
from .time_service import TibberPricesTimeService

__all__ = [
    "MINUTE_UPDATE_ENTITY_KEYS",
    "STORAGE_VERSION",
    "TIME_SENSITIVE_ENTITY_KEYS",
    "TibberPricesDataUpdateCoordinator",
    "TibberPricesTimeService",
]
