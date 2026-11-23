"""Tests for script/.lib/agent_cli.sh, which runs a one-shot prompt through an installed, signed-in agent CLI."""

from pathlib import Path
import shutil
import subprocess

import pytest

LIB = Path(__file__).parents[1] / ".lib" / "agent_cli.sh"

# Answers the sign-in checks from STUB_SIGNED_IN, echoes every other call and its stdin.
STUB = """#!/bin/bash
name="$(basename "$0")"
signed_in=0
[[ " ${STUB_SIGNED_IN:-} " == *" $name "* ]] && signed_in=1
case "$name $1 $2" in
"claude auth status") [[ $signed_in == 1 ]] && echo '{"loggedIn": true}' || echo '{"loggedIn": false}'; exit 0 ;;
"codex login status") [[ $signed_in == 1 ]] && exit 0 || exit 1 ;;
"opencode auth list") [[ $signed_in == 1 ]] && echo "anthropic oauth" || echo "No authenticated integrations"; exit 0 ;;
esac
echo "$name $*"
echo "cwd: $PWD"
for arg in "$@"; do
    case "$prev" in --output-last-message) echo "codex answer" >"$arg" ;; esac
    prev="$arg"
done
[[ -t 0 ]] || sed 's/^/stdin: /'
"""


def _bin(tmp_path: Path, *names: str) -> Path:
    folder = tmp_path / "bin"
    folder.mkdir(exist_ok=True)
    jq = shutil.which("jq")
    assert jq is not None
    (folder / "jq").symlink_to(jq)
    for name in names:
        stub = folder / name
        stub.write_text(STUB, encoding="utf-8")
        stub.chmod(0o755)
    return folder


