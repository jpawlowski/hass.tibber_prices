"""The translated attribute names (state_attributes) are generated from the entities' declarations; they must be current."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys

import pytest

REPO = Path(__file__).parent.parent

GENERATOR = REPO / "script" / "i18n" / "generate-attribute-translations.py"
TRANSLATIONS = REPO / "custom_components" / "tibber_prices" / "translations"
KEY = re.compile(r"^[a-z0-9_-]+$")
LANGUAGES = json.loads((REPO / "script" / "i18n" / "attribute-names.json").read_text(encoding="utf-8"))["languages"]


@pytest.mark.unit
def test_generated_translations_are_current() -> None:
    """Run the generator in check mode: the committed files match its output."""
    result = subprocess.run([sys.executable, str(GENERATOR), "--check"], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr or result.stdout


@pytest.mark.unit
@pytest.mark.parametrize("language", LANGUAGES)
def test_attribute_names_are_valid_and_the_same_in_every_language(language: str) -> None:
    """Keys follow Hassfest's pattern, and each entity has the same attributes in every language."""
    english = json.loads((TRANSLATIONS / "en.json").read_text(encoding="utf-8"))["entity"]
    data = json.loads((TRANSLATIONS / f"{language}.json").read_text(encoding="utf-8"))["entity"]
    for platform, entities in english.items():
        for entity, content in entities.items():
            expected = content.get("state_attributes", {})
            actual = data[platform][entity].get("state_attributes", {})
            assert list(actual) == list(expected), f"{platform}.{entity}"
            for attribute, texts in actual.items():
                assert KEY.match(attribute), f"{platform}.{entity}.{attribute}"
                assert texts["name"].strip(), f"{platform}.{entity}.{attribute}"
