"""Tests for script/.lib/output.sh, the library every script sources."""

import os
from pathlib import Path
import subprocess

import pytest

LIBRARY = Path(__file__).parents[1] / ".lib" / "output.sh"


def _bash(cwd: Path, script: str, **env: str) -> subprocess.CompletedProcess[str]:
    base = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}
    base.update({"HOME": str(cwd), "PATH": "/usr/bin:/bin", **env})
    return subprocess.run(
        ["bash", "-c", f'source "{LIBRARY}"; {script}'], cwd=cwd, capture_output=True, text=True, env=base, check=False
    )


@pytest.mark.unit
def test_scripts_get_what_mise_resolves(tmp_path: Path) -> None:
    """With mise and a mise.toml, a script runs with mise's PATH and venv, whatever its caller activated."""
    fake = tmp_path / "bin"
    fake.mkdir()
    (fake / "mise").write_text(
        "#!/bin/bash\necho 'export PATH=\"/venv/bin:$PATH\"; export VIRTUAL_ENV=/venv'\n", encoding="utf-8"
    )
    (fake / "mise").chmod(0o755)
    (tmp_path / "mise.toml").write_text("[tools]\n", encoding="utf-8")

    result = _bash(tmp_path, 'printf "%s %s" "$VIRTUAL_ENV" "${PATH%%:*}"', PATH=f"{fake}:/usr/bin:/bin")

    assert result.stdout == "/venv /venv/bin"


@pytest.mark.unit
def test_without_mise_nothing_changes(tmp_path: Path) -> None:
    """A machine without mise keeps its own PATH; the scripts fall back to it."""
    result = _bash(tmp_path, 'printf "%s" "$PATH"')

    assert result.stdout == "/usr/bin:/bin"


@pytest.mark.unit
@pytest.mark.parametrize(("exit_code", "state"), [(0, "done"), (3, "failed")])
def test_track_run_records_the_outcome(tmp_path: Path, exit_code: int, state: str) -> None:
    """A tracked script ends up done or failed, and leaves no PID behind."""
    _bash(tmp_path, f"track_run setup; exit {exit_code}")

    assert _bash(tmp_path, "run_state setup").stdout == state
    assert not (tmp_path / ".local" / "setup.pid").exists()


@pytest.mark.unit
def test_dead_process_counts_as_failed(tmp_path: Path) -> None:
    """A run whose process vanished without recording its end is not still running."""
    (tmp_path / ".local").mkdir()
    (tmp_path / ".local" / "setup.status").write_text("running\n", encoding="utf-8")
    with subprocess.Popen(["true"]) as finished:
        finished.wait()
    (tmp_path / ".local" / "setup.pid").write_text(f"{finished.pid}\n", encoding="utf-8")

    assert _bash(tmp_path, "run_state setup").stdout == "failed"


@pytest.mark.unit
def test_exclusive_run_refuses_a_second_one(tmp_path: Path) -> None:
    """While a run is alive, an exclusive second one stops instead of competing for the environment."""
    with subprocess.Popen(["sleep", "10"]) as alive:
        try:
            (tmp_path / ".local").mkdir()
            (tmp_path / ".local" / "setup.status").write_text("running\n", encoding="utf-8")
            (tmp_path / ".local" / "setup.pid").write_text(f"{alive.pid}\n", encoding="utf-8")
            result = _bash(tmp_path, "track_run setup --exclusive; echo started")
        finally:
            alive.kill()

    assert result.returncode != 0
    assert "already running" in result.stdout + result.stderr
    assert "started" not in result.stdout


@pytest.mark.unit
def test_wait_for_run_returns_once_the_other_run_ends(tmp_path: Path) -> None:
    """A second run waits for the first instead of working on the same environment beside it."""
    (tmp_path / ".local").mkdir()
    (tmp_path / ".local" / "setup.status").write_text("running\n", encoding="utf-8")
    # Started through a shell that exits at once, so the system reaps it when it ends, as with a real run.
    pid = subprocess.run(
        ["bash", "-c", "sleep 1 >/dev/null 2>&1 & echo $!"], capture_output=True, text=True, check=True
    ).stdout
    (tmp_path / ".local" / "setup.pid").write_text(pid, encoding="utf-8")
    result = _bash(tmp_path, "wait_for_run setup 10 && run_state setup")

    assert result.returncode == 0
    assert result.stdout.endswith("failed")


@pytest.mark.unit
def test_wait_for_run_gives_up_at_its_limit(tmp_path: Path) -> None:
    """A run that never ends does not hold the next one forever."""
    with subprocess.Popen(["sleep", "10"]) as other:
        try:
            (tmp_path / ".local").mkdir()
            (tmp_path / ".local" / "setup.status").write_text("running\n", encoding="utf-8")
            (tmp_path / ".local" / "setup.pid").write_text(f"{other.pid}\n", encoding="utf-8")
            result = _bash(tmp_path, "wait_for_run setup 1")
        finally:
            other.kill()

    assert result.returncode == 1
