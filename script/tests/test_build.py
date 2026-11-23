"""Tests for script/build, in a throwaway repository so no real hook is touched."""

import json
from pathlib import Path
import shutil
import subprocess
import zipfile

import pytest

SCRIPT_DIR = Path(__file__).parents[1]


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Return a git repository with script/build, its libraries and a tracked integration."""
    (tmp_path / "script" / ".lib").mkdir(parents=True)
    shutil.copy2(SCRIPT_DIR / "build", tmp_path / "script" / "build")
    for library in ("output.sh", "integration.sh"):
        shutil.copy2(SCRIPT_DIR / ".lib" / library, tmp_path / "script" / ".lib" / library)
    integration = tmp_path / "custom_components" / "demo"
    integration.mkdir(parents=True)
    (integration / "__init__.py").write_text('"""Demo."""\n', encoding="utf-8")
    (integration / "manifest.json").write_text(json.dumps({"domain": "demo", "version": "1.2.3"}), encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "custom_components"], cwd=tmp_path, check=True)
    return tmp_path


def _build(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bash", "script/build", *args], cwd=repo, capture_output=True, text=True, check=False)


@pytest.mark.unit
def test_zip_holds_tracked_files_at_its_root(repo: Path) -> None:
    """The archive root is the integration folder, and untracked files stay out."""
    (repo / "custom_components" / "demo" / "scratch.txt").write_text("not tracked", encoding="utf-8")

    result = _build(repo, "--zip", "demo.zip", "--version", "1.2.3")

    assert result.returncode == 0, result.stdout + result.stderr
    assert sorted(zipfile.ZipFile(repo / "demo.zip").namelist()) == ["__init__.py", "manifest.json"]


@pytest.mark.unit
def test_version_mismatch_fails(repo: Path) -> None:
    """A tag that does not match manifest.json stops the build."""
    result = _build(repo, "--version", "9.9.9")

    assert result.returncode != 0
    assert "not 9.9.9" in result.stdout + result.stderr


@pytest.mark.unit
def test_build_hook_adds_files_to_the_zip(repo: Path) -> None:
    """What script/hooks/build.post.sh writes into BUILD_DIR ships."""
    (repo / "script" / "hooks").mkdir()
    (repo / "script" / "hooks" / "build.post.sh").write_text(
        'mkdir -p "$BUILD_DIR/frontend" && echo "bundle" > "$BUILD_DIR/frontend/cards.js"\n', encoding="utf-8"
    )

    result = _build(repo, "--zip", "demo.zip")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "frontend/cards.js" in zipfile.ZipFile(repo / "demo.zip").namelist()


@pytest.mark.unit
def test_pre_hook_output_survives_and_hooks_may_change_directory(repo: Path) -> None:
    """What build.pre.sh writes ships, and a hook that changes directory still writes into BUILD_DIR."""
    hooks = repo / "script" / "hooks"
    hooks.mkdir()
    (hooks / "build.pre.sh").write_text('cd /tmp && echo "data" > "$BUILD_DIR/data.json"\n', encoding="utf-8")
    (hooks / "build.post.sh").write_text('cd / && touch "$BUILD_DIR/post.js"\n', encoding="utf-8")

    result = _build(repo, "--zip", "demo.zip")

    assert result.returncode == 0, result.stdout + result.stderr
    assert {"data.json", "post.js"} <= set(zipfile.ZipFile(repo / "demo.zip").namelist())


@pytest.mark.unit
@pytest.mark.parametrize("output", [".", "..", "custom_components/demo", "custom_components/demo/sub"])
def test_output_that_would_delete_the_source_is_refused(repo: Path, output: str) -> None:
    """The build folder is emptied first, so it may not contain the repository or sit in the integration."""
    result = _build(repo, "--output", output)

    assert result.returncode != 0
    assert (repo / "custom_components" / "demo" / "manifest.json").exists()


@pytest.mark.unit
def test_in_place_runs_the_hook_on_the_integration_folder(repo: Path) -> None:
    """--in-place generates next to the code, for script/develop."""
    (repo / "script" / "hooks").mkdir()
    (repo / "script" / "hooks" / "build.post.sh").write_text('touch "$BUILD_DIR/generated.js"\n', encoding="utf-8")

    result = _build(repo, "--in-place")

    assert result.returncode == 0, result.stdout + result.stderr
    assert (repo / "custom_components" / "demo" / "generated.js").exists()
