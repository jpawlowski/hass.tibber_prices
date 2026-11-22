"""
Show what the blueprint changed in the files template sync never ships.

.templatesyncignore keeps project-owned files out of the sync, yet some of them — AGENTS.md, the sync workflow, the
developer documentation — still carry blueprint changes a project usually wants, and so do the workflows, which the
sync skips without a TEMPLATE_SYNC_TARGET_PAT. This fetches the blueprint, renders those files with this repository's
own names in place of the blueprint's, and prints what changed since the blueprint commit recorded in
.agents/blueprint-update.json; without a record, how each file differs from the blueprint. A file that already matches
the blueprint is not shown. This repository's names come from the identity initialize.sh recorded in the same file,
and are inferred from the code only where a repository predates that record.

Invoked by script/blueprint-update; not intended to be run directly.
"""

from collections.abc import Callable
import difflib
import fnmatch
import json
import os
from pathlib import Path
import re
import subprocess
import sys

STATE_FILE = Path(".agents/blueprint-update.json")
SYNC_WORKFLOW = ".github/workflows/template-sync.yml"
WATCHED = (
    "AGENTS.md",
    "CLAUDE.md",
    "AI_POLICY.md",
    "pyproject.toml",
    ".templatesyncignore",
    ".vscode/launch.json",
    ".vscode/tasks.json",
    ".devcontainer/.env",
    ".github/pull_request_template.md",
    ".github/ISSUE_TEMPLATE/*",
    ".github/workflows/*.yml",
    "docs/development/*.md",
)
NOT_WATCHED = ("docs/development/decisions/*",)
COORDINATOR_CLASS = r"^class (\w+?)DataUpdateCoordinator\b"

Reader = Callable[[str], str | None]


def git(*args: str, check: bool = True) -> str:
    """Run git without ever waiting for credentials and return its output."""
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=False, env=env)
    if check and result.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def commit_exists(ref: str) -> bool:
    """Whether ref names a commit in this repository's object store."""
    result = subprocess.run(["git", "cat-file", "-e", f"{ref}^{{commit}}"], capture_output=True, check=False)
    return result.returncode == 0


def at(ref: str) -> Reader:
    """Read files as they are at a git ref."""

    def read(path: str) -> str | None:
        result = subprocess.run(["git", "show", f"{ref}:{path}"], capture_output=True, text=True, check=False)
        return result.stdout if result.returncode == 0 else None

    return read


def working_tree(path: str) -> str | None:
    """Read a file from the working tree."""
    file = Path(path)
    return file.read_text(encoding="utf-8") if file.is_file() else None


def identity(read: Reader, paths: list[str], ref: str | None) -> dict[str, str]:
    """Return the names initialize.sh substitutes, as one tree spells them; ref None is the working tree."""
    found: dict[str, str] = {}
    for path in paths:
        parts = path.split("/")
        if len(parts) == 3 and parts[0] == "custom_components" and parts[2] == "manifest.json" and parts[1] != "hacs":
            found["domain"] = parts[1]
            manifest = json.loads(read(path) or "{}")
            found["title"] = manifest.get("name", "")
            match = re.search(r"github\.com/([^/\s]+)/([^/\s#?]+)", manifest.get("documentation", ""))
            if match:
                found["owner"], found["repository"] = match.groups()
            break
    if "domain" in found:
        where = [ref] if ref else []
        hits = git(
            "grep", "-h", "-E", COORDINATOR_CLASS, *where, "--", f"custom_components/{found['domain']}", check=False
        )
        match = re.search(COORDINATOR_CLASS, hits, re.MULTILINE)
        if match:
            found["prefix"] = match.group(1)
    match = re.search(r"Copyright \(c\) \d{4}(?:-\d{4})? (.+)", read("LICENSE") or "")
    if match:
        found["author"] = match.group(1).strip()
    return {key: value for key, value in found.items() if value}


def substitutions(blueprint: dict[str, str], project: dict[str, str]) -> list[tuple[str, str]]:
    """Pair every blueprint name with this repository's, longest first so no name is replaced inside another."""
    pairs: dict[str, str] = {}

    def pair(
        keys: tuple[str, ...],
        spell: Callable[[dict[str, str]], str],
        spell_project: Callable[[dict[str, str]], str] | None = None,
    ) -> None:
        if all(key in blueprint and key in project for key in keys):
            pairs[spell(blueprint)] = (spell_project or spell)(project)

    pair(("owner", "repository"), lambda names: f"{names['owner']}/{names['repository']}")
    pair(("repository",), lambda names: names["repository"])
    pair(("owner",), lambda names: f"@{names['owner']}")
    pair(("owner",), lambda names: f"%40{names['owner']}")
    pair(("domain",), lambda names: names["domain"])
    pair(("title",), lambda names: names["title"])
    pair(("title",), lambda names: names["title"][:1] + names["title"][1:].lower(), lambda names: names["title"])
    pair(("prefix",), lambda names: names["prefix"])
    pair(("author",), lambda names: names["author"])
    return sorted(((old, new) for old, new in pairs.items() if old and old != new), key=lambda p: -len(p[0]))


