#!/bin/bash

# .agents/hooks/remind-dependency-sync.sh: Remind agents to mirror runtime dependencies
#
# Reads a PostToolUse payload on stdin and emits context only when exactly one
# side of the manifest.json/requirements.txt dependency contract was edited.

set -euo pipefail

payload=$(cat)
[[ $payload == *manifest.json* || $payload == *requirements.txt* ]] || exit 0
if ! kind=$(
    HOOK_PAYLOAD="$payload" python3 <<'PY'
import json
import os

try:
    payload = json.loads(os.environ["HOOK_PAYLOAD"])
except (KeyError, json.JSONDecodeError):
    raise SystemExit

tool_input = payload.get("tool_input", {})
if isinstance(tool_input, dict):
    paths = [tool_input.get("file_path", ""), tool_input.get("filePath", ""), tool_input.get("path", "")]
    searchable = json.dumps(tool_input)
else:
    paths = []
    searchable = str(tool_input)

manifest = any("/custom_components/" in path and path.endswith("/manifest.json") for path in paths if path)
manifest = manifest or ("custom_components/" in searchable and "manifest.json" in searchable)
requirements = any(path.endswith("/requirements.txt") for path in paths if path)
requirements = requirements or "requirements.txt" in searchable

if manifest != requirements:
    print("manifest" if manifest else "requirements")
PY
); then
    exit 0
fi

case $kind in
manifest)
    cat <<'JSON'
{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"If this manifest.json edit changed `requirements`, mirror the same pinned versions in the root requirements.txt. Ignore this reminder when dependencies did not change."}}
JSON
    ;;
requirements)
    cat <<'JSON'
{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"If this requirements.txt edit changed a runtime dependency, mirror the same pinned versions in custom_components/<domain>/manifest.json. Ignore this reminder for development-only changes."}}
JSON
    ;;
esac
