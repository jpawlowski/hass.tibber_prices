"""Regression tests for the synchronized agent protected-path checker."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

CHECKER = Path(__file__).parents[1] / ".lib" / "agent_policy_check.py"

CLAUDE = {
    "permissions": {"deny": ["Read(**/.env.local*)", "Edit(**/.env.local*)", "Edit(./.git/**)", "Edit(./x.json)"]}
}
OPENCODE = {
    "permissions": [
        {"action": "read", "resource": "*.env.local*", "effect": "deny"},
        {"action": "edit", "resource": "*.env.local*", "effect": "deny"},
        {"action": "edit", "resource": ".git/*", "effect": "deny"},
        {"action": "edit", "resource": "x.json", "effect": "deny"},
    ]
}
AUTO_APPROVE = {"**/.env.*": False, "**/.git/**": False, "x.json": False}
UNCOVERED = {key: value for key, value in AUTO_APPROVE.items() if key != "x.json"}
EXTRA_OPENCODE_RULE = {"action": "edit", "resource": "y.json", "effect": "deny"}
ALLOW_RULE = {**OPENCODE["permissions"][2], "effect": "allow"}


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _invoke(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(CHECKER)], cwd=root, capture_output=True, text=True, check=False)


def _run_checker(
    tmp_path: Path,
    *,
    claude: dict = CLAUDE,
    opencode: dict = OPENCODE,
    devcontainer_approve: dict = AUTO_APPROVE,
    default_approve: dict = AUTO_APPROVE,
) -> subprocess.CompletedProcess[str]:
    """Run the checker against one set of agent configuration files."""
    _write(tmp_path, ".devcontainer/claude-code/managed-settings.json", json.dumps(claude))
    _write(tmp_path, ".devcontainer/opencode/opencode.json", json.dumps(opencode))
    devcontainer = {"customizations": {"vscode": {"settings": {"chat.tools.edits.autoApprove": devcontainer_approve}}}}
    _write(tmp_path, ".devcontainer/devcontainer.json", "// JSONC header\n" + json.dumps(devcontainer, indent=2))
    _write(tmp_path, ".vscode/settings.default.jsonc", json.dumps({"chat.tools.edits.autoApprove": default_approve}))
    return _invoke(tmp_path)


@pytest.mark.unit
def test_accepts_matching_lists(tmp_path: Path) -> None:
    """Equivalent rules written in each tool's own syntax pass."""
    result = _run_checker(tmp_path)

    assert result.returncode == 0, result.stdout


@pytest.mark.unit
@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        pytest.param({"opencode": {"permissions": OPENCODE["permissions"][:-1]}}, '"resource": "x.json"', id="missing"),
        pytest.param(
            {"opencode": {"permissions": [*OPENCODE["permissions"], EXTRA_OPENCODE_RULE]}},
            "has no counterpart",
            id="opencode-only",
        ),
        pytest.param(
            {"devcontainer_approve": UNCOVERED, "default_approve": UNCOVERED}, "needs 'x.json': false", id="uncovered"
        ),
        pytest.param({"default_approve": {**AUTO_APPROVE, "**/.env": False}}, "differs from", id="diverging-vscode"),
        pytest.param(
            {"claude": {"permissions": {"deny": [*CLAUDE["permissions"]["deny"], "Edit(docs/*.md)"]}}},
            "must be Read(**/…)",
            id="unsupported-claude-pattern",
        ),
        pytest.param(
            {"opencode": {"permissions": [*OPENCODE["permissions"], ALLOW_RULE]}},
            "can lift a protection",
            id="opencode-allow-rule",
        ),
    ],
)
def test_reports_disagreement(tmp_path: Path, overrides: dict, expected: str) -> None:
    """Every kind of disagreement fails the check and names the offending entry."""
    result = _run_checker(tmp_path, **overrides)

    assert result.returncode == 1
    assert expected in result.stdout


@pytest.mark.unit
def test_reports_unparsable_file(tmp_path: Path) -> None:
    """A broken JSONC file is reported by name instead of crashing with a traceback."""
    _run_checker(tmp_path)
    (tmp_path / ".devcontainer" / "devcontainer.json").write_text("{ /* unclosed", encoding="utf-8")

    result = _invoke(tmp_path)

    assert result.returncode == 1
    assert ".devcontainer/devcontainer.json: cannot parse (unclosed block comment)" in result.stdout


@pytest.mark.unit
def test_accepts_matching_project_configs(tmp_path: Path) -> None:
    """The committed Claude Code and OpenCode configurations may mirror the managed list."""
    _write(tmp_path, ".claude/settings.json", json.dumps({**CLAUDE, "env": {"GIT_TERMINAL_PROMPT": "0"}}))
    _write(tmp_path, "opencode.json", json.dumps(OPENCODE))

    result = _run_checker(tmp_path)

    assert result.returncode == 0, result.stdout


@pytest.mark.unit
@pytest.mark.parametrize(
    ("relative", "content", "expected"),
    [
        pytest.param(
            ".claude/settings.json",
            {"permissions": {"deny": CLAUDE["permissions"]["deny"][:-1]}},
            '.claude/settings.json: missing "Edit(./x.json)"',
            id="claude-project-missing",
        ),
        pytest.param(
            "opencode.json",
            {"permissions": [*OPENCODE["permissions"], EXTRA_OPENCODE_RULE]},
            "opencode.json: {",
            id="opencode-project-extra",
        ),
    ],
)
def test_reports_diverging_project_config(tmp_path: Path, relative: str, content: dict, expected: str) -> None:
    """A committed configuration that protects less or more than the managed one fails the check."""
    _write(tmp_path, relative, json.dumps(content))

    result = _run_checker(tmp_path)

    assert result.returncode == 1
    assert expected in result.stdout
