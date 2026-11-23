"""Tests for script/prune-blueprint."""

from pathlib import Path
import shutil
import subprocess

import pytest

SCRIPT_DIR = Path(__file__).parents[1]
SECTION_FILE = ".agents/skills/README.md"
README = "keep\n\n<!-- blueprint-only:start -->\n\ndrop\n\n<!-- blueprint-only:end -->\n\nkeep too\n"
PRUNED = (
    ".github/FUNDING.yml",
    "docs/blueprint/MIGRATION.md",
    ".agents/skills/blueprint-skill-maintenance/SKILL.md",
    "script/tests/test_initialize.py",
)
PROJECT_OWNED = ".devcontainer/project-feature/devcontainer-feature.json"
SYNC_IGNORE = ".templatesyncignore"
SYNC_IGNORE_BEFORE = "docs/blueprint/\n.github/FUNDING.yml\n.agents/skills/blueprint-skill-maintenance/\n"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """An initialised-looking repository holding the blueprint leftovers and one file that must survive."""
    (tmp_path / "script" / ".lib").mkdir(parents=True)
    shutil.copy(SCRIPT_DIR / "prune-blueprint", tmp_path / "script" / "prune-blueprint")
    shutil.copy(SCRIPT_DIR / ".lib" / "output.sh", tmp_path / "script" / ".lib" / "output.sh")
    for name in (*PRUNED, PROJECT_OWNED, "docs/user/GUIDE.md"):
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text("x\n", encoding="utf-8")
    (tmp_path / SECTION_FILE).write_text(README, encoding="utf-8")
    (tmp_path / SYNC_IGNORE).write_text(SYNC_IGNORE_BEFORE, encoding="utf-8")
    return tmp_path


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run the copied script inside the temporary repository."""
    return subprocess.run(
        [str(repo / "script" / "prune-blueprint"), *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.unit
def test_dry_run_lists_without_deleting(repo: Path) -> None:
    """Without --apply the script reports and changes nothing."""
    result = _run(repo)

    assert result.returncode == 0
    assert "FUNDING.yml" in result.stdout
    assert all((repo / name).exists() for name in PRUNED)
    assert (repo / SECTION_FILE).read_text(encoding="utf-8") == README
    assert (repo / SYNC_IGNORE).read_text(encoding="utf-8") == SYNC_IGNORE_BEFORE


@pytest.mark.unit
def test_apply_adds_only_missing_sync_ignore_entries(repo: Path) -> None:
    """Paths already listed, with or without a trailing slash, gain no second entry."""
    result = _run(repo, "--apply")

    assert result.returncode == 0
    added = (repo / SYNC_IGNORE).read_text(encoding="utf-8").removeprefix(SYNC_IGNORE_BEFORE).splitlines()
    assert [line for line in added if line and not line.startswith("#")] == [
        "script/tests/test_initialize.py",
        "script/import-overlay",
        "script/tests/test_import_overlay.py",
        ".devcontainer/project-feature",
    ]


@pytest.mark.unit
def test_apply_removes_leftovers_and_keeps_the_rest(repo: Path) -> None:
    """--apply removes the listed paths and sections and leaves other files alone."""
    result = _run(repo, "--apply")

    assert result.returncode == 0
    assert not any((repo / name).exists() for name in PRUNED)
    assert (repo / SECTION_FILE).read_text(encoding="utf-8") == "keep\n\nkeep too\n"
    assert (repo / "docs" / "user" / "GUIDE.md").exists()
    assert (repo / PROJECT_OWNED).exists()


S, E = "<!-- blueprint-only:start -->", "<!-- blueprint-only:end -->"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("before", "after"),
    [
        pytest.param(f"keep\n{S}\ndrop\n{E}\nkeep too\n", "keep\nkeep too\n", id="tight"),
        pytest.param(f"keep\n\n{S}\n\ndrop\n\n{E}\n\nkeep too\n", "keep\n\nkeep too\n", id="spaced"),
        pytest.param(f"{S}\ndrop\n{E}\n\nkeep\n", "keep\n", id="at-start"),
        pytest.param(f"keep\n\n{S}\ndrop\n{E}\n", "keep\n", id="at-end"),
        pytest.param(
            f"```text\na\n\n\nb\n```\n\n{S}\ndrop\n{E}\n\nkeep\n",
            "```text\na\n\n\nb\n```\n\nkeep\n",
            id="blank-lines-elsewhere-kept",
        ),
    ],
)
def test_section_removal_leaves_lint_clean_blank_lines(repo: Path, before: str, after: str) -> None:
    """Only the blank lines meeting at the removed section are joined; the rest of the file keeps its own."""
    (repo / SECTION_FILE).write_text(before, encoding="utf-8")

    assert _run(repo, "--apply").returncode == 0
    assert (repo / SECTION_FILE).read_text(encoding="utf-8") == after


@pytest.mark.unit
def test_section_removal_writes_through_a_symlink_and_keeps_the_mode(repo: Path) -> None:
    """The file is rewritten in place, not replaced by a new one."""
    target = repo / "real-readme.md"
    target.write_text(README, encoding="utf-8")
    target.chmod(0o640)
    (repo / SECTION_FILE).unlink()
    (repo / SECTION_FILE).symlink_to(target)

    assert _run(repo, "--apply").returncode == 0
    assert (repo / SECTION_FILE).is_symlink()
    assert target.stat().st_mode & 0o777 == 0o640
    assert target.read_text(encoding="utf-8") == "keep\n\nkeep too\n"


@pytest.mark.unit
def test_apply_is_idempotent(repo: Path) -> None:
    """A second run finds nothing left to do."""
    _run(repo, "--apply")
    result = _run(repo, "--apply")

    assert result.returncode == 0
    assert "Nothing to prune" in result.stdout


@pytest.mark.unit
def test_refuses_while_initialize_script_exists(repo: Path) -> None:
    """The blueprint and uninitialised copies are never pruned."""
    (repo / "initialize.sh").write_text("#!/bin/bash\n", encoding="utf-8")

    result = _run(repo, "--apply")

    assert result.returncode == 1
    assert all((repo / name).exists() for name in PRUNED)
