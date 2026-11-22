---
name: "Shell Scripts"
description: "Script structure, shfmt formatting, and shellcheck suppression rules"
applyTo: "script/**, .devcontainer/*.sh, .agents/hooks/*.sh"
paths:
  - "script/**"
  - ".devcontainer/*.sh"
  - ".agents/hooks/*.sh"
---

# Shell Script Instructions

**Procedure:** [`blueprint-tooling`](../skills/blueprint-tooling/SKILL.md) — load it before changing anything under
`script/`. This file is the style rule set; the skill is which script a change belongs in, and when a hook script is
the answer instead — most files here are template-managed and an edit is reverted by the next sync.

**Applies to:** Shell scripts in `script/` (extensionless by convention), `.devcontainer/*.sh`, and
`.agents/hooks/*.sh`

## Formatting Standards

- **4 spaces** for indentation (never tabs)
- `#!/bin/bash` shebang on the first line
- `set -euo pipefail` after the shebang for strict error handling
- End files with a single newline

## Script Structure

```bash
#!/bin/bash

# script/name: One-line description
#
# Longer description if needed.
#
# Usage:
#   ./script/name [args]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."

# shellcheck source=script/.lib/output.sh
source "$SCRIPT_DIR/.lib/output.sh"
```

## Key Conventions

- Source `script/.lib/output.sh` for colored output and `activate_venv()`
- Use `activate_venv` (no `source .../activate` inline) to enter the Python venv
- Use `log_header`, `log_success`, `log_error` for consistent output
- Quote all variable references: `"$var"` not `$var`
- Use `[[ ]]` for conditionals, not `[ ]`
- Use `$()` for command substitution, not backticks
- **Never wait for an answer an agent cannot give.** A confirmation sits behind a `--yes` flag and stops with a
  message when stdin is not a terminal (`[[ -t 0 ]]`); call `sudo -n`, `apt-get -y` with
  `DEBIAN_FRONTEND=noninteractive`, and each tool's own non-interactive flag (`mise install --yes`, `npm ci`)
- No `command` prefix in a script: aliases do not expand in a script run as a file

## ShellCheck Suppressions

Suppress only specific rules, never blanket-disable:

```bash
# File-level (for library files where variables are intentionally unused):
# shellcheck disable=SC2034

# Line-level:
some_command  # shellcheck disable=SC2086
```

Common rules:

- `SC2034` — unused variable (use file-level in library scripts only)
- `SC2086` — unquoted variable (fix by quoting instead of suppressing)
- `SC2155` — declare and assign separately (always fix, don't suppress)

## Validation

**Recommended workflow — run fix scripts first:**

```bash
script/shell        # shfmt -i 4 -w  (auto-formats; silent on success)
script/shell-check  # shfmt -d + shellcheck -x  (reports remaining issues)
```

`script/shell` fixes formatting but does not run shellcheck (no auto-fix available).
Always follow with `script/shell-check` to catch logic and style issues.
