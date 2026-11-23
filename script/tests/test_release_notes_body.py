"""Tests for script/.lib/release_notes_body.py, which keeps a release-please body readable after a rewrite."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import subprocess
import sys

import pytest

MODULE = Path(__file__).parents[1] / ".lib" / "release_notes_body.py"
_spec = spec_from_file_location("release_notes_body", MODULE)
assert _spec is not None
assert _spec.loader is not None
release_notes_body = module_from_spec(_spec)
_spec.loader.exec_module(release_notes_body)
BodyError = release_notes_body.BodyError
merge = release_notes_body.merge
version_of = release_notes_body.version_of

PR_BODY = """:robot: I have created a release *beep* *boop*
---


## [0.2.0](https://github.com/owner/repo/compare/v0.1.0...v0.2.0) (2026-11-22)


### 🎉 What's new

* add a fan speed sensor ([#12](https://github.com/owner/repo/issues/12)) ([abc1234](https://github.com/owner/repo/commit/abc1234))

---
This PR was generated with [Release Please](https://github.com/googleapis/release-please).
"""

NOTES = """### 🎉 What's new

- A new sensor shows your device's fan speed on your dashboard.
"""


@pytest.mark.unit
def test_rewritten_body_keeps_what_release_please_reads_back() -> None:
    """Header, delimiters, version heading and footer stay; only the notes under the heading change."""
    body = merge(PR_BODY, NOTES)

    assert version_of(body) == "0.2.0"
    assert body.startswith(":robot: I have created a release")
    assert "## [0.2.0](https://github.com/owner/repo/compare/v0.1.0...v0.2.0) (2026-11-22)" in body
    assert "A new sensor shows your device's fan speed" in body
    assert "abc1234" not in body
    assert body.rstrip().endswith(
        "This PR was generated with [Release Please](https://github.com/googleapis/release-please)."
    )


@pytest.mark.unit
def test_version_heading_and_delimiters_from_the_model_are_dropped() -> None:
    """A heading or a '---' line in the rewritten notes would make release-please read the wrong text."""
    body = merge(PR_BODY, "## [9.9.9]\n\n---\n\n" + NOTES)

    assert version_of(body) == "0.2.0"
    assert "9.9.9" not in body
    assert body.count("\n---\n") == 2


@pytest.mark.parametrize(
    ("pr_body", "message"),
    [
        pytest.param("Just some text\n", "no '---' line", id="not-a-release-please-body"),
        pytest.param("header\n---\n\nno heading here\n\n---\nfooter\n", "names no version", id="no-version-heading"),
    ],
)
@pytest.mark.unit
def test_a_body_release_please_cannot_read_is_refused(pr_body: str, message: str) -> None:
    """Writing such a body would skip the release or publish it without notes, so nothing is written."""
    with pytest.raises(BodyError, match=message):
        merge(pr_body, NOTES)


@pytest.mark.unit
def test_notes_with_nothing_but_a_heading_are_refused() -> None:
    """Notes that are empty once the heading and delimiters are dropped would publish a release without notes."""
    with pytest.raises(BodyError, match="notes are empty"):
        merge(PR_BODY, "## [0.2.0]\n\n---\n")


@pytest.mark.unit
def test_command_line_prints_the_body(tmp_path: Path) -> None:
    """The script calls the module with two files and takes the new body from stdout."""
    (tmp_path / "pr.md").write_text(PR_BODY.replace("\n", "\r\n"), encoding="utf-8")
    (tmp_path / "notes.md").write_text(NOTES, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(MODULE), str(tmp_path / "pr.md"), str(tmp_path / "notes.md")],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert version_of(result.stdout) == "0.2.0"


CAPTURED = Path(__file__).parent / "fixtures" / "release-please-pr-body.txt"


@pytest.mark.unit
def test_a_body_captured_from_release_please_round_trips() -> None:
    """A real release PR body (release-please-action v5.0.0) keeps its header, heading and footer byte for byte.

    The body is taken unchanged from a merged release PR, so a release-please update that changes the format fails
    here rather than at the next release.
    """
    captured = CAPTURED.read_text(encoding="utf-8")
    first, last = captured.index("\n---\n"), captured.rindex("\n---\n")
    heading = next(line for line in captured[first:].split("\n") if line.startswith("## ["))

    body = merge(captured, NOTES)

    assert version_of(captured) == "0.40.0"
    assert version_of(body) == "0.40.0"
    assert body.startswith(captured[:first])
    assert body.endswith(captured[last:].rstrip("\n") + "\n")
    assert heading in body
    assert "BREAKING CHANGES" not in body
    assert "A new sensor shows your device's fan speed" in body
