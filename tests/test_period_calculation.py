"""
Tests for Period Calculation - Integration tests only.

NOTE: Period building functions (build_periods, split_intervals_by_day, etc.) are too
complex for effective unit testing. They require:

1. TibberPricesTimeService instance with full coordinator context
2. Complex price_context dict with ref_prices, avg_prices, flex, min_distance
3. Enriched price data with rating_level, _original_price, trailing_avg_24h, etc.

These functions are comprehensively tested via integration tests:
- tests/test_midnight_periods.py: Period calculation across day boundaries
- tests/test_midnight_turnover.py: Midnight cache invalidation and period recalculation

Unit testing individual helper functions (split_intervals_by_day, calculate_reference_prices)
provides minimal value since they're simple data transformations that can't fail independently
from the overall period building logic.

If you need to debug period calculation issues, run the integration tests with -v flag:
    ./scripts/test tests/test_midnight_periods.py -v
    ./scripts/test tests/test_midnight_turnover.py -v

For period calculation theory and algorithm documentation, see:
    docs/development/period-calculation-theory.md
"""
