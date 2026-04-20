"""
Entity reference resolution for service parameters.

Allows service parameters to accept Home Assistant entity IDs instead of
literal values. The entity's current state (or a specific attribute) is
resolved at call time and converted to the expected parameter type.

Syntax:
    "sensor.washing_duration"              → uses entity state
    "sensor.washing_duration@run_minutes"  → uses entity attribute

Supported target types: int, float, datetime, timedelta, time.

Usage in schemas:
    vol.Required("duration"): or_entity_ref(
        vol.All(cv.positive_time_period, vol.Range(...))
    ),

Usage in handlers:
    data, resolved = resolve_entity_references(hass, call.data, PARAM_TYPES)
    # 'data' is a mutable dict with entity refs replaced by resolved values
    # 'resolved' is a dict of resolution details for the response

"""

from __future__ import annotations

from datetime import datetime, time as dt_time, timedelta
import re
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from custom_components.tibber_prices.const import DOMAIN
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# Entity ID pattern: domain.object_id with optional @attribute
# domain: lowercase letters + underscores, must start with letter
# object_id: lowercase letters, digits, underscores
# attribute: anything after @ (HA attributes can have varied names)
_ENTITY_REF_RE = re.compile(
    r"^([a-z][a-z0-9_]*\.[a-z0-9_]+)"  # entity_id
    r"(?:@(.+))?$",  # optional @attribute
)


def is_entity_reference(value: Any) -> bool:
    """Check if a value looks like an entity reference."""
    return isinstance(value, str) and _ENTITY_REF_RE.match(value) is not None


def _validate_entity_ref(value: Any) -> str:
    """Voluptuous validator: accepts entity reference strings."""
    if not isinstance(value, str):
        raise vol.Invalid("Entity reference must be a string")
    if not _ENTITY_REF_RE.match(value):
        raise vol.Invalid(f"Not a valid entity reference: {value}")
    return value


def or_entity_ref(validator: Any) -> vol.Any:
    """Wrap a voluptuous validator to also accept entity references.

    The schema will first try the original validator (for literal values),
    then fall back to accepting an entity reference string.

    Example:
        vol.Required("duration"): or_entity_ref(
            vol.All(cv.positive_time_period, vol.Range(min=timedelta(minutes=1)))
        ),
    """
    return vol.Any(validator, _validate_entity_ref)


def _resolve_raw_value(hass: HomeAssistant, ref: str) -> tuple[str, str, str | None]:
    """Resolve an entity reference to its raw string value.

    Returns:
        Tuple of (raw_value, entity_id, attribute_name_or_none).

    Raises:
        ServiceValidationError: If entity not found, attribute missing, or state unavailable.

    """
    match = _ENTITY_REF_RE.match(ref)
    if not match:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_entity_reference",
            translation_placeholders={"reference": ref},
        )

    entity_id = match.group(1)
    attribute = match.group(2)

    state_obj = hass.states.get(entity_id)
    if state_obj is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entity_not_found",
            translation_placeholders={"entity_id": entity_id},
        )

    if attribute:
        if attribute not in state_obj.attributes:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="entity_attribute_not_found",
                translation_placeholders={"entity_id": entity_id, "attribute": attribute},
            )
        raw = state_obj.attributes[attribute]
    else:
        raw = state_obj.state
        if raw in ("unknown", "unavailable"):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="entity_state_unavailable",
                translation_placeholders={"entity_id": entity_id, "state": raw},
            )

    return str(raw), entity_id, attribute


# ---------------------------------------------------------------------------
# Type converters – convert raw string values to expected Python types
# ---------------------------------------------------------------------------


def _convert_to_timedelta(raw: str) -> timedelta:
    """Convert a raw string to timedelta.

    Accepts:
        - Numeric value → interpreted as minutes (e.g., "90" → 1h30m)
        - "HH:MM" → hours and minutes
        - "HH:MM:SS" → hours, minutes, seconds

    """
    # Try numeric (minutes)
    try:
        minutes = float(raw)
        return timedelta(minutes=minutes)
    except ValueError:
        pass

    # Try HH:MM or HH:MM:SS
    parts = raw.split(":")
    if len(parts) == 2:
        return timedelta(hours=int(parts[0]), minutes=int(parts[1]))
    if len(parts) == 3:
        return timedelta(hours=int(parts[0]), minutes=int(parts[1]), seconds=int(parts[2]))

    msg = f"Cannot convert '{raw}' to duration (expected minutes as number or HH:MM:SS)"
    raise ValueError(msg)


