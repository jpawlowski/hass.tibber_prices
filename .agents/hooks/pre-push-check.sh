#!/bin/bash

# .agents/hooks/pre-push-check.sh: Keep agent pushes behind git's pre-push hook
#
# Reads a PreToolUse payload on stdin. script/push-gate, installed as git's pre-push hook, does the
# real checks but only sees the first ref of a push; this hook blocks what it cannot see or vet in the
# git commands a shell call actually runs: skipping git hooks, pushing several refs, tags or deletions,
# and pushing from a repository without the hook. Text that only mentions a push passes.
#
# Usage:
#   .agents/hooks/pre-push-check.sh
#   .agents/hooks/pre-push-check.sh --explain < payload.json

set -euo pipefail

explain=0
if [[ ${1:-} == "--explain" ]]; then
    explain=1
fi

payload=$(cat)
if ! command -v python3 >/dev/null 2>&1; then
    if [[ $payload == *git*push* ]]; then
        echo "BLOCKED: python3 is required to vet this push" >&2
        exit 2
    fi
    exit 0
fi

HOOK_PAYLOAD="$payload" HOOK_EXPLAIN="$explain" python3 <<'PY'
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

HOOK_TYPES = re.compile(r"^default_install_hook_types:.*\bpre-push\b", re.MULTILINE)
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*")
REDIRECTION = re.compile(r"\d*(?P<operator>&>>|&>|>>|>&|>\||<<<|<<-|<<|<&|<>|>|<)")
SEPARATORS = ";&|()`\n"
COMMAND_PREFIXES = {
    "!", "{", "builtin", "command", "do", "elif", "else", "env", "exec", "if", "nohup", "sudo", "then", "time",
    "until", "while",
}
MAX_NESTING = 4
DOUBLE_QUOTE_ESCAPES = '$`"\\\n'


def skip_heredoc(command, index, delimiter, strip_tabs):
    """Return the index just past the here-document body that starts at index."""
    while index < len(command):
        end = command.find("\n", index)
        line = command[index:] if end < 0 else command[index:end]
        index = len(command) if end < 0 else end + 1
        if (line.lstrip("\t") if strip_tabs else line) == delimiter:
            break
    return index


def split_commands(command):
    """Split a shell command line into the words of each simple command it runs.

    Operators, subshell parentheses, backticks and newlines end a command; redirections are dropped together with
    their target, and comments and here-document bodies are skipped. Raises ValueError on an unclosed quote.
    """
    commands = [[]]
    heredocs = []
    word = None
    redirection = ""
    quote = ""

    def end_word():
        nonlocal word, redirection
        if word is not None:
            if redirection in {"<<", "<<-"}:
                heredocs.append((word, redirection == "<<-"))
            elif not redirection:
                commands[-1].append(word)
            word, redirection = None, ""

    index = 0
    while index < len(command):
        char = command[index]
        following = command[index + 1 : index + 2]
        if char == quote:
            quote = ""
        elif quote == "'":
            word += char
        elif char == "\\" and (not quote or following in DOUBLE_QUOTE_ESCAPES):
            if following != "\n":
                word = (word or "") + following
            index += 2
            continue
        elif quote:
            word += char
        elif char in "'\"":
            quote = char
            word = word or ""
        elif char in " \t":
            end_word()
        elif char == "#" and word is None:
            end = command.find("\n", index)
            index = len(command) if end < 0 else end
            continue
        elif (char in "<>&" or (char.isdigit() and word is None)) and (match := REDIRECTION.match(command, index)):
            end_word()
            redirection = match.group("operator")
            index = match.end()
            continue
        elif char in SEPARATORS:
            end_word()
            redirection = ""
            commands.append([])
            if char == "\n":
                index += 1
                for delimiter, strip_tabs in heredocs:
                    index = skip_heredoc(command, index, delimiter, strip_tabs)
                heredocs.clear()
                continue
        else:
            word = (word or "") + char
        index += 1
    if quote:
        raise ValueError("No closing quotation")
    end_word()
    return [words for words in commands if words]


