"""
Common utilities for planning services (find_best_start, plan_charging).

This module provides shared functionality for:
- Response envelope building
- Window parsing (datetime vs HH:MM)
- Time rounding and normalization
- Currency formatting
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from custom_components.tibber_prices.const import get_currency_info
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# API Version for response envelope
SERVICE_API_VERSION = "0.1"

DEFAULT_HORIZON_HOURS = 36  # Default horizon for planning services (hours)
RESOLUTION_MINUTES = 15  # Resolution in minutes (quarter-hourly)
RESOLUTION_HALF = 8  # Half the resolution for nearest rounding threshold (15/2 rounded up)


@dataclass
class ServiceResponse:
    """Response envelope for planning services."""

    ok: bool = True
    service: str = ""
    version: str = SERVICE_API_VERSION
    generated_at: str = ""
    entry_id: str = ""
    resolution_minutes: int = RESOLUTION_MINUTES
    currency: str = "EUR"
    currency_subunit: str = "ct"
    window_start: str = ""
    window_end: str = ""
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    result: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for service response."""
        return {
            "ok": self.ok,
            "service": self.service,
            "version": self.version,
            "generated_at": self.generated_at,
            "entry_id": self.entry_id,
            "resolution_minutes": self.resolution_minutes,
            "currency": self.currency,
            "currency_subunit": self.currency_subunit,
            "window": {
                "start": self.window_start,
                "end": self.window_end,
            },
            "warnings": self.warnings,
            "errors": self.errors,
            "result": self.result,
        }


@dataclass
class ParsedWindow:
    """Parsed and validated time window."""

    start: datetime
    end: datetime
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def create_response_envelope(
    service_name: str,
    entry_id: str,
    currency: str,
    window_start: datetime,
    window_end: datetime,
) -> ServiceResponse:
    """
    Create a response envelope with common fields.

    Args:
        service_name: Full service name (e.g., "tibber_prices.find_best_start")
        entry_id: Config entry ID
        currency: Currency code (e.g., "EUR")
        window_start: Start of time window
        window_end: End of time window

    Returns:
        ServiceResponse with common fields populated

    """
    _, subunit_symbol, _ = get_currency_info(currency)

    return ServiceResponse(
        service=service_name,
        generated_at=dt_util.now().isoformat(),
        entry_id=entry_id,
        currency=currency,
        currency_subunit=subunit_symbol,
        window_start=window_start.isoformat(),
        window_end=window_end.isoformat(),
    )


def is_hhmm_format(time_str: str) -> bool:
    """
    Check if string is in HH:MM or HH:MM:SS format (time-only, no date).

    The time selector in HA services.yaml returns HH:MM:SS format (e.g., "14:00:00").

    Args:
        time_str: Time string to check

    Returns:
        True if HH:MM or HH:MM:SS format (with optional microseconds), False otherwise

    """
    if not time_str:
        return False
    # Match HH:MM or HH:MM:SS format with optional microseconds
    # Examples: "14:00", "14:00:00", "14:00:00.123456"
    pattern = r"^([01]?[0-9]|2[0-3]):([0-5][0-9])(?::([0-5][0-9])(?:\.(\d+))?)?$"
    return bool(re.match(pattern, time_str.strip()))


def parse_datetime_string(time_str: str) -> datetime | None:
    """
    Parse a datetime string flexibly, accepting many common formats.

    Supports:
    - ISO 8601 with timezone: "2025-12-28T14:00:00+01:00"
    - ISO 8601 with Z: "2025-12-28T14:00:00Z"
    - ISO 8601 without timezone: "2025-12-28T14:00:00"
    - With microseconds: "2025-12-28T14:00:00.123456+01:00"
    - Date with space separator: "2025-12-28 14:00:00"
    - Without seconds: "2025-12-28T14:00" or "2025-12-28 14:00"

    Args:
        time_str: Datetime string in various formats

    Returns:
        Parsed datetime (timezone-aware in HA timezone) or None if unparseable

    """
    if not time_str:
        return None

    time_str = time_str.strip()

    # Replace Z with +00:00 for UTC
    if time_str.endswith("Z"):
        time_str = time_str[:-1] + "+00:00"

    # Replace space with T for ISO compatibility
    # Handle "2025-12-28 14:00:00" format
    if " " in time_str and "T" not in time_str:
        time_str = time_str.replace(" ", "T", 1)

    # Try parsing with fromisoformat (handles most ISO 8601 variants)
    try:
        parsed = datetime.fromisoformat(time_str)
    except ValueError:
        parsed = None

    if parsed is not None:
        # Add timezone if missing
        if parsed.tzinfo is None:
            parsed = dt_util.as_local(parsed)
        return parsed

    # Try additional formats that fromisoformat might not handle
    # Format without seconds: "2025-12-28T14:00"
    try:
        if len(time_str) == 16 and time_str[10] == "T":  # noqa: PLR2004
            parsed = datetime.strptime(time_str, "%Y-%m-%dT%H:%M")  # noqa: DTZ007
            return dt_util.as_local(parsed)
    except ValueError:
        pass

    return None


