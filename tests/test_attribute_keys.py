"""Attribute keys carry no `%`: translated attribute names allow only [a-z0-9_-] in their key (#267)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent / "custom_components" / "tibber_prices"


def _sources() -> list[Path]:
    return [path for path in sorted(ROOT.rglob("*.py")) if "frontend" not in path.parts]


@pytest.mark.unit
def test_no_attribute_key_ends_in_percent_sign() -> None:
    """No string constant looks like a `name_%` key, and no key is built by adding PERCENTAGE to a name."""
    offenders = []
    for path in _sources():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value.endswith("_%"):
                    offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}: {node.value!r}")
            elif (
                isinstance(node, ast.BinOp)
                and isinstance(node.op, ast.Add)
                and isinstance(node.right, ast.Name)
                and node.right.id == "PERCENTAGE"
            ):
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}: key built with PERCENTAGE")
    assert not offenders, "attribute keys must end in _percent, not %:\n" + "\n".join(offenders)