def find_shell_command(words, index):
    options_with_values = {"-O", "-o", "--init-file", "--rcfile"}
    index += 1
    while index < len(words):
        word = words[index]
        if word == "--":
            return None
        if word == "-c" or (word.startswith("-") and not word.startswith("--") and "c" in word[1:]):
            return words[index + 1] if index + 1 < len(words) else ""
        if word in options_with_values:
            index += 2
            continue
        if not word.startswith("-"):
            return None
        index += 1
    return None


def first_executable(words):
    """Return the index of the program a simple command runs, past assignments and prefix commands."""
    index = 0
    while index < len(words):
        word = words[index]
        is_assignment = ASSIGNMENT.fullmatch(word)
        is_prefix_option = index > 0 and words[index - 1] in COMMAND_PREFIXES and word.startswith("-")
        if not (is_assignment or word in COMMAND_PREFIXES or is_prefix_option):
            break
        index += 1
    return index


GIT_OPTIONS_WITH_VALUES = {"-C", "-c", "--config-env", "--exec-path", "--git-dir", "--namespace", "--work-tree"}
PUSH_OPTIONS_WITH_VALUES = {"--exec", "--receive-pack", "--push-option", "-o"}
OTHER_REFS = {"--all", "--branches", "--mirror", "--tags", "--follow-tags", "--delete", "-d", "--prune"}
CONFIG_READS = {"get", "--get", "--get-all", "--get-regexp", "--list", "-l"}
BYPASS = "skipping git hooks would skip script/push-gate; push without --no-verify or core.hooksPath"


def other_refs(what):
    return f"{what} sends refs script/push-gate cannot see; push the checked-out branch alone"


def sets_hooks_path(word):
    return "hookspath" in word.lower()


def inspect_git(words, index, cwd):
    """Return a block reason for one git command, the directory it pushes from, or None for anything else."""
    git_dir = ""
    configs = []
    index += 1
    while index < len(words) and words[index].startswith("-"):
        option = words[index]
        if option in GIT_OPTIONS_WITH_VALUES and index + 1 < len(words):
            if option == "-C":
                git_dir = words[index + 1]
            if option in {"-c", "--config-env"}:
                configs.append(words[index + 1].lower())
            index += 1
        elif option.startswith("-C"):
            git_dir = option[2:]
        index += 1
    if index >= len(words):
        return None
    subcommand, arguments = words[index], words[index + 1 :]

    if any(sets_hooks_path(config) for config in configs):
        return {"status": "block", "reason": BYPASS}
    if subcommand == "config":
        if any(map(sets_hooks_path, arguments)) and not CONFIG_READS.intersection(arguments):
            return {"status": "block", "reason": "setting core.hooksPath would skip script/push-gate"}
        return None
    if subcommand != "push":
        return None
    if any(config.startswith("push.followtags") for config in configs):
        return {"status": "block", "reason": other_refs("push.followTags")}

    positionals = []
    skip_value = False
    for argument in arguments:
        if skip_value:
            skip_value = False
        elif argument == "--no-verify":
            return {"status": "block", "reason": BYPASS}
        elif argument in OTHER_REFS or (re.fullmatch(r"-[a-z]+", argument) and "d" in argument):
            return {"status": "block", "reason": other_refs(argument)}
        elif argument == "--repo" or argument.startswith("--repo="):
            return {"status": "block", "reason": "--repo makes the pushed refs ambiguous; name the remote directly"}
        elif argument in PUSH_OPTIONS_WITH_VALUES:
            skip_value = True
        elif not argument.startswith("-"):
            positionals.append(argument)
    refspecs = positionals[1:]
    if len(refspecs) > 1:
        return {"status": "block", "reason": other_refs("a push of several refspecs")}
    if refspecs and refspecs[0].lstrip("+").startswith(":"):
        return {"status": "block", "reason": other_refs(refspecs[0])}
    directory = git_dir if os.path.isabs(git_dir) else os.path.join(cwd, git_dir)
    return {"status": "push", "directory": directory}


