"""Regression tests for synchronized skill catalogue validation."""

from pathlib import Path
import subprocess
import sys

import pytest

CHECKER = Path(__file__).parents[1] / ".lib" / "skills_check.py"


def _write_minimal_skill_repository(path: Path, *, blueprint: bool) -> None:
    """Create a repository whose README, but not AGENTS.md, lists one skill."""
    skill_dir = path / ".agents" / "skills" / "example-skill"
    skill_dir.mkdir(parents=True)
    (path / ".agents" / "instructions").mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: example-skill\ndescription: Validate the test catalogue behavior.\n---\n\n# Example skill\n",
        encoding="utf-8",
    )
    (path / ".agents" / "skills" / "README.md").write_text(
        "[`example-skill`](example-skill/SKILL.md)\n",
        encoding="utf-8",
    )
    (path / "AGENTS.md").write_text(
        "<!-- repo-role:start -->\nRepository role\n<!-- repo-role:end -->\n",
        encoding="utf-8",
    )
    if blueprint:
        (path / "initialize.sh").write_text("#!/bin/bash\n", encoding="utf-8")


@pytest.mark.unit
@pytest.mark.parametrize(("blueprint", "expected_returncode"), [(False, 0), (True, 1)])
def test_agents_catalogue_is_required_only_in_blueprint(
    tmp_path: Path,
    *,
    blueprint: bool,
    expected_returncode: int,
) -> None:
    """Template sync may add a skill without replacing downstream AGENTS.md."""
    _write_minimal_skill_repository(tmp_path, blueprint=blueprint)

    result = subprocess.run(
        [sys.executable, str(CHECKER)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == expected_returncode
    if blueprint:
        assert "example-skill is not linked from this catalogue" in result.stdout
    else:
        assert "1 synchronized catalogue(s) are complete" in result.stdout


@pytest.mark.unit
@pytest.mark.parametrize(("routed", "expected_returncode"), [(False, 1), (True, 0)])
def test_project_instructions_file_needs_a_routing_row(
    tmp_path: Path,
    *,
    routed: bool,
    expected_returncode: int,
) -> None:
    """Codex and OpenCode find a project instructions file only through AGENTS.md."""
    _write_minimal_skill_repository(tmp_path, blueprint=False)
    patterns = "custom_components/**/periods/**/*.py"
    (tmp_path / ".agents" / "instructions" / "myint.periods.instructions.md").write_text(
        f'---\nname: "Periods"\ndescription: "Period rules"\napplyTo: "{patterns}"\npaths:\n  - "{patterns}"\n---\n\n'
        "# Periods\n",
        encoding="utf-8",
    )
    if routed:
        with (tmp_path / "AGENTS.md").open("a", encoding="utf-8") as agents:
            agents.write("| periods | — | `myint.periods` |\n")

    result = subprocess.run(
        [sys.executable, str(CHECKER)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == expected_returncode, result.stdout
    assert ("does not name myint.periods" in result.stdout) is not routed