def parse_hhmm_to_datetime(time_str: str, reference_time: datetime) -> datetime:
    """
    Parse HH:MM or HH:MM:SS string to datetime, finding next occurrence from reference.

    Seconds are ignored as we round to 15-minute boundaries anyway.

    Args:
        time_str: Time in HH:MM or HH:MM:SS format
        reference_time: Reference datetime (typically now)

    Returns:
        Timezone-aware datetime for next occurrence of this time

    """
    parts = time_str.strip().split(":")
    hour = int(parts[0])
    minute = int(parts[1])
    # Ignore seconds if present (parts[2])

    # Create datetime for today with given time
    candidate = reference_time.replace(hour=hour, minute=minute, second=0, microsecond=0)

    # If candidate is in the past, move to next day
    if candidate <= reference_time:
        candidate += timedelta(days=1)

    return candidate


def parse_window(  # noqa: PLR0912, PLR0915
    _hass: HomeAssistant,
    start_input: str | datetime | None,
    end_input: str | datetime | None,
    horizon_hours: int = DEFAULT_HORIZON_HOURS,
    duration_minutes: int | None = None,
) -> ParsedWindow:
    """
    Parse window start/end with automatic format detection.

    Supports:
    - HH:MM or HH:MM:SS format (e.g., "14:00", "14:00:00") - time-only, next occurrence
    - ISO datetime strings with/without timezone (e.g., "2025-12-28T14:00:00+01:00")
    - ISO datetime with Z for UTC (e.g., "2025-12-28T14:00:00Z")
    - Datetime with space separator (e.g., "2025-12-28 14:00:00")
    - With or without microseconds
    - datetime objects

    Args:
        hass: Home Assistant instance
        start_input: Start time (HH:MM, ISO string, datetime, or None for now)
        end_input: End time (HH:MM, ISO string, datetime, or None for horizon)
        horizon_hours: Maximum look-ahead hours (default: 36)
        duration_minutes: Optional duration - if provided and > window, window is extended

    Returns:
        ParsedWindow with start/end datetimes and any warnings/errors

    """
    warnings: list[str] = []
    errors: list[str] = []

    now = dt_util.now()
    horizon_end = now + timedelta(hours=horizon_hours)

    # Parse start
    start: datetime
    start_is_hhmm = False

    if start_input is None:
        start = now
    elif isinstance(start_input, datetime):
        start = start_input
        if start.tzinfo is None:
            start = dt_util.as_local(start)
    elif isinstance(start_input, str):
        if is_hhmm_format(start_input):
            start = parse_hhmm_to_datetime(start_input, now)
            start_is_hhmm = True
        else:
            # Try to parse as datetime string (flexible format)
            parsed = parse_datetime_string(start_input)
            if parsed is not None:
                start = parsed
            else:
                errors.append("invalid_parameters")
                return ParsedWindow(start=now, end=horizon_end, errors=errors)
    else:
        errors.append("invalid_parameters")
        return ParsedWindow(start=now, end=horizon_end, errors=errors)

    # Parse end
    end: datetime
    end_is_hhmm = False

    if end_input is None:
        end = horizon_end
    elif isinstance(end_input, datetime):
        end = end_input
        if end.tzinfo is None:
            end = dt_util.as_local(end)
    elif isinstance(end_input, str):
        if is_hhmm_format(end_input):
            end_is_hhmm = True
            end_parts = end_input.strip().split(":")
            end_hour = int(end_parts[0])
            end_minute = int(end_parts[1])

            # Create end datetime based on start
            end = start.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)

            # Handle midnight wrap logic for HH:MM
            start_time_of_day = start.hour * 60 + start.minute
            end_time_of_day = end_hour * 60 + end_minute

            if end_time_of_day == start_time_of_day:
                # Same time -> +24h
                end += timedelta(days=1)
            elif end_time_of_day < start_time_of_day:
                # End is earlier in day -> wrap to next day
                end += timedelta(days=1)
            # else: end is later same day, keep as-is
        else:
            # Try to parse as datetime string (flexible format)
            parsed = parse_datetime_string(end_input)
            if parsed is not None:
                end = parsed
            else:
                errors.append("invalid_parameters")
                return ParsedWindow(start=start, end=horizon_end, errors=errors)
    else:
        errors.append("invalid_parameters")
        return ParsedWindow(start=start, end=horizon_end, errors=errors)

    # Validate: end < start only allowed for HH:MM (already handled above)
    if end <= start and not (start_is_hhmm and end_is_hhmm):
        errors.append("window_end_before_start")
        return ParsedWindow(start=start, end=end, errors=errors)

    # Check if window extends duration (if provided)
    if duration_minutes is not None:
        window_duration = (end - start).total_seconds() / 60
        if duration_minutes > window_duration:
            # Extend window to fit duration
            extension_minutes = duration_minutes - window_duration
            end = end + timedelta(minutes=extension_minutes)
            warnings.append("window_extended_for_duration")

    # Clamp end to horizon
    if end > horizon_end:
        end = horizon_end
        warnings.append("window_end_clamped_to_horizon")

    return ParsedWindow(start=start, end=end, warnings=warnings, errors=errors)


