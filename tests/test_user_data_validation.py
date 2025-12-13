"""
Test user data validation and currency extraction.

This test covers issue #60 where the Tibber API can temporarily return
incomplete or invalid data during maintenance or cache refresh periods.

The issue manifested when:
1. User updated integration while Tibber API was returning incomplete data
2. Integration accepted and cached the incomplete data
3. Next access crashed or used wrong currency (EUR fallback)
4. Next day at 13:02, user_data refreshed (24h interval) with correct data
5. Issue "fixed itself" because cache was updated with valid data

The fix implements data validation that:
- Rejects incomplete user data from API
- Keeps existing cached data when validation fails
- Only accepts data with complete home info (timezone, currency if subscription exists)
- Raises exception if currency cannot be determined (no silent EUR fallback)
"""

from datetime import timedelta

import pytest

from custom_components.tibber_prices.api.exceptions import TibberPricesApiClientError
from custom_components.tibber_prices.api.helpers import flatten_price_info
from custom_components.tibber_prices.coordinator.data_fetching import (
    TibberPricesDataFetcher,
)


@pytest.mark.unit
def test_validate_user_data_complete(mock_api_client, mock_time_service, mock_store) -> None:  # noqa: ANN001
    """Test that complete user data passes validation."""
    fetcher = TibberPricesDataFetcher(
        api=mock_api_client,
        store=mock_store,
        log_prefix="[Test]",
        user_update_interval=timedelta(days=1),
        time=mock_time_service,
        home_id="home-123",
    )

    user_data = {
        "viewer": {
            "homes": [
                {
                    "id": "home-123",
                    "timeZone": "Europe/Berlin",
                    "currentSubscription": {
                        "priceInfo": {
                            "current": {
                                "currency": "EUR",
                            }
                        }
                    },
                }
            ]
        }
    }

    assert fetcher._validate_user_data(user_data, "home-123") is True  # noqa: SLF001  # noqa: SLF001


@pytest.mark.unit
def test_validate_user_data_none_subscription(mock_api_client, mock_time_service, mock_store) -> None:  # noqa: ANN001
    """Test that user data without subscription (but with timezone) passes validation."""
    fetcher = TibberPricesDataFetcher(
        api=mock_api_client,
        store=mock_store,
        log_prefix="[Test]",
        user_update_interval=timedelta(days=1),
        time=mock_time_service,
        home_id="home-123",
    )

    user_data = {
        "viewer": {
            "homes": [
                {
                    "id": "home-123",
                    "timeZone": "Europe/Berlin",
                    "currentSubscription": None,  # No active subscription
                }
            ]
        }
    }

    # Should pass validation - timezone is present, subscription being None is valid
    assert fetcher._validate_user_data(user_data, "home-123") is True  # noqa: SLF001  # noqa: SLF001


@pytest.mark.unit
def test_validate_user_data_missing_timezone(mock_api_client, mock_time_service, mock_store) -> None:  # noqa: ANN001
    """Test that user data without timezone fails validation."""
    fetcher = TibberPricesDataFetcher(
        api=mock_api_client,
        store=mock_store,
        log_prefix="[Test]",
        user_update_interval=timedelta(days=1),
        time=mock_time_service,
        home_id="home-123",
    )

    user_data = {
        "viewer": {
            "homes": [
                {
                    "id": "home-123",
                    # Missing timeZone!
                    "currentSubscription": {
                        "priceInfo": {
                            "current": {
                                "currency": "EUR",
                            }
                        }
                    },
                }
            ]
        }
    }

    assert fetcher._validate_user_data(user_data, "home-123") is False  # noqa: SLF001  # noqa: SLF001


@pytest.mark.unit
def test_validate_user_data_subscription_without_currency(mock_api_client, mock_time_service, mock_store) -> None:  # noqa: ANN001
    """Test that user data with subscription but no currency fails validation."""
    fetcher = TibberPricesDataFetcher(
        api=mock_api_client,
        store=mock_store,
        log_prefix="[Test]",
        user_update_interval=timedelta(days=1),
        time=mock_time_service,
        home_id="home-123",
    )

    user_data = {
        "viewer": {
            "homes": [
                {
                    "id": "home-123",
                    "timeZone": "Europe/Berlin",
                    "currentSubscription": {
                        "priceInfo": {
                            "current": {}  # Currency missing!
                        }
                    },
                }
            ]
        }
    }

    assert fetcher._validate_user_data(user_data, "home-123") is False  # noqa: SLF001  # noqa: SLF001


