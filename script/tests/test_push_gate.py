"""Tests for script/push-gate, the pre-push hook installed through .pre-commit-config.yaml."""

import os
from pathlib import Path
import shutil
import subprocess

import pytest

SCRIPT_DIR = Path(__file__).parents[1]


def _stub(repository: Path, name: str, exit_code: int) -> None:
    """Install a script/<name> stub that prints its name and exits with exit_code."""
    script = repository / "script" / name
    script.write_text(f"#!/bin/bash\necho {name} output\nexit {exit_code}\n", encoding="utf-8")
    script.chmod(0o755)


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    """A clean repository on main with the push gate and passing check stubs committed."""
    (tmp_path / "script" / ".lib").mkdir(parents=True)
    shutil.copy(SCRIPT_DIR / "push-gate", tmp_path / "script" / "push-gate")
    shutil.copy(SCRIPT_DIR / ".lib" / "output.sh", tmp_path / "script" / ".lib" / "output.sh")
    _stub(tmp_path, "lint-check", 0)
    _stub(tmp_path, "type-check", 0)
    for command in (
        ["git", "init", "--quiet", "--initial-branch=main"],
        ["git", "config", "user.email", "test@example.com"],
        ["git", "config", "user.name", "Push Gate Test"],
        ["git", "add", "."],
        ["git", "commit", "--quiet", "-m", "test: initialize"],
    ):
        subprocess.run(command, cwd=tmp_path, check=True)
    return tmp_path


def _run(repository: Path, **push: str) -> subprocess.CompletedProcess[str]:
    """Run the gate with the PRE_COMMIT_* variables prek sets for a pre-push hook."""
    env = {**os.environ, **{f"PRE_COMMIT_{key.upper()}": value for key, value in push.items()}}
    return subprocess.run(
        [str(repository / "script" / "push-gate")],
        cwd=repository,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _head(repository: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repository, capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.mark.unit
def test_passes_a_push_of_head(repository: Path) -> None:
    """A clean push of the checked-out branch runs both checks and passes."""
    result = _run(repository, local_branch="refs/heads/main", to_ref=_head(repository))

    assert result.returncode == 0, result.stderr
    assert "Push gate passed" in result.stdout


@pytest.mark.unit
def test_checks_head_when_run_by_hand(repository: Path) -> None:
    """Without the pre-push variables the gate validates HEAD."""
    assert _run(repository).returncode == 0


@pytest.mark.unit
def test_blocks_dirty_worktree(repository: Path) -> None:
    """Uncommitted files would make the checks pass for a commit that is not pushed."""
    (repository / "dirty.txt").write_text("not committed\n", encoding="utf-8")

    result = _run(repository, local_branch="refs/heads/main", to_ref=_head(repository))

    assert result.returncode == 1
    assert "the worktree is dirty" in result.stderr


@pytest.mark.unit
@pytest.mark.parametrize("local_branch", ["refs/heads/other", "refs/tags/v1.0.0"])
def test_blocks_a_ref_other_than_head(repository: Path, local_branch: str) -> None:
    """Another branch or a tag is not what the checks ran on."""
    result = _run(repository, local_branch=local_branch, to_ref=_head(repository))

    assert result.returncode == 1
    assert "only HEAD is validated" in result.stderr


@pytest.mark.unit
def test_blocks_detached_head(repository: Path) -> None:
    """A detached HEAD cannot be matched to the branch being pushed."""
    subprocess.run(["git", "checkout", "--quiet", "--detach"], cwd=repository, check=True)

    result = _run(repository)

    assert result.returncode == 1
    assert "HEAD is detached" in result.stderr


@pytest.mark.unit
@pytest.mark.parametrize(
    ("lint_exit", "type_exit", "reported"),
    [(1, 0, ["lint-check"]), (0, 1, ["type-check"]), (1, 1, ["lint-check", "type-check"])],
)
def test_reports_each_failing_check(repository: Path, lint_exit: int, type_exit: int, reported: list[str]) -> None:
    """Both checks run, and the gate names every one that failed together with its output."""
    _stub(repository, "lint-check", lint_exit)
    _stub(repository, "type-check", type_exit)
    subprocess.run(["git", "commit", "--quiet", "-am", "test: failing checks"], cwd=repository, check=True)

    result = _run(repository)

    assert result.returncode == 1
    for name in ("lint-check", "type-check"):
        assert (f"script/{name} failed" in result.stderr) == (name in reported)
        assert (f"{name} output" in result.stderr) == (name in reported)