def _convert_to_datetime(raw: str) -> datetime:
    """Convert a raw string to datetime using HA's parser."""
    dt = dt_util.parse_datetime(raw)
    if dt is not None:
        return dt
    msg = f"Cannot convert '{raw}' to datetime"
    raise ValueError(msg)


def _convert_to_time(raw: str) -> dt_time:
    """Convert a raw string to time-of-day using HA's parser."""
    t = dt_util.parse_time(raw)
    if t is not None:
        return t
    msg = f"Cannot convert '{raw}' to time"
    raise ValueError(msg)


_CONVERTERS: dict[type, Any] = {
    int: lambda raw: int(float(raw)),
    float: float,
    timedelta: _convert_to_timedelta,
    datetime: _convert_to_datetime,
    dt_time: _convert_to_time,
}


def resolve_entity_references(
    hass: HomeAssistant,
    data: dict[str, Any] | Any,
    param_types: dict[str, type],
) -> tuple[dict[str, Any], dict[str, dict[str, str | None]]]:
    """Resolve entity references in service call data.

    Creates a mutable copy of the data dict and replaces any entity reference
    strings with their resolved and type-converted values.

    Args:
        hass: HomeAssistant instance.
        data: Service call data (typically call.data, may be immutable).
        param_types: Map of parameter name → expected Python type.
            Only parameters listed here are checked for entity references.

    Returns:
        Tuple of (resolved_data_dict, resolved_info_dict).
        resolved_data_dict: Mutable dict with entity refs replaced.
        resolved_info_dict: Details of resolved references (empty if none).
            Keys are parameter names; values contain entity_id, attribute,
            raw_value, and resolved_value for the service response.

    Raises:
        ServiceValidationError: If entity not found, attribute missing,
            state unavailable, or value cannot be converted.

    """
    resolved_data = dict(data)
    resolved_info: dict[str, dict[str, str | None]] = {}

    for param_name, expected_type in param_types.items():
        value = resolved_data.get(param_name)
        if value is None or not is_entity_reference(value):
            continue

        raw_value, entity_id, attribute = _resolve_raw_value(hass, value)

        converter = _CONVERTERS.get(expected_type)
        if converter is None:
            converted = raw_value
        else:
            try:
                converted = converter(raw_value)
            except (ValueError, TypeError) as err:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="entity_value_conversion_failed",
                    translation_placeholders={
                        "entity_id": entity_id,
                        "attribute": attribute or "state",
                        "raw_value": raw_value,
                        "expected_type": expected_type.__name__,
                    },
                ) from err

        resolved_data[param_name] = converted
        resolved_info[param_name] = {
            "entity_id": entity_id,
            "attribute": attribute,
            "raw_value": raw_value,
            "resolved_value": str(converted),
        }

    return resolved_data, resolved_info


def resolve_task_entity_references(
    hass: HomeAssistant,
    tasks: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, str | None]]]:
    """Resolve entity references in schedule task list.

    Handles entity references in task-level parameters (currently: duration).

    Args:
        hass: HomeAssistant instance.
        tasks: List of task dicts from service call data.

    Returns:
        Tuple of (resolved_tasks, resolved_info).
        resolved_tasks: New list with entity refs replaced in task dicts.
        resolved_info: Details keyed as "tasks[i].param_name".

    """
    task_param_types: dict[str, type] = {
        "duration": timedelta,
    }

    resolved_tasks = []
    all_resolved: dict[str, dict[str, str | None]] = {}

    for i, task in enumerate(tasks):
        resolved_task, task_resolved = resolve_entity_references(hass, task, task_param_types)
        resolved_tasks.append(resolved_task)
        for param_name, info in task_resolved.items():
            all_resolved[f"tasks[{i}].{param_name}"] = info

    return resolved_tasks, all_resolved