@pytest.mark.unit
def test_validate_user_data_home_not_found(mock_api_client, mock_time_service, mock_store) -> None:  # noqa: ANN001
    """Test that user data without the requested home fails validation."""
    fetcher = TibberPricesDataFetcher(
        api=mock_api_client,
        store=mock_store,
        log_prefix="[Test]",
        user_update_interval=timedelta(days=1),
        time=mock_time_service,
        home_id="home-123",
    )

    user_data = {
        "viewer": {
            "homes": [
                {
                    "id": "other-home",
                    "timeZone": "Europe/Berlin",
                }
            ]
        }
    }

    assert fetcher._validate_user_data(user_data, "home-123") is False  # noqa: SLF001  # noqa: SLF001


@pytest.mark.unit
def test_get_currency_raises_on_no_cached_data(mock_api_client, mock_time_service, mock_store) -> None:  # noqa: ANN001
    """Test that _get_currency_for_home raises exception when no data cached."""
    fetcher = TibberPricesDataFetcher(
        api=mock_api_client,
        store=mock_store,
        log_prefix="[Test]",
        user_update_interval=timedelta(days=1),
        time=mock_time_service,
        home_id="home-123",
    )

    # No cached data
    with pytest.raises(TibberPricesApiClientError, match="No user data cached"):
        fetcher._get_currency_for_home("home-123")  # noqa: SLF001  # noqa: SLF001


@pytest.mark.unit
def test_get_currency_raises_on_no_subscription(mock_api_client, mock_time_service, mock_store) -> None:  # noqa: ANN001
    """Test that _get_currency_for_home raises exception when home has no subscription."""
    fetcher = TibberPricesDataFetcher(
        api=mock_api_client,
        store=mock_store,
        log_prefix="[Test]",
        user_update_interval=timedelta(days=1),
        time=mock_time_service,
        home_id="home-123",
    )

    fetcher._cached_user_data = {  # noqa: SLF001  # noqa: SLF001
        "viewer": {
            "homes": [
                {
                    "id": "home-123",
                    "currentSubscription": None,  # No subscription
                }
            ]
        }
    }

    with pytest.raises(TibberPricesApiClientError, match="has no active subscription"):
        fetcher._get_currency_for_home("home-123")  # noqa: SLF001  # noqa: SLF001


@pytest.mark.unit
def test_get_currency_extracts_valid_currency(mock_api_client, mock_time_service, mock_store) -> None:  # noqa: ANN001
    """Test that _get_currency_for_home successfully extracts currency."""
    fetcher = TibberPricesDataFetcher(
        api=mock_api_client,
        store=mock_store,
        log_prefix="[Test]",
        user_update_interval=timedelta(days=1),
        time=mock_time_service,
        home_id="home-123",
    )

    fetcher._cached_user_data = {  # noqa: SLF001  # noqa: SLF001
        "viewer": {
            "homes": [
                {
                    "id": "home-123",
                    "currentSubscription": {
                        "priceInfo": {
                            "current": {
                                "currency": "NOK",
                            }
                        }
                    },
                }
            ]
        }
    }

    assert fetcher._get_currency_for_home("home-123") == "NOK"  # noqa: SLF001  # noqa: SLF001


@pytest.mark.unit
def test_flatten_price_info_with_none_priceinfo() -> None:
    """Test that flatten_price_info handles None priceInfo gracefully."""
    subscription = {
        "priceInfoRange": {
            "edges": [
                {"node": {"startsAt": "2025-12-10T00:00:00", "total": 0.25, "level": "NORMAL"}},
            ]
        },
        "priceInfo": None,  # ← Key exists but value is None
    }

    # Should not crash, should return only historical prices
    result = flatten_price_info(subscription)
    assert len(result) == 1
    assert result[0]["total"] == 0.25


@pytest.mark.unit
def test_flatten_price_info_with_none_today() -> None:
    """Test that flatten_price_info handles None today gracefully."""
    subscription = {
        "priceInfoRange": {"edges": []},
        "priceInfo": {
            "today": None,  # ← Key exists but value is None
            "tomorrow": [
                {"startsAt": "2025-12-13T00:00:00", "total": 0.30, "level": "NORMAL"},
            ],
        },
    }

    # Should not crash, should return only tomorrow prices
    result = flatten_price_info(subscription)
    assert len(result) == 1
    assert result[0]["total"] == 0.30


@pytest.mark.unit
def test_flatten_price_info_with_all_none() -> None:
    """Test that flatten_price_info handles all None values gracefully."""
    subscription = {
        "priceInfoRange": None,
        "priceInfo": None,
    }

    # Should not crash, should return empty list
    result = flatten_price_info(subscription)
    assert result == []