def inspect_nested(command, cwd, depth, kind):
    """Inspect a command embedded in another one, refusing to nest deeper than the limit."""
    if depth >= MAX_NESTING:
        return {"status": "block", "reason": f"{kind} nesting exceeds the inspection limit"}
    return inspect(command, cwd, depth + 1)


def inspect(command, cwd, depth=0):
    """Return the first block reason in a command line, or the directories its pushes start from."""
    try:
        segments = split_commands(command)
    except ValueError as err:
        return {"status": "block", "reason": f"cannot parse shell quoting: {err}"}

    pushes = []
    chain_dir = ""
    for words in segments:
        nested = [word for word in words if "$(" in word or "`" in word]
        if any(word.startswith("GIT_CONFIG") and sets_hooks_path(word) for word in words):
            return {"status": "block", "reason": BYPASS}

        index = first_executable(words)
        if index >= len(words):
            continue
        executable = os.path.basename(words[index])
        if executable == "cd":
            target = words[index + 2 : index + 3] if words[index + 1 : index + 2] == ["--"] else words[index + 1 :]
            chain_dir = os.path.join(cwd, target[0]) if target else chain_dir
            continue
        if executable in {"bash", "sh", "zsh"}:
            wrapped = find_shell_command(words, index)
            if wrapped == "":
                return {"status": "block", "reason": f"{executable} -c has no command to inspect"}
            if wrapped is not None:
                nested.append(wrapped)
        elif executable == "eval":
            nested.append(" ".join(words[index + 1 :]))
        elif executable == "git":
            result = inspect_git(words, index, chain_dir or cwd)
            if result and result["status"] == "block":
                return result
            if result:
                pushes.append(result["directory"])

        for inner in nested:
            result = inspect_nested(inner, chain_dir or cwd, depth, "command")
            if result["status"] == "block":
                return result
            pushes += result.get("directories", [])
    return {"status": "allow", "directories": pushes}


def missing_hook(directory):
    """Return why git's pre-push hook would not run for a push from directory, or None when it would."""
    toplevel = subprocess.run(["git", "-C", directory, "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if toplevel.returncode != 0:
        return None
    root = Path(toplevel.stdout.strip())
    config = root / ".pre-commit-config.yaml"
    if not config.is_file() or not HOOK_TYPES.search(config.read_text(encoding="utf-8")):
        return (
            "this repository does not install git's pre-push hook; add pre-push to default_install_hook_types and a "
            "pre-push hook running script/push-gate to .pre-commit-config.yaml (see the blueprint's), then run "
            "prek install"
        )
    hook = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--git-path", "hooks/pre-push"], capture_output=True, text=True
    )
    if not (root / hook.stdout.strip()).is_file():
        return "git's pre-push hook is not installed; run prek install (script/setup/bootstrap does it)"
    return None


def decide(payload):
    """Return None to allow the tool call, or the reason to block it."""
    tool_input = payload.get("tool_input", {})
    if isinstance(tool_input, dict):
        command = tool_input.get("command") or tool_input.get("cmd") or ""
        cwd = payload.get("cwd") or tool_input.get("cwd") or tool_input.get("workdir") or os.getcwd()
    else:
        command, cwd = tool_input, payload.get("cwd") or os.getcwd()
    if isinstance(command, list):
        command = shlex.join(map(str, command))
    result = inspect(str(command), str(cwd))
    if result["status"] == "block":
        return result["reason"]
    for directory in result["directories"]:
        if reason := missing_hook(directory):
            return reason
    return None


try:
    reason = decide(json.loads(os.environ["HOOK_PAYLOAD"]))
except (KeyError, json.JSONDecodeError):
    reason = "the hook payload is not valid JSON"

if os.environ["HOOK_EXPLAIN"] == "1":
    print("ALLOW" if reason is None else f"BLOCK {reason}")
    sys.exit(0)
if reason is not None:
    print(f"BLOCKED: {reason}", file=sys.stderr)
    sys.exit(2)
PY
