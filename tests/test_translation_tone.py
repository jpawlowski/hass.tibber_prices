"""
Guards that every locale addresses the reader informally.

Project rule: user-facing strings say "du", never the polite form - in every
language that distinguishes them. Home Assistant's own German and Dutch translations
do the same, so a polite string would stand out inside the UI it appears in.

Detection is deliberately narrow. Third-person pronouns collide with polite ones in
several of these languages: German "Sie wurde entfernt" is "it was removed", and
"die Ansicht benennt ihr Zuhause" is "its home". Dutch "u" is also the abbreviation
for "uur". Matching those would produce failures on correct strings, so each pattern
below keys on a construction that only the polite form produces.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

import pytest

COMPONENT = Path(__file__).parent.parent / "custom_components/tibber_prices"

# Per language, a pattern that only polite address can produce.
#
# de: the polite imperative is "<verb> Sie", and the polite possessive is capitalised
#     "Ihr*" mid-sentence, where a third-person "ihr" would be lowercase.
# nl: "uw" is unambiguously the polite possessive; bare "u" only counts when no digit
#     precedes it, which rules out the "1,5 u" hour abbreviation.
# sv/nb: polite address is archaic and only appears as these forms.
POLITE = {
    "de": re.compile(
        r"\b(?:[A-ZÄÖÜ][a-zäöüß]+en)\s+Sie\b|(?<=[a-zäöüß,]\s)Ihre?[nmrs]?\b|(?<=[a-zäöüß,]\s)Ihnen\b",
    ),
    "nl": re.compile(r"\buw\b|(?<!\d)(?<!\d )\bu\b"),
    "sv": re.compile(r"\b(?:Ni|Er|Ert|Era|Eder)\b"),
    "nb": re.compile(r"\b(?:Dem|Deres)\b"),
}

# Languages without a polite/familiar distinction worth guarding.
NO_DISTINCTION = {"en"}


def _strings(node: Any, path: str = "") -> list[tuple[str, str]]:
    if isinstance(node, dict):
        return [pair for key, value in node.items() for pair in _strings(value, f"{path}.{key}".lstrip("."))]
    return [(path, node)] if isinstance(node, str) else []


def _locale_files() -> list[Path]:
    files = sorted(
        path
        for folder in ("translations", "custom_translations")
        for path in (COMPONENT / folder).glob("*.json")
        if path.stem not in NO_DISTINCTION
    )
    assert files, "no translation files found"
    return files


@pytest.mark.unit
@pytest.mark.parametrize("path", _locale_files(), ids=lambda p: f"{p.parent.name}/{p.stem}")
def test_locale_addresses_the_reader_informally(path: Path) -> None:
    """No string may use the polite form."""
    pattern = POLITE.get(path.stem)
    if pattern is None:
        pytest.skip(f"no polite-form pattern defined for {path.stem}")

    offenders = [
        (key, value) for key, value in _strings(json.loads(path.read_text(encoding="utf-8"))) if pattern.search(value)
    ]

    assert not offenders, f"{path.parent.name}/{path.name} uses polite address: {offenders}"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("language", "polite"),
    [
        ("de", "Wählen Sie eine Ansicht aus."),
        ("de", "Das ist Ihre Ansicht."),
        ("nl", "Kies uw weergave."),
        ("sv", "Välj Er vy."),
        ("nb", "Velg Deres visning."),
    ],
)
def test_pattern_catches_polite_address(language: str, polite: str) -> None:
    """The guard must actually fire - a pattern that never matches guards nothing."""
    assert POLITE[language].search(polite), f"{language}: polite form not detected in {polite!r}"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("language", "correct"),
    [
        # Third person, not address - these are why the patterns are narrow.
        ("de", "Diese Ansicht ist nicht eingerichtet. Sie wurde möglicherweise entfernt."),
        ("de", "Die Ansicht benennt ihr Zuhause bereits."),
        ("de", "Wähle eine Ansicht von diesem Zuhause."),
        # "u" as the abbreviation for "uur", and informal address.
        ("nl", "UI kan 1,5 u tonen terwijl de waarde 90 blijft."),
        ("nl", "Kies je weergave."),
        ("sv", "Välj din vy."),
        ("nb", "Velg visningen din."),
    ],
)
def test_pattern_leaves_correct_strings_alone(language: str, correct: str) -> None:
    """A guard that fails on valid strings would be worse than none."""
    assert not POLITE[language].search(correct), f"{language}: false positive on {correct!r}"
