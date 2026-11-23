"""Tests for script/.lib/agent_plugins.py, which installs the pinned agent plugins and checks the settings agree."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).parents[2]
MODULE = Path(__file__).parents[1] / ".lib" / "agent_plugins.py"
SPEC = importlib.util.spec_from_file_location("agent_plugins", MODULE)
assert SPEC is not None
assert SPEC.loader is not None
agent_plugins = importlib.util.module_from_spec(SPEC)
sys.modules["agent_plugins"] = agent_plugins
SPEC.loader.exec_module(agent_plugins)

MARKET = "example-skills"
SETTINGS = {
    "extraKnownMarketplaces": {
        MARKET: {"source": {"source": "github", "repo": "someone/example-skills", "ref": "v1.2.0"}},
        "unpinned": {"source": {"source": "github", "repo": "someone/other"}},
    },
    "enabledPlugins": {f"plan@{MARKET}": True, f"review@{MARKET}": True, f"triage@{MARKET}": False},
}
CODEX = f"""
[marketplaces.{MARKET}]
source_type = "git"
source = "https://github.com/someone/example-skills.git"
ref = "v1.2.0"

[plugins."plan@{MARKET}"]
enabled = true

[plugins."review@{MARKET}"]
enabled = true
"""


def _write(root: Path, claude: dict, copilot: dict, codex: str) -> None:
    (root / ".claude").mkdir()
    (root / ".claude/settings.json").write_text(json.dumps(claude), encoding="utf-8")
    (root / ".github/copilot").mkdir(parents=True)
    (root / ".github/copilot/settings.json").write_text(json.dumps(copilot), encoding="utf-8")
    (root / ".codex").mkdir()
    (root / ".codex/config.toml").write_text(codex, encoding="utf-8")


def _check(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(MODULE), "--check"], cwd=root, capture_output=True, text=True, check=False
    )


@pytest.mark.unit
def test_only_pinned_github_marketplaces_and_enabled_plugins_count() -> None:
    """A marketplace without a ref pins nothing, and a plugin set to false is not enabled."""
    assert agent_plugins.pins_from_settings(SETTINGS) == [
        agent_plugins.Pin(MARKET, "someone/example-skills", "v1.2.0", ("plan", "review"))
    ]


@pytest.mark.unit
def test_check_passes_when_all_three_agree(tmp_path: Path) -> None:
    """The same marketplace, ref and plugins in all three files pass."""
    _write(tmp_path, SETTINGS, SETTINGS, CODEX)
    assert _check(tmp_path).returncode == 0


@pytest.mark.unit
@pytest.mark.parametrize(
    ("copilot_ref", "codex"),
    [("v1.1.0", CODEX), ("v1.2.0", CODEX.replace('ref = "v1.2.0"', 'ref = "v1.1.0"')), ("v1.2.0", "")],
)
def test_check_fails_on_a_ref_or_marketplace_that_differs(tmp_path: Path, copilot_ref: str, codex: str) -> None:
    """A tag bumped in one file but not the others, or a marketplace missing for Codex, is reported."""
    copilot = json.loads(json.dumps(SETTINGS))
    copilot["extraKnownMarketplaces"][MARKET]["source"]["ref"] = copilot_ref
    _write(tmp_path, SETTINGS, copilot, codex)
    result = _check(tmp_path)
    assert result.returncode == 1
    assert MARKET in result.stderr


@pytest.mark.unit
def test_check_fails_when_a_plugin_is_enabled_for_one_agent_only(tmp_path: Path) -> None:
    """Enabling a plugin for Claude Code alone is a mismatch, not a per-agent choice."""
    copilot = json.loads(json.dumps(SETTINGS))
    copilot["enabledPlugins"][f"review@{MARKET}"] = False
    _write(tmp_path, SETTINGS, copilot, CODEX)
    assert _check(tmp_path).returncode == 1


@pytest.mark.unit
def test_check_fails_when_only_copilot_or_codex_pins(tmp_path: Path) -> None:
    """A pin outside .claude/settings.json has no source of truth, so it is reported rather than passed as nothing."""
    _write(tmp_path, {}, SETTINGS, CODEX)
    result = _check(tmp_path)
    assert result.returncode == 1
    assert "not pinned in .claude/settings.json" in result.stderr


@pytest.mark.unit
def test_no_pin_is_nothing_to_do(tmp_path: Path) -> None:
    """A repository that pins no marketplace passes and installs nothing."""
    result = _check(tmp_path)
    assert result.returncode == 0
    assert "nothing to do" in result.stdout


@pytest.mark.unit
def test_claude_installs_missing_plugins_at_local_scope() -> None:
    """A fresh checkout adds the marketplace at the pinned ref and installs each plugin locally, never at project scope."""
    pin = agent_plugins.pins_from_settings(SETTINGS)[0]
    commands = agent_plugins.claude_commands(pin, {}, set())
    assert commands == [
        ["claude", "plugin", "marketplace", "add", "someone/example-skills@v1.2.0", "--scope", "local"],
        ["claude", "plugin", "install", f"plan@{MARKET}", "--scope", "local"],
        ["claude", "plugin", "install", f"review@{MARKET}", "--scope", "local"],
    ]
    assert all("project" not in command for command in commands)


@pytest.mark.unit
def test_claude_respects_a_plugin_turned_off_locally() -> None:
    """A developer who set a plugin to false in settings.local.json does not get it back on the next bootstrap."""
    pin = agent_plugins.pins_from_settings(SETTINGS)[0]
    local = {"enabledPlugins": {f"plan@{MARKET}": False}}
    commands = agent_plugins.claude_commands(pin, local, set())
    assert ["claude", "plugin", "install", f"plan@{MARKET}", "--scope", "local"] not in commands
    assert ["claude", "plugin", "install", f"review@{MARKET}", "--scope", "local"] in commands


@pytest.mark.unit
def test_claude_updates_installed_plugins_only_when_the_ref_moved() -> None:
    """Installed plugins are left alone on a rerun and updated after a tag bump."""
    pin = agent_plugins.pins_from_settings(SETTINGS)[0]
    installed = {f"plan@{MARKET}", f"review@{MARKET}"}
    same = {"extraKnownMarketplaces": {MARKET: {"source": {"ref": "v1.2.0"}}}}
    older = {"extraKnownMarketplaces": {MARKET: {"source": {"ref": "v1.1.0"}}}}
    assert len(agent_plugins.claude_commands(pin, same, installed)) == 1
    assert ["claude", "plugin", "update", f"review@{MARKET}", "--scope", "local"] in agent_plugins.claude_commands(
        pin, older, installed
    )


@pytest.mark.unit
def test_this_repository_agrees_with_itself() -> None:
    """The three settings files of this repository pin the same marketplace, tag and plugins."""
    result = _check(ROOT)
    assert result.returncode == 0, result.stderr


@pytest.mark.unit
def test_renovate_finds_the_pin_in_every_settings_file() -> None:
    """Renovate raises the tag only where its patterns match, so a reformatted settings file must not hide the pin."""
    spec = importlib.util.spec_from_file_location(
        "version_guard", Path(__file__).parents[1] / ".lib" / "version_guard.py"
    )
    assert spec is not None
    assert spec.loader is not None
    version_guard = importlib.util.module_from_spec(spec)
    sys.modules["version_guard"] = version_guard
    spec.loader.exec_module(version_guard)
    readers = version_guard.readers(json.loads((ROOT / ".github" / "renovate.json").read_text(encoding="utf-8")))
    pins = agent_plugins.pins_from_settings(
        json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    )
    expected = {pin.repo: pin.ref for pin in pins}
    for name in (".claude/settings.json", ".github/copilot/settings.json", ".codex/config.toml"):
        text = (ROOT / name).read_text(encoding="utf-8")
        found = {
            dep: occurrences[0][0]
            for reader in readers
            if any(pattern.search(name) for pattern in reader.files)
            for dep, occurrences in version_guard.pins(text, reader).items()
        }
        assert found == expected, name