def _run(tmp_path: Path, folder: Path, script: str, **env: str) -> subprocess.CompletedProcess[str]:
    (tmp_path / "prompt.md").write_text("Write the notes\n", encoding="utf-8")
    return subprocess.run(
        ["bash", "-c", f'source "{LIB}"; {script}'],
        cwd=tmp_path,
        env={"PATH": f"{folder}:/usr/bin:/bin", "HOME": str(tmp_path), **env},
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.unit
def test_auto_skips_clis_that_are_not_signed_in(tmp_path: Path) -> None:
    """With every CLI installed, the first one signed in wins — not merely the first one installed."""
    folder = _bin(tmp_path, "claude", "codex", "copilot", "opencode")

    result = _run(tmp_path, folder, 'agent_resolve && echo "$AGENT_NAME"', STUB_SIGNED_IN="codex opencode")

    assert result.stdout.strip() == "codex"


@pytest.mark.unit
def test_the_session_it_runs_in_comes_first(tmp_path: Path) -> None:
    """Inside a Claude Code session, its own CLI is taken even when another one would come first."""
    folder = _bin(tmp_path, "claude", "codex")

    result = _run(tmp_path, folder, 'agent_resolve && echo "$AGENT_NAME"', CLAUDECODE="1", STUB_SIGNED_IN="codex")

    assert result.stdout.strip() == "claude"


@pytest.mark.unit
def test_copilot_is_the_fallback_when_nothing_else_is_signed_in(tmp_path: Path) -> None:
    """Copilot cannot report its sign-in without a request, so it is tried after every CLI that can."""
    folder = _bin(tmp_path, "claude", "copilot")

    result = _run(tmp_path, folder, 'agent_resolve && echo "$AGENT_NAME"')

    assert result.stdout.strip() == "copilot"


@pytest.mark.unit
def test_nothing_signed_in_names_how_to_sign_in(tmp_path: Path) -> None:
    """The failure lists each installed CLI with its own sign-in command."""
    folder = _bin(tmp_path, "claude", "codex", "opencode")

    result = _run(tmp_path, folder, "agent_resolve")

    assert result.returncode == 1
    assert "codex: codex login" in result.stderr
    assert "opencode: opencode auth login" in result.stderr
    assert "claude: run claude and type /login" in result.stderr


@pytest.mark.unit
def test_any_takes_the_first_installed_for_a_session(tmp_path: Path) -> None:
    """An interactive session lets the user sign in there, so --any does not ask."""
    folder = _bin(tmp_path, "codex", "opencode")

    result = _run(tmp_path, folder, 'agent_resolve --any && echo "$AGENT_NAME"')

    assert result.stdout.strip() == "codex"


@pytest.mark.parametrize(
    ("cli", "signed_in", "message"),
    [
        pytest.param("codex", "", "it is not signed in — codex login", id="named-but-signed-out"),
        pytest.param("opencode", "opencode", "opencode is not installed", id="named-but-missing"),
    ],
)
@pytest.mark.unit
def test_a_named_cli_never_falls_back_to_another(tmp_path: Path, cli: str, signed_in: str, message: str) -> None:
    """Asking for one CLI fails with the reason rather than quietly using a different one."""
    folder = _bin(tmp_path, "claude", "codex")

    result = _run(tmp_path, folder, "agent_resolve", AGENT_CLI=cli, STUB_SIGNED_IN=f"claude {signed_in}")

    assert result.returncode == 1
    assert message in result.stderr


@pytest.mark.parametrize(
    ("cli", "expected"),
    [
        pytest.param("claude", "claude --print --tools  --model m1", id="claude"),
        pytest.param(
            "copilot",
            "copilot --silent --no-custom-instructions --deny-tool=write --deny-tool=shell --model m1",
            id="copilot",
        ),
        pytest.param("opencode", "opencode run --agent plan --archived --model m1 --file /", id="opencode"),
    ],
)
@pytest.mark.unit
def test_prompt_runs_without_tools_and_with_the_model(tmp_path: Path, cli: str, expected: str) -> None:
    """Each CLI gets its own non-interactive flags, no tools, and AGENT_MODEL when it is set."""
    folder = _bin(tmp_path, cli)

    result = _run(
        tmp_path, folder, "agent_resolve && agent_prompt prompt.md", AGENT_CLI=cli, AGENT_MODEL="m1", STUB_SIGNED_IN=cli
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith(expected)


@pytest.mark.unit
def test_codex_prints_only_its_last_message(tmp_path: Path) -> None:
    """Codex exec logs its progress; only the final answer reaches the caller."""
    folder = _bin(tmp_path, "codex")

    result = _run(tmp_path, folder, "agent_resolve && agent_prompt prompt.md", STUB_SIGNED_IN="codex")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "codex answer\n"


@pytest.mark.unit
def test_no_model_leaves_the_clis_default(tmp_path: Path) -> None:
    """An unset AGENT_MODEL passes no --model at all."""
    folder = _bin(tmp_path, "claude")

    result = _run(tmp_path, folder, "agent_resolve && agent_prompt prompt.md", STUB_SIGNED_IN="claude")

    assert "--model" not in result.stdout
    assert "stdin: Write the notes" in result.stdout


@pytest.mark.unit
def test_prompt_runs_outside_the_repository(tmp_path: Path) -> None:
    """The CLI starts in an empty directory, so it loads none of the repository's agent instructions or hooks."""
    folder = _bin(tmp_path, "claude")

    result = _run(tmp_path, folder, "agent_resolve && agent_prompt prompt.md", STUB_SIGNED_IN="claude")

    assert result.returncode == 0, result.stderr
    assert f"cwd: {tmp_path}\n" not in result.stdout
    assert "stdin: Write the notes" in result.stdout


@pytest.mark.unit
def test_a_github_token_alone_does_not_count_as_copilot_sign_in(tmp_path: Path) -> None:
    """GH_TOKEN is set for gh or CI without Copilot access, so a CLI that reports its sign-in goes first."""
    folder = _bin(tmp_path, "copilot", "opencode")

    result = _run(tmp_path, folder, 'agent_resolve && echo "$AGENT_NAME"', GH_TOKEN="x", STUB_SIGNED_IN="opencode")

    assert result.stdout.strip() == "opencode"


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        pytest.param({"AI_AGENT": "codex_cli"}, "codex", id="ai-agent-names-the-session"),
        pytest.param({"COPILOT_GITHUB_TOKEN": "t"}, "copilot", id="a-key-wins-before-any-probe"),
    ],
)
@pytest.mark.unit
def test_cheap_signals_come_before_sign_in_probes(tmp_path: Path, env: dict[str, str], expected: str) -> None:
    """The session marker and a key in the environment decide without starting any CLI."""
    folder = _bin(tmp_path, "claude", "codex", "copilot")

    result = _run(tmp_path, folder, 'agent_resolve && echo "$AGENT_NAME"', STUB_SIGNED_IN="claude", **env)

    assert result.stdout.strip() == expected


