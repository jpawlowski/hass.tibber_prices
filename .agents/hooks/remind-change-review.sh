#!/bin/bash

# .agents/hooks/remind-change-review.sh: Remind agents of the review pass before a pull request leaves draft
#
# Reads a PreToolUse payload on stdin and, when the shell command runs `gh pr ready` (not `--undo`), adds a note for
# the model without blocking the call.
#
# Usage:
#   .agents/hooks/remind-change-review.sh < payload.json

set -euo pipefail

payload=$(cat)
[[ $payload == *"pr ready"* ]] || exit 0
command -v python3 >/dev/null 2>&1 || exit 0

HOOK_PAYLOAD="$payload" python3 <<'PY' || exit 0
import json
import os
import re
import shlex

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
            "Before this pull request leaves draft, the review pass in .agents/skills/blueprint-change-review/SKILL.md "
            "runs over what came since the last one: simplify, the gates again, a review in a fresh context. If it "
            "has not run, say so instead of proceeding."
        )
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": note}}))
        break
PY
