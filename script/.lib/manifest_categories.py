"""
Copy the integration categories of the installed Home Assistant into the manifest schema.

The schema is where the editor and initialize.sh find the categories; Home Assistant generates the list in
homeassistant/generated/integration_categories.json from 2026.11. Run it in the project virtualenv after raising the
Home Assistant version:

    python3 script/.lib/manifest_categories.py
"""

from importlib.util import find_spec
import json
from pathlib import Path
import re
import sys

SCHEMA = Path(__file__).parents[2] / "schemas" / "json" / "manifest_schema.json"
ITEMS_BLOCK = re.compile(
    r'          "enum": \[(?:\n            .*)+\n          \],\n'
    r'          "enumDescriptions": \[(?:\n            .*)+\n          \]'
)


def installed_categories() -> dict[str, str] | None:
    """Return id → description for every category and subcategory, or None before Home Assistant ships the list."""
    spec = find_spec("homeassistant")
    if spec is None or spec.origin is None:
        return None
    generated = Path(spec.origin).parent / "generated" / "integration_categories.json"
    if not generated.is_file():
        return None
    categories = {}
    for category in json.loads(generated.read_text(encoding="utf-8")):
        categories[category["slug"]] = f"{category['name']}: {category['description']}"
        for sub in category["subcategories"]:
            categories[f"{category['slug']}.{sub['slug']}"] = f"{category['name']} › {sub['name']}"
    return categories


def schema_categories(schema: dict) -> dict:
    """Return the categories property of the manifest schema."""
    return schema["else"]["properties"]["categories"]


def _array(name: str, values: list[str]) -> str:
    entries = ",\n".join(f"            {json.dumps(value, ensure_ascii=False)}" for value in values)
    return f'          "{name}": [\n{entries}\n          ]'


def main() -> int:
    """Rewrite the category list in the schema from the installed Home Assistant."""
    categories = installed_categories()
    if categories is None:
        print("The installed Home Assistant has no integration categories (they arrived in 2026.11)", file=sys.stderr)
        return 1
    text = SCHEMA.read_text(encoding="utf-8")
    block = f"{_array('enum', list(categories))},\n{_array('enumDescriptions', list(categories.values()))}"
    updated, count = ITEMS_BLOCK.subn(lambda _: block, text)
    if count != 1:
        print(f"Found {count} category lists in {SCHEMA}, expected one", file=sys.stderr)
        return 1
    SCHEMA.write_text(updated, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
