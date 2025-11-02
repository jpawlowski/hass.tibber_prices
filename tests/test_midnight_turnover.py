"""Test midnight turnover logic - focused unit tests."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import Mock, patch


def generate_price_intervals(
    start_date: datetime,
    num_intervals: int = 96,
    base_price: float = 0.20,
) -> list[dict]:
    """Generate realistic price intervals for a day."""
    intervals = []
    current_time = start_date.replace(hour=0, minute=0, second=0, microsecond=0)

    for i in range(num_intervals):
        intervals.append(
            {
                "startsAt": current_time.isoformat(),
                "total": base_price + (i * 0.001),
                "level": "NORMAL",
            }
        )
        current_time += timedelta(minutes=15)

    return intervals


def test_midnight_turnover_with_stale_today_data() -> None:
    """Test midnight turnover when today's data is from the previous day."""
    from custom_components.tibber_prices.coordinator import TibberPricesDataUpdateCoordinator

    coordinator = Mock(spec=TibberPricesDataUpdateCoordinator)
    coordinator._perform_midnight_turnover = TibberPricesDataUpdateCoordinator._perform_midnight_turnover.__get__(
        coordinator, TibberPricesDataUpdateCoordinator
    )

    today_local = datetime(2025, 11, 2, 14, 30)

    yesterday_prices = generate_price_intervals(
        datetime(2025, 11, 1, 0, 0),
        num_intervals=96,
    )

    tomorrow_prices = generate_price_intervals(
        datetime(2025, 11, 3, 0, 0),
        num_intervals=96,
    )

    price_info = {
        "yesterday": [],
        "today": yesterday_prices,
        "tomorrow": tomorrow_prices,
    }

    with patch("custom_components.tibber_prices.coordinator.dt_util") as mock_dt_util:
        mock_dt_util.as_local.side_effect = lambda dt: dt if dt else datetime(2025, 11, 2)
        mock_dt_util.now.return_value = today_local
        mock_dt_util.parse_datetime.side_effect = lambda s: (datetime.fromisoformat(s) if s else None)

        rotated = coordinator._perform_midnight_turnover(price_info)

        assert len(rotated["yesterday"]) == 96
        assert rotated["yesterday"][0]["startsAt"].startswith("2025-11-01")

        assert len(rotated["today"]) == 96
        assert rotated["today"][0]["startsAt"].startswith("2025-11-03")

        assert len(rotated["tomorrow"]) == 0


def test_midnight_turnover_no_rotation_needed() -> None:
    """Test that turnover skips rotation when data is already current."""
    from custom_components.tibber_prices.coordinator import TibberPricesDataUpdateCoordinator

    coordinator = Mock(spec=TibberPricesDataUpdateCoordinator)
    coordinator._perform_midnight_turnover = TibberPricesDataUpdateCoordinator._perform_midnight_turnover.__get__(
        coordinator, TibberPricesDataUpdateCoordinator
    )

    today_local = datetime(2025, 11, 2, 14, 30)

    today_prices = generate_price_intervals(
        datetime(2025, 11, 2, 0, 0),
        num_intervals=96,
    )

    tomorrow_prices = generate_price_intervals(
        datetime(2025, 11, 3, 0, 0),
        num_intervals=96,
    )

    price_info = {
        "yesterday": [],
        "today": today_prices,
        "tomorrow": tomorrow_prices,
    }

    with patch("custom_components.tibber_prices.coordinator.dt_util") as mock_dt_util:
        mock_dt_util.as_local.side_effect = lambda dt: dt if dt else datetime(2025, 11, 2)
        mock_dt_util.now.return_value = today_local
        mock_dt_util.parse_datetime.side_effect = lambda s: (datetime.fromisoformat(s) if s else None)

        rotated = coordinator._perform_midnight_turnover(price_info)

        assert rotated == price_info
        assert rotated["today"][0]["startsAt"].startswith("2025-11-02")


def test_scenario_missed_midnight_recovery() -> None:
    """Scenario: Server was down at midnight, comes back online later."""
    from custom_components.tibber_prices.coordinator import TibberPricesDataUpdateCoordinator

    coordinator = Mock(spec=TibberPricesDataUpdateCoordinator)
    coordinator._perform_midnight_turnover = TibberPricesDataUpdateCoordinator._perform_midnight_turnover.__get__(
        coordinator, TibberPricesDataUpdateCoordinator
    )

    yesterday_prices = generate_price_intervals(datetime(2025, 11, 1, 0, 0))
    tomorrow_prices = generate_price_intervals(datetime(2025, 11, 2, 0, 0))

    price_info = {
        "yesterday": [],
        "today": yesterday_prices,
        "tomorrow": tomorrow_prices,
    }

    with patch("custom_components.tibber_prices.coordinator.dt_util") as mock_dt_util:
        current_local = datetime(2025, 11, 2, 14, 0)

        mock_dt_util.as_local.side_effect = lambda dt: (dt if isinstance(dt, datetime) else current_local)
        mock_dt_util.now.return_value = current_local
        mock_dt_util.parse_datetime.side_effect = lambda s: (datetime.fromisoformat(s) if s else None)

        rotated = coordinator._perform_midnight_turnover(price_info)

        assert len(rotated["yesterday"]) == 96
        assert rotated["yesterday"][0]["startsAt"].startswith("2025-11-01")

        assert len(rotated["today"]) == 96
        assert rotated["today"][0]["startsAt"].startswith("2025-11-02")

        assert len(rotated["tomorrow"]) == 0


def test_scenario_normal_daily_refresh() -> None:
    """Scenario: Normal daily refresh at 5 AM (all data is current)."""
    from custom_components.tibber_prices.coordinator import TibberPricesDataUpdateCoordinator

    coordinator = Mock(spec=TibberPricesDataUpdateCoordinator)
    coordinator._perform_midnight_turnover = TibberPricesDataUpdateCoordinator._perform_midnight_turnover.__get__(
        coordinator, TibberPricesDataUpdateCoordinator
    )

    today_prices = generate_price_intervals(datetime(2025, 11, 2, 0, 0))
    tomorrow_prices = generate_price_intervals(datetime(2025, 11, 3, 0, 0))

    price_info = {
        "yesterday": [],
        "today": today_prices,
        "tomorrow": tomorrow_prices,
    }

    with patch("custom_components.tibber_prices.coordinator.dt_util") as mock_dt_util:
        current_local = datetime(2025, 11, 2, 5, 0)

        mock_dt_util.as_local.side_effect = lambda dt: (dt if isinstance(dt, datetime) else current_local)
        mock_dt_util.now.return_value = current_local
        mock_dt_util.parse_datetime.side_effect = lambda s: (datetime.fromisoformat(s) if s else None)

        rotated = coordinator._perform_midnight_turnover(price_info)

        assert len(rotated["today"]) == 96
        assert rotated["today"][0]["startsAt"].startswith("2025-11-02")
        assert len(rotated["tomorrow"]) == 96
        assert rotated["tomorrow"][0]["startsAt"].startswith("2025-11-03")
