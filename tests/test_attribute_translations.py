"""The translated attribute names (state_attributes) are generated; they must be current and complete."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import subprocess
import sys

import pytest

REPO = Path(__file__).parent.parent
GENERATOR = REPO / "scripts" / "i18n" / "generate-attribute-translations"
TRANSLATIONS = REPO / "custom_components" / "tibber_prices" / "translations"
LANGUAGES = ("en", "de", "nb", "nl", "sv")
KEY = re.compile(r"^[a-z0-9_-]+$")


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


# Keys written with `x["key"] = ...` in the attribute builders that are no attributes: nested entries of the
# outlook lists and parameters of the chart metadata service call
NOT_ATTRIBUTES = {"energy", "part", "complete", "entry_id", "metadata", "subunit_currency"}


@pytest.mark.unit
def test_every_attribute_a_builder_writes_has_a_name() -> None:
    """A new `attributes["key"] = ...` needs a name in scripts/i18n/attribute-names.json (or is no attribute)."""
    package = REPO / "custom_components" / "tibber_prices"
    source = json.loads((REPO / "scripts" / "i18n" / "attribute-names.json").read_text(encoding="utf-8"))["names"]
    templates = [re.compile("^" + re.escape(name).replace(r"\{h\}", r"\d+") + "$") for name in source if "{h}" in name]
    builders = [
        *sorted((package / "sensor" / "attributes").glob("*.py")),
        package / "binary_sensor" / "attributes.py",
        package / "binary_sensor" / "core.py",
        package / "sensor" / "chart_metadata.py",
    ]
    missing = set()
    for path in builders:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Subscript)
                and isinstance(node.ctx, ast.Store)
                and isinstance(node.slice, ast.Constant)
                and isinstance(node.slice.value, str)
            ):
                key = node.slice.value
                if key not in source and key not in NOT_ATTRIBUTES and not any(t.match(key) for t in templates):
                    missing.add(f"{path.name}: {key}")
    assert not missing, f"attributes without a translated name: {sorted(missing)}"
