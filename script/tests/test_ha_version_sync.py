"""Tests for script/ha-version-sync, against a stand-in for PyPI."""

from collections.abc import Generator
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest

SCRIPT_DIR = Path(__file__).parents[1]
RELEASES = {
    ("homeassistant", "2026.11.9"): {"requires_python": ">=3.14.2"},
    ("homeassistant", "2026.10.4"): {"requires_python": ">=3.14.2"},
    ("pytest-homeassistant-custom-component", "0.13.375"): {"requires_dist": ["homeassistant==2026.10.4"]},
}


@pytest.fixture
def pypi(tmp_path: Path) -> Generator[str]:
    """Serve RELEASES the way PyPI's JSON API does, from a separate process the socket guard does not cover."""
    root = tmp_path / "pypi"
    for (package, version), info in RELEASES.items():
        (root / package / version).mkdir(parents=True)
        (root / package / version / "json").write_text(json.dumps({"info": info}), encoding="utf-8")
    server = subprocess.Popen(
        [sys.executable, "-u", "-m", "http.server", "0", "--bind", "127.0.0.1", "--directory", str(root)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    assert server.stdout is not None
    port = re.search(r"port (\d+)", server.stdout.readline())
    assert port is not None
    yield f"http://127.0.0.1:{port.group(1)}"
    server.terminate()
    server.wait()
    server.stdout.close()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repository holding the script and the files it reads, without an HA_VERSION override or workflows."""
    root = tmp_path / "repo"
    (root / "script" / ".lib").mkdir(parents=True)
    shutil.copy(SCRIPT_DIR / "ha-version-sync", root / "script" / "ha-version-sync")
    shutil.copy(SCRIPT_DIR / ".lib" / "output.sh", root / "script" / ".lib" / "output.sh")
    (root / "pyproject.toml").write_text('requires-python = ">=3.14"\n', encoding="utf-8")
    (root / "mise.toml").write_text('[tools]\npython = "3.14.9"\n', encoding="utf-8")
    return root


def _run(repo: Path, pypi: str, pin: str, minimum: str) -> subprocess.CompletedProcess[str]:
    """Run the script with this test pin and hacs.json minimum."""
    (repo / "requirements_test.txt").write_text(f"{pin}\n", encoding="utf-8")
    (repo / "hacs.json").write_text(json.dumps({"homeassistant": minimum}), encoding="utf-8")
    return subprocess.run(
        [str(repo / "script" / "ha-version-sync")],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "HA_VERSION_SYNC_PYPI_URL": pypi},
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("pin", "minimum", "reported"),
    [
        pytest.param("pytest-homeassistant==2026.11.9", "2026.11.0", "2026.11.9 (train 2026.11)", id="new-package"),
        pytest.param(
            "pytest-homeassistant==2026.11.9.post1", "2026.11.0", "2026.11.9 (train 2026.11)", id="repackaged"
        ),
        pytest.param(
            "pytest-homeassistant-custom-component==0.13.375",
            "2026.10.0",
            "2026.10.4 (train 2026.10)",
            id="old-package",
        ),
    ],
)
def test_matching_trains_pass(repo: Path, pypi: str, pin: str, minimum: str, reported: str) -> None:
    """Either package passes when its Home Assistant release is on the hacs.json train, Python check included."""
    result = _run(repo, pypi, pin, minimum)

    assert result.returncode == 0, result.stderr
    assert f"{pin}: {reported}" in result.stdout
    assert ">=3.14.2" in result.stdout
    assert "WARNING" not in result.stderr


@pytest.mark.unit
@pytest.mark.parametrize("pin", ["pytest-homeassistant==2026.11.9", "pytest-homeassistant-custom-component==0.13.375"])
def test_a_train_mismatch_fails(repo: Path, pypi: str, pin: str) -> None:
    """A pin on another train than hacs.json fails, whichever package it names."""
    result = _run(repo, pypi, pin, "2026.12.0")

    assert result.returncode == 1
    assert "release train mismatch" in result.stderr


@pytest.mark.unit
def test_a_missing_pin_fails(repo: Path, pypi: str) -> None:
    """Without either package in requirements_test.txt there is nothing to compare."""
    result = _run(repo, pypi, "pytest==9.0.3", "2026.11.0")

    assert result.returncode == 1
    assert "pin not found" in result.stderr
