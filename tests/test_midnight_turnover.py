"""Test midnight turnover logic - focused unit tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

from custom_components.tibber_prices.coordinator import (
    TibberPricesDataUpdateCoordinator,
)

# Constants for test validation
INTERVALS_PER_DAY = 96
BASE_PRICE = 0.20
PRICE_INCREMENT = 0.001


def generate_price_intervals(
    start_date: datetime,
    num_intervals: int = INTERVALS_PER_DAY,
    base_price: float = BASE_PRICE,
) -> list[dict]:
    """Generate realistic price intervals for a day."""
    intervals = []
    current_time = start_date.replace(hour=0, minute=0, second=0, microsecond=0)

    for i in range(num_intervals):
        intervals.append(
            {
                "startsAt": current_time.isoformat(),
                "total": base_price + (i * PRICE_INCREMENT),
                "level": "NORMAL",
            }
        )
        current_time += timedelta(minutes=15)

    return intervals


def test_midnight_turnover_with_stale_today_data() -> None:
    """Test midnight turnover when today's data is from the previous day."""
    coordinator = Mock(spec=TibberPricesDataUpdateCoordinator)
    coordinator._perform_midnight_turnover = (  # noqa: SLF001
        TibberPricesDataUpdateCoordinator._perform_midnight_turnover.__get__(  # noqa: SLF001
            coordinator, TibberPricesDataUpdateCoordinator
        )
    )

    today_local = datetime(2025, 11, 2, 14, 30, tzinfo=UTC)

    yesterday_prices = generate_price_intervals(
        datetime(2025, 11, 1, 0, 0, tzinfo=UTC),
        num_intervals=INTERVALS_PER_DAY,
    )

    tomorrow_prices = generate_price_intervals(
        datetime(2025, 11, 3, 0, 0, tzinfo=UTC),
        num_intervals=INTERVALS_PER_DAY,
    )

    price_info = {
        "yesterday": [],
        "today": yesterday_prices,
        "tomorrow": tomorrow_prices,
    }

    with patch("custom_components.tibber_prices.coordinator.dt_util") as mock_dt_util:
        mock_dt_util.as_local.side_effect = lambda dt: (dt if dt else datetime(2025, 11, 2, tzinfo=UTC))
        mock_dt_util.now.return_value = today_local
        mock_dt_util.parse_datetime.side_effect = lambda s: (datetime.fromisoformat(s) if s else None)

        rotated = coordinator._perform_midnight_turnover(price_info)  # noqa: SLF001

        assert len(rotated["yesterday"]) == INTERVALS_PER_DAY  # noqa: S101
        assert rotated["yesterday"][0]["startsAt"].startswith("2025-11-01")  # noqa: S101

        assert len(rotated["today"]) == INTERVALS_PER_DAY  # noqa: S101
        assert rotated["today"][0]["startsAt"].startswith("2025-11-03")  # noqa: S101

        assert len(rotated["tomorrow"]) == 0  # noqa: S101


def test_midnight_turnover_no_rotation_needed() -> None:
    """Test that turnover skips rotation when data is already current."""
    coordinator = Mock(spec=TibberPricesDataUpdateCoordinator)
    coordinator._perform_midnight_turnover = (  # noqa: SLF001
        TibberPricesDataUpdateCoordinator._perform_midnight_turnover.__get__(  # noqa: SLF001
            coordinator, TibberPricesDataUpdateCoordinator
        )
    )

    today_local = datetime(2025, 11, 2, 14, 30, tzinfo=UTC)

    today_prices = generate_price_intervals(
        datetime(2025, 11, 2, 0, 0, tzinfo=UTC),
        num_intervals=INTERVALS_PER_DAY,
    )

    tomorrow_prices = generate_price_intervals(
        datetime(2025, 11, 3, 0, 0, tzinfo=UTC),
        num_intervals=INTERVALS_PER_DAY,
    )

    price_info = {
        "yesterday": [],
        "today": today_prices,
        "tomorrow": tomorrow_prices,
    }

    with patch("custom_components.tibber_prices.coordinator.dt_util") as mock_dt_util:
        mock_dt_util.as_local.side_effect = lambda dt: (dt if dt else datetime(2025, 11, 2, tzinfo=UTC))
        mock_dt_util.now.return_value = today_local
        mock_dt_util.parse_datetime.side_effect = lambda s: (datetime.fromisoformat(s) if s else None)

        rotated = coordinator._perform_midnight_turnover(price_info)  # noqa: SLF001

        assert rotated == price_info  # noqa: S101
        assert rotated["today"][0]["startsAt"].startswith("2025-11-02")  # noqa: S101


