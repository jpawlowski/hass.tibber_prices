"""Tests for script/template-sync-guard, which keeps newer versions a template sync would lower."""

from pathlib import Path
import subprocess
import sys

import pytest

GUARD = Path(__file__).parents[1] / ".lib" / "version_guard.py"
RENOVATE_CONFIG = Path(__file__).parents[2] / ".github" / "renovate.json"
SHA_OLD = "a" * 40
SHA_NEW = "b" * 40

BASE = {
    "mise.toml": 'min_version = "2026.10.22"\n\n[tools]\npython = "3.14.9"\nuv = "0.14.0"\n',
    "requirements_test.txt": "pytest-homeassistant==2026.11.4\n",
    "package.json": '{\n  "devDependencies": {\n    "prettier": "3.9.0",\n    "pyright": "1.1.408"\n  }\n}\n',
    ".devcontainer/devcontainer.json": (
        '{\n  "features": {\n    "ghcr.io/devcontainers-extra/features/mise:1": {\n'
        '      "version": "2026.10.22"\n    }\n  }\n}\n'
    ),
    ".github/workflows/lint.yml": (
        f"jobs:\n  a:\n    steps:\n      - uses: actions/checkout@{SHA_NEW} # v7.1.0\n"
        "      - uses: jdx/mise-action@" + SHA_NEW + " # v5.2.5\n        with:\n"
        "          # renovate: datasource=github-releases depName=jdx/mise\n"
        '          version: "2026.10.22"\n'
    ),
}

SYNCED = {
    "mise.toml": 'min_version = "2026.10.1"\n\n[tools]\npython = "3.14.9"\nuv = "0.13.7"\nfd = "10.5.0"\n',
    "requirements_test.txt": "pytest-homeassistant==2026.11.2\n",
    "package.json": '{\n  "devDependencies": {\n    "prettier": "3.8.2",\n    "pyright": "1.1.409"\n  }\n}\n',
    ".devcontainer/devcontainer.json": (
        '{\n  "features": {\n    "ghcr.io/devcontainers-extra/features/mise:1": {\n'
        '      "version": "2026.9.30"\n    }\n  }\n}\n'
    ),
    ".github/workflows/lint.yml": (
        f"jobs:\n  a:\n    steps:\n      - uses: actions/checkout@{SHA_OLD} # v7.0.1\n"
        "      - uses: jdx/mise-action@" + SHA_NEW + " # v5.2.5\n        with:\n"
        "          # renovate: datasource=github-releases depName=jdx/mise\n"
        '          version: "2026.10.1"\n'
    ),
}


def _write(root: Path, files: dict[str, str]) -> None:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


@pytest.fixture
def synced(tmp_path: Path) -> Path:
    """A repository whose committed state is BASE and whose working tree holds the sync's SYNCED."""
    for command in (
        ["git", "init", "--quiet", "--initial-branch=main"],
        ["git", "config", "user.email", "test@example.com"],
        ["git", "config", "user.name", "Guard Test"],
    ):
        subprocess.run(command, cwd=tmp_path, check=True)
    _write(tmp_path, {**BASE, ".github/renovate.json": RENOVATE_CONFIG.read_text(encoding="utf-8")})
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "--quiet", "-m", "test: base"], cwd=tmp_path, check=True)
    _write(tmp_path, SYNCED)
    return tmp_path


def _guard(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", str(GUARD), "HEAD", *args], cwd=root, capture_output=True, text=True, check=False
    )


