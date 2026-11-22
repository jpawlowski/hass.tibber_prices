"""
Guards the Marketplace exclude markers in the README.

The Marketplace leaves out what lies between `<!-- ha-marketplace:exclude-start -->` and
`<!-- ha-marketplace:exclude-end -->`. A start without an end hides the rest of the README
there, and GitHub renders both as invisible comments, so nobody would notice.
"""

from __future__ import annotations

from pathlib import Path
import re

import pytest

README = Path(__file__).parent.parent / "README.md"
MARKER = re.compile(r"<!--\s*ha-marketplace:exclude-(start|end)\s*-->")


@pytest.mark.unit
def test_exclude_markers_alternate_and_close() -> None:
    """Every start is followed by one end before the next start, and none stays open."""
    kinds = [match.group(1) for match in MARKER.finditer(README.read_text(encoding="utf-8"))]
    assert kinds, "README has no Marketplace exclude markers"
    assert kinds == ["start", "end"] * (len(kinds) // 2), f"Unbalanced exclude markers: {kinds}"
