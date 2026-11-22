"""Rendering and redaction for the development CLI.

Two output modes: aligned tables for a human reading a terminal, and `--json`
for anything that will be piped into `jq`. Both go through the same redactor,
because the CLI's whole point is that an agent can read this output — and the
credential it authenticates with must never appear in it.
"""

import json
from typing import Any

REDACTED = "**REDACTED**"

# Matched case-insensitively against dict keys, anywhere in the structure.
# Home Assistant's own diagnostics redact through async_redact_data; this is the
# second layer, and it also covers endpoints that have no such convention.
SENSITIVE_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "authorization",
        "latitude",
        "longitude",
        "password",
        "refresh_token",
        "token",
    }
)


def redact(value: Any) -> Any:
    """Return value with sensitive dict entries replaced, recursively."""
    if isinstance(value, dict):
        return {key: REDACTED if str(key).lower() in SENSITIVE_KEYS else redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def emit_json(value: Any) -> None:
    """Print value as indented JSON."""
    print(json.dumps(redact(value), indent=2, sort_keys=False, default=str))


def _cell(value: Any) -> str:
    """Render one table cell, keeping it to a single line."""
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=str)
    return str(value).replace("\n", " ")


def emit_table(rows: list[dict[str, Any]], columns: list[str], empty: str = "nothing to show") -> None:
    """Print rows as an aligned table, using columns in the given order."""
    if not rows:
        print(empty)
        return
    rendered = [{column: _cell(redact(row).get(column)) for column in columns} for row in rows]
    widths = {column: max(len(column), *(len(row[column]) for row in rendered)) for column in columns}
    print("  ".join(column.upper().ljust(widths[column]) for column in columns).rstrip())
    for row in rendered:
        print("  ".join(row[column].ljust(widths[column]) for column in columns).rstrip())


def emit_pairs(pairs: dict[str, Any], empty: str = "nothing to show") -> None:
    """Print a single record as aligned key/value lines."""
    if not pairs:
        print(empty)
        return
    safe = redact(pairs)
    width = max(len(key) for key in safe)
    for key, value in safe.items():
        print(f"{key.ljust(width)}  {_cell(value)}")
