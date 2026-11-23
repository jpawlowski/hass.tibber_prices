"""Regression tests for synchronized agent lifecycle hooks."""

import json
from pathlib import Path
import subprocess

import pytest

HOOK = Path(__file__).parents[2] / ".agents" / "hooks" / "pre-push-check.sh"
CONFIG = "default_install_hook_types: [pre-commit, commit-msg, pre-push]\n"
BYPASS = "BLOCK skipping git hooks would skip script/push-gate; push without --no-verify or core.hooksPath"


def _initialize_repository(path: Path, *, config: str | None = CONFIG, hook_installed: bool = True) -> None:
    """Create a repository that installs git's pre-push hook unless told otherwise."""
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "--quiet", "--initial-branch=main"], cwd=path, check=True)
    if config is not None:
        (path / ".pre-commit-config.yaml").write_text(config, encoding="utf-8")
    if hook_installed:
        (path / ".git" / "hooks" / "pre-push").write_text("#!/bin/sh\n", encoding="utf-8")


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    """Return a repository with git's pre-push hook configured and installed."""
    path = tmp_path / "repository"
    _initialize_repository(path)
    return path


def _explain(command: str, cwd: Path) -> str:
    """Return the hook's explain-mode decision for one shell tool payload."""
    payload = json.dumps({"cwd": str(cwd), "tool_input": {"command": command}})
    result = subprocess.run(
        ["bash", str(HOOK), "--explain"],
        cwd=cwd,
        input=payload,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _other_refs(what: str) -> str:
    return f"BLOCK {what} sends refs script/push-gate cannot see; push the checked-out branch alone"


@pytest.mark.unit
@pytest.mark.parametrize(
    "command",
    [
        'printf "git status\\n"',
        "ls --all",
        "git fetch --tags",
        'grep -rn "git push --all" docs/',
        "git commit -m 'docs: explain why git push --no-verify skips the gate'",
        "git commit -F - <<'EOF'\nchore: block git push --tags\n\nwithout core.hooksPath\nEOF",
        "echo done # git push --mirror is documented here",
        "git config --get core.hooksPath",
        "bash -c 'grep \"git push --all\" README.md'",
    ],
)
def test_allows_text_that_only_mentions_a_push(tmp_path: Path, command: str) -> None:
    """Commit messages, here-documents, comments and searches that mention a push run no push."""
    assert _explain(command, tmp_path) == "ALLOW"


@pytest.mark.unit
@pytest.mark.parametrize(
    "command",
    [
        "git push",
        "git push origin main",
        "git push origin HEAD 2>&1 | tail -3",
        "git push --force-with-lease -u origin HEAD:main",
        "git push -o ci.skip origin main",
        "git -C . push origin main",
    ],
)
def test_allows_a_push_the_git_hook_checks(repository: Path, command: str) -> None:
    """A push of one branch is left to script/push-gate, which runs as git's pre-push hook."""
    assert _explain(command, repository) == "ALLOW"


@pytest.mark.unit
@pytest.mark.parametrize(
    "command",
    [
        "git push --no-verify",
        "git push --no-ver''ify origin main",
        'git push "--no-verify"',
        "git -c core.hooksPath=/dev/null push",
        "GIT_CONFIG_PARAMETERS=\"'core.hooksPath=/dev/null'\" git push",
        "bash -c 'git push --no-verify'",
        'echo "$(git push --no-verify)"',
        "eval git push --no-verify",
    ],
)
def test_blocks_skipping_git_hooks(repository: Path, command: str) -> None:
    """Skipping git hooks would skip the push gate, however the push is spelled or wrapped."""
    assert _explain(command, repository) == BYPASS


@pytest.mark.unit
def test_blocks_setting_hooks_path(tmp_path: Path) -> None:
    """Pointing git at another hooks directory would silently disable the gate for later pushes."""
    assert _explain("git config core.hooksPath /dev/null", tmp_path) == (
        "BLOCK setting core.hooksPath would skip script/push-gate"
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("command", "what"),
    [
        ("git push --all", "--all"),
        ("git push --mirror", "--mirror"),
        ("git push origin --tags", "--tags"),
        ("git push --follow-tags", "--follow-tags"),
        ("git -c push.followTags=true push", "push.followTags"),
        ("git push origin --delete old", "--delete"),
        ("git push -fd origin old", "-fd"),
        ("git push origin :old", ":old"),
        ("git push origin main other", "a push of several refspecs"),
    ],
)
def test_blocks_refs_the_git_hook_cannot_see(repository: Path, command: str, what: str) -> None:
    """Git's pre-push hook only sees the first ref, so several refs, tags and deletions are blocked."""
    assert _explain(command, repository) == _other_refs(what)


@pytest.mark.unit
@pytest.mark.parametrize("config", [None, "default_install_hook_types: [pre-commit, commit-msg]\n"])
def test_blocks_repository_without_pre_push_stage(tmp_path: Path, config: str | None) -> None:
    """A repository whose config does not install the pre-push hook gets a fix hint instead of an unchecked push."""
    repository = tmp_path / "repository"
    _initialize_repository(repository, config=config)

    assert _explain("git push", repository).startswith("BLOCK this repository does not install git's pre-push hook")


@pytest.mark.unit
def test_blocks_uninstalled_pre_push_hook(tmp_path: Path) -> None:
    """A configured but uninstalled hook would never run, so the push waits for prek install."""
    repository = tmp_path / "repository"
    _initialize_repository(repository, hook_installed=False)

    assert _explain("git push", repository) == (
        "BLOCK git's pre-push hook is not installed; run prek install (script/setup/bootstrap does it)"
    )


@pytest.mark.unit
def test_checks_the_repository_a_cd_moves_into(tmp_path: Path) -> None:
    """The installation check follows `cd` to the repository that actually pushes."""
    _initialize_repository(tmp_path / "repository", hook_installed=False)

    assert _explain("cd repository && git push", tmp_path).startswith("BLOCK git's pre-push hook is not installed")


@pytest.mark.unit
def test_blocks_invalid_payload(tmp_path: Path) -> None:
    """A payload the hook cannot read is blocked rather than waved through."""
    result = subprocess.run(
        ["bash", str(HOOK)], cwd=tmp_path, input="not json", capture_output=True, text=True, check=False
    )

    assert result.returncode == 2
    assert "not valid JSON" in result.stderr


@pytest.mark.unit
@pytest.mark.parametrize(
    "command",
    [
        "echo ok\ngit push --all",
        "echo ok # it's a comment\ngit push --all",
        "(git push --all)",
        "{ git push --all; }",
        "if true; then git push --all; fi",
        "time env -i git push --all",
        "diff <(git push --all) x",
        "echo `git push --all`",
        "cat <<'EOF'\nit's data\nEOF\ngit push --all",
        "git pu''sh --all",
        "git pu\\\nsh --all",
    ],
)
def test_finds_a_push_behind_shell_syntax(repository: Path, command: str) -> None:
    """A push hidden behind newlines, subshells, keywords, substitutions or quoting is still inspected."""
    assert _explain(command, repository) == _other_refs("--all")


REMIND = Path(__file__).parents[2] / ".agents" / "hooks" / "remind-change-review.sh"
HACI_REVIEW = "haci-review@ha-custom-integration-skills"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("command", "reminds"),
    [
        pytest.param("gh pr ready 12", True, id="ready"),
        pytest.param("script/test && gh pr ready", True, id="ready-after-a-chain"),
        pytest.param("gh pr ready --undo", False, id="back-to-draft"),
        pytest.param('echo "gh pr ready"', False, id="only-mentioned"),
        pytest.param("git status", False, id="unrelated"),
    ],
)
def test_change_review_reminder_before_a_pull_request_leaves_draft(
    tmp_path: Path, command: str, *, reminds: bool
) -> None:
    """The reminder adds context before gh pr ready and never blocks the call."""
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text(json.dumps({"enabledPlugins": {HACI_REVIEW: True}}))
    result = subprocess.run(
        ["bash", str(REMIND)],
        cwd=tmp_path,
        input=json.dumps({"tool_input": {"command": command}}),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    if reminds:
        assert "haci-change-review" in json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    else:
        assert result.stdout == ""


@pytest.mark.unit
@pytest.mark.parametrize(
    ("project", "local"),
    [
        pytest.param(None, None, id="not-enabled"),
        pytest.param(True, False, id="turned-off-locally"),
        pytest.param(False, None, id="off-in-the-project"),
    ],
)
def test_change_review_reminder_is_silent_without_the_plugin(
    tmp_path: Path, project: bool | None, local: bool | None
) -> None:
    """A developer who turned haci-review off gets no reminder about a review pass it no longer runs."""
    (tmp_path / ".claude").mkdir()
    if project is not None:
        (tmp_path / ".claude" / "settings.json").write_text(json.dumps({"enabledPlugins": {HACI_REVIEW: project}}))
    if local is not None:
        (tmp_path / ".claude" / "settings.local.json").write_text(json.dumps({"enabledPlugins": {HACI_REVIEW: local}}))
    result = subprocess.run(
        ["bash", str(REMIND)],
        cwd=tmp_path,
        input=json.dumps({"tool_input": {"command": "gh pr ready"}}),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout == ""