def _read(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8")


@pytest.mark.unit
def test_restores_every_lowered_pin(synced: Path) -> None:
    """Each format gets back the repository's own, higher version; everything else stays as synced."""
    result = _guard(synced)

    assert result.returncode == 0, result.stderr
    mise = _read(synced, "mise.toml")
    assert 'min_version = "2026.10.22"' in mise
    assert 'uv = "0.14.0"' in mise
    assert 'fd = "10.5.0"' in mise
    assert "==2026.11.4" in _read(synced, "requirements_test.txt")
    package = _read(synced, "package.json")
    assert '"prettier": "3.9.0"' in package
    assert '"pyright": "1.1.409"' in package
    assert '"version": "2026.10.22"' in _read(synced, ".devcontainer/devcontainer.json")
    workflow = _read(synced, ".github/workflows/lint.yml")
    assert f"actions/checkout@{SHA_NEW} # v7.1.0" in workflow
    assert 'version: "2026.10.22"' in workflow


@pytest.mark.unit
def test_reports_what_it_kept(synced: Path) -> None:
    """The Markdown report names every restored pin with both versions."""
    result = _guard(synced)

    assert "| `mise.toml` | `uv` | 0.13.7 | 0.14.0 |" in result.stdout
    assert "| `.github/workflows/lint.yml` | `actions/checkout` | v7.0.1 | v7.1.0 |" in result.stdout
    assert "pyright" not in result.stdout


@pytest.mark.unit
def test_check_mode_changes_nothing(synced: Path) -> None:
    """--check reports and fails without touching a file."""
    result = _guard(synced, "--check")

    assert result.returncode == 1
    assert "would keep" in result.stdout
    assert _read(synced, "mise.toml") == SYNCED["mise.toml"]


@pytest.mark.unit
def test_silent_when_nothing_is_lowered(synced: Path) -> None:
    """A sync that only raises versions passes without a report."""
    _write(synced, BASE)

    result = _guard(synced, "--check")

    assert result.returncode == 0
    assert result.stdout == ""


@pytest.mark.unit
def test_each_occurrence_is_compared_on_its_own(synced: Path) -> None:
    """Two jobs pinning one action at different versions keep their own; only the lowered one is restored."""
    base = f"jobs:\n  a:\n    steps:\n      - uses: actions/checkout@{SHA_OLD} # v6.0.0\n      - uses: actions/checkout@{SHA_NEW} # v7.1.0\n"
    lowered = f"jobs:\n  a:\n    steps:\n      - uses: actions/checkout@{SHA_OLD} # v6.0.0\n      - uses: actions/checkout@{SHA_OLD} # v7.0.1\n"
    _write(synced, {".github/workflows/two.yml": base})
    subprocess.run(["git", "add", "."], cwd=synced, check=True)
    subprocess.run(["git", "commit", "--quiet", "-m", "test: two jobs"], cwd=synced, check=True)
    _write(synced, {**SYNCED, ".github/workflows/two.yml": lowered})

    _guard(synced)

    workflow = _read(synced, ".github/workflows/two.yml")
    assert f"actions/checkout@{SHA_OLD} # v6.0.0" in workflow
    assert f"actions/checkout@{SHA_NEW} # v7.1.0" in workflow


@pytest.mark.unit
def test_a_release_replaces_its_pre_release(synced: Path) -> None:
    """A beta pinned here is not kept over the stable release the template moves to."""
    _write(synced, {"requirements_test.txt": "pytest-homeassistant==2026.12.0b1\n"})
    subprocess.run(["git", "commit", "--quiet", "-am", "test: beta"], cwd=synced, check=True)
    _write(synced, {**SYNCED, "requirements_test.txt": "pytest-homeassistant==2026.12.0\n"})

    _guard(synced)

    assert "==2026.12.0\n" in _read(synced, "requirements_test.txt")


@pytest.mark.unit
def test_a_renamed_package_is_neither_restored_nor_dropped(synced: Path) -> None:
    """A pin under a new package name is new, not lower, so the old name does not come back."""
    _write(synced, {"requirements_test.txt": "pytest-homeassistant-custom-component==0.13.375\n"})
    subprocess.run(["git", "commit", "--quiet", "-am", "test: old package"], cwd=synced, check=True)
    _write(synced, {**SYNCED, "requirements_test.txt": "pytest-homeassistant==2026.11.2\n"})

    _guard(synced)

    assert _read(synced, "requirements_test.txt") == "pytest-homeassistant==2026.11.2\n"