@pytest.mark.unit
def test_copilot_model_still_applies_to_copilot(tmp_path: Path) -> None:
    """COPILOT_MODEL keeps working for copilot when AGENT_MODEL is unset, and for no other CLI."""
    folder = _bin(tmp_path, "copilot")

    result = _run(tmp_path, folder, 'agent_resolve && echo "$AGENT_MODEL"', AGENT_CLI="copilot", COPILOT_MODEL="m2")

    assert result.stdout.strip() == "m2"


@pytest.mark.unit
def test_other_never_takes_the_sessions_own_cli(tmp_path: Path) -> None:
    """Inside a Claude Code session, --other skips claude even when it is the only one signed in besides codex."""
    folder = _bin(tmp_path, "claude", "codex")

    result = _run(
        tmp_path, folder, 'agent_resolve --other && echo "$AGENT_NAME"', CLAUDECODE="1", STUB_SIGNED_IN="claude codex"
    )

    assert result.stdout.strip() == "codex"


@pytest.mark.unit
def test_other_refuses_a_named_cli_that_is_the_sessions_own(tmp_path: Path) -> None:
    """AGENT_CLI naming the session's own CLI is not a second opinion, so --other fails instead of using it."""
    folder = _bin(tmp_path, "claude", "codex")

    result = _run(
        tmp_path, folder, "agent_resolve --other", AGENT_CLI="claude", CLAUDECODE="1", STUB_SIGNED_IN="claude"
    )

    assert result.returncode == 1
    assert "the CLI this session runs in" in result.stderr


@pytest.mark.unit
def test_other_with_only_the_sessions_cli_installed_says_so(tmp_path: Path) -> None:
    """When nothing but the session's own CLI is installed, the failure names it."""
    folder = _bin(tmp_path, "claude")

    result = _run(tmp_path, folder, "agent_resolve --other", CLAUDECODE="1", STUB_SIGNED_IN="claude")

    assert result.returncode == 1
    assert "other than claude" in result.stderr


@pytest.mark.parametrize(
    ("cli", "expected"),
    [
        pytest.param(
            "claude",
            "claude --print --restricted --strict-mcp-config --setting-sources user --permission-mode dontAsk "
            "--tools Read,Grep,Glob --model m1 --allowedTools Read Grep Glob",
            id="claude",
        ),
        pytest.param(
            "copilot",
            "copilot --silent --trust-folder --deny-tool=write --deny-tool=shell --model m1",
            id="copilot",
        ),
        pytest.param("opencode", "opencode run --agent plan --archived --model m1 --file /", id="opencode"),
    ],
)
@pytest.mark.unit
def test_review_runs_in_the_repository_reading_only(tmp_path: Path, cli: str, expected: str) -> None:
    """A reviewer starts in the directory it reviews, with reading tools only — no shell — and AGENT_MODEL."""
    folder = _bin(tmp_path, cli)
    (tmp_path / "repo").mkdir()

    result = _run(
        tmp_path,
        folder,
        "agent_resolve && agent_review repo prompt.md",
        AGENT_CLI=cli,
        AGENT_MODEL="m1",
        STUB_SIGNED_IN=cli,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith(expected)
    assert f"cwd: {tmp_path / 'repo'}\n" in result.stdout


@pytest.mark.unit
def test_codex_reviews_in_the_directory_in_a_read_only_sandbox(tmp_path: Path) -> None:
    """Codex starts in the directory with a read-only sandbox, and only its last message is printed."""
    folder = _bin(tmp_path, "codex")
    (tmp_path / "repo").mkdir()
    log = tmp_path / "calls"
    (folder / "codex").write_text(
        STUB.replace('echo "$name $*"', f'echo "$name $* @ $PWD" >>"{log}"; echo "$name $*"'), encoding="utf-8"
    )

    result = _run(tmp_path, folder, "agent_resolve && agent_review repo prompt.md", STUB_SIGNED_IN="codex")

    assert result.returncode == 0, result.stderr
    assert result.stdout == "codex answer\n"
    call = log.read_text()
    assert "codex exec --sandbox read-only --skip-git-repo-check --output-last-message" in call
    assert call.rstrip().endswith(f"@ {tmp_path / 'repo'}")
