"""Tests for script/second-review, which reviews a branch with a different agent CLI than the session's own."""

import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).parents[2]
BRIEF_TEXT = "# Reviewer brief\n\nYou review a change to this repository.\n"

# A codex stand-in: writes where it ran and the prompt's range line as its last message.
CODEX = """#!/bin/bash
[[ "$1" == login ]] && exit 0
out=""
while [[ $# -gt 0 ]]; do
    [[ "$1" == --output-last-message ]] && out="$2"
    shift
done
{ echo "ran in: $PWD"; grep '^Range:' -; grep -c '^+changed$' .second-review.patch; grep -c 'You review a change' "$BRIEF_PATH"; } >"$out"
"""


def _git(repository: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repository, capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    """A repository with the script and its libraries, and one commit on top of a base."""
    repository = tmp_path / "repository"
    (repository / "script" / ".lib").mkdir(parents=True)
    shutil.copy(ROOT / "script" / "second-review", repository / "script" / "second-review")
    for library in ("output.sh", "agent_cli.sh"):
        shutil.copy(ROOT / "script" / ".lib" / library, repository / "script" / ".lib" / library)
    (repository / ".gitignore").write_text(".agents/scratch/\n", encoding="utf-8")
    _git(repository, "init", "--quiet", "--initial-branch=main")
    _git(repository, "config", "user.email", "test@example.com")
    _git(repository, "config", "user.name", "Second Review Test")
    _git(repository, "add", ".")
    _git(repository, "commit", "--quiet", "-m", "test: base")
    (repository / "change.txt").write_text("changed\n", encoding="utf-8")
    _git(repository, "add", ".")
    _git(repository, "commit", "--quiet", "-m", "feat: the change")
    return repository


def _run(repository: Path, tmp_path: Path, *args: str, **env: str) -> subprocess.CompletedProcess[str]:
    folder = tmp_path / "bin"
    folder.mkdir(exist_ok=True)
    brief = tmp_path / "reviewer-brief.md"
    brief.write_text(BRIEF_TEXT, encoding="utf-8")
    stub = folder / "codex"
    stub.write_text(CODEX, encoding="utf-8")
    stub.chmod(0o755)
    environment = {
        **{key: value for key, value in os.environ.items() if key not in {"CLAUDECODE", "AI_AGENT", "AGENT_CLI"}},
        "PATH": f"{folder}:{os.environ['PATH']}",
        "BRIEF_PATH": str(brief),
        "CODEX_API_KEY": "k",
        **env,
    }
    return subprocess.run(
        [str(repository / "script" / "second-review"), "--brief", str(brief), *args],
        cwd=repository,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.unit
def test_reviews_an_export_of_the_head_and_cleans_up(repository: Path, tmp_path: Path) -> None:
    """The reviewer runs in an export of the head outside any checkout, with the brief and the patch, gone afterwards."""
    base = _git(repository, "rev-parse", "HEAD~1")
    head = _git(repository, "rev-parse", "HEAD")

    result = _run(repository, tmp_path, "--base", base, AGENT_CLI="codex")

    assert result.returncode == 0, result.stderr
    assert f"Range: {base}..{head}" in result.stdout
    assert "/second-review." in result.stdout
    assert str(repository) not in result.stdout.split("ran in: ")[1].splitlines()[0]
    assert result.stdout.rstrip().endswith("1\n1")
    report = repository / ".agents" / "scratch" / f"second-review-{head[:12]}.md"
    assert report.read_text(encoding="utf-8") == result.stdout
    assert not Path(result.stdout.split("ran in: ")[1].splitlines()[0]).exists()


@pytest.mark.unit
def test_an_empty_range_is_refused(repository: Path, tmp_path: Path) -> None:
    """A head that is its own base has nothing to review."""
    result = _run(repository, tmp_path, "--base", "HEAD", AGENT_CLI="codex")

    assert result.returncode != 0
    assert "nothing to review" in result.stderr + result.stdout


@pytest.mark.unit
def test_the_brief_is_required(repository: Path) -> None:
    """The brief ships with the plugin skill, not the repository, so a run without --brief names what it needs."""
    result = subprocess.run(
        [str(repository / "script" / "second-review")], cwd=repository, capture_output=True, text=True, check=False
    )

    assert result.returncode != 0
    assert "--brief is required" in result.stderr + result.stdout
