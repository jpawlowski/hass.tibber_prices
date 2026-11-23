"""hacs.json and release-please-config.json agree on how a release is installed."""

import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).parents[2]


def _load(name: str) -> dict[str, Any]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


@pytest.mark.unit
def test_zip_release_comes_with_its_companions() -> None:
    """With zip_release, the asset has a ZIP name, the default branch is hidden and releases start as drafts."""
    hacs = _load("hacs.json")
    package = _load("release-please-config.json")["packages"]["."]

    companions = {
        "hacs.json filename ending in .zip": str(hacs.get("filename", "")).endswith(".zip"),
        "hacs.json hide_default_branch": hacs.get("hide_default_branch") is True,
        "release-please-config.json draft": package.get("draft") is True,
        "release-please-config.json force-tag-creation": package.get("force-tag-creation") is True,
    }
    missing = [name for name, present in companions.items() if not present]

    assert hacs.get("zip_release") is not True or not missing, f"zip_release is set, but these are missing: {missing}"
