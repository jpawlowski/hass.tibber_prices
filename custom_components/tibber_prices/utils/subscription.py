"""
Subscription phase helpers.

A Tibber contract can be set up before it starts and keeps its data after it
ended. The integration treats the three phases differently:

* ``pending``: ``validFrom`` lies in the future. Tibber returns no prices yet
  (``priceInfo.current`` is null, ``today``/``tomorrow`` are empty), so nothing
  is fetched and only the entities that need no prices exist.
* ``active``: the normal case, also assumed when the dates are unknown.
* ``ended``: ``validTo`` has passed. The clock of the entities stops on the
  last day of the contract (see ``get_subscription_last_interval_start``).

Pure functions, no Home Assistant dependencies.
"""

from __future__ import annotations

from datetime import datetime, timedelta
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
    """Parse an ISO timestamp from the API; naive or malformed values count as unknown."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


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
    existed.
    """
    start = get_subscription_start(subscription)
    if start is not None and start > now:
        return PHASE_PENDING
    end = get_subscription_end(subscription)
    if end is not None and end <= now:
        return PHASE_ENDED
    return PHASE_ACTIVE
