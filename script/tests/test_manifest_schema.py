"""Keep the hand-maintained manifest schema in step with the Home Assistant release it targets."""

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path

import pytest

_spec = spec_from_file_location("manifest_categories", Path(__file__).parents[1] / ".lib" / "manifest_categories.py")
assert _spec is not None
assert _spec.loader is not None
manifest_categories = module_from_spec(_spec)
_spec.loader.exec_module(manifest_categories)

ITEMS = manifest_categories.schema_categories(json.loads(manifest_categories.SCHEMA.read_text(encoding="utf-8")))[
    "items"
]


@pytest.mark.unit
def test_every_category_has_a_description() -> None:
    """initialize.sh and the editor pair each id with the description at the same position."""
    assert len(ITEMS["enum"]) == len(ITEMS["enumDescriptions"]) == len(set(ITEMS["enum"]))


@pytest.mark.unit
@pytest.mark.skipif(
    not (Path(__file__).parents[2] / "initialize.sh").exists(),
    reason="the blueprint keeps this list; template sync brings an initialised repository its updates",
)
def test_categories_match_installed_home_assistant() -> None:
    """A category Home Assistant added, renamed or dropped has to reach the schema, which initialize.sh reads."""
    categories = manifest_categories.installed_categories()
    if categories is None:
        pytest.skip("the installed Home Assistant predates manifest categories (2026.11)")

    assert list(zip(ITEMS["enum"], ITEMS["enumDescriptions"], strict=True)) == list(categories.items()), (
        "Run python3 script/.lib/manifest_categories.py"
    )
