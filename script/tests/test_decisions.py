"""Tests for script/.lib/decisions.py, which writes and checks the decision record index."""

from pathlib import Path
import subprocess
import sys

import pytest

MODULE = Path(__file__).parents[1] / ".lib" / "decisions.py"
FOLDER = Path("docs/development/decisions")


def _record(root: Path, record_id: str, *, title: str = "Use the thing", **fields: str) -> None:
    lines = ["---", f"id: {record_id}"]
    lines += [f"{name}: {value}" for name, value in {"status": "accepted", **fields}.items()]
    lines += ["---", "", f"# {title}", "", "## Context", "", "Why.", ""]
    (root / FOLDER).mkdir(parents=True, exist_ok=True)
    (root / FOLDER / f"{record_id}.md").write_text("\n".join(lines), encoding="utf-8")


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(MODULE), *args], cwd=root, capture_output=True, text=True, check=False)


@pytest.mark.unit
def test_no_decisions_folder_passes(tmp_path: Path) -> None:
    """A repository still on the single DECISIONS.md, or with no decisions at all, is not failed."""
    assert _run(tmp_path, "--check").returncode == 0


@pytest.mark.unit
def test_index_lists_records_in_force_and_in_history(tmp_path: Path) -> None:
    """Writing the index puts accepted records under In force and superseded ones under History."""
    _record(tmp_path, "20260101-old-way", title="Old way", status="superseded", **{"superseded-by": "20260201-new-way"})
    _record(tmp_path, "20260201-new-way", title="New way", supersedes="20260101-old-way")

    assert _run(tmp_path).returncode == 0
    index = (tmp_path / FOLDER / "README.md").read_text(encoding="utf-8")

    in_force, history = index.split("## History")
    assert "New way" in in_force
    assert "Old way" in history
    assert _run(tmp_path, "--check").returncode == 0


@pytest.mark.unit
def test_stale_index_fails_the_check(tmp_path: Path) -> None:
    """A record added after the index was written makes --check fail until the index is regenerated."""
    _record(tmp_path, "20260101-first")
    _run(tmp_path)
    _record(tmp_path, "20260201-second")

    result = _run(tmp_path, "--check")

    assert result.returncode == 1
    assert "out of date" in result.stderr


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        pytest.param({"status": "proposed"}, "status must be one of", id="unknown-status"),
        pytest.param({"status": "superseded"}, "names its successor", id="superseded-without-successor"),
        pytest.param({"supersedes": "20250101-missing"}, "has no record", id="dangling-supersedes"),
        pytest.param({"rule": "AGENTS.md"}, "does not exist", id="missing-rule"),
        pytest.param({"owner": "someone"}, "unknown frontmatter fields", id="unknown-field"),
        pytest.param({"supersedes": "2026-01-01"}, "must be a string or a list", id="date-instead-of-id"),
    ],
)
@pytest.mark.unit
def test_invalid_record_fails(tmp_path: Path, fields: dict[str, str], message: str) -> None:
    """Each broken link or value is reported with the record it is in."""
    _record(tmp_path, "20260101-broken", **fields)

    result = _run(tmp_path)

    assert result.returncode == 1
    assert message in result.stderr


@pytest.mark.unit
def test_rule_must_point_back_to_its_record(tmp_path: Path) -> None:
    """A rule a record names carries a Source: line for it, so the rule leads back to why it holds."""
    rule = tmp_path / "AGENTS.md"
    rule.write_text("- Never do the thing.\n", encoding="utf-8")
    _record(tmp_path, "20260101-rule", rule="AGENTS.md")

    assert "has no 'Source:" in _run(tmp_path).stderr

    rule.write_text("- Never do the thing. Source: docs/development/decisions/20260101-rule.md\n", encoding="utf-8")
    assert _run(tmp_path).returncode == 0


@pytest.mark.unit
def test_id_must_match_the_file_name(tmp_path: Path) -> None:
    """The id in the frontmatter and the file name are the same, or links between records break."""
    _record(tmp_path, "20260101-right")
    path = tmp_path / FOLDER / "20260101-right.md"
    path.write_text(path.read_text(encoding="utf-8").replace("id: 20260101-right", "id: 20260101-wrong"), "utf-8")

    assert "id must equal the file name" in _run(tmp_path).stderr
