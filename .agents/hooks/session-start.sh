#!/bin/bash

# .agents/hooks/session-start.sh: Prepare the toolchain and the development environment for an agent session
#
# Reads a SessionStart payload on stdin and works in the checkout its `cwd` names, which is the worktree rather than
# the main checkout when the two differ. Run by hand from a terminal, it works in the current directory and says
# what it found. Where the agent provides CLAUDE_ENV_FILE, every later command of the session applies `mise env`, so
# it gets the pinned tools and the Home Assistant venv. Then it reports or starts what is missing, never in the way of
# the session — everything slow runs in the background with its state in .local/<script>.status and its output in
# .local/<script>.log:
#
#   - In a cloud session (CLAUDE_CODE_REMOTE=true), which starts on a fresh machine every time, it runs
#     script/setup/bootstrap — mise, the pinned tools, Home Assistant and the test dependencies.
#   - Anywhere else — the dev container included, where VS Code runs it for every new agent session — it runs
#     script/setup/toolchain, which installs mise only where the environment belongs to the project, and tells the
#     agent when the checkout still needs script/setup/bootstrap, without running that unasked.
#
# A run already in progress, such as the dev container's own setup, is waited for rather than started again. Plain
# stdout becomes context for the agent; everything else goes to stderr. Never blocks a session: exits 0.
#
# Usage:
#   .agents/hooks/session-start.sh < payload.json
#   .agents/hooks/session-start.sh               # by hand, in the current checkout

set -euo pipefail

manual=0
dir=""
if [[ -t 0 ]]; then
    manual=1
    dir="$PWD"
else
    input="$(cat || true)"
    re='"cwd"[[:space:]]*:[[:space:]]*"([^"]*)"'
    if [[ $input =~ $re ]]; then
        dir="${BASH_REMATCH[1]}"
    fi
fi

note() {
    if [[ $manual -eq 1 ]]; then
        echo "session-start.sh: $1" >&2
    fi
}

if [[ -z $dir ]] || ! cd "$dir" 2>/dev/null; then
    echo "session-start.sh: no usable cwd in the hook input; run script/setup/bootstrap yourself" >&2
    exit 0
fi
if ! top="$(git rev-parse --show-toplevel 2>/dev/null)"; then
    note "$dir is not inside a git checkout; nothing to do"
    exit 0
fi
cd "$top"
if [[ ! -x script/setup/bootstrap ]]; then
    note "$top has no script/setup/bootstrap; nothing to do"
    exit 0
fi

# shellcheck source=script/.lib/output.sh
source script/.lib/output.sh

if [[ -n ${CLAUDE_ENV_FILE:-} ]]; then
    # shellcheck disable=SC2016 # expands when the agent reads the file, before each command
    echo 'PATH="$HOME/.local/bin:$PATH"; eval "$(MISE_HIDE_UPDATE_WARNING=1 mise env -s bash 2>/dev/null)"' \
        >>"$CLAUDE_ENV_FILE"
fi

in_background() {
    local launcher=(nohup)
    if command -v setsid >/dev/null 2>&1; then
        launcher=(setsid nohup)
    fi
    mkdir -p .local
    "${launcher[@]}" "script/setup/$1" >".local/$1.log" 2>&1 </dev/null &
}

bootstrap="$(run_state bootstrap)"
have_venv=0
if resolve_venv_path >/dev/null 2>&1; then
    have_venv=1
fi

if [[ ${CLAUDE_CODE_REMOTE:-} == "true" ]]; then
    if [[ $bootstrap == "running" ]]; then
        note "the cloud setup is already running"
    elif [[ $bootstrap == "failed" ]]; then
        echo "The background run of script/setup/bootstrap failed; .local/bootstrap.log says why. Fix it and run" \
            "script/setup/bootstrap again before script/test, script/lint, script/type-check or script/develop."
    elif [[ $have_venv -eq 1 ]]; then
        note "cloud session already set up; nothing to start"
    else
        in_background bootstrap
        echo "The development environment is being set up in the background (mise, the pinned tools, Home Assistant" \
            "and its test dependencies; several minutes). .local/bootstrap.status reads running, done or failed," \
            "and .local/bootstrap.log has the progress. Wait for done before running script/test, script/lint," \
            "script/type-check or script/develop."
    fi
    exit 0
fi

toolchain="$(run_state toolchain)"
if [[ $toolchain == "failed" ]]; then
    echo "The last run of script/setup/toolchain failed; .local/toolchain.log says why."
fi
if [[ $bootstrap != "running" && $toolchain != "running" && -x script/setup/toolchain ]]; then
    in_background toolchain
    note "checking the pinned tools in the background (.local/toolchain.log)"
fi

if [[ $have_venv -eq 0 ]]; then
    if [[ $bootstrap == "running" ]]; then
        echo "script/setup/bootstrap is already running (in the dev container: its own setup after creation). Wait" \
            "for .local/bootstrap.status to read done instead of starting it again before running script/test," \
            "script/lint, script/type-check or script/develop."
    else
        echo "This checkout has no development environment yet. Run script/setup/bootstrap (several minutes) before" \
            "script/test, script/lint, script/type-check or script/develop."
    fi
elif [[ $bootstrap == "failed" ]]; then
    echo "The last run of script/setup/bootstrap failed; .local/bootstrap.log says why."
else
    note "the development environment is ready; nothing to report"
fi
exit 0
