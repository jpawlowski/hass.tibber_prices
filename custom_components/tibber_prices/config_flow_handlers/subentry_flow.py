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
from homeassistant.config_entries import ConfigSubentryFlow, SubentryFlowResult
from homeassistant.helpers.selector import (
    DurationSelector,
    DurationSelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)


class TibberPricesSubentryFlowHandler(ConfigSubentryFlow):
    """Handle subentry flows for tibber_prices (time-travel views)."""

    def __init__(self) -> None:
        """Initialize the subentry flow handler."""
        super().__init__()
        self._selected_parent_entry_id: str | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Step 1: Select which config entry should get a time-travel subentry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._selected_parent_entry_id = user_input["parent_entry_id"]
            return await self.async_step_time_offset()

        # Get all main config entries (not subentries)
        # Subentries have "_hist_" in their unique_id
        main_entries = [
            entry
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if entry.unique_id and "_hist_" not in entry.unique_id
        ]

        if not main_entries:
            return self.async_abort(reason="no_main_entries")

        # Build options for entry selection
        entry_options = [
            SelectOptionDict(
                value=entry.entry_id,
                label=f"{entry.title} ({entry.data.get('user_login', 'N/A')})",
            )
            for entry in main_entries
        ]

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("parent_entry_id"): SelectSelector(
                        SelectSelectorConfig(
                            options=entry_options,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
            description_placeholders={},
            errors=errors,
        )

    async def async_step_time_offset(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Step 2: Configure time offset for the time-travel view."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Extract values (convert days to int to avoid float from slider)
            offset_days = int(user_input.get(CONF_VIRTUAL_TIME_OFFSET_DAYS, 0))

            # DurationSelector returns dict with 'hours', 'minutes', and 'seconds' keys
            # We normalize to minute precision (ignore seconds)
            time_offset = user_input.get("time_offset", {})
            offset_hours = -abs(int(time_offset.get("hours", 0)))  # Always negative for historical data
            offset_minutes = -abs(int(time_offset.get("minutes", 0)))  # Always negative for historical data
            # Note: Seconds are ignored - we only support minute-level precision

            # Validate that at least one offset is negative (historical data only)
            if offset_days >= 0 and offset_hours >= 0 and offset_minutes >= 0:
                errors["base"] = "no_time_offset"

            if not errors:
                # Get parent entry
                if not self._selected_parent_entry_id:
                    return self.async_abort(reason="parent_entry_not_found")

                parent_entry = self.hass.config_entries.async_get_entry(self._selected_parent_entry_id)
                if not parent_entry:
                    return self.async_abort(reason="parent_entry_not_found")

                # Get home data from parent entry
                home_id = parent_entry.data.get("home_id")
                home_data = parent_entry.data.get("home_data", {})
                user_login = parent_entry.data.get("user_login", "N/A")

                # Build unique_id with time offset signature
                offset_str = f"d{offset_days}h{offset_hours}m{offset_minutes}"
                user_id = parent_entry.unique_id.split("_")[0] if parent_entry.unique_id else home_id
                unique_id = f"{user_id}_{home_id}_hist_{offset_str}"

                # Check if this exact time offset already exists
                for entry in self.hass.config_entries.async_entries(DOMAIN):
                    if entry.unique_id == unique_id:
                        return self.async_abort(reason="already_configured")

                # No duplicate found - create the entry
                offset_desc = self._format_offset_description(offset_days, offset_hours, offset_minutes)
                subentry_title = f"{parent_entry.title} ({offset_desc})"

                return self.async_create_entry(
                    title=subentry_title,
                    data={
                        "home_id": home_id,
                        "home_data": home_data,
                        "user_login": user_login,
                        CONF_VIRTUAL_TIME_OFFSET_DAYS: offset_days,
                        CONF_VIRTUAL_TIME_OFFSET_HOURS: offset_hours,
                        CONF_VIRTUAL_TIME_OFFSET_MINUTES: offset_minutes,
                    },
                    description=f"Time-travel view: {offset_desc}",
                    description_placeholders={"offset": offset_desc},
                    unique_id=unique_id,
                )

        return self.async_show_form(
            step_id="time_offset",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_VIRTUAL_TIME_OFFSET_DAYS, default=0): NumberSelector(
                        NumberSelectorConfig(
                            mode=NumberSelectorMode.SLIDER,
                            min=-374,
                            max=0,
                            step=1,
                        )
                    ),
                    vol.Optional("time_offset", default={"hours": 0, "minutes": 0}): DurationSelector(
                        DurationSelectorConfig(
                            allow_negative=False,  # We handle sign automatically
                            enable_day=False,  # Days are handled by the slider above
                        )
                    ),
                }
            ),
            description_placeholders={},
            errors=errors,
        )

    def _format_offset_description(self, days: int, hours: int, minutes: int) -> str:
        """
        Format time offset into human-readable description.

        Examples:
            -7, 0, 0 -> "7 days ago" (English) / "vor 7 Tagen" (German)
            0, -2, 0 -> "2 hours ago" (English) / "vor 2 Stunden" (German)
            -7, -2, -30 -> "7 days - 02:30" (compact format when time is added)

        """
        # Get translations loaded by Home Assistant
        standard_translations_key = f"{DOMAIN}_standard_translations_{self.hass.config.language}"
        translations = self.hass.data.get(standard_translations_key, {})
        time_units = translations.get("common", {}).get("time_units", {})

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

    async def async_step_init(self, user_input: dict | None = None) -> SubentryFlowResult:
        """Manage the options for an existing subentry (time-travel settings)."""
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}

        if user_input is not None:
            # Extract values (convert days to int to avoid float from slider)
            offset_days = int(user_input.get(CONF_VIRTUAL_TIME_OFFSET_DAYS, 0))

            # DurationSelector returns dict with 'hours', 'minutes', and 'seconds' keys
            # We normalize to minute precision (ignore seconds)
            time_offset = user_input.get("time_offset", {})
            offset_hours = -abs(int(time_offset.get("hours", 0)))  # Always negative for historical data
            offset_minutes = -abs(int(time_offset.get("minutes", 0)))  # Always negative for historical data
            # Note: Seconds are ignored - we only support minute-level precision

            # Validate that at least one offset is negative (historical data only)
            if offset_days >= 0 and offset_hours >= 0 and offset_minutes >= 0:
                errors["base"] = "no_time_offset"
            else:
                # Get parent entry to extract home_id and user_id
                parent_entry = self._get_entry()
                home_id = parent_entry.data.get("home_id")

                # Build new unique_id with updated offset signature
                offset_str = f"d{offset_days}h{offset_hours}m{offset_minutes}"
                user_id = parent_entry.unique_id.split("_")[0] if parent_entry.unique_id else home_id
                new_unique_id = f"{user_id}_{home_id}_hist_{offset_str}"

                # Generate new title with updated offset description
                offset_desc = self._format_offset_description(offset_days, offset_hours, offset_minutes)
                # Extract parent title (remove old offset description in parentheses)
                parent_title = parent_entry.title.split(" (")[0] if " (" in parent_entry.title else parent_entry.title
                new_title = f"{parent_title} ({offset_desc})"

                return self.async_update_and_abort(
                    parent_entry,
                    subentry,
                    unique_id=new_unique_id,
                    title=new_title,
                    data_updates=user_input,
                )

        offset_days = subentry.data.get(CONF_VIRTUAL_TIME_OFFSET_DAYS, 0)
        offset_hours = subentry.data.get(CONF_VIRTUAL_TIME_OFFSET_HOURS, 0)
        offset_minutes = subentry.data.get(CONF_VIRTUAL_TIME_OFFSET_MINUTES, 0)

        # Prepare time offset dict for DurationSelector (always positive, we negate on save)
        time_offset_dict = {"hours": 0, "minutes": 0}  # Default to zeros
        if offset_hours != 0:
            time_offset_dict["hours"] = abs(offset_hours)
        if offset_minutes != 0:
            time_offset_dict["minutes"] = abs(offset_minutes)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_VIRTUAL_TIME_OFFSET_DAYS, default=offset_days): NumberSelector(
                        NumberSelectorConfig(
                            mode=NumberSelectorMode.SLIDER,
                            min=-374,
                            max=0,
                            step=1,
                        )
                    ),
                    vol.Optional("time_offset", default=time_offset_dict): DurationSelector(
                        DurationSelectorConfig(
                            allow_negative=False,  # We handle sign automatically
                            enable_day=False,  # Days are handled by the slider above
                        )
                    ),
                }
            ),
            errors=errors,
        )