def test_scenario_missed_midnight_recovery() -> None:
    """Scenario: Server was down at midnight, comes back online later."""
    coordinator = Mock(spec=TibberPricesDataUpdateCoordinator)
    coordinator._perform_midnight_turnover = (  # noqa: SLF001
        TibberPricesDataUpdateCoordinator._perform_midnight_turnover.__get__(  # noqa: SLF001
            coordinator, TibberPricesDataUpdateCoordinator
        )
    )

    yesterday_prices = generate_price_intervals(datetime(2025, 11, 1, 0, 0, tzinfo=UTC))
    tomorrow_prices = generate_price_intervals(datetime(2025, 11, 2, 0, 0, tzinfo=UTC))

    price_info = {
        "yesterday": [],
        "today": yesterday_prices,
        "tomorrow": tomorrow_prices,
    }

    with patch("custom_components.tibber_prices.coordinator.dt_util") as mock_dt_util:
        current_local = datetime(2025, 11, 2, 14, 0, tzinfo=UTC)

        mock_dt_util.as_local.side_effect = lambda dt: (dt if isinstance(dt, datetime) else current_local)
        mock_dt_util.now.return_value = current_local
        mock_dt_util.parse_datetime.side_effect = lambda s: (datetime.fromisoformat(s) if s else None)

        rotated = coordinator._perform_midnight_turnover(price_info)  # noqa: SLF001

        assert len(rotated["yesterday"]) == INTERVALS_PER_DAY  # noqa: S101
        assert rotated["yesterday"][0]["startsAt"].startswith("2025-11-01")  # noqa: S101

        assert len(rotated["today"]) == INTERVALS_PER_DAY  # noqa: S101
        assert rotated["today"][0]["startsAt"].startswith("2025-11-02")  # noqa: S101

        assert len(rotated["tomorrow"]) == 0  # noqa: S101


def test_scenario_normal_daily_refresh() -> None:
    """Scenario: Normal daily refresh at 5 AM (all data is current)."""
    coordinator = Mock(spec=TibberPricesDataUpdateCoordinator)
    coordinator._perform_midnight_turnover = (  # noqa: SLF001
        TibberPricesDataUpdateCoordinator._perform_midnight_turnover.__get__(  # noqa: SLF001
            coordinator, TibberPricesDataUpdateCoordinator
        )
    )

    today_prices = generate_price_intervals(datetime(2025, 11, 2, 0, 0, tzinfo=UTC))
    tomorrow_prices = generate_price_intervals(datetime(2025, 11, 3, 0, 0, tzinfo=UTC))

    price_info = {
        "yesterday": [],
        "today": today_prices,
        "tomorrow": tomorrow_prices,
    }

    with patch("custom_components.tibber_prices.coordinator.dt_util") as mock_dt_util:
        current_local = datetime(2025, 11, 2, 5, 0, tzinfo=UTC)

        mock_dt_util.as_local.side_effect = lambda dt: (dt if isinstance(dt, datetime) else current_local)
        mock_dt_util.now.return_value = current_local
        mock_dt_util.parse_datetime.side_effect = lambda s: (datetime.fromisoformat(s) if s else None)

        rotated = coordinator._perform_midnight_turnover(price_info)  # noqa: SLF001

        assert len(rotated["today"]) == INTERVALS_PER_DAY  # noqa: S101
        assert rotated["today"][0]["startsAt"].startswith("2025-11-02")  # noqa: S101
        assert len(rotated["tomorrow"]) == INTERVALS_PER_DAY  # noqa: S101
        assert rotated["tomorrow"][0]["startsAt"].startswith("2025-11-03")  # noqa: S101
