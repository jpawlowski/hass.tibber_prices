"""
Guards the Marketplace exclude markers in the README.

The Marketplace leaves out what lies between `<!-- ha-marketplace:exclude-start -->` and
`<!-- ha-marketplace:exclude-end -->`. A start without an end hides the rest of the README
there, and GitHub renders both as invisible comments, so nobody would notice. Markers inside code
are text to the Marketplace and are not counted.
"""

from __future__ import annotations

from pathlib import Path
import re

import pytest

README = Path(__file__).parent.parent / "README.md"
# The Marketplace shows markers inside fenced or inline code as text, so they don't count
CODE = re.compile(r"```.*?```|`[^`\n]*`", re.DOTALL)
MARKER = re.compile(r"<!--\s*ha-marketplace:exclude-(start|end)\s*-->")


@pytest.mark.unit
def test_exclude_markers_alternate_and_close() -> None:
    """Every start is followed by one end before the next start, and none stays open."""
    text = CODE.sub("", README.read_text(encoding="utf-8"))
    kinds = [match.group(1) for match in MARKER.finditer(text)]
    assert kinds, "README has no Marketplace exclude markers"
    assert kinds == ["start", "end"] * (len(kinds) // 2), f"Unbalanced exclude markers: {kinds}"