def round_to_quarter(dt: datetime, mode: str = "ceil") -> datetime:
    """
    Round datetime to 15-minute boundary.

    Args:
        dt: Datetime to round
        mode: "nearest", "floor", or "ceil"

    Returns:
        Rounded datetime

    """
    minute = dt.minute
    quarter = minute // 15

    if mode == "floor":
        new_minute = quarter * 15
    elif mode == "ceil":
        new_minute = minute if minute % 15 == 0 else (quarter + 1) * 15
    else:  # nearest
        remainder = minute % 15
        new_minute = quarter * 15 if remainder < RESOLUTION_HALF else (quarter + 1) * 15

    # Handle hour overflow
    hour_add = new_minute // 60
    new_minute = new_minute % 60

    result = dt.replace(minute=new_minute, second=0, microsecond=0)
    if hour_add:
        result += timedelta(hours=hour_add)

    return result


def format_price(price: float, decimals: int = 4) -> float:
    """Round price to specified decimals."""
    return round(price, decimals)


def price_to_subunit(price_eur: float) -> float:
    """Convert price from main unit to subunit (e.g., EUR to ct)."""
    return round(price_eur * 100, 2)


def get_intervals_in_window(
    all_intervals: list[dict[str, Any]],
    window_start: datetime,
    window_end: datetime,
) -> list[dict[str, Any]]:
    """
    Filter intervals to those within the specified window.

    Args:
        all_intervals: List of all available price intervals
        window_start: Start of window (inclusive)
        window_end: End of window (exclusive)

    Returns:
        List of intervals within window

    """
    result = []
    for interval in all_intervals:
        starts_at = interval.get("startsAt")
        if not starts_at:
            continue

        # Parse interval start time
        interval_start = datetime.fromisoformat(starts_at) if isinstance(starts_at, str) else starts_at

        # Interval is within window if its start is >= window_start and < window_end
        if window_start <= interval_start < window_end:
            result.append(interval)

    return result


def calculate_intervals_needed(duration_minutes: int, rounding: str = "ceil") -> int:
    """
    Calculate number of 15-minute intervals needed for a duration.

    Args:
        duration_minutes: Duration in minutes
        rounding: "nearest", "floor", or "ceil"

    Returns:
        Number of intervals

    """
    exact = duration_minutes / RESOLUTION_MINUTES

    if rounding == "floor":
        return int(exact)
    if rounding == "ceil":
        return int(exact) if exact == int(exact) else int(exact) + 1
    # nearest
    return round(exact)
