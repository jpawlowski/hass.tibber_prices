"""Tests for script/setup/toolchain, which installs the tools mise.toml pins."""

import os
from pathlib import Path
import shutil
import subprocess

import pytest

SCRIPT_DIR = Path(__file__).parents[1]


@pytest.mark.unit
def test_own_machine_without_mise_falls_back_to_path(tmp_path: Path) -> None:
    """Outside an environment the project owns, a missing mise is reported, not installed."""
    repo = tmp_path / "repository"
    (repo / "script" / "setup").mkdir(parents=True)
    (repo / "script" / ".lib").mkdir()
    shutil.copy(SCRIPT_DIR / "setup" / "toolchain", repo / "script" / "setup" / "toolchain")
    for library in ("output.sh", "download.sh"):
        shutil.copy(SCRIPT_DIR / ".lib" / library, repo / "script" / ".lib" / library)
    (repo / "mise.toml").write_text('min_version = "2026.10.22"\n', encoding="utf-8")
    env = {key: value for key, value in os.environ.items() if key not in {"REMOTE_CONTAINERS", "CODESPACES"}}
    env.update({"HOME": str(tmp_path), "PATH": "/usr/bin:/bin", "MISE_DATA_DIR": str(tmp_path / "mise")})
    env.pop("CLAUDE_CODE_REMOTE", None)

    result = subprocess.run(
        ["bash", "script/setup/toolchain"], cwd=repo, capture_output=True, text=True, env=env, check=False
    )

    assert result.returncode == 0, result.stderr
    assert "mise not found" in result.stdout + result.stderr
    assert not (tmp_path / ".local" / "bin" / "mise").exists()
