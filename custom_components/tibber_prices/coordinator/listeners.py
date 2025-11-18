"""Listener management and scheduling for the coordinator."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers.event import async_track_utc_time_change

from .constants import QUARTER_HOUR_BOUNDARIES

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class ListenerManager:
    """Manages listeners and scheduling for coordinator updates."""

    def __init__(self, hass: HomeAssistant, log_prefix: str) -> None:
        """Initialize the listener manager."""
        self.hass = hass
        self._log_prefix = log_prefix

        # Listener lists
        self._time_sensitive_listeners: list[CALLBACK_TYPE] = []
        self._minute_update_listeners: list[CALLBACK_TYPE] = []

        # Timer cancellation callbacks
        self._quarter_hour_timer_cancel: CALLBACK_TYPE | None = None
        self._minute_timer_cancel: CALLBACK_TYPE | None = None

        # Midnight turnover tracking
        self._last_midnight_check: datetime | None = None

    def _log(self, level: str, message: str, *args: object, **kwargs: object) -> None:
        """Log with coordinator-specific prefix."""
        prefixed_message = f"{self._log_prefix} {message}"
        getattr(_LOGGER, level)(prefixed_message, *args, **kwargs)

    @callback
    def async_add_time_sensitive_listener(self, update_callback: CALLBACK_TYPE) -> CALLBACK_TYPE:
        """
        Listen for time-sensitive updates that occur every quarter-hour.

        Time-sensitive entities (like current_interval_price, next_interval_price, etc.) should use this
        method instead of async_add_listener to receive updates at quarter-hour boundaries.

        Returns:
            Callback that can be used to remove the listener

        """
        self._time_sensitive_listeners.append(update_callback)

        def remove_listener() -> None:
            """Remove update listener."""
            if update_callback in self._time_sensitive_listeners:
                self._time_sensitive_listeners.remove(update_callback)

        return remove_listener

    @callback
    def async_update_time_sensitive_listeners(self) -> None:
        """Update all time-sensitive entities without triggering a full coordinator update."""
        for update_callback in self._time_sensitive_listeners:
            update_callback()

        self._log(
            "debug",
            "Updated %d time-sensitive entities at quarter-hour boundary",
            len(self._time_sensitive_listeners),
        )

    @callback
    def async_add_minute_update_listener(self, update_callback: CALLBACK_TYPE) -> CALLBACK_TYPE:
        """
        Listen for minute-by-minute updates for timing sensors.

        Timing sensors (like best_price_remaining_minutes, peak_price_progress, etc.) should use this
        method to receive updates every minute for accurate countdown/progress tracking.

        Returns:
            Callback that can be used to remove the listener

        """
        self._minute_update_listeners.append(update_callback)

        def remove_listener() -> None:
            """Remove update listener."""
            if update_callback in self._minute_update_listeners:
                self._minute_update_listeners.remove(update_callback)

        return remove_listener

    @callback
    def async_update_minute_listeners(self) -> None:
        """Update all minute-update entities without triggering a full coordinator update."""
        for update_callback in self._minute_update_listeners:
            update_callback()

        self._log(
            "debug",
            "Updated %d minute-update entities",
            len(self._minute_update_listeners),
        )

    def schedule_quarter_hour_refresh(
        self,
        handler_callback: CALLBACK_TYPE,
    ) -> None:
        """Schedule the next quarter-hour entity refresh using Home Assistant's time tracking."""
        # Cancel any existing timer
        if self._quarter_hour_timer_cancel:
            self._quarter_hour_timer_cancel()
            self._quarter_hour_timer_cancel = None

        # Use Home Assistant's async_track_utc_time_change to trigger at quarter-hour boundaries
        # HA may schedule us a few milliseconds before or after the exact boundary (:XX:59.9xx or :00:00.0xx)
        # Our interval detection is robust - uses "starts_at <= target_time < interval_end" check,
        # so we correctly identify the current interval regardless of millisecond timing.
        self._quarter_hour_timer_cancel = async_track_utc_time_change(
            self.hass,
            handler_callback,
            minute=QUARTER_HOUR_BOUNDARIES,
            second=0,  # Trigger at :00, :15, :30, :45 exactly (HA handles scheduling tolerance)
        )

        self._log(
            "debug",
            "Scheduled quarter-hour refresh for boundaries: %s (second=0)",
            QUARTER_HOUR_BOUNDARIES,
        )

    def schedule_minute_refresh(
        self,
        handler_callback: CALLBACK_TYPE,
    ) -> None:
        """Schedule minute-by-minute entity refresh for timing sensors."""
        # Cancel any existing timer
        if self._minute_timer_cancel:
            self._minute_timer_cancel()
            self._minute_timer_cancel = None

        # Use Home Assistant's async_track_utc_time_change to trigger every minute
        # HA may schedule us a few milliseconds before/after the exact minute boundary.
        # Our timing calculations are based on dt_util.now() which gives the actual current time,
        # so small scheduling variations don't affect accuracy.
        self._minute_timer_cancel = async_track_utc_time_change(
            self.hass,
            handler_callback,
            second=0,  # Trigger at :XX:00 (HA handles scheduling tolerance)
        )

        self._log(
            "debug",
            "Scheduled minute-by-minute refresh for timing sensors (second=0)",
        )

    def check_midnight_crossed(self, now: datetime) -> bool:
        """
        Check if midnight has passed since last check.

        Args:
            now: Current datetime

        Returns:
            True if midnight has been crossed, False otherwise

        """
        current_date = now.date()

        # First time check - initialize
        if self._last_midnight_check is None:
            self._last_midnight_check = now
            return False

        last_check_date = self._last_midnight_check.date()

        # Check if we've crossed into a new day
        if current_date > last_check_date:
            self._log(
                "debug",
                "Midnight crossed: last_check=%s, current=%s",
                last_check_date,
                current_date,
            )
            self._last_midnight_check = now
            return True

        self._last_midnight_check = now
        return False

    def cancel_timers(self) -> None:
        """Cancel all scheduled timers."""
        if self._quarter_hour_timer_cancel:
            self._quarter_hour_timer_cancel()
            self._quarter_hour_timer_cancel = None
        if self._minute_timer_cancel:
            self._minute_timer_cancel()
            self._minute_timer_cancel = None
