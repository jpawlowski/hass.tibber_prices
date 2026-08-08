"""
Guards on placeholder syntax in the shipped translations.

The frontend renders these strings through ICU MessageFormat, where an ASCII single
quote before a brace starts an escape. A message written as `'{name}'` therefore
reaches the user as the literal text `{name}` - quotes consumed, value never
substituted. The backend substitutes with plain str.format() and is unaffected, so
the two disagree: the log line looks correct while the dialog shows the placeholder
name. Hassfest rejects it, but only after a push.

An apostrophe inside a word (`Tibber's`, `view's`) is not an escape - ICU only treats
a quote specially when a brace, or another quote, follows it directly.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

import pytest

TRANSLATIONS = Path(__file__).parent.parent / "custom_components/tibber_prices/translations"

# A quote that ICU would read as starting an escape sequence.
ICU_ESCAPE = re.compile(r"'(?=[{}'])")

PLACEHOLDER = re.compile(r"\{(\w+)\}")


def _strings(node: Any, path: str = "") -> list[tuple[str, str]]:
    """Flatten a translation file to (dotted path, string) pairs."""
    if isinstance(node, dict):
        return [pair for key, value in node.items() for pair in _strings(value, f"{path}.{key}".lstrip("."))]
    if isinstance(node, list):
        return [pair for index, value in enumerate(node) for pair in _strings(value, f"{path}[{index}]")]
    return [(path, node)] if isinstance(node, str) else []


def _locale_files() -> list[Path]:
    files = sorted(TRANSLATIONS.glob("*.json"))
    assert files, "no translation files found"
    return files


@pytest.mark.unit
@pytest.mark.parametrize("path", _locale_files(), ids=lambda p: p.stem)
def test_no_icu_escape_before_a_brace(path: Path) -> None:
    """No string may quote a brace, which would suppress substitution in the UI."""
    offenders = [
        (key, value)
        for key, value in _strings(json.loads(path.read_text(encoding="utf-8")))
        if ICU_ESCAPE.search(value)
    ]

    assert not offenders, (
        f"{path.name}: ICU would treat these quotes as escapes and print the placeholder "
        f"name instead of its value - use typographic quotes: {offenders}"
    )


@pytest.mark.unit
def test_every_locale_uses_the_same_placeholders() -> None:
    """A translation must not invent or drop a placeholder the code does not supply.

    An unknown name raises at substitution time; a dropped one silently hides detail
    that the English message promises.
    """
    per_locale: dict[str, dict[str, set[str]]] = {}
    for path in _locale_files():
        per_locale[path.stem] = {
            key: set(PLACEHOLDER.findall(value))
            for key, value in _strings(json.loads(path.read_text(encoding="utf-8")))
            if PLACEHOLDER.search(value)
        }

    reference = per_locale["en"]
    mismatches = [
        (locale, key, sorted(names), sorted(reference[key]))
        for locale, entries in per_locale.items()
        if locale != "en"
        for key, names in entries.items()
        if key in reference and names != reference[key]
    ]

    assert not mismatches, f"placeholders differ from en.json: {mismatches}"
