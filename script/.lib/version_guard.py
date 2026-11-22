"""
Keep this repository's newer versions when a template sync would lower them.

Compares the version pins in the working tree with those at a base ref — the repository's own state before the
sync — and restores every pin the sync lowered. Which files hold pins and how to read them follows the dependency
bots: the managers .github/renovate.json enables, with their default file patterns, and its custom regex managers.
Prints a Markdown report of what it restored.

Invoked by script/template-sync-guard; not intended to be run directly.
"""

from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess
import sys

RENOVATE_CONFIG = Path(".github/renovate.json")

# The managers Dependabot and Renovate both raise here, with Renovate's default file patterns. Each pattern names the
# dependency (`key`), its version (`version`) and the text a restore replaces (`value`).
MANAGERS: dict[str, tuple[list[str], re.Pattern[str]]] = {
    "mise": (
        [r"(^|/)\.?mise\.toml$", r"(^|/)\.?mise/config\.toml$"],
        re.compile(r'^(?P<key>[A-Za-z0-9_.:@/"\'-]+)\s*=\s*(?P<value>"(?P<version>\d[^"]*)")', re.MULTILINE),
    ),
    "pip_requirements": (
        [r"(^|/)[\w-]*requirements([-._]\w+)?\.(txt|pip)$"],
        re.compile(
            r"^(?P<key>[A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?==(?P<value>(?P<version>[^\s;#]+))", re.MULTILINE
        ),
    ),
    "npm": (
        [r"(^|/)package\.json$"],
        re.compile(r'"(?P<key>(?:@[^"/]+/)?[^"@/][^"]*)":\s*(?P<value>"(?P<version>\d[^"]*)")'),
    ),
    "github-actions": (
        [r"(^|/)(workflow-templates|\.github/(workflows|actions))/.+\.ya?ml$", r"(^|/)action\.ya?ml$"],
        re.compile(r"uses:\s*(?P<key>[^@\s]+)@(?P<value>[0-9a-f]{40}\s*#\s*(?P<version>v?\d\S*))"),
    ),
}
PRE_RELEASE = re.compile(r"[-._]?(dev|a|alpha|b|beta|c|rc|pre|preview)[-._]?(\d*)", re.IGNORECASE)
PRE_RELEASE_ORDER = {"dev": 0, "a": 1, "alpha": 1, "b": 2, "beta": 2, "c": 3, "rc": 3, "pre": 3, "preview": 3}

Occurrence = tuple[str, tuple[int, int], str]


@dataclass(frozen=True, slots=True)
class Reader:
    """One way to find pins: which files it applies to, and the pattern that reads them."""

    files: tuple[re.Pattern[str], ...]
    pattern: re.Pattern[str]
    key: str | None = None


@dataclass(frozen=True, slots=True)
class Restore:
    """One pin the sync lowered and the value kept instead."""

    path: str
    key: str
    template: str
    kept: str


def version_key(version: str) -> tuple[tuple[int, ...], tuple[int, int, int]] | None:
    """Order versions numerically, with a pre-release below the release it leads to; None when there is no number."""
    match = re.match(r"[vV]?(\d+(?:\.\d+)*)(.*)", version)
    if not match:
        return None
    numbers = tuple(int(part) for part in match.group(1).split("."))
    pre = PRE_RELEASE.match(match.group(2))
    stage = (0, PRE_RELEASE_ORDER[pre.group(1).lower()], int(pre.group(2) or 0)) if pre else (1, 0, 0)
    return numbers, stage


def lower(new: str, old: str) -> bool:
    """Whether new is a lower version than old; versions that cannot be read never count as lower."""
    new_key, old_key = version_key(new), version_key(old)
    if new_key is None or old_key is None:
        return False
    width = max(len(new_key[0]), len(old_key[0]))
    new_numbers = new_key[0] + (0,) * (width - len(new_key[0]))
    old_numbers = old_key[0] + (0,) * (width - len(old_key[0]))
    return (new_numbers, new_key[1]) < (old_numbers, old_key[1])


def renovate_pattern(pattern: str) -> re.Pattern[str]:
    """Turn a Renovate file pattern or match string into a Python regex."""
    if len(pattern) > 1 and pattern.startswith("/") and pattern.endswith("/"):
        pattern = pattern[1:-1]
    return re.compile(re.sub(r"\(\?<(?![=!])", "(?P<", pattern))