def verbatim(initialize: str | None) -> tuple[set[str], set[str]]:
    """Return the file names and paths the blueprint's initialize.sh leaves unrenamed, which are compared as they are."""

    def array(name: str) -> set[str]:
        body = re.search(rf"^\s*(?:local )?{name}=\((.*?)\n\s*\)", initialize or "", re.DOTALL | re.MULTILINE)
        return set(re.findall(r'^\s*"([^"]+)"', body.group(1), re.MULTILINE)) if body else set()

    return array("exclude_files"), {path.removeprefix("./") for path in array("exclude_paths")}


def watched(paths: list[str]) -> list[str]:
    """Return the watched files among paths."""
    return sorted(
        path
        for path in set(paths)
        if any(fnmatch.fnmatch(path, pattern) for pattern in WATCHED)
        and not any(fnmatch.fnmatch(path, pattern) for pattern in NOT_WATCHED)
    )


def source(override: str | None = None) -> tuple[str, str]:
    """Return the blueprint's clone URL and branch, as the sync workflow names them; override replaces the URL."""
    text = working_tree(SYNC_WORKFLOW) or ""
    repository = re.search(r"source_repo_path:\s*['\"]?([^\s'\"]+)", text)
    branch = re.search(r"upstream_branch:\s*['\"]?([^\s'\"]+)", text)
    if override:
        url = override
    elif repository:
        url = f"https://github.com/{repository.group(1)}.git"
    else:
        raise SystemExit(f"{SYNC_WORKFLOW} names no source_repo_path; pass --source")
    return url, branch.group(1) if branch else "main"


def load_state() -> dict[str, object]:
    """Read the record of the last blueprint commit this repository went through."""
    return json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.is_file() else {}


def main(argv: list[str]) -> int:
    """Fetch the blueprint and print, list or record what changed."""
    if Path("initialize.sh").exists():
        print("This is the blueprint or a copy not yet initialised; there is nothing to update from.", file=sys.stderr)
        return 2
    options = {arg for arg in argv if arg.startswith("--") and "=" not in arg}
    override = next((arg.split("=", 1)[1] for arg in argv if arg.startswith("--source=")), None)
    url, branch = source(override)
    upstream = f"refs/blueprint/{branch}"
    git("fetch", "--quiet", "--no-tags", url, f"+refs/heads/{branch}:{upstream}")
    head = git("rev-parse", upstream).strip()

    state = load_state()
    if "--record" in options:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps({**state, "reviewed": head}, indent=2) + "\n", encoding="utf-8")
        print(f"Recorded blueprint {head[:12]} as reviewed in {STATE_FILE}", file=sys.stderr)
        return 0

    reviewed = str(state.get("reviewed", ""))
    if reviewed and not commit_exists(reviewed):
        print(
            f"Recorded blueprint {reviewed[:12]} is not in the blueprint's history; comparing in full", file=sys.stderr
        )
        reviewed = ""

    read_upstream = at(upstream)
    blueprint_paths = git("ls-tree", "-r", "--name-only", upstream).splitlines()
    tracked = git("ls-files").splitlines()
    recorded = state.get("identity")
    project = {**identity(working_tree, tracked, None), **(recorded if isinstance(recorded, dict) else {})}
    pairs = substitutions(identity(read_upstream, blueprint_paths, upstream), project)
    verbatim_names, verbatim_paths = verbatim(read_upstream("initialize.sh"))

    def render(text: str | None, path: str) -> str | None:
        if text is None or path in verbatim_paths or Path(path).name in verbatim_names:
            return text
        for old, new in pairs:
            text = text.replace(old, new)
        return text

    if reviewed:
        candidates = watched(git("diff", "--name-only", reviewed, upstream).splitlines())
        read_reviewed = at(reviewed)
    else:
        candidates = watched(blueprint_paths + tracked)

    changed = []
    output = []
    for path in candidates:
        current = working_tree(path)
        upstream_text = read_upstream(path)
        if upstream_text is None and not reviewed:
            continue
        new = render(upstream_text, path)
        if reviewed:
            old, label = render(read_reviewed(path), path), f"blueprint {reviewed[:12]}"
        else:
            old, label = current, "this repository"
        if new in (old, current):
            continue
        changed.append(path)
        output.append(f"### {path}{'' if current is not None else ' (not in this repository)'}\n")
        output.extend(
            difflib.unified_diff(
                (old or "").splitlines(keepends=True),
                (new or "").splitlines(keepends=True),
                f"{label}/{path}",
                f"blueprint {head[:12]}/{path}",
            )
        )
        output.append("\n")

    since = f"since blueprint {reviewed[:12]}" if reviewed else "against this repository (nothing recorded yet)"
    if "--files" in options:
        print("\n".join(changed))
    elif changed:
        print("".join(output), end="")
    print(f"{len(changed)} watched file(s) changed {since}; blueprint is at {head[:12]}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
