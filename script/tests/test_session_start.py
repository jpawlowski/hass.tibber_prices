"""Tests for .agents/hooks/session-start.sh, the SessionStart hook every agent runs."""

from collections.abc import Callable
import json
import os
from pathlib import Path
import pty
import shutil
import subprocess
import time

import pytest

ROOT = Path(__file__).parents[2]
HOOK = ROOT / ".agents" / "hooks" / "session-start.sh"
SETUP_STUB = "#!/bin/bash\nset -euo pipefail\nsource script/.lib/output.sh\ntrack_run {name}\n{body}\n"


def _stub(repo: Path, name: str, body: str) -> None:
    """Replace script/setup/<name> with a stub that records its run the way the real script does."""
    script = repo / "script" / "setup" / name
    script.write_text(SETUP_STUB.format(name=name, body=body), encoding="utf-8")
    script.chmod(0o755)


def _wait_for(condition: Callable[[], bool]) -> None:
    deadline = time.monotonic() + 10
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.1)


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    """A repository with the shared script library and setup stubs; bootstrap creates the venv."""
    repo = tmp_path / "repository"
    (repo / "script" / ".lib").mkdir(parents=True)
    (repo / "script" / "setup").mkdir()
    shutil.copy(ROOT / "script" / ".lib" / "output.sh", repo / "script" / ".lib" / "output.sh")
    _stub(repo, "bootstrap", "mkdir -p .local/ha-venv/bin && touch .local/ha-venv/bin/activate")
    _stub(repo, "toolchain", "true")
    subprocess.run(["git", "init", "--quiet"], cwd=repo, check=True)
    return repo


def _environment(home: Path, **env: str) -> dict[str, str]:
    """A clean environment: the caller's, a CI runner's or a dev container's markers would change what the hook sees."""
    return {"HOME": str(home), "PATH": "/usr/bin:/bin", "MISE_DATA_DIR": str(home / "mise"), "LANG": "C.UTF-8", **env}


def _run(cwd: Path | None, home: Path, **env: str) -> subprocess.CompletedProcess[str]:
    """Run the hook with a SessionStart payload and an environment free of the dev container's markers."""
    payload = json.dumps({"hook_event_name": "SessionStart", **({"cwd": str(cwd)} if cwd else {})})
    return subprocess.run(
        ["bash", str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        env=_environment(home, **env),
        check=False,
        timeout=30,
    )


def _make_venv(repo: Path) -> None:
    (repo / ".local" / "ha-venv" / "bin").mkdir(parents=True)
    (repo / ".local" / "ha-venv" / "bin" / "activate").touch()


def _status(repo: Path, name: str, state: str, pid: int | None = None) -> None:
    (repo / ".local").mkdir(exist_ok=True)
    (repo / ".local" / f"{name}.status").write_text(f"{state}\n", encoding="utf-8")
    if pid is not None:
        (repo / ".local" / f"{name}.pid").write_text(f"{pid}\n", encoding="utf-8")


@pytest.mark.unit
def test_missing_cwd_does_not_block(tmp_path: Path) -> None:
    """Without a cwd the hook says so on stderr and lets the session start."""
    result = _run(None, tmp_path)
    assert result.returncode == 0
    assert result.stdout == ""
    assert "no usable cwd" in result.stderr


@pytest.mark.unit
def test_local_session_reports_missing_environment(repository: Path, tmp_path: Path) -> None:
    """On a local machine the hook tells the agent to bootstrap instead of doing it unasked."""
    env_file = tmp_path / "claude-env"
    result = _run(repository, tmp_path, CLAUDE_ENV_FILE=str(env_file))
    assert result.returncode == 0
    assert "Run script/setup/bootstrap" in result.stdout
    assert not (repository / ".local" / "ha-venv").exists()
    assert "mise env -s bash" in env_file.read_text(encoding="utf-8")


@pytest.mark.unit
def test_local_session_is_silent_when_set_up(repository: Path, tmp_path: Path) -> None:
    """A checkout that is already set up adds nothing to the agent's context."""
    _make_venv(repository)
    result = _run(repository, tmp_path)
    assert result.returncode == 0
    assert result.stdout == ""


@pytest.mark.unit
def test_toolchain_runs_in_the_background(repository: Path, tmp_path: Path) -> None:
    """The toolchain check never holds up the session; it runs with the session's environment."""
    record = repository / "toolchain-env"
    _stub(repository, "toolchain", f'sleep 1; echo "${{REMOTE_CONTAINERS:-}}" >"{record}"')
    _make_venv(repository)

    started = time.monotonic()
    _run(repository, tmp_path, REMOTE_CONTAINERS="true")

    assert time.monotonic() - started < 1
    _wait_for(record.exists)
    assert record.read_text(encoding="utf-8").strip() == "true"


@pytest.mark.unit
def test_cloud_session_bootstraps_in_background(repository: Path, tmp_path: Path) -> None:
    """A cloud session starts the bootstrap itself, which records how it ended."""
    result = _run(repository, tmp_path, CLAUDE_CODE_REMOTE="true")
    assert result.returncode == 0
    assert "being set up in the background" in result.stdout
    status = repository / ".local" / "bootstrap.status"
    _wait_for(lambda: status.is_file() and status.read_text(encoding="utf-8").strip() == "done")
    assert status.read_text(encoding="utf-8").strip() == "done"
    assert (repository / ".local" / "ha-venv" / "bin" / "activate").exists()

    again = _run(repository, tmp_path, CLAUDE_CODE_REMOTE="true")
    assert again.stdout == ""


@pytest.mark.unit
def test_cloud_session_reports_a_failed_setup_despite_a_venv(repository: Path, tmp_path: Path) -> None:
    """A bootstrap that created the venv and then failed is not mistaken for a finished one."""
    _make_venv(repository)
    _status(repository, "bootstrap", "failed")

    result = _run(repository, tmp_path, CLAUDE_CODE_REMOTE="true")

    assert "failed" in result.stdout


@pytest.mark.unit
def test_running_bootstrap_is_not_started_twice(repository: Path, tmp_path: Path) -> None:
    """A bootstrap already running, like the dev container's own setup, is reported instead of requested again."""
    with subprocess.Popen(["sleep", "10"]) as bootstrap:
        try:
            _status(repository, "bootstrap", "running", bootstrap.pid)
            result = _run(repository, tmp_path)
        finally:
            bootstrap.kill()
    assert "already running" in result.stdout
    assert "Run script/setup/bootstrap" not in result.stdout


@pytest.mark.unit
def test_dead_run_does_not_count_as_running(repository: Path, tmp_path: Path) -> None:
    """A status left at running by a process that is gone does not hide a missing environment."""
    with subprocess.Popen(["true"]) as finished:
        finished.wait()
    _status(repository, "bootstrap", "running", finished.pid)

    result = _run(repository, tmp_path)

    assert "Run script/setup/bootstrap" in result.stdout


@pytest.mark.unit
def test_run_by_hand_does_not_wait_for_input(repository: Path, tmp_path: Path) -> None:
    """From a terminal the hook works in the current directory instead of waiting for a payload on stdin."""
    _make_venv(repository)
    controller, terminal = pty.openpty()
    try:
        result = subprocess.run(
            ["bash", str(HOOK)],
            stdin=terminal,
            cwd=repository,
            capture_output=True,
            text=True,
            env=_environment(tmp_path),
            timeout=10,
            check=False,
        )
    finally:
        os.close(terminal)
        os.close(controller)
    assert result.returncode == 0
    assert "ready" in result.stderr