def readers(settings: dict) -> list[Reader]:
    """Return the pin readers the dependency bots' configuration implies."""
    enabled = settings.get("enabledManagers", tuple(MANAGERS))
    found = []
    for manager in enabled:
        if manager in MANAGERS:
            defaults, pattern = MANAGERS[manager]
            extra = settings.get(manager, {}).get("managerFilePatterns", [])
            found.append(Reader(tuple(renovate_pattern(file) for file in [*defaults, *extra]), pattern))
    if "custom.regex" not in enabled:
        return found
    for custom in settings.get("customManagers", []):
        files = tuple(renovate_pattern(file) for file in custom.get("managerFilePatterns", []))
        for match_string in custom.get("matchStrings", []):
            pattern = renovate_pattern(match_string)
            if "currentValue" not in pattern.groupindex:
                continue
            key = None if "depName" in pattern.groupindex else custom.get("depNameTemplate", match_string)
            found.append(Reader(files, pattern, key))
    return found


def pins(text: str, reader: Reader) -> dict[str, list[Occurrence]]:
    """Return every pin a reader finds, per dependency in file order: (version, span of the value, value)."""
    found: dict[str, list[Occurrence]] = {}
    groups = reader.pattern.groupindex
    value, version = ("value", "version") if "value" in groups else ("currentValue", "currentValue")
    for match in reader.pattern.finditer(text):
        key = reader.key or match["key" if "key" in groups else "depName"]
        found.setdefault(key, []).append((match[version], match.span(value), match[value]))
    return found


def base_text(base: str, path: str) -> str | None:
    """Return a file's content at the base ref, or None when it did not exist there."""
    result = subprocess.run(["git", "show", f"{base}:{path}"], capture_output=True, text=True, check=False)
    return result.stdout if result.returncode == 0 else None


def tracked_files() -> list[str]:
    """Return the files of the working tree."""
    return subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True).stdout.splitlines()


def guard(base: str, *, fix: bool) -> list[Restore]:
    """Find, and with fix restore, every pin the working tree has lower than at the base ref."""
    config = json.loads(RENOVATE_CONFIG.read_text(encoding="utf-8")) if RENOVATE_CONFIG.is_file() else {}
    all_readers = readers(config)
    restores = []
    for path in tracked_files():
        applicable = [reader for reader in all_readers if any(file.search(path) for file in reader.files)]
        if not applicable or not Path(path).is_file():
            continue
        before = base_text(base, path)
        if before is None:
            continue
        text = Path(path).read_text(encoding="utf-8")
        replacements: set[tuple[tuple[int, int], str]] = set()
        for reader in applicable:
            kept = pins(before, reader)
            for key, occurrences in pins(text, reader).items():
                for (version, span, _), (old_version, _, old_value) in zip(
                    occurrences, kept.get(key, []), strict=False
                ):
                    if lower(version, old_version):
                        restores.append(Restore(path, key, version, old_version))
                        replacements.add((span, old_value))
        if fix and replacements:
            for (start, end), value in sorted(replacements, reverse=True):
                text = text[:start] + value + text[end:]
            Path(path).write_text(text, encoding="utf-8")
    return list(dict.fromkeys(restores))


def report(restores: list[Restore], *, fix: bool) -> str:
    """Write the restores as a Markdown section for the pull request and the job summary."""
    verb = "kept" if fix else "would keep"
    lines = [
        "### Newer versions kept",
        "",
        (
            "The template sync would have lowered these pins below what this repository already uses, so the sync"
            f" {verb} this repository's version:"
        ),
        "",
        "| File | Dependency | Template | Kept |",
        "| ---- | ---------- | -------- | ---- |",
    ]
    lines += [f"| `{r.path}` | `{r.key}` | {r.template} | {r.kept} |" for r in restores]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    """Guard the working tree against the base ref given on the command line."""
    args = [arg for arg in argv if not arg.startswith("--")]
    fix = "--check" not in argv
    if len(args) != 1:
        print("usage: version_guard.py <base-ref> [--check]", file=sys.stderr)
        return 2
    restores = guard(args[0], fix=fix)
    if restores:
        print(report(restores, fix=fix), end="")
    return 1 if restores and not fix else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
