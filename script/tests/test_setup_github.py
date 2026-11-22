"""Tests for script/setup/github, which applies the repository's GitHub settings and rulesets."""

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

SCRIPT_DIR = Path(__file__).parents[1]
ROOT = SCRIPT_DIR.parent

# A gh that records every write and answers the few reads the script makes.
FAKE_GH = """#!/bin/bash
case "$1 $2" in
"auth status") exit 0 ;;
"repo view") echo owner/repo; exit 0 ;;
esac
if [[ $1 == api && $2 != -X ]]; then
    case "$2" in
    repos/owner/repo) echo "$PRIVATE" ;;
    repos/owner/repo/rulesets) echo "${EXISTING:-[]}" ;;
    repos/owner/repo/issues*) [[ $RENOVATE == yes ]] && echo 1 || echo 0 ;;
    */contents/.github/workflows/codeql.yml) [[ $CODEQL == yes ]] || exit 1 ;;
    esac
    exit 0
fi
echo "$* $(cat 2>/dev/null)" >>"$CALLS"
"""


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    """A repository with the setup script, its library, a ruleset and a Dependabot config."""
    repo = tmp_path / "repository"
    (repo / "script" / "setup").mkdir(parents=True)
    (repo / "script" / ".lib").mkdir()
    shutil.copy(SCRIPT_DIR / "setup" / "github", repo / "script" / "setup" / "github")
    shutil.copy(SCRIPT_DIR / ".lib" / "output.sh", repo / "script" / ".lib" / "output.sh")
    (repo / ".github" / "rulesets").mkdir(parents=True)
    shutil.copy(ROOT / ".github" / "rulesets" / "main.json", repo / ".github" / "rulesets" / "main.json")
    (repo / ".github" / "dependabot.yml").write_text("version: 2\n", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "gh").write_text(FAKE_GH, encoding="utf-8")
    (bin_dir / "gh").chmod(0o755)
    return repo


def _setup(
    repo: Path, *args: str, private: bool = False, existing: str = "", codeql: bool = False, renovate: bool = False
) -> tuple[list[str], str]:
    calls = repo.parent / "calls"
    env = {
        **os.environ,
        "PATH": f"{repo.parent / 'bin'}:{os.environ['PATH']}",
        "CALLS": str(calls),
        "PRIVATE": "true" if private else "false",
        "EXISTING": existing,
        "CODEQL": "yes" if codeql else "no",
        "RENOVATE": "yes" if renovate else "no",
    }
    result = subprocess.run(
        ["bash", "script/setup/github", *args], cwd=repo, capture_output=True, text=True, env=env, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return (calls.read_text(encoding="utf-8").splitlines() if calls.exists() else []), result.stdout


@pytest.mark.unit
def test_dry_run_changes_nothing(repository: Path) -> None:
    """--dry-run makes no write call."""
    assert _setup(repository, "--dry-run")[0] == []


@pytest.mark.unit
def test_public_repository_gets_the_free_security_features(repository: Path) -> None:
    """A public repository gets secret scanning, push protection, alerts and the ruleset."""
    calls, _ = _setup(repository)

    patch = next(call for call in calls if call.startswith("api -X PATCH repos/owner/repo "))
    body = json.loads(patch.split("--input - ", 1)[1])
    assert body["security_and_analysis"]["secret_scanning_push_protection"] == {"status": "enabled"}
    assert (body["allow_squash_merge"], body["allow_merge_commit"], body["allow_rebase_merge"]) == (True, False, True)
    assert body["squash_merge_commit_title"] == "PR_TITLE"
    assert any("vulnerability-alerts" in call for call in calls)
    assert any("automated-security-fixes" in call for call in calls)
    assert any("fork-pr-contributor-approval" in call and "all_external_contributors" in call for call in calls)
    assert any(call.startswith("api -X POST repos/owner/repo/rulesets ") for call in calls)


@pytest.mark.unit
def test_existing_ruleset_is_updated_by_name(repository: Path) -> None:
    """A ruleset of the same name is replaced in place instead of added a second time."""
    calls, _ = _setup(repository, existing='[{"id": 12, "name": "main"}]')

    assert any(call.startswith("api -X PUT repos/owner/repo/rulesets/12 ") for call in calls)
    assert not any("POST repos/owner/repo/rulesets" in call for call in calls)


@pytest.mark.unit
def test_private_repository_skips_the_paid_features(repository: Path) -> None:
    """Secret scanning and CodeQL cost money on a private repository, so the script leaves them alone."""
    calls, _ = _setup(repository, private=True, codeql=True)

    assert not any("secret_scanning" in call for call in calls)
    assert not any("default-setup" in call for call in calls)


@pytest.mark.unit
def test_codeql_default_setup_goes_off_only_with_the_workflow_in_place(repository: Path) -> None:
    """The default setup stays until codeql.yml is on the default branch, so the code is never left unanalysed."""
    assert not any("default-setup" in call for call in _setup(repository)[0])
    (repository.parent / "calls").unlink()
    assert any("default-setup" in call for call in _setup(repository, codeql=True)[0])


@pytest.mark.unit
def test_merge_methods_follow_the_ruleset(repository: Path) -> None:
    """A repository that allows more merge methods in its ruleset gets them in its settings too."""
    ruleset = repository / ".github" / "rulesets" / "main.json"
    rules = json.loads(ruleset.read_text(encoding="utf-8"))
    for rule in rules["rules"]:
        if rule["type"] == "pull_request":
            rule["parameters"]["allowed_merge_methods"] = ["squash", "rebase"]
    ruleset.write_text(json.dumps(rules), encoding="utf-8")

    patch = next(call for call in _setup(repository)[0] if call.startswith("api -X PATCH repos/owner/repo "))
    body = json.loads(patch.split("--input - ", 1)[1])

    assert (body["allow_squash_merge"], body["allow_merge_commit"], body["allow_rebase_merge"]) == (True, False, True)


@pytest.mark.unit
def test_reports_whether_renovate_is_active(repository: Path) -> None:
    """The install hint appears only where Renovate has left no trace yet."""
    assert "Install the Renovate app" in _setup(repository, "--dry-run")[1]
    output = _setup(repository, "--dry-run", renovate=True)[1]
    assert "Renovate is active" in output
    assert "Install the Renovate app" not in output
