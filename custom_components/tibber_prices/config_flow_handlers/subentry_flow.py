"""Subentry config flow for creating time-travel views."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, NamedTuple

import voluptuous as vol

from custom_components.tibber_prices.const import (
    CONF_HEADLESS,
    CONF_REALISTIC_TOMORROW,
    CONF_TOMORROW_ARRIVAL_HOUR,
    CONF_VIRTUAL_TIME_OFFSET_DAYS,
    CONF_VIRTUAL_TIME_OFFSET_HOURS,
    CONF_VIRTUAL_TIME_OFFSET_MINUTES,
    CONF_VIRTUAL_TIME_OFFSET_MODE,
    CONF_VIRTUAL_TIME_OFFSET_YEARS,
    DEFAULT_HEADLESS,
    DEFAULT_REALISTIC_TOMORROW,
    DEFAULT_TOMORROW_ARRIVAL_HOUR,
    DOMAIN,
)
from custom_components.tibber_prices.time_travel import (
    MODE_DAYS,
    MODE_YEARLY,
    QUARTER_HOURLY_SINCE,
    build_time_shift,
    max_selectable_days,
    max_selectable_years,
)
from homeassistant.config_entries import ConfigSubentryFlow, SubentryFlowResult
from homeassistant.helpers.selector import (
    BooleanSelector,
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
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

# Form key of the hours/minutes duration input (not persisted as-is: it is
# normalized into the CONF_VIRTUAL_TIME_OFFSET_* keys before storing).
CONF_TIME_OFFSET = "time_offset"


class TibberPricesSubentryFlowHandler(ConfigSubentryFlow):
    """
    Handle subentry flows for tibber_prices (time-travel views).

    The flow is already scoped to a config entry - `self._get_entry()` returns
    the home the view belongs to, so there is nothing to pick. Creation asks for
    the offset mode first (days vs. same date in an earlier year), then for the
    offset itself and the view's behaviour; reconfigure jumps straight to the
    latter, keeping the mode fixed so the view keeps its identity.
    """

    def __init__(self) -> None:
        """Initialize the flow."""
        super().__init__()
        self._mode: str = MODE_DAYS

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Pick the offset mode for a new time-travel view."""
        today = dt_util.now().date()
        years_available = max_selectable_years(today)

        if user_input is not None:
            self._mode = user_input[CONF_VIRTUAL_TIME_OFFSET_MODE]
            return await self.async_step_offset()

        if not years_available:
            # Yearly mode needs a full year of quarter-hourly data behind it.
            # Until then it can only produce unavailable entities, so skip the
            # choice entirely rather than offering a dead end.
            self._mode = MODE_DAYS
            return await self.async_step_offset()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_VIRTUAL_TIME_OFFSET_MODE, default=MODE_DAYS): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=MODE_DAYS, label="days"),
                                SelectOptionDict(value=MODE_YEARLY, label="yearly"),
                            ],
                            mode=SelectSelectorMode.LIST,
                            translation_key="offset_mode",
                        )
                    ),
                }
            ),
        )

    async def async_step_offset(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Configure the offset and behaviour of a new time-travel view."""
        parent_entry = self._get_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            offsets = _normalize_offset(user_input, self._mode)
            errors = self._validate(offsets)

            if not errors:
                unique_id = self._build_unique_id(parent_entry, offsets)
                if any(subentry.unique_id == unique_id for subentry in parent_entry.subentries.values()):
                    return self.async_abort(reason="already_configured")

                data = _build_data(offsets, self._mode, user_input)
                title = self._build_title(parent_entry, data)
                return self.async_create_entry(
                    title=title,
                    data=data,
                    description=f"Time-travel view: {title}",
                    description_placeholders={"offset": title},
                    unique_id=unique_id,
                )

        return self.async_show_form(
            step_id="offset",
            data_schema=self._offset_schema(),
            errors=errors,
            description_placeholders=self._placeholders(),
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Update an existing time-travel view."""
        parent_entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        self._mode = MODE_YEARLY if subentry.data.get(CONF_VIRTUAL_TIME_OFFSET_MODE) == MODE_YEARLY else MODE_DAYS
        errors: dict[str, str] = {}

        if user_input is not None:
            offsets = _normalize_offset(user_input, self._mode)
            errors = self._validate(offsets)

            if not errors:
                unique_id = self._build_unique_id(parent_entry, offsets)
                clashes = any(
                    other.unique_id == unique_id and other.subentry_id != subentry.subentry_id
                    for other in parent_entry.subentries.values()
                )
                if clashes:
                    return self.async_abort(reason="already_configured")

                # Store the normalized offset, not the raw form input - the form
                # carries a duration dict that the coordinator cannot read.
                data = _build_data(offsets, self._mode, user_input)
                return self.async_update_and_abort(
                    parent_entry,
                    subentry,
                    unique_id=unique_id,
                    title=self._build_title(parent_entry, data),
                    data_updates=data,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._offset_schema(subentry.data),
            errors=errors,
            description_placeholders=self._placeholders(),
        )

    def _validate(self, offsets: _Offsets) -> dict[str, str]:
        """
        Check that the requested offset points at a usable date.

        Returns:
            Field errors, empty when the offset is fine.

        """
        shift = build_time_shift(
            {
                CONF_VIRTUAL_TIME_OFFSET_MODE: self._mode,
                CONF_VIRTUAL_TIME_OFFSET_DAYS: offsets.days,
                CONF_VIRTUAL_TIME_OFFSET_YEARS: offsets.years,
                CONF_VIRTUAL_TIME_OFFSET_HOURS: offsets.hours,
                CONF_VIRTUAL_TIME_OFFSET_MINUTES: offsets.minutes,
            }
        )

        if shift.is_live:
            return {"base": "no_time_offset"}
        if not shift.has_data_coverage(dt_util.now()):
            return {"base": "before_quarter_hourly"}
        return {}

    def _offset_schema(self, current: Any = None) -> vol.Schema:
        """Build the offset form for the active mode, pre-filled from current data."""
        data = current or {}
        today = dt_util.now().date()

        if self._mode == MODE_YEARLY:
            primary = {
                vol.Required(
                    CONF_VIRTUAL_TIME_OFFSET_YEARS,
                    default=int(data.get(CONF_VIRTUAL_TIME_OFFSET_YEARS, -1)),
                ): NumberSelector(
                    NumberSelectorConfig(
                        mode=NumberSelectorMode.SLIDER,
                        min=-max_selectable_years(today),
                        max=-1,
                        step=1,
                    )
                )
            }
        else:
            primary = {
                vol.Required(
                    CONF_VIRTUAL_TIME_OFFSET_DAYS,
                    default=int(data.get(CONF_VIRTUAL_TIME_OFFSET_DAYS, 0)),
                ): NumberSelector(
                    NumberSelectorConfig(
                        mode=NumberSelectorMode.SLIDER,
                        # Shrinks to what Tibber actually has quarter-hourly data for.
                        min=-max_selectable_days(today),
                        max=0,
                        step=1,
                    )
                )
            }

        return vol.Schema(
            {
                **primary,
                # DurationSelector cannot express negative values, so it always
                # shows the magnitude and the sign is applied on save.
                vol.Optional(
                    CONF_TIME_OFFSET,
                    default={
                        "hours": abs(int(data.get(CONF_VIRTUAL_TIME_OFFSET_HOURS, 0))),
                        "minutes": abs(int(data.get(CONF_VIRTUAL_TIME_OFFSET_MINUTES, 0))),
                    },
                ): DurationSelector(
                    DurationSelectorConfig(
                        allow_negative=False,
                        enable_day=False,  # Days are handled by the slider above
                    )
                ),
                vol.Optional(
                    CONF_REALISTIC_TOMORROW,
                    default=bool(data.get(CONF_REALISTIC_TOMORROW, DEFAULT_REALISTIC_TOMORROW)),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_TOMORROW_ARRIVAL_HOUR,
                    default=int(data.get(CONF_TOMORROW_ARRIVAL_HOUR, DEFAULT_TOMORROW_ARRIVAL_HOUR)),
                ): NumberSelector(
                    NumberSelectorConfig(
                        mode=NumberSelectorMode.BOX,
                        min=0,
                        max=23,
                        step=1,
                    )
                ),
                vol.Optional(
                    CONF_HEADLESS,
                    default=bool(data.get(CONF_HEADLESS, DEFAULT_HEADLESS)),
                ): BooleanSelector(),
            }
        )

    def _placeholders(self) -> dict[str, str]:
        """Provide context for the form description."""
        today = dt_util.now().date()
        return {
            "earliest_date": QUARTER_HOURLY_SINCE.isoformat(),
            "max_days": str(max_selectable_days(today)),
            "max_years": str(max_selectable_years(today)),
        }

    def _build_unique_id(self, parent_entry: ConfigEntry, offsets: _Offsets) -> str:
        """Build a unique ID identifying this home plus offset combination."""
        home_id = parent_entry.data.get("home_id", "")
        user_id = parent_entry.unique_id.split("_")[0] if parent_entry.unique_id else home_id
        primary = f"y{offsets.years}" if self._mode == MODE_YEARLY else f"d{offsets.days}"
        return f"{user_id}_{home_id}_hist_{primary}h{offsets.hours}m{offsets.minutes}"

    def _build_title(self, parent_entry: ConfigEntry, data: dict[str, Any]) -> str:
        """Build the view title: home name, offset description, headless marker."""
        description = self._format_offset_description(data)
        title = f"{_base_title(parent_entry)} ({description})"
        if data.get(CONF_HEADLESS):
            title = f"{title} [headless]"
        return title

    def _format_offset_description(self, data: dict[str, Any]) -> str:
        """
        Format the configured offset into a human-readable description.

        Examples:
            -7 days -> "7 days ago" (English) / "vor 7 Tagen" (German)
            -2 hours -> "2 hours ago" (English) / "vor 2 Stunden" (German)
            -7 days -02:30 -> "7 days - 02:30" (compact format when time is added)

        """
        time_units = self._time_units()

        years = int(data.get(CONF_VIRTUAL_TIME_OFFSET_YEARS, 0))
        days = int(data.get(CONF_VIRTUAL_TIME_OFFSET_DAYS, 0))
        hours = int(data.get(CONF_VIRTUAL_TIME_OFFSET_HOURS, 0))
        minutes = int(data.get(CONF_VIRTUAL_TIME_OFFSET_MINUTES, 0))

        is_yearly = data.get(CONF_VIRTUAL_TIME_OFFSET_MODE) == MODE_YEARLY
        primary_count = abs(years) if is_yearly else abs(days)
        primary_unit = (
            ("years" if primary_count != 1 else "year") if is_yearly else ("days" if primary_count != 1 else "day")
        )
        has_time = hours != 0 or minutes != 0

        if primary_count and has_time:
            # Compact format: "7 days - 02:30"
            primary_part = time_units[primary_unit].format(count=primary_count)
            return f"{primary_part} - {abs(hours):02d}:{abs(minutes):02d}"

        parts = []
        if primary_count:
            parts.append(time_units[primary_unit].format(count=primary_count))
        if hours:
            parts.append(time_units["hours" if abs(hours) != 1 else "hour"].format(count=abs(hours)))
        if minutes:
            parts.append(time_units["minutes" if abs(minutes) != 1 else "minute"].format(count=abs(minutes)))

        if not parts:
            return time_units.get("now", "now")

        # All offsets are negative (historical data only)
        return time_units["ago"].format(parts=" ".join(parts))

    def _time_units(self) -> dict[str, str]:
        """Return the localized time unit templates, falling back to English."""
        translations_key = f"{DOMAIN}_translations_{self.hass.config.language}"
        translations = self.hass.data.get(translations_key, {})
        time_units = dict(translations.get("time_units", {}))

        defaults = {
            "day": "{count} day",
            "days": "{count} days",
            "hour": "{count} hour",
            "hours": "{count} hours",
            "minute": "{count} minute",
            "minutes": "{count} minutes",
            "year": "{count} year",
            "years": "{count} years",
            "ago": "{parts} ago",
            "now": "now",
        }
        for key, value in defaults.items():
            time_units.setdefault(key, value)
        return time_units


class _Offsets(NamedTuple):
    """Normalized (never positive) offset components."""

    days: int
    years: int
    hours: int
    minutes: int


def _normalize_offset(user_input: dict[str, Any], mode: str) -> _Offsets:
    """
    Normalize form input into negative offset components.

    Only historical data exists, so every component is forced negative. Seconds
    from the duration selector are ignored - the integration works on 15-minute
    intervals and minute precision is already more than enough. The component
    that does not belong to the active mode is zeroed so it cannot linger in
    storage after a mode change.
    """
    time_offset = user_input.get(CONF_TIME_OFFSET) or {}
    days = -abs(int(user_input.get(CONF_VIRTUAL_TIME_OFFSET_DAYS, 0)))
    years = -abs(int(user_input.get(CONF_VIRTUAL_TIME_OFFSET_YEARS, 0)))
    return _Offsets(
        days=0 if mode == MODE_YEARLY else days,
        years=years if mode == MODE_YEARLY else 0,
        hours=-abs(int(time_offset.get("hours", 0))),
        minutes=-abs(int(time_offset.get("minutes", 0))),
    )


def _build_data(offsets: _Offsets, mode: str, user_input: dict[str, Any]) -> dict[str, Any]:
    """Build the subentry data payload from normalized offsets and form input."""
    return {
        CONF_VIRTUAL_TIME_OFFSET_MODE: mode,
        CONF_VIRTUAL_TIME_OFFSET_DAYS: offsets.days,
        CONF_VIRTUAL_TIME_OFFSET_YEARS: offsets.years,
        CONF_VIRTUAL_TIME_OFFSET_HOURS: offsets.hours,
        CONF_VIRTUAL_TIME_OFFSET_MINUTES: offsets.minutes,
        CONF_REALISTIC_TOMORROW: bool(user_input.get(CONF_REALISTIC_TOMORROW, DEFAULT_REALISTIC_TOMORROW)),
        CONF_TOMORROW_ARRIVAL_HOUR: int(user_input.get(CONF_TOMORROW_ARRIVAL_HOUR, DEFAULT_TOMORROW_ARRIVAL_HOUR)),
        CONF_HEADLESS: bool(user_input.get(CONF_HEADLESS, DEFAULT_HEADLESS)),
    }


def _base_title(parent_entry: ConfigEntry) -> str:
    """Return the parent entry title without any trailing "(...)" suffix."""
    return parent_entry.title.split(" (")[0] if " (" in parent_entry.title else parent_entry.title
