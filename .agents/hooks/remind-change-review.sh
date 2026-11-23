#!/bin/bash

# .agents/hooks/remind-change-review.sh: Remind agents of the review pass before a pull request leaves draft
#
# Reads a PreToolUse payload on stdin and, when the shell command runs `gh pr ready` (not `--undo`), adds a note for
# the model without blocking the call. Silent where the haci-review plugin is not enabled: the project settings of
# Claude Code or Copilot turn it on, and either local settings file turns it off.
#
# Usage:
#   .agents/hooks/remind-change-review.sh < payload.json

set -euo pipefail

payload=$(cat)
[[ $payload == *"pr ready"* ]] || exit 0
command -v python3 >/dev/null 2>&1 || exit 0

root=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
HOOK_PAYLOAD="$payload" HOOK_ROOT="$root" python3 <<'PY' || exit 0
import json
import os
import re
import shlex
from pathlib import Path

PLUGIN = "haci-review@ha-custom-integration-skills"


def setting(name):
    try:
        return json.loads((Path(os.environ["HOOK_ROOT"]) / name).read_text()).get("enabledPlugins", {}).get(PLUGIN)
    except (OSError, ValueError, AttributeError):
        return None


projects = (setting(".claude/settings.json"), setting(".github/copilot/settings.json"))
overrides = (setting(".claude/settings.local.json"), setting(".github/copilot/settings.local.json"))
if True not in projects or False in overrides:
    raise SystemExit

try:
    tool_input = json.loads(os.environ["HOOK_PAYLOAD"]).get("tool_input", {})
except (KeyError, json.JSONDecodeError, AttributeError):
    raise SystemExit
command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
if isinstance(command, list):
    command = " ".join(command)

for part in re.split(r"&&|\|\||;|\||\n", command):
    try:
        words = shlex.split(part)
    except ValueError:
        continue
    if words[:3] == ["gh", "pr", "ready"] and "--undo" not in words:
        note = (
            "Before this pull request leaves draft, the review pass of the haci-change-review skill (haci-review "
            "plugin) runs over the commits since the last Agent-Review: trailer: simplify, the gates again, a review "
            "in a fresh context. If it has not run, say so instead of proceeding."
        )
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": note}}))
        break
PY
