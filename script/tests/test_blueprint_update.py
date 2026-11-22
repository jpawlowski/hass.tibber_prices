"""Tests for script/blueprint-update, which carries blueprint changes into files template sync never ships."""

import json
from pathlib import Path
import shutil
import subprocess

import pytest

SCRIPT_DIR = Path(__file__).parents[1]


def _commit(repo: Path, files: dict[str, str], message: str) -> None:
    for relative, content in files.items():
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "--quiet", "-m", message], cwd=repo, check=True)


def _init(repo: Path) -> None:
    repo.mkdir()
    for command in (
        ["git", "init", "--quiet", "--initial-branch=main"],
        ["git", "config", "user.email", "test@example.com"],
        ["git", "config", "user.name", "Update Test"],
    ):
        subprocess.run(command, cwd=repo, check=True)


def _identity(domain: str, title: str, owner: str, repository: str, prefix: str) -> dict[str, str]:
    manifest = {"domain": domain, "name": title, "documentation": f"https://github.com/{owner}/{repository}"}
    return {
        f"custom_components/{domain}/manifest.json": json.dumps(manifest),
        f"custom_components/{domain}/coordinator.py": f"class {prefix}DataUpdateCoordinator:\n    pass\n",
    }


@pytest.fixture
def repos(tmp_path: Path) -> tuple[Path, Path]:
    """A blueprint with one commit and a project generated from it under its own names."""
    blueprint = tmp_path / "blueprint"
    _init(blueprint)
    _commit(
        blueprint,
        {
            **_identity("blue_domain", "Blue Title", "blue-owner", "blue.repo", "BluePrefix"),
            "AGENTS.md": "# Agents for Blue Title\n\nUse `blue_domain` and BluePrefixEntity.\n",
        },
        "first",
    )
    project = tmp_path / "project"
    _init(project)
    (project / "script" / ".lib").mkdir(parents=True)
    shutil.copy(SCRIPT_DIR / "blueprint-update", project / "script" / "blueprint-update")
    shutil.copy(SCRIPT_DIR / ".lib" / "output.sh", project / "script" / ".lib" / "output.sh")
    shutil.copy(SCRIPT_DIR / ".lib" / "blueprint_update.py", project / "script" / ".lib" / "blueprint_update.py")
    _commit(
        project,
        {
            **_identity("my_device", "My Device", "me", "my-device", "MyDevice"),
            "AGENTS.md": "# Agents for My Device\n\nUse `my_device` and MyDeviceEntity.\n\nOur own rule.\n",
            ".github/workflows/template-sync.yml": "source_repo_path: blue-owner/blue.repo\nupstream_branch: main\n",
        },
        "project",
    )
    return blueprint, project


def _update(project: Path, blueprint: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "script/blueprint-update", f"--source={blueprint}", *args],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.unit
def test_first_run_compares_with_the_blueprint_in_this_repositorys_names(repos: tuple[Path, Path]) -> None:
    """Without a record the diff is against the blueprint, spelled with the project's own names."""
    blueprint, project = repos

    result = _update(project, blueprint)

    assert result.returncode == 0, result.stderr
    assert "-Our own rule." in result.stdout
    assert "blue_domain" not in result.stdout
    assert "BluePrefix" not in result.stdout


@pytest.mark.unit
def test_after_record_only_new_blueprint_changes_show(repos: tuple[Path, Path]) -> None:
    """Once recorded, the diff holds what the blueprint changed since — not the project's own additions."""
    blueprint, project = repos
    assert _update(project, blueprint, "--record").returncode == 0
    assert _update(project, blueprint, "--files").stdout.strip() == ""

    _commit(
        blueprint,
        {
            "AGENTS.md": "# Agents for Blue Title\n\nUse `blue_domain` and BluePrefixEntity.\n\nNew rule for Blue Title.\n"
        },
        "second",
    )
    result = _update(project, blueprint)

    assert "+New rule for My Device." in result.stdout
    assert "Our own rule" not in result.stdout
    assert _update(project, blueprint, "--files").stdout.strip() == "AGENTS.md"


@pytest.mark.unit
def test_refuses_in_the_blueprint_itself(repos: tuple[Path, Path]) -> None:
    """A repository that still has initialize.sh is the blueprint, or not initialised yet."""
    blueprint, project = repos
    (project / "initialize.sh").write_text("#!/bin/bash\n", encoding="utf-8")

    result = _update(project, blueprint)

    assert result.returncode == 2
    assert "nothing to update from" in result.stderr


@pytest.mark.unit
def test_files_initialize_leaves_unrenamed_compare_as_they_are(repos: tuple[Path, Path]) -> None:
    """A file that names the blueprint on purpose, like the release workflow, is not reported as changed."""
    blueprint, project = repos
    workflow = {".github/workflows/release-please.yml": "repo: blue-owner/blue.repo\n"}
    _commit(blueprint, {**workflow, "initialize.sh": 'exclude_files=(\n    "release-please.yml"\n)\n'}, "release")
    _commit(project, workflow, "release")

    result = _update(project, blueprint, "--files")

    assert "release-please.yml" not in result.stdout


@pytest.mark.unit
def test_recorded_identity_wins_over_the_code(repos: tuple[Path, Path]) -> None:
    """The names initialize.sh recorded still apply after the project renamed the class they were read from."""
    blueprint, project = repos
    _commit(project, {"custom_components/my_device/coordinator.py": "class Renamed:\n    pass\n"}, "rename")
    (project / ".agents").mkdir(exist_ok=True)
    (project / ".agents" / "blueprint-update.json").write_text(
        json.dumps({"identity": {"prefix": "MyDevice"}}), encoding="utf-8"
    )

    result = _update(project, blueprint)

    assert result.returncode == 0, result.stderr
    assert "BluePrefix" not in result.stdout
