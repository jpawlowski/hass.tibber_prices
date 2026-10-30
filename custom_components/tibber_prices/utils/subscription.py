"""
Subscription phase helpers.

A Tibber contract can be set up before it starts and keeps its data after it
ended. The integration treats the three phases differently:

* ``pending``: ``validFrom`` lies in the future and the status is not "running".
  Right after signing up it is "awaiting market" (the switch of supplier is not
  confirmed): Tibber has no prices then (``priceInfo.current`` is null,
  ``today``/``tomorrow`` are empty), so nothing is fetched and only the entities
  that need no prices exist. Once the switch is confirmed the status turns
  "running" and Tibber sends the prices of the price area, often weeks before
  ``validFrom``: such a contract is ``active``. The status decides, not a missing
  current price: that also happens during Tibber's maintenance, and must not stop
  a running contract.
* ``active``: the normal case, also assumed when the dates are unknown.
* ``ended``: ``validTo`` has passed. The clock of the entities stops on the
  last day of the contract (see ``get_subscription_last_interval_start``).

Pure functions, no Home Assistant dependencies.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

PHASE_PENDING = "pending"
PHASE_ACTIVE = "active"
PHASE_ENDED = "ended"


def find_subscription(user_data: dict[str, Any] | None, home_id: str) -> dict[str, Any] | None:
    """Return the ``currentSubscription`` of a home from the viewer query, if present."""
    if not user_data:
        return None
    viewer = user_data.get("viewer") or {}
    for home in viewer.get("homes") or []:
        if home.get("id") == home_id:
            return home.get("currentSubscription") or None
    return None


def _parse(value: Any) -> datetime | None:
    """Parse an ISO timestamp from the API; a value without offset is UTC, a malformed one unknown."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def get_subscription_start(subscription: dict[str, Any] | None) -> datetime | None:
    """Return when the subscription starts (``validFrom``), or None if unknown."""
    return _parse(subscription.get("validFrom")) if subscription else None


def get_subscription_end(subscription: dict[str, Any] | None) -> datetime | None:
    """Return when the subscription ends (``validTo``, exclusive), or None if open-ended."""
    return _parse(subscription.get("validTo")) if subscription else None


def get_subscription_last_interval_start(subscription: dict[str, Any] | None) -> datetime | None:
    """
    Return the start of the last quarter hour inside the subscription, or None if it is open-ended.

    ``validTo`` is the first moment after the contract. The entities of an ended
    subscription stay on the day before it, at its last interval: a moment inside
    that interval, not its very end, because a clock a second before midnight
    would be rounded up to the next day's first interval.
    """
    end = get_subscription_end(subscription)
    if end is None:
        return None
    last = end - timedelta(seconds=1)
    return last.replace(minute=last.minute - last.minute % 15, second=0, microsecond=0)


def get_subscription_phase(subscription: dict[str, Any] | None, now: datetime) -> str:
    """
    Return the phase of a subscription at ``now``.

    Without a subscription or without usable dates the phase is ``active``: that
    keeps the behaviour of an unknown state identical to the one before phases
    existed. Before ``validFrom`` only a "running" contract is ``active``: Tibber
    has its prices already. Any other status, or none, is ``pending``.
    """
    start = get_subscription_start(subscription)
    if start is not None and start > now and _status(subscription) != "running":
        return PHASE_PENDING
    end = get_subscription_end(subscription)
    if end is not None and end <= now:
        return PHASE_ENDED
    return PHASE_ACTIVE


def has_no_price_yet(subscription: dict[str, Any] | None, now: datetime) -> bool:
    """
    Return True if Tibber cannot have a current price for this subscription.

    While pending or ended, and right at the start while Tibber still reports the
    status "awaiting market": the dates say the contract runs, the API has no price
    for it yet.
    """
    if get_subscription_phase(subscription, now) != PHASE_ACTIVE:
        return True
    return _status(subscription).startswith("awaiting")


def _status(subscription: dict[str, Any] | None) -> str:
    """Return the subscription status in lowercase ("running", "awaiting market", ...), or "" if missing."""
    status = (subscription or {}).get("status")
    return status.lower() if isinstance(status, str) else ""
