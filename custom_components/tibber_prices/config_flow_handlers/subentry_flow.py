"""Subentry config flow for creating time-travel views."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from custom_components.tibber_prices.const import (
    CONF_VIRTUAL_TIME_OFFSET_DAYS,
    CONF_VIRTUAL_TIME_OFFSET_HOURS,
    CONF_VIRTUAL_TIME_OFFSET_MINUTES,
    DOMAIN,
)
from custom_components.tibber_prices.time_travel import MAX_OFFSET_DAYS
from homeassistant.config_entries import ConfigEntry, ConfigSubentryFlow, SubentryFlowResult
from homeassistant.helpers.selector import (
    DurationSelector,
    DurationSelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

# Form key of the hours/minutes duration input (not persisted as-is: it is
# normalized into the CONF_VIRTUAL_TIME_OFFSET_* keys before storing).
CONF_TIME_OFFSET = "time_offset"


class TibberPricesSubentryFlowHandler(ConfigSubentryFlow):
    """
    Handle subentry flows for tibber_prices (time-travel views).

    The flow is already scoped to a config entry - `self._get_entry()` returns
    the home the view belongs to, so there is nothing to pick: both the creation
    step and the reconfigure step only ask for the time offset.
    """

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Create a time-travel view for this config entry."""
        parent_entry = self._get_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            offset_days, offset_hours, offset_minutes = _normalize_offset(user_input)

            if not _has_offset(offset_days, offset_hours, offset_minutes):
                errors["base"] = "no_time_offset"
            else:
                unique_id = self._build_unique_id(parent_entry, offset_days, offset_hours, offset_minutes)
                if any(subentry.unique_id == unique_id for subentry in parent_entry.subentries.values()):
                    return self.async_abort(reason="already_configured")

                offset_desc = self._format_offset_description(offset_days, offset_hours, offset_minutes)
                return self.async_create_entry(
                    title=f"{_base_title(parent_entry)} ({offset_desc})",
                    data={
                        CONF_VIRTUAL_TIME_OFFSET_DAYS: offset_days,
                        CONF_VIRTUAL_TIME_OFFSET_HOURS: offset_hours,
                        CONF_VIRTUAL_TIME_OFFSET_MINUTES: offset_minutes,
                    },
                    description=f"Time-travel view: {offset_desc}",
                    description_placeholders={"offset": offset_desc},
                    unique_id=unique_id,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_offset_schema(),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Update the time offset of an existing time-travel view."""
        parent_entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}

        if user_input is not None:
            offset_days, offset_hours, offset_minutes = _normalize_offset(user_input)

            if not _has_offset(offset_days, offset_hours, offset_minutes):
                errors["base"] = "no_time_offset"
            else:
                unique_id = self._build_unique_id(parent_entry, offset_days, offset_hours, offset_minutes)
                clashes = any(
                    other.unique_id == unique_id and other.subentry_id != subentry.subentry_id
                    for other in parent_entry.subentries.values()
                )
                if clashes:
                    return self.async_abort(reason="already_configured")

                offset_desc = self._format_offset_description(offset_days, offset_hours, offset_minutes)
                # Store the normalized offset, not the raw form input - the form
                # carries a duration dict that the coordinator cannot read.
                return self.async_update_and_abort(
                    parent_entry,
                    subentry,
                    unique_id=unique_id,
                    title=f"{_base_title(parent_entry)} ({offset_desc})",
                    data_updates={
                        CONF_VIRTUAL_TIME_OFFSET_DAYS: offset_days,
                        CONF_VIRTUAL_TIME_OFFSET_HOURS: offset_hours,
                        CONF_VIRTUAL_TIME_OFFSET_MINUTES: offset_minutes,
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_offset_schema(
                days=int(subentry.data.get(CONF_VIRTUAL_TIME_OFFSET_DAYS, 0)),
                hours=int(subentry.data.get(CONF_VIRTUAL_TIME_OFFSET_HOURS, 0)),
                minutes=int(subentry.data.get(CONF_VIRTUAL_TIME_OFFSET_MINUTES, 0)),
            ),
            errors=errors,
        )

    def _build_unique_id(self, parent_entry: ConfigEntry, days: int, hours: int, minutes: int) -> str:
        """Build a unique ID identifying this home plus offset combination."""
        home_id = parent_entry.data.get("home_id", "")
        user_id = parent_entry.unique_id.split("_")[0] if parent_entry.unique_id else home_id
        return f"{user_id}_{home_id}_hist_d{days}h{hours}m{minutes}"

    def _format_offset_description(self, days: int, hours: int, minutes: int) -> str:
        """
        Format time offset into human-readable description.

        Examples:
            -7, 0, 0 -> "7 days ago" (English) / "vor 7 Tagen" (German)
            0, -2, 0 -> "2 hours ago" (English) / "vor 2 Stunden" (German)
            -7, -2, -30 -> "7 days - 02:30" (compact format when time is added)

        """
        # Get translations from custom_translations (loaded via async_load_translations)
        translations_key = f"{DOMAIN}_translations_{self.hass.config.language}"
        translations = self.hass.data.get(translations_key, {})
        time_units = translations.get("time_units", {})

        # Fallback to English if translations not available
        if not time_units:
            time_units = {
                "day": "{count} day",
                "days": "{count} days",
                "hour": "{count} hour",
                "hours": "{count} hours",
                "minute": "{count} minute",
                "minutes": "{count} minutes",
                "ago": "{parts} ago",
                "now": "now",
            }

        # Check if we have hours or minutes (need compact format)
        has_time = hours != 0 or minutes != 0

        if days != 0 and has_time:
            # Compact format: "7 days - 02:30"
            count = abs(days)
            unit_key = "days" if count != 1 else "day"
            day_part = time_units[unit_key].format(count=count)
            time_part = f"{abs(hours):02d}:{abs(minutes):02d}"
            return f"{day_part} - {time_part}"

        # Standard format: separate parts with spaces
        parts = []

        if days != 0:
            count = abs(days)
            unit_key = "days" if count != 1 else "day"
            parts.append(time_units[unit_key].format(count=count))

        if hours != 0:
            count = abs(hours)
            unit_key = "hours" if count != 1 else "hour"
            parts.append(time_units[unit_key].format(count=count))

        if minutes != 0:
            count = abs(minutes)
            unit_key = "minutes" if count != 1 else "minute"
            parts.append(time_units[unit_key].format(count=count))

        if not parts:
            return time_units.get("now", "now")

        # All offsets should be negative (historical data only)
        # Join parts with space and apply "ago" template
        return time_units["ago"].format(parts=" ".join(parts))


def _offset_schema(days: int = 0, hours: int = 0, minutes: int = 0) -> vol.Schema:
    """Build the offset form, pre-filled with the given (negative) offset."""
    return vol.Schema(
        {
            vol.Required(CONF_VIRTUAL_TIME_OFFSET_DAYS, default=days): NumberSelector(
                NumberSelectorConfig(
                    mode=NumberSelectorMode.SLIDER,
                    min=-MAX_OFFSET_DAYS,
                    max=0,
                    step=1,
                )
            ),
            # DurationSelector cannot express negative values, so it always shows
            # the magnitude and the sign is applied on save.
            vol.Optional(
                CONF_TIME_OFFSET,
                default={"hours": abs(hours), "minutes": abs(minutes)},
            ): DurationSelector(
                DurationSelectorConfig(
                    allow_negative=False,
                    enable_day=False,  # Days are handled by the slider above
                )
            ),
        }
    )


def _normalize_offset(user_input: dict[str, Any]) -> tuple[int, int, int]:
    """
    Normalize form input into a (days, hours, minutes) triple of negative values.

    Only historical data exists, so every component is forced negative. Seconds
    from the duration selector are ignored - the integration works on 15-minute
    intervals and minute precision is already more than enough.
    """
    time_offset = user_input.get(CONF_TIME_OFFSET) or {}
    return (
        -abs(int(user_input.get(CONF_VIRTUAL_TIME_OFFSET_DAYS, 0))),
        -abs(int(time_offset.get("hours", 0))),
        -abs(int(time_offset.get("minutes", 0))),
    )


def _has_offset(days: int, hours: int, minutes: int) -> bool:
    """Return True if the offset actually travels back in time."""
    return bool(days or hours or minutes)


def _base_title(parent_entry: ConfigEntry) -> str:
    """Return the parent entry title without any trailing "(...)" suffix."""
    return parent_entry.title.split(" (")[0] if " (" in parent_entry.title else parent_entry.title
