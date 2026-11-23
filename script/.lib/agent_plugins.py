"""
Install the agent plugins this repository enables, at the version it pins, and check that the agents agree.

The pin has one source: the ``ref`` of the GitHub marketplace in ``.claude/settings.json`` →
``extraKnownMarketplaces``, with the plugins its ``enabledPlugins`` turns on. ``.github/copilot/settings.json`` and
``.codex/config.toml`` repeat both; ``--check`` fails when they do not match it.

Without ``--check``, this installs for the agent CLIs found on ``PATH``:

- Claude Code reads a marketplace declared in project settings only after the folder is trusted interactively, so the
  marketplace and each enabled plugin are added at local scope, which writes the gitignored
  ``.claude/settings.local.json`` and leaves ``.claude/settings.json`` alone. A plugin set to ``false`` there stays off.
- Codex reads its marketplace from ``.codex/config.toml`` once the project is trusted; refreshing that one marketplace
  installs the enabled plugins.
- Copilot installs from ``.github/copilot/settings.json`` itself.

A failed install is reported and skipped; it never fails the caller.

Invoked by script/setup/agent-plugins; not intended to be run directly.
"""

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib

CLAUDE_SETTINGS = Path(".claude/settings.json")
CLAUDE_LOCAL = Path(".claude/settings.local.json")
COPILOT_SETTINGS = Path(".github/copilot/settings.json")
CODEX_CONFIG = Path(".codex/config.toml")
TIMEOUT = 180


@dataclass(frozen=True)
class Pin:
    """One GitHub marketplace at one ref, and the plugins enabled from it."""

    marketplace: str
    repo: str
    ref: str
    plugins: tuple[str, ...]

    @property
    def git_url(self) -> str:
        """The clone URL Codex records for the marketplace."""
        return f"https://github.com/{self.repo}.git"


def _json(path: Path) -> dict:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def pins_from_settings(settings: dict) -> list[Pin]:
    """Read every pinned GitHub marketplace, with its enabled plugins, from Claude-format settings."""
    pins = []
    enabled = [key for key, value in settings.get("enabledPlugins", {}).items() if value is True]
    for name, entry in settings.get("extraKnownMarketplaces", {}).items():
        source = entry.get("source", {}) if isinstance(entry, dict) else {}
        if source.get("source") != "github" or not source.get("repo") or not source.get("ref"):
            continue
        plugins = tuple(sorted(key.split("@", 1)[0] for key in enabled if key.endswith(f"@{name}")))
        pins.append(Pin(name, source["repo"], source["ref"], plugins))
    return pins


def codex_pins(config: dict) -> list[Pin]:
    """Read the same information from a Codex ``config.toml``."""
    pins = []
    enabled = [key for key, value in config.get("plugins", {}).items() if value.get("enabled") is True]
    for name, entry in config.get("marketplaces", {}).items():
        url = entry.get("source", "")
        repo = url.removeprefix("https://github.com/").removesuffix(".git")
        plugins = tuple(sorted(key.split("@", 1)[0] for key in enabled if key.endswith(f"@{name}")))
        pins.append(Pin(name, repo, entry.get("ref", ""), plugins))
    return pins


def mismatches(expected: list[Pin], copilot: list[Pin], codex: list[Pin]) -> list[str]:
    """Name every way the Copilot or Codex settings differ from the Claude Code pins."""
    problems = []
    for label, actual in ((str(COPILOT_SETTINGS), copilot), (str(CODEX_CONFIG), codex)):
        by_name = {pin.marketplace: pin for pin in actual}
        for pin in expected:
            other = by_name.get(pin.marketplace)
            if other is None:
                problems.append(f"{label}: marketplace {pin.marketplace} is missing")
            elif other != pin:
                problems.append(f"{label}: {other} differs from {CLAUDE_SETTINGS}: {pin}")
        names = {pin.marketplace for pin in expected}
        problems.extend(
            f"{label}: marketplace {pin.marketplace} is not pinned in {CLAUDE_SETTINGS}, the one source of the version"
            for pin in actual
            if pin.marketplace not in names
        )
    return problems


def claude_commands(pin: Pin, local: dict, installed: set[str]) -> list[list[str]]:
    """The Claude Code CLI calls that bring this checkout to the pin, respecting a plugin turned off locally."""
    known = local.get("extraKnownMarketplaces", {}).get(pin.marketplace, {}).get("source", {})
    moved = bool(known) and known.get("ref") != pin.ref
    commands = [["claude", "plugin", "marketplace", "add", f"{pin.repo}@{pin.ref}", "--scope", "local"]]
    for plugin in pin.plugins:
        plugin_id = f"{plugin}@{pin.marketplace}"
        if local.get("enabledPlugins", {}).get(plugin_id) is False:
            continue
        if plugin_id not in installed:
            commands.append(["claude", "plugin", "install", plugin_id, "--scope", "local"])
        elif moved:
            commands.append(["claude", "plugin", "update", plugin_id, "--scope", "local"])
    return commands


def _run(command: list[str]) -> bool:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=TIMEOUT, check=False)
    except (OSError, subprocess.TimeoutExpired) as err:
        print(f"⚠ {' '.join(command)}: {err}", file=sys.stderr)
        return False
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        print(f"⚠ {' '.join(command)}: {detail[-1] if detail else f'exit {result.returncode}'}", file=sys.stderr)
        return False
    return True


def _claude_installed() -> set[str]:
    try:
        result = subprocess.run(
            ["claude", "plugin", "list", "--json"], capture_output=True, text=True, timeout=TIMEOUT, check=False
        )
        entries = json.loads(result.stdout) if result.returncode == 0 else []
    except OSError, subprocess.TimeoutExpired, json.JSONDecodeError:
        return set()
    cwd = str(Path.cwd())
    return {
        entry["id"]
        for entry in entries
        if isinstance(entry, dict) and entry.get("scope") == "local" and entry.get("projectPath") == cwd
    }


def install(pins: list[Pin]) -> None:
    """Install for every agent CLI on PATH; report what was skipped."""
    if shutil.which("claude"):
        installed = _claude_installed()
        for pin in pins:
            for command in claude_commands(pin, _json(CLAUDE_LOCAL), installed):
                _run(command)
        print("✓ Claude Code: " + ", ".join(f"{p.marketplace}@{p.ref}" for p in pins))
    else:
        print("· Claude Code: claude not on PATH, skipped")
    if shutil.which("codex") and CODEX_CONFIG.is_file():
        for pin in pins:
            _run(["codex", "plugin", "marketplace", "upgrade", pin.marketplace])
        print("✓ Codex: refreshed from .codex/config.toml (takes effect once the project is trusted)")
    print("· Copilot: installs from .github/copilot/settings.json itself")


def main(argv: list[str]) -> int:
    """Check, then install unless ``--check`` was given."""
    pins = pins_from_settings(_json(CLAUDE_SETTINGS))
    codex = codex_pins(tomllib.loads(CODEX_CONFIG.read_text(encoding="utf-8"))) if CODEX_CONFIG.is_file() else []
    copilot = pins_from_settings(_json(COPILOT_SETTINGS))
    if not (pins or copilot or codex):
        print(f"· {CLAUDE_SETTINGS} pins no GitHub marketplace; nothing to do")
        return 0
    problems = mismatches(pins, copilot, codex)
    for problem in problems:
        print(f"✗ {problem}", file=sys.stderr)
    if problems:
        return 1
    print(f"✓ {CLAUDE_SETTINGS}, {COPILOT_SETTINGS} and {CODEX_CONFIG} pin the same plugins")
    if "--check" not in argv:
        install(pins)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
